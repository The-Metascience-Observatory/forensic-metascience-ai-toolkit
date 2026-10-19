"""Tests for the duplication / copy-paste detector."""

from metascience_agent.tools.duplication import detect_duplication
from metascience_agent.tools.tableparse import parse_table

# Four identical (mean, SD) affect pairs appearing in two tables that a paper
# presents as separate studies with different participants.
#
# Deliberately unattributed. What this pins is the DETECTOR's behaviour on a
# k=4 cross-source match — that is a property of the arithmetic, not of any
# particular paper, and naming a paper here would attach a permanent accusation
# to a source file for no test-value whatsoever.
DUPLICATED_AFFECT = [(2.37, 0.92), (3.06, 0.97), (1.73, 0.82), (1.25, 0.37)]


def _cells(pairs, prefix="c"):
    return [{"label": f"{prefix}{i}", "value": v, "sd": s}
            for i, (v, s) in enumerate(pairs)]


class TestCrossSourceDuplication:
    def test_four_pair_cross_source_match_regression_pin(self):
        """Four identical pairs across independent samples: highly_suspicious."""
        r = detect_duplication([
            {"label": "Table S1", "sample_id": "study1a", "independent": True,
             "cells": _cells(DUPLICATED_AFFECT) + [{"label": "clar", "value": 5.38, "sd": 1.17}]},
            {"label": "Table S2", "sample_id": "study1b", "independent": True,
             "cells": _cells(DUPLICATED_AFFECT) + [{"label": "clar", "value": 5.58, "sd": 1.19}]},
        ])
        assert r["severity"] == "highly_suspicious"
        assert r["max_identical_pairs"] == 4
        assert r["chance_probability"] < 1e-6
        grp = next(g for g in r["duplicate_groups"] if g["kind"] == "cross_source_pair")
        assert grp["k_pairs"] == 4 and grp["same_sample_caveat"] is False

    def test_single_unusual_match_is_suspicious_at_most(self):
        r = detect_duplication([
            {"label": "A", "sample_id": "a", "cells": [{"label": "x", "value": 2.37, "sd": 0.92}]},
            {"label": "B", "sample_id": "b", "cells": [{"label": "y", "value": 2.37, "sd": 0.92}]},
        ])
        assert r["severity"] == "suspicious"
        assert r["max_identical_pairs"] == 1

    def test_single_round_match_is_consistent(self):
        """WAS `indeterminate`; now `consistent`, and this test's own data is why.

        The matched cell is labelled `sex`, value 0.50, SD 0.50 -- and
        sqrt(0.5 x 0.5) is exactly 0.50, so it is a BINARY variable's proportion
        beside its own deterministic SD. The pair carries one number, not two,
        and the "match" reduces to "both samples are about half male", which is
        the least surprising observation available.

        Under the old rule it earned only the round-value discount (one tier).
        It now also earns the Bernoulli discount, and `consistent` is the more
        accurate answer: not merely uninformative, but EXPECTED. Changed
        2026-08-12 with the fix for the verified false accusation on
        10.1001/jamanetworkopen.2023.51752.
        """
        r = detect_duplication([
            {"label": "A", "sample_id": "a", "cells": [{"label": "sex", "value": 0.50, "sd": 0.50},
                                                        {"label": "x", "value": 1.23, "sd": 0.44}]},
            {"label": "B", "sample_id": "b", "cells": [{"label": "sex", "value": 0.50, "sd": 0.50},
                                                        {"label": "y", "value": 2.71, "sd": 0.88}]},
        ])
        assert r["severity"] == "consistent"
        grp = next(g for g in r["duplicate_groups"] if g["kind"] == "cross_source_pair")
        assert grp["is_round_value"] is True
        assert grp["is_bernoulli_pair"] is True

    def test_same_sample_guard(self):
        """Identical pairs across blocks sharing a sample_id are expected."""
        r = detect_duplication([
            {"label": "Total", "sample_id": "S", "cells": _cells(DUPLICATED_AFFECT)},
            {"label": "Subgroup", "sample_id": "S", "cells": _cells(DUPLICATED_AFFECT)},
        ])
        assert r["max_identical_pairs"] == 0  # no independent overlap counted
        grp = next(g for g in r["duplicate_groups"] if g["kind"] == "cross_source_pair")
        assert grp["same_sample_caveat"] is True
        assert grp["severity"] in ("indeterminate", "consistent")

    def test_no_duplication_is_consistent(self):
        r = detect_duplication([
            {"label": "A", "sample_id": "a", "cells": [{"label": "x", "value": 2.37, "sd": 0.92}]},
            {"label": "B", "sample_id": "b", "cells": [{"label": "y", "value": 4.11, "sd": 0.55}]},
        ])
        assert r["severity"] == "consistent"
        assert r["max_identical_pairs"] == 0

    def test_severity_ladder_on_pair_count(self):
        two = [(2.37, 0.92), (3.06, 0.97)]
        r2 = detect_duplication([
            {"label": "A", "sample_id": "a", "cells": _cells(two)},
            {"label": "B", "sample_id": "b", "cells": _cells(two)},
        ])
        assert r2["severity"] == "suspicious" and r2["max_identical_pairs"] == 2


