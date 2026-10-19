"""The audit artefacts must not accuse our own output of things it did not do.

Four separate paths were emitting the strongest claim the system makes for
reasons that had nothing to do with the paper or with the model's behaviour:

* the unbacked-findings count scored stage-1 findings against stage 2's
  ledger, so any finding using one of the 15 stage-1-only tools was reported
  "asserted, not performed" on every run, by construction;
* every `BREACH (surface)` on record was the harness's own StructuredOutput;
* `Reproduce:` commands were checked for shape and never run, so 67% of them
  were printed to readers as runnable while exiting non-zero;
* `_GUARD_CONSEQUENCE["data_type"]` carried a "verified:" claim the code had
  since stopped implementing.

`indeterminate` -- "a precondition could not be verified, so I decline to
judge" -- is the right destination for all of it.
"""
import json

import pytest

from forensic_metascience_ai_toolkit.agent import STAGE1_TOOLS, STAGE2_TOOLS, _GUARD_CONSEQUENCE, _annotate_reproductions, _mcp, _sandbox_audit, _stage_meta, _tool_call_ledger, _unbacked_findings


def _msgs(*calls):
    """A minimal message stream: one assistant tool_use plus its result."""
    out = []
    for i, (name, inp, result) in enumerate(calls):
        tid = f"toolu_{i}"
        out.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": tid, "name": name, "input": inp}]}})
        out.append({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": tid,
             "content": [{"type": "text", "text": result}]}]}})
    return out


# ---------------------------------------------------------------- FIX 7 -----

class TestEachStageIsScoredAgainstItsOwnLedger:
    """A stage-1-only tool cannot appear in stage 2's ledger. Ever.

    `check_table` is one of 15 tools registered for the sweep and not for the
    editorial pass (with check_summation, check_regression, grim_percentage,
    rivets_anova and ten others). Scoring the sweep's findings against stage
    2's ledger therefore measures the difference between two allowlists, not
    anything about the paper.

    MEASURED on the archived runs under eval/ground_truth/papers/*/
    forensic_review_specificity/, whose sandbox_audit.json files were written
    by the union rule:

        10.3389--fpsyg.2019.02949    headline 6 unbacked, stage-1 truth 0
        10.3349--ymj.2009.50.1.55    headline 5 unbacked, stage-1 truth 0
        10.1007--s11031-011-9216-y   headline 8 unbacked, stage-1 truth 3

    On 10.1002--hbm.26595 wave 3 one of the six false breaches was against the
    published `suspicious` finding `text_vs_figure4a_correlation_mismatch`,
    which a `check_table` call in stage 1 had backed.
    """

    FINDINGS = [{"id": "t1_reconcile", "technique": "reconcile",
                 "severity": "suspicious", "location": "Table 1"}]

    def _result(self):
        return {
            "report": "x",
            "findings": {"findings": list(self.FINDINGS)},
            "report_obj": {"findings": [
                {"title": "T", "severity": "suspicious",
                 "stage1_finding_ids": ["t1_reconcile"]}]},
            # The sweep ran the check. The editorial pass could not have.
            "stage1": {"messages": _msgs(
                (_mcp("check_table"), {"cells": []}, '{"severity": "suspicious"}'))},
            "stage2": {"messages": _msgs(
                (_mcp("statcheck"), {"text": "t(20)=2.1, p=.04"}, "{}"))},
            "run_meta": {},
        }

    def test_check_table_is_stage_1_only(self):
        """The premise. If this ever changes the measurement below is stale."""
        assert _mcp("check_table") in STAGE1_TOOLS
        assert _mcp("check_table") not in STAGE2_TOOLS

# ---------------------------------------------------------------- FIX 8 -----

