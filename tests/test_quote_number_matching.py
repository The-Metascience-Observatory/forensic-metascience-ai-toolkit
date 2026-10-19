"""The number matcher must not wave through fabricated or misstated numbers.

Each case here was a CONFIRMED defect found by adversarial audit (venv repros):
a fabricated APA decimal passing `stitched`, a quote number matching inside a
larger number as `verbatim`, a sign-flip passing `stitched`, and a quote number
matching the last group of a thousands-separated number. All four are false
all-clears about the quote's own accuracy -- the class this module exists to
stop.
"""

from forensic_metascience_ai_toolkit.quotes import classify, normalise


def H(paper: str) -> dict:
    return {"the paper's text": normalise(paper)}


class TestFabricatedNumbersDoNotPassStitched:
    def test_apa_decimal_absent_from_paper_is_not_stitched(self):
        # r = .99 is fabricated; APA style (no leading zero) was invisible to the
        # tokenizer, so `stitched` ("every number appears") was granted blind.
        v = classify("n = 100, and the correlation was r = .99",
                     H("We recruited n = 100 undergraduates for the study."))
        assert v["quote_verified"] == "unverified"

    def test_apa_decimal_present_is_found(self):
        v = classify("the correlation was r = .99",
                     H("the correlation was r = .99 in the sample"))
        assert v["quote_verified"] == "verbatim"

    def test_apa_decimal_present_but_sentence_assembled_is_stitched(self):
        v = classify("n = 100 and r = .99",
                     H("we had r = .99 here and n = 100 there, separately"))
        assert v["quote_verified"] == "stitched"

    def test_sign_flip_is_not_stitched(self):
        # Quote says -0.21; the paper says +0.21. A directional flip is the worst
        # number to wave through, and the unsigned tokenizer did exactly that.
        v = classify("a negative association, r = -0.21, p = 0.04",
                     H("we observed a positive association, r = 0.21, p = 0.04"))
        assert v["quote_verified"] == "unverified"

    def test_a_real_negative_still_verifies(self):
        v = classify("the effect was d = -0.21 overall",
                     H("in the analysis the effect was d = -0.21 overall"))
        assert v["quote_verified"] == "verbatim"

    def test_a_group_of_a_thousands_number_is_not_a_match(self):
        # "345" is not present in a paper that only says "12,345".
        v = classify("we recruited 345 participants for follow-up",
                     H("the registry contained 12,345 records in total"))
        assert v["quote_verified"] == "unverified"


class TestDotLedDecimalIsNotFoundInsideALargerNumber:
    def test_point_86_does_not_verify_against_40_point_86(self):
        # .86 (0.86) matching inside 40.86 was stamped `verbatim` -- "As printed"
        # -- misstating the paper's value by ~47x.
        v = classify(".86 was the correlation we measured in the cohort",
                     H("we note that 40.86 was the correlation we measured in the cohort"))
        assert v["quote_verified"] != "verbatim"
        assert v["quote_verified"] == "unverified"


class TestExistingBehaviourPreserved:
    """The matcher's earlier guarantees must survive the rewrite."""

    HAY = {"the paper's text": normalise(
        "The interaction was reliable, F(1, 38) = 7.21, p = .011, "
        "with a mean of 3.45 (SD 1.02). Attrition was 12 of 50.")}

    def test_n42_not_in_n428(self):
        hay = H("the final sample was n = 428")
        assert classify("n = 42", hay)["quote_verified"] == "unverified"

    def test_n428_verbatim(self):
        hay = H("the final sample was n = 428")
        assert classify("n = 428", hay)["quote_verified"] == "verbatim"

    def test_4_2_not_in_4_28(self):
        hay = H("we saw a ratio of 4.28 overall")
        assert classify("the ratio was 4.2 overall", hay)["quote_verified"] == "unverified"

    def test_page_reference_is_not_a_decimal(self):
        hay = H("Table 2 on page 22 reports 39.87")
        assert classify("reports 39.87 [PDF p.22]", hay)["quote_verified"] == "stitched"

    def test_stitched_sentence(self):
        v = classify("mean 3.45, SD 1.02, F = 7.21, n = 50", self.HAY)
        assert v["quote_verified"] == "stitched"

    def test_minus_matches_hyphen_verbatim(self):
        hay = {"the paper's text": normalise("the change was −0.42 points")}
        assert classify("the change was -0.42 points", hay)["quote_verified"] == "verbatim"
