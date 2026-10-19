"""The prose denominator: what is not a statistic, and what counts as read.

H2 asks how many statistic-bearing sentences had every statistic in them read.
Two things made it read low for reasons that are not about reading.

THE FLOOR ALREADY KNEW. `(Table 4)` is classed `ordinal` by `numerals.index`,
with the reason string `follows '(Table'`, and H2 counted it anyway -- so
"none of the practices was associated with EBP fidelity (Table 4)" was uncovered
on the strength of the 4. Measured over ajcp.70049's 24 not-covered sentences:
9 blocked by a citation year the classifier missed, 9 by a `(Table N)` already
named `ordinal`, 8 by a declared phase label, 4 by factorial notation, 1 by a
page number. `NOT_A_STATISTIC_CLASSES` keys on the class the floor computed.

AND READ IS READ. A p-threshold does not become a value row -- it becomes a field
on a comparison -- so five ajcp sentences read as uncovered while a comparison
quoted them verbatim and carried `p_threshold: 0.05`.

EVERY CHANGE HERE IS A CLASSIFICATION AND NONE IS A SUPPRESSION. The numeral
stays in the floor's `n_total` and moves bucket; a rule that shrank the floor
would shrink the denominator of every "numbers we did not check" claim, which is
the distinction measured at +206 rows in CLAUDE.md 8f. The first test class is
that invariant, and it is the one that must never be relaxed.
"""

from __future__ import annotations

import pytest

from metascience_agent import numerals
from metascience_agent.scaffold import bind, coverage

# --------------------------------------------------------------------------
# Every sentence a rule here touches, and the false-removal battery beside it.
# --------------------------------------------------------------------------

TOUCHED = [
    ("Prior work ([2016]) found the same.", "2016", "citation_year"),
    ("Both ([2010], [2015]) agree.", "2015", "citation_year"),
    ("As [CADCA], [2018] notes, coalitions vary.", "2018", "citation_year"),
    ("Kaner's ([2014]) review says so.", "2014", "citation_year"),
    ("See (Shore et al., [2018], p. 185) for the argument.", "185", "citation_page"),
    ("Reported in (Smith, 2018, pp. 12-14) at length.", "12", "citation_page"),
    ("Results were significant (eTable 3 in Supplement 1).", "3", "ordinal"),
    ("Results were significant (eTable 3 in Supplement 1).", "1", "ordinal"),
    ("none was associated with fidelity (Table 4).", "4", "ordinal"),
    ("We used a 2 x 2 design.", "2", "ordinal"),
    ("There were nearly 46000 deaths.18,19,20", "19", "citation_marker"),
    ("[Table 1: Sample characteristics — 75 rows x 5 cols; see tables]", "75", "placeholder"),
]

#: NONE OF THESE MAY MOVE. Each is a real reported number in a shape one of the
#: rules above could plausibly over-fire on; a false removal is permanent,
#: because nobody looks at a classified numeral again.
UNTOUCHED = [
    ("We enrolled (1989 patients) in total.", "1989"),
    ("Arms of 250, 2013, and 210 patients were used.", "2013"),
    ("A total of 46,000 deaths occurred.", "46,000"),
    ("There were 46,000,000 people.", "46,000,000"),
    ("We enrolled 2013 participants.", "2013"),
    ("Data were collected in 2013, and later analysed.", "2013"),
    ("The mean was 4.01 (SD 1.2).", "4.01"),
    ("The interval was [95% CI 1990, 2010] wide.", "1990"),
    ("The test gave F (1,78) = 3.2.", "78"),
    ("Scores of 1,2,3 were given by the raters.", "1"),
    ("Attrition was 12% and the model converged (p = .03).", ".03"),
    ("Earlier work found p = .03 as well (Smith, 2011).", ".03"),
]


def _row(text: str, printed: str) -> dict:
    rows = {r["printed"]: r for r in numerals.index(text, tables_available=False)}
    assert printed in rows, f"{printed!r} not enumerated in {text!r}: {sorted(rows)}"
    return rows[printed]


class TestTheFloorIsNeverShrunk:

    @pytest.mark.parametrize("text", [t for t, _, _ in TOUCHED] + [t for t, _ in UNTOUCHED])
    def test_classification_never_removes_a_row(self, text):
        """`n_total` is invariant across every rule in this file: `index` emits
        one row per token whatever it decides the token is."""
        assert len(numerals.index(text, tables_available=False)) \
            == len(list(numerals.tokens(text)))

    def test_a_phase_label_classification_moves_a_row_and_removes_none(self):
        text = "Wave 1 data were collected in 2020 from 68 coalitions."
        rows = numerals.index(text, tables_available=False)
        before = len(rows)
        account = {"phases": [{"id": "phase:w1", "label": "Wave 1 (baseline / Time 1)"}],
                   "studies": []}
        n = bind.classify_phase_labels(rows, text, account)
        assert n == 1 and len(rows) == before
        assert [r["class"] for r in rows if r["printed"] == "1"] == ["phase_label"]

    def test_an_undeclared_wave_is_not_a_phase_label(self):
        """A join against the structure's own phases, not a word list."""
        text = "Wave 1 data were collected in 2020."
        rows = numerals.index(text, tables_available=False)
        assert bind.classify_phase_labels(rows, text, {"phases": [], "studies": []}) == 0

    def test_a_one_character_phase_label_cannot_sweep_the_paper(self):
        text = "Phase 1 gave 1 and 1 and 1."
        rows = numerals.index(text, tables_available=False)
        assert bind.classify_phase_labels(
            rows, text, {"phases": [{"id": "p", "label": "1"}], "studies": []}) == 0


