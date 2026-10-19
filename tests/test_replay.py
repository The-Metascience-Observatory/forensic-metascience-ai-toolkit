"""Measure a code change against real runs, instead of guessing or paying.

Every fix in this repo has faced "would that actually have changed anything?",
and until 2026-08-12 the only answer was a fresh paid run: $9-10, ~26 minutes,
and a non-deterministic model in the middle, so even then a fix could not be
told apart from a re-roll.

But the model is only half the pipeline. Once it has chosen a tool and its
arguments, everything downstream is a pure function of those arguments -- and
every archived run records them. So the deterministic half replays exactly.

Both halves of that claim are load-bearing and both are tested here: the replay
must actually re-execute (a harness that silently skipped everything would
report a serene "no verdict moved" forever), and it must classify a moved
verdict by DIRECTION -- because the first corpus replay reported "111 got
worse" when 107 of those were `consistent -> indeterminate`, a REFUSAL rather
than an accusation, and the opposite of a regression under this project's
cardinal rule.
"""
import json
import pathlib

import pytest

from metascience_agent.evaluation import replay

REPO = pathlib.Path(__file__).resolve().parent.parent
CORPUS = REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on"


class TestItActuallyReplays:
    @pytest.fixture(scope="class")
    def corpus(self):
        if not CORPUS.exists():
            pytest.skip("archived corpus not present in this checkout")
        return replay.replay_corpus(CORPUS)

    def test_it_re_executes_a_lot_of_real_calls(self, corpus):
        """The guard against a serene harness. If this collapses, every other
        replay result is vacuously reassuring."""
        assert corpus["n_replayed"] > 300, corpus["n_replayed"]

    def test_it_finds_the_runs_without_double_counting_bundles(self, corpus):
        """A bundle holds a COPY of its run's ledger under `analysis/`, so a
        naive walk replays every run twice. The first corpus replay reported 13
        runs against an archive of 11."""
        n_ledgers = len(list(CORPUS.rglob("toolcalls.stage1.json")))
        assert corpus["n_runs"] < n_ledgers, (
            f"{corpus['n_runs']} runs from {n_ledgers} ledger files -- bundle "
            "copies are being replayed as if they were separate runs")

    def test_an_unreplayable_call_is_reported_not_silently_dropped(self, corpus):
        """A skipped call must never read as agreement. This repo has twice
        published a coverage figure whose denominator was effort."""
        assert corpus["n_skipped"] > 0, "expected some non-replayable calls"
        for run in corpus["runs"]:
            for s in run["skipped"]:
                assert s.get("why"), s

    def test_a_missing_ledger_is_an_error_and_not_an_empty_pass(self, tmp_path):
        out = replay.replay_run(tmp_path)
        assert out["error"]
        assert out["n_calls"] == 0


class TestTheDirectionSplit:
    """The classification that stopped a wrong headline."""

    def _summary(self, before, after):
        return {"runs": [{"paper": "p", "run": "r", "changed": [
            {"tool": "t", "seq": 1, "locator": "",
             "before": {"severity": before}, "after": {"severity": after}}]}]}

    def test_clean_to_refusal_is_NOT_counted_as_a_regression(self):
        """`consistent -> indeterminate` means we stopped claiming to know
        something. Under the cardinal rule that is a good outcome, and calling
        it a regression is how a correct fix gets reverted."""
        s = replay.classify(self._summary("consistent", "indeterminate"))
        assert len(s["refused"]) == 1
        assert not s["became_accusatory"]

    def test_clean_to_accusation_IS_flagged(self):
        for tier in ("suspicious", "highly_suspicious", "impossible"):
            s = replay.classify(self._summary("consistent", tier))
            assert len(s["became_accusatory"]) == 1, tier

    def test_refusal_to_accusation_is_flagged_too(self):
        s = replay.classify(self._summary("indeterminate", "suspicious"))
        assert len(s["became_accusatory"]) == 1

    def test_an_accusation_withdrawn_lands_in_relieved(self):
        for before in ("suspicious", "highly_suspicious", "impossible"):
            s = replay.classify(self._summary(before, "consistent"))
            assert len(s["relieved"]) == 1, before

    def test_a_softened_accusation_is_relief_not_a_regression(self):
        s = replay.classify(self._summary("impossible", "indeterminate"))
        assert len(s["relieved"]) == 1
        assert not s["became_accusatory"]

    def test_the_render_leads_with_what_became_accusatory(self):
        text = replay.render({
            "n_replayed": 1, "n_runs": 1, "n_changed": 1,
            **self._summary("consistent", "suspicious")})
        assert "BECAME ACCUSATORY" in text
        assert text.index("BECAME ACCUSATORY") < len(text)


class TestTheVerdictExtractor:
    def test_it_reads_the_top_level_severity(self):
        assert replay._verdict_of({"severity": "consistent"}) == {
            "severity": "consistent"}

    def test_it_reads_per_row_severities_from_a_batch(self):
        got = replay._verdict_of({"results": [{"severity": "consistent"},
                                              {"severity": "suspicious"}]})
        assert got["row_severities"] == ["consistent", "suspicious"]

    def test_it_ignores_prose_so_a_reworded_explanation_is_not_a_diff(self):
        a = {"severity": "consistent", "explanation": "one wording"}
        b = {"severity": "consistent", "explanation": "a completely different wording"}
        assert replay._verdict_of(a) == replay._verdict_of(b)

    def test_a_truncated_archived_result_yields_nothing_to_diff_against(self):
        assert replay._archived_payload({"result_truncated": True,
                                         "result": '{"severity": "x"}'}) is None

    def test_it_parses_a_json_string_result(self):
        assert replay._archived_payload(
            {"result": json.dumps({"severity": "suspicious"})}) == {
                "severity": "suspicious"}
