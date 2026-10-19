"""The reproduction validator must run on GENERATED output, not just fixtures.

`validate_reproduction` and `check_reproductions` existed and were correct, but
were called only from the eval harness. Nothing in `write_review_outputs` or
`report_render` used them, so the pipeline wrote unrunnable commands and the
renderer printed them verbatim as "**Reproduce:** `...`".

A real run emitted `metascience recalc_independent_t --mean1 21.7 --sd1 4.899
--n1 24 ...` -- that is an MCP tool name with invented flags, not a CLI command,
and it errors immediately. The arithmetic in that finding was correct; only the
citation was malformed.

Graceful failure requirement: a malformed command must never be handed to a
reader as something to paste. `report.md` has since stopped printing a
reproduction command at all, so for that document the requirement is met by
silence; the verdict is still stamped for `findings.json` and the viewer, which
is where the requirement is now enforced (`bundle.reproHtml`).
"""
import json

from metascience_agent.agent import _annotate_reproductions
BAD = "metascience recalc_independent_t --mean1 21.7 --sd1 4.899 --n1 24"
GOOD = "metascience ttest 21.7 4.899 24 24.4 5.367 20 --reported-p 0.0396"


def _result(cmd):
    return {
        "report": "x",
        "findings": {"findings": [{"id": "f1", "reproduction": cmd}]},
        "run_meta": {},
    }


class TestAnnotation:
    def test_invalid_command_is_flagged(self):
        r = _result(BAD)
        summary = _annotate_reproductions(r)
        f = r["findings"]["findings"][0]
        assert f["reproduction_valid"] is False
        assert "unknown subcommand" in f["reproduction_problem"]
        assert summary["n_invalid"] == 1 and summary["n_valid"] == 0

    def test_valid_command_passes(self):
        r = _result(GOOD)
        summary = _annotate_reproductions(r)
        assert r["findings"]["findings"][0]["reproduction_valid"] is True
        assert summary["n_valid"] == 1 and summary["n_invalid"] == 0

    def test_summary_lands_in_run_meta(self):
        r = _result(BAD)
        _annotate_reproductions(r)
        assert r["run_meta"]["reproducibility"]["n_invalid"] == 1

    def test_no_findings_is_not_an_error(self):
        r = {"report": "x", "run_meta": {}}
        assert _annotate_reproductions(r)["n_findings"] == 0


