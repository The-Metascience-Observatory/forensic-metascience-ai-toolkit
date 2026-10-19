"""The audit must score calls against the list it publishes.

FOUND BY THE RUN-INCOHERENCE SWEEP, 2026-08-11, across three archived runs of
`10.1002--eat.24415`.

WHAT WAS WRONG. `_tool_call_ledger` set `surface = "forensic_mcp"` for any name
carrying the MCP prefix. That answers "is this one of our tools", which is not
the question `sandbox_audit.json` puts to a reader: the object prints
`declared_allowlist` and a breach count side by side, so the implied claim is
that the run stayed inside the list beside it. It did not. Measured:

    run       stage   allowlist   off-list calls                   verdict
    review    1       41          check_sd_range x6, flag_round_n  BREACH (surface)
    review    2       28          grim_percentage x2, ...batch     BREACH (surface)
    warrant   1       48          check_sd_range                   BREACH (unbacked)
    warrant   2       35          absence_of_evidence              CLEAN
    clamped   2       35          absence_of_evidence x2           CLEAN

`absence_of_evidence` is on stage 1's allowlist and not on stage 2's. Two runs
printed a 35-name list, `n_unvalidated: 0`, and the word "clean".

WHY OFF-LIST IS ITS OWN TIER AND NOT A BREACH. The arithmetic really was done
by a tool we wrote and test, so no finding is discredited -- folding these into
`n_unvalidated` would tell a reader that trustworthy computations were
untrustworthy, which is the false-accusation direction and worse than the
silence it replaced. `validated` therefore stays true; only `surface` and the
verdict change.
"""
import json
from pathlib import Path

import pytest

from metascience_agent.agent import (MCP_TOOL_PREFIX, STAGE1_TOOLS,
                                     STAGE2_TOOLS, _sandbox_audit,
                                     _tool_call_ledger)

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--eat.24415"

ON_LIST = MCP_TOOL_PREFIX + "check_effect_plausibility"
OFF_LIST = MCP_TOOL_PREFIX + "absence_of_evidence"


def _messages(*names: str) -> list[dict]:
    return [{"type": "assistant",
             "message": {"content": [
                 {"type": "tool_use", "id": f"t{i}", "name": n, "input": {}}
                 for i, n in enumerate(names)]}}]


class TestTheLedgerSeparatesOurToolFromThisStagesList:
    def test_a_declared_tool_is_forensic_mcp(self):
        led = _tool_call_ledger(_messages(ON_LIST), STAGE2_TOOLS)
        assert led[0]["surface"] == "forensic_mcp"

    def test_an_undeclared_forensic_tool_is_marked_off_list(self):
        assert OFF_LIST in STAGE1_TOOLS and OFF_LIST not in STAGE2_TOOLS, (
            "this test is built on the real asymmetry the sweep found; if the "
            "allowlists changed, pick another tool rather than deleting it")
        led = _tool_call_ledger(_messages(OFF_LIST), STAGE2_TOOLS)
        assert led[0]["surface"] == "forensic_mcp_offlist"

    def test_off_list_is_still_validated(self):
        """THE LINE THAT MUST NOT MOVE. `_unbacked_findings` reads `validated`
        to decide whether a finding's technique was actually computed. Marking
        an off-list call unvalidated would turn a stage-discipline slip into an
        accusation that a real check never ran."""
        led = _tool_call_ledger(_messages(OFF_LIST), STAGE2_TOOLS)
        assert led[0]["validated"] is True

    def test_with_no_declared_list_nothing_is_off_it(self):
        """Several internal callers build a ledger with `allowed=[]` only to
        read results back. Scoring those as off-list would manufacture a breach
        out of our own bookkeeping."""
        led = _tool_call_ledger(_messages(OFF_LIST), [])
        assert led[0]["surface"] == "forensic_mcp"

    def test_a_non_mcp_allowlist_does_not_switch_the_rule_on(self):
        """`["Read"]` declares no forensic tool, so it makes no claim about
        which of ours may run."""
        led = _tool_call_ledger(_messages(OFF_LIST), ["Read"])
        assert led[0]["surface"] == "forensic_mcp"


