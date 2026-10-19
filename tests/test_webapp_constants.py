"""The generated TS constants cannot drift from their Python sources."""

from forensic_metascience_ai_toolkit import webapp_constants as W


class TestParity:
    def test_the_checked_in_file_matches_a_fresh_render(self):
        current = W.target_path().read_text()
        assert current == W.render(), (
            "webapp/lib/constants.gen.ts is stale -- run "
            "`metascience gen-webapp-constants` and commit the result")

    def test_the_drift_guard_can_fire(self, monkeypatch):
        """Known positive (LESSONS #4): mutate the ladder and the comparison
        MUST fail -- a byte-compare that always passes is indistinguishable
        from one comparing nothing."""
        from forensic_metascience_ai_toolkit import severity9
        real = severity9.as_json

        def mutated():
            j = real()
            j["levels"][0]["label"] = "MUTATED"
            return j
        monkeypatch.setattr(severity9, "as_json", mutated)
        assert W.target_path().read_text() != W.render()

    def test_the_checked_in_ladder_json_matches_a_fresh_render(self):
        current = W.ladder_json_path().read_text()
        assert current == W.render_ladder_json(), (
            "docs/severity_ladder.json is stale -- run "
            "`metascience gen-webapp-constants` and commit the result")

    def test_the_ladder_json_drift_guard_can_fire(self, monkeypatch):
        from forensic_metascience_ai_toolkit import severity9
        real = severity9.as_json

        def mutated():
            j = real()
            j["levels"][0]["web_summary"] = "MUTATED"
            return j
        monkeypatch.setattr(severity9, "as_json", mutated)
        assert W.ladder_json_path().read_text() != W.render_ladder_json()

    def test_both_artifacts_carry_the_same_ladder(self):
        """One payload, two encodings: the JSON must not be a stale fork of
        what the TS ships."""
        import json
        ladder = json.loads(W.ladder_json_path().read_text())
        ts = W.target_path().read_text()
        for level in ladder["levels"]:
            assert json.dumps(level["web_summary"])[1:-1] in ts
            assert level["boundaries"], f"level {level['n']} has no boundaries"

    def test_the_file_carries_the_decision_vocabularies(self):
        text = W.target_path().read_text()
        for probe in ("false_positive", "true_issue", "ran_result_discarded",
                      "legacyToNine", "GENERATED FILE"):
            assert probe in text
