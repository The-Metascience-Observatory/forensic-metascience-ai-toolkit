"""A field called `quote` that nobody checks invites composed text to be read as copied text.

`findings[].quote` is described in the schema as "verbatim reported text/values
from the paper" and is populated on 505 of 505 findings across the corpus. It
was never verified against the paper. MEASURED by `metascience_agent.quotes`
over the 499 findings it can build a haystack for:

    verbatim   186  37%
    elided      63  13%
    stitched   228  46%   every number is real, the sentence is not in the paper
    unverified  22   4%

The 22 were hand-adjudicated and contain NO FABRICATIONS -- every one is a limit
of the search (a paper spelling "Eighty-seven per cent" in words, a raw table
header row, a page reference `p.22` read as the decimal .22). So the point of
this is not to catch the model lying. It is that NEARLY HALF of all quotes are
stitched, and a stitched quote is the one thing a reader cannot act on: they
search the PDF for it and find nothing, under a heading that said "As printed".
"""
import json
from pathlib import Path

import pytest

from metascience_agent.quotes import annotate, build_haystack, classify, normalise

def _has_paper_files(d) -> bool:
    """Is this a real paper directory, or a leftover shell?

    `d.exists()` is NOT the question. The corpus was removed from the repo on
    2026-08-09, but a working tree can still hold the DIRECTORY -- run outputs
    and `figures/` are written inside it and survive as untracked files -- while
    the PDF and XML the test actually reads are gone. Gating on the directory
    let the test run against an empty shell and FAIL, which is the same
    absence-read-as-presence mistake the toolkit polices in its own checks,
    appearing here in the harness.

    A suite that is red by default on every machine without the corpus teaches
    people to ignore it, so gate on the artefact rather than the folder.
    """
    return d.is_dir() and (any(d.glob("*.pdf")) or any(d.glob("*.xml")))


PAPER = Path("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--mpr.70006")
corpus = pytest.mark.skipif(not _has_paper_files(PAPER), reason="corpus not present")

HAY = {"the paper's text": normalise(
    "Participants completed the task. The interaction was reliable, "
    "F(1, 38) = 7.21, p = .011, with a mean of 3.45 (SD 1.02). "
    "Attrition was 12 of 50.")}


class TestTheVerdicts:
    def test_a_copied_sentence_is_verbatim(self):
        v = classify("The interaction was reliable, F(1, 38) = 7.21, p = .011", HAY)
        assert v["quote_verified"] == "verbatim"
        assert v["quote_source"] == "the paper's text"

    def test_an_ellipsis_with_both_halves_present_is_elided(self):
        v = classify("The interaction was reliable ... with a mean of 3.45 (SD 1.02)", HAY)
        assert v["quote_verified"] == "elided"

    def test_real_numbers_in_a_sentence_the_paper_never_printed_are_stitched(self):
        """The 46% case. Every value is real; the sentence is ours."""
        v = classify("mean 3.45, SD 1.02, F = 7.21, n = 50", HAY)
        assert v["quote_verified"] == "stitched"
        assert "searching the PDF for it will find nothing" in v["quote_problem"]

    def test_text_we_cannot_locate_says_OUR_search_failed(self):
        """The house rule: never report our limitation in the grammar of a
        claim about the paper. On the measured evidence the likely cause of an
        unverified quote is this module's haystack, not the authors."""
        v = classify("Participants were compensated with 40 dollars", HAY)
        assert v["quote_verified"] == "unverified"
        p = v["quote_problem"]
        assert "WE could not locate" in p
        assert "not about the paper" in p
        assert "Do not read it as evidence that the authors did not write this" in p

    def test_no_quote_is_absent_not_unverified(self):
        assert classify("", HAY)["quote_verified"] == "absent"
        assert classify("   ", HAY)["quote_verified"] == "absent"


