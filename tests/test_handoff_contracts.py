"""Positive controls for the handoff audit.

The module's own rule, inherited from `inertness.py`: every contract must have a
test that CONSTRUCTS the violation and asserts the audit reports it. A detector
that cannot fire returns zero exactly as convincingly as a healthy pipeline.

So each contract below is exercised three ways -- owed and arrived, owed and
missing, and not owed -- because a detector that only ever sees healthy runs is
indistinguishable from one that always returns `satisfied`.
"""
from __future__ import annotations

import json

import pytest

from forensic_metascience_ai_toolkit import handoff_contracts as H


def _run(**over):
    """A minimally healthy run: every contract satisfied."""
    base = {
        "review_dir": "/tmp/x",
        "has_paper_dir": True,
        "report_md": "## Reporting conventions\n\n- **1 of 13** ...\n",
        "findings_v2": {
            "checks_tally": {
                "rounding_convention": {"n_fit_only_under_truncation": 3,
                                        "n_granularity_checks": 13},
                "sd_convention": {"n_fit_only_under_population_sd": 0,
                                  "n_granularity_checks": 13},
                "grace": {"n_rescued": 3, "n_items": 13},
            },
            "findings": [{"slug": "f1", "anchors": [{"where": "table"}]}],
            "channels": {"tool_expert": {"state": "ran", "detail": ""}},
        },
        "value_register": {
            "n_values": 42,
            "coverage": {"n_checked": 1, "n_no_applicable_tool": 2,
                         "n_silent": 0, "states_are_exclusive": True},
        },
    }
    base.update(over)
    return base


def _state(run, producer):
    for r in H.audit(run):
        if r.contract.producer == producer:
            return r.state
    raise AssertionError(f"no contract for {producer}")


class TestTheHealthyRunIsClean:
    def test_nothing_is_violated_when_every_payload_arrives(self):
        assert not [r for r in H.audit(_run()) if r.state == H.VIOLATED]


class TestGraceThePayloadThatMotivatedThis:
    """`grace.record` IS called, so `inertness` correctly says nothing. The
    defect is that its output reaches no reader, which only a run artifact
    shows."""

    def test_it_fires_when_rescues_happened_and_no_grace_arrived(self):
        run = _run()
        del run["findings_v2"]["checks_tally"]["grace"]
        assert _state(run, "grace.py") == H.VIOLATED

    def test_an_empty_grace_block_is_not_an_arrival(self):
        """`{"grace": {}}` is the shape a broken handoff writes. A contract that
        tested for the KEY would pass on it."""
        run = _run()
        run["findings_v2"]["checks_tally"]["grace"] = {}
        assert _state(run, "grace.py") == H.VIOLATED

    def test_a_zero_count_is_not_an_arrival_either(self):
        run = _run()
        run["findings_v2"]["checks_tally"]["grace"] = {"n_rescued": 0}
        assert _state(run, "grace.py") == H.VIOLATED

    def test_per_finding_records_also_satisfy_it(self):
        run = _run()
        del run["findings_v2"]["checks_tally"]["grace"]
        run["findings_v2"]["findings"][0]["grace"] = {"rescued": True,
                                                      "residual": 0.004}
        assert _state(run, "grace.py") == H.SATISFIED

    def test_no_rescues_means_nothing_was_owed(self):
        """The state that keeps this safe. Most papers rescue nothing, and a
        detector without this fires on all of them and gets switched off."""
        run = _run()
        del run["findings_v2"]["checks_tally"]["grace"]
        run["findings_v2"]["checks_tally"]["rounding_convention"][
            "n_fit_only_under_truncation"] = 0
        assert _state(run, "grace.py") == H.PRECONDITION_ABSENT

    def test_the_precondition_survives_the_producer_being_wholly_silent(self):
        """Circularity check, stated behaviourally rather than by reading the
        source. If `owed` were derived from grace's own output, a producer that
        emitted nothing would report "nothing was owed" and the contract could
        never fire -- the bug wearing the detector's clothes.

        So: strip every trace of grace from the run and assert the precondition
        STILL holds, because it is computed by `agent.py` from the convention
        tally, which is independent of the module under test.
        """
        run = _run()
        run["findings_v2"]["checks_tally"].pop("grace")
        for f in run["findings_v2"]["findings"]:
            f.pop("grace", None)
        assert H._n_rescued_by_convention(run) > 0, (
            "the precondition must be computable with the producer silent")
        assert _state(run, "grace.py") == H.VIOLATED


class TestTheOtherContractsCanAllFire:
    @pytest.mark.parametrize("producer,break_it", [
        ("agent.py checks_tally", lambda r: r.update(report_md="## Findings\n")),
        ("values.py", lambda r: r["value_register"].update(n_values=0)),
        ("values.coverage", lambda r: r["value_register"]["coverage"].pop("n_silent")),
        ("anchors.py", lambda r: r["findings_v2"]["findings"][0].pop("anchors")),
        ("channels bookkeeping", lambda r: r["findings_v2"].update(channels={})),
    ])
    def test_each_contract_reports_its_own_violation(self, producer, break_it):
        run = _run()
        break_it(run)
        assert _state(run, producer) == H.VIOLATED

    def test_a_dropped_coverage_stratum_is_caught(self):
        """`states_are_exclusive` is the conservation flag; losing it turns
        coverage back into a claim."""
        run = _run()
        run["value_register"]["coverage"].pop("states_are_exclusive")
        assert _state(run, "values.coverage") == H.VIOLATED


class TestOurOwnFailureIsNeverAViolation:
    def test_an_unreadable_artifact_is_cannot_tell_not_violated(self, tmp_path):
        run = H.load_run(tmp_path)          # nothing on disk at all
        states = {r.state for r in H.audit(run)}
        assert H.VIOLATED not in states, (
            "an absent artifact is our gap, not a broken handoff")

    def test_a_corrupt_json_loads_as_None_rather_than_empty(self, tmp_path):
        (tmp_path / "findings.v2.json").write_text("{not json", encoding="utf-8")
        assert H.load_run(tmp_path)["findings_v2"] is None

    def test_a_raising_predicate_is_cannot_tell(self):
        bad = H.Contract(
            producer="x", payload="y", consumer="z", why="w",
            owed=lambda run: (_ for _ in ()).throw(RuntimeError("boom")),
            arrived=lambda run: True)
        assert H.audit(_run(), (bad,))[0].state == H.CANNOT_TELL


class TestTheRenderIsActionable:
    def test_violations_come_first(self):
        run = _run()
        del run["findings_v2"]["checks_tally"]["grace"]
        out = H.render(H.audit(run))
        assert out.index("VIOLATED") < out.index("[         ok]")

    def test_it_states_the_denominator(self):
        assert "of 6 contracts" in H.render(H.audit(_run()))

    def test_a_violation_names_the_payload_and_not_only_the_module(self):
        run = _run()
        del run["findings_v2"]["checks_tally"]["grace"]
        out = H.render(H.audit(run))
        assert "n_rescued" in out


class TestEveryContractIsDocumented:
    def test_each_says_what_breaks_when_it_stops(self):
        for c in H.CONTRACTS:
            assert len(c.why) > 80, (
                f"{c.producer}: `why` must say what silently breaks, so a "
                "reader can judge whether the contract is worth keeping")
            assert c.payload and c.consumer
