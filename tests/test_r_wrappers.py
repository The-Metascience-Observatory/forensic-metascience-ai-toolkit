"""An R exception is a fact about R, never a verdict about a paper.

`r_sprite` used to turn EVERY raise out of rsprite2's `set_parameters()` into
`infeasible=True, severity="impossible"` -- the strongest claim this system can
make, emitted because a subprocess errored.

Two measured failures motivated this file:

1. Statistics computed from a REAL integer sample (1, 5, 6, 7, 7, 8, 9) --
   mean 6.1, sd 2.61, n 7 on a 1-9 scale -- came back `impossible`, because
   rsprite2 raised "the mean is not consistent with this number of
   observations". A sample provably exists; we constructed it. Across such
   real-sample triples the rate was 16.2% at the values' correct printed
   precision and 32.8-41.9% at the 2-dp default.

2. `mean=nan` came back `impossible` with the reason "object 'nan' not found",
   which is an R SYNTAX error: `repr(float("nan"))` is the bare word `nan`, and
   R read it as a symbol. A parser error was published as a finding.

Both are now `indeterminate`, and non-finite input never reaches R at all.
"""
import math
import shutil
import subprocess

import pytest

from metascience_agent.tools.r_wrappers import _r_int, _r_num, r_sprite


def _rsprite2_available() -> bool:
    if not shutil.which("Rscript"):
        return False
    out = subprocess.run(
        ["Rscript", "-e", 'cat(requireNamespace("rsprite2", quietly=TRUE))'],
        capture_output=True, text=True,
    )
    return "TRUE" in out.stdout


needs_r = pytest.mark.skipif(not _rsprite2_available(), reason="R/rsprite2 not installed")


class TestNonFiniteNeverReachesR:
    """`_r_num` refuses what R cannot parse, so no call site can inject it."""

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_r_num_refuses_non_finite(self, bad):
        with pytest.raises(ValueError):
            _r_num(bad)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf")])
    def test_r_int_refuses_non_finite(self, bad):
        with pytest.raises(ValueError):
            _r_int(bad)

    def test_finite_values_still_pass(self):
        assert _r_num(2.61) == repr(2.61)
        assert _r_int(7) == "7"

    def test_a_nan_mean_is_indeterminate_not_impossible(self):
        """No R needed: the guard fires before the subprocess."""
        r = r_sprite(mean=float("nan"), sd=2.61, n=7, scale_min=1, scale_max=9, decimals=2)
        assert r["severity"] == "indeterminate"
        assert r["severity"] != "impossible"
        assert r.get("infeasible") is False
        # The old failure signature: an R parser error used as the reason.
        assert "object 'nan' not found" not in str(r.get("error", ""))

    def test_a_nan_sd_is_indeterminate_too(self):
        r = r_sprite(mean=4.0, sd=float("nan"), n=10)
        assert r["severity"] == "indeterminate"


@needs_r
class TestRExceptionsAreIndeterminate:
    #: mean/sd computed from the integer sample (1, 5, 6, 7, 7, 8, 9), which
    #: exists, so `impossible` here is provably wrong.
    REAL_SAMPLE = (1, 5, 6, 7, 7, 8, 9)

    def test_the_sample_really_does_have_these_statistics(self):
        xs = self.REAL_SAMPLE
        n = len(xs)
        mean = sum(xs) / n
        var = sum((x - mean) ** 2 for x in xs) / (n - 1)
        assert round(mean, 2) == 6.14 and round(math.sqrt(var), 2) == 2.61
        assert round(mean, 1) == 6.1

    def test_a_raise_from_set_parameters_is_never_impossible(self):
        r = r_sprite(mean=6.1, sd=2.61, n=7, scale_min=1, scale_max=9, decimals=2)
        assert r["severity"] == "indeterminate"
        assert r["severity"] != "impossible"
        assert r.get("infeasible") is False

    def test_the_r_message_is_kept_as_the_reason(self):
        r = r_sprite(mean=6.1, sd=2.61, n=7, scale_min=1, scale_max=9, decimals=2)
        assert r.get("r_error")
        assert "consistent" in r["r_error"] or "GRIM" in r["r_error"]
        assert "not proof of infeasibility" in r["note"]

    def test_a_genuinely_reconstructable_pair_still_succeeds(self):
        """The fix must be "stop accusing on exceptions", not "stop running"."""
        r = r_sprite(mean=4.0, sd=0.82, n=10, scale_min=1, scale_max=7, decimals=2)
        assert r["success"] is True
        assert r["num_distributions"] > 0