class TestWithinTableDuplication:
    def test_duplicated_row_flagged(self):
        md = (
            "| M | c1 | c2 | c3 |\n|---|---|---|---|\n"
            "| rowA | 5.10 (1.2) | 4.30 (0.9) | 6.00 (1.1) |\n"
            "| rowB | 5.10 (1.2) | 4.30 (0.9) | 6.00 (1.1) |\n"
            "| rowC | 2.20 (0.5) | 3.30 (0.7) | 4.40 (0.8) |\n"
        )
        t = parse_table(md, source_label="T")
        r = detect_duplication([{"label": "T", "sample_id": "t", "cells": t["cells"]}])
        wt = [g for g in r["duplicate_groups"] if g["kind"] == "within_table_row"]
        assert wt and set(wt[0]["labels"]) == {"rowA", "rowB"}
        assert wt[0]["n_identical_cells"] == 3
        assert r["severity"] == "highly_suspicious"


class TestNearMatch:
    def test_digit_transposition(self):
        r = detect_duplication([
            {"label": "A", "sample_id": "a", "cells": [{"label": "x", "value": 2.37, "sd": 0.5}]},
            {"label": "B", "sample_id": "b", "cells": [{"label": "y", "value": 2.73, "sd": 0.9}]},
        ])
        nm = [g for g in r["duplicate_groups"] if g["kind"] == "near_match"]
        assert nm and nm[0]["relation"] == "digit_transposition"

    def test_near_match_can_be_disabled(self):
        r = detect_duplication([
            {"label": "A", "sample_id": "a", "cells": [{"label": "x", "value": 2.37, "sd": 0.5}]},
            {"label": "B", "sample_id": "b", "cells": [{"label": "y", "value": 2.73, "sd": 0.9}]},
        ], near_match=False)
        assert not any(g["kind"] == "near_match" for g in r["duplicate_groups"])


class TestEdgeCases:
    def test_empty_blocks(self):
        assert "error" in detect_duplication([])

    def test_end_to_end_from_parse_table(self):
        """parse_table cells feed straight into detect_duplication."""
        s1 = "| M | Un | Et |\n|---|---|---|\n| PosAff | 2.37 (0.92) | 3.06 (0.97) |\n| NegAff | 1.73 (0.82) | 1.25 (0.37) |\n"
        s2 = "| M | Un | Et |\n|---|---|---|\n| PosAff | 2.37 (0.92) | 3.06 (0.97) |\n| NegAff | 1.73 (0.82) | 1.25 (0.37) |\n"
        t1 = parse_table(s1, source_label="Table S1")
        t2 = parse_table(s2, source_label="Table S2")
        r = detect_duplication([
            {"label": "Table S1", "sample_id": "1a", "cells": t1["cells"]},
            {"label": "Table S2", "sample_id": "1b", "cells": t2["cells"]},
        ])
        assert r["severity"] == "highly_suspicious"
        assert r["max_identical_pairs"] == 4


