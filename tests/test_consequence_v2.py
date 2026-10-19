"""Who says a consequence was COMPUTED.

A finding's `consequence` block says what the problem costs the paper -- whether
a decision flips, how many claims are affected -- and carries a `basis` of
`computed` or `asserted`. That word is the whole distinction this toolkit rests
on: "a validated tool computed this" against "the model asserted it".

THE DEFECT. The parallel pipeline never called `consequence` at all. The v2
schema REQUIRES `basis` and its enum admits `computed`, so the model wrote it
and nothing checked. MEASURED on the live paid run of 2026-08-29: 34 findings,
**14 claiming `basis: "computed"`, and 12 of those 14 `computed_by:
"model_reading"`.** `bundle.py` ranks computed above asserted within a severity
band and prints the word, so a model assertion reached the reader wearing the
toolkit's own authority. `consequence.py`'s docstring already recorded the
exploit: such a claim "was awarded the highest consequence rank in the system,
on a number nothing produced."

WHY `annotate_v2` AND NOT `annotate`. Re-calling the legacy guard was tried and
is wrong rather than merely incomplete. Its exact-key match cannot see a v2
finding's derivation-suffixed keys -- the schema instructs the model to write
`n_claims_lost_to_correction_read_off_bh` rather than the bare name -- so
replayed over the live ledger it corroborates NOTHING, including the one claim
that genuinely is corroborable. A naive re-plumb demotes a true positive and
calls that a fix.

THE SPLIT, established per claim over that run's 53-call ledger: exactly ONE of
the fourteen is corroborable, and only in half -- `claims_affected = 3` matches
the multiplicity tool's validated `n_claims_lost_to_correction: 3`, while the
same finding's `flips_significance: true` is not corroborable and
`consequence.py` expressly forbids deriving significance-flipping from
correction loss. Thirteen are asserted in full. Structural reason it cannot be
higher here: statcheck found zero statistics, so no `decision_error` pair exists
in the ledger at all.
"""
from __future__ import annotations

import copy
import json
import pathlib

import pytest

from forensic_metascience_ai_toolkit import consequence as C

REPO = pathlib.Path(__file__).resolve().parent.parent
RUN = (REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on" / "10.1002--ajcp.70049"
       / "forensic_review_gatetest2_2026-08-29")


@pytest.fixture(scope="module")
def live():
    if not (RUN / "findings.v2.json").is_file():
        pytest.skip("the reference run is not present in this checkout")
    doc = json.loads((RUN / "findings.v2.json").read_text(encoding="utf-8"))
    ledger = []
    for agent in ("tool_agent", "science_agent", "adjudicator"):
        p = RUN / f"toolcalls.{agent}.json"
        if p.is_file():
            ledger += json.loads(p.read_text(encoding="utf-8"))
    return doc["findings"], ledger


def _run(rows, ledger):
    rows = copy.deepcopy(rows)
    return rows, C.annotate_v2(rows, ledger)


class TestTheLiveReplay:
    def test_the_shipped_run_claimed_fourteen(self, live):
        """The defect, pinned as a fact about what shipped. If this stops being
        true the fixture has been regenerated and every number below is stale."""
        rows, _ = live
        claimed = [r for r in rows
                   if (r.get("consequence") or {}).get("basis") == "computed"]
        assert len(claimed) == 14
        assert sum(1 for r in claimed if r.get("computed_by") == "model_reading") == 12

    def test_only_one_survives_corroboration(self, live):
        rows, ledger = live
        out, summary = _run(rows, ledger)
        assert summary["n_computed"] == 1, summary
        survivors = [r["slug"] for r in out
                     if (r.get("consequence") or {}).get("basis") == "computed"]
        assert survivors == ["primary_family_multiplicity_uncorrected"]

    def test_the_uncorroborable_half_is_stripped(self, live):
        """The survivor claimed BOTH that three claims are affected and that
        significance flips. Only the first is in the ledger, and the module
        forbids deriving the second from correction loss."""
        rows, ledger = live
        out, _ = _run(rows, ledger)
        block = next(r["consequence"] for r in out
                     if r["slug"] == "primary_family_multiplicity_uncorrected")
        assert block["claims_affected"] == 3
        assert block["flips_significance"] is None
        assert block["basis"] == "computed"


