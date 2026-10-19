"""The parallel pipeline writes a sandbox audit, and every verdict is reachable.

`docs/specs/pipeline.md §13` has listed `sandbox_audit.json` among a parallel
run's outputs since the v2 cutover, and `README.md:296` calls it "**read this
one** ... a silently un-sandboxed run is otherwise indistinguishable from a
validated one". It was never written. MEASURED 2026-09-03: none of the four
archived parallel runs has one; all three legacy runs do; and
`obligations.PARALLEL_TOLERATED` had come to excuse the absence as a
"legacy-path artifact", which is a missing requirement wearing the clothes of
a design decision.

The known-positive tests below exist because the first run of the ported audit
returned `clean` on all four archived runs. That is the right answer for those
runs, and it is also exactly what a broken guard returns (LESSONS.md, entry 4).
"""
from __future__ import annotations

import json

import pytest

from forensic_metascience_ai_toolkit import agent, obligations, parallel
from forensic_metascience_ai_toolkit.parallel import TOOL_AGENT_TOOLS


def _ledger(*names, allowed=None):
    msgs = [{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": str(i), "name": n, "input": {}}
        for i, n in enumerate(names)]}}]
    return agent._tool_call_ledger(msgs, allowed or TOOL_AGENT_TOOLS)


def _level(ledger, allowed=None, findings=None):
    a = agent._sandbox_audit(ledger, allowed or TOOL_AGENT_TOOLS, findings or [])
    return agent.compose_sandbox_audit({"tool_agent": a}, "tool_agent")


class TestEveryVerdictIsReachable:
    """A guard that cannot fail is worse than no guard: it reads as a pass."""

    def test_a_shell_call_is_severe(self):
        d = _level(_ledger("Bash"))
        assert d["level"] == "severe"
        assert "could compute statistics" in d["verdict"]
        assert d["n_severe_total"] == 1

    def test_an_off_surface_tool_is_a_surface_breach(self):
        d = _level(_ledger("WebFetch"), allowed=["Read"])
        assert d["level"] == "surface"
        assert d["n_unvalidated_total"] == 1

    def test_a_finding_naming_a_check_that_never_ran_is_unbacked(self):
        """`grim` is backed by `grim_check`; a statcheck call does not back it."""
        d = _level(_ledger(agent._mcp("statcheck")),
                   findings=[{"id": "f1", "technique": "grim",
                              "severity": "suspicious"}])
        assert d["level"] == "unbacked"
        assert d["unbacked_finding_ids"] == ["f1"]

    def test_an_undeclared_forensic_tool_is_off_list_not_a_breach(self):
        """`grim_test` is not a tool name; the registry's is `grim_check`.
        Calling the former is a real off-list call, and off-list is NOT a
        breach -- our arithmetic is still our arithmetic."""
        d = _level(_ledger(agent._mcp("grim_test")))
        assert d["level"] == "off_allowlist"
        assert d["n_severe_total"] == 0 and d["n_unvalidated_total"] == 0

    def test_a_declared_forensic_call_backing_its_finding_is_clean(self):
        """The known NEGATIVE. `severity_reconcile._TECHNIQUE_TOOLS` maps the
        technique `grim` onto the tool `grim_check`, so this finding is
        backed by the call beside it and nothing is in doubt."""
        d = _level(_ledger(agent._mcp("grim_check")),
                   findings=[{"id": "f1", "technique": "grim",
                              "severity": "suspicious"}])
        assert d["level"] == "clean", d["verdict"]


