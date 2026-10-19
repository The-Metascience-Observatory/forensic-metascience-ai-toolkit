"""Every number the paper printed, and what each one turned out to be."""
import re

from metascience_agent import numerals as N


class TestTheIndexIsExhaustive:
    """The property the whole design rests on. A pattern-based enumerator can be
    silently incomplete -- two conventions were found missing from
    `completeness.BODY_PATTERNS` in one afternoon, `M = x, SD = y` and
    `65.2 ± 1.17`, together worth 5,942 occurrences across the corpus. A scan
    for digits cannot be, and this test is what says so."""

    TEXT = ("In Experiment 2 (see Fig. 1), participants (N = 45, 30 female) "
            "rated 6.58 (.52) on a 1-9 scale where 1 = sad and 9 = happy. "
            "The effect held, M = 4.64, SD = 1.50, F(1, 46) = 6.95, p = .011, "
            "replicating Wood (1989) and Isbell [2004]. Age was 65.2 ± 1.17. "
            "Reliability was high (Cronbach's alpha = .91). N = 12,345 overall.")

    def test_every_numeric_token_appears_exactly_once(self):
        rows = N.index(self.TEXT)
        found = [r["printed"] for r in rows]
        expected = N.NUMERAL.findall(self.TEXT)
        assert found == expected
        assert len({r["offset"] for r in rows}) == len(rows)

    def test_nothing_is_filtered_out_of_the_index(self):
        """Classification happens ON the index, never instead of it. A number
        the rules cannot name is still a row."""
        rows = N.index(self.TEXT)
        assert all(r["class"] in N.CLASSES for r in rows)
        assert N.tally(rows)["n_total"] == len(rows)

    def test_the_forms_that_matter_survive_tokenising(self):
        rows = {r["printed"] for r in N.index(self.TEXT)}
        assert ".52" in rows and ".011" in rows      # APA leading dot
        assert "12,345" in rows                      # thousands separator
        assert "65.2" in rows and "1.17" in rows      # plus-minus components
        assert "6.58" in rows

    def test_a_number_inside_a_word_is_not_a_number(self):
        rows = {r["printed"] for r in N.index("COVID-19 and p22 and F1 scores")}
        assert rows == set(), rows


class TestTheDenominatorStaysIndependentOfTheFinder:
    """`register.py`'s rule: a model that both enumerates and judges
    checkability reports full coverage of whatever it noticed, and the metric
    IMPROVES as the enumeration degrades."""

    def test_the_tally_publishes_the_model_free_total(self):
        rows = N.index("N = 45 and M = 4.64, SD = 1.50 and Fig. 1")
        t = N.tally(rows)
        assert t["n_total"] == len(rows)
        assert set(t["by_class"]) == set(N.CLASSES)

    def test_an_under_classifying_pass_is_visible(self):
        """It shows as a falling `share_judged` rather than an unchanged
        coverage score."""
        rows = N.index("4.1 and 5.2 and 6.3 and 7.4")
        assert N.tally(rows)["share_judged"] == 0.0
        N.classify_with(rows, [(0, 3)])
        assert N.tally(rows)["share_judged"] == 0.25

    def test_patterns_classify_the_index_rather_than_being_it(self):
        """`BODY_PATTERNS` keeps earning its place as a positive classifier over
        what it does match well. What it misses is now `unclassified` -- visible
        -- instead of absent."""
        from metascience_agent import completeness as C
        text = "The effect held, M = 4.64, SD = 1.50, and p = .011 overall."
        rows = N.index(text)
        spans = [(i["offset"], i["offset"] + len(i["raw"])) for i in C._body_items(text)]
        n = N.classify_with(rows, spans)
        assert n >= 3
        assert all(r["class"] == "statistic"
                   for r in rows if r["printed"] in {"4.64", "1.50", ".011"})


