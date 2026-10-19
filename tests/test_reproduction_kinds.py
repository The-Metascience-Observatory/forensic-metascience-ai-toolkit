"""A reproduction may be a CLI command, a persisted script, or nothing at all.

Regression for three defects measured on the 2026-09-01 flagged batch, all of
the house shape: two sides of one comparison written at different times.
"""

from metascience_agent import agent
from metascience_agent.evaluation.deterministic import classify_reproduction


class TestClassify:
    def test_trailing_no_command_disclaimer_is_recognised(self):
        # 11 of 26 invalid rows. `_NO_COMMAND_RE` anchors at the start, so the
        # model's honest answer failed with "must invoke `metascience`".
        assert classify_reproduction(
            "Reading of Table 2 against the Results; no command applies."
        ) == "no_command_applies"

    def test_a_typo_still_fails_loudly(self):
        # THE DIRECTION THAT MATTERS. Recognising a disclaimer must never
        # launder a BROKEN command into "there was nothing to check".
        assert classify_reproduction("metascienc grim 20.0 223") == "command"
        assert classify_reproduction("Derived by hand from Table 2") == "command"

    def test_script_citation_is_its_own_kind(self):
        # `science_error.md` INSTRUCTS this answer; the validator demanded
        # `metascience` and stamped the prompt's own prescription invalid.
        assert classify_reproduction(
            "Computed in analysis_code/001_roster.py (run_python_script)"
        ) == "script"

    def test_prose_naming_a_bare_py_file_is_not_a_citation(self):
        assert classify_reproduction("see helper.py for the method") != "script"


class TestScriptValidation:
    def _finding(self, cmd):
        return {"findings": {"findings": [
            {"id": "f1", "severity": 2, "reproduction": cmd}]}}

    def test_existing_script_validates(self, tmp_path):
        (tmp_path / "analysis_code").mkdir()
        (tmp_path / "analysis_code" / "001_roster.py").write_text("x = 1\n")
        doc = self._finding("analysis_code/001_roster.py")
        agent._annotate_reproductions(doc, execute=False, paper_dir=tmp_path)
        row = doc["findings"]["findings"][0]
        assert row["reproduction_kind"] == "script"
        assert row["reproduction_valid"] is True

    def test_missing_script_is_invalid_and_says_so(self, tmp_path):
        doc = self._finding("analysis_code/999_absent.py")
        agent._annotate_reproductions(doc, execute=False, paper_dir=tmp_path)
        row = doc["findings"]["findings"][0]
        assert row["reproduction_valid"] is False
        assert "not found" in row["reproduction_problem"]

    def test_unverifiable_is_none_not_true(self):
        # FAILS CLOSED. "We did not check" and "we checked and it is there"
        # are different facts, and only the second is one a reader acts on.
        doc = self._finding("analysis_code/001_roster.py")
        agent._annotate_reproductions(doc, execute=False, paper_dir=None)
        row = doc["findings"]["findings"][0]
        assert row["reproduction_valid"] is None
        assert "not verified" in row["reproduction_problem"]


class TestAgreementAcrossVocabularies:
    """A v2 finding's NUMERIC severity against a tool's 5-enum STRING.

    `agrees = (said == claim)` compared `"suspicious"` with `"2"`, so on every
    v2 row with a readable verdict the toolkit told the reader its own command
    disagreed with its own finding. Measured 2026-09-01: it fired on the
    headline `check_count_percent` hit that the tool and finding AGREE about.
    """

    CMD = ("metascience tool run check_count_percent --json "
           """'{"count": 278, "percentage": 83, "n": 324, "decimals": 0}'""")

    def _run(self, **kw):
        from metascience_agent.evaluation.deterministic import run_reproduction
        return run_reproduction(self.CMD, **kw)

    def test_tool_and_finding_agreeing_is_not_a_disagreement(self):
        out = self._run(claimed_severity=2, claimed_outcome="problem")
        assert out["reported_severity"] == "suspicious"
        assert out["agrees"] is True and out["valid"] is True

    def test_a_real_disagreement_still_fails(self):
        # The check must keep its teeth: a tool saying this is a problem under
        # a finding claiming a pass is exactly what it exists to catch.
        out = self._run(claimed_severity=2, claimed_outcome="pass")
        assert out["agrees"] is False and out["valid"] is False

    def test_missing_outcome_is_unknown_never_false(self):
        # We do not manufacture a disagreement out of a vocabulary we could
        # not read.
        assert self._run(claimed_severity=2)["agrees"] is None

    def test_v1_string_claims_still_compare_exactly(self):
        assert self._run(claimed_severity="suspicious")["agrees"] is True
        assert self._run(claimed_severity="impossible")["agrees"] is False

    def test_the_bridge_is_imported_not_restated(self):
        # The defect was a second copy of a vocabulary. Assert we read the one
        # stated definition, so this cannot drift again.
        import inspect

        from metascience_agent.evaluation import deterministic
        src = inspect.getsource(deterministic.run_reproduction)
        assert "OUTCOME_FROM_FIVE" in src
        assert '"suspicious": 3' not in src