class TestTheVerdict:
    def test_an_off_list_call_is_not_reported_as_clean(self):
        led = _tool_call_ledger(_messages(ON_LIST, OFF_LIST), STAGE2_TOOLS)
        audit = _sandbox_audit(led, STAGE2_TOOLS, None)
        assert audit["level"] == "off_allowlist"
        assert not audit["verdict"].startswith("clean")
        assert "absence_of_evidence" in audit["verdict"]

    def test_it_names_the_tool_so_the_reader_can_check_the_list(self):
        led = _tool_call_ledger(_messages(OFF_LIST), STAGE2_TOOLS)
        audit = _sandbox_audit(led, STAGE2_TOOLS, None)
        assert audit["n_off_allowlist"] == 1
        assert audit["off_allowlist_calls"][0]["tool"] == "absence_of_evidence"

    def test_it_does_not_inflate_the_unvalidated_count(self):
        led = _tool_call_ledger(_messages(OFF_LIST), STAGE2_TOOLS)
        audit = _sandbox_audit(led, STAGE2_TOOLS, None)
        assert audit["n_unvalidated"] == 0, (
            "off-list is a different thing from off-surface, and the field a "
            "reader treats as 'untrustworthy computations' must keep meaning it")

    def test_a_real_breach_still_outranks_it(self):
        """Ordering matters: a `Bash` call must never be reported as the milder
        finding just because an off-list call sits beside it."""
        led = _tool_call_ledger(_messages(OFF_LIST, "Bash"), STAGE2_TOOLS)
        audit = _sandbox_audit(led, STAGE2_TOOLS, None)
        assert audit["level"] == "severe"
        assert audit["n_off_allowlist"] == 1, "still counted, just not headlined"

    def test_a_genuinely_clean_stage_is_still_clean(self):
        led = _tool_call_ledger(_messages(ON_LIST, ON_LIST), STAGE2_TOOLS)
        audit = _sandbox_audit(led, STAGE2_TOOLS, None)
        assert audit["level"] == "clean"


class TestTheCountsPartitionTheCalls:
    """`n_validated + n_unvalidated` fell short of `n_calls` in all six
    archived stage blocks -- by 8, 7, 3, 2, 4 and 2 -- because `Read` and
    `StructuredOutput` are harness plumbing and belong to neither bucket. The
    residual was reconstructible from `calls_by_tool` and named nowhere."""

    def test_by_surface_sums_to_n_calls(self):
        led = _tool_call_ledger(
            _messages(ON_LIST, OFF_LIST, "StructuredOutput", "Bash"), STAGE2_TOOLS)
        audit = _sandbox_audit(led, STAGE2_TOOLS, None)
        assert sum(audit["by_surface"].values()) == audit["n_calls"] == 4

    def test_the_harness_calls_are_named_rather_than_left_as_a_residual(self):
        """`StructuredOutput` is the schema-emission mechanism the harness calls
        on our behalf. It is why `forensic_review`'s bundle carries a BREACH
        verdict aimed at our own plumbing, and why the counts never added up."""
        led = _tool_call_ledger(_messages("StructuredOutput"), STAGE2_TOOLS)
        audit = _sandbox_audit(led, STAGE2_TOOLS, None)
        assert audit["by_surface"].get("harness") == 1


class TestTheThreeArchivedRunsThatReportedIt:
    """Replayed from the ledgers on disk, so these are the real calls."""

    # RE-MEASURED 2026-08-15, and the change is the point rather than drift.
    # `check_sd_range` and `flag_round_n` were RESTORED to the stage-1 surface
    # that day, so calls these runs made are no longer off-list. They were never
    # refusals: the ledger shows them executing on `surface=forensic_mcp` with
    # `validated=True` and returning ordinary verdicts. The archive records 49
    # `check_sd_range` and 18 `flag_round_n` calls -- the model used these tools
    # heavily and they were later withdrawn from the surface without being
    # withdrawn from the registry.
    @pytest.mark.parametrize("run,stage,expect", [
        ("forensic_review", "stage1", 0),           # was 7: check_sd_range x6 + flag_round_n
        ("forensic_review", "stage2", 3),           # grim_percentage x2 + batch
        ("forensic_review_warrant", "stage1", 0),   # was 1: check_sd_range
        ("forensic_review_warrant", "stage2", 1),   # absence_of_evidence -- was "clean"
        ("forensic_review_clamped", "stage1", 0),
        ("forensic_review_clamped", "stage2", 2),   # absence_of_evidence x2 -- was "clean"
    ])
    def test_the_off_list_counts_are_the_measured_ones(self, run, stage, expect):
        p = BASE / run / f"toolcalls.{stage}.json"
        if not p.exists():
            pytest.skip(f"{run}/{stage} not in this checkout")
        allowed = STAGE1_TOOLS if stage == "stage1" else STAGE2_TOOLS
        declares = any(t.startswith(MCP_TOOL_PREFIX) for t in allowed)
        got = 0
        for call in json.loads(p.read_text(encoding="utf-8")):
            name = call.get("tool", "")
            if (name.startswith(MCP_TOOL_PREFIX) and declares
                    and name not in set(allowed)):
                got += 1
        assert got == expect


