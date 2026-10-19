"""Resolving an ambiguous cell is the path that UNCAPS severity.

Every check refuses a cell typed `ambiguous`. `_resolve_ambiguous` is what
lifts that refusal, using the variable the model declared -- and a declared
variable with stated bounds is also what lets the exact-arithmetic checks reach
`impossible`. So the numbers this function pulls out of a cell had better be
the numbers the paper printed.

Twice they were not, both reproduced by execution before the fix:

    "1,234 (56.7)" + declared continuous  ->  mean=1.0,  sd=234.0
    "48.9 (7.1)"   + declared binary      ->  count=48

The first is a pattern that could not span a digit-group comma, so `re.findall`
cut `1,234` in half and the `.replace(",", "")` afterwards had nothing left to
repair. The second truncated a mean into a count -- and a count is a whole
thing, so 48.9 of them is not a misread count, it is one that never existed.
Both sets of fabricated numbers went to GRIM, GRIMMER and SPRITE with the
severity cap already lifted.
"""

import pytest

from metascience_agent.dispatch import _resolve_ambiguous


def resolve(raw, family, candidates=("mean_sd", "n_percent")):
    return _resolve_ambiguous(
        {"kind": "ambiguous", "raw": raw, "candidates": list(candidates)},
        {"family": family})


class TestDigitGroupsSurviveResolution:
    def test_a_thousands_comma_is_not_cut_in_half(self):
        got = resolve("1,234 (56.7)", "continuous")
        assert (got["kind"], got["value"], got["sd"]) == ("mean_sd", 1234.0, 56.7)

    @pytest.mark.parametrize("raw,value,sd", [
        ("1,234,567 (89.1)", 1234567.0, 89.1),
        ("84,299 (108,353)", 84299.0, 108353.0),   # found live in the corpus
        ("48.9 (7.1)", 48.9, 7.1),                 # the ordinary case, unchanged
    ])
    def test_grouped_and_plain_numbers_both_survive(self, raw, value, sd):
        got = resolve(raw, "continuous")
        assert (got["value"], got["sd"]) == (value, sd)

    def test_it_uses_the_same_pattern_celltypes_parses_with(self):
        """Two number patterns in one pipeline is two chances to disagree about
        what a cell contains, and the disagreement is silent."""
        import inspect
        from metascience_agent import dispatch
        assert "_NUM" in inspect.getsource(dispatch._resolve_ambiguous)


class TestACountMustActuallyBeACount:
    def test_a_mean_is_not_truncated_into_a_count(self):
        got = resolve("48.9 (7.1)", "binary", ("n_percent", "mean_sd"))
        assert got["kind"] == "ambiguous"
        assert "count" not in got

    def test_a_percentage_above_100_is_refused(self):
        got = resolve("142 (171.0)", "binary", ("n_percent", "mean_sd"))
        assert got["kind"] == "ambiguous"

    def test_a_negative_percentage_is_refused(self):
        got = resolve("142 (-1.0)", "binary", ("n_percent", "mean_sd"))
        assert got["kind"] == "ambiguous"

    def test_the_legitimate_case_still_resolves(self):
        """The whole point of the function. A real n (%) cell under a declared
        binary variable must still reach the granularity checks."""
        got = resolve("142 (71.0)", "binary", ("n_percent", "mean_sd"))
        assert (got["kind"], got["count"], got["percent"]) == ("n_percent", 142, 71.0)

    def test_zero_and_one_hundred_are_both_admissible(self):
        for raw, count, pct in (("0 (0.0)", 0, 0.0), ("30 (100.0)", 30, 100.0)):
            got = resolve(raw, "binary", ("n_percent", "mean_sd"))
            assert (got["count"], got["percent"]) == (count, pct), raw


class TestTheRefusalsThatWereAlreadyCorrect:
    def test_a_cell_that_is_not_ambiguous_is_untouched(self):
        cell = {"kind": "mean_sd", "raw": "48.9 (7.1)", "value": 48.9}
        assert _resolve_ambiguous(cell, {"family": "continuous"}) is cell

    def test_no_declared_variable_means_no_resolution(self):
        assert resolve("142 (71.0)", None)["kind"] == "ambiguous"

    def test_a_target_the_cell_never_offered_is_not_forced_onto_it(self):
        """The declaration says what the VARIABLE is, not what the cell says.
        Where they disagree the declaration is the likelier error."""
        got = resolve("5 (3-15)", "binary", ("median_iqr", "estimate_ci"))
        assert got["kind"] == "ambiguous"