class TestWithinTableDesignedRepeats:
    """The within-table branch applied NONE of the de-escalations the
    cross-source branch has always had (same-sample drop, round-value drop).

    Measured on the code before the fix: a stratified randomised Table 1
    whose three arms share n=20/20/20, 10/10/10 males and a 1-dp baseline
    age of 45.2 (5.1) -- the counts identical BY DESIGN under blocked,
    sex-stratified allocation, the age a single coarse-precision coincidence
    -- scored top-level `highly_suspicious`, the same tier as the k=4
    duplicated-affect copy-paste pin. Zero-attrition count rows ("Randomised
    n" and "Analysed n" both reading 20/20/20) also scored highly_suspicious.

    The fix: count cells (integer value, no SD or SD exactly 0) never count
    toward the ladder, which runs on the matched cells that actually carry a
    statistic; and a COLUMN match whose statistics are all round values drops
    one tier, mirroring the cross-source `all_round` discount (columns of one
    table are arms drawn from the same recruitment, where near-equality is
    expected under randomisation). ROW matches keep full severity: different
    variables sharing a whole line of means AND SDs is the fill-down
    signature, so `test_duplicated_row_flagged` above must keep passing.
    """

    def _one_table(self, md):
        t = parse_table(md, source_label="Table 1")
        return detect_duplication(
            [{"label": "Table 1", "sample_id": "trial", "cells": t["cells"]}])

    def test_randomised_arms_sharing_counts_and_a_round_baseline_are_not_accused(self):
        r = self._one_table(
            "| | Arm A | Arm B | Arm C |\n|---|---|---|---|\n"
            "| Randomised n | 20 | 20 | 20 |\n"
            "| Male n | 10 | 10 | 10 |\n"
            "| Age | 45.2 (5.1) | 45.2 (5.1) | 45.2 (5.1) |\n"
        )
        grp = next(g for g in r["duplicate_groups"]
                   if g["kind"] == "within_table_col")
        assert grp["n_statistic_cells"] == 1  # only the age carries evidence
        assert grp["severity"] == "indeterminate"
        assert r["severity"] == "indeterminate"

    def test_zero_attrition_count_rows_repeat_legitimately(self):
        r = self._one_table(
            "| | Arm A | Arm B | Arm C |\n|---|---|---|---|\n"
            "| Randomised n | 20 | 20 | 20 |\n"
            "| Analysed n | 20 | 20 | 20 |\n"
            "| Age | 45.2 (5.1) | 44.8 (5.3) | 45.9 (4.7) |\n"
        )
        grp = next(g for g in r["duplicate_groups"]
                   if g["kind"] == "within_table_row")
        assert grp["n_statistic_cells"] == 0
        assert grp["severity"] == "indeterminate"
        assert r["severity"] == "indeterminate"

    def test_zero_event_adverse_event_rows_repeat_legitimately(self):
        """'0 (0)' lines -- integer value, SD exactly zero -- are count cells."""
        r = self._one_table(
            "| | Arm A | Arm B | Arm C |\n|---|---|---|---|\n"
            "| Nausea | 0 (0) | 0 (0) | 0 (0) |\n"
            "| Headache | 0 (0) | 0 (0) | 0 (0) |\n"
        )
        assert all(g["severity"] == "indeterminate"
                   for g in r["duplicate_groups"])
        assert r["severity"] == "indeterminate"

    def test_two_round_baselines_matching_across_arms_drop_one_tier(self):
        r = self._one_table(
            "| | Arm A | Arm B |\n|---|---|---|\n"
            "| n | 20 | 20 |\n"
            "| Age | 45.2 (5.1) | 45.2 (5.1) |\n"
            "| BMI | 24.1 (2.0) | 24.1 (2.0) |\n"
        )
        grp = next(g for g in r["duplicate_groups"]
                   if g["kind"] == "within_table_col")
        assert grp["severity"] == "indeterminate"  # suspicious, less one tier
        assert grp["is_round_value"] is True

    def test_copied_high_precision_arm_column_is_still_highly_suspicious(self):
        """Three 2-dp (mean, SD) pairs identical across two arms cannot be
        explained by randomisation balance at reporting precision -- the
        copied-column signature keeps its full severity."""
        r = self._one_table(
            "| | Arm A | Arm B | Arm C |\n|---|---|---|---|\n"
            "| Age | 45.23 (5.17) | 45.23 (5.17) | 41.02 (6.33) |\n"
            "| BMI | 24.13 (2.04) | 24.13 (2.04) | 25.48 (2.16) |\n"
            "| HDL | 1.37 (0.29) | 1.37 (0.29) | 1.22 (0.31) |\n"
        )
        grp = next(g for g in r["duplicate_groups"]
                   if g["kind"] == "within_table_col")
        assert grp["severity"] == "highly_suspicious"
        assert r["severity"] == "highly_suspicious"

    def test_round_fill_down_row_keeps_full_severity(self):
        """The row direction gets NO round discount: two different variables
        sharing a whole line of 1-dp means AND SDs is six coinciding numbers
        with no design reason to coincide."""
        r = self._one_table(
            "| M | c1 | c2 | c3 |\n|---|---|---|---|\n"
            "| rowA | 5.1 (1.2) | 4.3 (0.9) | 6.0 (1.1) |\n"
            "| rowB | 5.1 (1.2) | 4.3 (0.9) | 6.0 (1.1) |\n"
        )
        grp = next(g for g in r["duplicate_groups"]
                   if g["kind"] == "within_table_row")
        assert grp["severity"] == "highly_suspicious"


