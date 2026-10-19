"""A quote is checked against a DIFFERENT drawing of the paper than the model read.

WHY THIS FILE EXISTS
--------------------
`quotes.classify` requires a quote to be one contiguous span of the paper, and
that rule was suspected of being the thing capping provenance at about half.
MEASURED 2026-08-12 over all 637 quotes actually supplied across the archived
runs (429 finding quotes, 208 tool-call quotes), it is not. Of the 228 that
failed to locate, these many stop being locatable if that one substitution is
removed -- the counts overlap, because a table row can need three of them:

    cell-separator rendering (`|` against a space)           35
    hyphen spacing (`group -based`, `- 0.01`)                27
    undecoded HTML entities (`&lt;` for `<`)                 19
    ligature splits (`fi nal`, `signi fi cant`)               6
    `(cid:2)` / `GLYPH<n>` debris                             4
    the model's own wrapping quote marks                      1

    genuinely more than one span                              9   (REJECTED)

The model copies from what an extraction tool showed it; `build_haystack`
searches text produced by other extractors, which the model never saw. Every
case above is ONE PAPER SEEN TWICE, reported to the reader as a quote that is
not in the paper -- the house failure pattern, our gap in the grammar of a claim
about the authors.

So the fix folds the RENDERING on both sides and leaves the rule alone. Each
test below pins one measured cause, and the last group pins the property that
makes the fold safe: it is many-to-one on typography and the IDENTITY ON DIGITS,
so no fold can put a number into a quote that the paper does not print.
"""
import pytest

from metascience_agent.quotes import (
    build_haystack, classify, fold_haystack, fold_rendering, normalise,
)


def hay(text: str) -> tuple[dict, dict]:
    h = {"the paper's text": normalise(text)}
    return h, fold_haystack(h)


class TestTheMeasuredCauses:
    """One test per failure bucket found in the archive, with its real string."""

    def test_an_undecoded_entity_is_the_same_sentence(self):
        """`p &lt; 0.05` reached the model from a markdown extraction; the JATS
        text we search holds `p < 0.05`. Seen 17 times in the archive, including
        five copies of one honest sentence in 10.1002--ajcp.70049."""
        h, f = hay("effects, defined as p < 0.05; momentary observations at "
                   "level 1 were nested within persons")
        v = classify("reflect significant effects, defined as p &lt; 0.05", h, f)
        assert v["quote_verified"] == "stitched"     # `reflect` is not in ours
        v = classify("defined as p &lt; 0.05; momentary observations", h, f)
        assert v["quote_verified"] == "verbatim"

    def test_a_ligature_split_by_the_pdf_is_the_same_word(self):
        """10.1002--ajcp.70049 prints `final`; its text layer emits `fi nal`,
        and the model quoted what it was shown. Reporting that unlocatable
        marks the author for our extractor's ligature handling."""
        h, f = hay("Variables were retained in the final models as covariates "
                   "only if bivariate associations had p values under 0.10.")
        assert classify(
            "Variables were retained in the fi nal models as covariates",
            h, f)["quote_verified"] == "verbatim"

    def test_a_hyphen_the_extractor_spaced_is_the_same_word(self):
        """`group -based` / `Number of evidence - based programs`: the space
        around the hyphen is the extractor's, not the paper's."""
        h, f = hay("Number of evidence-based programs (mean, SD) 1.67 (2.15)")
        assert classify("Number of evidence - based programs (mean, SD) | 1.67 (2.15)",
                        h, f)["quote_verified"] == "verbatim"

    def test_a_table_row_drawn_with_pipes_matches_one_drawn_with_spaces(self):
        """`build_haystack` joins table cells with ` | `; a model may write the
        row with pipes, with tabs, or with neither. The cell BOUNDARY is a
        rendering decision of whichever extractor drew the row, so it cannot be
        the thing that decides whether a row was quoted."""
        h = {"a table": normalise("Inclusive decision making | 8.57 (3.03) | .01")}
        f = fold_haystack(h)
        assert classify("Inclusive decision making\t8.57 (3.03)\t.01",
                        h, f)["quote_verified"] == "verbatim"
        assert classify("| Inclusive decision making | 8.57 (3.03) | .01 |",
                        h, f)["quote_verified"] == "verbatim"

    def test_cid_debris_is_not_a_difference_in_content(self):
        """`glyphs.py` measures `(cid:n)` on 400 papers. One extractor emits it
        where another prints the glyph, and 10.1007--s00702-004-0248-2 was
        quoted as `65(cid:2)1.17` against a haystack holding the same cell
        without the marker. Both are the same cell."""
        h, f = hay("Age (years) means 65 1.17 and 65 1.32 by arm")
        assert classify("means 65(cid:2)1.17 and 65(cid:2)1.32",
                        h, f)["quote_verified"] == "verbatim"
        assert "cid" not in fold_rendering("65(cid:2)1.17")

    def test_the_models_own_quotation_marks_are_not_the_papers(self):
        """A real finding quoted `'The datasets analyzed ... upon reasonable
        request.'`. The sentence is verbatim; the apostrophes are the model
        showing that it is quoting, and they alone made it unlocatable."""
        h, f = hay("The datasets analyzed for the current study are available "
                   "from Drs. Brown and Chilenski upon reasonable request.")
        assert classify(
            "'The datasets analyzed for the current study are available from "
            "Drs. Brown and Chilenski upon reasonable request.'",
            h, f)["quote_verified"] == "verbatim"

    def test_a_relational_operator_has_two_spellings(self):
        """`α ≤ .05` in 10.1001--jamanetworkopen.2023.37679, quoted as
        `alpha <= .05`. NFKC leaves `≤` alone, so the two strings could never
        meet however faithful the copy."""
        h, f = hay("Test-specific significance levels were assessed at α ≤ .05.")
        assert classify("significance levels were assessed at α <= .05",
                        h, f)["quote_verified"] == "verbatim"
        assert normalise("p ≥ .05") == "p >= .05"