class TestHarnessPlumbingIsNotABreach:
    """Every `BREACH (surface)` in this repo's archive is StructuredOutput.

    Counted across the eight sandbox_audit.json files written before the
    harness bucket existed: 21 of 21 unvalidated calls are StructuredOutput,
    e.g. 10.1001--jamanetworkopen.2023.37679 (2 in stage 1, 1 in stage 2) and
    10.1002--ajcp.70049 (1 and 1). StructuredOutput is HOW a schema-constrained
    answer is returned -- it is mandatory and it computes nothing -- and `Read`
    is on the declared allowlist. An audit that fires on every clean run
    teaches its reader to skip it.
    """

    def test_structured_output_is_classified_as_harness(self):
        led = _tool_call_ledger(_msgs(("StructuredOutput", {}, "{}")), STAGE1_TOOLS)
        assert led[0]["surface"] == "harness"

    def test_a_run_that_only_returns_its_answer_is_clean(self):
        a = _sandbox_audit(_tool_call_ledger(_msgs(
            (_mcp("grim_check"), {}, "x"),
            ("Read", {"file_path": "body.md"}, "x"),
            ("StructuredOutput", {}, "{}"),
        ), STAGE1_TOOLS), STAGE1_TOOLS)
        assert a["level"] == "clean"
        assert a["n_unvalidated"] == 0 and a["n_surface"] == 0

    def test_a_real_surface_extension_is_still_caught(self):
        a = _sandbox_audit(_tool_call_ledger(
            _msgs(("ToolSearch", {"query": "select:grim_check"}, "x")),
            STAGE1_TOOLS), STAGE1_TOOLS)
        assert a["level"] == "surface" and a["n_surface"] == 1


# --------------------------------------------------------------- FIX 13 -----

#: Passes `validate_reproduction` -- `metascience`, a known subcommand, no
#: placeholders -- and exits 2. `expected_total` is not a parameter; the tool
#: takes `expected_sum`. The verb-era form of this mistake (`--expected-total`)
#: accounted for 57 of the archive's failures.
RUNS_BUT_FAILS = ("metascience tool run check_summation --json "
                  """'{"values": [1, 2, 3], "expected_total": 100}'""")
ACTUALLY_RUNS = ("metascience tool run grim_check --json "
                 """'{"mean": 5.5, "n": 30, "decimals": 1, "data_type": "likert"}'""")


class TestReproductionsAreExecuted:
    """MEASURED by running all 523 distinct reproduction strings in the
    archive: 60 (11.5%) exit 0, 352 (67.3%) pass the static check and then
    exit non-zero, 111 (21.2%) fail the static check. The static gate cleared
    412 of 523 and only 60 of those 412 actually run.
    """

    def test_the_static_check_alone_passes_the_broken_command(self):
        """The old behaviour, reproduced against the same command."""
        from forensic_metascience_ai_toolkit.evaluation.deterministic import validate_reproduction
        assert validate_reproduction(RUNS_BUT_FAILS)["valid"] is True

    def test_executing_it_suppresses_it(self):
        r = {"findings": {"findings": [{"id": "f1", "reproduction": RUNS_BUT_FAILS}]},
             "run_meta": {}}
        summary = _annotate_reproductions(r)
        f = r["findings"]["findings"][0]
        assert f["reproduction_valid"] is False
        assert "exited 2" in f["reproduction_problem"]
        assert summary["n_ran_failed"] == 1 and summary["executed"] is True

    def test_a_command_that_runs_is_kept(self):
        r = {"findings": {"findings": [{"id": "f1", "reproduction": ACTUALLY_RUNS}]},
             "run_meta": {}}
        summary = _annotate_reproductions(r)
        assert r["findings"]["findings"][0]["reproduction_valid"] is True
        assert summary["n_ran_ok"] == 1

    def test_the_paid_subcommands_are_never_executed(self, monkeypatch):
        """`metascience analyze` is a full two-stage paid run. Executing one to
        check a `Reproduce:` line would launch it from inside the build of the
        report that line belongs to. `run_reproduction`'s premise -- "a pure
        local computation with no network access" -- does not hold for
        analyze/batch/eval/preflight."""
        import forensic_metascience_ai_toolkit.agent as agent

        def _boom(command, timeout=90):
            raise AssertionError(f"executed a paid subcommand: {command}")

        monkeypatch.setattr(agent, "_run_repro_cached", _boom)
        for verb in ("analyze", "batch", "eval", "preflight", "image-sweep", "review-write"):
            r = {"findings": {"findings": [
                {"id": "f1", "reproduction": f"metascience {verb} paper.pdf"}]},
                 "run_meta": {}}
            _annotate_reproductions(r)

    def test_execute_false_keeps_the_static_verdict(self):
        r = {"findings": {"findings": [{"id": "f1", "reproduction": RUNS_BUT_FAILS}]},
             "run_meta": {}}
        _annotate_reproductions(r, execute=False)
        assert r["findings"]["findings"][0]["reproduction_valid"] is True