class TestTheRulesMayNotRemoveARealStatistic:
    """An adversarial review found every cheap rule removing real reported
    statistics -- 582 of 689 "factorial" classifications on a 12-paper sample
    (84%) were statistics. That is WORSE than the silence this module replaced,
    because a removed number carries a confident recorded reason and
    `classify_with` refuses to touch a row already classified, so a matching
    pattern cannot repair it."""

    def _classes(self, text):
        return {r["printed"]: r["class"] for r in N.index(text)}

    def test_a_mean_followed_by_a_parenthesis_survives(self):
        """`^\\s*\\(` matched ANY number before a bracket, so `4.17 (SD = 1.19)`
        lost its mean to "factorial design notation"."""
        assert self._classes("scores of 4.17 (SD = 1.19) here")["4.17"] == "unclassified"

    def test_a_count_before_its_percentage_survives(self):
        assert self._classes("96 of 104 (92.3%) responded")["104"] == "unclassified"

    def test_a_trial_effect_estimate_survives(self):
        """Verbatim from a corpus stroke RCT: the primary effect estimate was
        filed as design notation."""
        assert self._classes("MW=0.71 (95% CI 0.55-0.87)")["0.71"] == "unclassified"

    def test_a_sample_size_after_an_ordinal_survives(self):
        """`In Study 1, 45 participants` -- the coordinator rule accepted a bare
        comma and took the sample size with it."""
        c = self._classes("In Study 1, 45 participants")
        assert c["1"] == "ordinal" and c["45"] == "unclassified"

    def test_a_bracketed_number_that_is_not_a_citation_survives(self):
        assert self._classes("a cohort of (1989 patients)")["1989"] == "unclassified"

    def test_a_word_ending_in_x_is_not_a_multiplication(self):
        """`approx 30` lost its 30 to the factorial rule."""
        assert self._classes("approx 30 participants")["30"] == "unclassified"

    def test_an_n_equals_is_not_a_scale_anchor(self):
        assert self._classes("n = 45 patients")["45"] == "unclassified"

    def test_the_rules_that_should_fire_still_do(self):
        assert self._classes("replicating Wood (1989) here")["1989"] == "citation_year"
        assert self._classes("In Experiment 2 we")["2"] == "ordinal"
        assert self._classes("a 2 x 2 design")["2"] == "ordinal"
        assert self._classes("where 1 = sad and 9 = happy")["1"] == "scale_anchor"


class TestTheIndexReallyIsExhaustive:
    """"Exhaustive by construction" was false: glued units, scientific notation
    and superscripts were invisible with no residue row -- 293 unit-glued
    occurrences in 55 of 305 corpus papers."""

    def test_a_number_glued_to_its_unit_is_indexed(self):
        for text, want in (("Age was 542ms later", "542"), ("a 250mg dose", "250"),
                           ("24h after", "24")):
            assert want in {r["printed"] for r in N.index(text)}, text

    def test_scientific_notation_is_one_number(self):
        assert [r["printed"] for r in N.index("rate was 1.2e-4 overall")] == ["1.2e-4"]

    def test_an_identifier_is_still_not_a_number(self):
        assert N.index("trial NCT02737566 was") == []
        assert N.index("COVID-19 and p22 and F1") == []


class TestTheTallyCountsWhatItSays:
    def test_a_row_with_no_class_key_increments_rather_than_resets(self):
        """The write defaulted a missing `class` to "unclassified" while the
        read looked up the raw None, so such a row RESET its bucket to 1 --
        deflating counts and inflating `share_judged`, in the function whose
        purpose is an honest denominator."""
        t = N.tally([{"printed": "1"}, {"printed": "2"},
                     {"printed": "3", "class": "statistic"}])
        assert t["by_class"]["unclassified"] == 2
        assert t["n_total"] == 3 and t["share_judged"] == 1 / 3


