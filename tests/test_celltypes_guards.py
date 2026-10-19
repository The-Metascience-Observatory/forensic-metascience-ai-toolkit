"""Guards against CONFIDENT mistyping in `celltypes.parse_cell`.

The layer's cardinal rule is that a cell typed confidently-but-wrongly is worse
than one typed `ambiguous`, because `ambiguous` is refused downstream and a
confident kind is not. Each class here was demonstrated by execution before the
fix, with the downstream accusation it produced:

* An unlabeled `X (a-b)` cell was typed `estimate_ci` by default, so an
  ordinary SKEWED median (IQR) -- `5 (3-15)`, the modal way length-of-stay is
  reported -- went to `check_estimate_ci`, which returned `suspicious`: "the
  estimate 5 is not the arithmetic midpoint of [3, 15]". Our guess, reported in
  the grammar of a claim about the paper.
* `48.9 (7.1-9.2)` -- a value OUTSIDE its own parenthetical interval, so
  whatever it is, it is not an estimate with its CI -- returned `suspicious`:
  "the estimate 48.9 lies outside its own CI".
* Conflicting row/column labels ("Age, mean (SD)" in an "n (%)" column) were
  resolved silently by pattern order: the cell was typed `n_percent` although
  the row label said the opposite.
* The English word "or" ("Death or MI") matched the odds-ratio abbreviation
  case-insensitively and hinted `estimate_ci` onto an n (%) row.
* The bare `X (Y)` heuristic (integer > 100 beside a value in [0, 100]) typed
  the cell a definite `n_percent`. `154 (23.4)` -- a mean cholesterol with its
  SD, printed without a label -- fed grim_percentage, which returns
  `impossible` for 23.4% at n=180. The declared-variable resolution path in
  dispatch recovers the same cells without the guess.
"""
import pytest

from forensic_metascience_ai_toolkit.tools.celltypes import label_hint, parse_cell


class TestUnlabeledIntervalCellsMayNotAccuse:
    def test_skewed_median_iqr_is_refused_not_typed_estimate_ci(self):
        # LOS-style skewed median (IQR); off both midpoints, inside interval.
        pc = parse_cell("5 (3-15)")
        assert pc.kind == "ambiguous"
        assert "estimate_ci" in pc.candidates and "median_iqr" in pc.candidates

    def test_skewed_median_iqr_with_decimals_is_refused(self):
        pc = parse_cell("5.2 (3.1-15.4)")
        assert pc.kind == "ambiguous"

    def test_value_outside_its_own_interval_is_refused(self):
        pc = parse_cell("48.9 (7.1-9.2)")
        assert pc.kind == "ambiguous"

    def test_reversed_bounds_without_a_label_are_refused(self):
        pc = parse_cell("48.9 (9.2-7.1)")
        assert pc.kind == "ambiguous"

    def test_a_plausible_ci_is_still_typed(self):
        # Near the arithmetic midpoint: the unlabeled guess keeps its coverage.
        pc = parse_cell("1.42 (1.08-1.87)")
        assert pc.kind == "estimate_ci"
        assert (pc.low, pc.high) == (1.08, 1.87)

    def test_a_log_symmetric_ratio_ci_is_still_typed(self):
        pc = parse_cell("0.30 (0.10-0.85)")
        assert pc.kind == "estimate_ci"

    def test_a_labelled_outside_value_is_kept_for_the_checker(self):
        # With an explicit CI label the paper asserts the reading, so an
        # estimate outside its CI is the CHECKER's legitimate finding.
        pc = parse_cell("48.9 (7.1-9.2)", None, "OR (95% CI)")
        assert pc.kind == "estimate_ci"

    def test_a_bracket_interval_containing_its_value_is_still_median_iqr(self):
        pc = parse_cell("48.9 [7.1, 9.2]")
        assert pc.kind == "ambiguous"  # value outside -> refused
        pc = parse_cell("8.1 [7.1, 9.2]")
        assert pc.kind == "median_iqr"