class TestLoneMatchChanceGate:
    """`_severity_for_k` sent any lone high-precision cross-source match
    straight to `suspicious` while the span-aware, multiplicity-corrected
    chance probability the SAME RESULT reports was never consulted.

    Measured on the code before the fix: two independent 10- and 11-item
    tables of clustered 2-dp statistics (means spanning 0.40, SDs 0.06)
    share exactly one non-round (mean, SD) pair -> chance_probability 0.368
    and severity `suspicious` -- an accusation issued alongside the tool's
    own statement that over a third of innocent papers with these tables
    would show such a match.

    The gate, on P(>=1 chance match) = 1 - exp(-lam) over ALL comparisons
    made: > 0.5 -> consistent (a match is the EXPECTED outcome under
    innocence); > 0.10 -> indeterminate (too likely by chance to accuse);
    <= 0.10 -> the existing `suspicious` stands. It runs only when both
    observed spans cover at least five rounding steps: spans are estimated
    from the observed values themselves, so two single-cell blocks that
    match have ZERO span, p_pair saturates at 1, chance reads 0.63, and an
    ungated model would launder the strongest possible lone match to
    `consistent` (`test_single_unusual_match_is_suspicious_at_most` above
    pins that degenerate case at `suspicious`).
    """

    @staticmethod
    def _items(means, sds, label, sample):
        return {"label": label, "sample_id": sample,
                "cells": [{"label": f"{sample}_i{i}", "value": v, "sd": s}
                          for i, (v, s) in enumerate(zip(means, sds))]}

    def test_lone_match_likely_by_chance_is_indeterminate(self):
        a = self._items(
            [2.21, 2.23, 2.24, 2.26, 2.28, 2.29, 2.31, 2.33, 2.34, 2.37],
            [0.81, 0.83, 0.86, 0.87, 0.82, 0.84, 0.86, 0.83, 0.87, 0.84],
            "Study 1 items", "s1")
        b = self._items(
            [2.41, 2.42, 2.44, 2.46, 2.47, 2.49, 2.51, 2.52, 2.53, 2.61, 2.37],
            [0.82, 0.86, 0.81, 0.84, 0.87, 0.83, 0.86, 0.82, 0.84, 0.87, 0.84],
            "Study 2 items", "s2")
        r = detect_duplication([a, b])
        assert r["max_identical_pairs"] == 1
        assert 0.10 < r["chance_probability"] < 0.5
        grp = next(g for g in r["duplicate_groups"]
                   if g["kind"] == "cross_source_pair")
        assert grp["severity"] == "indeterminate"
        assert grp["chance_gated"] is True
        assert r["severity"] == "indeterminate"

    def test_lone_match_more_likely_than_not_by_chance_is_consistent(self):
        a = self._items(
            [2.21, 2.22, 2.23, 2.24, 2.26, 2.27, 2.28, 2.29, 2.31, 2.32,
             2.33, 2.34, 2.37],
            [0.81, 0.83, 0.86, 0.84, 0.82, 0.85, 0.86, 0.83, 0.81, 0.84,
             0.86, 0.82, 0.84],
            "Study 1 items", "s1")
        b = self._items(
            [2.41, 2.42, 2.43, 2.44, 2.46, 2.47, 2.48, 2.49, 2.51, 2.52,
             2.53, 2.54, 2.61, 2.37],
            [0.82, 0.86, 0.81, 0.84, 0.85, 0.83, 0.86, 0.82, 0.84, 0.85,
             0.81, 0.83, 0.86, 0.84],
            "Study 2 items", "s2")
        r = detect_duplication([a, b], near_match=False)
        assert r["chance_probability"] > 0.5
        grp = next(g for g in r["duplicate_groups"]
                   if g["kind"] == "cross_source_pair")
        assert grp["severity"] == "consistent"
        assert r["severity"] == "consistent"

    def test_lone_improbable_match_stays_suspicious(self):
        """Wide spans, few comparisons: a lone 2-dp (mean, SD) coincidence at
        P ~ 5e-5 is real evidence and keeps its severity."""
        a = self._items([1.24, 4.56, 8.93], [0.31, 1.27, 2.44], "T2", "g1")
        b = self._items([2.18, 4.56, 7.77], [0.52, 1.27, 1.88], "T5", "g2")
        r = detect_duplication([a, b])
        assert r["max_identical_pairs"] == 1
        assert r["chance_probability"] < 0.10
        assert r["severity"] == "suspicious"


