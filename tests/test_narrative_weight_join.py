"""A MEASURED NEGATIVE: findings cannot be joined to anatomy tests.

`weight_finding_severity` (anatomy.py) is unconsumed, and it was on the
2026-08-11 triage's ranked shortlist as an (A) -- something whose absence costs
something. The cost is real: `anatomy.py`'s own docstring says "A discrepancy in
a paper's headline claim and one in an incidental baseline row are not the same
event. Severity should be weighted by narrative role", and no finding carries
`narrative_weight`, so no report can lead with what is load-bearing.

THE OBVIOUS FIX WAS MEASURED AND REJECTED. `infer_narrative_tier` takes a
`StatisticalTest`; a finding is not one. The only field the two share is a
free-text `location`. Measured over every archived run that holds both a
findings list and an anatomy block:

    11 runs, 283 findings
      89.0%  no matching test at all      (252)
       5.7%  exactly one, exact match      (16)
       4.9%  exactly one, by substring     (14)
       0.4%  ambiguous, several matched     (1)

Wiring it on `location` would tier 10.6% of findings. That is not merely thin,
it is BIASED: the findings that match are the ones whose location was phrased
like a test's, which favours verbose per-cell table locations and excludes
prose findings entirely. `undermines_headline_claim` is the flag a reader would
weigh most heavily, and setting it from a string-format accident points that
weight at the wrong findings -- toward accusation, on the project's own reading
of which errors are worst.

WHAT THIS FILE IS FOR. Not to celebrate a gap. It pins the measurement so that
(a) nobody rebuilds the bad join, and (b) the day the sweep emits a declared
`test_id`, `test_the_join_is_still_impossible` fails and says the wiring is now
available.
"""
import glob
import json
import re
from pathlib import Path

import pytest

from metascience_agent.anatomy import SEVERITY_WEIGHT, weight_finding_severity

REPO = Path(__file__).resolve().parents[1]

#: MEASURED 2026-08-11. A ratchet, not a pin: the match rate may only improve.
#: Stated as a floor on the FAILURE share so that a change which makes the join
#: worse also trips it.
MAX_UNJOINABLE_SHARE = 0.92
MEASURED_UNJOINABLE_SHARE = 0.89


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def _archive():
    for p in sorted(glob.glob(str(REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on/*/forensic_review*/findings.json"))):
        if "scratchpad" in p:
            continue
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        findings = d.get("findings") or []
        tests = ((d.get("anatomy") or {}).get("tests")) or []
        if findings and tests:
            yield p, findings, tests


class TestTheFunctionItselfIsSound:
    """It is not broken -- it is unreachable. Keep it tested so that wiring it
    later is a one-line change and not a rewrite."""

    def test_it_never_escalates_the_severity_it_was_given(self):
        for tier in SEVERITY_WEIGHT:
            got = weight_finding_severity("suspicious", tier)
            assert got["severity"] == "suspicious", (
                "narrative importance may reorder findings; it may not make one "
                "more damning than the arithmetic supports")

    def test_only_primary_undermines_the_headline(self):
        assert weight_finding_severity("consistent", "primary")["undermines_headline_claim"]
        for tier in ("secondary", "exploratory", "incidental"):
            assert not weight_finding_severity("x", tier)["undermines_headline_claim"]

    def test_an_unknown_tier_takes_the_lowest_weight(self):
        """Fail-safe direction: an unrecognised tier must not be promoted into
        the group a report leads with."""
        got = weight_finding_severity("suspicious", "not-a-tier")
        assert got["narrative_weight"] == min(SEVERITY_WEIGHT.values())
        assert got["undermines_headline_claim"] is False


class TestTheJoinThatWouldWireIt:
    def test_the_archive_has_runs_to_measure(self):
        runs = list(_archive())
        if not runs:
            pytest.skip("no archived run carries both findings and an anatomy block")
        assert len(runs) >= 5, "the 89% figure was measured over 11 runs"

    def test_the_join_is_still_impossible(self):
        """DELETE THIS TEST WHEN IT FAILS, and wire the annotator instead.

        A failure here means the match rate improved -- almost certainly
        because findings gained a declared `test_id` -- and the measured reason
        for leaving `weight_finding_severity` unwired no longer holds."""
        runs = list(_archive())
        if not runs:
            pytest.skip("no archived run carries both findings and an anatomy block")
        total = unjoinable = 0
        for _, findings, tests in runs:
            locs = [_norm(t.get("location")) for t in tests]
            ids = {t.get("id") for t in tests if t.get("id")}
            for f in findings:
                total += 1
                if f.get("test_id") in ids:
                    continue            # a DECLARED join -- the thing we want
                fl = _norm(f.get("location"))
                if not fl:
                    unjoinable += 1
                    continue
                hits = [t for t in locs if t and (t == fl or t in fl or fl in t)]
                if len(hits) != 1:
                    unjoinable += 1
        share = unjoinable / max(total, 1)
        assert share <= MAX_UNJOINABLE_SHARE, (
            f"{unjoinable} of {total} findings ({share:.0%}) cannot be joined to a "
            f"test, above the pinned ceiling -- the join got WORSE")
        assert share >= 0.5, (
            f"only {share:.0%} of findings are unjoinable, down from the measured "
            f"{MEASURED_UNJOINABLE_SHARE:.0%}. The join may now be good enough to "
            "wire `weight_finding_severity` through -- see its docstring, delete "
            "this assertion, and add the annotator at agent.py's annotator chain.")

    def test_no_finding_carries_a_narrative_weight_yet(self):
        """The consequence, stated plainly, so it is not rediscovered as new."""
        for path, findings, _ in _archive():
            for f in findings:
                assert "narrative_weight" not in f, (
                    f"{path} carries narrative_weight -- if the annotator was "
                    "wired, this file's premise is stale and it should be "
                    "replaced by a test of the join's accuracy")
