import pytest
"""Every tool call is recorded, and an off-tool computation is detectable.

The motivating run (tests/fixtures/papers/cerebrolysin_papers/done/10.1002--adbi.202300439,
2026-07-17) hand-wrote scipy in `python3 -c` for its two-tailed lifespan
p-value and its r-squared comparison. Two of the report's three most prominent
findings rested on that code. Nothing in the output distinguished them from
findings produced by a validated tool, and the only way to discover it was to
read 200KB of message log by hand.

These tests pin the machinery that makes it a one-line answer instead.
"""
import json

from metascience_agent import agent as A
from metascience_agent.agent import STAGE1_TOOLS, _mcp, _sandbox_audit, _tool_call_ledger


def _msgs(*calls):
    """Build a minimal message stream: one assistant tool_use + its result."""
    out = []
    for i, (name, inp, result) in enumerate(calls):
        tid = f"toolu_{i}"
        out.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": tid, "name": name, "input": inp}]}})
        out.append({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": tid,
             "content": [{"type": "text", "text": result}]}]}})
    return out


class TestLedger:
    def test_records_every_call_with_inputs(self):
        led = _tool_call_ledger(_msgs(
            (_mcp("grim_check"), {"mean": 5.51, "n": 30}, '{"consistent": false}'),
            ("Bash", {"command": "python3 -c 'print(1)'"}, "1"),
        ), STAGE1_TOOLS)
        assert [c["seq"] for c in led] == [1, 2]
        assert led[0]["input"] == {"mean": 5.51, "n": 30}
        assert led[0]["result"] == '{"consistent": false}'

    def test_classifies_the_surface(self):
        led = _tool_call_ledger(_msgs(
            (_mcp("grim_check"), {}, "x"),
            ("Read", {}, "x"),
            ("Bash", {}, "x"),
        ), STAGE1_TOOLS)
        assert [c["surface"] for c in led] == [
            "forensic_mcp", "builtin_allowed", "UNVALIDATED"]
        assert [c["validated"] for c in led] == [True, False, False]

    def test_forensic_results_are_kept_in_full(self):
        """Forensic results ARE the evidence; truncating them loses provenance."""
        big = "y" * 9000
        led = _tool_call_ledger(_msgs((_mcp("grim_check"), {}, big)), STAGE1_TOOLS)
        assert led[0]["result_truncated"] is False
        assert len(led[0]["result"]) == 9000

    def test_bulk_results_are_truncated_but_measured(self):
        """extract_pdf embeds the paper; record the size, not the payload."""
        big = "z" * 9000
        led = _tool_call_ledger(_msgs((_mcp("extract_pdf"), {}, big)), STAGE1_TOOLS)
        assert led[0]["result_truncated"] is True
        assert led[0]["result_chars"] == 9000
        assert len(led[0]["result"]) < 9000


class TestSandboxAudit:
    def test_clean_run(self):
        a = _sandbox_audit(_tool_call_ledger(
            _msgs((_mcp("grim_check"), {}, "x")), STAGE1_TOOLS), STAGE1_TOOLS)
        assert a["level"] == "clean" and a["n_unvalidated"] == 0

    def test_bash_is_severe(self):
        """Bash can COMPUTE a statistic. That corrupts findings."""
        a = _sandbox_audit(_tool_call_ledger(
            _msgs(("Bash", {"command": "python3 -c ..."}, "x")), STAGE1_TOOLS), STAGE1_TOOLS)
        assert a["level"] == "severe" and a["n_severe"] == 1
        assert "re-checked" in a["verdict"]

    def test_surface_extension_is_not_conflated_with_computation(self):
        """ToolSearch widens the surface but does no arithmetic.

        Grading them the same would bury the severe case under routine noise,
        and an audit that cries wolf gets ignored.
        """
        a = _sandbox_audit(_tool_call_ledger(
            _msgs(("ToolSearch", {"query": "select:grim_check"}, "x")),
            STAGE1_TOOLS), STAGE1_TOOLS)
        assert a["level"] == "surface"
        assert a["n_severe"] == 0 and a["n_surface"] == 1

    def test_severe_dominates_when_both_present(self):
        a = _sandbox_audit(_tool_call_ledger(_msgs(
            ("ToolSearch", {}, "x"), ("Bash", {}, "x"),
        ), STAGE1_TOOLS), STAGE1_TOOLS)
        assert a["level"] == "severe"


