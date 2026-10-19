"""mode="parallel": the failure matrix, end to end on faked stages.

The fakes stand where `_run_stage` stands; everything else -- row conversion,
id minting, docket build, apply(), skip paths, the writer -- is the real
code. The fake adjudicator reads the DOCKET it is handed and answers with
the finding_ids found there, so the join is exercised for real rather than
staged.
"""

import asyncio
import json
import pathlib
import re

import pytest

from metascience_agent import agent, parallel


def _doc(producer_rows, **top):
    d = {"schema_version": "1.0", "paper_id": "p", "findings": producer_rows,
         "coverage": {"stats_found": 1, "tools_run": ["grim_check"]},
         "anatomy": {"studies": [], "variables": [], "tests": []}}
    d.update(top)
    return d


def _row(slug, prov=4, **kw):
    r = {"slug": slug, "technique": "grim_check",
         "title": "a plain-language headline here",
         "description": "a plain-english description of what is wrong, "
                        "with the numbers inline",
         "location": "Table 2", "outcome": "problem",
         "provisional_severity": prov,
         "quote": "81.3% of participants reported full compliance"}
    r.update(kw)
    return r


def _stage(doc=None, *, is_error=False, cost=1.0, text=""):
    return {"structured_output": doc, "result": None, "text": text,
            "prompt": "PROMPT AS SENT", "messages": [], "cost_usd": cost,
            "input_tokens": 10, "output_tokens": 10,
            "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
            "return_code": 0, "is_error": is_error, "error_subtype": None,
            "wall_seconds": 1.0, "tool_calls": 0, "stop_reason": None,
            "num_turns": 1, "allowed_tools": []}


def _reader_call_messages():
    """One on-list forensic call (the paper read) and its result."""
    return [
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "read1",
             "name": agent._mcp("extract_pdf"), "input": {"pdf_path": "p.pdf"}}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "read1",
             "content": [{"type": "text", "text": "{\"text\": \"...\"}"}]}]}},
    ]


def _fake_adjudicator_output(docket_text):
    fids = re.findall(r'"finding_id": "(f_[0-9a-f]{16}(?:-\d+)?)"', docket_text)
    verdicts = [{"finding_id": fid, "action": "kept", "severity": 5,
                 "category": "none",
                 "rationale": "kept after reading the docket row"}
                for fid in dict.fromkeys(fids)]
    return {"verdicts": verdicts,
            "paper": {"verdict": "does_not_reconcile", "paper_severity": 5,
                      "confidence": "medium", "summary": "s" * 200,
                      "headline_finding_id": fids[0] if fids else "f_x"}}


@pytest.fixture()
def paper(tmp_path):
    (tmp_path / "body.md").write_text("The compliance rate was 81.3% of "
                                      "participants reported full compliance.")
    return tmp_path


@pytest.fixture()
def fakes(monkeypatch):
    """Route both stage entry points to canned payloads, per stage label."""
    state = {"tool": _stage(_doc([_row("t1")])),
             "science": _stage(_doc([_row("s1", technique="factual_claim",
                                          basis="model_knowledge")])),
             "adjudicator": "auto", "calls": []}

    async def fake_requiring(*, build_cmd, prompt, stage_label, **kw):
        # The real `_run_stage_requiring_forensic_tools` CALLS build_cmd; a
        # fake that does not diverges from production in ways that hide bugs
        # -- the system-prompt capture is one, since it happens there.
        build_cmd()
        state["calls"].append(stage_label)
        res = state["tool"]
        if isinstance(res, Exception):
            raise res
        if isinstance(res, dict) and res.get("messages") == [] \
                and not res.get("is_error"):
            # Every real tools-agent run reads the paper first; a fake with
            # an empty ledger is refused as a plumbing failure (the
            # forensic-tools gate in `AnalystModule.run`). A test that wants
            # ZERO calls installs its own `fake_requiring`.
            res = {**res, "messages": _reader_call_messages()}
        agent.record_spend(stage_label, res)
        return res

    async def fake_run_stage(cmd, prompt, *a, **kw):
        label = kw.get("stage_label") or (a[3] if len(a) > 3 else "?")
        state["calls"].append(label)
        if label == "science_agent":
            res = state["science"]
            if isinstance(res, Exception):
                raise res
            return res
        if label == "adjudicator":
            if state["adjudicator"] == "auto":
                return _stage(_fake_adjudicator_output(prompt))
            if isinstance(state["adjudicator"], Exception):
                raise state["adjudicator"]
            return state["adjudicator"]
        raise AssertionError(f"unexpected stage {label}")

    monkeypatch.setattr(agent, "_run_stage_requiring_forensic_tools",
                        fake_requiring)
    monkeypatch.setattr(agent, "_run_stage", fake_run_stage)
    monkeypatch.setattr(agent, "ensure_paper_extracted", lambda *a, **k: None)
    from metascience_agent import paper_metadata
    monkeypatch.setattr(paper_metadata, "record_for_run", lambda d: None)
    return state


def run(paper, **kw):
    return asyncio.run(agent.analyze_paper(
        str(paper), mode="parallel", image_forensics=False,
        text_forensics=False, **kw))


class TestAnalyzeCommand:
    """Exercise the actual verb, gates, pipeline and writer with fake LLMs."""

    def _invoke(self, paper, monkeypatch, *args):
        from typer.testing import CliRunner

        from metascience_agent.cli import app

        monkeypatch.setattr(agent, "ensure_paper_extracted",
                            lambda *a, **k: {"failed": []})
        return CliRunner().invoke(app, [
            "analyze", str(paper), "--backend", "claude", "--model", "opus",
            "--no-usage-guard", "--no-text-forensics", "--no-pdf",
            *args,
        ])

    def test_writes_an_adjudicated_review_and_viewer(self, paper, fakes, monkeypatch):
        from metascience_agent.cli import _analyze_out_dir

        result = self._invoke(paper, monkeypatch)
        assert result.exit_code == 0, (result.output, result.exception)
        assert "Viewer bundle failed" not in result.output
        out, _ = _analyze_out_dir(paper, None, "opus")
        doc = json.loads((out / "findings.v2.json").read_text())
        assert len(doc["findings"]) == 2
        assert all(f["finding_id"] and "severity" in f for f in doc["findings"])
        assert (out / "run_meta.json").is_file()
        assert (out / "report.md").is_file()
        assert list(paper.rglob("viewer.html")), "the default viewer was not delivered"

    def test_crash_record_uses_the_selected_review_directory(
            self, paper, fakes, monkeypatch, tmp_path):
        from metascience_agent.cli import _analyze_out_dir

        working = tmp_path / "working"
        working.mkdir()
        monkeypatch.chdir(working)

        async def crash(*args, **kwargs):
            agent.reset_spend()
            agent.record_spend("tool_agent", {"cost_usd": 1.25})
            raise RuntimeError("stage failed after billing")

        monkeypatch.setattr(agent, "analyze_paper", crash)
        result = self._invoke(paper, monkeypatch, "--no-bundle")
        assert isinstance(result.exception, RuntimeError)
        out, _ = _analyze_out_dir(paper, None, "opus")
        record = json.loads((out / "run_crash.json").read_text())
        assert record["total_cost_usd"] == 1.25
        assert "stage failed after billing" in record["error"]
        assert not (working / "run_crash.json").exists()

    def test_unwritable_crash_record_does_not_mask_the_stage_error(
            self, paper, fakes, monkeypatch):
        out = paper / "blocked-output"
        out.write_text("an existing file")

        async def crash(*args, **kwargs):
            raise RuntimeError("original stage failure")

        monkeypatch.setattr(agent, "analyze_paper", crash)
        result = self._invoke(paper, monkeypatch, "--output", str(out), "--no-bundle")
        assert isinstance(result.exception, RuntimeError), result.exception
        assert str(result.exception) == "original stage failure"
        assert "crash record could not be written" in result.output

    def test_unsupported_artefacts_are_refused_before_extraction(
            self, paper, fakes, monkeypatch):
        from typer.testing import CliRunner

        from metascience_agent.cli import app

        def must_not_extract(*args, **kwargs):
            pytest.fail("an unsupported input must be refused before work starts")

        monkeypatch.setattr(agent, "ensure_paper_extracted", must_not_extract)
        data = paper / "external-data.csv"
        data.write_text("x,y\n1,2\n")
        result = CliRunner().invoke(app, [
            "analyze", str(paper), "--artefact", str(data), "--no-usage-guard",
            "--backend", "claude",
        ])
        assert result.exit_code == 2, result.output
        assert "--artefact" in result.output and "--supplement" in result.output
        assert fakes["calls"] == []


