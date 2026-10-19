"""GRIM's `impossible` rests on TWO premises, and only one of them was gated.

GREG, 2026-08-10, on the operating philosophy of this whole family:

    "GRIM/GRIMMER/SPRITE and that family are very unlikely to be applicable for
     most studies. It requires very specific variables, which are discrete, with
     known or reported ranges, and with ascertainable granularity. I think that
     any such test should be 'guilty until proven innocent' owing to this low
     prior probability. These kinds of GRIM-tractable instruments are mainly in
     psychology, and we will be using this tool across many fields."

The asymmetry he is pointing at was real and sat in the code for months.
`bound_source` has been gated since #87 -- a range violation against a scale WE
invented caps at `suspicious`, because our invention is not the paper's claim.
The GRANULARITY branch reached `impossible` unconditionally, on a premise of
exactly the same kind: that each subject contributed a WHOLE NUMBER. Nothing in
the arithmetic establishes that. It arrives as `data_type`, which is the model's
reading of prose, and `impossible` is the top of the ladder -- the claim that no
honest sample could have produced this number.

MEASURED, on systolic blood pressure 128.43 asserted as `likert`: 29 of 495
sample sizes returned `impossible` before this gate and 0 after. That is 29
potential false accusations against a continuous clinical measure, bought back
at the cost of requiring the paper to say its data are integers.
"""
import pytest

from metascience_agent.anatomy import Variable
from metascience_agent.tools.grim import (
    DISCRETENESS_CAVEAT, HARD_DISCRETENESS_SOURCES, granularity_ceiling, grim_test,
)
from metascience_agent.tools.sd_checks import grimmer_test
from metascience_agent.tools.sprite import sprite_reconstruct

#: 5.51 x 30 = 165.3. No integer total rounds to it under round-half OR
#: truncation, so this is a genuine granularity failure on every scale -- the
#: case where the ceiling, and only the ceiling, is what varies.
IMPOSSIBLE_MEAN = dict(mean=5.51, n=30, decimals=2, data_type="likert")


class TestTheRule:
    def test_only_two_words_license_impossible(self):
        assert HARD_DISCRETENESS_SOURCES == {"stated", "logically_necessary"}

    @pytest.mark.parametrize("source", ["stated", "logically_necessary"])
    def test_a_demonstrated_premise_reaches_the_top_of_the_ladder(self, source):
        assert granularity_ceiling(source) == "impossible"

    @pytest.mark.parametrize("source", ["assumed", "", None, "STATED_BY_MODEL", "probably"])
    def test_everything_else_caps(self, source):
        """Including the empty and unknown cases: an unrecognised word is not a
        licence, for the same reason `canonical_data_type` maps one to
        `unknown`. A gate that fails open is not a gate."""
        assert granularity_ceiling(source) == "suspicious"

    def test_the_words_are_case_and_space_insensitive(self):
        assert granularity_ceiling("  Stated ") == "impossible"


class TestTheThreeToolsAgree:
    """One cell, three tools, one verdict. Two prior bugs in this repo were
    exactly this failure: `grim_check` said `suspicious` on a cell
    `grimmer_check` called `impossible`, and `composite` certified a denominator
    that `check_count_percent` then convicted."""

    def test_grim(self):
        assert grim_test(**IMPOSSIBLE_MEAN)["severity"] == "suspicious"
        assert grim_test(**IMPOSSIBLE_MEAN,
                         discreteness_source="stated")["severity"] == "impossible"

    def test_grimmer(self):
        args = dict(mean=5.51, sd=1.0, n=30, data_type="likert")
        assert grimmer_test(**args)["severity"] == "suspicious"
        assert grimmer_test(**args, discreteness_source="stated")["severity"] == "impossible"

    def test_sprite(self):
        args = dict(mean=5.51, sd=1.2, n=30, data_type="likert")
        assert sprite_reconstruct(**args)["outcome"] == "grim_fail"
        assert sprite_reconstruct(**args)["severity"] == "suspicious"
        assert sprite_reconstruct(**args,
                                  discreteness_source="stated")["severity"] == "impossible"