class TestWhatTheRulesTouch:

    @pytest.mark.parametrize("text,printed,cls", TOUCHED)
    def test_it_is_classified_and_carries_its_reason(self, text, printed, cls):
        r = _row(text, printed)
        assert r["class"] == cls, r
        assert r["why"], "a rule that cannot show its reason is a rule nobody can audit"

    @pytest.mark.parametrize("text,printed", UNTOUCHED)
    def test_the_false_removal_battery_still_passes(self, text, printed):
        assert _row(text, printed)["class"] == "unclassified"

    def test_every_excluded_class_is_a_real_class(self):
        assert set(coverage.NOT_A_STATISTIC_CLASSES) <= set(numerals.CLASSES)

    def test_a_scale_anchor_is_deliberately_not_excluded(self):
        """`1 = sad, 9 = happy` names the ends of a measured scale, and a reader
        may reasonably want it covered."""
        assert "scale_anchor" not in coverage.NOT_A_STATISTIC_CLASSES


# --------------------------------------------------------------------------
# H2 itself
# --------------------------------------------------------------------------

TEXT = """## RESULTS

Being externally funded was associated with reach (p < .05) in every model.
None of the practices was associated with fidelity (Table 4).
Significance was assessed at an alpha of .05 throughout.
The mean score was 4.01 in the treated group.
"""


def _account(**kw) -> dict:
    rows = numerals.index(TEXT, tables_available=False)
    for r in rows:
        r["disposition"] = "unaccounted"
        r["role"] = "results"
        r["source"] = "article"
        r["value_id"] = None
    acct = {
        "document": {"tables": [], "figures": [],
                     "sections": [{"role": "results", "start": 0, "end": len(TEXT)}]},
        "variables": [], "values": [], "unparsed_cells": [], "studies": [],
        "accounting": rows, "comparisons": [], "statistical_analysis": {},
    }
    acct.update(kw)
    return acct


CMP = {"id": "cmp:1", "p_threshold": 0.05, "p_printed": None, "statistic_printed": None,
       "df_printed": None, "quote_verified": "verbatim",
       "quote": "Being externally funded was associated with reach (p < .05) in every model."}


class TestAComparisonAndTheDeclaredAlphaCountAsRead:

    def test_a_cross_reference_no_longer_blocks_a_sentence(self):
        h2 = coverage.statistic_sentences(_account(), TEXT)
        assert not any("fidelity (Table 4)" in u["sentence"] for u in h2["not_covered"])
        assert h2["numerals_excluded_by_class"]["ordinal"] == 1

    def test_a_p_threshold_a_comparison_holds_covers_its_sentence(self):
        before = coverage.statistic_sentences(_account(), TEXT)
        after = coverage.statistic_sentences(_account(comparisons=[CMP]), TEXT)
        assert any("externally funded" in u["sentence"] for u in before["not_covered"])
        assert not any("externally funded" in u["sentence"] for u in after["not_covered"])
        assert after["n_numerals_held_by_a_comparison_or_the_declared_alpha"] == 1

    def test_the_threshold_is_matched_by_value_not_by_string(self):
        """The paper prints `p < .05` and the comparison carries `0.05`."""
        held = coverage.numerals_a_comparison_holds(_account(comparisons=[CMP]), TEXT)
        assert len(held) == 1

    def test_an_unlocated_comparison_quote_credits_nothing(self):
        c = {**CMP, "quote": "a sentence the paper does not contain at all"}
        assert coverage.numerals_a_comparison_holds(_account(comparisons=[c]), TEXT) == set()

    def test_an_unverified_comparison_quote_credits_nothing(self):
        c = {**CMP, "quote_verified": "absent"}
        assert coverage.numerals_a_comparison_holds(_account(comparisons=[c]), TEXT) == set()

    def test_a_numeral_in_the_quote_the_comparison_does_not_carry_is_not_credited(self):
        """Merely being near a comparison is not being read by one."""
        c = {**CMP, "p_threshold": 0.01}
        assert coverage.numerals_a_comparison_holds(_account(comparisons=[c]), TEXT) == set()

    def test_the_declared_alpha_covers_the_sentence_that_states_it(self):
        sa = {"alpha_declared": 0.05,
              "alpha_quote": "Significance was assessed at an alpha of .05 throughout."}
        h2 = coverage.statistic_sentences(_account(statistical_analysis=sa), TEXT)
        assert not any("alpha of .05" in u["sentence"] for u in h2["not_covered"])

    def test_a_genuine_p_in_a_sentence_with_a_citation_stays_a_statistic(self):
        """The citation rules may not take a real reported number with them."""
        text = "## RESULTS\n\nAttrition was 12% and the model converged, p = .03 (Smith, 2011).\n"
        rows = numerals.index(text, tables_available=False)
        for r in rows:
            r["disposition"] = "unaccounted"
            r["role"] = "results"
        acct = _account()
        acct["accounting"] = rows
        acct["document"]["sections"] = [{"role": "results", "start": 0, "end": len(text)}]
        h2 = coverage.statistic_sentences(acct, text)
        row = next(u for u in h2["not_covered"] if "Attrition" in u["sentence"])
        assert row["n_statistics"] == 2 and row["tier"] == "uncovered"
        assert h2["numerals_excluded_by_class"] == {"citation_year": 1}