class TestComputedBy:
    """`computed_by` is derived from the LEDGER, not from prose alone.

    Measured on the 2026-08-21 cerebrolysin run: the science agent ran two
    scripts, cited them loosely ("# compare against the roster script"),
    and every script-backed row was stamped model_reading because only the
    literal "analysis_code/" substring was tested."""

    def _script_call(self, label):
        return {"validated": False, "tool_short": "run_python_script",
                "input": {"label": label},
                "result": json.dumps({
                    "success": True,
                    "script_path": f"analysis_code/001_{label}.py",
                    "label": label})}

    def test_a_loose_script_citation_is_still_agent_code(self):
        ledger = [self._script_call("table4_roster_check")]
        rows = parallel._rows_from_producer(
            _doc([_row("s1", notes="computed by the table4_roster_check "
                                   "script; output captured")]),
            "science_error", ledger, "p")
        assert rows[0]["computed_by"] == "agent_code"

    def test_a_validated_tool_verdict_outranks_the_script(self):
        ledger = [
            self._script_call("table4_roster_check"),
            {"validated": True, "tool_short": "grim_check",
             "input": {"mean": 3.53, "n": 30},
             "result": json.dumps({"severity": "impossible"})},
        ]
        rows = parallel._rows_from_producer(
            _doc([_row("s1", inputs={"mean": 3.53, "n": 30},
                       notes="cross-checked with the table4_roster_check "
                             "script")]),
            "science_error", ledger, "p")
        assert rows[0]["computed_by"] == "registry_tool"
        assert rows[0]["impossible"] is True

    def test_no_citation_and_no_verdict_is_model_reading(self):
        rows = parallel._rows_from_producer(
            _doc([_row("s1")]), "science_error", [], "p")
        assert rows[0]["computed_by"] == "model_reading"


class TestHappyPath:
    def test_both_agents_merge_and_adjudicate(self, paper, fakes):
        res = run(paper)
        doc = res["findings_v2"]
        assert res["mode"] == "parallel" and res["is_error"] is False
        producers = {f["producer"] for f in doc["findings"]}
        assert producers == {"tool_expert", "science_error"}
        for f in doc["findings"]:
            assert f["finding_id"].startswith("f_")
            assert f["adjudication"]["action"] == "kept"
            assert f["severity_is_provisional"] is False
        assert doc["adjudication"]["ran"] is True
        assert doc["adjudication"]["verdict"] == "does_not_reconcile"
        assert doc["channels"]["tool_expert"]["state"] == "ran"
        # provisional clamps ran: model_knowledge basis caps at 3, so the
        # adjudicator's 5 stands only where legal -- science row was capped.
        sci = next(f for f in doc["findings"]
                   if f["producer"] == "science_error")
        assert sci["provisional_severity"] <= 3

    def test_outputs_are_written(self, paper, fakes, tmp_path):
        res = run(paper)
        out = tmp_path / "review"
        written = parallel.write_parallel_outputs(res, out)
        assert (out / "findings.v2.json").exists()
        assert (out / "report.md").exists()
        assert (out / "run_meta.json").exists()
        assert (out / "prompt.tool_agent.md").read_text() == "PROMPT AS SENT"
        body = json.loads((out / "findings.v2.json").read_text())
        assert body["schema_version"] == "2.0" and body["disclaimer"]
        # The value register runs on parallel output too (stacked-headers
        # merge follow-through) -- either the register or its named error
        # file must exist; silent absence is the failure mode.
        assert (out / "value_register.json").exists() \
            or (out / "value_register.error.txt").exists()

    def test_the_system_prompt_is_archived_beside_the_user_turn(self, paper,
                                                                fakes, tmp_path):
        """MEASURED 2026-08-22: `prompt.tool_agent.md` is 504 bytes -- the USER
        turn. The system prompt, which carries the rulebook, the severity
        ladder, the CLI map and every guard sentence, appeared in no artefact
        and in no transcript, so a finished review could not be audited for
        what instructed it and `_provenance`'s `prompt_sha256` had nothing to
        compare against."""
        res = run(paper)
        out = tmp_path / "review_sysprompt"
        parallel.write_parallel_outputs(res, out)
        for label in ("tool_agent", "science_agent", "adjudicator"):
            f = out / f"system_prompt.{label}.md"
            assert f.exists(), f"{label} system prompt was not archived"
            assert len(f.read_text()) > 1000, \
                f"{label}: that is the user turn, not the system prompt"
        # And it is the real thing, not a placeholder.
        assert "severity" in (out / "system_prompt.tool_agent.md").read_text().lower()

    def test_the_archived_system_prompt_is_the_one_that_was_sent(self, paper,
                                                                 fakes):
        """Captured where the command is built, not rebuilt by the writer: a
        rebuild is a second answer to "what was sent" and can drift."""
        from metascience_agent.core import prompts as _p
        res = run(paper)
        assert res["system_prompts"]["adjudicator"] == \
            _p.adjudication_system_prompt()

    def test_quote_verification_actually_runs(self, paper, fakes):
        """The annotator takes a RESULT dict wrapping the doc; handing it
        the doc directly crashed on every parallel run and shipped quotes
        unverified behind a swallowed exception (found via the failed
        2026-08-21 apple_cider eval gate)."""
        res = run(paper)
        assert "quote annotation failed; quotes ship unverified" \
            not in (res.get("limitations") or [])
        rows = [f for f in res["findings_v2"]["findings"]
                if f.get("quote")]
        assert rows, "fixture rows carry quotes"
        assert any("quote_verified" in f for f in rows), (
            "the quote pass writes verdicts onto the merged rows")

    def test_analysis_code_moves_into_the_archive(self, paper, fakes,
                                                  tmp_path):
        """The run's own scripts land in the archive FLAT, slug removed.

        `run_python_script` writes under `analysis_code/<run_slug>/`; the
        archive drops the slug so a finished review reads
        `analysis_code/001_check.py` exactly as it always did -- which is also
        what the tool reports as `script_path`."""
        res = run(paper)
        scripts = paper / "analysis_code" / res["run_slug"]
        scripts.mkdir(parents=True)
        (scripts / "001_check.py").write_text("print(1)")
        out = tmp_path / "review2"
        parallel.write_parallel_outputs(res, out)
        assert (out / "analysis_code" / "001_check.py").exists()
        assert not scripts.exists()
        # No empty `analysis_code/` left behind: a directory that exists and
        # holds nothing reads as "scripts ran and produced nothing".
        assert not (paper / "analysis_code").exists()

    def test_a_concurrent_run_keeps_its_own_scripts(self, paper, fakes,
                                                    tmp_path):
        """THE COLLISION THIS SCOPING EXISTS TO PREVENT.

        Two analyses of one paper directory -- a cross-backend comparison, or a
        re-run started before the first finished -- used to share one
        `analysis_code/`, and whichever finished first `shutil.move`d the whole
        thing into its own archive. The loser's `reproduction_kind: "script"`
        findings then named files filed under the other run's review."""
        res = run(paper)
        mine = paper / "analysis_code" / res["run_slug"]
        mine.mkdir(parents=True)
        (mine / "001_check.py").write_text("print('mine')")
        theirs = paper / "analysis_code" / "other-run-deadbeef"
        theirs.mkdir(parents=True)
        (theirs / "001_check.py").write_text("print('theirs')")

        parallel.write_parallel_outputs(res, tmp_path / "review3")

        assert (tmp_path / "review3" / "analysis_code"
                / "001_check.py").read_text() == "print('mine')"
        assert (theirs / "001_check.py").read_text() == "print('theirs')"
        # The shared parent survives precisely because it is not empty.
        assert (paper / "analysis_code").is_dir()

    def test_a_run_with_no_slug_still_archives_the_flat_directory(
            self, paper, fakes, tmp_path):
        """Legacy and hand-driven callers keep the old layout."""
        scripts = paper / "analysis_code"
        scripts.mkdir()
        (scripts / "001_check.py").write_text("print(1)")
        res = run(paper)
        res.pop("run_slug", None)
        parallel.write_parallel_outputs(res, tmp_path / "review4")
        assert (tmp_path / "review4" / "analysis_code"
                / "001_check.py").exists()
        assert not scripts.exists()


