"""PyPI statcheck 0.0.7 mis-measures how many decimals a p-value was printed to.

Found by the validation sweep of 2026-08-27, re-derived against the R original,
and reproduced here minimally. `helpers_parse_stats.extract_p_value` does:

    249:  p_value.append(re.split(RGX_COMP, p_raw[i])[1])
    251:  # remove leading/trailing whitespaces        <- a comment, NO CODE
    254:  dec = re.search(RGX_DEC, p_value[i]).end() - 2   # not sure

R does:

    p_value <- trimws(p_value, which = "both")
    dec <- attr(regexpr(RGX_DEC, p_value), "match.length") - 1

`match.length` is position-independent; `.end()` equals `start + length`, so the
port carries the match's START as an error term, and the skipped `trimws` lets a
leading space -- which `RGX_P` explicitly permits -- push that start along.

`p_dec` is the ONLY place the reported p's printed precision enters the
comparison in `error_test`, so being one too high narrows the acceptance band by
a factor of ten. Like the sign bug, this is not our arithmetic.

WHAT THIS COSTS, MEASURED, and stated honestly because the filed severity was
higher than what a reader actually sees. Over 300 honest t-tests rendered
`p = 0.059`, the raw statcheck `Error` column falls from 134 to 57. Through
FMT's own `python_statcheck_text`, `errors_found` falls only 58 -> 57, because
`_within_printed_precision` was already absorbing nearly all of it. The repair
is still worth making at the root: `decision_errors` is NOT passed through that
filter (r_wrappers.py, `if stat["decision_error"]` has no precision guard beside
the one on `errors_found`), so relying on the downstream rescue leaves a path
that skips it.
"""
from __future__ import annotations

import contextlib
import io
import random

import pytest

statcheck = pytest.importorskip("statcheck", reason="statcheck is optional")

from forensic_metascience_ai_toolkit.tools.r_wrappers import (  # noqa: E402
    _patch_statcheck,
    _patch_statcheck_p_dec_bug,
)


def _p_dec(text: str):
    from statcheck.helpers_parse_stats import extract_p_value
    return list(extract_p_value(text)["p_dec"])


def _errors(lines: list[str]) -> int:
    from statcheck.st import statcheck as run
    with contextlib.redirect_stdout(io.StringIO()), \
         contextlib.redirect_stderr(io.StringIO()):
        df, _ = run(". ".join(lines))
    return int(df["Error"].sum())


def _honest(n: int = 120, seed: int = 11) -> list[tuple[int, float, float]]:
    """Exactly-correct t-tests: p computed from the statistic, then printed."""
    from statcheck.compute_p import compute_p
    random.seed(seed)
    out = []
    for _ in range(n):
        df = random.randint(5, 120)
        t = round(random.uniform(0.5, 4.5), 2)
        out.append((df, t, max(0.0005, compute_p("t", t, None, df, True))))
    return out


@pytest.fixture(autouse=True)
def _patched():
    assert _patch_statcheck_p_dec_bug(), "the shim must install for these tests"


class TestTheMeasurementItself:
    """R's rule against the port's, on the literals a paper actually prints."""

    def test_the_apa_style_was_read_one_too_high(self):
        """`p = 0.059` is printed to THREE decimals. The port said four."""
        assert _p_dec("t(20) = 2.00, p = 0.059") == [3]

    @pytest.mark.parametrize("text,dec", [
        ("t(20) = 2.00, p = 0.059", 3),
        ("t(20) = 2.00, p = .059", 3),
        ("t(20) = 2.00, p=0.059", 3),
        ("t(20) = 2.00, p = 0.0001", 4),
        ("F(1, 30) = 4.10, p = 0.052", 3),
    ])
    def test_every_rendering_of_a_three_decimal_p_reads_the_same(self, text, dec):
        assert _p_dec(text) == [dec]