class TestTheHeadlineIsAnnotatedToo:
    """report.schema.json REQUIRES a `reproduction` on the headline, but the
    annotator only ever walked `findings`. Absence is not False, so the single
    most prominent command in the review -- the one a reader is most likely to
    paste -- was printed verbatim whatever it did.

    `report.md` has since stopped printing any reproduction command, headline
    included, so the renderer test below asserts silence. The annotation is what
    still matters: `findings.json` and the viewer bundle read
    `reproduction_valid` off the headline, and the viewer refuses to offer a
    command the write path marked invalid.

    The fixture used to put the headline under `report_obj`, the serial
    pipeline's editorial report. That writer and `report.schema.json` were
    deleted in v1.27.0 and the annotator stopped walking `report_obj` on
    2026-09-05 (tests/test_repro_entries_v2.py); the headline walk itself is
    unchanged and is exercised here on the one document that still exists."""

    def _result(self, cmd):
        return {"findings": {"headline": {"statement": "s", "reproduction": cmd},
                             "findings": []},
                "run_meta": {}}

    def test_a_broken_headline_command_is_suppressed(self):
        r = self._result(RUNS_BUT_FAILS)
        summary = _annotate_reproductions(r)
        head = r["findings"]["headline"]
        assert head["reproduction_valid"] is False
        # COUNTED, AND COUNTED AS WHAT IT IS. This asserted `n_findings == 1`
        # on a result holding zero findings -- which is how `run_meta.json`
        # came to publish `reproducibility.n_findings: 25` beside 24 findings,
        # and how `bundle.py` printed "13 of 25 reproduction commands do not
        # run" over a denominator that was not the number of findings. The
        # headline is still walked and still checked; it is just no longer
        # added to a count named for something else.
        assert summary["n_targets"] == 1, "the headline must be counted"
        assert summary["n_headline"] == 1
        assert summary["n_findings"] == 0, "there are no findings in this result"

    def test_a_working_headline_command_survives(self):
        r = self._result(ACTUALLY_RUNS)
        _annotate_reproductions(r)
        assert r["findings"]["headline"]["reproduction_valid"] is True

# --------------------------------------------------------------- FIX 36 -----

class TestCacheTokensAreRecorded:
    """Cache tokens are separate counters, not a subset of `input_tokens`, and
    they dominate spend. MEASURED on the stage-1 sweep of
    eval/ground_truth/papers/10.3389--fpsyg.2019.02949: input_tokens 22,
    cache_creation_input_tokens 171,926, cache_read_input_tokens 1,176,684,
    cost $4.30. run_meta.json recorded 22 input tokens for that stage.
    """

    STAGE = {
        "cost_usd": 4.300558, "input_tokens": 22, "output_tokens": 79659,
        "cache_creation_input_tokens": 171926, "cache_read_input_tokens": 1176684,
        "wall_seconds": 847.6, "return_code": 0, "is_error": False, "messages": [],
    }

    def test_both_counters_are_recorded(self):
        meta = _stage_meta(dict(self.STAGE), "opus")
        assert meta["cache_creation_input_tokens"] == 171926
        assert meta["cache_read_input_tokens"] == 1176684

    def test_they_dominate_the_input_count_that_used_to_be_the_whole_record(self):
        meta = _stage_meta(dict(self.STAGE), "opus")
        cached = (meta["cache_creation_input_tokens"] + meta["cache_read_input_tokens"])
        assert cached > 60_000 * meta["input_tokens"]

    def test_a_stage_without_them_still_builds(self):
        """Results assembled by older paths, and every hand-built fixture, have
        no such key. A KeyError here would lose a paid analysis."""
        stage = {k: v for k, v in self.STAGE.items()
                 if not k.startswith("cache_")}
        meta = _stage_meta(stage, "opus")
        assert meta["cache_creation_input_tokens"] == 0
        assert meta["cache_read_input_tokens"] == 0