class TestFailureMatrix:
    def test_science_failure_keeps_the_survivor(self, paper, fakes):
        fakes["science"] = RuntimeError("rate limited")
        res = run(paper)
        assert res["is_error"] is True
        assert any("science_agent stage failed" in l
                   for l in res["limitations"])
        producers = {f["producer"] for f in res["findings_v2"]["findings"]}
        assert producers == {"tool_expert"}
        assert res["findings_v2"]["adjudication"]["ran"] is True

    def test_tool_failure_keeps_the_survivor(self, paper, fakes):
        fakes["tool"] = RuntimeError("ForensicToolsNeverRan")
        res = run(paper)
        assert res["is_error"] is True
        producers = {f["producer"] for f in res["findings_v2"]["findings"]}
        assert producers == {"science_error"}

    def test_both_failing_raises_stage_error(self, paper, fakes):
        fakes["tool"] = RuntimeError("dead")
        fakes["science"] = RuntimeError("dead too")
        with pytest.raises(agent.StageError):
            run(paper)

    def test_unparseable_adjudicator_fails_open(self, paper, fakes,
                                                monkeypatch):
        fakes["adjudicator"] = _stage(None, text="not json at all")

        async def no_repair(*a, **k):
            return None
        monkeypatch.setattr(agent, "_repair_json", no_repair)
        res = run(paper)
        doc = res["findings_v2"]
        assert doc["adjudication"]["ran"] is False
        for f in doc["findings"]:
            assert "adjudication" not in f
            assert f["severity_is_provisional"] is True

    def test_budget_floor_skips_adjudication_with_the_stamp(self, paper,
                                                            fakes):
        fakes["tool"] = _stage(_doc([_row("t1")]), cost=0.9)
        fakes["science"] = _stage(_doc([_row("s1")]), cost=0.05)
        res = run(paper, budget_usd=1.0)   # remainder 0.05 < 0.20 floor
        doc = res["findings_v2"]
        assert doc["adjudication"]["ran"] is False
        assert "budget below adjudication floor" in \
            doc["adjudication"]["skipped_reason"]
        assert any("provisional" in l for l in res["limitations"])


class TestEmptyReportRetry:
    """MEASURED 2026-08-21 (wound_healing on grok): a one-turn empty dump
    from the science agent and a 91-call sweep that filed ZERO rows both
    read as 'success', and a five-finding gold paper scored recall 0.0."""

    def test_a_dropped_report_is_retried_and_the_retry_used(self, paper,
                                                            monkeypatch,
                                                            fakes):
        calls = {"n": 0}
        empty = _doc([])
        full = _doc([_row("s1")])

        async def staged(cmd, prompt="", verbose=False, timeout=None,
                         on_progress=None, stage_label=""):
            calls["n"] += 1
            doc = empty if "retry" not in stage_label else full
            return _stage(doc)

        monkeypatch.setattr(agent, "_run_stage", staged)
        res = run(paper)
        assert any("EMPTY report" in l for l in res["limitations"])
        rows = res["findings_v2"]["findings"]
        assert any(f.get("slug") == "s1" for f in rows), \
            "the retry's rows must be the ones that ship"

    def test_a_doc_with_unchecked_entries_is_not_suspicious(self, paper,
                                                            monkeypatch,
                                                            fakes):
        honest = _doc([], unchecked=[{"what": "no tables", "why": "scan"}])

        async def staged(cmd, prompt="", verbose=False, timeout=None,
                         on_progress=None, stage_label=""):
            assert "retry" not in stage_label, \
                "an honest nothing-checkable doc must not be retried"
            return _stage(honest)

        monkeypatch.setattr(agent, "_run_stage", staged)
        res = run(paper)
        assert not any("EMPTY report" in l for l in res["limitations"])