class TestTypographyIsNotAFailureToQuote:
    """A paper prints a minus sign where a model types a hyphen. Treating that
    as an unlocatable quote is how a verifier manufactures alarm."""

    @pytest.mark.parametrize("written", [
        "a mean of 3.45 (SD 1.02)",          # plain
        "a mean of 3.45 (SD 1.02)",     # non-breaking space
        "a mean of 3.45 (SD 1.02)",          # already normal
        "A MEAN OF 3.45 (SD 1.02)",          # case
        "a  mean  of  3.45  (SD  1.02)",     # runs of whitespace
    ])
    def test_it_still_verifies(self, written):
        assert classify(written, HAY)["quote_verified"] == "verbatim"

    def test_a_minus_sign_matches_a_hyphen(self):
        hay = {"the paper's text": normalise("the change was −0.42 points")}
        assert classify("the change was -0.42 points", hay)["quote_verified"] == "verbatim"

    def test_a_page_reference_is_not_read_as_a_decimal(self):
        """`p.22` tokenised as the decimal .22 made a page reference look like
        a missing value, and pushed a good quote into `unverified`."""
        hay = {"the paper's text": normalise("Table 2 on page 22 reports 39.87")}
        v = classify("reports 39.87 [PDF p.22]", hay)
        assert v["quote_verified"] == "stitched", v


class TestItIsPipelineSetAndSafe:
    def test_a_forged_verdict_is_stripped_even_when_the_paper_cannot_be_opened(self, tmp_path):
        """THE EXPLOIT THAT WORKED. The schema must declare these fields
        (finding items set additionalProperties:false), so the model can emit
        them -- and the early return on an empty haystack used to skip the
        strip. A model-written `quote_verified: "verbatim"` then survived and
        rendered as "As printed ... found in the paper's text" on a paper
        nobody opened. The strip now runs before the haystack is attempted.
        """
        findings = [{"quote": "fabricated text",
                     "quote_verified": "verbatim",
                     "quote_source": "the paper's text"}]
        annotate(findings, tmp_path / "does-not-exist")
        assert "quote_verified" not in findings[0]
        assert "quote_source" not in findings[0]

    def test_a_model_supplied_verdict_never_survives_verification_either(self):
        """When the haystack DOES build, the model's value is replaced by the
        pipeline's -- a self-assessment written by the thing being assessed is
        not a check. Same reason `reproduction_valid` is pipeline-set."""
        findings = [{"quote": "no such text anywhere in this haystack",
                     "quote_verified": "verbatim",
                     "quote_source": "invented by the model"}]
        from metascience_agent.quotes import classify
        v = classify(findings[0]["quote"], HAY)
        assert v["quote_verified"] != "verbatim"

    def test_an_unopenable_paper_writes_no_verdict_at_all(self, tmp_path):
        """Stamping every finding `unverified` because WE could not read the
        source would be the house mistake in a new field."""
        findings = [{"quote": "anything"}]
        annotate(findings, tmp_path / "does-not-exist")
        assert "quote_verified" not in findings[0]

    def test_the_wrapper_strips_a_forgery_even_with_no_paper_path(self):
        """`_annotate_quotes` returned early when `paper_path` was absent,
        WITHOUT stripping -- so a model-forged verdict survived on any result
        that never recorded its path. Reproduced: the forgery came through as
        "verbatim". The strip is now unconditional; verification is what
        depends on the path."""
        from metascience_agent.agent import _annotate_quotes
        result = {"findings": {"findings": [
            {"id": "x", "quote": "fabricated",
             "quote_verified": "verbatim", "quote_source": "the paper's text"}]}}
        _annotate_quotes(result, None)
        f = result["findings"]["findings"][0]
        assert "quote_verified" not in f
        assert "quote_source" not in f

    def test_it_never_raises(self, tmp_path):
        annotate([{"quote": None}, {}, "not a dict", {"quote": 12}], tmp_path)

    def test_it_is_idempotent(self):
        f = [{"quote": "The interaction was reliable"}]
        annotate(f, ".")
        annotate(f, ".")
        assert list(f[0]).count("quote_verified") <= 1


class TestTheSchemaDeclaresWhatWeWrite:
    """Finding items set `additionalProperties: false`, so an undeclared
    pipeline key makes every findings.json we write violate its own schema."""

    def test_the_three_fields_are_declared(self):
        s = json.loads(Path(
            "src/metascience_agent/schema/findings.v2.schema.json"
        ).read_text())
        props = s["properties"]["findings"]["items"]["properties"]
        for k in ("quote_verified", "quote_source", "quote_problem"):
            assert k in props, k
            assert "not the model" in props[k]["description"]

    def test_the_instruction_now_asks_for_one_contiguous_span(self):
        """The old description was "verbatim reported text/values from the
        paper" -- disjunctive and plural, which licenses a bag of values rather
        than a copied span, and never warned that the string is checked."""
        s = json.loads(Path(
            "src/metascience_agent/schema/findings.v2.schema.json"
        ).read_text())
        d = s["properties"]["findings"]["items"]["properties"]["quote"]["description"]
        assert "CONTIGUOUS" in d
        assert "Copy it; do not compose it" in d
        assert "CHECKED against" in d


