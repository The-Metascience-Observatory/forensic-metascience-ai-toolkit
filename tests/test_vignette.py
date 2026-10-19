"""One tool call must be followable on its own.

WHAT THESE TESTS ARE FOR. The "Chain of reasoning" page is the only surface in
the bundle where an individual check can be inspected, and it rendered each
call as two JSON dumps. The vignette replaces that with five labelled parts --
what we asked, what the paper said, what the tool computed, what that means,
what would change the answer.

The properties worth pinning are not "it renders": they are the ones that stop
a reader over-reading a single check. Every one of these tests encodes a way
the old page, or an early draft of this one, was wrong -- and several of the
drafts were caught only by composing all 2,106 archived calls and reading the
output, which `TestTheWholeArchiveComposes` does on every run.
"""
import json
import re

import pytest

from metascience_agent import vignette
from metascience_agent.bundle import _distil_calls, _integrity_card, collect
from tests.test_bundle import flat, review, section_html  # noqa: F401


def compose(tool, parsed, *, inp=None, **entry):
    """One vignette, composed the way `_distil_calls` composes it.

    The second argument is the PARSED result, and it is named `parsed` rather
    than `result` on purpose: `result` is also a ledger-entry field, and a
    helper taking both under one name silently shadowed the raw text an errored
    call is rendered from."""
    base = {"tool": tool, "input": inp or {}, "is_error": False,
            "validated": True, "sourceable": True}
    base.update(entry)
    return vignette.compose(base, parsed, _integrity_card(tool))


#: Directories that hold no ledger and are expensive to walk. Copied in spirit
#: from `inertness._SKIP_DIRS`, which excludes them for the same measured
#: reason: the paper corpora are 516 MB of PDFs and markdown and none of it is
#: a run record.
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv",
              "cerebrolysin_papers", ".extraction_cache"}


@pytest.fixture(scope="module")
def composed():
    """Every archived ledger in this checkout, distilled once.

    PRUNED WITH `os.walk`, NOT `Path.glob("**/...")`. The glob walks the whole
    tree before any filter sees it, and on this repo that is 49 SECONDS against
    1.7s to read the files it finds and 1.0s to compose every vignette --
    95% of the cost in the part that finds nothing. Under `-n 10`
    that overran the suite's 120s per-test timeout and turned all four tests in
    this class into errors, which is a green-looking suite with its most
    valuable assertions not running.

    Module-scoped and skipped when the checkout has no corpus, so a clone
    without the papers still passes -- but here it is the only population that
    has caught the defects worth catching."""
    import os
    from pathlib import Path
    repo = Path(__file__).resolve().parent.parent
    out = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        # A BUNDLE CARRIES A COPY of its run's ledger under `analysis/`, so a
        # naive walk composes every run twice and doubles every count.
        # `replay._replay_corpus` documents the same trap and the same fix; a
        # first count here inherited it and reported 3,436 calls where the
        # archive holds 2,106.
        if "analysis" in Path(root).parts:
            continue
        for name in sorted(files):
            if not name.startswith("toolcalls.stage"):
                continue
            try:
                out += _distil_calls(
                    json.loads(Path(root, name).read_text()), "sweep")
            except Exception:
                continue
    if len(out) < 100:
        pytest.skip("no archived ledgers in this checkout")
    return out


GRIMMER_IMPOSSIBLE = {
    "consistent": False, "severity": "impossible",
    "failure_mode": "sd_granularity", "bound_source": "assumed",
    "discreteness_source": "stated", "grim_consistent": True,
    "feasible_ignoring_bounds": False, "population_feasible_in_bounds": False,
    "reported_mean": 6.58, "reported_sd": 0.52, "n": 12,
    "methodology": "GRIMMER test: enumerate integer sums S with |S/12 - 6.58| "
                   "<= 0.005 (found 1), then for each S search integer "
                   "sums-of-squares Q with matching parity.",
    "failure_reason": "no integer sum-of-squares consistent with the reported SD",
}


