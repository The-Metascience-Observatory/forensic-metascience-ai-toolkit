"""The four refusals that live in `ToolSpec.call`, before any tool runs.

This file started as the measured-value gate alone and now covers all four
argument-coercion gates, because they share one property that is the whole
point: each one turns a verdict that had NOTHING TO DO WITH THE PAPER into an
`indeterminate`. NaN from a failed cell extraction, a figure-read value, a
missing printed precision, a batch whose rows are measured -- none of these is
evidence about an author, and every one of them used to come back as
`impossible`, `highly_suspicious` or `suspicious`.

Exact-arithmetic checks must REFUSE measured values, not merely soften them.

WHY REFUSAL AND NOT A CAP
-------------------------
Every other unverified premise in this repo is handled by capping severity: an
`assumed` scale bound caps GRIM at `suspicious` rather than `impossible`. That
is right when the arithmetic stays valid and only a premise is borrowed.

A measured value is different in kind, for two independent reasons.

SEMANTIC: `impossible` is a claim about the paper's own printed numerals -- "no
dataset produces that mean". A value read off a chart was never asserted by the
paper; it is OUR measurement of the authors' rendering of a number they did not
print. That bar would hold even if digitization error went to zero.

ARITHMETIC: a figure-read mean on a 1-7 scale at 400px carries sigma ~0.023.
GRIM's decision window at 2 dp is 0.005, and admissible means at n=30 are spaced
1/30 = 0.033 apart. So the noise is ~5x the window and comparable to the entire
granularity spacing: a genuinely consistent mean perturbed that far lands back
inside an admissible window only about 30% of the time. GRIM would call it
impossible roughly 70% of the time. Capping a 70% false-positive rate to
`suspicious` does not fix it -- it relabels false accusations as softer false
accusations.

Hence: refuse. This is `celltypes`-style ("run nothing on a value whose meaning
is unknown"), not `bound_source`-style.
"""
import pytest

from metascience_agent import registry as R
from metascience_observatory_image_analysis.extraction.figures import (
    AS_PRINTED,
    MEASURED,
    MEASURED_RASTER,
    PRINTED_FIGURE,
    Provenance,
    combine,
    dispersion_relative_error,
)

EXACT_CHECKS = [s.name for s in R.SPECS if s.is_exact_check()]


class TestTheGate:
    @pytest.mark.parametrize("name", EXACT_CHECKS)
    def test_exact_checks_refuse_measured_input(self, name):
        spec = R.BY_NAME[name]
        param = sorted(spec.exact_params())[0]
        out = spec.call({param: 1.0, "uncertainty": {param: 0.05}})
        assert out["severity"] == "indeterminate", f"{name} did not refuse"
        assert out["applicable"] is False
        assert param in out["measured_params"]

    @pytest.mark.parametrize("name", EXACT_CHECKS)
    def test_refusal_never_accuses(self, name):
        """A refusal is not a soft finding and must never read as one."""
        spec = R.BY_NAME[name]
        param = sorted(spec.exact_params())[0]
        out = spec.call({param: 1.0, "uncertainty": {param: 0.05}})
        assert out["severity"] not in ("impossible", "highly_suspicious", "suspicious")
        assert "not a statement about the paper" in out["explanation"]

    def test_printed_values_are_unaffected(self):
        """No uncertainty key -> the full ladder, exactly as before."""
        out = R.BY_NAME["grim_check"].call(
            {"mean": 5.51, "n": 30, "decimals": 2, "data_type": "likert",
             "discreteness_source": "stated"})
        assert out["severity"] == "impossible"
        assert out["applicable"] is True

    def test_uncertainty_on_a_NON_exact_param_does_not_block(self):
        """Only the load-bearing params gate. A sigma on something else is noise."""
        out = R.BY_NAME["grim_check"].call(
            {"mean": 5.51, "n": 30, "decimals": 2, "data_type": "likert",
             "discreteness_source": "stated",
             "uncertainty": {"scale_max": 0.1}})
        assert out["severity"] == "impossible"

    def test_tolerant_checks_still_run_on_measured_input(self):
        """The point of the split: some checks survive digitization error."""
        out = R.BY_NAME["check_effect_plausibility"].call(
            {"d": 3.5, "field": "psychotherapy", "uncertainty": {"d": 0.2}})
        assert out["severity"] == "suspicious"

    def test_uncertainty_is_never_passed_to_the_implementation(self):
        """It is gate metadata; leaking it would be a TypeError at call time."""
        out = R.BY_NAME["check_estimate_ci"].call(
            {"estimate": 1.42, "ci_low": 1.08, "ci_high": 1.87, "uncertainty": {"estimate": 0.01}})
        assert "severity" in out