class TestTheFoldCannotManufactureANumber:
    """The fabrication guarantee rests on ONE property: the fold is the identity
    on digits. It may merge typography; it may never let a quote claim a value
    the paper does not print. These pin that directly."""

    def test_no_fold_introduces_a_digit(self):
        """The invariant is one-directional and that is the point: the fold may
        DROP the digits inside an extractor's `(cid:2)` marker, which are not
        the paper's, but it may never put a digit into a quote. Only the second
        direction can manufacture support."""
        for raw in ("p &lt; 0.05", "65(cid:2)1.17", "a | b | 3.14",
                    "fi nal 12,345", "group -based 0.75", "α ≤ .05",
                    "GLYPH<237> 4.2", "&#x2264; 7"):
            n = normalise(raw)
            introduced = set(fold_rendering(n)) - set(n)
            assert not any(c.isdigit() for c in introduced), (raw, introduced)

    def test_content_digits_survive_the_fold_intact(self):
        """Where there is no debris marker to drop, the digit sequence is
        preserved exactly -- so a value cannot be reshaped into another value."""
        for raw in ("p &lt; 0.05", "a | b | 3.14", "fi nal 12,345",
                    "group -based 0.75", "α ≤ .05"):
            n = normalise(raw)
            assert ([c for c in n if c.isdigit()]
                    == [c for c in fold_rendering(n) if c.isdigit()]), raw

    def test_a_dropped_separator_becomes_a_SPACE_never_nothing(self):
        """The one way this fold could manufacture a value: if `|` or `(cid:2)`
        were deleted rather than replaced, two adjacent cells `4 | 2` would
        become the number `42`, which the paper never printed.

        This is not hypothetical framing. `Sex | Male 114071243 ...` in
        10.1001--jamanetworkopen.2023.37679 was promoted from `stitched` to
        `verbatim` by this change, and the paper's own XML prints that count as
        `114 071 243`. It is a correct promotion -- the JATS table extractor,
        which is what the model read, emits the digits unspaced, and the fold
        only removed the pipes. Had the fold deleted separators instead of
        spacing them, the same code would have been assembling numbers.
        """
        assert fold_rendering("4 | 2") == "4 2"
        assert fold_rendering("4|2") == "4 2"
        assert fold_rendering("4(cid:2)2") == "4 2"
        assert fold_rendering("4 GLYPH<237> 2") == "4 2"

    def test_a_wrong_value_still_fails_after_folding(self):
        """The fold must not turn a misquote into a quotation. 8.57 is in the
        paper; 8.58 is not, and no amount of separator folding may bridge that."""
        h, f = hay("Inclusive decision making | 8.57 (3.03) | .01")
        assert classify("Inclusive decision making | 8.58 (3.03) | .01",
                        h, f)["quote_verified"] == "unverified"

    def test_a_number_may_not_match_inside_a_longer_one_after_folding(self):
        """`_contains_bounded`'s digit-boundary guard is what stops `n = 42`
        verifying against a paper that only says `n = 428`. The folded haystack
        is searched by the same function, so the guard must survive the fold."""
        h, f = hay("the final sample was n = 428 after exclusions")
        assert classify("the final sample was n = 42", h, f)["quote_verified"] \
            == "unverified"

    def test_whitespace_is_not_folded_away(self):
        """MEASURED: removing ALL whitespace would recover 26 further quotes, by
        making `236 551 727` and `236551727` the same string -- a guess about
        where a digit boundary lies. `glyphs.py` records the project's rule that
        a guess about a digit is the one repair never to make, so this is
        DELIBERATELY still unlocatable and the test pins the choice.

        It lands on `unverified` rather than `stitched` because `_number_forms`
        does not build the space-grouped spelling either -- the same refusal,
        stated once more one layer down."""
        h, f = hay("representing 236 551 727 US adults, by veteran status")
        assert classify("representing 236551727 US adults, by veteran status",
                        h, f)["quote_verified"] == "unverified"

    def test_a_fabricated_sentence_is_still_not_a_quotation(self):
        h, f = hay("Participants completed the task. Attrition was 12 of 50.")
        assert classify("Every participant improved substantially on all measures",
                        h, f)["quote_verified"] == "unverified"