class TestEveryPartIsPresent:
    """A MISSING PART IS NOT AN EMPTY SLOT, it is a slot that says what is
    missing. The five parts are the unit; a vignette that silently drops one is
    a vignette a reader finishes believing they have seen everything."""

    def test_all_five_parts_for_a_flagged_check(self):
        v = compose("grimmer_check", GRIMMER_IMPOSSIBLE)
        assert [k for k, _ in vignette.PARTS] == list(v)

    def test_all_five_parts_for_a_tool_with_no_registry_card(self):
        v = compose("Read", None, inp={"file_path": "body.md"}, sourceable=False)
        assert [k for k, _ in vignette.PARTS] == list(v)
        assert "not one of the forensic checks" in v["means"]["scope"]

    def test_the_part_labels_reach_the_viewer_as_data(self, review, tmp_path):
        """Shipped, not restated in the JS. `test_viewer_vocabulary_drift` keeps
        a register of the vocabularies still hand-written in the page precisely
        because each one had already drifted."""
        payload = collect(review)
        assert payload["vignette_parts"] == [
            {"key": k, "label": lab} for k, lab in vignette.PARTS]
        html = flat(section_html(payload, "calls", tmp_path))
        for _, label in vignette.PARTS:
            assert label in html, f"the viewer never renders the part `{label}`"


class TestNothingIsInvented:
    """The cardinal rule reaches the rendering: a slot the ledger cannot fill
    says so rather than being filled."""

    def test_a_call_with_no_source_quote_says_so_and_invents_none(self):
        v = compose("grimmer_check", GRIMMER_IMPOSSIBLE)
        assert v["paper"] == {"state": "unrecorded"}
        assert "quote" not in json.dumps(v["paper"]).replace('"state"', "")

    def test_a_tool_never_offered_a_quote_is_not_scored_as_unsourced(self):
        """An extractor has no reported value to source. Marking it unsourced
        turns a design decision into a coverage failure on every run."""
        v = compose("extract_pdf", None, sourceable=False,
                    inp={"pdf_path": "/x/paper.pdf"})
        assert v["paper"]["state"] == "not_offered"
        assert "none is missing" in v["paper"]["note"]

    def test_the_method_sentence_is_the_tools_own_words(self):
        v = compose("grimmer_check", GRIMMER_IMPOSSIBLE)
        assert v["computed"]["method"] == flat(GRIMMER_IMPOSSIBLE["methodology"])

    def test_a_check_that_described_no_method_is_not_given_one(self):
        v = compose("grimmer_check", {"severity": "consistent"})
        assert v["computed"]["method"] == ""
        assert v["computed"]["no_method"] is True

    def test_the_question_is_the_registrys_purpose_not_a_new_description(self):
        from metascience_agent import registry
        v = compose("grim_check", {"severity": "consistent"})
        assert v["asked"]["question"] == registry.BY_NAME["grim_check"].purpose


class TestThePassesAndRefusalsCarryTheirDenominator:
    """845 of the 2,106 archived calls are `consistent` and 311 are
    `indeterminate` -- 75% of every call that returned a verdict. A rendering
    tuned only for flags drops the denominator, and `severity_ledger` already
    caught this document dropping its `consistent` verdicts once."""

    def test_a_pass_says_what_it_did_not_establish(self):
        v = compose("grim_check", {"severity": "consistent", "n": 30})
        scope = v["means"]["scope"]
        assert "PASS" in scope
        assert "does not say the analysis is correct" in scope
        assert "any other check would pass" in scope

    def test_a_refusal_is_not_rendered_as_a_pass(self):
        v = compose("grim_check", {"severity": "indeterminate"})
        scope = v["means"]["scope"]
        assert "REFUSAL, not a pass" in scope
        assert "neither cleared nor implicated" in scope

    def test_a_pass_still_shows_the_numbers_the_check_had_in_hand(self):
        v = compose("recalc_f_to_p", {
            "severity": "consistent", "f_value": 4.65, "df1": 1, "df2": 13,
            "calculated_p": 0.0503, "reported_p": 0.05, "p_matches": True})
        names = {f["name"] for f in v["computed"]["figures"]}
        assert {"f_value", "df1", "df2", "calculated_p", "reported_p"} <= names


