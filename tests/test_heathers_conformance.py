"""What the founding text says a forensic report must do, pinned as tests.

James Heathers, "An Introduction to Forensic Metascience" (Linnaeus
University, 14 Feb 2025, doi:10.5281/zenodo.14871843) coined the term this
toolkit is named after and defines the field's purpose and its norms. A full
read against this registry found we implement or exceed nearly every numerical
technique in the book. What we were missing was not arithmetic -- it was three
things the book is emphatic about and our output was silent on.

1. SCOPE. "More problems with published papers have been noticed via detection
   of similarities, differences, or impossibilities within visual elements than
   all other techniques combined." We perform none of that, and until now no
   report said so. A report that mentions figures at all is exactly the one a
   reader will assume covered them.

2. DIRECTION. "Forensic metascientific analysis is designed to modify trust by
   evaluating research consistency. It is not designed to 'find fraud'." Trust
   moves both ways: "When analysis determines elements within a paper are
   perfectly internally consistent, this should increase trustworthiness as
   well."

3. BASE RATES. Every anomaly class in the book is paired with its modal
   innocent cause. Olsen (2002): 35 of 88 studies (40%) reported the standard
   error where they said standard deviation. An anomaly reported without its
   base rate reads as an accusation.
"""

from forensic_metascience_ai_toolkit import registry as R
MINIMAL = {"headline": {"severity": "consistent", "statement": "x"},
           "findings": [], "coverage_summary": {"stats_found": 1, "stats_checked": 1}}


class TestTheBenignExplanationTravelsWithTheAnomaly:
    def test_the_sd_se_card_carries_the_measured_base_rate(self):
        """40% of studies reporting a dispersion reported the SEM instead
        (Olsen 2002). A tool that flags SD/SE confusion without saying that is
        inviting the reader to read incompetence as misconduct."""
        card = R.BY_NAME["check_sd_or_se"].integrity_card()
        joined = " ".join(card["assumptions"])
        assert "40%" in joined
        assert "integrity" in joined.lower()


class TestTheModelIsToldToLookForWhatTheBookLooksFor:
    """These are prompt contents, not code paths -- but a prompt nobody checks
    is a prompt that silently loses a section, which has happened here before
    (guidance written into tool_reference.md that was never sent to the model)."""

    def _sweep(self):
        return (R.__file__.rsplit("registry.py", 1)[0]
                + "modules/tools_agent/prompt.md")

    def _editorial(self):
        return (R.__file__.rsplit("registry.py", 1)[0]
                + "modules/adjudicator/prompt.md")

    def test_the_sweep_asks_about_hand_drawn_figures(self):
        text = open(self._sweep(), encoding="utf-8").read()
        assert "hand" in text.lower() and "capital T" in text

    def test_the_sweep_forbids_implying_image_forensics(self):
        text = open(self._sweep(), encoding="utf-8").read()
        assert "not performing image forensics" in text