class TestFigureBlindnessIsDeclared:
    """Figure-blindness is true by construction; it must not depend on the
    model noticing. Measured 2026-09-01: clinem--dgag124's CONSORT screening
    counts exist only in Figure 1A, and the run said so only because the model
    wrote it into a tool-call description.
    """

    def _limitations(self, figures):
        import inspect

        from metascience_agent import parallel
        src = inspect.getsource(parallel)
        assert "figure values were not extracted for the numeric/science analysts" in src, "the declaration is gone"
        assert "if not figures:" in src, "it must be conditional on the flag"
        return src

    def test_the_declaration_exists_and_is_conditional(self):
        self._limitations(False)

    def test_it_names_what_a_reader_would_otherwise_assume(self):
        src = self._limitations(False)
        # The honest failure is silence reading as a pass, so the wording has
        # to say the value was neither checked NOR counted as unchecked.
        assert "neither checked nor counted as unchecked" in src


class TestTheGeneratorRunsOnV2Findings:
    """`reproduction_command` builds the invocation from the check's own
    inputs so the model never guesses a CLI signature. It keyed on
    `inputs["tool"]` -- a v1 shape -- so on v2 it never fired: measured
    2026-09-01, `reproduction_source` was None on 150 of 150 findings.
    """

    def _annotate(self, finding):
        doc = {"findings": {"findings": [finding]}}
        agent._annotate_reproductions(doc, execute=False)
        return doc["findings"]["findings"][0]

    def test_a_v2_finding_gets_a_generated_command(self):
        row = self._annotate({
            "id": "f1", "severity": 2, "technique": "check_count_percent",
            "inputs": {"count": 278, "percentage": 83, "n": 324,
                       "decimals": 0},
            "reproduction": "metascience check-count-percent --count 278",
        })
        assert row.get("reproduction_source") == "generated_from_registry"
        # Since Phase 3b: the generic command, which runs through the gates.
        assert row["reproduction"].startswith(
            "metascience tool run check_count_percent --json ")
        # The model's guess must be REPLACED, not appended to.
        assert "--count 278" not in row["reproduction"]

    def test_a_technique_naming_no_tool_keeps_the_models_string(self):
        # It must refuse rather than invent an invocation.
        row = self._annotate({
            "id": "f2", "severity": 2, "technique": "internal_contradiction",
            "inputs": {"a": 1},
            "reproduction": "Reading of Table 2; no command applies.",
        })
        assert row.get("reproduction_source") != "generated_from_registry"

    def test_a_refusal_says_why(self):
        # A refusal keeps the model's string AND records the reason, so a
        # missing argument is a legible gap rather than a silent fallback.
        row = self._annotate({
            "id": "f4", "severity": 2, "technique": "check_count_percent",
            "inputs": {"count": 278, "percentage": 83},
            "reproduction": "metascience check-count-percent 278 83",
        })
        assert row.get("reproduction_source") == "model_written"
        assert "lack required argument(s) ['n'" in row.get(
            "reproduction_not_generatable", "")

    def test_an_explicit_tool_key_still_wins(self):
        row = self._annotate({
            "id": "f3", "severity": 2, "technique": "not_the_tool",
            "inputs": {"tool": "check_count_percent", "count": 278,
                       "percentage": 83, "n": 324, "decimals": 0},
            "reproduction": "metascience bogus",
        })
        assert row.get("reproduction_source") == "generated_from_registry"
        assert "tool run check_count_percent" in row["reproduction"]

    def test_structured_input_now_has_a_command(self):
        """The per-tool generator refused any list argument (54% of calls had
        no command); JSON carries it."""
        row = self._annotate({
            "id": "f5", "severity": 2, "technique": "grim_sweep",
            "inputs": {"values": [12.5, 37.5], "decimals": 1, "n_min": 2,
                       "n_max": 40, "n_max_source": "stated"},
        })
        assert row.get("reproduction_source") == "generated_from_registry", row
        assert '"values":[12.5,37.5]' in row["reproduction"]

    def test_the_backing_call_is_replayed_not_the_restatement(self):
        """With a ledger, the arguments the TOOL received win over the model's
        `inputs`, and the finding records which call it replays."""
        call = {"seq": 7, "tool_short": "grim_check", "validated": True,
                "surface": "forensic_mcp",
                "input": {"mean": 3.53, "n": 30, "decimals": 2,
                          "data_type": "likert", "source_quote": "M = 3.53"},
                "result": '{"severity": "consistent"}'}
        doc = {"findings": {"findings": [{
            "id": "f6", "severity": 1, "technique": "grim_check",
            "producer": "tool_expert", "inputs": {"mean": 3.53, "n": 30}}]}}
        agent._annotate_reproductions(doc, execute=False,
                                      ledgers={"tool_expert": [call]})
        row = doc["findings"]["findings"][0]
        assert row["reproduction_source"] == "generated_from_tool_call"
        assert row["reproduction_call"] == 7
        assert '"data_type":"likert"' in row["reproduction"]
        assert "source_quote" not in row["reproduction"]   # not the arithmetic


