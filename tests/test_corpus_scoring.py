"""The scorer is committed before the run, so the scorer needs its own ground truth.

A bug here is indistinguishable from a result. Every assertion below is against
counts computed by hand or against the real manifest's structure, so if the
corpus changes underneath the pre-registration the suite says so instead of
silently scoring a different study.
"""
from __future__ import annotations

import json
import math

import pytest

from forensic_metascience_ai_toolkit.evaluation.corpus import (
    ACCUSATORY,
    ACCUSATORY_SECONDARY,
    FIRE,
    NULL,
    UNDETERMINED,
    VETOED,
    accuses,
    case_of,
    cell_states,
    clopper_pearson_lower,
    clopper_pearson_upper,
    cluster_bootstrap_ci,
    format_report,
    load_cells,
    load_manifest,
    score,
    verdict,
)
from forensic_metascience_ai_toolkit.evaluation.harness import repo_root

ALL8 = "grim,grimmer,sprite,debit,statcheck,baseline_similarity,digit_preference,duplication"


def row(doi, label, expected, can=ALL8, cannot="", notes=""):
    return {
        "doi": doi, "label": label, "notes": notes,
        "expected_statistical_signature": expected,
        "can_validate_tools": can, "cannot_validate_tools": cannot,
    }


def cell(doi, tool, severity="consistent", evaluated=True):
    return {"doi": doi, "tool": tool, "evaluated": evaluated,
            "max_severity": severity, "n_findings": 1 if severity != "consistent" else 0}


class TestStateAssignment:
    def test_hand_counted_toy_manifest(self):
        rows = [
            # fraud, GRIM+SPRITE expected -> 2 FIRE, 6 UNDETERMINED
            row("10.1/a", "fraud", "grim|sprite", notes="[CaseA] x"),
            # control -> 8 NULL
            row("10.1/b", "control", "none"),
            # fraud with a documented null expectation -> 8 NULL (canary)
            row("10.1/c", "fraud", "none", notes="[CaseC] x"),
            # fraud, GRIM expected but no text at all -> 8 VETOED
            row("10.1/d", "fraud", "grim", cannot=ALL8, notes="[CaseD] x"),
        ]
        counts = {}
        for c in cell_states(rows):
            counts[c.state] = counts.get(c.state, 0) + 1
        assert counts == {FIRE: 2, UNDETERMINED: 6, NULL: 16, VETOED: 8}

    def test_veto_beats_expectation(self):
        """A tool with no text to read cannot be scored even if a signature is claimed."""
        states = cell_states([row("10.1/d", "fraud", "grim", cannot="grim", notes="[D] x")])
        assert {c.state for c in states if c.tool == "grim"} == {VETOED}

    def test_unknown_tool_is_rejected_not_ignored(self):
        with pytest.raises(ValueError, match="unknown tool"):
            cell_states([row("10.1/x", "control", "none", can="grim,teleology")])

    def test_none_plus_a_signature_is_a_contradiction(self):
        """`none` is a positive claim about the paper, not an empty field."""
        bad = row("10.1/x", "fraud", "none", notes="[X] y")
        bad["expected_statistical_signature"] = "none,grim"
        with pytest.raises(ValueError, match="both 'none'"):
            cell_states([bad])

    def test_case_clusters_on_the_bracketed_prefix(self):
        assert case_of({"notes": "[Sato (Kurume finding; Bolland)] ...", "doi": "d"}) == "Sato"
        assert case_of({"notes": "", "doi": "10.1/z"}) == "doi:10.1/z"


class TestTheRealManifestStillMatchesThePreregistration:
    """If these fail, the corpus changed and PREREGISTRATION.md must be revised.

    That is the point: the pre-registered cell counts are a claim about a
    specific corpus, and a silent change to the manifest would otherwise let a
    different study be reported under the same protocol.
    """

    @pytest.fixture(scope="class")
    def rows(self):
        return load_manifest(repo_root() / "eval" / "ground_truth" / "manifest.csv")

    def test_cell_counts(self, rows):
        counts = {}
        for c in cell_states(rows):
            counts[c.state] = counts.get(c.state, 0) + 1
        assert counts == {FIRE: 60, NULL: 408, UNDETERMINED: 146, VETOED: 10}

    def test_sixteen_fraud_cases_not_thirty_papers(self, rows):
        cases = {case_of(r) for r in rows if r["label"] == "fraud"}
        assert len(cases) == 16
        assert sum(1 for r in rows if r["label"] == "fraud") == 30

    def test_debit_has_no_positive_control_at_all(self, rows):
        """Recorded in the pre-registration; asserted here so it cannot be forgotten."""
        fire = [c for c in cell_states(rows) if c.state == FIRE and c.tool == "debit"]
        assert fire == []

    def test_baseline_similarity_survives_the_circularity_exclusion_only_once(self, rows):
        fire = [c for c in cell_states(rows)
                if c.state == FIRE and c.tool == "baseline_similarity"]
        assert len(fire) == 1, "the Sato cluster is circular for this tool and must stay excluded"

    def test_three_fraud_papers_expect_a_clean_report(self, rows):
        canaries = [r for r in rows if r["label"] == "fraud"
                    and r["expected_statistical_signature"].strip() == "none"]
        assert len(canaries) == 3