class TestAnAbsentEngineSaysSoInsteadOfReturningNothing:
    """A cross-check that never ran must not look like one that disagreed.

    MEASURED. With `scrutiny` absent, `r_grim` returned
    `{"error": "", "note": "Consider using Python GRIM implementation
    instead"}`. R writes "ERROR: scrutiny package not installed" to STDOUT via
    `cat()`, and `require(..., quietly = TRUE)` leaves STDERR empty, so the old
    branch -- `result.get("error") or result.get("stderr")` -- resolved to the
    empty string and threw the diagnostic away.

    That mattered because `registry.py` tells the model a disagreement between
    engines means OUR tooling is wrong. An empty result was therefore read as
    "the confirming engine declined to confirm", and every GRIM failure in
    `10.22141--2224-0713.5.83.2016.78473` was capped at `suspicious`. Re-run by
    hand with the paper's own stated bounds, all three were `impossible`.

    None of these tests need R: they drive the failure shape directly.
    """

    #: What `run_r_code` actually returns when the package is missing: exit 1,
    #: diagnostic on stdout, empty stderr, and NO `error` key -- no Python
    #: exception fired, so nothing set one.
    @staticmethod
    def _missing(pkg: str) -> dict:
        return {
            "success": False,
            "stdout": f"ERROR: {pkg} package not installed. "
                      f"Run: install.packages('{pkg}')",
            "stderr": "",
            "returncode": 1,
        }

    def test_grim_names_the_missing_package(self, monkeypatch):
        monkeypatch.setattr("metascience_agent.tools.r_wrappers.run_r_code",
                            lambda *a, **k: self._missing("scrutiny"))
        from metascience_agent.tools.r_wrappers import r_grim
        r = r_grim(mean=5.06, n=28, decimals=2)
        assert r["available"] is False
        assert r["unavailable_reason"] == "package_missing"
        assert r["package"] == "scrutiny"
        assert r["error"], "the reason must never be the empty string"
        assert "scrutiny" in r["error"]
        # It must not read as a verdict about the paper.
        assert "consistent" not in r

    def test_sprite_answers_the_severity_question_when_absent(self, monkeypatch):
        """Silence is not an answer: an absent engine still owes `indeterminate`."""
        monkeypatch.setattr("metascience_agent.tools.r_wrappers.run_r_code",
                            lambda *a, **k: self._missing("rsprite2"))
        r = r_sprite(mean=4.0, sd=0.82, n=10, scale_min=1, scale_max=7, decimals=2)
        assert r["available"] is False
        assert r["unavailable_reason"] == "package_missing"
        assert r["severity"] == "indeterminate"
        assert r.get("infeasible") is False
        assert r["error"]

    def test_an_absent_engine_is_distinguishable_from_a_disagreement(self, monkeypatch):
        """The whole point: three outcomes, three names."""
        from metascience_agent.tools.r_wrappers import r_grim
        monkeypatch.setattr("metascience_agent.tools.r_wrappers.run_r_code",
                            lambda *a, **k: self._missing("scrutiny"))
        absent = r_grim(mean=5.06, n=28, decimals=2)

        monkeypatch.setattr(
            "metascience_agent.tools.r_wrappers.run_r_code",
            lambda *a, **k: {"success": True, "stdout": "GRIM_FAIL\n",
                             "stderr": "", "returncode": 0})
        disagreed = r_grim(mean=5.06, n=28, decimals=2)

        assert absent["available"] is False and "consistent" not in absent
        assert disagreed["available"] is True and disagreed["consistent"] is False

    def test_no_rscript_is_its_own_reason(self, monkeypatch):
        from metascience_agent.tools.r_wrappers import r_grim
        monkeypatch.setattr(
            "metascience_agent.tools.r_wrappers.run_r_code",
            lambda *a, **k: {"success": False, "stdout": "",
                             "error": "R not installed or Rscript not in PATH"})
        r = r_grim(mean=5.06, n=28, decimals=2)
        assert r["unavailable_reason"] == "r_absent"
        assert r["error"]

    def test_a_real_r_error_is_not_reported_as_a_missing_package(self, monkeypatch):
        from metascience_agent.tools.r_wrappers import r_grim
        monkeypatch.setattr(
            "metascience_agent.tools.r_wrappers.run_r_code",
            lambda *a, **k: {"success": False, "stdout": "",
                             "stderr": "Error in grim(): unused argument",
                             "returncode": 1})
        r = r_grim(mean=5.06, n=28, decimals=2)
        assert r["unavailable_reason"] == "r_error"
        assert "unused argument" in r["error"]