class TestTheDispatcherSRefusalsReachTheReport:
    """`not_run` was machine-generated per (cell, check) and consumed by nothing.

    A run that submitted three tables and had every cell inside them refused
    still reported `tables_checked: ["Table 1","Table 2","Table 3"]`, because
    "checked" meant "attempted". The reader could not tell "checked and clean"
    from "never actually checked".
    """

    @staticmethod
    def _messages(not_run):
        import json
        return [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "t1",
                 "name": "mcp__forensic_metascience__check_table", "input": {}}]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "t1",
                 "content": [{"type": "text",
                              "text": json.dumps({"not_run": not_run})}]}]}},
        ]

    def test_refusals_are_harvested(self):
        from metascience_agent.agent import _machine_refusals
        out = _machine_refusals(self._messages([
            {"cell": "r0", "tools": ["grim_check"], "reason": "needs n"},
            {"cell": "r1", "tools": ["grim_check"], "reason": "needs n"},
        ]))
        assert len(out) == 1
        assert out[0]["n_cells"] == 2
        assert "grim_check" in out[0]["reason"] and "needs n" in out[0]["reason"]
        assert out[0]["source"] == "dispatcher"

    def test_many_identical_refusals_collapse_to_one_entry(self):
        from metascience_agent.agent import _machine_refusals
        out = _machine_refusals(self._messages(
            [{"cell": f"r{i}", "tools": ["grim_check"], "reason": "needs n"}
             for i in range(34)]))
        assert len(out) == 1 and out[0]["n_cells"] == 34
        assert "and 28 more" in out[0]["location"]

    def test_different_reasons_stay_separate(self):
        from metascience_agent.agent import _machine_refusals
        out = _machine_refusals(self._messages([
            {"cell": "r0", "tools": ["grim_check"], "reason": "needs n"},
            {"cell": "r1", "tools": ["debit_check"], "reason": "no stated bound"},
        ]))
        assert len(out) == 2

    def test_a_clean_run_harvests_nothing(self):
        from metascience_agent.agent import _machine_refusals
        assert _machine_refusals(self._messages([])) == []

    def test_a_truncated_or_unparseable_result_does_not_crash(self):
        from metascience_agent.agent import _machine_refusals
        msgs = self._messages([])
        msgs[1]["message"]["content"][0]["content"][0]["text"] = '{"not_run": [ trunca'
        assert _machine_refusals(msgs) == []

class TestTheGateableSubsetIsNotTheRawVerdict:
    """A run linter must fire on unbacked ACCUSATIONS, not on BREACH.

    MEASURED over 25 archived runs: 21 of 24 carry a BREACH verdict (88%), but 9
    are `level: surface` -- allowlist bookkeeping whose own text says "no
    statistic was computed off-tool". Of the genuinely unbacked findings, 33
    exist corpus-wide and 25 are `indeterminate` or `consistent`. Only 8 of 239
    accusations are unbacked.

    The 2026-08-10 control run is the case that settles the design: it breached
    on two `indeterminate` findings while its three `grim_sweep` `impossible`
    findings were tool-backed, verbatim-quoted and correct on hand-checked
    arithmetic. Gating on the raw verdict would have blocked a right answer.
    """

    LEDGER = [{"tool_short": "grim_check", "validated": True}]

    def _findings(self):
        return [
            # unbacked and accusatory -- the thing a gate exists for
            {"id": "a", "technique": "sprite", "severity": "impossible"},
            # unbacked but a refusal: log it, do not stop the run
            {"id": "b", "technique": "duplication", "severity": "indeterminate"},
            {"id": "c", "technique": "csf", "severity": "consistent"},
            # honestly labelled: never a breach
            {"id": "d", "technique": "manual", "severity": "suspicious"},
            # backed by a real validated call
            {"id": "e", "technique": "grim", "severity": "impossible"},
        ]

    def test_only_the_accusatory_unbacked_findings_are_gateable(self):
        from metascience_agent.agent import unbacked_accusations
        ids = {f["id"] for f in unbacked_accusations(self.LEDGER, self._findings())}
        assert ids == {"a"}, ids

    def test_the_raw_unbacked_list_is_wider_and_must_stay_wider(self):
        """Both lists are wanted: one to LOG, one to GATE."""
        from metascience_agent.agent import _unbacked_findings, unbacked_accusations
        raw = {f["id"] for f in _unbacked_findings(self.LEDGER, self._findings())}
        gate = {f["id"] for f in unbacked_accusations(self.LEDGER, self._findings())}
        assert gate < raw, "the gateable subset must be strictly narrower"
        assert {"b", "c"} <= raw, "refusals still get recorded"

    def test_a_manual_finding_is_never_gateable(self):
        """`manual` is honestly labelled. It is a severity-cap question, not a
        sandbox breach, and conflating them would punish the honest label."""
        from metascience_agent.agent import unbacked_accusations
        assert unbacked_accusations(
            [], [{"id": "m", "technique": "manual", "severity": "impossible"}]) == []