class TestTheFoldNeverWeakensAVerdict:
    """A quote that located before must still locate. The second pass runs only
    after the first has failed, so this is true by construction -- pinned here
    because a later refactor could reorder it and silently downgrade real
    provenance into `stitched`, which reads to a reader as "we composed this"."""

    def test_a_plain_verbatim_quote_is_unaffected(self):
        h, f = hay("The interaction was reliable, F(1, 38) = 7.21, p = .011.")
        v = classify("The interaction was reliable, F(1, 38) = 7.21", h, f)
        assert v["quote_verified"] == "verbatim"
        assert v["quote_source"] == "the paper's text"

    def test_the_folded_copy_still_names_a_source_the_reader_can_open(self):
        """A hit in the folded haystack must report the SOURCE NAME, not an
        internal label: it is the same passage of the same file."""
        h = {"a table": normalise("Inclusive decision making | 8.57 (3.03) | .01")}
        v = classify("Inclusive decision making\t8.57 (3.03)\t.01",
                     h, fold_haystack(h))
        assert v["quote_source"] == "a table"

    def test_classify_still_works_without_a_prebuilt_folded_haystack(self):
        """Callers outside the two annotation loops pass only the haystack. They
        must get the same verdict, at the cost of folding per call."""
        h, _ = hay("Number of evidence-based programs (mean, SD) 1.67 (2.15)")
        assert classify("Number of evidence - based programs (mean, SD) | 1.67 (2.15)",
                        h)["quote_verified"] == "verbatim"

    def test_an_empty_quote_is_absent_not_unverified(self):
        h, f = hay("anything at all")
        assert classify("", h, f)["quote_verified"] == "absent"
        assert classify("   ", h, f)["quote_verified"] == "absent"


