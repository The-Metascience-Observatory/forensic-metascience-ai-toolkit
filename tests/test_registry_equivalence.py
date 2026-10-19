"""The registry's derived surface is pinned, and every tool actually runs.

The switch from 38 hand-written MCP wrappers to registry-derived ones was
verified tool-by-tool before it landed: 52 argument cases across all 38 tools,
byte-identical MCP responses old-vs-new. Those wrappers no longer exist, so that
comparison cannot be re-run. Two things replace it.

1. A GOLDEN SNAPSHOT of the derived surface (`tests/data/registry_snapshot.json`)
   -- names, schemas, description hashes, stage membership, CLI names, guards and
   withheld params. Any accidental change to what the model sees fails here and
   has to be acknowledged by updating the snapshot deliberately.

2. A SMOKE TEST that calls every tool with representative arguments through
   `ToolSpec.call`, the exact path the MCP handler uses. This did not exist
   before the registry: there was no way to invoke all 38 tools uniformly, so
   nothing checked that they were all callable at all.

The smoke cases deliberately exercise BOTH bare calls (defaults apply) and calls
with guards set, because the defaults are where the false accusations came from.
"""

import json
import pathlib
from typing import Annotated, get_args, get_origin

import pytest

from metascience_agent import registry as R

SNAPSHOT = pathlib.Path(__file__).parent / "data" / "registry_snapshot.json"

TYPE_NAME = {str: "str", int: "int", float: "float", bool: "bool",
             list: "list", dict: "dict", tuple: "tuple"}


def schema_repr(spec) -> dict[str, str]:
    """The snapshot's rendering of one tool's MCP schema.

    `Param.help` now reaches the model as the JSON-schema `description` of that
    property (via `Annotated[type, help]`), so the HELP TEXT is part of what the
    model sees and has to be pinned like everything else here. It is rendered
    inline -- `"int :: Printed decimals of ..."` -- rather than as a seventh
    snapshot key, so a reviewer reads the exact sentence in the diff and a param
    with no help keeps its old one-word row unchanged.
    """
    out = {}
    for name, ann in spec.schema().items():
        if get_origin(ann) is Annotated:
            base, help_text = get_args(ann)[0], get_args(ann)[1]
            out[name] = f"{TYPE_NAME[base]} :: {help_text}"
        else:
            out[name] = TYPE_NAME[ann]
    return out