class TestRunProvenance:
    """Two runs of "the same toolkit" can be two different experiments.

    `version` moves monthly; the prompts and registry move several times a day.
    Nothing recorded the difference, which is exactly why the three archived
    same-paper repeat sets cannot serve as the run-to-run noise floor the
    cheaper-model study is gated on.
    """

    def test_provenance_never_breaks_a_run(self):
        """It is bookkeeping. A failure here must not cost a paid analysis."""
        from metascience_agent import agent as A
        import metascience_agent.registry as R
        real = R.SPECS
        try:
            R.SPECS = property(lambda self: 1 / 0)  # force the hash to raise
            out = A._provenance()
        finally:
            R.SPECS = real
        assert isinstance(out, dict)


class TestTheVerdictGetsADenominator:
    """A verdict is a judgement about a paper, and a judgement needs a
    denominator. Stage 2 receives `findings.json`, so individually-reported
    passes DO reach it -- but `check_table` returns its passes as a COUNT plus
    an index rather than repeating them, and stage 2 is handed findings, not the
    ledger. MEASURED over 21 archived runs: 184 passes reported individually,
    while one run collapsed 125 MORE that the editorial stage never saw.

    Greg's reading (2026-08-10) was that consistent checks were "in the pile of
    tested but not included in the report". Half right, and the half that is
    right is this one: the collapsed passes were genuinely invisible.
    """

    @staticmethod
    def _msgs_with_collapsed(n):
        import json as _j
        payload = _j.dumps({
            "severity": "consistent",
            "consistent_index": [{"check_id": f"r{i}.grim_check",
                                  "tool": "grim_check"} for i in range(n)],
            "results": [],
        })
        return _msgs((_mcp("check_table"), {"cells": []}, payload))

    def test_collapsed_passes_are_counted(self):
        from metascience_agent.agent import checks_tally
        t = checks_tally(self._msgs_with_collapsed(125),
                         {"findings": [{"severity": "consistent"},
                                       {"severity": "suspicious"}]})
        assert t["of_which_collapsed_by_check_table"] == 125
        assert t["checks_passed"] == 126, "1 reported + 125 collapsed"
        assert t["checks_flagged"] == 1
        assert t["checks_total"] == 127

    def test_refusals_are_kept_separate_from_passes_and_from_flags(self):
        """`indeterminate` is OUR reach failing. Folding it into either column
        would make our blind spots read as evidence about the paper."""
        from metascience_agent.agent import checks_tally
        t = checks_tally([], {"findings": [
            {"severity": "indeterminate"}, {"severity": "indeterminate"},
            {"severity": "consistent"}, {"severity": "impossible"}]})
        assert t["checks_refused_indeterminate"] == 2
        assert t["checks_passed"] == 1
        assert t["checks_flagged"] == 1

    def test_findings_v2_outcomes_are_counted(self):
        """THE REGRESSION THAT WAS MISSING. `checks_tally` bucketed on the v1
        lowercase severity ladder while findings-v2 carries `outcome` and an
        INTEGER severity, so every v2 finding fell into "unknown" and
        `checks_total` came out 0 -- on all 9 papers of a real batch. The dict
        goes straight into `adjudicate.build_docket(tally=...)`, so a zeroed
        tally tells the adjudicator nothing passed and nothing was flagged."""
        from metascience_agent.agent import checks_tally
        t = checks_tally([], {"findings": [
            {"outcome": "pass", "severity": None},
            {"outcome": "pass", "severity": None},
            {"outcome": "problem", "severity": 4},
            {"outcome": "problem", "provisional_severity": 2},
            {"outcome": "undecided", "severity": None},
        ]})
        assert t["checks_total"] == 5, "a v2 docket must not tally to zero"
        assert t["checks_passed"] == 2
        assert t["checks_flagged"] == 2
        assert t["checks_refused_indeterminate"] == 1
        assert t["by_outcome"] == {"pass": 2, "flagged": 2, "refused": 1}

    def test_an_unrecognised_vocabulary_is_named_not_binned(self):
        """A finding neither branch understands is counted as `unclassified`.
        Folding it into passes is how a blind spot reads as a clean paper."""
        from metascience_agent.agent import checks_tally
        t = checks_tally([], {"findings": [{"title": "no outcome, no severity"}]})
        assert t["checks_total"] == 0
        assert t["checks_passed"] == 0
        assert t["by_outcome"] == {"unclassified": 1}