class TestTheLinkedDataGap:
    """The ONE quote in the whole archive whose numbers appear nowhere in our
    haystack was not a fabrication. It was a row of
    `..._linked_data_dataverse_..._CEA_CARS.xlsx`, sitting in the paper's own
    directory, which `_supplements` refused to open because the filename said
    `linked_data` rather than `supplement`. A deposited dataset is the paper's
    evidence; declining to read it turned a filename rule of ours into a verdict
    about somebody's quote."""

    def test_a_linked_data_workbook_beside_the_paper_is_read(self, tmp_path):
        import openpyxl
        wb = openpyxl.Workbook()
        wb.active.append(["patient_ID", "arm", "utility"])
        wb.active.append(["P-2-29", "Placebo", 0.17381666666666667])
        wb.save(tmp_path / "10.3390--x_linked_data_dataverse_CEA_CARS.xlsx")
        h = build_haystack(tmp_path)
        assert "a supplement" in h, h
        assert "p-2-29" in h["a supplement"]
        # The workbook stores 17 significant figures as 16; the point of the
        # test is that the FILE is opened at all, not that Excel round-trips.
        assert "0.1738166666666667" in h["a supplement"]

    def test_an_unrelated_workbook_is_still_not_read(self, tmp_path):
        """The widening is to deposited data, not to every spreadsheet that
        happens to share a folder -- a haystack that accepts anything nearby
        would certify quotes from a file that is not the paper's evidence."""
        import openpyxl
        wb = openpyxl.Workbook()
        wb.active.append(["scratch", 999.123])
        wb.save(tmp_path / "my_notes.xlsx")
        assert "a supplement" not in build_haystack(tmp_path)


class TestWhatWasMeasuredAndRejected:
    """Multi-span was the hypothesis this investigation was sent to confirm. It
    is recorded here as a REFUSAL, with its number, so nobody re-opens it from
    intuition: k disjoint verified spans recover 9 of 637 quotes (1.4%), and the
    variant that also drops the same-source and reading-order constraints -- the
    one that lets a model assemble support from opposite ends of a paper --
    recovers 15 (2.4%)."""

    def test_two_spans_that_do_not_adjoin_are_not_a_quotation(self):
        h, f = hay("The treatment group improved on the primary outcome. "
                   "Many pages of unrelated method text sit here. "
                   "For the secondary outcome, p < 0.001.")
        v = classify("The treatment group improved on the primary outcome, p < 0.001",
                     h, f)
        assert v["quote_verified"] == "stitched"
        assert "composed by the review" in v["quote_problem"]


class TestEntitiesDoNotReachTheReader:
    """The promise is "as printed in the paper", and the paper printed `<`.

    MEASURED 2026-08-16 over the 16 cached docling extractions: 176 `&lt;`/`&gt;`
    and 201 `&amp;`, so essentially every threshold p-value in the corpus is
    entity-encoded on arrival. Four of them reached the delivered PNAS report as
    a literal `&lt;` inside the "As printed in the paper" line.

    Decoding makes the line MORE faithful, not less -- the encoding is our
    extractor's, not the author's -- and it matches the checking path, where
    `quotes.py` already unescapes the haystack before matching.
    """

    def test_a_threshold_p_renders_as_the_paper_printed_it(self):
        from metascience_agent.report_render import _quote_line
        line = _quote_line("- ", "F (1,13) = 4.65; P &lt; 0.05", "the paper's text", "exact")
        assert "P < 0.05" in line
        assert "&lt;" not in line

    def test_ampersand_and_gt_are_decoded_too(self):
        from metascience_agent.report_render import _quote_line
        line = _quote_line("- ", "Smith &amp; Jones report n &gt; 30", "the paper", "exact")
        assert "Smith & Jones" in line and "n > 30" in line

    def test_decoding_happens_once(self):
        """`&amp;lt;` is a literal "&lt;" in the source, not a `<`. Unescaping
        twice would silently rewrite the paper's text."""
        from metascience_agent.report_render import _quote_line
        line = _quote_line("- ", "the token &amp;lt; appears", "the paper", "exact")
        assert "&lt;" in line and "< appears" not in line

    def test_plain_text_is_untouched(self):
        from metascience_agent.report_render import _quote_line
        line = _quote_line("- ", "M = 4.52 (SD = 1.13), t(48) = 2.51", "Table 1", "exact")
        assert "M = 4.52 (SD = 1.13), t(48) = 2.51" in line