class TestTheDemotionIsExplained:
    """A verdict one rung lower than the arithmetic warrants reads as a WEAKER
    FINDING unless it says why, and the reader cannot then go and supply the
    missing premise."""

    def test_grim_says_which_premise_is_missing(self):
        r = grim_test(**IMPOSSIBLE_MEAN)
        assert r["failure_mode"] == "granularity"
        assert r["discreteness_caveat"] == DISCRETENESS_CAVEAT
        assert "whole number" in r["discreteness_caveat"].lower()
        assert "discreteness_source='stated'" in r["discreteness_caveat"]

    def test_no_caveat_when_nothing_was_capped(self):
        assert "discreteness_caveat" not in grim_test(**IMPOSSIBLE_MEAN,
                                                      discreteness_source="stated")

    def test_the_source_is_echoed_for_the_audit_trail(self):
        for src in ("assumed", "stated"):
            assert grim_test(**IMPOSSIBLE_MEAN,
                             discreteness_source=src)["discreteness_source"] == src

    def test_sprite_puts_it_in_the_prose_a_reader_actually_sees(self):
        r = sprite_reconstruct(5.51, 1.2, n=30, data_type="likert")
        assert "whole number" in r["explanation"].lower()


class TestItDoesNotBluntTheCheck:
    """A cap that swallowed real detections would be worse than none. The
    arithmetic, the failure mode and the reconstruction are untouched -- only
    the WORD changes."""

    def test_a_consistent_mean_is_still_consistent(self):
        assert grim_test(mean=5.0, n=30, decimals=2,
                         data_type="likert")["severity"] == "consistent"

    def test_the_failure_is_still_reported_and_still_a_finding(self):
        r = grim_test(**IMPOSSIBLE_MEAN)
        assert r["consistent"] is False
        assert r["applicable"] is True
        assert r["failure_mode"] == "granularity"
        assert r["severity"] != "consistent", (
            "a capped granularity failure must still REACH the reader -- demoting "
            "it to `consistent` would be the false all-clear this gate exists to "
            "avoid on the other side"
        )

    def test_the_continuous_refusal_is_unchanged(self):
        """The applicability guard fires first and is not affected: a continuous
        measure is REFUSED, not demoted."""
        r = grim_test(mean=128.43, n=100, data_type="continuous")
        assert r["severity"] == "indeterminate" and r["applicable"] is False

    def test_out_of_range_still_keys_on_the_BOUNDS(self):
        """The two gates are independent. A range failure is about the scale,
        so `discreteness_source` must not move it either way."""
        args = dict(mean=9.0, n=30, scale_min=1, scale_max=7, decimals=1,
                    data_type="likert", bound_source="stated")
        r = grim_test(**args, discreteness_source="assumed")
        assert r["failure_mode"] == "out_of_range" and r["severity"] == "impossible"


