"""Printed precision must survive the trip from raw cell to check.

This exists because `check_table` -- the tool built specifically to stop the
model choosing its own checks -- returned `impossible` on the cell
`101 (71%)` with n=142. 101/142 = 71.13%, which prints as "71". Nothing was
wrong with the number.

`dispatch._build_args` never passed `decimals`, so `grim_percentage` fell back
to its registry default of 1 and tested a zero-decimal value against a rounding
window ten times too tight. The identical defect had already been found and
fixed for GRIMMER; the percentage branch never got it.

The root cause is that a parsed float cannot carry printed precision:
`percent=71.0` has already lost the distinction between "71" and "71.0". So the
precision has to be captured at parse time, from the raw string.
"""
import pytest

from forensic_metascience_ai_toolkit import registry as R
from forensic_metascience_ai_toolkit.dispatch import _build_args, check_table
from forensic_metascience_ai_toolkit.tools.celltypes import _dp, parse_cell
from forensic_metascience_ai_toolkit.tools.estimates import check_estimate_ci
from forensic_metascience_ai_toolkit.tools.se_sd import check_sd_or_se


class TestDecimalPlaces:
    @pytest.mark.parametrize("text,expected", [
        ("71", 0), ("71.0", 1), ("71.13", 2), ("1,234.567", 3),
        ("-4.50", 2), ("0", 0),
    ])
    def test_counts_printed_places(self, text, expected):
        assert _dp(text) == expected

    def test_unparseable_is_unknown_not_zero(self):
        """"printed to 0 dp" and "unknown" must not collapse together."""
        assert _dp("n/a") is None
        assert _dp(None) is None


class TestCellCapturesPrecision:
    def test_percent_precision_is_captured_separately(self):
        c = parse_cell("101 (71%)", row_label="Male, n (%)")
        assert c.percent == 71.0
        assert c.decimals_percent == 0      # NOT 1, and not inferred from the float

    def test_one_decimal_percent(self):
        c = parse_cell("101 (71.1%)", row_label="Male, n (%)")
        assert c.decimals_percent == 1

    def test_mean_and_sd_precision_captured_independently(self):
        c = parse_cell("5.5 (1.234)", row_label="Score, mean (SD)")
        assert c.decimals_value == 1
        assert c.decimals_sd == 3

    def test_plus_minus_form(self):
        c = parse_cell("48.9 ± 14.53")
        assert (c.decimals_value, c.decimals_sd) == (1, 2)

    def test_precision_reaches_as_dict(self):
        d = parse_cell("101 (71%)", row_label="Male, n (%)").as_dict()
        assert d["decimals_percent"] == 0


def _table(raw, n=142):
    label = "Male, n (%)"
    return check_table(
        cells=[{"raw": raw, "row_label": label, "n": n}],
        variables=[{"id": "v1", "name": "Male", "family": "binary"}],
        bindings={label: "v1"},
        provenance="printed_table",
    )


class TestNoFalseImpossible:
    def test_the_reported_false_accusation(self):
        """101/142 = 71.127%, printed as "71". This returned `impossible`.

        The bug this class exists for is the ACCUSATION, and it is still fixed.
        The verdict is now `indeterminate` rather than `consistent`, which is
        the more honest of the two: at n = 142 the attainable percentages are
        100/142 = 0.70 points apart, FINER than the 1-point grid a whole
        percentage is printed on, so no reported figure could have failed here.
        A pass would have been true and empty.
        """
        r = _table("101 (71%)")
        assert r["severity"] not in ("impossible", "highly_suspicious", "suspicious")
        assert r["severity"] == "indeterminate"

    def test_same_value_printed_to_one_decimal(self):
        assert _table("101 (71.1%)")["severity"] == "consistent"

    def test_a_genuine_impossibility_is_still_caught(self):
        """The fix must not be "stop checking". 71.5% is unreachable at n=142."""
        r = _table("101 (71.5%)")
        assert r["severity"] == "impossible"

    def test_the_check_received_the_printed_precision(self):
        r = _table("101 (71.5%)")
        assert any(x.get("inputs", {}).get("decimals") == 1 for x in r["results"])


