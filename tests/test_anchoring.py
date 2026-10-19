"""An accusation with nothing behind it, and the narrow rule that catches it.

FROM THE ROMANO VARIABILITY STUDY, 2026-08-11
(`scratchpad/romano_variability_fable_2026-08-11.md`). Two runs of one paper at
byte-identical prompt and schema shared 5 of 7 accusatory clusters. One of the
two unilateral accusations was this:

    "Fixed slopes omit a variance component known to bias 1-1-1 multilevel
     indirect effects"   suspicious · warrant field_norm · stage1_finding_ids []

No sweep ancestor, no tool, no mention anywhere in the other run's report. An
accusation born whole in the editorial pass from a methodological norm the
review supplied, with a 50% chance of existing at all.

WHY THE RULE IS NARROW, WHICH IS THE WHOLE DESIGN. "Clamp every unanchored
stage-2 finding" was the first proposal and it is wrong. MEASURED over 89
archived editorial findings: 7 unanchored, 3 of them accusatory -- and reading
the three shows they are three different things. One is

    "Results text reverses the direction of the lorazepam-hypertension
     association against its own table"   suspicious · confidence high

a text-vs-table contradiction naming Table 3's Lorazepam row. No tool in the kit
produces that, any reader can check it in one glance, and it is exactly what
this toolkit exists to find. A blunt rule silences it.

`warrant` is the discriminator, and it was already in the schema. `field_norm`
is, in `warrants.py`'s words, "a standard WE supply that this paper never
accepted" -- the only class that can hold a paper to something its design never
owed. Unanchored AND `field_norm` means no sweep result, no arithmetic, and no
commitment by the authors: an appeal to authority. That is worth saying and not
worth accusing on.

MEASURED AFTER THE FIX, replaying the archive through the production shape:
89 findings, 7 unanchored, **1 clamped**.
"""
import copy
import glob
import json
from pathlib import Path

import pytest

from metascience_agent import anchoring as A

REPO = Path(__file__).resolve().parents[1]


def _result(findings, sweep_ids=("s1", "s2")):
    """PRODUCTION SHAPE. The editorial object lives under `report_obj` and the
    sweep under `findings` -- reading `report` alone is how two earlier clamps
    returned at their first line on every real run while their tests passed."""
    return {
        "report_obj": {"findings": findings},
        "findings": {"findings": [{"id": i} for i in sweep_ids]},
    }


def _f(**kw):
    base = {"title": "t", "severity": "suspicious", "warrant": "logical",
            "stage1_finding_ids": []}
    base.update(kw)
    return base


class TestWhatCountsAsAnAnchor:
    def test_a_resolvable_stage1_id_anchors_it(self):
        r = _result([_f(stage1_finding_ids=["s1"])])
        assert A.annotate_anchoring(r)["n_anchored"] == 1

    def test_no_ids_at_all_is_unanchored(self):
        assert A.annotate_anchoring(_result([_f()]))["n_unanchored"] == 1

    def test_ids_that_do_not_resolve_are_unanchored(self):
        """THE EASIEST ANCHOR TO FAKE. A citation is only evidence if it points
        at something; counting the list length would let a finding assert its
        own provenance for free."""
        s = A.annotate_anchoring(_result([_f(stage1_finding_ids=["nope"])]))
        assert s["n_unanchored"] == 1 and s["n_dangling"] == 1

    def test_one_good_id_among_bad_ones_still_anchors(self):
        r = _result([_f(stage1_finding_ids=["nope", "s2"])])
        assert A.annotate_anchoring(r)["n_anchored"] == 1

    def test_the_finding_carries_the_verdict_for_the_reader(self):
        r = _result([_f()])
        A.annotate_anchoring(r)
        f = r["report_obj"]["findings"][0]
        assert f["anchored"] is False and f["anchor"] == "none"

    def test_every_kind_has_a_meaning_a_reader_can_read(self):
        for kind in A.ANCHOR_KINDS:
            assert len(A.ANCHOR_MEANING[kind]) > 40


class TestAnnotationNeverChangesASeverity:
    """Provenance, not punishment. The lorazepam finding must survive this pass
    untouched; only the separate clamp may lower anything."""

    def test_an_unanchored_accusation_keeps_its_severity(self):
        r = _result([_f(severity="suspicious", warrant="logical")])
        A.annotate_anchoring(r)
        assert r["report_obj"]["findings"][0]["severity"] == "suspicious"

    def test_it_is_reported_so_a_reader_can_weigh_it(self):
        r = _result([_f(severity="suspicious", warrant="logical")])
        s = A.annotate_anchoring(r)
        assert len(s["unanchored_accusations"]) == 1


