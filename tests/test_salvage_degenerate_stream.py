"""A producer that degenerates mid-document and recovers must not be a loss.

MEASURED 2026-09-04 on a live grok tool-expert run (airforce, the A/B's
parallel/parallel arm). The stage made 87 tool calls over 1,030 s and returned
one `impossible` verdict. Its 61,300-char result BEGAN with a real document,
broke off at char 4,904 into `Extra. Extra. Extra...` repeated, and then
re-emitted a COMPLETE 18-finding document (34 register rows, 8 unchecked).

`_extract_json` returned `failed` and discarded all of it, because every tier
it had reads from the START of the stream: `json.loads` on the whole string
dies on the abandoned prefix, and the fenced-block tier finds nothing because
grok emits bare JSON. The run was then charged for a paid `_repair_json`, which
in the archive came back EMPTY -- so a stage that had done the work was
recorded as having produced nothing, and the "analyst loss" was partly ours.
"""
from __future__ import annotations

import json

from forensic_metascience_ai_toolkit.agent import _extract_json, _salvage_documents

DOC = {"schema_version": "2.0", "paper_id": "p",
       "findings": [{"slug": "a", "technique": "grim_percentage"}],
       "statistics_register": [{"x": 1}]}
EMPTY = {"schema_version": "2.0", "paper_id": "p", "findings": [],
         "statistics_register": []}


def _degenerate(prefix_len: int = 80) -> str:
    """The measured shape: a truncated document, filler, then a complete one."""
    broken = json.dumps(DOC)[:prefix_len]
    return broken + " Extra." * 60 + json.dumps(DOC)


class TestTheCompleteDocumentIsRecovered:
    def test_a_degenerate_stream_yields_its_complete_document(self):
        doc, path = _extract_json({"result": _degenerate(), "text": ""})
        assert path == "salvaged_object"
        assert doc is not None and len(doc["findings"]) == 1

    def test_the_richest_document_wins_not_the_last(self):
        """Grok emits empty skeleton placeholders throughout a run, so 'the
        last complete object' would happily return one emitted AFTER the real
        document and call the paper clean."""
        stream = "junk{ " + json.dumps(DOC) + json.dumps(EMPTY)
        doc, path = _extract_json({"result": stream, "text": ""})
        assert path == "salvaged_object"
        assert len(doc["findings"]) == 1, "an empty skeleton outranked the real one"

    def test_the_stream_is_searched_when_the_result_has_nothing(self):
        doc, path = _extract_json({"result": "", "text": _degenerate()})
        assert path == "salvaged_object" and len(doc["findings"]) == 1


class TestItNeverInventsAndNeverPreempts:
    def test_a_truncated_document_alone_is_not_salvaged(self):
        """Only objects that decode COMPLETELY are eligible. A half-written
        document is skipped, not repaired -- repairing it here would be us
        writing the model's findings for it."""
        broken = json.dumps(DOC)[:80] + " Extra." * 40
        doc, path = _extract_json({"result": broken, "text": ""})
        assert path == "failed" and doc is None

    def test_a_genuinely_empty_stage_still_fails(self):
        """airforce's archived failure is a real one: 238 chars, zero tool
        calls. Salvage must not manufacture a document for it."""
        assert _extract_json({"result": "", "text": ""}) == (None, "failed")
        assert _extract_json({"result": "I could not do this.",
                              "text": ""}) == (None, "failed")

    def test_an_embedded_non_document_object_is_ignored(self):
        """Tool results and argument blobs are objects too. Only things
        carrying a document marker are eligible."""
        assert _salvage_documents('{"severity": "impossible", "n": 80}') == []

    def test_the_cheap_tiers_still_win(self):
        assert _extract_json({"structured_output": {"a": 1}})[1] == "json_schema"
        assert _extract_json({"result": json.dumps(DOC)})[1] == "json_schema"
        fenced = "```json\n" + json.dumps(DOC) + "\n```"
        assert _extract_json({"result": "no", "text": fenced})[1] == "fenced_block"