# Representative MCP arguments per tool. Where a tool has guards, at least one
# case sets them and one leaves them at their defaults.
CASES: dict[str, list[dict]] = {
    # Needs a sandbox and a paper dir; covered by tests/test_run_script.py.
    "run_python_script": [],
    # A reconciling cascade and a broken step identity.
    "check_flow_arithmetic": [
        {"stages": [
            {"label": "assessed", "n": 240,
             "excluded": [{"reason": "declined", "n": 40}]},
            {"label": "randomized", "n": 200,
             "arms": [{"label": "treatment", "n": 100},
                      {"label": "control", "n": 100}]},
        ]},
        {"stages": [
            {"label": "assessed", "n": 240,
             "excluded": [{"reason": "declined", "n": 12}]},
            {"label": "randomized", "n": 200},
        ], "randomized_label": "randomized"},
    ],
    # All four regimes: in-bounds, the extraction refusal, the verified
    # escalation, and a measure with no logically necessary bound.
    "check_statistic_bounds": [
        {"value": 0.113, "measure": "correlation"},
        {"value": 11.3, "measure": "correlation"},
        {"value": 11.3, "measure": "r", "extraction_verified": True,
         "source_quote": "a correlation coefficient of 11.3"},
        {"value": 500.0, "measure": "widget_index"},
    ],
    "extract_pdf": [],  # needs a real PDF; covered by test_paper_inputs
    # needs a real XML file; covered by test_jats.py and test_jats_corpus.py
    "extract_xml": [],
    # needs a real XML file; covered by test_table_delivery.py
    "get_table": [],
    # needs a real HTML file; covered by test_html.py
    "extract_html": [],
    # needs a real .docx/.xlsx; covered by test_supplements_read.py
    "extract_supplement": [],
    # needs a real .xlsx; covered by test_supplement_windowing.py
    "get_supplement_table": [],
    # The two measured cases plus the by-name refusal.
    "effect_size_from_f": [
        # the measured mismatch: F(2, 54) = 51.81 with eta_p^2 = .83
        {"f_value": 51.81, "df1": 2, "df2": 54, "reported_effect_size": 0.83,
         "decimals_f": 2, "decimals_effect_size": 2},
        # df1 = 1, where the retired F/(F + df2) shortcut happens to agree
        {"f_value": 14.231, "df1": 1, "df2": 30,
         "reported_effect_size": 0.322, "decimals_f": 3,
         "decimals_effect_size": 3},
        # the refusal path: a measure needing a total sum of squares
        {"f_value": 51.81, "df1": 2, "df2": 54, "reported_effect_size": 0.83,
         "measure": "eta_squared"},
    ],
    # One case with the precision supplied and one without, because the
    # decimals gate decides between a verdict and a refusal.
    "recalc_stat_to_p": [
        {"statistic": 2.10, "kind": "t", "df": 28},
        {"statistic": 4.10, "kind": "chi2", "df": 1, "reported_p": 0.04,
         "decimals_stat": 2},
        {"statistic": 180.74, "kind": "chi2"},   # no df, no p: bounded, computes only
        # An exact p printed far ABOVE its statistic (10.1037/a0024422): the
        # under-claim, stated and inferred. tests/test_p_relation.py has more.
        {"statistic": 3.94, "kind": "t", "df": 38, "reported_p": 0.696,
         "decimals_stat": 2, "decimals_p": 3, "p_relation": "="},
        {"statistic": 3.94, "kind": "t", "df": 38, "reported_p": 0.696,
         "decimals_stat": 2, "decimals_p": 3},
        {"statistic": 2.0, "kind": "t", "reported_p": 0.04, "decimals_stat": 2,
         "decimals_p": 2, "df_max": 10.0},       # no df: bounded over [1, 10]
        {"statistic": 4.2, "kind": "f", "df2": 30},   # the refusal path: F, no df1
    ],
    "check_count_percent": [
        {"count": 142, "percentage": 71.0, "n": 200, "decimals": 1},
        {"count": 142, "percentage": 73.0, "n": 200},
    ],
    # `decimals` is now a precision guard with no default, so the bare call is a
    # refusal and every arithmetic case states the printed precision.
    "grim_check": [
        {"mean": 5.51, "n": 30},
        {"mean": 5.51, "n": 30, "decimals": 2, "data_type": "likert",
         "bound_source": "stated"},
        {"mean": 79.05, "n": 30, "decimals": 2, "data_type": "continuous"},
        {"mean": 12.4, "n": 50, "decimals": 1, "data_type": "count"},
    ],
    "grim_percentage": [{"percentage": 69.4, "n": 49}],
    "grim_sweep": [{"values": [69.4], "n_max": 60, "n_min": 40, "decimals": 1}],
    "reconstruct_2x2": [{"pct_col1": 63.7, "pct_col2": 44.9, "n_total": 100}],
    "grimmer_check": [
        {"mean": 4.0, "sd": 1.0, "n": 10},
        {"mean": 48.9, "sd": 14.46, "n": 49, "data_type": "continuous"},
    ],
    "debit_check": [
        {"mean": 0.30, "sd": 0.30, "n": 50},
        {"mean": 0.30, "sd": 0.30, "n": 50, "decimals_mean": 2, "decimals_sd": 2,
         "data_type": "binary"},
        {"mean": 0.5, "sd": 0.5, "n": 30, "decimals_mean": 1, "decimals_sd": 1,
         "data_type": "continuous"},
    ],
    "debit_check_batch": [{"rows": [{"mean": 0.3, "sd": 0.3, "n": 50}]}],
    "recalc_independent_t": [
        {"mean1": 10.0, "sd1": 2.0, "n1": 30, "mean2": 12.0, "sd2": 2.0, "n2": 30,
         "reported_p": 0.05},
        {"mean1": 10.0, "sd1": 2.0, "n1": 30, "mean2": 12.0, "sd2": 2.0, "n2": 30,
         "reported_p": 0.43, "decimals_p": 2, "p_relation": "="},
    ],
    "recalc_within_subjects_t": [
        {"mean_pre": 10.0, "sd_pre": 2.0, "mean_post": 12.0, "sd_post": 2.0,
         "n": 30, "reported_p": 0.01},
    ],
    "recalc_anova": [{"means": [1, 2, 3], "sds": [1, 1, 1], "ns": [10, 10, 10]},
                     {"means": [1, 2, 3], "sds": [1, 1, 1], "ns": [10, 10, 10],
                      "reported_p": 0.4, "decimals_p": 1, "p_relation": "="}],
    "recalc_f_to_p": [{"f_value": 4.82, "df1": 1, "df2": 45},
                      # df2 omitted: the unstated-df2 attainability mode
                      # (the measured Sholl FP shape, now consistent).
                      {"f_value": 6.951, "df1": 3, "reported_p": 0.0001,
                       "decimals_p": 4},
                      {"f_value": 11.38, "df1": 2, "df2": 66, "reported_p": 0.26,
                       "decimals_p": 2, "p_relation": "="}],
    "recalc_chi_squared": [{"observed": [[10, 20], [15, 25]]},
                           {"observed": [[5, 12], [7, 8]], "reported_p": 0.71,
                            "decimals_p": 2, "p_relation": "="}],
    "check_sd_range": [{"sd": 2.0, "min_val": 1, "max_val": 7}],
    "check_summation": [{"values": [50.0, 49.0], "expected_sum": 100.0}],
    # Guards set and left at default, plus the two refusals: a denominator
    # whose own rounding interval spans zero, and a reproducible ratio.
    "check_ratio": [
        {"numerator": 408.0, "denominator": 0.014, "reported_ratio": 18788.0,
         "decimals_numerator": 0, "decimals_denominator": 3,
         "decimals_ratio": 0},
        {"numerator": 408.0, "denominator": 0.015, "reported_ratio": 27200.0,
         "decimals_numerator": 0, "decimals_denominator": 3,
         "decimals_ratio": 0},
        {"numerator": 408.0, "denominator": 0.014, "reported_ratio": 18788.0},
        {"numerator": 5.0, "denominator": 0.02, "reported_ratio": 250.0,
         "decimals_numerator": 1, "decimals_denominator": 1,
         "decimals_ratio": 0},
    ],
    "check_summation_batch": [
        {"rows": [{"values": [50.0, 50.0], "expected_sum": 100.0, "description": "pct"},
                  {"values": [231099.0, 73986.0], "expected_sum": 315661.0,
                   "description": "flow diagram"}]},
        # A batch that can evaluate nothing must return `indeterminate`, never
        # `consistent` -- the same false-clear that had to be fixed in DEBIT,
        # where zero impossible rows out of zero evaluated rows read as a clean
        # bill of health.
        {"rows": []},
    ],
    "check_regression": [
        {"b": 2.0, "se": 0.5, "reported_t": 4.0},
        # A censored p, declared. "P < .001" is the commonest reported p in the
        # archive and reaches the tool as the bare float 0.001; the guard is
        # what separates it from an exact "P = .001".
        {"b": 2.0, "se": 0.5, "df": 40, "reported_p": 0.001,
         "decimals_b": 1, "decimals_se": 1, "decimals_p": 3,
         "p_is_threshold": True},
        {"b": 0.55, "se": 0.13, "df": 200, "reported_p": 0.31,
         "decimals_p": 2, "p_relation": "="},
    ],
    "check_regression_batch": [
        {"rows": [{"b": 2.0, "se": 0.5, "reported_t": 4.0, "df": 40,
                   "label": "Communication"},
                  {"b": 1.34, "se": 0.6, "reported_t": 9.99, "df": 40,
                   "reported_p": 0.001, "decimals_p": 3,
                   "p_is_threshold": True}]},
        # Nothing evaluable must yield `indeterminate`, never `consistent`.
        {"rows": []},
    ],
    "stalt_check": [{"calculated_p": 1e-18, "reported_threshold": "<0.05"}],
    "sprite_reconstruct": [
        {"mean": 4.0, "sd": 1.5, "n": 30},
        {"mean": 128.4, "sd": 15.2, "n": 200, "data_type": "continuous"},
    ],
    "multiplicity_report": [
        # The family from the ajcp.70049 run: a 3x3 design, nine tests, no
        # stated correction.
        {"tests": [{"p_value": p} for p in
                   [0.01, 0.03, 0.07, 0.03, 0.01, 0.03, 0.38, 0.96, 0.89]],
         "family_label": "nine outcomes, 3x3 design"},
        # A family whose tests were all corrected already has nothing left to
        # compute; it must say so rather than report an empty family.
        {"tests": [{"p_value": 0.01, "correction_applied": "Bonferroni"}],
         "family_label": "one test the authors already corrected"},
        # No family_label: a refusal, not a default. The default used to be
        # "all reported tests", which is the pooling the tool's own description
        # tells the model not to do.
        {"tests": [{"p_value": 0.01}, {"p_value": 0.9}]},
        # A threshold-reported p is dropped rather than coerced, and counted.
        {"tests": [{"p_value": 0.05, "p_is_threshold": True},
                   {"p_value": 0.02}],
         "family_label": "two tests, one reported as p < .05"},
    ],
    "csf_test": [
        {"p_values": [0.93, 0.99, 0.99]},
        {"p_values": [0.93, 0.99, 0.99], "design": "matched_pairs"},
        {"p_values": [0.93, 0.99, 0.99], "correlation": 0.3},
    ],
    "check_sd_or_se": [
        {"reported_value": 2.0, "n": 30},
        {"reported_value": 2.0, "n": 30, "variable_range_min": 1, "variable_range_max": 7},
    ],
    "flag_round_n": [{"ns": [100, 200, 300]}],
    "flag_uninformative_stat": [{"means": [1.0, 2.0], "sds": [1.0, 1.0], "ns": [10, 10]}],
    "rivets_independent_t": [
        {"mean1": 10.0, "sd1": 2.0, "n1": 30, "mean2": 12.0, "sd2": 2.0, "n2": 30},
    ],
    "rivets_anova": [{"means": [1, 2, 3], "sds": [1, 1, 1], "ns": [10, 10, 10]}],
    "check_proportion_from_normal": [
        {"reported_proportion": 0.3, "mean": 5.0, "sd": 1.0, "n": 100, "threshold": 4.5},
    ],
    "bayesian_table1_dispersion": [{"rows": [
        {"label": "a", "means": [1, 1.1], "sds": [1, 1], "ns": [20, 20]},
        {"label": "b", "means": [2, 2.1], "sds": [1, 1], "ns": [20, 20]},
        {"label": "c", "means": [3, 3.1], "sds": [1, 1], "ns": [20, 20]},
    ]}],
    # Both guard regimes: the assumption stated (a verdict is available) and
    # left unset (refusal). The published Smeesters SDs, so the smoke case is
    # also a real one. `iterations` is withheld, so these run the full default.
    "check_variance_dispersion": [
        {"sds": [25.09, 24.58, 25.65], "ns": [15, 15, 15],
         "sd_texts": ["25.09", "24.58", "25.65"],
         "homogeneous_variances": True, "design": "parallel_rct"},
        {"sds": [25.09, 24.58, 25.65], "ns": [15, 15, 15],
         "sd_texts": ["25.09", "24.58", "25.65"]},
    ],
    "parse_table": [{"source": "| M | A |\n|---|---|\n| x | 1.0 (0.5) |\n"}],
    "detect_duplication": [{"blocks": [
        {"label": "A", "sample_id": "a", "cells": [{"label": "x", "value": 2.37, "sd": 0.92}]},
        {"label": "B", "sample_id": "b", "cells": [{"label": "y", "value": 2.37, "sd": 0.92}]},
    ]}],
    # Real .xlsx/.csv fixtures live in test_raw_duplication.py; this case
    # exercises the structured file-not-found refusal through the MCP path.
    "detect_raw_duplication": [{"path": "does_not_exist.xlsx"}],
    # Needs a real PDF on disk; behavior is covered by
    # tests/test_image_analysis.py on synthetic PDFs. The missing-file
    # case still exercises the registry/direct-call equivalence.
    "analyze_paper_images": [{"pdf_path": "does_not_exist.pdf"}],
    "detect_tortured_phrases": [{"paper_dir": "does_not_exist"}],
    "grimu_check": [{"n1": 6, "n2": 6, "reported_p": "0.001"}],
    "grimu_coexistence": [{"n1": 6, "n2": 6, "p_values": ["0.171", "0.172"]}],
    "statcheck": [{}],  # no input -> structured error, not an exception
    "parse_cells_typed": [{"cells": [
        {"raw": "142 (71.0)", "row_label": "Male, n (%)"},
        {"raw": "3.5 (1.2)"},
    ]}],
    "parse_cells_as_declared": [
        # The declaration that fits, and the one that is refused. Both are the
        # tool behaving correctly, and the second is the one worth smoke-testing:
        # a refusal must return a structured result, not raise, or it reads
        # downstream as "the table is unreadable".
        {"cells": [{"raw": "5.38 {1.17}"}, {"raw": "4.20 {0.98}"}],
         "declared": "mean_sd:brace"},
        {"cells": [{"raw": "4.2 (150.0)"}], "declared": "n_percent:paren"},
        {"cells": [{"raw": "1 (2)"}], "declared": "mean_sd:curly"},
    ],
    "check_estimate_ci": [
        {"estimate": 1.42, "ci_low": 1.08, "ci_high": 1.87},
        {"estimate": 1.42, "ci_low": 1.08, "ci_high": 1.87, "measure": "HR"},
        {"estimate": 1.37, "ci_low": 0.31, "ci_high": 2.43, "measure": "MD",
         "reported_p": 0.01, "confidence_level": 0.8},
    ],
    "absence_of_evidence": [
        {"ci_low": 0.72, "ci_high": 1.95},
        {"ci_low": 0.72, "ci_high": 1.95, "measure": "OR", "sesoi": 1.25},
    ],
    "verify_power_analysis": [
        {"test_type": "two_sample_t"},
        {"test_type": "two_sample_t", "effect_size": 0.5, "alpha": 0.05,
         "target_power": 0.8, "n_reported": 128},
    ],
    "required_n": [{"test_type": "two_sample_t", "effect_size": 0.5}],
    "paired_d_interval": [
        {"dz": 0.89},                                  # r unknown -> an interval
        {"dz": 0.89, "r": 0.6},                        # r reported -> a point
        {"t": 6.3, "n": 50},                           # dz derived from t and n
        {"t": 6.3},                                    # n missing -> structured refusal
        {"dz": 0.5, "r": 1.0},                         # r out of range -> refusal
    ],
    "check_effect_plausibility": [
        {"d": 0.35, "field": "social_psychology"},
        {"d": 3.5, "field": "psychotherapy"},
        {"d": 2.2},                                    # no field -> declines to judge
        {"mean1": 12.0, "sd1": 2.0, "n1": 20, "mean2": 5.0, "sd2": 2.0, "n2": 20,
         "field": "psychotherapy", "provenance": "measured_raster"},
    ],
    "extract_figures": [],   # needs a real PDF; covered by test_figures.py
    "check_table": [
        {"cells": [{"raw": "5.51 (1.20)", "row_label": "S", "n": 30}],
         "variables": [{"id": "y", "family": "likert_item", "lower_bound": 1,
                        "upper_bound": 7, "confidence": "high"}],
         "bindings": {"S": "y"}},
        {"cells": []},
    ],
    # need a real paper directory; covered by test_grim_harness.py
    "list_tables": [],
    "declare_table": [],
    "r_grim_ground_truth": [],      # needs R; covered by the R validation suite
    "r_sprite_ground_truth": [],    # needs R
}