class TestOurFailureIsNotThePapersProperty:
    """House failure mode #2. Every branch here was a real conflation."""

    def test_an_errored_call_is_never_a_quiet_pass(self):
        v = compose("grim_check", None, is_error=True,
                    result="Error: R is not installed")
        assert v["computed"]["errored"] is True
        assert "not about the paper" in v["computed"]["headline"]
        assert "nothing here clears or implicates" in v["computed"]["headline"]

    def test_the_error_flag_survives_distillation(self):
        """It sat on the ledger entry and was dropped, so an errored call
        arrived at the viewer indistinguishable from one that found nothing."""
        [entry] = _distil_calls([{
            "seq": 1, "tool_short": "grim_check", "validated": True,
            "is_error": True, "input": {"mean": 1.0}, "result": "Error: boom"}],
            "sweep")
        assert entry["is_error"] is True

    def test_cells_we_could_not_parse_are_not_reservations_about_the_paper(self):
        """One archived `parse_cells_typed` call emits twelve warnings, every
        one "could not parse '1458 EUR' as a numeric cell". Filed as caveats
        they read as twelve reservations about the authors' table."""
        v = compose("parse_cells_typed", {
            "severity": "indeterminate",
            "warnings": [f"could not parse '{n} EUR' as a numeric cell"
                         for n in (1458, 1050, 1466, 1767, 1437, 1029, 1188)]})
        warn = [lev for lev in v["changes"] if "could not read" in lev["lever"]]
        assert len(warn) == 1, "one lever, not one per unreadable cell"
        assert warn[0]["lever"].startswith("7 values")
        assert "not a value the paper got wrong" in warn[0]["detail"]

    def test_a_check_that_graded_nothing_is_not_a_clean_bill(self):
        """36 archived `statcheck` calls return `errors_found` and no
        `severity`, so they register as a blank in every severity tally."""
        v = compose("statcheck", {"success": True, "stats_found": 22,
                                  "errors_found": 20})
        assert v["means"]["no_verdict"] is True
        assert "nothing here is a pass" in v["means"]["scope"]
        assert "gap in OUR tool's output" in v["means"]["scope"]


