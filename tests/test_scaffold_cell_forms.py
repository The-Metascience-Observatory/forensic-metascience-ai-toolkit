"""The cell parser must accept the forms the reading correctly names.

FOUND on the first end-to-end JATS run (ajcp.70049, 2026-09-06): the model read
Tables 2-4 correctly -- `model_coefficient`, form `other`, and named the paper's
own mislabel (`M (SD)` over coefficients) -- and the deterministic parser then
refused every cell: "Cells parsed into values: 0 of 42" three times over. 202 of
210 table cells unparsed. The paper's core results contributed zero values.
"""
from metascience_agent.scaffold.bind import cell_components as cc


def test_a_coefficient_with_a_parenthesised_dispersion_lands_unnamed():
    """The statistic name is the closed vocabulary's -- a first draft wrote
    `estimate`, which the integrity check refused 64 times over. Right call."""
    """The parenthesis is NOT called SE or SD: the reading declined to say, and
    a derived boundary may narrow a premise, never supply one."""
    assert cc("1.01 (0.38)", "other") == [("other", "1.01"), ("dispersion_unstated", "0.38")]


def test_a_p_column_parses_as_p_whatever_the_row_form_says():
    assert cc("< .001", "other", col_label="Coefficient | p") == [("p_value", "<.001")]
    assert cc(".01", "other", col_label="Coefficient | p") == [("p_value", ".01")]
    assert cc("0", "other", col_label="Coefficient | p") == [("p_value", "0")]


def test_a_count_with_a_percentage_yields_both():
    assert cc("38 (59%)", "count") == [("count", "38"), ("percentage", "59")]


def test_the_old_forms_still_parse():
    assert cc("4.01 (0.92)", "mean_pm_sd") == [("mean", "4.01"), ("sd", "0.92")]
    assert cc("64", "count") == [("count", "64")]