class TestTheViewer:
    def test_a_quote_cannot_break_out_of_the_payload_block(self):
        """A quote is text copied out of someone else's PDF, and it is carried
        into the page inside a `<script type="application/json">` block.

        The dangerous property is NOT that the characters appear in the file --
        as JSON data they are inert, and asserting their absence is a test that
        fails on safe code. What matters is that a `</script>` in the DATA
        cannot close the block early and turn the rest into live markup.
        `bundle.py` escapes `</` to `<\\/` for exactly this; the assertion is
        that the count of real closing tags still matches the opening ones.
        """
        from metascience_agent.bundle import render_viewer
        nasty = '</script><img src=x onerror=alert(1)>'
        html = render_viewer({"findings": [
            {"id": "x", "quote": nasty, "quote_verified": "verbatim",
             "severity": "consistent", "technique": "t", "location": "l"}]})
        assert "<\\/script>" in html, "the data's closing tag must be escaped"
        assert html.count("</script>") == html.count("<script"), (
            "a quote injected an extra closing tag")

    def test_the_quote_reaches_the_dom_through_the_escaper(self):
        from metascience_agent.bundle import render_viewer
        assert "esc(f.quote)" in render_viewer({})

    def test_the_heading_stops_promising_as_printed_for_assembled_text(self):
        from metascience_agent.bundle import render_viewer
        html = render_viewer({})
        assert "Values, assembled by this review" in html
        assert "Quoted by the review, not located" in html

    def test_an_unlocatable_quote_offers_no_jump_link(self):
        """A jump on text that is not in the document highlights nothing and
        leaves the reader believing they searched and the paper came up short."""
        from metascience_agent.bundle import render_viewer
        html = render_viewer({})
        assert "const findable = f.quote_verified==='verbatim'||f.quote_verified==='elided';" in html


@corpus
class TestOnTheRealCorpus:
    def test_the_haystack_finds_more_than_the_body_text(self):
        hay = build_haystack(PAPER)
        assert "the paper's text" in hay
        assert len(hay) > 1, f"only found {list(hay)}"

    def test_romano_quotes_are_mostly_locatable(self):
        rev = PAPER / "forensic_review_wave3"
        if not (rev / "findings.json").exists():
            pytest.skip("no findings for this paper")
        d = json.loads((rev / "findings.json").read_text())
        hay = build_haystack(PAPER)
        verdicts = [classify(f.get("quote") or "", hay)["quote_verified"]
                    for f in d["findings"]]
        located = sum(1 for v in verdicts if v in ("verbatim", "elided"))
        assert located >= len(verdicts) // 3, dict(
            (v, verdicts.count(v)) for v in set(verdicts))


class TestTableAndFigureMentionsAreLinks:
    """Greg, 2026-08-01, verbatim: "Whenever a table or section is mentioned in
    any of the pages, it should be a clickable link that will snap to the Paper
    vs Text page."

    Same intent as the quote verdicts above -- traceability from a claim back to
    the place in the paper it came from. A finding whose Where says "Table 2,
    Height row" is asking the reader to go and look at Table 2, and making them
    find it by hand is the same friction as an unlocatable quote.

    The machinery already existed: `goTable(label)` switches the source pane to
    rendered view and highlights the label. This is wiring, not new plumbing.
    """

    def test_the_linkifier_exists_and_is_applied_to_where(self):
        from metascience_agent.bundle import render_viewer
        html = render_viewer({})
        assert "function refLinks(escaped)" in html
        assert "refLinks(esc(f.location))" in html

    def test_it_is_given_already_escaped_text(self):
        """Linkifying before escaping would destroy the anchors; escaping after
        would emit them literally. The order is load-bearing, and the pattern
        must not be able to match inside an HTML entity -- that is the failure
        that bit the search box, where a needle matched inside `&#39;` and
        split it open."""
        from metascience_agent.bundle import render_viewer
        html = render_viewer({})
        assert "refLinks(esc(" in html
        assert "esc(refLinks(" not in html

    def test_the_title_is_left_alone(self):
        """`fTitle` renders inside a clickable <summary>; a link there would
        fight the disclosure toggle."""
        from metascience_agent.bundle import render_viewer
        html = render_viewer({})
        assert "const where=esc(String(f.location||'').trim());" in html


