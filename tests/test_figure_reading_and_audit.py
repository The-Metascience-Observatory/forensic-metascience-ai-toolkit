"""Three defects found by an adversarial review of the wave-3 batch.

All three share a shape: the pipeline had the information and reported the
opposite. Figures were extracted to disk and the report said figures could not
be seen. Stage 2 recorded six unbacked findings and the audit said "clean". A
third of reproduction commands ran fine and were labelled unrunnable.
"""
import json

import pytest

from forensic_metascience_ai_toolkit.agent import _figures_were_read
from forensic_metascience_ai_toolkit.evaluation.deterministic import validate_reproduction
from forensic_metascience_ai_toolkit.report_render import FIGURE_BLINDNESS_NOTE, FIGURES_READ_NOTE


def _report():
    return {
        "headline": {"statement": "x", "severity": "suspicious",
                     "rests_on": "stated_constraint", "evidence": "e",
                     "reproduction": """metascience tool run grim_check --json '{"mean": 5.5, "n": 30, "decimals": 1, "data_type": "likert"}'"""},
        "verdict": "unresolved", "confidence": "high", "findings": [],
        "not_checked": [], "limitations": [], "coverage_summary": {},
    }


class TestTheReportMustNotLieAboutItsOwnCoverage:
    """`extract_figures` wrote six PNGs into the run directory and the report
    said "this agent reads text and tables only. It does not see figures."
    A false statement about our own coverage is the exact thing this document
    exists to catch in other people's work."""

    def test_the_note_distinguishes_printed_from_measured(self):
        """A value PRINTED on a panel is a reported value; one MEASURED off a
        mark has no last printed digit and no exact check may use it."""
        assert "PRINTED" in FIGURES_READ_NOTE and "MEASURED" in FIGURES_READ_NOTE


class TestFiguresWereRead:
    """Decided from the ledger, not from a flag: a flag records what we
    intended and the ledger records what happened."""

    def _ledger(self, *paths):
        return [{"tool_short": "Read", "input": {"file_path": p}} for p in paths]

    def test_reading_a_png_counts(self):
        assert _figures_were_read(self._ledger("figures/Figure_4_p009.png")) is True

    def test_case_does_not_matter(self):
        assert _figures_were_read(self._ledger("figures/FIG_2.PNG")) is True

    def test_reading_only_text_does_not_count(self):
        assert _figures_were_read(self._ledger("body.md", "paper.xml")) is False

    def test_extracting_without_reading_does_not_count(self):
        """This is the whole distinction. Extraction is not inspection."""
        led = [{"tool_short": "extract_figures", "input": {"pdf": "p.pdf"},
                "validated": True}]
        assert _figures_were_read(led) is False

    def test_an_empty_ledger_is_not_a_claim_to_have_read_anything(self):
        assert _figures_were_read([]) is False
        assert _figures_were_read(None) is False

    @pytest.mark.parametrize("paper", ["10.1002--eat.24415", "10.1002--hbm.26595",
                                       "10.1002--mpr.70006"])
    def test_the_real_wave3_runs_did_not_read_their_figures(self, paper):
        """Regression anchor. 27 Read calls across the three runs, not one of
        them a figure -- while six PNGs sat in one of the directories."""
        from pathlib import Path
        p = Path(f"tests/fixtures/papers/high_value_pdfs_to_run_on/{paper}/forensic_review_wave3/"
                 "toolcalls.stage1.json")
        if not p.exists():
            pytest.skip("run artefacts not present")
        assert _figures_were_read(json.loads(p.read_text())) is False


class TestReproductionValidatorDoesNotRejectWorkingCommands:
    """A ~35% false-positive rate on a real batch: 10 of 13, 8 of 10 and 11 of
    11 flagged commands were rejected over a brace inside a JSON payload. The
    report then printed "not runnable as written" beside a command that runs."""

    JSON_CMD = ("""metascience tool run multiplicity_report --json """
                """'{"alpha": 0.05, "family_label": "primary", """
                """"tests": [{"id":"M1","p_value":0.001}]}'""")

    def test_a_json_payload_is_not_a_placeholder(self):
        r = validate_reproduction(self.JSON_CMD)
        assert r["valid"] is True, r["problems"]

    def test_angle_brackets_inside_quotes_are_fine(self):
        r = validate_reproduction(
            """metascience tool run grim_check --json '{"mean": 5.5, "note": "<derived>"}'""")
        assert r["valid"] is True, r["problems"]

    def test_a_real_template_is_still_caught(self):
        """The fix must not be "stop checking"."""
        assert validate_reproduction("metascience grim <mean> <n>")["valid"] is False

    def test_an_ellipsis_is_still_caught_anywhere(self):
        """Unlike braces, `...` never legitimately appears in an argument."""
        assert validate_reproduction("metascience grim ... 30")["valid"] is False
        assert validate_reproduction("metascience grim '...' 30")["valid"] is False

    def test_a_hallucinated_subcommand_is_still_caught(self):
        """The guard worked in exactly one place on the real batch and that
        path must not weaken: `extract-pdf` is not a CLI verb."""
        r = validate_reproduction("metascience extract-pdf --first-page 20")
        assert r["valid"] is False
        assert any("unknown subcommand" in p for p in r["problems"])

    def test_an_unterminated_quote_does_not_crash_it(self):
        validate_reproduction("""metascience grim 5.5 30 --note 'oops""")


class TestTitleQualityIsMeasured:
    """The schema asked for noun phrases and a real batch returned 8 of 31.
    An instruction nobody measures is one nobody knows is being ignored."""

    from forensic_metascience_ai_toolkit.evaluation.deterministic import check_titles as _c

    def _check(self, *titles):
        from forensic_metascience_ai_toolkit.evaluation.deterministic import check_titles
        return check_titles({"findings": [{"title": t} for t in titles]})

    def test_a_noun_phrase_passes(self):
        r = self._check("Per-arm sample sizes absent from Table 1 and the Methods")
        assert r["pass"] is True and r["n_sentence_shaped"] == 0

    def test_a_sentence_is_flagged(self):
        r = self._check("Table 1 prints df = 3 on all seven chi-square rows")
        assert r["n_sentence_shaped"] == 1

    def test_two_defects_joined_by_a_semicolon_are_flagged(self):
        """Those are two findings, and a reader cannot cite half a title."""
        r = self._check("Caption omits the restriction; all three misstate the waves")
        assert r["n_joined"] == 1

    def test_an_overlong_title_is_flagged(self):
        """Derived from the cap, not from a literal. `"x" * 120` was overlong
        under the 90-character cap and is exactly at the limit under the 120 it
        became on 2026-08-13, so the test silently stopped exercising the
        branch it names."""
        from forensic_metascience_ai_toolkit.evaluation.deterministic import _TITLE_MAX
        assert self._check("x" * (_TITLE_MAX + 1))["n_overlong"] == 1
        assert self._check("x" * _TITLE_MAX)["n_overlong"] == 0

    def test_it_never_fails_a_report_outright(self):
        """A NOTE, not a rejection. Title style does not make a finding wrong,
        and a check that blocked on prose would be worse than the problem."""
        r = self._check("Table 1 prints df = 3")
        assert "pass" in r and r["n"] == 1        # reported, not raised

    def test_no_findings_is_not_a_failure(self):
        from forensic_metascience_ai_toolkit.evaluation.deterministic import check_titles
        assert check_titles({})["pass"] is True