# --------------------------------------------------------------- FIX 44 -----

class TestTheDataTypeConsequenceIsWhatTheCodeDoes:
    """The claim was "GRIM/GRIMMER/SPRITE ran assuming INTEGER data on a 1-7
    scale ... (verified: systolic BP 128.43 +/- 15.21 returns `impossible`)".
    Both halves had gone stale, and a stale "verified" is worse than silence.
    """

    @pytest.mark.parametrize("fn,args", [
        ("grim", (128.43, 100)),
        ("grimmer", (128.43, 15.21, 100)),
        ("sprite", (128.43, 15.21, 100)),
    ])
    def test_the_defaulted_guard_refuses_rather_than_accuses(self, fn, args):
        from forensic_metascience_ai_toolkit.registry import BY_NAME

        name = {"grim": "grim_check", "grimmer": "grimmer_check",
                "sprite": "sprite_reconstruct"}[fn]
        spec = BY_NAME[name]
        default = next(p.default for p in spec.params if p.name == "data_type")
        assert default == "unknown", "the guard's default is the thing under test"
        out = {"grim": lambda: spec.fn(*args, data_type=default),
               "grimmer": lambda: spec.fn(*args, data_type=default),
               "sprite": lambda: spec.fn(*args, data_type=default)}[fn]()
        assert out["severity"] == "indeterminate"
        assert out.get("applicable") is False

    def test_asserting_integer_is_where_the_accusation_comes_from(self):
        """Measured for the replacement text: `suspicious` on these numbers
        with an assumed bound, and `impossible` at 29 of 495 sample sizes.

        (Was 43 before the truncation-rescue bound gate: 14 of those
        `impossible` verdicts were truncation-consistent means whose sums lay
        outside the ASSUMED 1-7 scale -- verdicts riding on our invented
        bound, now correctly capped at `suspicious`. With bound_source=
        'stated' the sweep is still 495/495 `impossible`.)"""
        from forensic_metascience_ai_toolkit.tools.grim import grim_test

        assert grim_test(128.43, 100, data_type="likert")["severity"] == "suspicious"
        # `discreteness_source="stated"` holds the measurement fixed at what it
        # was written to measure: what the DATA_TYPE assertion alone buys. From
        # 2026-08-10 a second premise is also required (the observations must be
        # shown to be whole numbers), and the line below records what happens
        # without it -- which is a sharper statement of this test's own thesis.
        n_impossible = sum(grim_test(128.43, n, data_type="likert",
                                     discreteness_source="stated")["severity"]
                           == "impossible" for n in range(5, 500))
        assert n_impossible == 29
        # THE DISCRETENESS GATE, measured on the same sweep: asserting `likert`
        # on a systolic blood pressure no longer accuses at any n. 29 potential
        # false accusations to 0, at the cost of needing the paper to say its
        # data are integers before we use the word `impossible`.
        assert sum(grim_test(128.43, n, data_type="likert")["severity"] == "impossible"
                   for n in range(5, 500)) == 0

    def test_the_consequence_text_no_longer_asserts_the_stale_claim(self):
        text = _GUARD_CONSEQUENCE["data_type"]
        assert "ran assuming INTEGER data on a 1-7 scale" not in text
        assert "indeterminate" in text