class TestGoldenSnapshot:
    """What the model sees must not change by accident."""

    def _snapshot(self):
        return json.loads(SNAPSHOT.read_text())

    def test_tool_set_unchanged(self):
        assert {s.name for s in R.SPECS} == set(self._snapshot())

    @pytest.mark.parametrize("spec", R.SPECS, ids=lambda s: s.name)
    def test_schema_unchanged(self, spec):
        expected = self._snapshot()[spec.name]["schema"]
        got = schema_repr(spec)
        assert got == expected, (
            f"{spec.name}'s MCP schema changed. If deliberate, regenerate "
            "tests/data/registry_snapshot.json and say why in the commit."
        )

    @pytest.mark.parametrize("spec", R.SPECS, ids=lambda s: s.name)
    def test_description_unchanged(self, spec):
        import hashlib
        got = hashlib.sha256(spec.description.encode()).hexdigest()[:16]
        assert got == self._snapshot()[spec.name]["desc_sha"], (
            f"{spec.name}'s description changed. Descriptions encode guard guidance "
            "(when a tool REFUSES, which params are mandatory); changing one changes "
            "how the model uses the tool. Regenerate the snapshot deliberately."
        )

    @pytest.mark.parametrize("spec", R.SPECS, ids=lambda s: s.name)
    def test_stages_guards_and_cli_unchanged(self, spec):
        snap = self._snapshot()[spec.name]
        assert sorted(spec.stages) == snap["stages"], f"{spec.name}: stage membership changed"
        assert spec.cli == snap["cli"], f"{spec.name}: CLI name changed"
        assert sorted(spec.guards()) == snap["guards"], f"{spec.name}: guards changed"
        assert sorted(spec.withheld()) == snap["withheld"], f"{spec.name}: withheld changed"


