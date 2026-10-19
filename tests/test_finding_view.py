"""`finding_view`: one reader for the four shapes a finding row takes.

Every fixture here is SHAPED LIKE A LIVE ROW, by construction: the producer
row is what `parallel.analyze_paper_parallel` hands `secondlook.worklist`
(after `assign_finding_ids` and the quote/reproduction annotators, before
`adjudicate.apply`); the adjudicated row is a `findings.v2.json` row; the card
is built THROUGH `bundle._v2_container` so it cannot drift from the adapter.
A v1-shaped fixture is how the `secondlook` defect survived three fixes.
"""

from __future__ import annotations

import pytest

from metascience_agent import finding_view as FV
from metascience_agent import severity9
from metascience_agent.bundle import _v2_container

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
V1 = {"id": "table2_gordon", "severity": "suspicious", "location": "Table 2",
      "technique": "grim"}


def card(row: dict) -> dict:
    return _v2_container({"findings": [row]})["findings"][0]


class TestTheFixturesAreLiveShaped:
    def test_no_fixture_carries_the_v1_key(self):
        for row in (PRODUCER, ADJUDICATED, DISCARDED):
            assert "id" not in row and row["finding_id"].startswith("f_")

    def test_the_producer_row_has_no_severity_key_at_all(self):
        """The shape at parallel.py's `secondlook.worklist` call: absent, not None."""
        assert "severity" not in PRODUCER
        assert "provisional_severity" in PRODUCER

    def test_the_card_carries_the_adapter_string(self):
        c = card(ADJUDICATED)
        assert c["severity"] == "S4" and c["id"] == "f_262ff67245b226e5"


class TestRef:
    def test_finding_id_first(self):
        assert FV.ref(ADJUDICATED) == "f_262ff67245b226e5"
        assert FV.ref({**ADJUDICATED, "id": "other"}) == "f_262ff67245b226e5"

    def test_v1_id_then_slug(self):
        assert FV.ref(V1) == "table2_gordon"
        assert FV.ref({"slug": "s"}) == "s"

    def test_the_card_copy_agrees_with_the_row(self):
        assert FV.ref(card(ADJUDICATED)) == FV.ref(ADJUDICATED)

    @pytest.mark.parametrize("junk", [None, "x", 3, {}, {"finding_id": ""}])
    def test_junk_is_the_empty_string(self, junk):
        assert FV.ref(junk) == ""


class TestSeverity:
    def test_a_producer_row_reports_its_provisional_level(self):
        assert FV.effective_severity(PRODUCER) == 4
        assert FV.severity_level(PRODUCER) == 4

    def test_an_adjudicated_none_is_a_discard_not_an_absence(self):
        """`severity: None` with a provisional of 4 must NOT resurrect the 4."""
        assert FV.effective_severity(DISCARDED) is None
        assert FV.severity_level(DISCARDED) is None

    def test_the_card_string_is_a_level(self):
        assert FV.severity_level(card(ADJUDICATED)) == 4
        assert FV.severity_level(card(DISCARDED)) is None

    def test_a_v1_word_is_not_a_level(self):
        assert FV.severity_level(V1) is None
        assert FV.effective_severity(V1) == "suspicious"

    @pytest.mark.parametrize("bad", [True, False, 0, 10, "S0", "S10", "4", "x"])
    def test_off_ladder_values_are_none(self, bad):
        assert FV.severity_level({"severity": bad}) is None


class TestIsAccusatory:
    def test_a_producer_row_at_the_threshold_accuses(self):
        assert FV.is_accusatory(PRODUCER)
        assert FV.is_accusatory({**PRODUCER, "provisional_severity": severity9.ACCUSATORY_MIN})
        assert not FV.is_accusatory({**PRODUCER, "provisional_severity": severity9.ACCUSATORY_MIN - 1})

    def test_the_three_v2_shapes_agree(self):
        assert FV.is_accusatory(PRODUCER) is FV.is_accusatory(ADJUDICATED) \
            is FV.is_accusatory(card(ADJUDICATED)) is True

    def test_a_discard_accuses_nobody_in_any_shape(self):
        assert not FV.is_accusatory(DISCARDED)
        assert not FV.is_accusatory(card(DISCARDED))

    @pytest.mark.parametrize("outcome", ["pass", "undecided", "", None])
    def test_a_level_without_a_problem_outcome_is_not_an_accusation(self, outcome):
        assert not FV.is_accusatory({**ADJUDICATED, "outcome": outcome})

    def test_the_v1_words_still_accuse(self):
        for word in ("suspicious", "highly_suspicious", "impossible"):
            assert FV.is_accusatory({**V1, "severity": word}), word
        for word in ("indeterminate", "consistent", None, ""):
            assert not FV.is_accusatory({**V1, "severity": word}), word

    def test_it_reads_the_ladder_rather_than_copying_it(self):
        import inspect
        src = inspect.getsource(FV.is_accusatory)
        assert "severity9.ACCUSATORY_MIN" in src

    @pytest.mark.parametrize("junk", [None, "x", 3, [], {}])
    def test_junk_accuses_nobody(self, junk):
        assert not FV.is_accusatory(junk)
