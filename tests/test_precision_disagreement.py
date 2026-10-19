"""An extractor's trailing zero is a false-accusation pathway.

MEASURED 2026-08-20. Two readings of the same page disagree about PRECISION,
not about value: `body.md` reads `35.4` where docling reads `35.40`, `1.09`
against `1.090`, `3.4` against `3.40`. Neither is corrupt. Both are the same
number.

But GRIM's granularity is a function of the decimal count, and over 3,606 means
at six sample sizes **480 (13%) flip their GRIM verdict between one and two
decimals -- every single one from consistent to INCONSISTENT.** So an extractor
that renders a trailing zero the paper did not print can turn an honest value
into an accusation, and nothing in the pipeline was comparing the two readings.

`agreement.py` was written for exactly this and had zero importers.
"""

import pytest

from metascience_agent.agreement import compare
from metascience_agent.tools.grim import _mean_passes_grim


class TestTheDecimalCountDecidesTheVerdict:
    @pytest.mark.parametrize("mean,n", [(0.2, 52), (0.3, 52), (0.7, 52), (0.8, 52)])
    def test_a_trailing_zero_can_flip_grim_to_inconsistent(self, mean, n):
        """The direction is always the same, and it is the dangerous one."""
        one_dp, _ = _mean_passes_grim(mean, n, 1)
        two_dp, _ = _mean_passes_grim(mean, n, 2)
        assert one_dp is True and two_dp is False

    def test_the_flip_rate_is_not_negligible(self):
        flips = tot = 0
        for n in (20, 30, 40, 52, 68, 100):
            for i in range(601):
                m = round(i / 10, 1)
                tot += 1
                a, _ = _mean_passes_grim(m, n, 1)
                b, _ = _mean_passes_grim(m, n, 2)
                flips += a != b
        assert flips / tot > 0.10, (
            f"only {flips}/{tot} flip; if this has fallen, re-measure before "
            "relaxing the differential-reading guard")

    def test_no_flip_ever_goes_the_safe_way(self):
        """Every flip turns consistent into inconsistent. A precision error
        therefore ACCUSES; it never quietly excuses."""
        for n in (20, 30, 40, 52, 68, 100):
            for i in range(601):
                m = round(i / 10, 1)
                a, _ = _mean_passes_grim(m, n, 1)
                b, _ = _mean_passes_grim(m, n, 2)
                if a != b:
                    assert a is True and b is False, (m, n, a, b)


class TestTheDisagreementIsVisible:
    def test_a_precision_difference_is_reported_as_a_disagreement(self):
        a = "The mean was 35.4 and the SD 1.09."
        b = "The mean was 35.40 and the SD 1.090."
        c = compare(a, b, label_a="body.md", label_b="docling")
        assert c["n_only_in_a"] == 2 and c["n_only_in_b"] == 2
        assert set(c["only_in_a"]) == {"35.4", "1.09"}
        assert set(c["only_in_b"]) == {"35.40", "1.090"}

    def test_identical_readings_agree_completely(self):
        t = "Mean 35.4 (SD 1.09), n = 68."
        assert compare(t, t)["agreement"] == 1.0

    def test_it_does_not_say_which_reading_is_right(self):
        """It cannot, and claiming otherwise would be the guess the toolkit
        refuses. The note has to say so."""
        c = compare("35.4", "35.40")
        assert "not evidence that either is wrong" in c["note"]