class TestAnExplicitNonePrecisionDoesNotKillTheCall:
    """`dict.get(k, default)` returns the default only when the key is ABSENT.

    A typed cell carrying `decimals_sd: None` -- what `parse_cell` emits when a
    cell's second number has no determinable printed precision -- came back
    None and crashed the whole call on `int(None)`. A crash here is the worst
    class of failure this codebase has: `detect_duplication` runs late, after
    both stages are billed, so the run dies having already been paid for and
    the report is never written.

    Found by the full suite after a parse-layer change started emitting the key
    explicitly; the two modules were each correct in isolation.
    """

    def _blocks(self, **overrides):
        cell = {"label": "Age", "value": 48.9, "sd": 7.1}
        cell.update(overrides)
        return [{"label": "T1", "cells": [cell]},
                {"label": "T2", "cells": [dict(cell, value=52.3, sd=8.4)]}]

    def test_a_none_decimals_sd_is_survived(self):
        out = detect_duplication(self._blocks(decimals_sd=None))
        assert out.get("severity") is not None

    def test_a_none_decimals_mean_is_survived(self):
        out = detect_duplication(self._blocks(decimals_mean=None))
        assert out.get("severity") is not None

    def test_both_none_falls_back_to_the_call_level_precision(self):
        """The fallback must be the caller's declared precision, not a guess:
        these cells are printed to one decimal and the call says so."""
        out = detect_duplication(
            self._blocks(decimals_mean=None, decimals_sd=None),
            decimals_mean=1, decimals_sd=1)
        assert out.get("severity") is not None

    def test_an_absent_key_still_works(self):
        """The behaviour that was already correct, pinned so the fix for the
        None case cannot break the missing case."""
        out = detect_duplication(self._blocks())
        assert out.get("severity") is not None