class TestTruncatedDocketRetry:
    """MEASURED 2026-08-22, 10.1177--0956797614564191 on grok-4.6. The tool
    agent made 56 calls; its structured output then degenerated mid-array
    (backticks for quotes) and it closed the findings list after ONE row with
    `"coverage":{"stats_found":0,"tools_run":[]}`. 55 of 56 tool results were
    discarded -- including a statcheck run that had found two real
    inconsistencies -- while `is_error` was false, `output_parse_path` was
    "json_schema" and `limitations` was EMPTY. One surviving finding was enough
    to satisfy the not-empty test, so nothing downstream could see it."""

    @staticmethod
    def _busy_messages(n=12):
        out = []
        for i in range(n):
            tid = f"toolu_{i}"
            out.append({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": tid,
                 "name": agent._mcp("grim_check"), "input": {}}]}})
            out.append({"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": tid,
                 "content": [{"type": "text", "text": "{}"}]}]}})
        return out

    def test_a_truncated_tool_docket_is_retried(self, paper, monkeypatch,
                                                fakes):
        stub = _doc([_row("t1")], coverage={"stats_found": 0, "tools_run": []})
        full = _doc([_row("t2"), _row("t3")])

        async def fake_requiring(*, build_cmd, prompt, stage_label, **kw):
            res = _stage(stub)
            res["messages"] = self._busy_messages()
            agent.record_spend(stage_label, res)
            return res

        inner = agent._run_stage

        async def fake_run_stage(cmd, prompt, *a, **kw):
            if (kw.get("stage_label") or "") == "tool_agent_retry":
                res = _stage(full)
                res["messages"] = self._busy_messages()
                return res
            return await inner(cmd, prompt, *a, **kw)

        monkeypatch.setattr(agent, "_run_stage_requiring_forensic_tools",
                            fake_requiring)
        monkeypatch.setattr(agent, "_run_stage", fake_run_stage)
        res = run(paper)
        assert any("TRUNCATED report" in l for l in res["limitations"]),             res["limitations"]
        slugs = {f.get("slug") for f in res["findings_v2"]["findings"]}
        assert "t2" in slugs, "the retry's rows must be the ones that ship"

    def test_an_honest_docket_with_tools_recorded_is_not_retried(
            self, paper, monkeypatch, fakes):
        """The gate keys on `tools_run` being EMPTY beside a busy ledger. A
        docket that names the tools it used is a report, not a casualty."""
        async def fake_requiring(*, build_cmd, prompt, stage_label, **kw):
            assert "retry" not in stage_label,                 "a docket that records its tools must not be retried"
            res = _stage(_doc([_row("t1")]))
            res["messages"] = self._busy_messages()
            agent.record_spend(stage_label, res)
            return res

        monkeypatch.setattr(agent, "_run_stage_requiring_forensic_tools",
                            fake_requiring)
        res = run(paper)
        assert not any("TRUNCATED" in l for l in res["limitations"])

    def test_a_quiet_ledger_does_not_trigger_the_truncation_gate(
            self, paper, monkeypatch, fakes):
        """Empty `tools_run` beside an EMPTY ledger is an agent that did no
        forensic work, which the pre-existing empty-report gate already owns.
        Only a busy ledger says results were computed and then lost."""
        stub = _doc([_row("t1")], coverage={"stats_found": 0, "tools_run": []})

        async def fake_requiring(*, build_cmd, prompt, stage_label, **kw):
            assert "retry" not in stage_label
            res = _stage(stub)
            res["messages"] = []
            agent.record_spend(stage_label, res)
            return res

        monkeypatch.setattr(agent, "_run_stage_requiring_forensic_tools",
                            fake_requiring)
        res = run(paper)
        assert not any("TRUNCATED" in l for l in res["limitations"])


class TestTranscriptSalvage:
    """MEASURED 2026-08-22 (neulet on grok): the science agent did 22 tool
    calls and 13 web searches, NARRATED its findings in its final turns,
    then errored at error_max_structured_output_retries -- $0.32 of real
    work lost while the findings sat in the transcript."""

    NARRATION = ("Finding 1: the sham bars in Figure 2 are labelled "
                 "fold-of-sham yet none of the sham bars equals 1.0, "
                 "which contradicts the normalization the caption states. "
                 "Finding 2: the Discussion claims CREB phosphorylation "
                 "rose while Results report no significant change. "
                 "These are the findings I would have filed as JSON.")

    def _msgs(self):
        return [
            {"message": {"role": "assistant", "content": [
                {"type": "thinking", "thinking": "private reasoning"},
                {"type": "text", "text": "Calling one more tool."}]}},
            {"message": {"role": "user", "content": [
                {"type": "tool_result", "content": "ok"}]}},
            {"message": {"role": "assistant", "content": [
                {"type": "text", "text": self.NARRATION}]}},
        ]

    def test_final_assistant_texts_collects_narration_not_thinking(self):
        got = parallel._final_assistant_texts(self._msgs())
        assert self.NARRATION in got
        assert "private reasoning" not in got

    def test_short_transcripts_are_not_salvage(self):
        msgs = [{"message": {"role": "assistant",
                             "content": [{"type": "text", "text": "done"}]}}]
        assert parallel._final_assistant_texts(msgs) == ""

    def test_looks_empty_doc(self):
        assert parallel._looks_empty_doc(
            json.dumps({"findings": [], "unchecked": []}))
        assert not parallel._looks_empty_doc(
            json.dumps({"findings": [{"slug": "x"}]}))
        assert not parallel._looks_empty_doc("not json at all")

    def test_schema_failure_salvages_the_transcript(self, paper, monkeypatch,
                                                    fakes):
        broken = _stage(None, is_error=True)
        broken["error_subtype"] = "error_max_structured_output_retries"
        broken["messages"] = self._msgs()
        fakes["science"] = broken
        seen = {}

        async def fake_repair(raw, schema, model, verbose, timeout,
                              effort="medium", backend=None):
            seen["raw"] = raw
            return _doc([_row("salvaged", technique="internal_contradiction",
                              basis=None)])

        monkeypatch.setattr(agent, "_repair_json", fake_repair)
        res = run(paper)
        assert "fold-of-sham" in seen["raw"], \
            "the repair pass must see the narrated findings, not the envelope"
        assert any(f.get("slug") == "salvaged"
                   for f in res["findings_v2"]["findings"])