class TestThePromptIsPersisted:
    """What we SENT was recorded nowhere, and the gap was not academic.

    On 2026-08-10 a change added a check tally to the stage-2 prompt; a paid run
    was made to confirm it; and the confirmation was impossible. MEASURED on
    that run's `messages.stage2.json`: "Write the editorial forensic review",
    "Stage-1 sweep findings" and "Triage these findings" each appear ZERO times,
    and all three are in the prompt on every run regardless of any change. The
    transcript holds the model's turns, never the instruction.

    Same blind spot as the 135 dropped help strings, one layer up: our side
    believed something was delivered and no artifact could contradict it.
    """

    @pytest.mark.usefixtures("image_package")
    def test_the_runner_carries_the_prompt_out(self):
        """The prompt is recorded where it is SENT, not rebuilt afterwards -- a
        prompt reconstructed later is a guess about what ran, not a record."""
        import inspect
        from metascience_agent import agent as A
        from metascience_observatory_image_analysis import runtime
        src = inspect.getsource(runtime._run_stage)
        assert '"prompt": prompt' in src


class TestLedgerToolNamesAreBackendNeutral:
    """MEASURED 2026-08-22 over the 24 archived ledgers of a 10-paper grok-4.6
    run (2,196 tool calls). One tool name in the whole stream was not a name:
    `"Web search:"`, trailing colon included, 7 calls. Consequences, both
    silent:

      - `surface` was `UNVALIDATED` -- the value reserved for a tool the stage
        never declared -- so legitimate web searches by the science agent were
        filed as a list breach.
      - `_WEB_TOOLS` in parallel.py never matched it, and that set decides what
        the adjudicator is told the agent actually visited.

    `WebFetch` and `Read` happened to arrive under Claude's names in that run,
    so those counters were right; `read_file` and `web_fetch` are Grok's own
    builtin names and are mapped rather than waited for.
    """

    _ALLOWED = ["Read", "WebSearch", "WebFetch",
                "mcp__forensic_metascience__grim_test"]

    def _ledger(self, *names):
        msgs = [{"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": str(i), "name": n, "input": {}}
            for i, n in enumerate(names)]}}]
        return A._tool_call_ledger(msgs, self._ALLOWED)

    def test_a_display_string_is_not_filed_as_a_list_breach(self):
        """The invariant is NOT-A-BREACH, which is what this class is for.

        The surface NAME moved from `builtin_allowed` to `web` in v1.21.0,
        when `docs/specs/pipeline.md §9`'s `web` / `agent_code` surfaces
        were finally implemented. Both are legitimate; `UNVALIDATED` is the
        breach value and is what this test exists to keep it away from.
        """
        row, = self._ledger("Web search:")
        assert row["tool_short"] == "WebSearch"
        assert row["surface"] == "web"
        assert row["surface"] != "UNVALIDATED"

    def test_web_text_is_never_validated_evidence(self):
        """The other half of the same spec line: `validated` stays False for
        web and for ad-hoc code, "even though `run_python_script` rides the
        forensic MCP server"."""
        row, = self._ledger("Web search:")
        assert row["validated"] is False
        code, = A._tool_call_ledger([{"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "1",
             "name": A._mcp("run_python_script"), "input": {}}]}}], self._ALLOWED)
        assert code["surface"] == "agent_code"
        assert code["validated"] is False, (
            "a script the model wrote itself is not arithmetic this toolkit "
            "performed; `_unbacked_findings` reads this flag")

    def test_the_raw_name_is_preserved_as_evidence(self):
        """`tool` records what the model asked for; normalising it erases that."""
        row, = self._ledger("Web search:")
        assert row["tool"] == "Web search:"

    def test_grok_builtin_names_map_onto_the_canonical_ones(self):
        rows = self._ledger("read_file", "web_fetch")
        assert [r["tool_short"] for r in rows] == ["Read", "WebFetch"]

    def test_a_denied_shell_stays_conspicuous(self):
        """Aliasing `run_terminal_cmd` onto `Bash` would hide a breach."""
        row, = self._ledger("run_terminal_cmd")
        assert row["tool_short"] == "run_terminal_cmd"
        assert row["surface"] == "UNVALIDATED"

    def test_our_own_mcp_names_are_untouched(self):
        row, = self._ledger("mcp__forensic_metascience__grim_test")
        assert row["tool_short"] == "grim_test"
        assert row["surface"] == "forensic_mcp"