class TestTheParallelWriterProducesIt:
    def test_it_is_a_required_artifact_now(self):
        assert "sandbox_audit.json" in obligations.required_names()
        assert "sandbox_audit.json" not in obligations.PARALLEL_TOLERATED, (
            "it was tolerated as a 'legacy-path artifact' while the spec "
            "required it; that exemption is what hid the gap")

    def test_an_unmeasurable_run_says_so_rather_than_vanishing(self, tmp_path):
        """No ledger means no agent recorded a tool call. Omitting the file
        would make 'we could not look' indistinguishable from 'we looked and
        it was clean', on the one artifact whose job is telling them apart."""
        written = {}

        def _w(name, payload):
            (tmp_path / name).write_text(
                payload if isinstance(payload, str)
                else json.dumps(payload, indent=2, default=str))
            written[name] = True

        parallel._write_sandbox_audit({"run_meta": {}}, {}, {"findings": []}, _w)
        doc = json.loads((tmp_path / "sandbox_audit.json").read_text())
        assert doc["level"] == "not_measured"
        assert "is unknown for this run" in doc["verdict"]
        assert doc["n_severe_total"] is None, (
            "0 would assert there were no breaches; there was no measurement")

    def test_each_agent_is_scored_against_its_own_findings(self, tmp_path):
        """The union rule was measured wrong on the legacy archive: 29
        top-level unbacked findings fell to 6 under per-producer scoring."""
        written = {}

        def _w(name, payload):
            written[name] = payload

        result = {"run_meta": {}}
        doc = {"findings": [
            {"finding_id": "t1", "producer": "tool_expert",
             "technique": "grim", "severity": 5},
            {"finding_id": "s1", "producer": "science_error",
             "technique": "internal_contradiction", "severity": 4},
        ]}
        ledgers = {"tool_agent": _ledger(agent._mcp("grim_check")),
                   "science_agent": _ledger(agent._mcp("check_flow_arithmetic"))}
        parallel._write_sandbox_audit(result, ledgers, doc, _w)
        audit = written["sandbox_audit.json"]
        assert set(audit["stages"]) == {"tool_agent", "science_agent"}
        # The science finding must not be scored against the tool agent's
        # ledger, nor the reverse.
        assert audit["n_unbacked_findings"] == 0, audit["unbacked_finding_ids"]
        assert result["run_meta"]["sandbox"]["level"] == audit["level"]

    def test_run_meta_carries_every_count_the_verdict_rests_on(self, tmp_path):
        result = {"run_meta": {}}
        parallel._write_sandbox_audit(
            result, {"tool_agent": _ledger("Bash")}, {"findings": []},
            lambda name, payload: None)
        sb = result["run_meta"]["sandbox"]
        assert sb["level"] == "severe"
        assert set(sb) >= {"verdict", "level", "n_unvalidated", "n_severe",
                           "n_unbacked_findings", "n_off_allowlist"}


class TestAgainstTheRealArchive:
    """The known negative, to match the known positives above."""

    RUNS = ["apple_cider", "cerebrolysin_flow", "wound_healing", "airforce"]

    @pytest.mark.parametrize("run", RUNS)
    def test_each_archived_parallel_run_audits_without_error(self, run):
        import pathlib
        d = (pathlib.Path(__file__).resolve().parents[1]
             / "benchmarks" / "paper_reviews" / "runs" / run / "forensic_review")
        if not (d / "findings.v2.json").is_file():
            pytest.skip(f"{run} is not in this checkout")
        doc = json.loads((d / "findings.v2.json").read_text())
        allowed = {"tool_agent": TOOL_AGENT_TOOLS,
                   "science_agent": parallel.SCIENCE_AGENT_TOOLS,
                   "adjudicator": parallel.ADJUDICATOR_TOOLS}
        by = {}
        for f in doc.get("findings") or []:
            by.setdefault(f.get("producer"), []).append(f)
        audits = {}
        for label in allowed:
            p = d / f"toolcalls.{label}.json"
            if not p.is_file():
                continue
            led = json.loads(p.read_text())
            if led:
                audits[label] = agent._sandbox_audit(
                    led, allowed[label],
                    by.get(parallel._AUDIT_PRODUCERS.get(label), []))
        assert audits, f"{run} has no ledger to audit"
        out = agent.compose_sandbox_audit(audits, "tool_agent")
        assert out["level"] in {"clean", "off_allowlist", "surface",
                                "unbacked", "severe"}
        assert out["verdict"]


class TestTheGuardAuditReachesEveryAgent:
    """v1.22.0 ported the sandbox audit and dropped its guard half.

    The legacy writer attaches `guards` per stage; the parallel port called
    `_sandbox_audit` and stopped there. `bundle._guards_by_stage` reads
    `sandbox_audit.stages.<stage>.guards` and its docstring asserts
    "_guard_audit runs on every stage of every run" -- false for every
    parallel run from v1.22.0 until this fix, so the viewer's guard pane was
    empty and nothing said why.

    This is the more consequential half. A guard is a precondition without
    which a check INVERTS rather than degrades, so a defaulted `data_type` is
    the likeliest single cause of a false accusation, and this block is the
    only thing that counts how often one is supplied. MEASURED on the archived
    `wound_healing` tool-agent ledger once attached: 51 guarded calls, 92
    guard slots, 46 supplied -- half of them defaulted, previously invisible.
    """

    def _audit(self, ledger, findings=None):
        out = {}
        parallel._write_sandbox_audit(
            {"run_meta": {}}, {"tool_agent": ledger},
            {"findings": findings or []},
            lambda name, payload: out.__setitem__(name, payload))
        return out["sandbox_audit.json"]

    def test_every_agent_block_carries_guards(self):
        doc = self._audit(_ledger(agent._mcp("grim_check")))
        for label, block in doc["stages"].items():
            assert "guards" in block, f"{label} has no guard audit"

    def test_the_block_is_the_shape_the_viewer_reads(self):
        """`_guards_by_stage` keeps only stages whose `guards` is a dict."""
        from forensic_metascience_ai_toolkit import bundle
        doc = self._audit(_ledger(agent._mcp("grim_check")))
        assert bundle._guards_by_stage(doc), (
            "the viewer's guard pane would still be empty")

    def test_it_counts_a_defaulted_guard_as_a_known_positive(self):
        """A `grim_check` call with no `data_type` is the exact case the audit
        exists to find; a guard audit that never reports one is inert."""
        led = _ledger(agent._mcp("grim_check"))
        g = self._audit(led)["stages"]["tool_agent"]["guards"]
        assert g["n_guard_slots"] > 0, "no guarded tool was recognised at all"
        assert g["n_defaulted"] >= 1, (
            "a call supplying no guard was not counted as defaulted")