class TestPlaceholderThenFinalDocument:
    """MEASURED 2026-10-11 (schnall2008, grok-4.6): the science agent wrote an
    empty placeholder document beside each of seven tool calls, then its real
    seven-finding document last. The Grok CLI joined them, could not parse
    the result and ended at error_max_structured_output_retries; the run
    called the stream DEGENERATED and the channel `refused`, beside seven of
    that analyst's findings."""

    PLACEHOLDER = json.dumps({"schema_version": "2.0", "paper_id": "p",
                              "findings": []})

    def _stage(self, *texts):
        st = _stage(None, is_error=True, text="\n".join(texts))
        st["error_subtype"] = "error_max_structured_output_retries"
        st["messages"] = [{"type": "assistant", "message": {
            "role": "assistant", "content": [{"type": "text", "text": t}]}}
            for t in texts]
        return st

    def _final(self):
        return json.dumps(_doc([_row("s_final", technique="factual_claim",
                                     basis="model_knowledge")]))

    def test_the_final_document_is_the_answer_and_the_stage_did_not_fail(
            self, paper, fakes):
        fakes["science"] = self._stage(*[self.PLACEHOLDER] * 3, self._final())
        res = run(paper)
        meta = res["run_meta"]["stages"]["science_agent"]
        assert meta["output_parse_path"] == "final_after_placeholders"
        assert meta["is_error"] is False and meta["error_subtype"] is None
        assert meta["cli_error_subtype"] == "error_max_structured_output_retries"
        assert not any("DEGENERATED" in l for l in res["limitations"])
        assert res["findings_v2"]["channels"]["science_error"]["state"] == "ran"
        assert any(f.get("slug") == "s_final"
                   for f in res["findings_v2"]["findings"])

    def test_narration_is_not_this_shape_and_keeps_the_warning(self, paper,
                                                               fakes):
        fakes["science"] = self._stage(self.PLACEHOLDER, "Let me check one "
                                       "more reference first.", self._final())
        res = run(paper)
        meta = res["run_meta"]["stages"]["science_agent"]
        assert meta["output_parse_path"] == "salvaged_object"
        assert meta["is_error"] is True
        assert any("DEGENERATED" in l for l in res["limitations"])
        # ...but its findings ARE in the document, so not `refused`.
        ch = res["findings_v2"]["channels"]["science_error"]
        assert ch["state"] == "ran" and "recovered (salvaged_object)" in ch["detail"]

    def test_an_earlier_document_with_findings_is_not_a_placeholder(self):
        earlier = json.dumps(_doc([_row("early")]))
        msgs = self._stage(earlier, self._final())["messages"]
        assert parallel._final_after_placeholders(msgs) is None

    def test_all_placeholders_is_not_a_recovery(self):
        msgs = self._stage(self.PLACEHOLDER, self.PLACEHOLDER)["messages"]
        assert parallel._final_after_placeholders(msgs) is None


class TestUnreportedCost:
    def test_a_stage_with_no_reported_cost_is_named_in_run_meta(self, paper,
                                                                fakes):
        fakes["tool"]["cost_reported"] = False
        res = run(paper)
        assert res["run_meta"]["cost_unreported_stages"] == ["tool_agent"]
        assert res["run_meta"]["stages"]["tool_agent"]["cost_reported"] is False

    def test_reported_costs_add_no_key(self, paper, fakes):
        res = run(paper)
        assert "cost_unreported_stages" not in res["run_meta"]


class TestSchemaGateRetry:
    """The errored-at-schema-gate variant of the empty-report guard: salvage
    found nothing, the stage is lost -- one bounded retry, billed."""

    def test_schema_gate_error_triggers_the_retry(self, paper, monkeypatch,
                                                  fakes):
        broken = _stage(None, is_error=True)
        broken["error_subtype"] = "error_max_structured_output_retries"
        fakes["science"] = broken
        full = _doc([_row("recovered")])
        labels = []

        async def staged(cmd, prompt="", verbose=False, timeout=None,
                         on_progress=None, stage_label=""):
            labels.append(stage_label)
            if stage_label == "science_agent":
                return broken
            if "retry" in stage_label:
                return _stage(full)
            return _stage(_fake_adjudicator_output(prompt))

        monkeypatch.setattr(agent, "_run_stage", staged)
        res = run(paper)
        assert any("science_agent_retry" == l for l in labels)
        assert any("ERRORED at the structured-output gate" in l
                   for l in res["limitations"])
        assert any(f.get("slug") == "recovered"
                   for f in res["findings_v2"]["findings"])

    def test_a_timeout_is_not_retried_by_this_guard(self, paper, monkeypatch,
                                                    fakes):
        timed = _stage(None, is_error=True)
        timed["error_subtype"] = "error_timeout"
        fakes["science"] = timed

        async def staged(cmd, prompt="", verbose=False, timeout=None,
                         on_progress=None, stage_label=""):
            assert "retry" not in stage_label, \
                "a timeout must not be doubled by the schema-gate guard"
            if stage_label == "science_agent":
                return timed
            return _stage(_fake_adjudicator_output(prompt))

        monkeypatch.setattr(agent, "_run_stage", staged)
        res = run(paper)
        assert not any("structured-output gate" in l
                       for l in res["limitations"])


class TestUnsourcedLookupLedgerContext:
    """The adjudicator judging an unsourced web_lookup row needs to see what
    the agent's ledger shows it VISITED -- without the pipeline fabricating
    a citation into web_sources (that field stays the model's attestation)."""

    def _science_row(self, **kw):
        r = _row("ba1400", technique="factual_claim", basis="web_lookup",
                 web_sources=[])
        r.update(kw)
        return r

    def test_visited_urls_attach_to_the_unsourced_row(self):
        ledger = [
            {"tool_short": "WebFetch",
             "input": {"url": "https://vectorlabs.com/ba-1400"}},
            {"tool_short": "WebSearch",
             "input": {"query": "Vector BA-1400 reactivity"}},
            {"tool_short": "grim_check", "input": {"mean": 1.0}},
        ]
        rows = parallel._rows_from_producer(
            _doc([self._science_row()]), "science_error", ledger, "p")
        assert rows[0]["web_unbacked"] == "no_recorded_source"
        assert rows[0]["ledger_web_context"] == [
            "https://vectorlabs.com/ba-1400", "Vector BA-1400 reactivity"]

    def test_web_sources_are_never_fabricated(self):
        ledger = [{"tool_short": "WebFetch", "input": {"url": "https://x"}}]
        rows = parallel._rows_from_producer(
            _doc([self._science_row()]), "science_error", ledger, "p")
        assert rows[0]["web_sources"] == []

    def test_a_sourced_row_gets_no_context_attachment(self):
        ledger = [{"tool_short": "WebFetch", "input": {"url": "https://x"}}]
        rows = parallel._rows_from_producer(
            _doc([self._science_row(
                web_sources=[{"url": "https://x", "quote": "q"}])]),
            "science_error", ledger, "p")
        assert "web_unbacked" not in rows[0]
        assert "ledger_web_context" not in rows[0]


class TestStubPdfLimitation:
    def test_a_preview_stub_main_pdf_is_a_named_limitation(self, paper,
                                                           monkeypatch,
                                                           fakes):
        from metascience_agent import webapp_index as W
        monkeypatch.setattr(W, "probe_main_pdf_stub",
                            lambda *a, **k: {"main_pdf_pages": 1,
                                             "pdf_suspect_stub": True})
        res = run(paper)
        assert any("preview STUB" in l for l in res["limitations"]), \
            "a figure-blind run must say so in its own report"

    def test_a_full_pdf_adds_no_limitation(self, paper, monkeypatch, fakes):
        from metascience_agent import webapp_index as W
        monkeypatch.setattr(W, "probe_main_pdf_stub",
                            lambda *a, **k: {"main_pdf_pages": 9})
        res = run(paper)
        assert not any("preview STUB" in l for l in res["limitations"])