class TestAccusationRule:
    def test_threshold_is_the_pre_registered_pair(self):
        assert accuses(cell("d", "grim", "impossible"))
        assert accuses(cell("d", "grim", "highly_suspicious"))
        assert not accuses(cell("d", "grim", "suspicious"))
        assert not accuses(cell("d", "grim", "indeterminate"))
        assert not accuses(cell("d", "grim", "consistent"))

    def test_secondary_threshold_adds_only_suspicious(self):
        assert accuses(cell("d", "grim", "suspicious"), ACCUSATORY_SECONDARY)
        assert not accuses(cell("d", "grim", "indeterminate"), ACCUSATORY_SECONDARY)

    def test_a_tool_that_never_ran_accuses_nobody(self):
        """Absence is coverage, not a false positive and not a clean pass."""
        assert not accuses(None)
        assert not accuses(cell("d", "grim", "impossible", evaluated=False))


class TestIntervalsBehaveHonestlyAtZero:
    def test_zero_of_48_is_not_certainty(self):
        ub = clopper_pearson_upper(0, 48)
        assert 0.05 < ub < 0.07, ub

    def test_smaller_n_gives_a_worse_bound(self):
        assert clopper_pearson_upper(0, 14) > clopper_pearson_upper(0, 48)

    def test_a_perfect_score_is_not_certainty_either(self):
        """14 of 14 cases establishes ">80%", not "100%". Same error, other direction."""
        lo = clopper_pearson_lower(14, 14)
        assert 0.79 < lo < 0.82, lo

    def test_perfect_sensitivity_prints_a_lower_bound_not_a_hundred(self):
        rows = [row("10.1/f", "fraud", "grim|sprite", notes="[CaseA] x")]
        cells = {("10.1/f", t): cell("10.1/f", t, "impossible") for t in ("grim", "sprite")}
        res = score(rows, cells)
        assert res["E2"].rate == 1.0
        assert res["E2"].lower_bound is not None and res["E2"].lower_bound < 1.0
        e2_line = next(ln for ln in format_report(res).splitlines() if "E2 sensitivity" in ln)
        assert "100%]" in e2_line and "Clopper-Pearson" in e2_line

    def test_bootstrap_resamples_cases_not_cells(self):
        """Eight papers from one misconduct case are one fact, not eight.

        Cell-level resampling of this input would give a tight interval around
        8/9; case-level resampling must be able to draw the all-miss case twice
        and reach zero.
        """
        units = [("Sato", True)] * 8 + [("Reuben", False)]
        lo, hi = cluster_bootstrap_ci(units, n_boot=2000)
        assert lo == 0.0, (lo, hi)
        assert hi == 1.0, (lo, hi)

    def test_single_cluster_refuses_to_invent_an_interval(self):
        lo, hi = cluster_bootstrap_ci([("Sato", True)] * 8)
        assert math.isnan(lo) and math.isnan(hi)