class TestEveryToolRuns:
    """Call all 38 through the exact path the MCP handler uses."""

    @pytest.fixture(autouse=True)
    def _run_in_tmp(self, tmp_path, monkeypatch):
        # The missing-file cases are bare relative names, and the image tools
        # create their default output dir (`<pdf dir>/panels`, `/figures`)
        # before noticing the PDF is absent -- run from the repo root, every
        # suite run left `panels/` and `figures/` there.
        monkeypatch.chdir(tmp_path)

    def test_every_tool_has_smoke_cases_or_a_stated_reason(self):
        missing = [s.name for s in R.SPECS if s.name not in CASES]
        assert not missing, f"no smoke cases declared for {missing}"

    @pytest.mark.parametrize("spec", R.SPECS, ids=lambda s: s.name)
    def test_calls_cleanly(self, spec):
        for args in CASES[spec.name]:
            result = spec.call(dict(args))
            assert isinstance(result, dict), (
                f"{spec.name} returned {type(result).__name__}, not a dict"
            )
            assert result, f"{spec.name} returned an empty result for {args}"

    @pytest.mark.parametrize("spec", R.SPECS, ids=lambda s: s.name)
    def test_results_are_json_serialisable(self, spec):
        """The MCP envelope json.dumps the result; a non-serialisable value
        would fail at the boundary, in a run that already cost money."""
        for args in CASES[spec.name]:
            R.as_mcp_content(spec.call(dict(args)))

    @pytest.mark.parametrize("spec", R.SPECS, ids=lambda s: s.name)
    def test_severity_is_from_the_ladder(self, spec):
        ladder = {"impossible", "highly_suspicious", "suspicious",
                  "indeterminate", "consistent"}
        for args in CASES[spec.name]:
            sev = spec.call(dict(args)).get("severity")
            if sev is not None:
                assert sev in ladder, f"{spec.name} returned severity {sev!r}"