class TestMissingSupplementLimitation:
    """Since 2026-10-18 a paper citing an absent supplement runs instead of
    being refused, so its own report must say what was missing."""

    def test_a_cited_absent_supplement_is_a_named_limitation(self, paper,
                                                            monkeypatch, fakes):
        from metascience_agent import supplements
        monkeypatch.setattr(supplements, "audit", lambda *a, **k: {
            "missing": True, "styles": {"eTable / eFigure (JAMA)": ["eTable 3"]}})
        res = run(paper)
        assert any("eTable 3" in line and "not available to this review" in line
                   for line in res["limitations"])

    def test_a_complete_paper_adds_no_such_limitation(self, paper, monkeypatch,
                                                      fakes):
        from metascience_agent import supplements
        monkeypatch.setattr(supplements, "audit", lambda *a, **k: {"missing": False})
        res = run(paper)
        assert not any("not available to this review" in line
                       for line in res["limitations"])


class TestATimedOutStageIsACoverageFact:
    """Until 2026-09-02 a stage killed by the per-stage timeout with no
    findings reached the report as "produced no parseable findings JSON" --
    a sentence about the model, over what was a fact about coverage. The
    budget branch beside it has said BUDGET-TRUNCATED since v1.0.0."""

    def test_the_limitation_names_the_timeout(self, paper, fakes):
        cut = _stage(None, is_error=True)
        cut["error_subtype"] = "error_timeout"
        fakes["tool"] = cut
        res = run(paper)
        lims = res["limitations"]
        assert any("CUT OFF by the per-stage timeout" in l for l in lims), lims
        assert not any("no parseable findings JSON" in l
                       and "tool_agent" in l for l in lims), lims
        assert res["run_meta"]["stages"]["tool_agent"]["truncated_by_timeout"] is True

    def test_a_budget_cut_still_says_budget(self, paper, fakes):
        cut = _stage(None, is_error=True)
        cut["error_subtype"] = "error_max_budget_usd"
        fakes["tool"] = cut
        res = run(paper)
        assert any("BUDGET-TRUNCATED" in l for l in res["limitations"])
        assert not any("per-stage timeout" in l for l in res["limitations"])


class TestTheRetryRecoversTheWorkInsteadOfRedoingIt:
    """MEASURED 2026-09-03 on `wound_healing` (grok-4.6, v1.15.0).

    The tool expert made 90 calls, began writing its report, degenerated into
    `n.n.n.n.n…` mid-document and recovered by filing ONE finding. Its ledger
    held 78 forensic results -- 1 `highly_suspicious`, 13 `suspicious`, 12
    `indeterminate`, 48 `consistent`. The bounded retry re-ran the whole stage
    from scratch, came back empty, and all 78 were discarded.

    Re-deriving what is already recorded is the expensive way to fail twice.
    """

    @staticmethod
    def _busy(n=12, tool="grim_check", result='{"severity": "suspicious"}'):
        out = []
        for i in range(n):
            tid = f"toolu_{i}"
            out.append({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": tid,
                 "name": agent._mcp(tool), "input": {"mean": 3.5}}]}})
            out.append({"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": tid,
                 "content": [{"type": "text", "text": result}]}]}})
        return out

    def _drive(self, paper, monkeypatch, first_messages, retry_doc,
               retry_messages=None, stub=None):
        """Run the pipeline with a truncated first tool docket. Returns the
        (cmd, prompt) the retry was invoked with."""
        seen = {}
        if stub is None:
            stub = _doc([_row("t1")],
                        coverage={"stats_found": 0, "tools_run": []})

        async def fake_requiring(*, build_cmd, prompt, stage_label, **kw):
            res = _stage(stub)
            res["messages"] = first_messages
            agent.record_spend(stage_label, res)
            return res

        inner = agent._run_stage

        async def fake_run_stage(cmd, prompt, *a, **kw):
            if (kw.get("stage_label") or "") == "tool_agent_retry":
                seen["cmd"], seen["prompt"] = cmd, prompt
                res = _stage(retry_doc)
                res["messages"] = retry_messages or []
                return res
            return await inner(cmd, prompt, *a, **kw)

        monkeypatch.setattr(agent, "_run_stage_requiring_forensic_tools",
                            fake_requiring)
        monkeypatch.setattr(agent, "_run_stage", fake_run_stage)
        res = run(paper)
        return seen, res

    def test_a_busy_ledger_is_recovered_not_re_derived(self, paper, monkeypatch,
                                                       fakes):
        seen, _ = self._drive(paper, monkeypatch, self._busy(),
                              _doc([_row("t2")]))
        assert "prompt" in seen, "the retry never ran"
        p = seen["prompt"]
        assert "YOUR TOOL LEDGER" in p, "the retry was not given its own ledger"
        assert "grim_check" in p, "the ledger's calls are not in the prompt"
        assert "severity" in p, "the ledger's RESULTS are not in the prompt"
        assert "there are none available" in p, (
            "the recovery turn must forbid tool use; re-running the work is "
            "what this replaces")

    def test_the_recovery_turn_carries_no_forensic_tools(self, paper,
                                                         monkeypatch, fakes):
        seen, _ = self._drive(paper, monkeypatch, self._busy(),
                              _doc([_row("t2")]))
        allowed = list(getattr(seen["cmd"], "allowed_tools", []) or [])
        forensic = [t for t in allowed if agent.MCP_TOOL_PREFIX in t]
        assert not forensic, (
            f"the recovery turn was handed forensic tools {forensic[:3]}; it "
            "must serialize what the ledger already holds, not run more checks")

    def test_an_empty_ledger_still_re_runs_the_whole_stage(self, paper,
                                                          monkeypatch, fakes):
        """Nothing on the ledger means nothing to recover FROM, so the old
        full re-run is still the right response.

        The signature that reaches the retry with an empty ledger is the
        EMPTY docket, not the truncated one: `truncated_docket` requires
        >= 8 forensic calls, so a 1-finding doc beside a silent ledger
        returns before any retry (pre-existing, and correct).
        """
        seen, _ = self._drive(paper, monkeypatch, [], _doc([_row("t2")]),
                              stub=_doc([]))
        assert "prompt" in seen, "the retry never ran"
        assert "YOUR TOOL LEDGER" not in seen["prompt"]
        assert "RETRY -- your previous report was not usable" in seen["prompt"]

    def test_the_recovered_rows_are_the_ones_that_ship(self, paper, monkeypatch,
                                                       fakes):
        _, res = self._drive(paper, monkeypatch, self._busy(),
                             _doc([_row("t2"), _row("t3")]))
        slugs = {f.get("slug") for f in res["findings_v2"]["findings"]}
        assert "t2" in slugs and "t3" in slugs, slugs


