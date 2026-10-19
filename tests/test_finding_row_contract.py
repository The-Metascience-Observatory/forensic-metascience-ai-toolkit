"""Every consumer of a finding row names the row and sees the accusation.

THE CLASS OF DEFECT. A module reads a finding-row field under a name, or with
a value vocabulary, that the producing path does not use. Each instance below
was LIVE on real output when this file was written (2026-09-04), and each is
pinned here on a fixture shaped like the row the live path actually hands the
consumer -- because a v1-shaped fixture is exactly how every one of them
passed its own tests while shipping wrong:

  secondlook.worklist        wrote `"id": f.get("id")` on rows carrying
                             `finding_id`; `{"id": null, "severity": null}`
                             reached the adjudicator on 4 of 10 control runs
                             (litvak02/05/06/07, v1.22.0).
  agreement._band            `str(severity) in ACCUSATORY` (v1 words) on v2
                             integers: 285 of 285 control rows banded
                             "clears", 51 of them level-3+ problems. (The one
                             two-run v2 paper in reach has no accusation in
                             either run, so its 0 clusters was a TRUE zero --
                             the defect is proven on the band count, not
                             there.)
  viewer_facts.evidence_ledger
                             tested the int ladder, but the bundle path hands
                             it `_v2_container` cards whose severity is the
                             STRING "S<n>": `accusatory_without_a_validated_check`
                             read 0 on litvak05 where the true count is 5.
  bundle._sankey             right-hand nodes from the five v1 words only, so
                             13 of 29 links on litvak05 pointed at nodes that
                             did not exist and the JS dropped every accusation
                             ribbon.

DIRECTION. None of these accuses MORE; each says less than the system knows,
and the first hides from the adjudicator the one list built to make it look
again at a weak accusation.
"""

from __future__ import annotations

from forensic_metascience_ai_toolkit import secondlook as S
from forensic_metascience_ai_toolkit import viewer_facts as VF
from forensic_metascience_ai_toolkit.bundle import _check_table, _sankey, _v2_container
from forensic_metascience_ai_toolkit.evaluation import agreement as A

from forensic_metascience_ai_toolkit.bundle import _v2_container as _adapter

# THE SAME FIXTURES AS tests/test_finding_view.py, restated because test
# modules here are not importable from one another. Shaped on litvak05
# `f_262ff67245b226e5` (v1.22.0, 2026-09-03): the producer row is the shape
# at parallel.py's `secondlook.worklist` call -- `finding_id`,
# `provisional_severity`, and NO `severity` key.
PRODUCER = {
    "slug": "gordon_self_esteem_mean_exceeds_scale_maximum",
    "finding_id": "f_262ff67245b226e5", "finding_id_hasher": "1",
    "producer": "tool_expert", "technique": "grim_check",
    "title": "Table 2: Gordon self-esteem mean 50.48 exceeds the stated scale maximum",
    "description": "The paper states the self-esteem measure is the 10-item Rosenberg scale.",
    "location": "Table 2, Gordon row, Self-esteem column",
    "outcome": "problem", "provisional_severity": 4,
    "quote": "| Gordon | 80 | 14 | 66 |", "quote_verified": "verbatim",
    "quote_source": "the paper's text",
    "inputs": {"mean": 50.48, "n": 80, "bound_source": "logically_necessary"},
    "computed": {"grim_verdict": "impossible"},
    "computed_by": "registry_tool", "impossible": True, "quarantined": False,
    "tool_verdict": {"severity": "impossible", "tool": "grim_check",
                     "validated": True, "quarantined_raw": None},
    "reproduction": "metascience grim ...", "reproduction_kind": "command",
    "reproduction_valid": True, "anchors": [],
}
ADJUDICATED = {**PRODUCER, "severity": 4, "severity_is_provisional": False,
               "adjudication": {"action": "kept", "rationale": "...", "category": "none"},
               "anchor_summary": {"pdf": "anchored", "primary_anchor_id": None, "page": 31}}
DISCARDED = {**ADJUDICATED, "finding_id": "f_3a508c51af917c91", "severity": None,
             "adjudication": {"action": "discarded", "rationale": "...",
                              "category": "misapplication"}}


def card(row: dict) -> dict:
    """Built THROUGH the adapter, so the fixture cannot drift from it."""
    return _adapter({"findings": [row]})["findings"][0]

#: A kept model-reading accusation, shaped on litvak05 `f_0fd8774546f184a7`
#: (severity 4, `not_computational`, `computed_by: model_reading`).
MODEL_READING = {**ADJUDICATED, "finding_id": "f_0fd8774546f184a7",
                 "slug": "discussion_overstates_meta_effect",
                 "technique": "not_computational", "computed_by": "model_reading",
                 "tool_verdict": None, "impossible": False, "computed": {},
                 "inputs": {}, "location": "Discussion, paragraph 2"}