class TestWithholdingIsEnforcedAtCallTime:
    """A withheld parameter must be ignored even if an argument supplies it.

    Declaring it absent from the schema is not enough -- the MCP layer does not
    validate arguments against the schema, so a model that guesses the name
    would otherwise get it through.
    """

    def test_supplying_a_withheld_param_has_no_effect(self):
        spec = R.BY_NAME["sprite_reconstruct"]
        base = spec.call({"mean": 4.0, "sd": 1.5, "n": 30})
        smuggled = spec.call({"mean": 4.0, "sd": 1.5, "n": 30, "max_iterations": 1})
        assert base.get("outcome") == smuggled.get("outcome"), (
            "max_iterations reached the implementation despite being withheld"
        )

    def test_withheld_csf_grid_is_ignored(self):
        spec = R.BY_NAME["csf_test"]
        base = spec.call({"p_values": [0.93, 0.99, 0.99]})
        smuggled = spec.call({"p_values": [0.93, 0.99, 0.99], "rho_grid": (0.0,)})
        assert base["severity"] == smuggled["severity"]
        assert base["sensitivity_profile"] == smuggled["sensitivity_profile"]


class TestMultiplicityRefusesAnUnstatedFamily:
    """A default family label is a judgement the tool made on the caller's behalf.

    It used to default to "all reported tests" -- pooling every test in the
    paper, which is the one thing the tool's own description tells the model not
    to do. The description and the behaviour disagreed, and the behaviour won on
    every call that omitted the argument.
    """

    SPEC = R.BY_NAME["multiplicity_report"]
    FAMILY = [{"p_value": 0.01}, {"p_value": 0.03}, {"p_value": 0.9}]

    @pytest.mark.parametrize("args", [
        {"tests": FAMILY},
        {"tests": FAMILY, "family_label": ""},
        {"tests": FAMILY, "family_label": "   "},
    ])
    def test_a_missing_label_is_refused_not_filled_in(self, args):
        out = self.SPEC.call(dict(args))
        assert out["applicable"] is False
        assert out["severity"] == "indeterminate"
        assert "n_significant_bh" not in out, "arithmetic ran without a stated family"

    def test_a_stated_label_runs(self):
        out = self.SPEC.call({"tests": self.FAMILY, "family_label": "three primary outcomes"})
        assert out["family"] == "three primary outcomes"
        assert out["n_tests"] == 3