class TestCrossRenderingIsTheProperty:
    """How a paper CHOOSES to render a p-value carries no information about
    whether it is correct, so the verdict must not depend on the rendering.
    This is the invariant; the point cases above are illustrations of it.

    It fails on the unpatched port: 134 errors for `p = 0.059` against 57 for
    the identical statistics written `p = .059` or `p=0.059`.
    """

    def test_the_same_statistics_get_the_same_count_in_every_style(self):
        rows = _honest()
        counts = {
            "apa_space": _errors([f"t({d}) = {t:.2f}, p = {p:.3f}" for d, t, p in rows]),
            "no_leading_zero": _errors([f"t({d}) = {t:.2f}, p = {p:.3f}".replace("= 0.", "= .")
                                        for d, t, p in rows]),
            "no_space": _errors([f"t({d}) = {t:.2f}, p={p:.3f}" for d, t, p in rows]),
        }
        assert len(set(counts.values())) == 1, (
            f"the rendering changed the verdict count: {counts}")


class TestRecallIsNotTradedAway:
    """A shim that widened every band would pass every test above.

    NOT the >= N-of-M floor a first draft proposed: that floor cannot fail,
    because these misreports are displaced far enough that they are caught at
    any p_dec. The property that CAN fail is the one asserted here -- the fix
    must not move a single genuine misreport out of `Error`.
    """

    def test_a_displaced_p_is_still_caught_in_every_style(self):
        rows = _honest(n=60, seed=5)
        for style in ("t({d}) = {t:.2f}, p = {p:.3f}",
                      "t({d}) = {t:.2f}, p={p:.3f}"):
            lines = [style.format(d=d, t=t, p=min(0.98, p + 0.02)) for d, t, p in rows]
            assert _errors(lines) == len(rows), (
                f"a genuine misreport escaped in style {style!r}")


class TestScientificNotationIsConvertedNotGuessed:
    """Both the port AND R undercount a p-value printed in scientific notation.

    R counts the MANTISSA's decimals and never sees the exponent, so it calls
    `1.5e-1` (0.15, two places) and `1.5e-2` (0.015, three) both ONE. Too few is
    not the harmless direction: `error_test` compares against
    `round(low_p, p_dec)`, so an undercount COLLAPSES both bounds onto a coarse
    grid and an honest value falls outside them. Measured over 300 honest results
    printed in e-notation: 203 flagged before, 0 after.

    Greg Fitzgerald proposed the conversion on 2026-08-27, calling it "close
    enough to exact preservation". It is exact: scientific notation asserts
    precision in the mantissa and the shifted decimal asserts the identical
    interval, so `decimals = mantissa_decimals - exponent`.

    This DELIBERATELY DIVERGES FROM R. The shim's warrant is "match R where R is
    right", and here R is demonstrably wrong.
    """

    @pytest.mark.parametrize("text,dec", [
        ("t(19) = 1.49, p = 1.5e-1", 2),      # 0.15
        ("t(19) = 1.49, p = 1.5e-2", 3),      # 0.015
        ("t(19) = 1.49, p = 2.30e-3", 5),     # 0.00230, trailing zero kept
        ("t(19) = 1.49, p = 9.9e-4", 5),      # 0.00099
    ])
    def test_the_decimals_are_those_of_the_value_not_the_mantissa(self, text, dec):
        assert _p_dec(text) == [dec]

    def test_the_window_it_implies_is_the_mantissas_own(self):
        """The claim that makes the conversion safe rather than merely tidy:
        the interval is unchanged, only its expression."""
        from decimal import Decimal
        for lit, dec in (("1.5e-1", 2), ("1.5e-2", 3), ("1.50e-1", 3)):
            mant, exp = lit.split("e")
            md = len(mant.split(".")[1]) if "." in mant else 0
            half_m = Decimal(5) * Decimal(10) ** (-md - 1)
            lo_m = (Decimal(mant) - half_m) * Decimal(10) ** int(exp)
            hi_m = (Decimal(mant) + half_m) * Decimal(10) ** int(exp)
            half_d = Decimal(5) * Decimal(10) ** (-dec - 1)
            assert (lo_m, hi_m) == (Decimal(lit) - half_d, Decimal(lit) + half_d)

    def test_a_precision_coarser_than_one_unit_is_refused_not_guessed(self):
        """`1.5e3` asserts [1450, 1550). No count of DECIMAL PLACES can express
        that, and reading it as "1500 at 0 dp" gives a window 100x too tight --
        the direction that accuses. The helper returns None and the shim then
        leaves upstream's value alone."""
        from forensic_metascience_ai_toolkit.tools.r_wrappers import _p_decimals
        assert _p_decimals("1.5e3") is None    # [1450, 1550): -2 decimal places
        # BUT NOT EVERY POSITIVE EXPONENT. `2.5e1` is 25 asserted to 0 dp, and
        # [24.5, 25.5) is exactly the mantissa's own window -- expressible, so
        # allowed. A first draft of this test asserted None here and was wrong.
        assert _p_decimals("2.5e1") == 0
        assert _p_decimals("2.50e2") == 0

    def test_e_notation_is_no_worse_than_the_same_values_in_decimal(self):
        """The end-to-end property, stated as a COMPARISON rather than a zero.

        An absolute "0 flagged" is the wrong assertion and a first draft used
        it: `_honest` floors p at 0.0005, so a result whose true p is below the
        floor is reported at a value it does not have, and statcheck flags it
        CORRECTLY. That is the fixture fabricating errors, not the reader
        finding them. The property that isolates this fix is that HOW a p is
        rendered must not change the verdict -- the same invariant as
        TestCrossRenderingIsTheProperty, extended to scientific notation.
        """
        from forensic_metascience_ai_toolkit.tools.r_wrappers import _p_decimals
        rows = [(d, t, p) for d, t, p in _honest(n=60, seed=3) if p > 0.0006]
        assert len(rows) > 30, "the fixture must retain enough decidable rows"
        sci = [f"t({d}) = {t:.2f}, p = {p:.1e}" for d, t, p in rows]
        dec = [f"t({d}) = {t:.2f}, p = "
               f"{('%%.%df' % _p_decimals('%.1e' % p)) % p}" for d, t, p in rows]
        assert _errors(sci) == _errors(dec) == 0

    def test_and_recall_survives_in_e_notation(self):
        rows = [r for r in _honest(n=60, seed=4) if r[2] > 0.0006]
        lines = [f"t({d}) = {t:.2f}, p = {min(0.98, p * 8 + 0.05):.1e}"
                 for d, t, p in rows]
        assert _errors(lines) == len(rows)