class TestDispatchHoles:
    """`_build_args` only populated a parameter LITERALLY named `decimals` or
    `decimals_sd`, so three checks ran on defaults while the precision they
    needed sat in the cell beside them. Nothing surfaced: the check ran,
    returned a verdict, and had sized its rounding interval off a guess.
    """

    def _args(self, tool: str, cell: dict, n=30):
        return _build_args(R.BY_NAME[tool], cell, {}, n)

    MEAN_SD_CELL = {
        "raw": "71 (0.30)", "kind": "mean_sd", "value": 71.0, "sd": 0.30,
        "decimals_value": 0, "decimals_sd": 2,
    }

    @pytest.mark.parametrize("tool", ["sprite_reconstruct", "debit_check"])
    def test_decimals_mean_reaches_the_tools_that_ask_for_it(self, tool):
        """Unmapped, sprite fell back to re-deriving precision from the parsed
        float -- `str(71.0)` reads a mean printed "71" as one decimal -- and
        debit silently defaulted to two."""
        assert self._args(tool, self.MEAN_SD_CELL)["decimals_mean"] == 0

    def test_estimate_ci_gets_the_coarsest_of_the_three(self):
        cell = {"raw": "5 (1-8)", "kind": "estimate_ci", "value": 5.0,
                "low": 1.0, "high": 8.0,
                "decimals_value": 0, "decimals_interval": 0}
        assert self._args("check_estimate_ci", cell, n=100)["decimals"] == 0

    def test_estimate_ci_precision_is_the_interval_not_the_estimate(self):
        """`1.42 (1.1-1.9)` is a 1 dp comparison however finely 1.42 is printed:
        the coarsest of the three numbers is the binding constraint."""
        c = parse_cell("1.42 (1.1-1.9)", row_label="OR (95% CI)")
        assert c.decimals_value == 2
        assert c.decimals_interval == 1
        cell = c.as_dict()
        assert self._args("check_estimate_ci", cell, n=100)["decimals"] == 1

    def test_sd_or_se_gets_the_dispersions_precision_not_the_means(self):
        """It consumes the SD beside the mean, so `decimals_value` would be the
        wrong number -- and wrong silently, since both are integers."""
        assert self._args("check_sd_or_se", self.MEAN_SD_CELL)["decimals"] == 2


class TestPrecisionChangesTheVerdict:
    """A parameter that is threaded but ignored is worse than one that is
    missing, so each hole gets a case where supplying the precision changes
    the answer."""

    def test_estimate_ci_false_positive_disappears(self):
        """An estimate printed `5` against a CI of `(1-8)` sits 0.5 from the
        midpoint -- entirely within what 0 dp permits. The old fallback read
        `5.0` off its repr as one decimal and called it suspicious; the
        fallback now reads integral values at 0 dp, so the false positive is
        gone with or without the explicit precision (which remains the
        intended path -- trailing zeros are still unrecoverable from floats)."""
        assert check_estimate_ci(5.0, 1.0, 8.0)["severity"] == "consistent"
        assert check_estimate_ci(5.0, 1.0, 8.0, decimals=0)["severity"] == "consistent"

    def test_estimate_ci_still_catches_a_real_mismatch(self):
        """The fix must not be "widen until nothing fires"."""
        r = check_estimate_ci(9.0, 1.0, 8.0, decimals=0)
        assert r["severity"] != "consistent"

    def test_sd_or_se_ceiling_uses_printed_precision_not_a_flat_1_percent(self):
        r_guessed = check_sd_or_se(2.0, 30, reported_as="SD", variable_range=(1, 7))
        r_printed = check_sd_or_se(2.0, 30, reported_as="SD", variable_range=(1, 7),
                                   decimals=1)
        assert "flat 1%" in r_guessed["methodology"]
        assert "printed precision (1 dp)" in r_printed["methodology"]


class TestNoCircularImport:
    def test_dispatch_imports_standalone(self):
        """`import forensic_metascience_ai_toolkit.dispatch` first used to raise ImportError.

        It worked only because every real entry point happened to import
        `registry` before it.
        """
        import subprocess
        import sys

        r = subprocess.run(
            [sys.executable, "-c", "import forensic_metascience_ai_toolkit.dispatch"],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stderr