class TestTheBatchFormOfTheGate:
    """A batch tool's exact param is the row LIST, so the stamp is one level down.

    The branch that looks inside the list existed but had never run: `blocked`
    was `frozenset & set`, i.e. a frozenset, so `blocked.add(p)` raised
    `AttributeError: 'frozenset' object has no attribute 'add'`. Measured before
    the fix, on exactly the arguments below:

        debit_check_batch(rows=[{mean, sd, n}], uncertainty={"mean": 0.05})
            -> AttributeError

    A crash is not a refusal. Through MCP it surfaces as a tool error, on the one
    input -- a figure-derived batch -- that most needs a stated `indeterminate`.
    The comment claiming the batch branch was verified (commit 2b6b766) was
    therefore describing behaviour the code could not produce; only the DEFECT it
    names was real.
    """

    ROWS = [{"mean": 0.3, "sd": 0.3, "n": 50}, {"mean": 0.4, "sd": 0.49, "n": 50}]

    def test_a_measured_row_refuses_the_whole_batch(self):
        out = R.BY_NAME["debit_check_batch"].call(
            {"rows": list(self.ROWS), "uncertainty": {"mean": 0.05}})
        assert out["severity"] == "indeterminate"
        assert out["applicable"] is False
        assert out["measured_params"] == ["rows"]

    def test_the_batch_and_the_single_agree(self):
        """The defect was a DISAGREEMENT between the two forms of one check."""
        single = R.BY_NAME["debit_check"].call(
            {"mean": 0.3, "sd": 0.3, "n": 50, "decimals_mean": 1, "decimals_sd": 1,
             "data_type": "binary", "uncertainty": {"mean": 0.05}})
        batch = R.BY_NAME["debit_check_batch"].call(
            {"rows": list(self.ROWS), "uncertainty": {"mean": 0.05}})
        assert single["severity"] == batch["severity"] == "indeterminate"

    def test_a_stamp_naming_nothing_in_the_rows_does_not_block(self):
        """The gate looks for the stamped FIELD, not merely for a stamp."""
        out = R.BY_NAME["debit_check_batch"].call(
            {"rows": list(self.ROWS), "data_type": "binary",
             "uncertainty": {"nothing_here": 0.05}})
        assert out["severity"] != "indeterminate" or "measured_params" not in out