class TestALowEntropyColumnIsNotSixCoincidences:
    """MEASURED 2026-08-22, `10.1002--alz.13600` on the harness prepass sweep.

    `run_meta.exhaustive_checks` recorded `highly_suspicious` with "6 identical
    (mean, SD) pair(s) shared across independent blocks (coincidence
    probability ~ 2e-39)". The six pairs were (-0.01,0.01) (0.00,0.01)
    (0.01,0.01) (0.02,0.01) (0.03,0.01) (0.05,0.01) -- regression coefficients
    beside their standard errors, from Table 3 and from Supplementary Table 5,
    which is the same models re-fitted by sex.

    There is no coincidence to price. TEN of Table 3's twenty beta-plus-minus-SE
    cells have SE exactly 0.01, and Supplementary Table 5 looks the same, so a
    tie on the beta forces a tie on the pair. The span model priced 0.01 as if
    any value in [0.01, 0.12] were equally likely.

    This is the documented Bernoulli defect one level up: `_is_bernoulli_pair`
    handles an SD that is arithmetic in its mean, and this handles the general
    case of a concentrated column.

    Values below are the real cells, read from the paper's XML and the DOCX
    supplement.
    """

    _T3 = ["0.02 0.01", "0.08 0.01", "-0.06 0.04", "-0.66 0.08", "0.02 0.01",
           "0.05 0.01", "-0.06 0.04", "-0.45 0.08", "0.00 0.01", "0.03 0.01",
           "-0.04 0.03", "-0.26 0.06", "-0.01 0.01", "0.03 0.01", "0.01 0.03",
           "-0.23 0.06", "0.02 0.01", "-0.12 0.03", "0.01 0.01", "-0.08 0.04"]
    _S5 = ["0.03 0.01", "0.08 0.02", "-0.14 0.04", "-0.63 0.12", "0.01 0.01",
           "0.09 0.02", "0.02 0.06", "-0.71 0.11", "0.00 0.01", "0.02 0.01",
           "-0.06 0.05", "-0.18 0.08", "-0.01 0.01", "0.05 0.01", "0.00 0.043",
           "-0.37 0.08", "0.02 0.01", "-0.17 0.05", "0.01 0.01", "-0.06 0.05"]

    @staticmethod
    def _block(label, raws):
        cells = []
        for i, raw in enumerate(raws):
            m, sd = raw.split()
            cells.append({"label": f"{label} row {i}",
                          "value": float(m), "sd": float(sd)})
        return {"label": label, "cells": cells}

    def _run(self):
        return detect_duplication([self._block("TABLE 3", self._T3),
                                   self._block("supplement Table 5", self._S5)])

    def test_the_real_cells_are_not_an_accusation(self):
        r = self._run()
        assert r["max_identical_pairs"] == 6, "the six collisions are real"
        assert r["severity"] in ("consistent", "indeterminate"), r["severity"]

    def test_the_published_probability_is_no_longer_absurd(self):
        r = self._run()
        assert r["chance_probability"] > 0.5, (
            "half the SEs in both tables are 0.01; six matches on that grid "
            "are expected, not one-in-a-million")

    def test_the_group_records_that_it_was_gated(self):
        """An audit trail, not a silent reclassification."""
        groups = [g for g in self._run()["duplicate_groups"]
                  if g.get("kind") == "cross_source_pair"]
        assert groups and all(g.get("chance_gated") for g in groups)


class TestTheChanceGateOnlyEverClears:
    """The gate now runs at every k, so it must be provably one-directional.

    A gate that could RAISE a severity would be manufacturing an accusation
    out of its own chance model, which is worse than the false positive it
    was written to remove.
    """

    def test_drop_to_never_escalates(self):
        from metascience_agent.tools.duplication import _TIERS, _drop_to
        for cur in _TIERS:
            for target in _TIERS:
                out = _drop_to(cur, target)
                assert _TIERS.index(out) >= _TIERS.index(cur), (cur, target, out)

    def test_an_unknown_tier_is_left_alone(self):
        from metascience_agent.tools.duplication import _drop_to
        assert _drop_to("impossible", "consistent") == "impossible"