class TestAStageThatNeverCalledAToolIsARefusal:
    """MEASURED 2026-09-03 on `airforce` (grok-4.6): the tool expert took one
    turn, 36,169 input tokens, 184 output tokens, ZERO tool calls, `end_turn`
    in 7.4 s. It emitted a schema-valid EMPTY document and stopped; the retry
    did the same. Downstream, an empty-but-valid document from a stage that
    ran no check is indistinguishable from a paper with nothing wrong."""

    def _drive(self, paper, monkeypatch):
        empty = _doc([])

        async def fake_requiring(*, build_cmd, prompt, stage_label, **kw):
            res = _stage(empty)
            res["messages"] = []          # zero tool calls, as measured
            agent.record_spend(stage_label, res)
            return res

        inner = agent._run_stage

        async def fake_run_stage(cmd, prompt, *a, **kw):
            if (kw.get("stage_label") or "") == "tool_agent_retry":
                res = _stage(empty)
                res["messages"] = []      # the retry did the same
                return res
            return await inner(cmd, prompt, *a, **kw)

        monkeypatch.setattr(agent, "_run_stage_requiring_forensic_tools",
                            fake_requiring)
        monkeypatch.setattr(agent, "_run_stage", fake_run_stage)
        return run(paper)

    def test_it_is_named_a_refusal_not_a_clean_result(self, paper, monkeypatch,
                                                      fakes):
        res = self._drive(paper, monkeypatch)
        lim = " ".join(res["limitations"])
        assert "NO forensic tool calls" in lim, res["limitations"]
        assert "did not examine the paper" in lim, res["limitations"]
        assert "OUR failure" in lim, (
            "the limitation must say whose failure this is; a silent stage "
            "reads as a clean paper otherwise")

    def test_the_stage_carries_its_own_error_subtype(self, paper, monkeypatch,
                                                     fakes):
        res = self._drive(paper, monkeypatch)
        st = res["run_meta"]["stages"]["tool_agent"]
        assert st["error_subtype"] == "no_forensic_calls"
        assert st["is_error"] is True

    def test_it_is_not_mistaken_for_a_budget_or_timeout_cut(self, paper,
                                                            monkeypatch, fakes):
        """`_stage_hit_budget` / `_stage_hit_timeout` both key on is_error plus
        a subtype; a new subtype only half the predicates know about is the
        guard-that-stops-guarding failure agent.py warns about."""
        res = self._drive(paper, monkeypatch)
        st = res["run_meta"]["stages"]["tool_agent"]
        assert st["truncated_by_budget"] is False
        assert st["truncated_by_timeout"] is False

    def test_nothing_from_it_is_merged(self, paper, monkeypatch, fakes):
        res = self._drive(paper, monkeypatch)
        producers = {f.get("producer") for f in res["findings_v2"]["findings"]}
        assert "tool_expert" not in producers, (
            "a stage that examined nothing must contribute nothing")


class TestTheDigestAgainstTheRealArchive:
    """The known positive. A digest builder tested only on synthetic rows is
    the guard this repo keeps writing and then finding inert."""

    LEDGER = pathlib.Path(__file__).resolve().parents[1] / (
        "benchmarks/paper_reviews/runs/wound_healing/forensic_review/toolcalls.tool_agent.json")

    @pytest.mark.skipif(not LEDGER.is_file(),
                        reason="the wound_healing run is not in this checkout")
    def test_the_measured_run_yields_a_usable_digest(self):
        from metascience_agent import parallel as P
        rows = json.loads(self.LEDGER.read_text())
        d = P._ledger_digest(rows if isinstance(rows, list) else [])
        n = d.count("### call ")
        assert n >= 20, f"only {n} calls reached the digest of a 78-call ledger"
        assert "highly_suspicious" in d, (
            "the one highly_suspicious result in the measured ledger did not "
            "survive into the digest -- that is the finding this recovers")
        assert len(d) <= P._LEDGER_DIGEST_CHARS + 2000


class TestWhatCountsAsWorkIsPerProducer:
    """`agent_code` is never validated evidence, but for the science-error
    analyst it IS the work.

    v1.21.0 implemented `docs/specs/pipeline.md §9`: `run_python_script`
    moved off the `forensic_mcp` surface (where all six archived calls had
    been filed `validated: True`) onto `agent_code`, `validated: False`. That
    reclassification collides with the `no_forensic_calls` refusal shipped the
    same day unless "did this stage do work" is asked per producer: the
    science agent reasons through sandboxed scripts and the literature and is
    not on the forensic allowlist for most of what it does, so counting only
    `forensic_mcp` would refuse an analyst that had done everything asked.
    """

    @staticmethod
    def _script_messages(n=3):
        out = []
        for i in range(n):
            tid = f"py_{i}"
            out.append({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": tid,
                 "name": agent._mcp("run_python_script"),
                 "input": {"script": "print(1)"}}]}})
            out.append({"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": tid,
                 "content": [{"type": "text", "text": "1"}]}]}})
        return out

    def test_a_science_agent_working_only_through_python_is_not_refused(
            self, paper, fakes, monkeypatch):
        empty = _stage(_doc([]))
        empty["messages"] = self._script_messages()
        fakes["science"] = empty
        inner = agent._run_stage

        async def fake_run_stage(cmd, prompt, *a, **kw):
            if (kw.get("stage_label") or "") == "science_agent_retry":
                res = _stage(_doc([_row("s9", technique="factual_claim",
                                        basis="model_knowledge")]))
                res["messages"] = self._script_messages()
                return res
            return await inner(cmd, prompt, *a, **kw)

        monkeypatch.setattr(agent, "_run_stage", fake_run_stage)
        res = run(paper)
        lim = " ".join(res["limitations"])
        assert "NO forensic tool calls" not in lim, (
            "the science agent's scripts ARE its work; refusing it here would "
            "throw away an analyst that did everything asked")
        st = res["run_meta"]["stages"]["science_agent"]
        assert st.get("error_subtype") != "no_forensic_calls"

    def test_the_scripts_are_still_never_validated_evidence(self):
        led = agent._tool_call_ledger(self._script_messages(1), [])
        assert [r["surface"] for r in led] == ["agent_code"]
        assert all(r["validated"] is False for r in led)

    def test_a_tool_expert_with_only_scripts_is_still_refused(self, paper,
                                                              fakes, monkeypatch):
        """The tool expert has no such excuse: the validated toolkit is its
        whole job, so `agent_code` does not count as work for it."""
        from metascience_agent import parallel as P
        assert P._n_work_calls(
            agent._tool_call_ledger(self._script_messages(4), []),
            "tool_expert") == 0
        assert P._n_work_calls(
            agent._tool_call_ledger(self._script_messages(4), []),
            "science_error") == 4