class TestSecondLookNamesTheAccusation:
    def test_the_worklist_item_carries_the_finding_id(self):
        row = {**PRODUCER, "quote_verified": "absent"}   # one decidable weakness
        w = S.worklist([row])
        assert w["n_accusatory"] == 1 and w["n_flagged"] == 1
        item = w["items"][0]
        assert item["id"] == "f_262ff67245b226e5", item
        assert item["severity"] == 4, item

    def test_a_producer_row_is_counted_as_an_accusation(self):
        assert S.worklist([PRODUCER])["n_accusatory"] == 1

    def test_a_discarded_row_is_not(self):
        assert S.worklist([DISCARDED])["n_accusatory"] == 0


class TestAgreementBandsTheV2Ladder:
    def test_an_accusation_bands_as_one(self):
        assert A.cluster_key(ADJUDICATED).endswith("|accuses")
        assert A.cluster_key(ADJUDICATED, loose=True).endswith("|accuses")

    def test_a_discard_and_a_pass_band_as_clears(self):
        assert A.cluster_key(DISCARDED).endswith("|clears")
        assert A.cluster_key({**ADJUDICATED, "outcome": "pass", "severity": None}).endswith("|clears")

    def test_accusation_pass_at_k_sees_a_v2_accusation(self):
        r = A.agreement([[ADJUDICATED], [ADJUDICATED]])
        assert r["accusations"]["n_clusters"] == 1
        assert r["accusations"]["in_every_run"] == 1

    def test_an_accusation_and_a_pass_at_one_location_are_two_clusters(self):
        clear = {**ADJUDICATED, "finding_id": "f_other", "outcome": "pass", "severity": None}
        assert A.cluster_key(ADJUDICATED) != A.cluster_key(clear)


class TestTheEvidenceLedgerCountsCardAccusations:
    def test_a_model_reading_accusation_on_a_card_is_counted(self):
        led = VF.evidence_ledger({"findings": [card(MODEL_READING)]})
        assert led["n"] == 1
        assert led["counts"]["reading"] == 1
        assert led["accusatory_without_a_validated_check"] == 1

    def test_a_tool_computed_accusation_is_not(self):
        led = VF.evidence_ledger({"findings": [card(ADJUDICATED)]})
        assert led["counts"]["computed"] == 1
        assert led["accusatory_without_a_validated_check"] == 0

    def test_a_discarded_model_reading_row_is_not(self):
        row = {**MODEL_READING, "severity": None,
               "adjudication": {"action": "discarded", "rationale": "", "category": "none"}}
        assert VF.evidence_ledger({"findings": [card(row)]})["accusatory_without_a_validated_check"] == 0

    def test_the_raw_v2_document_gives_the_same_answer_as_the_card(self):
        """The bundle path hands cards; a raw `findings.v2.json` hands rows.
        The two must not disagree about the same finding."""
        raw = VF.evidence_ledger({"findings": [MODEL_READING]})
        via_card = VF.evidence_ledger({"findings": [card(MODEL_READING)]})
        assert raw["accusatory_without_a_validated_check"] == \
            via_card["accusatory_without_a_validated_check"] == 1


class TestTheSankeyHasANodeForEveryLink:
    CALLS = [{"tool": "grim_check", "validated": True}]

    def _cards(self):
        return _v2_container({"findings": [ADJUDICATED, MODEL_READING, DISCARDED]})["findings"]

    def test_every_link_endpoint_is_a_node(self):
        s = _sankey(self.CALLS, self._cards(), None)
        ids = {n["id"] for n in s["nodes"]}
        dangling = [l for l in s["links"] if l["source"] not in ids or l["target"] not in ids]
        assert not dangling, dangling

    def test_the_accusation_rung_is_a_right_hand_node(self):
        s = _sankey(self.CALLS, self._cards(), None)
        mids = [n["id"] for n in s["nodes"] if n["column"] == 1]
        assert "S4" in mids
        # worst rung first, then the v1 words' own order, then the sink
        assert mids.index("S4") < mids.index("no finding") if "no finding" in mids else True

    def test_the_third_column_joins_on_the_card_id(self):
        s = _sankey(self.CALLS, self._cards(), [])   # v2: editorial list is empty
        reported = [l for l in s["links"] if l["target"] == "reported"]
        assert sum(l["value"] for l in reported) == 2, s["links"]   # two kept problems

    def test_the_check_table_kept_column_joins_on_the_card_id(self):
        rows = {r["check"]: r for r in _check_table(self.CALLS, self._cards(), [])}
        assert rows["grim_check"]["kept"] == 1
        assert rows["hand-computed"]["kept"] == 1