class TestNonFiniteInputIsRefused:
    """NaN is OUR extraction failing, never the author's arithmetic.

    An empty cell, an en dash, a footnote marker read as a number: all arrive as
    NaN, and every one of these paths published it as a finding. MEASURED before
    the fix, through `ToolSpec.call`:

        check_sd_range(sd=nan, 1, 7)            -> impossible
        grim_percentage(percentage=nan, n=49)   -> impossible
        stalt_check(calculated_p=nan)           -> highly_suspicious
        check_estimate_ci(estimate=nan)         -> suspicious
        check_summation(values=[nan, 50], 100)  -> suspicious
        grim_check(mean=nan) / grimmer_check    -> ValueError

    `check_sd_range` is the proof that these are artefacts and not arithmetic:
    it emitted "SD of nan exceeds maximum possible SD of 3.0000", and `nan >
    3.0` is False. The sentence was reachable only down an else branch.
    """

    NAN = float("nan")
    INF = float("inf")

    ACCUSING_BEFORE = [
        ("check_sd_range", {"sd": NAN, "min_val": 1, "max_val": 7}),
        ("grim_percentage", {"percentage": NAN, "n": 49}),
        ("stalt_check", {"calculated_p": NAN, "reported_threshold": "<0.05"}),
        ("check_estimate_ci", {"estimate": NAN, "ci_low": 1.08, "ci_high": 1.87}),
        ("check_summation", {"values": [NAN, 50.0], "expected_sum": 100.0,
                             "decimals": [1, 1]}),
        ("grim_check", {"mean": NAN, "n": 30, "decimals": 2, "data_type": "likert"}),
        ("grimmer_check", {"mean": NAN, "sd": 1.0, "n": 30, "decimals": 2,
                           "decimals_sd": 2, "data_type": "likert"}),
    ]

    @pytest.mark.parametrize("name,args", ACCUSING_BEFORE,
                             ids=[n for n, _ in ACCUSING_BEFORE])
    def test_a_nan_is_refused_not_judged(self, name, args):
        out = R.BY_NAME[name].call(dict(args))
        assert out["severity"] == "indeterminate", f"{name} judged a NaN"
        assert out["applicable"] is False
        assert out["nonfinite_params"]

    @pytest.mark.parametrize("name,args", ACCUSING_BEFORE,
                             ids=[n for n, _ in ACCUSING_BEFORE])
    def test_the_refusal_never_reads_as_a_finding(self, name, args):
        out = R.BY_NAME[name].call(dict(args))
        assert out["severity"] not in ("impossible", "highly_suspicious", "suspicious")
        assert "not a statement about the paper" in out["explanation"]

    def test_infinity_is_refused_on_the_same_terms(self):
        """An upstream divide-by-zero, not a claim. Same class, same answer."""
        out = R.BY_NAME["check_sd_range"].call(
            {"sd": self.INF, "min_val": 1, "max_val": 7})
        assert out["severity"] == "indeterminate"

    def test_a_nan_inside_a_batch_row_is_found(self):
        """The scan is recursive because the batch tools take the same numbers
        one level down -- the exact gap the measured-value gate had."""
        out = R.BY_NAME["debit_check_batch"].call(
            {"rows": [{"mean": self.NAN, "sd": 0.3, "n": 50}]})
        assert out["severity"] == "indeterminate"
        assert out["nonfinite_params"] == ["rows[0].mean"]

    def test_the_offending_argument_is_named(self):
        """A refusal that does not say WHICH value failed cannot be acted on."""
        out = R.BY_NAME["check_estimate_ci"].call(
            {"estimate": self.NAN, "ci_low": 1.08, "ci_high": 1.87})
        assert out["nonfinite_params"] == ["estimate"]

    def test_finite_arguments_are_untouched(self):
        # Finite inputs are judged, not refused. The verdict is
        # `highly_suspicious` rather than `impossible` because the registry
        # path cannot state a `bound_source`, so the 1-7 range counts as
        # assumed (see test_sd_range_bounds.py::TestBoundSourceCapsTheVerdict).
        out = R.BY_NAME["check_sd_range"].call({"sd": 9.0, "min_val": 1, "max_val": 7})
        assert out["severity"] == "highly_suspicious"
        assert out["is_plausible"] is False


