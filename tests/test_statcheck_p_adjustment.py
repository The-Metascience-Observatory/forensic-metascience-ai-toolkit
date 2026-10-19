"""statcheck respects a correction the paper DECLARES (1.97.0).

statcheck recomputes every p as a raw, unadjusted test, so a Huynh-Feldt p
printed beside the uncorrected df, or a Bonferroni p beside its raw statistic,
always reads as an error -- in the under-claim direction only. With
`p_adjustment` the wrapper excuses exactly that direction, the way the recalc
tools have since 1.90.0; a reported p SMALLER than the recomputed one is never
explained by a correction. The benchmark side is pinned by
tests/test_pvalue_tools_bench.py.
"""

import pytest

pytest.importorskip("statcheck")

from forensic_metascience_ai_toolkit import registry  # noqa: E402
from forensic_metascience_ai_toolkit.p_adjustment import p_adjustment_note  # noqa: E402
from forensic_metascience_ai_toolkit.tools.r_wrappers import python_statcheck_text  # noqa: E402

#: true p .000057 (under-claim, crosses .05), .25 (over-claim of a bound),
#: .018 (under-claim, crosses .05), .24 (under-claim, no decision change).
TEXT = ("A main effect, F(2, 66) = 11.38, p = .26. A contrast, t(20) = 1.2, p < .05. "
        "Another, t(30) = 2.5, p = .90. And F(2, 66) = 1.45, p = .40.")


def _rows(r):
    return {s["raw"]: s for s in r["statistics"]}


@pytest.mark.parametrize("adj", [None, "none", "unknown"])
def test_without_a_declared_correction_every_error_counts(adj):
    r = python_statcheck_text(TEXT, p_adjustment=adj)
    assert r["errors_found"] == 4
    assert r["decision_errors"] == 3
    assert "errors_explained_by_adjustment" not in r
    assert all("explained_by_adjustment" not in s for s in r["statistics"])


def test_the_default_output_is_unchanged_by_the_parameter():
    assert python_statcheck_text(TEXT) == python_statcheck_text(TEXT, p_adjustment=None)


@pytest.mark.parametrize("adj", ["sphericity", "multiplicity"])
def test_a_declared_correction_explains_only_the_under_claims(adj):
    r = python_statcheck_text(TEXT, p_adjustment=adj)
    rows = _rows(r)
    assert rows["F(2, 66) = 11.38, p = .26"]["explained_by_adjustment"] is True
    assert rows["t(30) = 2.5, p = .90"]["explained_by_adjustment"] is True
    assert rows["F(2, 66) = 1.45, p = .40"]["explained_by_adjustment"] is True
    # A bound the true p does not satisfy is an over-claim: never excused.
    assert rows["t(20) = 1.2, p < .05"]["explained_by_adjustment"] is False
    assert r["errors_found"] == 1
    assert r["errors_explained_by_adjustment"] == 3
    assert r["decision_errors"] == 1
    assert r["decision_errors_explained_by_adjustment"] == 2
    assert r["p_adjustment"] == adj
    # The rows stay visible and keep statcheck's own verdict.
    assert all(s["error"] for s in r["statistics"])
    assert "explained_by_adjustment" in r["methodology"]


def test_an_exact_over_claim_still_counts_under_a_correction():
    # t(30) = 2.0 gives p = .055; printed .03 is SMALLER: no correction makes it.
    r = python_statcheck_text("We found t(30) = 2.0, p = .03.", p_adjustment="sphericity")
    (row,) = r["statistics"]
    assert row["error"] and row["explained_by_adjustment"] is False
    assert r["errors_found"] == 1 and r["decision_errors"] == 1


def test_a_greater_than_bound_the_true_p_misses_is_an_under_claim():
    r = python_statcheck_text("We found t(20) = 2.5, p > .05.", p_adjustment="multiplicity")
    (row,) = r["statistics"]
    assert row["error"] and row["explained_by_adjustment"] is True
    assert r["errors_found"] == 0


def test_rounding_is_still_its_own_explanation():
    # .232008 is correct at 3 dp; it is rounding, not the correction.
    r = python_statcheck_text("r(51) = -0.167, p = .232.", p_adjustment="sphericity")
    if r["errors_flagged_upstream"]:
        assert r["errors_explained_by_rounding"] == 1
        assert r["errors_explained_by_adjustment"] == 0


def test_an_unknown_value_is_refused():
    r = python_statcheck_text(TEXT, p_adjustment="bonferroni")
    assert r["success"] is False and "p_adjustment" in r["error"]


def test_the_registry_routes_it_on_both_inputs(tmp_path):
    spec = registry.BY_NAME["statcheck"]
    assert "p_adjustment" in spec.schema()
    assert "p_adjustment" in spec.guards()
    r = spec.call({"text": TEXT, "p_adjustment": "sphericity"})
    assert r["errors_explained_by_adjustment"] == 3
    # The PDF route validates the value before reading anything.
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    bad = spec.call({"pdf_path": str(pdf), "p_adjustment": "holm"})
    assert bad["success"] is False


def test_the_description_and_the_prompt_note_name_it():
    assert "p_adjustment" in registry.BY_NAME["statcheck"].description
    note = p_adjustment_note("Greenhouse-Geisser corrections were applied.")
    assert "`statcheck`" in note