class TestAnOmissionAndADisclaimerAgree:
    """The model has two honest ways to say "this is a reading": write the
    disclaimer, or leave the field off. They used to get opposite verdicts.
    Measured 2026-09-01: 18 of 150 findings, all `model_reading`, all
    non-computational techniques, all stamped `reproduction_valid: false`.
    """

    def _row(self, technique, reproduction=None):
        f = {"id": "f1", "severity": 2, "technique": technique,
             "computed_by": "model_reading"}
        if reproduction is not None:
            f["reproduction"] = reproduction
        doc = {"findings": {"findings": [f]}}
        agent._annotate_reproductions(doc, execute=False)
        return doc["findings"]["findings"][0]

    def test_omitting_the_field_is_not_a_failure(self):
        for tech in ("internal_contradiction", "not_computational",
                     "factual_claim"):
            row = self._row(tech)
            assert row["reproduction_valid"] is None, tech
            assert row["reproduction_kind"] == "no_command_applies", tech

    def test_the_two_honest_answers_now_agree(self):
        omitted = self._row("not_computational")
        stated = self._row("not_computational", "No command applies.")
        assert omitted["reproduction_valid"] == stated["reproduction_valid"]

    def test_a_computational_finding_with_no_command_still_fails(self):
        # THE DIRECTION THAT MATTERS. A tool-backed check that cannot say how
        # it was computed is exactly what this exists to catch.
        row = self._row("grim_sweep")
        assert row["reproduction_valid"] is False

    def test_membership_is_read_from_the_spec(self):
        import inspect
        src = inspect.getsource(agent._annotate_reproductions)
        assert "NON_TOOL_TECHNIQUES" in src
        assert "internal_contradiction\"," not in src, "second list re-stated"


class TestScriptCitationDuringTheRun:
    """`run_python_script` writes under analysis_code/<run_slug>/ and cites the
    flattened path the archive will have; annotation runs before the move.
    Both apple_cider runs of 2026-10-13 stamped every citation 'not found'."""

    def test_the_run_directory_is_where_the_script_is_found(self, tmp_path):
        (tmp_path / "analysis_code" / "sonnet-abc").mkdir(parents=True)
        (tmp_path / "analysis_code" / "sonnet-abc" / "001_x.py").write_text("print(1)")
        doc = {"findings": {"findings": [{
            "id": "s1", "technique": "factual_claim", "producer": "science_error",
            "reproduction": "analysis_code/001_x.py"}]}}
        agent._annotate_reproductions(doc, execute=False, paper_dir=tmp_path,
                                      run_slug="sonnet-abc")
        row = doc["findings"]["findings"][0]
        assert row["reproduction_kind"] == "script" and row["reproduction_valid"] is True

    def test_without_the_slug_it_is_still_not_found(self, tmp_path):
        (tmp_path / "analysis_code" / "sonnet-abc").mkdir(parents=True)
        (tmp_path / "analysis_code" / "sonnet-abc" / "001_x.py").write_text("print(1)")
        doc = {"findings": {"findings": [{
            "id": "s1", "technique": "factual_claim", "producer": "science_error",
            "reproduction": "analysis_code/001_x.py"}]}}
        agent._annotate_reproductions(doc, execute=False, paper_dir=tmp_path)
        assert doc["findings"]["findings"][0]["reproduction_valid"] is False