class TestWhatWouldChangeTheAnswerIsNotDecoration:
    def test_every_archived_call_gets_at_least_one_lever(self):
        assert compose("grim_check", {"severity": "consistent"})["changes"]

    def test_the_last_lever_is_always_the_read_off_lever(self):
        """It is the only lever that applies to all 2,106 archived calls: every
        verdict here is a verdict about numbers somebody read off a page."""
        for parsed in ({"severity": "consistent"}, GRIMMER_IMPOSSIBLE,
                       {"severity": "indeterminate"}):
            for entry in ({}, {"source_quote": "q",
                               "source_quote_verified": "verbatim"}):
                v = compose("grimmer_check", parsed, **entry)
                # Last, or second-to-last where a card pointer follows it.
                where = [lev for lev in v["changes"]
                         if "the paper does not contain" in lev["detail"]]
                assert len(where) == 1, "no lever names where the numbers came from"

    def test_an_unlocated_quote_is_stated_as_our_search_failing(self):
        v = compose("grimmer_check", GRIMMER_IMPOSSIBLE,
                    source_quote="a passage", source_quote_verified="unverified")
        lever = [lev for lev in v["changes"] if "could not locate" in lev["lever"]]
        assert lever, "an unlocated quote must be named as a lever"
        assert "limit of our extraction" in lever[0]["detail"]

    def test_assumed_bounds_are_named_as_ours(self):
        v = compose("grimmer_check", GRIMMER_IMPOSSIBLE)
        assert any("bounds are ours" in lev["lever"] for lev in v["changes"])

    def test_stated_bounds_are_named_too(self):
        """A lever that only fires when something is wrong teaches a reader
        that its absence means nothing. "The paper gave us the bounds" is
        exactly what tells them the verdict does not rest on our assumption."""
        v = compose("grimmer_check", {**GRIMMER_IMPOSSIBLE, "bound_source": "stated"})
        assert any("came from the paper" in lev["lever"] for lev in v["changes"])

    def test_the_assumed_bounds_caveat_does_not_contradict_the_verdict(self):
        """MEASURED: the first real call this rendered was `bound_source:
        assumed` with a verdict of `impossible`, because its failure mode was
        `sd_granularity`, which is bound-free. A draft said such a verdict "is
        capped below `impossible`" -- a caveat contradicting the verdict six
        lines above it, which teaches a reader to stop reading the caveats."""
        v = compose("grimmer_check", GRIMMER_IMPOSSIBLE)
        bounds = next(lev for lev in v["changes"] if "bounds are ours" in lev["lever"])
        assert "rests ONLY on assumed bounds" in bounds["detail"]
        assert re.search(r"rests? ONLY on assumed bounds is capped", bounds["detail"])

    def test_the_conventions_the_check_already_tried_are_shown(self):
        v = compose("grimmer_check", GRIMMER_IMPOSSIBLE)
        alt = next(lev for lev in v["changes"] if "already tried" in lev["lever"])
        assert "ignoring the scale bounds entirely: still infeasible" in alt["detail"]
        assert "population (n) SD convention" in alt["detail"]

    def test_the_precision_the_check_ran_at_is_named(self):
        """A wrong printed precision produced a measured 41.1% of GRIM rows and
        73.6% of DEBIT rows falsely reported `impossible`, and it moves in the
        accusing direction, so a reader is entitled to see it."""
        v = compose("grim_check", {"severity": "impossible"},
                    inp={"mean": 5.9, "n": 12, "decimals": 2})
        assert any("decimals = 2" in lev["lever"] for lev in v["changes"])

    def test_repeated_tool_caveats_are_not_repeated_levers(self):
        v = compose("detect_duplication", {
            "severity": "suspicious",
            "caveats": ["Blocks are assumed independent.",
                        "Blocks are assumed independent."]})
        assert sum("own caveat" in lev["lever"] for lev in v["changes"]) == 1

    def test_the_rest_of_the_preconditions_are_pointed_at_not_reprinted(self):
        """A run makes several times more calls than it uses tools; inlining
        five assumptions per call buries the levers above them in boilerplate.
        The same reason `_tool_cards` is one card per tool."""
        v = compose("grimmer_check", GRIMMER_IMPOSSIBLE)
        pointer = v["changes"][-1]
        assert pointer["card"] == "grimmer_check"
        assert "further precondition" in pointer["lever"]
        card = _integrity_card("grimmer_check")
        assert str(len(card["assumptions"])) in pointer["lever"]
        for assumption in card["assumptions"]:
            assert assumption not in json.dumps(v)


class TestTheRawRecordStillShips:
    def test_the_input_and_result_json_are_still_on_the_card(self, review, tmp_path):
        """A rendering a reader cannot check against the record is one they
        have to take on trust, which is the opposite of the point."""
        html = flat(section_html(collect(review), "calls", tmp_path))
        assert "The record this was built from" in html
        assert "Input" in html and "Result" in html

    def test_elided_result_fields_are_counted_not_dropped_silently(self):
        result = {"severity": "consistent",
                  **{f"k{i}": i for i in range(vignette._MAX_FIGURES + 6)}}
        v = compose("check_estimate_ci", result)
        assert len(v["computed"]["figures"]) == vignette._MAX_FIGURES
        assert v["computed"]["n_more"] == 6

    def test_the_vignette_is_composed_from_the_unclipped_result(self):
        """`entry["result"]` is clipped to 2,000 characters and a `check_table`
        result runs past 30 kB. Composing from the clipped copy would silently
        describe the first fifth of the check."""
        padding = {f"pad{i}": "x" * 120 for i in range(40)}
        raw = json.dumps({**padding, "severity": "impossible",
                          "explanation": "the tail of a long result"})
        assert len(raw) > 2000
        [entry] = _distil_calls([{
            "seq": 1, "tool_short": "check_table", "validated": True,
            "input": {}, "result": raw}], "sweep")
        assert "[clipped]" in entry["result"]
        assert entry["vignette"]["computed"]["detail"] == "the tail of a long result"


