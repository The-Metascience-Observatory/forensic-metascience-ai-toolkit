"""A coefficient is not a mean, and the cell cannot tell you which.

`8.57 (3.03)` types as `mean_sd` whether it is a mean beside its standard
deviation or a regression coefficient beside its standard error. Only the
column band distinguishes them, and getting it wrong turns an honest paper into
an accusation.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from metascience_agent import prepass
from metascience_agent.prepass import reports_model_output, sweep_sd_range

CORPUS = pathlib.Path(__file__).resolve().parents[1] / "tests/fixtures/papers/high_value_pdfs_to_run_on"
AJCP = CORPUS / "10.1002--ajcp.70049"


class TestItRecognizesAModelOutputColumn:
    @pytest.mark.parametrize("label, needle", [
        ("Coefficient | M (SD)", "Coefficient"),
        ("Coefficient", "Coefficient"),
        ("Estimate", "Estimate"),
        ("aOR (95% CI)", "aOR"),
        ("Odds Ratio", "Odds Ratio"),
        ("Hazard ratio", "Hazard ratio"),
        ("Adjusted model 1", "Adjusted model"),
        ("Beta", "Beta"),
    ])
    def test_a_model_output_band_is_named(self, label, needle):
        why = reports_model_output(col_label=label)
        assert why and needle in why

    @pytest.mark.parametrize("label", [
        "b (SE)", "B (SE)", "Beta (SE)", "Est (SE)", "Within-person | b (SE)"])
    def test_a_coefficient_beside_its_standard_error_is_caught(self, label):
        """The COEFFICIENT SYMBOL is the evidence, not the SE. A regression
        coefficient's standard error is not a sample SD of any variable, so a
        plausibility ceiling derived from that variable's range does not apply
        -- but a bare `b` is too short a token to match safely, and paired with
        `(SE)` it is not."""
        why = reports_model_output(col_label=label)
        assert why and "coefficient beside" in why

    @pytest.mark.parametrize("label", ["Mean (SE)", "M (SE)", "Score, mean (SE)"])
    def test_an_ordinary_mean_with_its_standard_error_is_left_alone(self, label):
        """THIS WAS ONCE A BARE `(SE)` TEST, AND IT WAS WRONG. Measured over
        the 12-paper corpus, the bare rule blocked 168 cells and every one
        typed `mean_se` -- the typer had already recognised the parenthetical
        as a standard error and was routing them to `check_sd_or_se`, whose
        entire job is adjudicating SE-versus-SD columns. It removed real
        coverage and prevented nothing, since `b (SE)` types as `mean_se` too."""
        assert reports_model_output(col_label=label) is None

    @pytest.mark.parametrize("label", [
        "Mean (SD)", "M (SD)", "All coalitions", "Baseline", "Total (n = 64)"])
    def test_a_descriptive_column_is_left_alone(self, label):
        assert reports_model_output(col_label=label) is None

    def test_the_caption_is_a_fallback_when_the_band_is_silent(self):
        assert reports_model_output(
            caption="Associations between leadership and outcomes")
        assert reports_model_output(caption="Predictors of adherence")
        assert reports_model_output(
            caption="Coalition attributes and characteristics") is None

    def test_the_band_outranks_the_caption(self):
        """The band is the paper's own markup for THIS column; a caption
        describes the whole table."""
        why = reports_model_output(col_label="Coefficient | M (SD)",
                                   caption="Sample characteristics")
        assert "column" in why


class TestItOnlyEverRemovesChecks:
    """Invariant 1 applied here: this may narrow what a check does, never widen
    it. A false positive costs coverage; it cannot cost correctness."""

    @staticmethod
    def _table(col_label: str):
        """The real shape: `8.57 (3.03)` types as `mean_sd` only because the
        band carries `M (SD)` -- which is exactly the trap, since the same band
        also says `Coefficient`."""
        return [{"cells": [{"row": 1, "col": 1, "row_label": "Anxiety",
                            "col_label": col_label, "raw": "8.57 (3.03)"}],
                 "caption": ""}]

    def test_the_fixture_really_produces_a_target(self):
        """Guard against a fixture that proves nothing: without the band, this
        cell types as `ambiguous` and never reaches the check at all."""
        out = sweep_sd_range(self._table("M (SD)"), [], None)
        assert out["targets_enumerated"] == 1
        assert out["n_skipped_model_output"] == 0

    def test_nothing_is_added_to_the_denominator(self):
        out = sweep_sd_range(self._table("Coefficient | M (SD)"), [], None)
        assert out["targets_enumerated"] == 1
        assert out["n_checked"] == 0
        assert out["n_skipped_model_output"] == 1

    def test_a_skip_is_counted_and_explained_never_silent(self):
        out = sweep_sd_range(self._table("Coefficient | M (SD)"), [], None)
        assert out["n_skipped_model_output"] == 1
        assert any("Coefficient" in k for k in out["skipped_model_output_why"])

    def test_an_odds_ratio_band_never_reaches_this_guard(self):
        """Recorded rather than asserted as a guard hit: `aOR | M (SD)` types
        as an estimate upstream and never becomes a `mean_sd` target at all, so
        the guard is belt-and-braces there. The band the typer DOES route here
        is `Coefficient`, which is why that is the live case."""
        out = sweep_sd_range(self._table("aOR | M (SD)"), [], None)
        assert out["targets_enumerated"] == 0
        assert reports_model_output(col_label="aOR | M (SD)")


@pytest.mark.skipif(not AJCP.is_dir(), reason="working corpus not present")
class TestOnTheRealPaperThatMotivatedIt:
    """ajcp.70049 prints three regression tables whose column band reads
    `Coefficient | M (SD)`. Binding those rows to the variables their labels
    name and running check_sd_range returns `impossible` on an honest paper:
    SD 3.03 against a 1-5 scale, whose largest possible SD is 2.0. The verdict
    is arithmetically correct and completely wrong -- 3.03 is a standard error.
    """

    def _variables(self):
        run = AJCP / "forensic_review_gatetest2_2026-08-29" / "findings.v2.json"
        if not run.is_file():
            pytest.skip("the reference run is not present")
        return json.loads(run.read_text(encoding="utf-8"))["anatomy"]["variables"]

    def test_the_coefficient_cells_are_skipped(self):
        tables = prepass.paper_tables(AJCP, include_supplements=True)
        out = sweep_sd_range(tables, self._variables(), None)
        assert out["n_skipped_model_output"] == 63
        assert any("Coefficient" in k for k in out["skipped_model_output_why"])

    def test_binding_every_row_by_name_now_accuses_nobody(self):
        """The prototype binder that produced the false `impossible`. With the
        guard it produces none -- which is the property that makes improving
        the binder safe to attempt at all."""
        import re
        from metascience_agent.prepass import _norm_label

        kind = re.compile(
            r"\s*\((?:\s*(?:mean|sd|std|median|iqr|range|n|no|%|percent|se|sem"
            r"|ci|min|max)\b[^)]*)\)\s*$", re.I)

        def resolve(label, variables):
            raw = str(label or "")
            cands = [_norm_label(kind.sub("", raw))]
            if "|" in raw:
                cands.append(_norm_label(kind.sub("", raw.split("|")[-1])))
            for c in [x for x in dict.fromkeys(cands) if x]:
                hits = [v for v in variables
                        if _norm_label(v.get("name")) == c
                        or _norm_label(v.get("name")).startswith(c + " ")]
                if len(hits) == 1:
                    return hits[0]
                if len(hits) > 1:
                    return None
            return None

        variables = self._variables()
        tables = prepass.paper_tables(AJCP, include_supplements=True)
        bind = {}
        for tab in tables:
            for c in prepass._typed(tab.get("cells") or []):
                if c.get("kind") == "mean_sd" and c.get("sd") is not None:
                    v = resolve(c.get("row_label"), variables)
                    if v:
                        bind[c.get("row_label")] = v["id"]
        assert bind, "the prototype binder bound nothing; the test proves nothing"

        out = sweep_sd_range(tables, variables, bind)
        accusatory = [r for r in out["results"]
                      if r.get("severity") in ("impossible", "highly_suspicious",
                                               "suspicious")]
        assert accusatory == [], accusatory
        assert out["n_checked"] > 0, "the guard removed all coverage, not just the unsafe part"


class TestTheModelFacingToolHasTheSameGuard:
    """`check_table` is the surface the model actually calls WITH bindings, so
    it is where a coefficient most easily reaches an accusatory tool.

    MEASURED before the guard, on real cells from ajcp.70049 Table 4 bound to
    the 1-5 variable their row labels correctly name: `grim_check`,
    `grimmer_check` and `sprite_reconstruct` all ran, and `-0.05 (0.98)`
    returned `suspicious` -- GRIM reading a regression coefficient as a mean of
    a 1-5 scale. The paper is honest and the binding is right; the premise is
    wrong.
    """

    VARIABLE = {"id": "v_idm", "name": "Inclusive decision making",
                "measurement_level": "ordinal", "discreteness": "discrete",
                "family": "likert_item", "lower_bound": 1, "upper_bound": 5,
                "bounds_source": "stated", "derivation": "measured",
                "confidence": "high", "provenance_quote": "1-5 scale",
                "provenance_verdict": "verbatim"}

    def _run(self, raw: str, col_label: str):
        from metascience_agent.dispatch import check_table
        return check_table(
            cells=[{"raw": raw, "row_label": "Inclusive decision making",
                    "col_label": col_label, "n": 64}],
            variables=[self.VARIABLE],
            bindings={"Inclusive decision making": "v_idm"})

    @pytest.mark.parametrize("raw", ["-0.05 (0.98)", "8.57 (3.03)", "1.34 (0.60)"])
    def test_no_tool_runs_on_a_coefficient(self, raw):
        out = self._run(raw, "Coefficient | M (SD)")
        assert out["tools_run"] == []
        assert out["severity"] == "indeterminate"

    def test_the_accusation_that_used_to_fire_no_longer_does(self):
        """`-0.05 (0.98)` is the exact cell that returned `suspicious`."""
        out = self._run("-0.05 (0.98)", "Coefficient | M (SD)")
        assert out["severity"] not in ("suspicious", "highly_suspicious",
                                       "impossible")
        assert out["results"] == []

    def test_the_refusal_is_recorded_not_silent(self):
        out = self._run("-0.05 (0.98)", "Coefficient | M (SD)")
        reasons = [str(n.get("reason")) for n in (out.get("not_run") or [])]
        assert any("model output" in r for r in reasons), reasons
        assert any("Coefficient" in r for r in reasons), reasons

    def test_a_genuine_mean_on_the_same_variable_is_untouched(self):
        """The guard must remove the unsafe cells, not the coverage."""
        out = self._run("3.20 (0.81)", "M (SD)")
        assert out["tools_run"] == ["grim_check", "grimmer_check",
                                    "sprite_reconstruct"]
        assert out["severity"] == "consistent"

    def test_one_definition_shared_with_the_sweep(self):
        """Eleven hand-copied definitions of `ACCUSATORY` is why this is
        imported rather than restated."""
        from metascience_agent import dispatch, prepass
        assert (dispatch._reports_model_output("Coefficient")
                == prepass.reports_model_output(col_label="Coefficient"))


class TestTheDeclaredRangeReachesCheckSdOrSe:
    """One fact, two names. `Variable.forensic_kwargs` emits `scale_min` and
    `scale_max`; `check_sd_or_se`'s ToolSpec calls the same two numbers
    `variable_range_min` and `variable_range_max`. `_build_args` intersects by
    NAME, so a declared variable's range was dropped at the schema boundary and
    the tool received no bounds -- leaving it able to return nothing but
    `indeterminate` through `check_table`, on all 8 DISPATCH rows routing to it.
    """

    VARIABLE = {"id": "v1", "name": "Anxiety", "family": "likert_item",
                "lower_bound": 1, "upper_bound": 5,
                "measurement_level": "ordinal", "discreteness": "discrete",
                "derivation": "measured", "confidence": "high",
                "provenance_quote": "rated 1-5", "provenance_verdict": "verbatim",
                "bounds_source": "stated"}

    def _run(self, raw="3.20 (0.06)"):
        from metascience_agent.dispatch import check_table
        return check_table(
            cells=[{"raw": raw, "row_label": "Anxiety",
                    "col_label": "Mean (SE)", "n": 100}],
            variables=[self.VARIABLE], bindings={"Anxiety": "v1"})

    def test_the_tool_now_reaches_a_verdict(self):
        """Without bounds it could only ever say `indeterminate`."""
        out = self._run()
        assert "check_sd_or_se" in (out.get("tools_run") or [])
        assert out["severity"] != "indeterminate"

    def test_the_range_is_no_longer_dropped(self):
        from metascience_agent.dispatch import _build_args
        from metascience_agent.registry import SPECS
        spec = next(s for s in SPECS if s.name == "check_sd_or_se")
        dropped: set[str] = set()
        args = _build_args(spec, {"decimals_sd": 2},
                           {"reported_value": 0.06, "n": 100,
                            "scale_min": 1, "scale_max": 5,
                            "bound_source": "stated"}, 100, dropped)
        assert args.get("variable_range_min") == 1
        assert args.get("variable_range_max") == 5

    def test_it_only_aliases_and_never_invents(self):
        """The alias must not manufacture a bound where the variable declared
        none -- that is the route to a false accusation."""
        from metascience_agent.dispatch import _build_args
        from metascience_agent.registry import SPECS
        spec = next(s for s in SPECS if s.name == "check_sd_or_se")
        args = _build_args(spec, {"decimals_sd": 2},
                           {"reported_value": 0.06, "n": 100,
                            "bound_source": "assumed"}, 100, set())
        assert "variable_range_min" not in args
        assert "variable_range_max" not in args

    def test_an_explicit_target_name_is_not_overwritten(self):
        from metascience_agent.dispatch import _build_args
        from metascience_agent.registry import SPECS
        spec = next(s for s in SPECS if s.name == "check_sd_or_se")
        args = _build_args(spec, {"decimals_sd": 2},
                           {"reported_value": 0.06, "n": 100,
                            "scale_min": 1, "variable_range_min": 20,
                            "bound_source": "stated"}, 100, set())
        assert args["variable_range_min"] == 20
