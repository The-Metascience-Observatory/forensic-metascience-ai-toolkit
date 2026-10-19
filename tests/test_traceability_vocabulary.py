"""The viewer said all 34 findings were "produced by a validated check". 5 were.

`MODEL_TECHNIQUES` froze on the v1 vocabulary, whose catch-all was `manual`. The
v2 schema DELETED `manual` and names the non-tool cases explicitly --
`not_computational`, `internal_contradiction`, `absence_of_evidence` -- so the
exclusion this module's own docstring says exists to stop us "inflating our own
stated shortfall" matched NOTHING.

MEASURED on the current ajcp run: 0 of 34 techniques are in `MODEL_TECHNIQUES`,
while `computed_by` says 5 are `registry_tool` and 29 are `model_reading`.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from forensic_metascience_ai_toolkit.viewer_facts import traceability, traceability_sentence

RUN = (pathlib.Path(__file__).resolve().parents[1] / "tests/fixtures/papers/high_value_pdfs_to_run_on"
       / "10.1002--ajcp.70049" / "forensic_review_gatetest2_2026-08-29"
       / "findings.v2.json")


def _f(fid, computed_by=None, technique="grim_check", **kw):
    row = {"finding_id": fid, "technique": technique, "outcome": "problem"}
    if computed_by is not None:
        row["computed_by"] = computed_by
    row.update(kw)
    return row


class TestItReadsWhatATooolActuallyComputed:
    def test_a_model_reading_row_is_not_counted_as_tool_produced(self):
        tr = traceability({"findings": [_f("a", "model_reading")]})
        assert tr["joined_to_call"]["of"] == 0

    def test_a_registry_tool_row_is(self):
        tr = traceability({"findings": [_f("a", "registry_tool")]})
        assert tr["joined_to_call"]["of"] == 1

    @pytest.mark.parametrize("cb", ["model_reading", "model_knowledge"])
    def test_every_model_provenance_is_excluded(self, cb):
        tr = traceability({"findings": [_f("a", cb)]})
        assert tr["joined_to_call"]["of"] == 0

    def test_a_v2_technique_name_no_longer_slips_through(self):
        """These are exactly the techniques the v1 list could not name."""
        rows = [_f("a", "model_reading", technique="not_computational"),
                _f("b", "model_reading", technique="internal_contradiction"),
                _f("c", "model_reading", technique="absence_of_evidence")]
        assert traceability({"findings": rows})["joined_to_call"]["of"] == 0

    def test_the_v1_fallback_still_works_for_archived_rows(self):
        """An archived run carries no `computed_by`; the technique test is
        kept for it."""
        rows = [_f("a", None, technique="manual"),
                _f("b", None, technique="grim_check")]
        assert traceability({"findings": rows})["joined_to_call"]["of"] == 1


@pytest.mark.skipif(not RUN.is_file(), reason="reference run not present")
class TestOnTheRealRun:
    @pytest.fixture(scope="class")
    def doc(self):
        return json.loads(RUN.read_text(encoding="utf-8"))

    def test_the_denominator_matches_computed_by(self, doc):
        n_tool = sum(1 for f in doc["findings"]
                     if f.get("computed_by") == "registry_tool")
        assert traceability(doc)["joined_to_call"]["of"] == n_tool == 5

    def test_the_sentence_no_longer_claims_all_of_them(self, doc):
        sentence = traceability_sentence(traceability(doc))
        assert "Of the 5 produced by a validated check" in sentence
        assert "Of the 34 produced by a validated check" not in sentence

    def test_the_hand_read_findings_are_named_rather_than_hidden(self, doc):
        """29 is the number the reader most needs, and it was folded into the
        tool-produced count."""
        assert traceability(doc)["joined_to_call"]["hand_read_excluded"] == 29
        assert "29 findings the review read off the paper by hand" in \
            traceability_sentence(traceability(doc))