class TestTheClampIsNarrowOnPurpose:
    def test_unanchored_plus_supplied_norm_is_clamped(self):
        r = _result([_f(severity="suspicious", warrant="field_norm")])
        s = A.clamp_unanchored_norms(r)
        assert s["n_clamped"] == 1
        assert r["report_obj"]["findings"][0]["severity"] == A.UNANCHORED_CEILING

    def test_unanchored_but_logical_is_left_alone(self):
        """THE LORAZEPAM CASE. A contradiction inside the document needs no
        external norm and no tool; it needs a reader."""
        r = _result([_f(severity="suspicious", warrant="logical")])
        assert A.clamp_unanchored_norms(r)["n_clamped"] == 0
        assert r["report_obj"]["findings"][0]["severity"] == "suspicious"

    def test_anchored_supplied_norm_is_left_alone(self):
        """`clamp_supplied_norms` already caps this at `suspicious`. Having a
        sweep result behind it is what earns it that rung."""
        r = _result([_f(severity="suspicious", warrant="field_norm",
                        stage1_finding_ids=["s1"])])
        assert A.clamp_unanchored_norms(r)["n_clamped"] == 0

    def test_a_benign_unanchored_norm_is_not_touched(self):
        """The clamp exists to stop ACCUSATIONS with no evidence. A finding
        below the accusatory line is already saying it found nothing."""
        r = _result([_f(severity="consistent", warrant="field_norm")])
        assert A.clamp_unanchored_norms(r)["n_clamped"] == 0
        assert r["report_obj"]["findings"][0]["severity"] == "consistent"

    def test_it_lands_on_the_refusal_tier_not_on_a_clean_bill(self):
        """`indeterminate` says we could not settle it. `consistent` would
        assert the paper is fine, which we equally cannot support."""
        assert A.UNANCHORED_CEILING == "indeterminate"

    def test_the_reader_is_told_it_was_lowered_and_why(self):
        r = _result([_f(severity="highly_suspicious", warrant="field_norm")])
        A.clamp_unanchored_norms(r)
        src = r["report_obj"]["findings"][0]["severity_source"]
        assert src["original"] == "highly_suspicious"
        assert src["clamped_by"] == "unanchored_supplied_norm"
        assert "never accepted" in src["why"] or "supplied" in src["why"]


class TestItReadsTheShapeProductionActuallyWrites:
    """Two clamps in this repo shipped as enforced and enforced nothing, because
    they read `result["report"]` while production writes `report_obj`. Their
    tests passed throughout on hand-built `{"report": ...}` fixtures."""

    def test_report_obj_is_read(self):
        r = {"report_obj": {"findings": [_f(warrant="field_norm")]}, "findings": {}}
        assert A.clamp_unanchored_norms(r)["n_clamped"] == 1

    def test_report_still_works_as_a_fallback(self):
        r = {"report": {"findings": [_f(warrant="field_norm")]}, "findings": {}}
        assert A.clamp_unanchored_norms(r)["n_clamped"] == 1

    def test_a_result_with_no_report_returns_a_zeroed_summary(self):
        for r in ({}, {"report_obj": None}, {"report_obj": {"findings": "x"}}):
            assert A.clamp_unanchored_norms(r)["n_clamped"] == 0
            assert A.annotate_anchoring(r)["n_findings"] == 0

    def test_the_warrant_string_matches_the_module_that_defines_it(self):
        """Kept as a literal here so a rename in `warrants.py` fails loudly
        instead of silently disabling this clamp."""
        from metascience_agent.warrants import SUPPLIED_WARRANT
        assert A.SUPPLIED_WARRANT == SUPPLIED_WARRANT

class TestTheArchiveReplayed:
    """The measurement the rule was calibrated on. A ratchet, not a pin: the
    clamp may fire less often, never wildly more."""

    MAX_CLAMPED = 3

    @pytest.fixture(scope="class")
    def replay(self):
        runs = []
        for p in sorted(glob.glob(str(
                REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on/*/forensic_review*/report.json"))):
            d = Path(p)
            try:
                rep = json.loads(d.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            fp = d.parent / "findings.json"
            try:
                sweep = json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else {}
            except (OSError, ValueError):
                sweep = {}
            r = {"report_obj": copy.deepcopy(rep), "findings": sweep}
            runs.append((d, A.annotate_anchoring(r), A.clamp_unanchored_norms(r), r))
        if not runs:
            pytest.skip("no archived reports in this checkout")
        return runs

    def test_almost_every_finding_is_anchored(self, replay):
        tot = sum(a["n_findings"] for _, a, _, _ in replay)
        un = sum(a["n_unanchored"] for _, a, _, _ in replay)
        assert un / max(tot, 1) < 0.25, (
            f"{un} of {tot} editorial findings cite no stage-1 result. If this "
            "climbs, the editorial stage has stopped building on the sweep and "
            "the clamp is no longer the right instrument -- the PROMPT is.")

    def test_the_clamp_stays_rare(self, replay):
        n = sum(c["n_clamped"] for _, _, c, _ in replay)
        assert n <= self.MAX_CLAMPED, (
            f"{n} archived findings clamped, above the pinned "
            f"{self.MAX_CLAMPED}. A clamp that fires often is a prompt problem "
            "wearing a clamp's clothes; read the new ones before raising this.")

    def test_it_catches_the_finding_it_was_built_for(self, replay):
        """The fixed-slopes finding in the clamped Romano run."""
        hits = [c for d, _, c, _ in replay
                if "eat.24415" in str(d) and "clamped" in d.parent.name
                for c in c["clamps"]]
        if not hits:
            pytest.skip("clamped Romano run not in this checkout")
        assert any("ixed slopes" in h["title"] for h in hits)
        assert hits[0]["from"] == "suspicious"
        assert hits[0]["to"] == "indeterminate"

    def test_it_does_not_touch_the_lorazepam_contradiction(self, replay):
        """The regression that matters most: a real catch, unanchored, kept."""
        for d, _, _, r in replay:
            for f in r["report_obj"].get("findings") or []:
                if "lorazepam" in str(f.get("title", "")).lower():
                    assert f["severity"] == "suspicious", (
                        "a text-vs-table contradiction was silenced -- that is "
                        "the cost this rule was made narrow to avoid")