class TestASerialisedTableRowBelongsToTheTablePass:
    """docling emits tables as pipe rows inside the prose, so a paper's
    tabulated results arrive twice. MEASURED over the 211-paper Zotero corpus:
    26,163 of 98,463 unclassified tokens (27%) sat on such a line, and they are
    real statistics -- CIs, p-values, medians with IQR. Routing them lifts the
    judged share from 22% to 43%."""

    ROW = "| A | 524 (369-739) | 0.045 |"

    def test_a_pipe_row_routes_to_the_table_pass(self):
        assert {r["class"] for r in N.index(self.ROW)} == {"table_cell"}

    def test_it_is_a_ROUTING_not_a_removal(self):
        """`table_cell` does not say "not a statistic". It says another pass
        owns this number -- one that knows its row and column."""
        why = N.index(self.ROW)[0]["why"]
        assert "table pass owns it" in why

    def test_prose_on_the_next_line_is_untouched(self):
        rows = N.index(self.ROW + "\nThe effect was reliable at 4.17 overall.")
        assert [r["class"] for r in rows if r["printed"] == "4.17"] == ["unclassified"]

    def test_it_does_not_route_into_a_void(self):
        """If the extractor produced no tables, no pass owns the number, and
        `table_cell` would be a false assurance. 5 papers and 84 tokens on the
        Zotero corpus -- small enough to be tempting to ignore, and exactly the
        shape of defect this repository keeps finding."""
        assert {r["class"] for r in N.index(self.ROW, tables_available=False)} == \
            {"unclassified"}


class TestMultiYearCitations:
    """`(Kawamata, 1997, 1998; Schaebitz, 1999)` classified only its first year.
    The second saw `Kawamata, 1997, ` behind it, and `_CITATION` wants an author
    token immediately before, so the chain broke at the comma."""

    def _classes(self, text):
        idx = N.index(text, tables_available=False)
        return [(r["printed"], r["class"]) for r in idx]

    def test_every_year_in_a_chain_is_a_citation_year(self):
        got = self._classes(
            "reduces infarct size (Kawamata, 1997, 1998; Schaebitz, 1999).")
        assert got == [("1997", "citation_year"), ("1998", "citation_year"),
                       ("1999", "citation_year")]

    def test_lettered_years_chain_too(self):
        got = self._classes("as shown before (Smith, 1997a, 1997b).")
        assert [c for _, c in got] == ["citation_year", "citation_year"]

    def test_a_sample_size_after_a_comma_is_still_not_a_year(self):
        """The rule that keeps the rule honest. `of` is not one of the
        connectives the author alternation allows, so no author token matches
        and a list of group sizes stays unclassified rather than being filed as
        a bibliography -- a false removal is permanent, because `classify_with`
        will not touch a row that already carries a class."""
        got = dict(self._classes("with arms of 250, 2013, and 210 patients"))
        assert got["2013"] != "citation_year"

    def test_a_year_chain_does_not_swallow_a_following_statistic(self):
        got = dict(self._classes(
            "(Kawamata, 1997, 1998), and 146 patients were enrolled"))
        assert got["146"] != "citation_year"


class TestTheFourthReaderOfTheMiddleDot:
    """`numerals.NUMERAL` was the FOURTH reader of Lancet-style decimals and the
    one still getting it wrong after the other three were fixed.

        tokens("the estimate was -5·077 (95% CI -7·716 to -2·437)")
        -> ['-5', '077', '95', '-7', '716', '-2', '437']

    Seven tokens where the paper printed three numbers -- in the module whose
    docstring promises "exhaustive by construction". Across the eleven-paper
    corpus it invented exactly 158 spurious tokens, all in one paper, which is
    precisely that paper's count of middle-dot decimals: every one was being
    split in two.

    WORSE THAN A LOCAL BUG. `agreement._numbers` delegates here, so two
    independent readings of a Lancet page shredded IDENTICALLY and the
    comparison reported perfect agreement on garbage. Sharing a lexer removes
    divergence between readers and removes their independence with it. That is
    the trade, and it is only safe if the lexer is right.
    """

    def _toks(self, text):
        from metascience_agent.numerals import tokens
        return [m.group(0) for m in tokens(text)]

    def test_a_lancet_interval_is_three_numbers_not_seven_tokens(self):
        assert self._toks("the estimate was -5·077 (95% CI -7·716 to -2·437)") == [
            "-5·077", "95", "-7·716", "-2·437"]

    def test_the_plain_conventions_are_untouched(self):
        assert self._toks("mean 6.58 (SD 0.52)") == ["6.58", "0.52"]
        assert self._toks("n = 12,345 patients") == ["12,345"]
        assert self._toks("rate 1.2e-4 per year") == ["1.2e-4"]
        assert self._toks("Age was 65.2 ± 1.17.") == ["65.2", "1.17"]
        assert self._toks("542ms and 250mg") == ["542", "250"]

    def test_the_guards_still_guard(self):
        assert self._toks("see p.22 of the report") == []
        assert self._toks("COVID-19 patients") == []
        assert self._toks("rows 1-8 and 9-16") == ["1", "8", "9", "16"]

    def test_a_middle_dot_does_not_start_a_new_number(self):
        """The leading guard must refuse a match beginning straight after a
        decimal mark, or `077` is emitted as a number of its own."""
        assert "077" not in self._toks("-5·077")