class TestCodexShellReadsAreTheReadAnalog:
    """Codex's shell is its only file reader (`llm_backend.CODEX`). MEASURED
    2026-10-11: a gpt-5.6-terra review's seven shell calls were all `rg`,
    `sed -n 'N,Mp'` and `pdftotext` over the paper, and its audit read
    "BREACH (severe)". A pure read is not computation; anything else is."""

    READS = [
        "/bin/bash -lc \"rg -n -F -e 'clean and tidy' -e 'n 5 20)' body.md\"",
        "/bin/bash -lc \"pdftotext -layout paper.pdf - | sed -n '175,223p'\"",
        "/bin/bash -lc 'rg --files /home/dan/paper | head -80'",
        "sed -n '1,240p' notes.md",
        "cat body.md | grep -n Kitten | wc -l",
        # The second terra science-agent call, verbatim in shape:
        "/bin/bash -lc 'rg -n \"extract_pdf|check_flow_arithmetic\" . "
        "/home/dan/.cache/metascience 2>/dev/null | head -80; "
        "rg --files . | head -100'",
        "/bin/bash -lc 'rg -n x body.md 2>&1 | head -5'",
    ]
    COMPUTES = [
        "/bin/bash -lc \"python3 -c 'print(3.63**0.5)'\"",
        "/bin/bash -lc \"awk '{s+=$1} END {print s}' col.txt\"",
        "/bin/bash -lc 'rg -n x body.md > out.txt'",
        "/bin/bash -lc 'rg -n x body.md >> /tmp/log'",
        "/bin/bash -lc 'cat < /etc/passwd'",
        "/bin/bash -lc 'cat a; python3 b.py'",
        "/bin/bash -lc 'rg -n x body.md && bc <<< 2+2'",
        "/bin/bash -lc 'echo $(python3 -c 1)'",
        "/bin/bash -lc 'rg --pre ./run.sh x .'",
        "/bin/bash -lc \"find . -name '*.py' -exec python3 {} ;\"",
        "/bin/bash -lc \"sed -n 'e python3 x.py' f\"",
        "/bin/bash -lc \"sed -i 's/a/b/' f\"",
        "bash -lc",
    ]

    @pytest.mark.parametrize("cmd", READS)
    def test_a_pure_read_is_recognised(self, cmd):
        assert agent._shell_reads_only({"command": cmd})

    @pytest.mark.parametrize("cmd", COMPUTES)
    def test_anything_that_could_compute_is_not(self, cmd):
        assert not agent._shell_reads_only({"command": cmd})

    def _shell_ledger(self, cmd, allowed):
        msgs = [{"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "c1", "name": "Bash",
             "input": {"command": cmd}}]}}]
        return agent._tool_call_ledger(msgs, allowed)

    def test_a_read_on_a_stage_that_may_read_is_no_breach(self):
        led = self._shell_ledger(self.READS[1], ["Read"])
        assert led[0]["surface"] == "builtin_allowed"
        assert led[0]["validated"] is False
        assert _level(led, ["Read"])["level"] == "clean"

    def test_a_computing_shell_call_is_still_severe(self):
        led = self._shell_ledger(self.COMPUTES[0], ["Read"])
        assert led[0]["surface"] == "UNVALIDATED"
        assert _level(led, ["Read"])["level"] == "severe"

    def test_a_stage_that_may_not_read_gets_no_exemption(self):
        led = self._shell_ledger(self.READS[0], ["mcp__forensic_metascience__grim_check"])
        assert led[0]["surface"] == "UNVALIDATED"
