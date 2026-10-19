"""A tie between two plausible readings must not produce an accusation.

`check_sd_or_se` asks whether a dispersion labelled SD (or SE) is really the
other one. When BOTH readings are plausible it has established nothing -- and it
used to resolve that tie by hardcoding `likely = "SD"`, described in the code as
"the literal reading". The literal reading is whatever the paper LABELLED. For an
SE-labelled value the default contradicted the page, and the tool reported
`suspicious` mislabeling off a coin-flip.

VERIFIED FALSE ACCUSATION: 8 archived calls across 3 papers, every one of which
the paper had labelled correctly. Ladurner Table 1, CNS row: SE = 0.09, n = 78,
scale 4.5-8. Read as SE it implies SD = 0.79, 23% of the scale range, entirely
ordinary for 78 stroke patients. Read as SD it implies 0.09 -- 2.6% of the range,
an implausibly tight spread. The tool preferred the reading the paper did not
use, then flagged the paper for not using it.
"""

from metascience_agent.registry import BY_NAME


def _check(value, n, reported_as, lo, hi, decimals="2"):
    return BY_NAME["check_sd_or_se"].call({
        "reported_value": value, "n": n, "reported_as": reported_as,
        "decimals": decimals, "variable_range_min": lo, "variable_range_max": hi,
        "bound_source": "stated"})


class TestATieDefersToThePapersLabel:
    def test_the_eight_archived_false_accusations_are_gone(self):
        for value, n in ((0.09, 78), (0.14, 68), (0.2, 78), (0.2, 68)):
            r = _check(value, n, "SE", 4.5, 8)
            assert r["severity"] == "consistent", (value, n, r.get("explanation"))

    def test_an_sd_labelled_tie_is_unchanged(self):
        # label SD + likely SD was already `consistent`; deferring to the label
        # must not move it.
        assert _check(0.09, 78, "SD", 4.5, 8)["severity"] == "consistent"

    def test_a_tie_never_returns_an_accusation_either_way(self):
        for label in ("SD", "SE"):
            sev = _check(0.09, 78, label, 4.5, 8)["severity"]
            assert sev not in ("suspicious", "highly_suspicious", "impossible"), label


class TestDiscriminatingPowerSurvives:
    """The fix may not buy its safety by making the check inert."""

    def test_a_genuinely_impossible_dispersion_still_fires(self):
        # SE = 3.0 with n = 78 implies SD = 26.5 on a 4.5-8 scale: impossible
        # under either reading.
        r = _check(3.0, 78, "SE", 4.5, 8, decimals="1")
        assert r["severity"] in ("suspicious", "highly_suspicious", "impossible")

    def test_a_real_mislabel_is_still_caught(self):
        # A value plausible ONLY as an SE, labelled SD -- not a tie, so the
        # label-deference rule does not apply and the diagnosis stands.
        r = _check(9.0, 100, "SD", 0, 10)
        assert r["severity"] != "consistent"