class TestPrintedPrecisionIsRequired:
    """A missing printed precision is refused, not defaulted to 2 decimals.

    MEASURED before the fix, through `ToolSpec.call`:

        grim_check(mean=5.9, n=12, data_type='likert')  -> impossible
        ... the same call with decimals=1                -> consistent
        debit_check(mean=0.3, sd=0.5, n=50, binary)      -> impossible
        ... the same call with decimals_mean/_sd=1       -> consistent

    Conditioned on rows consistent at 1 dp, the 2-dp default returned a false
    `impossible` on 41.1% of GRIM rows and 73.6% of DEBIT rows. The error is
    one-directional: too many digits always SHRINKS the admissible set, and a
    smaller admissible set is what `impossible` means.
    """

    def test_grim_refuses_without_decimals(self):
        out = R.BY_NAME["grim_check"].call({"mean": 5.9, "n": 12, "data_type": "likert"})
        assert out["severity"] == "indeterminate"
        assert out["missing_precision_params"] == ["decimals"]

    def test_grim_stops_refusing_for_want_of_PRECISION(self):
        """The gate under test is the precision one, and supplying `decimals`
        must clear it.

        This used to assert `consistent`, and later measurement overturned that:
        at n = 12 and 1 dp GRIM has NO discriminating power -- every printable
        value is attainable -- so the row was never "clear at the printed
        precision", it was UNCHECKABLE at that precision.

        That also reframes this class's own headline number. The 41.1% of GRIM
        rows that flipped from `impossible` at the 2-dp default to `consistent`
        at 1 dp did not become consistent; they became unmeasurable. The
        precision gate is still right, and what it buys is a refusal instead of
        a false accusation -- not a clean bill of health.
        """
        out = R.BY_NAME["grim_check"].call(
            {"mean": 5.9, "n": 12, "decimals": 1, "data_type": "likert"})
        assert "missing_precision_params" not in out
        assert out["failure_mode"] == "no_discriminating_power"

    def test_grim_still_accuses_a_genuinely_impossible_mean(self):
        """The gate must not blunt the check -- only stop it guessing."""
        out = R.BY_NAME["grim_check"].call(
            {"mean": 5.51, "n": 30, "decimals": 2, "data_type": "likert",
             "discreteness_source": "stated"})
        assert out["severity"] == "impossible"

    def test_debit_refuses_without_both_precisions(self):
        out = R.BY_NAME["debit_check"].call(
            {"mean": 0.3, "sd": 0.5, "n": 50, "data_type": "binary"})
        assert out["severity"] == "indeterminate"
        assert out["missing_precision_params"] == ["decimals_mean", "decimals_sd"]

    def test_debit_runs_at_the_printed_precision(self):
        out = R.BY_NAME["debit_check"].call(
            {"mean": 0.3, "sd": 0.5, "n": 50, "decimals_mean": 1, "decimals_sd": 1,
             "data_type": "binary"})
        assert out["severity"] == "consistent"

    def test_an_explicit_none_is_the_same_as_omitting_it(self):
        """A model that sends `decimals: null` has not declared anything."""
        out = R.BY_NAME["grim_check"].call(
            {"mean": 5.9, "n": 12, "decimals": None, "data_type": "likert"})
        assert out["severity"] == "indeterminate"

    def test_zero_decimals_is_a_declaration_not_a_gap(self):
        """A mean printed `6` is 0 dp; falsy, and it must not be mistaken for a
        MISSING declaration.

        Both now return `indeterminate`, so the severity no longer separates
        them -- but the reason does, and the reason is the whole point. An
        omitted `decimals` is a gap in what we were told; `decimals: 0` is a
        complete declaration of a precision at which GRIM simply has no
        resolution (at 0 dp it has none at any n). Distinguishing "you did not
        tell us" from "you told us, and it does not help" is what stops the
        precision gate reading as a data-entry complaint.
        """
        zero = R.BY_NAME["grim_check"].call(
            {"mean": 6.0, "n": 12, "decimals": 0, "data_type": "likert"})
        omitted = R.BY_NAME["grim_check"].call(
            {"mean": 6.0, "n": 12, "data_type": "likert"})
        assert "missing_precision_params" not in zero
        assert zero["failure_mode"] == "no_discriminating_power"
        assert omitted["missing_precision_params"] == ["decimals"]

    def test_the_refusal_never_reads_as_a_finding(self):
        out = R.BY_NAME["debit_check"].call(
            {"mean": 0.3, "sd": 0.5, "n": 50, "data_type": "binary"})
        assert out["severity"] not in ("impossible", "highly_suspicious", "suspicious")
        assert "not a statement about the paper" in out["explanation"]