class TestEndpointsAndVerdict:
    def _corpus(self):
        return [
            row("10.1/fr1", "fraud", "grim|sprite", notes="[CaseA] x"),
            row("10.1/fr2", "fraud", "grim", notes="[CaseA] x"),      # same case
            row("10.1/can", "fraud", "none", notes="[Canary] x"),
            row("10.1/ct1", "control", "none"),
            row("10.1/ct2", "control", "none"),
        ]

    def test_undetermined_never_enters_either_headline(self):
        """A fraud paper's unsignatured tools are unknown, and must stay unknown."""
        rows = self._corpus()
        # Accuse on every UNDETERMINED cell and nothing else.
        cells = {}
        for c in cell_states(rows):
            if c.state == UNDETERMINED:
                cells[(c.doi, c.tool)] = cell(c.doi, c.tool, "impossible")
        res = score(rows, cells)
        assert res["E1"].k == 0, "undetermined leaked into the false-accusation rate"
        assert res["E2"].k == 0, "undetermined leaked into sensitivity"
        assert res["E5"].k == res["E5"].n > 0
        assert not res["E3_canary_hits"]

    def test_too_few_clusters_cannot_certify_deployability(self):
        """A clean sweep over three clusters is not evidence of a low error rate.

        The toy corpus below produces zero accusations and still fails, because
        the upper bound over three clusters is ~63%. This is the property that
        stops a small clean run from being quoted as a pass.
        """
        rows = self._corpus()
        cells = {(c.doi, c.tool): cell(c.doi, c.tool, "consistent") for c in cell_states(rows)}
        res = score(rows, cells)
        assert res["E1"].k == 0
        assert any("NOT DEPLOYABLE" in v for v in verdict(res))

    def test_the_real_corpus_has_enough_clusters_for_the_ceiling_to_be_reachable(self):
        """The 20% ceiling must be a test the study can pass, not a guaranteed fail."""
        rows = load_manifest(repo_root() / "eval" / "ground_truth" / "manifest.csv")
        cells = {(c.doi, c.tool): cell(c.doi, c.tool, "consistent") for c in cell_states(rows)}
        res = score(rows, cells)
        assert res["E1"].upper_bound < 0.20, res["E1"].upper_bound

    def test_canary_hit_is_reported_and_fails_the_run(self):
        rows = self._corpus()
        cells = {("10.1/can", "grim"): cell("10.1/can", "grim", "impossible")}
        res = score(rows, cells)
        assert len(res["E3_canary_hits"]) == 1
        assert res["E3_canary_hits"][0]["doi"] == "10.1/can"
        assert any("EXTRACTION UNFIT" in v for v in verdict(res))

    def test_false_accusation_ceiling_trips(self):
        rows = self._corpus()
        cells = {(c.doi, c.tool): cell(c.doi, c.tool, "impossible")
                 for c in cell_states(rows) if c.state == NULL}
        res = score(rows, cells)
        assert res["E1"].rate == 1.0
        assert any("NOT DEPLOYABLE" in v for v in verdict(res))

    def test_a_clean_sweep_still_reports_a_bound_not_a_hundred_percent(self):
        rows = self._corpus()
        cells = {(c.doi, c.tool): cell(c.doi, c.tool, "consistent") for c in cell_states(rows)}
        res = score(rows, cells)
        assert res["E1"].k == 0
        assert res["E1"].upper_bound is not None and res["E1"].upper_bound > 0
        text = format_report(res)
        e1_line = next(ln for ln in text.splitlines() if "E1 false-accusation" in ln)
        assert "Clopper-Pearson" in e1_line
        assert "0/24 = 0.0%" in e1_line
        assert "100" not in e1_line

    def test_low_coverage_is_declared_a_parsing_result(self):
        rows = self._corpus()
        res = score(rows, {})  # nothing evaluated at all
        assert res["E4_coverage"]["rate"] == 0.0
        assert any("PARSING RESULT" in v for v in verdict(res))

    def test_missing_cells_are_listed_rather_than_assumed_clean(self):
        rows = self._corpus()
        res = score(rows, {})
        assert len(res["missing_cells"]) == res["E4_coverage"]["scoreable"]

    def test_per_tool_sensitivity_refuses_below_the_minimum(self):
        rows = self._corpus()
        res = score(rows, {})
        sens = res["per_tool"]["grim"]["sensitivity"]
        assert not sens.estimable
        assert "not estimable" in sens.note
        assert "not estimable" in format_report(res)


class TestLoader:
    def test_duplicate_cell_is_an_error(self, tmp_path):
        p = tmp_path / "cells.jsonl"
        p.write_text("\n".join(json.dumps(cell("d", "grim")) for _ in range(2)))
        with pytest.raises(ValueError, match="duplicate cell"):
            load_cells(p)

    def test_unknown_tool_in_output_is_an_error(self, tmp_path):
        p = tmp_path / "cells.jsonl"
        p.write_text(json.dumps({"doi": "d", "tool": "vibes", "evaluated": True,
                                 "max_severity": "consistent"}))
        with pytest.raises(ValueError, match="unknown tool"):
            load_cells(p)