class TestTheCrossCheckAsksTheSameQuestion:
    """MEASURED 2026-08-22 on 10.1177--0093854811403123. The adjudicator
    cross-checked a `grim_percentage` finding -- "28% of the other criminal
    justice professionals", n=41, Python verdict `impossible` -- by calling
    `r_grim_ground_truth` with mean=28, decimals=0. R answered
    `consistent: true`, correctly, to the question it was asked: can 41
    integers average 28? (28*41 = 1148, an integer.) That is not the share
    question. 11/41 = 26.83 and 12/41 = 29.27, so 28% is not a possible k/41,
    and the adjudicator's second call with mean=0.28 agreed with Python.

    The engines "disagreed" because they were asked different things -- the
    same trap as rsprite2 inferring precision from the literal. A cross-check
    that quietly answers an easier question is worse than no cross-check,
    because it reads as exoneration."""

    def _captured(self, monkeypatch):
        seen = {}

        def fake(code, *a, **k):
            seen["code"] = code
            return {"success": True, "stdout": "GRIM_PASS\n"}

        monkeypatch.setattr("metascience_agent.tools.r_wrappers.run_r_code",
                            fake)
        return seen

    def test_percentage_is_converted_to_the_proportion_literal(self, monkeypatch):
        from metascience_agent.tools.r_wrappers import r_grim
        seen = self._captured(monkeypatch)
        r_grim(mean=28, n=41, decimals=0, percentage=True)
        assert '"0.28"' in seen["code"], seen["code"]

    def test_a_percentage_at_one_dp_carries_three(self, monkeypatch):
        """grim_test_percentage reads a percentage at `decimals` dp as a
        proportion at `decimals + 2`. The two engines must format the SAME
        literal or they are not comparable."""
        from metascience_agent.tools.r_wrappers import r_grim
        seen = self._captured(monkeypatch)
        r_grim(mean=9.6, n=93, decimals=1, percentage=True)
        assert '"0.096"' in seen["code"], seen["code"]

    def test_without_the_flag_the_mean_literal_is_unchanged(self, monkeypatch):
        from metascience_agent.tools.r_wrappers import r_grim
        seen = self._captured(monkeypatch)
        r_grim(mean=5.06, n=28, decimals=2)
        assert '"5.06"' in seen["code"]

    def test_the_reply_says_which_question_was_answered(self, monkeypatch):
        """A reader of `notes` must be able to tell the two apart."""
        from metascience_agent.tools.r_wrappers import r_grim
        self._captured(monkeypatch)
        assert r_grim(mean=28, n=41, decimals=0)["asked_as"] == "mean"
        assert r_grim(mean=28, n=41, decimals=0,
                      percentage=True)["asked_as"] == "percentage_share"

    @pytest.mark.skipif(
        shutil.which("Rscript") is None,
        reason="needs R with scrutiny installed",
    )
    def test_against_live_r_the_two_engines_now_agree(self):
        """The end-to-end claim, run against the real package: asked the share
        question, R reaches the same verdict as grim_percentage."""
        from metascience_agent.tools.grim import grim_test_percentage
        from metascience_agent.tools.r_wrappers import r_grim

        py = grim_test_percentage(28, 41, decimals=0, data_type="proportion")
        r = r_grim(mean=28, n=41, decimals=0, percentage=True)
        if not r.get("available"):
            pytest.skip(f"R cross-check unavailable: {r.get('error')}")
        assert py["severity"] == "impossible"
        assert r["consistent"] is False, "asked the share question, R must agree"
        # And the misapplication this guards against, pinned:
        as_mean = r_grim(mean=28, n=41, decimals=0)
        assert as_mean["consistent"] is True, (
            "28 IS a possible mean of 41 integers -- which is why passing a "
            "percentage as a mean reads as exoneration"
        )