class TestConflictingLabelsAreRefusedNotOrdered:
    def test_row_says_mean_sd_col_says_n_percent(self):
        pc = parse_cell("48.9 (7.1)", "Age, mean (SD)", "n (%)")
        assert pc.kind == "ambiguous"
        assert "mean_sd" in pc.candidates and "n_percent" in pc.candidates

    def test_mixed_format_column_header(self):
        pc = parse_cell("48.9 (7.1)", "Age", "Mean (SD) or n (%)")
        assert pc.kind == "ambiguous"

    def test_label_hint_returns_none_on_conflict(self):
        assert label_hint("Age, mean (SD)", "n (%)") is None

    def test_a_single_clear_label_still_types_the_cell(self):
        pc = parse_cell("48.9 (7.1)", "Age", "Mean (SD)")
        assert pc.kind == "mean_sd" and pc.sd == 7.1


class TestEnglishOrDoesNotHintOddsRatio:
    def test_death_or_mi_is_not_an_estimate(self):
        pc = parse_cell("12 (5.2)", "Death or MI", None)
        assert pc.kind == "ambiguous"

    def test_or_less_with_n_percent_column_stays_n_percent(self):
        pc = parse_cell("142 (71.0)", "8th grade education or less", "n (%)")
        assert pc.kind == "n_percent"

    def test_uppercase_or_abbreviation_still_hints(self):
        pc = parse_cell("1.23 (0.98-1.55)", None, "OR (95% CI)")
        assert pc.kind == "estimate_ci"


class TestSingleParentheticalUnderIntervalLabel:
    def test_ci_label_with_one_value_is_refused(self):
        # "OR (95% CI)" promises two bounds; one number does not fit the label.
        pc = parse_cell("1.23 (0.98)", None, "OR (95% CI)")
        assert pc.kind == "ambiguous"

    def test_median_iqr_label_with_one_value_claims_no_bound(self):
        # A single parenthetical under "Median (IQR)" is the IQR WIDTH; typing
        # it as the lower bound asserted a quartile the paper never printed.
        pc = parse_cell("48.9 (7.1)", "LOS", "Median (IQR)")
        assert pc.kind == "median_iqr"
        assert pc.low is None and pc.high is None


class TestTheCountPercentHeuristicRefusesInsteadOfGuessing:
    def test_modal_clinical_cell_without_labels_is_ambiguous(self):
        pc = parse_cell("142 (71.0)")
        assert pc.kind == "ambiguous"
        # The likeliest reading leads the candidates, so a declared variable
        # can still resolve it downstream.
        assert pc.candidates[0] == "n_percent"
        assert "mean_sd" in pc.candidates

    def test_ambiguous_cell_records_the_parenthetical_precision(self):
        # dispatch._resolve_ambiguous copies the cell dict; without these the
        # resolved cell would fall back to a default `decimals` and a check
        # would size its interval off the wrong precision.
        pc = parse_cell("142 (71.0)")
        d = pc.as_dict()
        assert d["decimals_percent"] == 1 and d["decimals_sd"] == 1

    def test_declared_binary_variable_still_reaches_grim(self):
        # The recovery path the demotion relies on: declaration, not guessing.
        from forensic_metascience_ai_toolkit.dispatch import check_table
        r = check_table(
            cells=[{"raw": "142 (71.0)", "row_label": "M", "n": 200}],
            variables=[{"id": "s", "family": "binary"}],
            bindings={"M": "s"},
        )
        assert "grim_percentage" in r["tools_run"]

    def test_mean_with_sd_no_longer_reaches_grim_percentage(self):
        # `154 (23.4)` -- a mean with its SD -- previously typed n_percent and
        # grim_test_percentage(23.4, n=180) returns `impossible`.
        pc = parse_cell("154 (23.4)")
        assert pc.kind == "ambiguous"


class TestNPercentLabelInternalConsistency:
    def test_non_integer_count_under_n_percent_label_is_refused(self):
        # The column header can be right for the column and wrong for the row:
        # the Age row inside an "n (%)" table is mean (SD).
        pc = parse_cell("48.9 (7.1)", "Age, y", "n (%)")
        assert pc.kind == "ambiguous"

    def test_percent_above_100_under_n_percent_label_is_refused(self):
        pc = parse_cell("142 (708)", "Rate", "n (%)")
        assert pc.kind == "ambiguous"

    def test_a_true_count_percent_cell_is_unaffected(self):
        pc = parse_cell("142 (71.0)", "Female", "n (%)")
        assert pc.kind == "n_percent"
        assert pc.count == 142 and pc.percent == 71.0