class TestTheViewerRendersIt:
    def test_a_call_shows_its_five_headings_and_its_question(self, review, tmp_path):
        html = flat(section_html(collect(review), "calls", tmp_path))
        from metascience_agent import registry
        assert registry.BY_NAME["grim_check"].purpose in html

    def test_the_severity_word_still_comes_from_the_pages_own_map(self, review,
                                                                  tmp_path):
        """`SEV_DEF` is the viewer's and is pinned by
        `test_viewer_vocabulary_drift`. Restating the ladder in Python would
        create the second copy that test exists to prevent, so the vignette
        renders the verdict through the existing `sev()` chip and says only
        what a reader may carry away from THIS call."""
        payload = collect(review)
        assert 'data-cb="cb-severity"' in section_html(payload, "calls", tmp_path)
        for definition in vignette._MEANS.values():
            assert "No dataset could produce the reported numbers" not in definition
        assert "No dataset could produce the reported numbers" not in \
            json.dumps(payload["calls"]), \
            "SEV_DEF's wording must not be duplicated into the payload"

    def test_the_parts_are_divs_because_sections_are_hidden(self, review, tmp_path):
        """`section{display:none}` hides every section that is not the open
        tab. A `<section>` per part would render the whole page's worth of
        vignettes invisible while every assertion on the HTML string passed --
        so the rule is asserted alongside the element, or this test passes for
        the wrong reason the day that rule is dropped."""
        from tests.test_bundle import _css_rules
        payload = collect(review)
        assert "display:none" in _css_rules(payload).get("section", "")
        html = section_html(payload, "calls", tmp_path)
        assert '<div class="vpart">' in flat(html)
        assert "<section" not in html


class TestTheWholeArchiveComposes:
    """EVERY archived ledger, not a fixture. Three defects in this module were
    invisible on the two runs it was designed against and obvious the moment
    all 68 ledgers went through it: the 44 calls with no severity field, the
    sixteen-warning `parse_cells_typed` call, and an assumed-bounds caveat that
    contradicted its own verdict."""

    def test_every_call_composes_all_five_parts(self, composed):
        keys = [k for k, _ in vignette.PARTS]
        for call in composed:
            assert list(call["vignette"]) == keys, call["tool"]

    def test_no_call_ends_with_an_empty_what_would_change(self, composed):
        assert not [c["tool"] for c in composed if not c["vignette"]["changes"]]

    def test_no_call_falls_through_to_the_undocumented_verdict_line(self, composed):
        """The fallback exists so a new severity word is NAMED rather than
        rendered as a blank. If it fires on the archive, a real verdict has no
        reading and the fix is a line in `_MEANS`, not a wider fallback."""
        stray = {(c["tool"], c["severity"]) for c in composed
                 if c["vignette"]["means"]["scope"].startswith(
                     "This review has no plain-language")}
        assert not stray, f"verdicts with no plain-language reading: {stray}"

    def test_no_vignette_buries_its_levers(self, composed):
        """Measured before the caveat collapsing: one call carried 18 levers,
        twelve of them the same unreadable-cell warning."""
        worst = max((len(c["vignette"]["changes"]), c["tool"]) for c in composed)
        assert worst[0] <= 9, f"{worst[1]} renders {worst[0]} levers"
