"""A paper's declared p correction is found and quoted (1.90.0, `p_adjustment.py`)."""

import pytest

from metascience_agent.p_adjustment import declares_p_adjustment, p_adjustment_note


@pytest.mark.parametrize("text, kind", [
    ("Degrees of freedom were corrected using Greenhouse-Geisser estimates.", "sphericity"),
    ("Huynh–Feldt corrected p values are reported.", "sphericity"),
    ("Where sphericity was violated we report sphericity-corrected results.", "sphericity"),
    ("We applied a Bonferroni correction.", "multiplicity"),
    ("Post hoc comparisons used Tukey HSD tests.", "multiplicity"),
    ("Scheffé post hoc tests were used.", "multiplicity"),
    ("p values were corrected for multiple comparisons.", "multiplicity"),
    ("We controlled the false discovery rate (Benjamini-Hochberg).", "multiplicity"),
])
def test_declared_corrections_are_found(text, kind):
    found = declares_p_adjustment(text)
    assert [f["kind"] for f in found] == [kind]
    assert found[0]["quote"]  # the paper's own clause, for the prompt


@pytest.mark.parametrize("text", [
    "The mean age was 34 years (SD = 4.2).",
    "We used a two-tailed t test, t(28) = 2.10, p = .04.",
    "Participants were recruited through Holmes Community College.",  # not Holm
    None, "",
])
def test_nothing_declared(text):
    assert declares_p_adjustment(text) == []
    assert p_adjustment_note(text) == ""


def test_both_kinds_are_reported_once_each():
    text = ("Greenhouse-Geisser corrections were applied; pairwise comparisons were "
            "Bonferroni-corrected, and the Huynh-Feldt epsilon was also inspected.")
    assert sorted(f["kind"] for f in declares_p_adjustment(text)) == ["multiplicity", "sphericity"]


def test_note_names_the_tools_and_keeps_the_over_claim_direction():
    note = p_adjustment_note("A Bonferroni correction was applied.")
    assert "p_adjustment" in note and "recalc_stat_to_p" in note
    assert "SMALLER" in note  # an over-claim is never excused


# --- a stated one-tailed test (1.93.0, statcheck's OneTailedTxt rule) ---
from metascience_agent.p_adjustment import declares_one_tailed, one_tailed_note  # noqa: E402


@pytest.mark.parametrize("text", [
    "All tests were one-tailed.",
    "Hypotheses were tested with one-sided t tests.",
    "Given the directional hypothesis, we report one tailed p values.",
    "A directional test was used.",
])
def test_a_stated_one_tailed_test_is_found(text):
    found = declares_one_tailed(text)
    assert found and found["quote"]


@pytest.mark.parametrize("text", [
    "A non-directional hypothesis was tested.",
    "Bidirectional associations were examined.",
    "All tests were two-tailed.",
    None, "",
])
def test_no_one_tailed_statement(text):
    assert declares_one_tailed(text) is None
    assert one_tailed_note(text) == ""


def test_the_note_names_the_parameter_and_the_tools():
    note = one_tailed_note("Planned contrasts were one-tailed.")
    assert "one_tailed_stated=True" in note
    for tool in ("recalc_stat_to_p", "recalc_f_to_p", "check_regression"):
        assert tool in note


def test_the_batch_passes_the_row_key_through():
    from metascience_agent.tools.regression import check_regression_batch
    row = dict(b=0.110, se=0.050, reported_p=0.014, df=100, df_source="reported",
               decimals_b=3, decimals_se=3, decimals_p=3)
    assert check_regression_batch([row])["severity"] == "suspicious"
    assert check_regression_batch([{**row, "one_tailed_stated": True}])["severity"] == "consistent"