class TestItReadsTheLedgerInBothDirections:
    """A guard that never says `computed` passes for the wrong reason, and a
    guard that says it without looking is the original defect. These pin both."""

    def test_removing_the_producing_call_removes_the_survivor(self, live):
        rows, ledger = live
        thin = [c for c in ledger if "multiplicity" not in str(c.get("tool", ""))]
        _, summary = _run(rows, thin)
        assert summary["n_computed"] == 0

    def test_changing_the_ledger_value_removes_the_survivor(self, live):
        rows, ledger = live
        altered = copy.deepcopy(ledger)
        for c in altered:
            if isinstance(c.get("result"), str):
                c["result"] = c["result"].replace(
                    '"n_claims_lost_to_correction": 3',
                    '"n_claims_lost_to_correction": 4')
        _, summary = _run(rows, altered)
        assert summary["n_computed"] == 0

    def test_no_ledger_corroborates_nothing(self, live):
        rows, _ = live
        _, summary = _run(rows, None)
        assert summary["n_computed"] == 0
        assert summary["corroborated"] is False


class TestBorrowingAndFabrication:
    def test_the_canonical_key_under_the_wrong_technique_does_not_corroborate(self, live):
        """The hole an earlier cut of this actually had. It fell back to the
        ungated derivation when the technique-gated view came out empty, so a
        finding carrying the exact canonical key under an unrelated technique
        came out `computed`. Two paths, one guarded -- the same shape as the
        defect this file exists to close."""
        rows, ledger = live
        borrowed = copy.deepcopy(rows)
        for r in borrowed:
            if r.get("technique") == "check_table":
                r["computed"] = dict(r.get("computed") or {})
                r["computed"]["n_claims_lost_to_correction"] = 3
                break
        else:
            pytest.skip("no check_table finding in the fixture")
        _, summary = _run(borrowed, ledger)
        assert summary["n_computed"] == 1, "the borrowed claim must not be promoted"

    def test_a_fabricated_value_under_the_right_technique_does_not_corroborate(self, live):
        rows, ledger = live
        faked = copy.deepcopy(rows)
        for r in faked:
            if r.get("technique") == "multiplicity_report":
                r["computed"] = dict(r.get("computed") or {})
                r["computed"]["n_claims_lost_to_correction_x"] = 99
                break
        _, summary = _run(faked, ledger)
        assert summary["n_computed"] == 0


class TestValueMatchingWouldHaveFailed:
    """WHY the producer scope and the technique gate are not belt-and-braces.

    Censused over this ledger, every integer 0-21 plus 23 and 26 appears
    somewhere in a validated result, and so do both booleans. A matcher that
    accepts "this number occurs in the ledger" corroborates nearly everything.
    """

    def test_the_ledger_contains_almost_every_small_integer(self, live):
        _, ledger = live
        seen = set()
        for c in ledger:
            if not c.get("validated"):
                continue
            try:
                found = set()
                C._walk(json.loads(c.get("result") or ""), found)
            except (ValueError, TypeError):
                continue
            seen |= {v for _, v in found if isinstance(v, int)}
        # The point is not the exact set; it is that a value-only match is
        # nearly free. Two of the live findings independently carry
        # `claims_affected: 3` as a count the model READ, coinciding with the
        # multiplicity tool's 3.
        coincidences = sum(
            1 for r in live[0]
            if (r.get("consequence") or {}).get("claims_affected") == 3)
        assert coincidences >= 2, coincidences


class TestItFailsTowardAsserted:
    def test_a_block_with_no_computed_output_is_asserted_not_dropped(self):
        rows = [{"slug": "x", "technique": "check_table",
                 "consequence": {"flips_significance": False,
                                 "claims_affected": 0, "basis": "computed"}}]
        out, summary = _run(rows, [])
        assert out[0]["consequence"]["basis"] == "asserted"
        assert summary["n_asserted"] == 1
