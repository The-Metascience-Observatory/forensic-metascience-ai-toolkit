"""The coverage census runs on the parallel pipeline.

It is the only INDEPENDENT denominator this system has: it reads the paper's
own tables with no model involved, so the model's "I checked N" has something
to be divided by. `docs/specs/pipeline.md` has said since the v2 cutover that
the enrichment block "attaches to the ADJUDICATED object", and until v1.23.0
it ran only on the retiring legacy path.

Two measurements shaped these tests, both from 2026-09-03:

* The census read stage `messages`, and `_slim_messages` empties large
  `tool_result` payloads before they are persisted. On the archived
  `wound_healing` run the three `check_table` results are **0 chars** in
  `messages.tool_agent.json` and 25,519 / 21,809 / 9,774 chars in
  `toolcalls.tool_agent.json`. A census computed from an archived run
  therefore reported nothing checked, and I nearly filed that as a defect in
  the census rather than in my own probe.
* `render` reported only the `check_table` path. On `apple_cider` it printed
  "0 of 168 checkable cells were checked (0%)" beside 47 per-value calls and
  39 findings -- true of that path and false as a summary of the run.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from metascience_agent import agent, census, parallel

ROOT = pathlib.Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "benchmarks" / "paper_reviews" / "runs"


def _mcp_call(name, cid, inp=None, result=""):
    return ([{"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": cid, "name": agent._mcp(name),
                 "input": inp or {}}]}},
             {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": cid,
                 "content": [{"type": "text", "text": result}]}]}}])


class TestToolEventsReadsEitherSource:
    def test_messages_and_ledger_agree(self):
        msgs = _mcp_call("grim_check", "c1", {"mean": 3.5}, '{"severity":"suspicious"}')
        led = agent._tool_call_ledger(msgs, [])
        from_msgs = agent._tool_events(msgs, None)
        from_led = agent._tool_events(None, led)
        assert [e["short"] for e in from_msgs] == ["grim_check"]
        assert [e["short"] for e in from_led] == ["grim_check"]
        assert from_msgs[0]["result"] == from_led[0]["result"]
        assert from_msgs[0]["input"] == from_led[0]["input"] == {"mean": 3.5}

    def test_a_truncated_ledger_row_prefers_the_message(self):
        """`statcheck` is a bulk tool and its ledger copy is capped. The
        message still carries the whole payload, and the census counts rows
        out of it."""
        msgs = _mcp_call("statcheck", "c9", {}, '{"n_tests": 12}')
        led = agent._tool_call_ledger(msgs, [])
        led[0]["result"] = '{"n_tes'          # as a cap would leave it
        led[0]["result_truncated"] = True
        ev, = agent._tool_events(msgs, led)
        assert ev["result"] == '{"n_tests": 12}', (
            "a truncated ledger row must fall back to the message, or the "
            "census silently loses every batch row on a large paper")

    def test_the_ledger_supplies_the_canonical_name(self):
        """A backend that reports a display string is canonicalised in the
        ledger and not by `name.split('__')[-1]`."""
        msgs = [{"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "c2", "name": "Web search:", "input": {}}]}}]
        led = agent._tool_call_ledger(msgs, [])
        assert agent._tool_events(None, led)[0]["short"] == "WebSearch"


class TestTheCensusAgainstTheRealArchive:
    """The known positive. A census tested only on synthetic tables is the
    guard this repo keeps writing and then finding inert."""

    @pytest.mark.skipif(not (ARCHIVE / "airforce" / "paper").is_dir(),
                        reason="the airforce run is not in this checkout")
    def test_it_reproduces_the_legacy_denominator(self):
        """The model-free half must not change by being ported. The legacy run
        on this paper recorded 69 cells, 33 consumable, 29 routable, 4 blocked
        on declaration."""
        out = agent._checkable_coverage(ARCHIVE / "airforce" / "paper", None, [])
        assert out is not None
        assert (out["n_cells"], out["n_consumable"], out["n_routable"],
                out["blocked_on_declaration"]) == (69, 33, 29, 4)

    @pytest.mark.skipif(
        not (ARCHIVE / "wound_healing" / "forensic_review"
             / "toolcalls.tool_agent.json").is_file(),
        reason="the wound_healing run is not in this checkout")
    def test_the_numerator_survives_the_archive(self):
        """Computed from the LEDGER it is 19 of 57; computed from the archived
        MESSAGES it is 0, because their check_table results are empty. That
        difference is the reason `_tool_events` exists."""
        d = ARCHIVE / "wound_healing" / "forensic_review"
        led, msgs = [], []
        for label in ("tool_agent", "science_agent", "adjudicator"):
            lp, mp = d / f"toolcalls.{label}.json", d / f"messages.{label}.json"
            if lp.is_file():
                led += json.loads(lp.read_text())
            if mp.is_file():
                msgs += json.loads(mp.read_text())
        from_led = agent._checkable_coverage(ARCHIVE / "wound_healing" / "paper",
                                             None, led)
        assert from_led["n_checked"] > 0, (
            "the census read nothing from a ledger holding three check_table "
            "calls with full results")
        from_msgs = agent._checkable_coverage(ARCHIVE / "wound_healing" / "paper",
                                              msgs, None)
        assert from_msgs["n_checked"] == 0, (
            "if the slimmed archive ever regains its results this test is "
            "stale, not wrong -- re-measure before changing it")


class TestTheProseNamesEveryPopulation:
    """`direct_check_calls` was computed and the sentence a reader reads
    ignored it, so a run with 47 per-value calls was summarised as 0%."""

    def _note(self, **over):
        s = {"n_cells": 100, "n_consumable": 168, "n_checked": 0,
             "coverage": 0.0, "blocked_on_declaration": 0,
             "blocked_on_input": 0, "missing_inputs": {}}
        s.update(over)
        return census.render(s)

    def test_a_zero_fraction_beside_real_calls_says_so(self):
        note = self._note(direct_check_calls=47)
        assert "0 of 168" in note
        assert "47 per-value call(s)" in note
        assert "not left unchecked" in note

    def test_batch_rows_are_named_too(self):
        assert "37 row(s) through batch tools" in self._note(
            rows_checked_by_batch_tools=37)

    def test_they_are_never_summed_into_the_fraction(self):
        note = self._note(direct_check_calls=47, rows_checked_by_batch_tools=37)
        assert "0 of 168" in note, "the fraction must not absorb the other two"
        assert "without inventing a union" in note

    def test_a_run_with_no_other_calls_says_nothing_extra(self):
        assert "per-value call" not in self._note()


class TestTheWriterShipsIt:
    def _result(self, tmp_path, paper):
        return {"findings_v2": {"schema_version": "2.0", "findings": [],
                                "statistics_register": []},
                "run_meta": {"paper_id": "p", "version": "9.9.9"},
                "paper_path": str(paper), "limitations": []}

    @pytest.mark.skipif(not (ARCHIVE / "airforce" / "paper").is_dir(),
                        reason="the airforce run is not in this checkout")
    def test_the_census_is_inside_the_written_document(self, tmp_path):
        """Not beside it, and not after it. `run_meta.sandbox` was set AFTER
        run_meta.json was written and reached the in-memory dict and never the
        file, on 21 archived runs; this is the same hazard.

        THE PAPER IS COPIED FIRST, and that is not fussiness: the writer MOVES
        `analysis_code/` out of the paper directory into the run archive, so
        pointing it at the tracked corpus deletes fixture files. Caught on
        2026-09-03 when a suite run left three archived `analysis_code`
        scripts staged as deletions.
        """
        import shutil
        paper = tmp_path / "paper"
        shutil.copytree(ARCHIVE / "airforce" / "paper", paper,
                        ignore=shutil.ignore_patterns("analysis_code"))
        out = tmp_path / "rv"
        parallel.write_parallel_outputs(
            self._result(tmp_path, paper), out, render_pdf=False)
        doc = json.loads((out / "findings.v2.json").read_text())
        cs = doc.get("coverage_summary")
        assert cs, "the census did not reach the file"
        assert cs["checkable"]["n_consumable"] == 33

    def test_an_unreadable_paper_gets_a_named_absence(self, tmp_path):
        """A census that vanishes reads as a paper with nothing checkable.
        The blocks degrade honestly rather than raising, so the thing to pin
        is that `checkable` is PRESENT and says why it is empty."""
        res = self._result(tmp_path, tmp_path / "nonexistent")
        cs = parallel._build_coverage_summary(res, {}, res["findings_v2"])
        assert "checkable" in cs, "the block must not simply disappear"
        assert cs["checkable"].get("no_cells_examined") is True
        assert "not a count of zero" in cs["checkable"]["note"]
        assert cs["computation_audit"]["paper_readable"] is False, (
            "the audit must record that the paper could not be read")

    def test_no_paper_path_is_a_named_refusal(self):
        cs = parallel._build_coverage_summary({}, {}, {})
        assert "error" in cs and "paper_path" in cs["error"]


class TestTheModelCannotWriteIt:
    def test_the_document_declares_it_and_the_producer_schema_does_not(self):
        """Its entire value is that no model produced it."""
        from metascience_agent.core import prompts
        assert "coverage_summary" in prompts.findings_schema_v2()["properties"]
        for producer in ("tool_expert", "science_error"):
            assert "coverage_summary" not in prompts.producer_findings_schema(
                producer)["properties"]


class TestTheDispatchersRefusalsReachTheDocument:
    """`dispatch.check_table` writes a per-(cell, check) `not_run` record with
    a reader-grade reason, so that coverage does not depend on the model
    remembering what it skipped. On the parallel path nothing consumed it: a
    run that submitted three tables and had every cell inside them refused
    still read as "checked", because checked meant attempted.

    They merge into `unchecked`, which held the producers' own account only.
    The model's declaration and the dispatcher's refusals are the same kind of
    fact and belong in one list.
    """

    @staticmethod
    def _refusal_messages():
        payload = json.dumps({"results": [], "not_run": [
            {"cell": "r0", "tools": ["grim_check"],
             "reason": "no sample size was declared for this column"},
            {"cell": "r1", "tools": ["grim_check"],
             "reason": "no sample size was declared for this column"}]})
        return [{"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": "c1",
                     "name": agent._mcp("check_table"), "input": {"cells": []}}]}},
                {"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "c1",
                     "content": [{"type": "text", "text": payload}]}]}}]

    def test_a_refused_cell_reaches_unchecked(self, tmp_path):
        res = {"findings_v2": {"schema_version": "2.0", "findings": [],
                               "unchecked": []},
               "run_meta": {}, "paper_path": str(tmp_path), "limitations": [],
               "tool_agent": {"messages": self._refusal_messages(), "prompt": ""}}
        parallel.write_parallel_outputs(res, tmp_path / "rv", render_pdf=False)
        doc = json.loads((tmp_path / "rv" / "findings.v2.json").read_text())
        reasons = " ".join(str(u.get("reason")) for u in doc["unchecked"])
        assert "no sample size was declared" in reasons, (
            "the dispatcher's refusals did not reach the document; a table "
            "whose cells were all refused would read as checked")

    def test_the_producers_own_account_is_not_displaced(self, tmp_path):
        mine = {"location": "Table 3", "reason": "the model's own note"}
        res = {"findings_v2": {"schema_version": "2.0", "findings": [],
                               "unchecked": [mine]},
               "run_meta": {}, "paper_path": str(tmp_path), "limitations": [],
               "tool_agent": {"messages": self._refusal_messages(), "prompt": ""}}
        parallel.write_parallel_outputs(res, tmp_path / "rv", render_pdf=False)
        doc = json.loads((tmp_path / "rv" / "findings.v2.json").read_text())
        assert mine in doc["unchecked"], "the producer's own entry was lost"
        assert len(doc["unchecked"]) > 1, "the machine's entries did not merge"

    def test_refusals_are_read_from_messages_not_the_truncated_ledger(self):
        """`check_table` is a bulk tool whose ledger result is capped at 4,000
        chars, so refusals read from there would be cut off on exactly the
        tables big enough to matter."""
        import inspect
        wrapper = inspect.getsource(parallel.write_parallel_outputs)
        assert "_write_parallel_outputs_impl(" in wrapper
        src = inspect.getsource(parallel._write_parallel_outputs_impl)
        i = src.index("_machine_refusals")
        assert 'get("messages")' in src[i:i + 400], (
            "the refusal harvest must read raw messages, not the ledger")


class TestTheAnnotatorsReachDiskAndNotOnlyMemory:
    """SERIALISE-THEN-MUTATE, THE FOURTH TIME IN THIS WRITER.

    `severity_reconcile.annotate_v2` sat BELOW `_w("findings.v2.json", ...)`
    from v1.24.0 until 2026-09-04. It writes `severity_source` onto the
    findings -- of a document that had already been serialised -- so the field
    never reached disk. Every test still passed, because the SUMMARY it returns
    goes to `run_meta`, which is written later.

    Both annotators now sit immediately above the write, and these tests read
    the FILE rather than the in-memory dict, which is the only way this class
    of bug is visible at all.
    """

    @staticmethod
    def _res(tmp_path):
        # THROUGH MESSAGES, because `write_parallel_outputs` derives the
        # ledger with `_tool_call_ledger` -- a hand-built `toolcalls` key is
        # not read, and a fixture that supplied one would test nothing.
        args = {"mean": 3.5, "n": 30, "source_quote": "Age 3.5 (n=30)",
                "source_locator": "Table 1"}
        messages = [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "c1",
                 "name": agent._mcp("grim_check"), "input": args}]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "c1", "content": [
                    {"type": "text",
                     "text": json.dumps({"severity": "suspicious"})}]}]}},
        ]
        finding = {"finding_id": "f1", "technique": "grim", "severity": 7,
                   "title": "t", "detail": "d",
                   "tool_verdict": {"severity": "suspicious",
                                    "tool": "grim_check", "validated": True}}
        return {"findings_v2": {"schema_version": "2.0", "paper_id": "p",
                                "findings": [finding], "unchecked": []},
                "run_meta": {}, "paper_path": str(tmp_path), "limitations": [],
                "tool_agent": {"messages": messages, "prompt": ""}}

    def test_source_is_in_the_written_file(self, tmp_path):
        parallel.write_parallel_outputs(self._res(tmp_path), tmp_path / "rv",
                                        render_pdf=False)
        doc = json.loads((tmp_path / "rv" / "findings.v2.json").read_text())
        src = doc["findings"][0].get("source")
        assert src, ("`source` did not reach disk -- it is declared in the v2 "
                     "schema and listed as pipeline-written")
        assert src["source_quote"] == "Age 3.5 (n=30)"

    def test_severity_source_is_in_the_written_file(self, tmp_path):
        """The published rung (7) departs from the tool's `suspicious` (3), so
        a `severity_source` block is owed on this finding."""
        parallel.write_parallel_outputs(self._res(tmp_path), tmp_path / "rv",
                                        render_pdf=False)
        doc = json.loads((tmp_path / "rv" / "findings.v2.json").read_text())
        block = doc["findings"][0].get("severity_source")
        assert block, ("`severity_source` did not reach disk -- the annotator "
                       "ran after the document was serialised")
        assert block["tool_rung"] == 3 and block["model"] == 7