class TestTheShimItself:
    def test_it_is_idempotent(self):
        assert _patch_statcheck_p_dec_bug()
        assert _patch_statcheck_p_dec_bug()

    def test_it_marks_the_function_so_a_double_wrap_is_impossible(self):
        from statcheck.helpers_parse_stats import extract_p_value
        assert getattr(extract_p_value, "_fmt_pdec_patched", False)

    def test_the_modules_that_actually_call_it_see_the_patch(self):
        """`extract_stats.py` and `st.py` copy the function object at import
        time. Rebinding only the defining module would leave the real pipeline
        calling the original while a test reported the patch installed -- the
        exact trap the sign shim's own tests caught. This is why it walks
        sys.modules.
        """
        import statcheck.extract_stats as es
        assert getattr(es.extract_p_value, "_fmt_pdec_patched", False)

    def test_a_fragment_with_no_comparison_does_not_crash(self):
        assert isinstance(_p_dec("there were no statistics here"), list)


class TestBothRepairsReachBothEntryPoints:
    """`_patch_statcheck` exists because the sign shim was installed by the
    TEXT path and not by `_statcheck_pdf_via_vendored_reader`, so a paper read
    through statcheck's own PDF reader was still scored with transposed bounds.
    A fix that does not reach half its callers is the failure this guards.
    """

    def test_the_combined_installer_installs_both(self):
        assert _patch_statcheck()
        from statcheck.error_test import error_test
        from statcheck.helpers_parse_stats import extract_p_value
        assert getattr(error_test, "_fmt_sign_patched", False)
        assert getattr(extract_p_value, "_fmt_pdec_patched", False)

    def test_both_statcheck_entry_points_install_the_repairs(self):
        import inspect
        from forensic_metascience_ai_toolkit.tools import r_wrappers as rw
        for fn in (rw.python_statcheck_text, rw._statcheck_pdf_via_vendored_reader):
            src = inspect.getsource(fn)
            assert "_patch_statcheck()" in src, (
                f"{fn.__name__} enters statcheck without installing the repairs")