@pytest.mark.usefixtures("image_package")
@pytest.mark.parametrize("image_outcome", ["completed", "incomplete", "failed", "disabled"])
def test_independent_images_overlap_analysts_and_reach_report(
        paper, fakes, monkeypatch, image_outcome):
    from metascience_observatory_image_analysis.image_forensics import pipeline, screening
    from tests.test_image_review import _group, _paper
    from tests.test_image_pipeline import detection_record
    _paper(paper.parent, paper.name, [_group()])
    detector_result = json.loads((paper / "image_duplication_findings.json").read_text())

    async def exercise():
        screened = asyncio.Event()
        tool_started, science_started = asyncio.Event(), asyncio.Event()
        tool_call = agent._run_stage_requiring_forensic_tools
        stage_call = agent._run_stage
        async def tool(**kwargs):
            tool_started.set()
            if image_outcome != "disabled":
                await asyncio.wait_for(screened.wait(), 3)
            return await tool_call(**kwargs)
        async def stage(*args, **kwargs):
            if kwargs.get("stage_label") == "science_agent":
                science_started.set()
                if image_outcome != "disabled":
                    await asyncio.wait_for(screened.wait(), 3)
            if kwargs.get("stage_label") == "adjudicator" and image_outcome == "completed":
                assert "image_track" in args[1], "screened image row never reached the docket"
            return await stage_call(*args, **kwargs)
        async def detect(*args, **kwargs):
            assert image_outcome != "disabled", "opt-out still launched images"
            await asyncio.wait_for(tool_started.wait(), 3)
            await asyncio.wait_for(science_started.wait(), 3)
            rec = detection_record()
            rec["output"]["result"] = detector_result
            if image_outcome == "failed":
                rec.update(ran=False, is_error=True, detail="detector crashed")
                screened.set()
            return rec
        async def judge(*args, **kwargs):
            assert image_outcome != "disabled"
            screened.set()
            if image_outcome == "incomplete":
                return {"decision": "unresolved", "confidence": "low", "validated": False}
            return {"decision": "issue", "confidence": "high", "validated": True,
                    "explanation": "Matching experimental content across different treatments."}
        monkeypatch.setattr(agent, "_run_stage_requiring_forensic_tools", tool)
        monkeypatch.setattr(agent, "_run_stage", stage)
        monkeypatch.setattr(pipeline, "run_detection", detect)
        monkeypatch.setattr(screening, "judge", judge)
        opts = {"image_forensics": False} if image_outcome == "disabled" else {}
        return await agent.analyze_paper(str(paper), text_forensics=False, **opts)

    result = asyncio.run(exercise())
    assert not result["is_error"], "image problems discarded successful analyst results"
    assert result["run_meta"]["stages"]["image_forensics"]["execution_status"] == image_outcome
    rows = result["findings_v2"]["findings"]
    assert any(r["producer"] == "tool_expert" for r in rows)
    assert any(r["producer"] == "science_error" for r in rows)
    assert any(r["producer"] == "image_track" for r in rows) == (image_outcome == "completed")
    out = paper / "review-images"
    parallel.write_parallel_outputs(result, out, render_pdf=False)
    rendered = (out / "report.md").read_text()
    assert image_outcome in rendered
    assert "no figure content was read" not in rendered
    if image_outcome == "incomplete":
        assert "1 of 1" in rendered and "unpublished" in rendered
    if image_outcome == "completed":
        assert "1 publishable finding(s)" in rendered


@pytest.mark.usefixtures("image_package")
def test_full_run_cancellation_awaits_image_cleanup(paper, fakes, monkeypatch):
    from metascience_observatory_image_analysis.image_forensics import pipeline
    async def exercise():
        started, cleaned = asyncio.Event(), asyncio.Event()
        async def images(*args, **kwargs):
            started.set()
            try:
                await asyncio.Future()
            finally:
                await asyncio.sleep(0)
                cleaned.set()
        monkeypatch.setattr(pipeline, "run", images)
        task = asyncio.create_task(agent.analyze_paper(str(paper), text_forensics=False))
        await asyncio.wait_for(started.wait(), 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cleaned.is_set()
    asyncio.run(exercise())


class TestTheReportUsesTheArchiveTheRunStartedIn:
    """MEASURED 2026-10-13: the image track writes `.image_track/` into the
    paper's parent directory mid-run. The report writers re-resolved the
    archive by marker at report time, landed on that new empty directory and
    raised `unknown or unsealed run` after the analysis had been paid for
    (wound_healing and cerebrolysin_flow, staged beneath an archive-bearing
    ancestor). The root is now pinned when the run starts."""

    def test_a_marker_created_mid_run_does_not_move_the_archive(
            self, tmp_path, fakes):
        root = tmp_path / "project"
        (root / ".analysis_runs").mkdir(parents=True)
        paper = root / "corpus" / "paper"
        paper.mkdir(parents=True)
        (paper / "body.md").write_text("The compliance rate was 81.3% of "
                                       "participants reported full compliance.")
        res = run(paper)
        assert res["history_root"] == str(root.resolve())
        (paper.parent / ".image_track").mkdir()   # what the image track does
        parallel.write_parallel_outputs(res, tmp_path / "rv", render_pdf=False)
        assert (tmp_path / "rv" / "findings.v2.json").is_file()
        assert not (paper.parent / ".analysis_runs").exists()


class TestAToolsAgentThatNeverReachedItsToolsIsRefused:
    """`_assert_forensic_tools_ran` checks only the legacy labels
    `sweep`/`analysis`, so in the parallel pipeline (label `tool_agent`) it
    never fired: a tools agent with zero calls on its forensic list could
    file rows that read as a checked paper. The gate now runs after the
    retries, in `AnalystModule.run`."""

    def _run_with(self, paper, monkeypatch, messages):
        async def fake_requiring(*, build_cmd, prompt, stage_label, **kw):
            build_cmd()
            res = _stage(_doc([_row("t_unbacked")]))
            res["messages"] = messages
            agent.record_spend(stage_label, res)
            return res
        monkeypatch.setattr(agent, "_run_stage_requiring_forensic_tools",
                            fake_requiring)
        return run(paper)

    def test_rows_with_no_forensic_call_behind_them_are_refused(
            self, paper, monkeypatch, fakes):
        res = self._run_with(paper, monkeypatch, [])
        assert any("REFUSED" in l and "tool_agent" in l
                   for l in res["limitations"])
        assert not any(f.get("slug") == "t_unbacked"
                       for f in res["findings_v2"]["findings"])
        assert res["is_error"] is True          # a configured analyst lost

    def test_one_reader_call_is_enough(self, paper, monkeypatch, fakes):
        res = self._run_with(paper, monkeypatch, _reader_call_messages())
        assert not any("REFUSED" in l for l in res["limitations"])
        assert any(f.get("slug") == "t_unbacked"
                   for f in res["findings_v2"]["findings"])


class TestAnAdjudicatorCrashKeepsTheFindings:
    """Astra design item #8 (2026-10-02), deferred until now: a stage that
    RAISES in the adjudicator propagated, and no findings.v2 was written, so
    both analysts' paid work was lost to the step that only grades it."""

    def test_a_stage_error_finalises_with_provisional_severities(
            self, paper, fakes):
        fakes["adjudicator"] = agent.StageError("`claude` CLI exited with code 1")
        res = run(paper)
        doc = res["findings_v2"]
        assert doc["adjudication"]["ran"] is False
        assert {f.get("slug") for f in doc["findings"]} >= {"t1", "s1"}
        assert any("adjudicator stage failed (StageError)" in l
                   for l in res["limitations"])

    def test_an_account_level_stop_still_propagates(self, paper, fakes):
        from metascience_agent.llm_backend import BackendUnavailable
        fakes["adjudicator"] = BackendUnavailable("out of credits")
        with pytest.raises(BackendUnavailable):
            run(paper)