# ---------------------------------------------------------------------------
# A SUPPLEMENT'S NUMBERS BELONG IN THE SAME DENOMINATOR
#
# An article's own tables are already in the floor because docling inlines them
# as pipe rows -- 174 of Stern 2014's 876 rows are `table_cell` for that reason.
# A supplement is a separate FILE that never enters the body text, so its
# numbers were in no denominator at all: fetching Stern's supplement took the
# scaffold from 144 table cells to 2,638 and left `n_total` at 876.
# ---------------------------------------------------------------------------

def _supp(cells):
    """The walked-table shape `index_table_cells` takes."""
    return [{"cells": cells}]


def test_supplement_cells_are_enumerated():
    rows = N.index_table_cells(
        _supp([{"raw": "41.87", "row_label": "Veh", "col_label": "Mean"},
               {"raw": "F6,51=6.819", "row_label": "Veh", "col_label": "Test"}]),
        "si.docx")
    # NOT "6": `tokens` does not read a digit that is directly preceded by a
    # letter, so `F6,51` yields only the second df. That is pre-existing floor
    # behaviour on the body path too (`t15 = 2.3` yields only `2.3`) and is
    # asserted here as it IS, not as it should be -- a test written to the
    # wished-for answer would have hidden it.
    assert [r["printed"] for r in rows] == ["41.87", "51", "6.819"]
    assert {r["source"] for r in rows} == {"supplement"}


def test_a_supplement_row_carries_no_body_offset():
    """`offset` indexes the BODY text. Reusing it for a supplement would file
    the number into whichever body chunk spans the same integer and serve it to
    the model with the wrong surrounding text."""
    rows = N.index_table_cells(_supp([{"raw": "41.87"}]), "si.docx")
    assert all(r["offset"] is None for r in rows)


def test_supplement_ids_cannot_collide_with_body_ids():
    body = N.index("The mean was 41.87 units.")
    supp = N.index_table_cells(_supp([{"raw": "41.87"}]), "si.docx")
    assert not ({r["id"] for r in body} & {r["id"] for r in supp})


def test_the_tally_splits_by_source_and_keeps_one_total():
    body = N.index("Two values: 41.87 and 3.07.")
    supp = N.index_table_cells(_supp([{"raw": "41.87"}, {"raw": "3.07"}]), "si.docx")
    t = N.tally(body + supp)
    assert t["n_total"] == len(body) + len(supp)
    assert t["by_source"]["supplement_table"]["n_total"] == len(supp)
    assert t["by_source"]["article_prose"]["n_total"] == len(body)


def test_each_source_reports_its_own_share():
    """The top-line share stops being informative once a large auto-classified
    block joins: on Stern it went 0.371 -> 0.851 with nothing newly read."""
    body = N.index("Background: 12 sites.")
    supp = N.index_table_cells(_supp([{"raw": "41.87"}]), "si.docx")
    t = N.tally(body + supp)
    assert t["by_source"]["supplement_table"]["share_judged"] == 1.0
    assert t["by_source"]["article_prose"]["share_judged"] < 1.0