class TestANumberCannotVerifyAsPartOfALongerNumber:
    """Plain substring containment reported "n = 42" as verbatim in a paper
    that only ever says "n = 428" -- 42 is a substring of 428.

    Reproduced: classify("n = 42", {paper: "the final sample was n = 428"})
    returned quote_verified="verbatim". That is a false all-clear about the
    quote's own accuracy -- the reader is told the number is printed in the
    paper, and it is not; a different number is. `_contains_bounded` requires a
    non-digit (and non-decimal-point) on the digit-facing edge of the match.
    """

    def test_the_attack_no_longer_verifies(self):
        hay = {"t": normalise("The final sample was n = 428 participants.")}
        assert classify("n = 42", hay)["quote_verified"] == "unverified"
        assert classify("n = 4", hay)["quote_verified"] == "unverified"

    def test_the_true_number_still_verifies(self):
        hay = {"t": normalise("The final sample was n = 428 participants.")}
        assert classify("n = 428", hay)["quote_verified"] == "verbatim"

    def test_a_paper_printing_both_still_verifies_both(self):
        """The boundary rule must not reject a legitimate short number just
        because a longer one also appears."""
        hay = {"t": normalise("Group A had n = 42 and group B had n = 428.")}
        assert classify("n = 42", hay)["quote_verified"] == "verbatim"
        assert classify("n = 428", hay)["quote_verified"] == "verbatim"

    def test_a_decimal_is_not_read_as_a_truncation(self):
        hay = {"t": normalise("the ratio was 4.28 overall")}
        assert classify("the ratio was 4.2 overall", hay)["quote_verified"] == "unverified"
        assert classify("the ratio was 4.28 overall", hay)["quote_verified"] == "verbatim"

    def test_non_numeric_text_is_unaffected(self):
        """The boundary check only applies when the needle's edge is a digit --
        ordinary prose still uses plain containment."""
        hay = {"t": normalise("The interaction was reliable and robust.")}
        assert classify("interaction was reliable", hay)["quote_verified"] == "verbatim"


class TestElidedMayNotLaunderAFabricatedNumber:
    """`elided` is one of the two verdicts allowed to make the "As printed"
    promise, and the reader is offered a link to find the text in the PDF. Two
    independent holes let a quote that is NOT in the paper earn it."""

    HAY = {"the paper's text": normalise(
        "The control group showed a marked improvement over the baseline "
        "period. Many paragraphs intervene here about unrelated matters. "
        "Finally the treatment group is mentioned again in the discussion. "
        "Doses were given at 10 mg / kg and the male / female split was even.")}

    def test_a_number_absent_from_the_paper_blocks_elided(self):
        """Fragments under 12 characters are non-probative and are dropped --
        correctly, since "0.05" is in every paper. But they were dropped BEFORE
        `all(found)` ran, so they were never searched, and the verdict asserted
        the whole string was present having checked only the long parts.
        Numbers are exactly what falls under 12 characters."""
        v = classify(
            "The control group showed a marked improvement ... 99.9 ... "
            "the treatment group is mentioned again", self.HAY)
        assert v["quote_verified"] != "elided"
        assert v["quote_verified"] == "unverified"

    def test_a_slash_is_a_separator_not_an_elision(self):
        """` / ` and `||` occur naturally: `mg / kg`, `male / female`, a table
        row rendered with ` / ` between cells, a markdown pipe pair surviving
        normalise(). This module's docstring already said such a quote should
        land in `stitched`; the code did the opposite."""
        for sep in (" / ", " || "):
            q = ("The control group showed a marked improvement" + sep +
                 "the treatment group is mentioned again")
            assert classify(q, self.HAY)["quote_verified"] != "elided", sep

    def test_a_real_elision_still_verifies(self):
        v = classify("The control group showed a marked improvement ... "
                     "the treatment group is mentioned again", self.HAY)
        assert v["quote_verified"] == "elided"

    def test_the_bracketed_form_is_an_elision(self):
        """`[...]` is how the convention is actually written in scholarship,
        and it has to be matched whole or the brackets stay glued to the
        fragments."""
        v = classify("The control group showed a marked improvement [...] "
                     "the treatment group is mentioned again", self.HAY)
        assert v["quote_verified"] == "elided"

    def test_an_elision_whose_number_IS_present_still_verifies(self):
        """The precondition must not turn every numeric elision into a
        refusal."""
        v = classify("The control group showed a marked improvement ... at "
                     "10 mg / kg and the male / female split was even", self.HAY)
        assert v["quote_verified"] == "elided"