class TestProvenanceOnTheDirectCall:
    """`check_table` took `provenance`; the single-tool call did not.

    So the same figure-read number was refused through the table path and judged
    through the per-cell path -- and the per-cell path is the only one stage 2
    has, since `check_table` is stage-1-only. The registry now converts a
    measured provenance into an `uncertainty` stamp on every exact param, which
    is exactly what `dispatch.check_table` already did.
    """

    EXACT = [s.name for s in R.SPECS if s.is_exact_check()]

    @pytest.mark.parametrize("name", EXACT)
    def test_every_exact_check_takes_provenance(self, name):
        assert "provenance" in R.BY_NAME[name].schema()

    @pytest.mark.parametrize("source", ["measured_raster", "measured_vector",
                                        "figure_pixels"])
    def test_a_measured_provenance_refuses(self, source):
        out = R.BY_NAME["grim_check"].call(
            {"mean": 5.51, "n": 30, "decimals": 2, "data_type": "likert",
             "provenance": source})
        assert out["severity"] == "indeterminate"
        assert "mean" in out["measured_params"]

    @pytest.mark.parametrize("source", ["printed_text", "printed_table", None])
    def test_a_printed_provenance_runs(self, source):
        args = {"mean": 5.51, "n": 30, "decimals": 2, "data_type": "likert",
                "discreteness_source": "stated"}
        if source is not None:
            args["provenance"] = source
        assert R.BY_NAME["grim_check"].call(args)["severity"] == "impossible"

    def test_provenance_never_reaches_the_implementation(self):
        """It is gate metadata; `grim_test()` has no such parameter, so leaking
        it would be a TypeError at call time rather than a wrong answer."""
        out = R.BY_NAME["grim_check"].call(
            {"mean": 5.51, "n": 30, "decimals": 2, "data_type": "likert",
             "provenance": "printed_table"})
        assert "severity" in out

    def test_a_tolerant_check_is_not_gated_by_provenance(self):
        """`check_effect_plausibility` is the check that WORKS on figure data;
        its own `provenance` param is a real argument, not a refusal trigger."""
        out = R.BY_NAME["check_effect_plausibility"].call(
            {"d": 3.5, "field": "psychotherapy", "provenance": "measured_raster"})
        assert out["severity"] == "suspicious"


class TestHelpReachesTheModel:
    """14 authored help strings were declared here and reached nobody.

    `schema()` returned `{name: type}`, dropping `Param.help` entirely, so
    "Printed decimals of b, read from the literal" existed in the registry and
    in no schema the model ever saw. Advice that exists and is invisible is the
    same class of defect as the six omissions this module was built to prevent.
    """

    def test_help_is_carried_into_the_schema(self):
        from typing import Annotated, get_args, get_origin
        ann = R.BY_NAME["check_regression"].schema()["decimals_b"]
        assert get_origin(ann) is Annotated
        assert get_args(ann)[0] is int
        assert "read from the literal" in get_args(ann)[1]

    def test_a_param_without_help_stays_a_bare_type(self):
        assert R.BY_NAME["check_regression"].schema()["b"] is float

    def test_the_server_turns_help_into_a_json_schema_description(self):
        """The whole point: it has to survive into what the model is shown.

        Pinned at the seam WE own -- `mcp_server._to_json_schema`, the
        conversion the stdio server actually serves -- not at the SDK's
        private `_python_type_to_json_schema`, which this SDK version
        removed (and whose own dict conversion drops Annotated help AND
        mistypes the param as string; the server function exists precisely
        because of that)."""
        from metascience_agent.mcp_server import _to_json_schema
        props = _to_json_schema(R.BY_NAME["grim_check"].schema())["properties"]
        assert "the wrong one accuses" in props["decimals"]["description"]
        assert props["decimals"]["type"] == "integer", \
            "Annotated[int, help] must stay an integer, not fall to string"

    def test_every_authored_help_string_is_reachable(self):
        helped = {(s.name, p.name) for s in R.SPECS for p in s.params
                  if p.help and not p.withheld}
        assert helped, "no help strings declared at all"
        for tool, param in helped:
            from typing import Annotated, get_origin
            assert get_origin(R.BY_NAME[tool].schema()[param]) is Annotated