class TestEntityEscapedArgumentsAreNotLost:
    """GATE 0b: a value the model read CORRECTLY should not die in transport.

    MEASURED 2026-08-16 across 2,706 archived tool calls: 19 `stalt_check` calls
    failed with `Could not parse threshold: '&lt;0.01'`, and the failure was
    verified STILL LIVE before the fix -- `<0.01` parsed, `&lt;0.01` did not.

    The source is not a model error. In JATS XML `<` is REQUIRED to be encoded
    as `&lt;`, so a threshold read out of publisher XML -- the format this
    pipeline PREFERS because its tables are ground truth -- arrives escaped by
    specification. The better the extraction gets, the more often this fires.

    Found while auditing the other tools for the weakness Greg had just had
    removed from `check_effect_plausibility`. The audit's first two instruments
    were both wrong: "% indeterminate" ranked `absence_of_evidence` worst when
    its indeterminate verdicts ARE its finding, and the type-error sweep that
    followed turned up 132 archived failures that a GATE 0 coercion had already
    fixed months ago (LESSONS #8 -- check whether the code postdates the
    archive). This is what survived both corrections.
    """

    def _stalt(self, threshold):
        spec = next(s for s in R.SPECS if s.name == "stalt_check")
        return spec.call({"calculated_p": 0.004, "reported_threshold": threshold})

    def test_the_escaped_form_now_parses(self):
        assert self._stalt("&lt;0.01").get("error") is None

    def test_the_numeric_entity_form_parses(self):
        assert self._stalt("&#60;0.01").get("error") is None

    def test_it_agrees_with_the_unescaped_form(self):
        """The whole point: transport must not change the verdict."""
        assert self._stalt("&lt;0.01")["severity"] == self._stalt("<0.01")["severity"]

    def test_an_ordinary_string_is_untouched(self):
        """Only strings that actually contain an entity are decoded, so a
        normal value passes through byte-identical."""
        from metascience_agent.registry import _unescape_entity_args
        spec = next(s for s in R.SPECS if s.name == "stalt_check")
        args = {"reported_threshold": "p < 0.05", "source_quote": "a & b", "calculated_p": 0.01}
        assert _unescape_entity_args(spec, args) == args

    def test_a_quote_carrying_an_entity_is_decoded(self):
        """`quotes.py` already unescapes the haystack before matching, so
        decoding here closes the third gap rather than opening an inconsistency."""
        from metascience_agent.registry import _unescape_entity_args
        spec = next(s for s in R.SPECS if s.name == "stalt_check")
        out = _unescape_entity_args(spec, {"source_quote": "reported as p &lt; .01"})
        assert out["source_quote"] == "reported as p < .01"