class TestTheEvidenceBar:
    """`Variable.discreteness_source` is where the premise is adjudicated, and
    the model must not be able to write its own licence."""

    def _v(self, **kw):
        base = dict(id="v", name="x", family="likert_item",
                    discreteness="discrete", confidence="high")
        v = Variable(**{**base, **{k: val for k, val in kw.items()
                                   if k != "provenance_verdict"}})
        v.provenance_verdict = kw.get("provenance_verdict", "verbatim")
        return v

    def test_a_verified_quote_plus_high_confidence_licenses_it(self):
        assert self._v().discreteness_source() == "stated"

    @pytest.mark.parametrize("verdict", ["stitched", "unverified", "absent", None])
    def test_an_unverified_quote_does_not(self, verdict):
        """`stitched` means WE assembled the sentence and it is not in the paper.
        `unverified` means our search failed, which is not evidence either way
        and so is not evidence FOR."""
        assert self._v(provenance_verdict=verdict).discreteness_source() == "assumed"

    @pytest.mark.parametrize("confidence", ["medium", "low"])
    def test_confidence_below_high_does_not(self, confidence):
        assert self._v(confidence=confidence).discreteness_source() == "assumed"

    @pytest.mark.parametrize("discreteness", ["continuous", "unknown", ""])
    def test_the_declaration_itself_must_say_discrete(self, discreteness):
        """`Variable.discreteness` existed from the first schema and NO CHECK
        HAD EVER READ IT -- the house failure pattern, built and never consumed.
        Declining to commit ("unknown") reads as not-demonstrated."""
        assert self._v(discreteness=discreteness).discreteness_source() == "assumed"

    def test_a_likert_composite_the_model_called_continuous_is_capped(self):
        """The most common real case in the archive: 28 `likert_composite`
        variables declared `continuous`. A mean of k items moves in steps of
        1/(k*n), not 1/n, so GRIM's denominator is wrong for them and an
        `impossible` would be manufactured."""
        v = self._v(family="likert_composite", discreteness="continuous")
        assert v.discreteness_source() == "assumed"

    def test_it_reaches_the_tools_through_forensic_kwargs(self):
        """Emitted for EVERY variable, bounded or not: a granularity failure
        needs no bounds, which is exactly why it was reaching `impossible`
        unchecked."""
        assert self._v().forensic_kwargs()["discreteness_source"] == "stated"
        unbounded = self._v(provenance_verdict=None)
        assert unbounded.forensic_kwargs()["discreteness_source"] == "assumed"


class TestWhatThisCostsOnTheProductionPath:
    """MEASURED 2026-08-10, and recorded here because it is the thing a future
    reader most needs to know about this gate.

    `provenance_verdict` is stamped by `agent._annotate_quotes`, which runs
    AFTER the model's tool calls. So no variable has ever reached `check_table`
    carrying one -- verified across every archived run -- and on that path
    `discreteness_source` is therefore ALWAYS `assumed`.

    The gate is consequently ABSOLUTE for table-path GRIM, not evidential. The
    pre-existing `bounds_are_stated` gate has exactly the same shape and the
    same consequence, which nothing had noticed. Making either genuinely
    evidential means verifying variable quotes BEFORE dispatch, which is a
    separate change; until then this test states the true behaviour so the
    limitation cannot be mistaken for a bug or quietly forgotten.
    """

    def test_a_model_supplied_variable_cannot_license_impossible(self):
        from metascience_agent.dispatch import _as_variable
        raw = {"id": "v1", "name": "Anxiety", "family": "likert_item",
               "discreteness": "discrete", "confidence": "high",
               # Forged: the model tries to certify its own quote.
               "provenance_verdict": "verbatim"}
        v = _as_variable(raw)
        assert v.provenance_verdict is None, "PIPELINE_ONLY_FIELDS must strip it"
        assert v.discreteness_source() == "assumed"
        assert v.forensic_kwargs()["discreteness_source"] == "assumed"

    def test_the_bound_gate_has_the_same_shape(self):
        """Pinned so the two are fixed together when the ordering is fixed."""
        from metascience_agent.dispatch import _as_variable
        v = _as_variable({"id": "v1", "name": "x", "family": "likert_item",
                          "lower_bound": 1, "upper_bound": 7, "confidence": "high",
                          "provenance_verdict": "verbatim"})
        assert v.bounds_are_stated() is False
        assert v.forensic_kwargs()["bound_source"] == "assumed"


class TestTheBloodPressureSweep:
    """The measurement that motivated the gate, kept executable."""

    def test_asserting_likert_on_a_blood_pressure_no_longer_accuses(self):
        capped = sum(grim_test(128.43, n, data_type="likert")["severity"] == "impossible"
                     for n in range(5, 500))
        licensed = sum(grim_test(128.43, n, data_type="likert",
                                 discreteness_source="stated")["severity"] == "impossible"
                       for n in range(5, 500))
        assert (capped, licensed) == (0, 29)