class TestProvenance:
    def test_a_numeral_printed_in_a_figure_is_a_printed_number(self):
        """The split is as-printed vs measured, NOT text vs figure.

        A data label, an in-panel n, an exact p in a legend -- the authors
        asserted these. Refusing them would throw away most of what figures
        uniquely contain.
        """
        p = Provenance(source=PRINTED_FIGURE)
        assert p.is_as_printed is True
        assert p.is_measured is False
        assert p.tier == 0

    def test_measured_is_not_as_printed(self):
        p = Provenance(source=MEASURED_RASTER)
        assert p.is_as_printed is False and p.is_measured is True

    def test_taint_propagates_through_derivation(self):
        """No chain of arithmetic launders a measured value into a printed one."""
        p = Provenance(source=MEASURED_RASTER).derive("converted to an effect size")
        assert p.is_measured is True
        assert p.source == MEASURED_RASTER

    def test_a_printed_value_derives_to_merely_derived(self):
        p = Provenance(source=PRINTED_FIGURE).derive()
        assert p.is_measured is False and p.tier == 1

    def test_combining_takes_the_weakest(self):
        """An effect size from a printed n and a measured mean is measured."""
        p = combine(Provenance(source=PRINTED_FIGURE), Provenance(source=MEASURED_RASTER))
        assert p.is_measured is True

    def test_as_printed_and_measured_are_disjoint(self):
        assert not (AS_PRINTED & MEASURED)


class TestErrorBudgetFromGeometry:
    """Sigma is computed per value from the geometry, not assumed globally.

    A single global 4% is simultaneously far too lenient for a 4-pixel error-bar
    cap and far too strict for a 200-pixel one, and it discards the only
    information that lets a downstream check gate itself.
    """

    def test_reproduces_the_measured_benchmark(self):
        """The analytic model must land on Greg's empirical numbers.

        3.89% median and 27.7% worst case were measured by clicking; caps of
        ~36 px and ~5 px reproduce them from geometry alone.

        THE PREVIOUS VALUES HERE WERE RETRACTED, and this test was the fifth
        and last site still asserting them. 4.15% / 37.3% came from a
        figure-extractor benchmark seeded with `hash()`, which CPython salts
        per process -- so, as that repo's README says, they "could not be
        reproduced by anyone, including its author". A test asserting a
        withdrawn measurement passes forever and pins the model to it.
        """
        assert dispersion_relative_error(36) == pytest.approx(0.0389, abs=0.004)
        assert dispersion_relative_error(5) == pytest.approx(0.277, abs=0.02)

    def test_the_retracted_benchmark_is_not_reproduced(self):
        """A guard against the old numbers creeping back: 4 px was the cap
        implied by the retracted 37.3%, and it is not the cap implied by the
        27.7% that replaced it."""
        assert dispersion_relative_error(4) > 0.30

    def test_shorter_caps_are_worse(self):
        assert dispersion_relative_error(4) > dispersion_relative_error(34) > \
               dispersion_relative_error(200)

    def test_zero_height_is_infinite_not_a_crash(self):
        assert dispersion_relative_error(0) == float("inf")