class TestTheTierReachesTheReader:
    """FACTS IN PYTHON, PRESENTATION IN JS -- and for one turn the fact stopped
    at the JSON.

    The off-allowlist tier was added so a run could stop printing "clean" beside
    an allowlist its calls were not on. `sandbox_audit.json` became honest
    immediately; the landing screen said exactly as little as before, because
    all three of its branches missed the new tier:

        n_severe_total        0 by design -- nothing computed off-tool
        /^BREACH/ on verdict  fails: the string starts "OFF-LIST:"
        n_unvalidated_total   0 by design -- the arithmetic IS ours

    So the reader of a run that left its declared surface saw nothing, which is
    the state the tier existed to end. Caught by BUILDING A REAL BUNDLE and
    executing the page's own function, not by reading the diff -- the standing
    lesson in this repo, and the reason it is standing.
    """

    SRC = REPO / "src/metascience_agent/bundle.py"

    def _alarms(self, sandbox):
        """Run the landing screen's own alarm block under node."""
        import json
        import shutil
        import subprocess
        import tempfile
        node = shutil.which("node") or shutil.which("nodejs")
        if not node:
            pytest.skip("node not available")
        src = self.SRC.read_text(encoding="utf-8")
        i = src.index("  const sa=D.sandbox_audit||{};")
        j = src.index("+jump('audit','Audit'));",
                      src.index("n_off_allowlist_total")) + len("+jump('audit','Audit'));")
        prog = ("const esc=s=>String(s==null?'':s);\n"
                "const jump=(a,b)=>'';\n"
                "function run(sandbox){const L=[];const D={sandbox_audit:sandbox};\n"
                + src[i:j] + "\nreturn L;}\n"
                "console.log(JSON.stringify(run(" + json.dumps(sandbox) + ")));")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(prog)
            path = fh.name
        out = subprocess.run([node, path], capture_output=True, text=True)
        assert out.returncode == 0, out.stderr[:400]
        return json.loads(out.stdout.strip())

    def test_an_off_list_run_tells_the_reader(self):
        got = self._alarms({"verdict": "OFF-LIST: 2 call(s) ...",
                            "n_severe_total": 0, "n_unvalidated_total": 0,
                            "n_off_allowlist_total": 2})
        assert got, "the reader is told nothing about an off-list run"
        assert "did not declare" in got[0]

    def test_it_does_not_read_as_an_accusation(self):
        """The arithmetic is ours and tested; no finding is in doubt. Saying so
        is the difference between a provenance note and a false alarm."""
        got = self._alarms({"verdict": "OFF-LIST: 1 call", "n_off_allowlist_total": 1})
        assert "no finding is in doubt" in got[0]

    def test_a_clean_run_still_says_nothing(self):
        assert self._alarms({"verdict": "clean: every tool call was on the "
                             "validated forensic surface",
                             "n_severe_total": 0, "n_unvalidated_total": 0,
                             "n_off_allowlist_total": 0}) == []

    def test_a_severe_breach_still_outranks_it(self):
        got = self._alarms({"verdict": "BREACH (severe): 1 call(s)",
                            "n_severe_total": 1, "n_unvalidated_total": 1,
                            "n_off_allowlist_total": 3})
        assert "SEVERE SANDBOX BREACH" in got[0]

    def test_an_archived_bundle_without_the_field_is_silent(self):
        """Absent must stay absent. Inventing a zero here would print an
        off-list line on every bundle built before the tier existed."""
        assert self._alarms({"verdict": "clean: every tool call was on the "
                             "validated forensic surface"}) == []
