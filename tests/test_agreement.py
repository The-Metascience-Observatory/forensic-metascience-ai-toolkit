"""Two readings of one page, and where they disagree about a number.

MEASURED across the 22 damaged papers, text layer vs full-page OCR: median
agreement 0.907, worst 0.709, best 0.982. 9,490 numbers agreed; 1,953 did not.
The per-paper rate is the triage signal and the disagreeing values are the work
list."""

from forensic_metascience_ai_toolkit.agreement import compare, suspect_values

A = "Age was 65 ± 1.17 years, p < 0.05, n = 68 patients."


class TestAgreement:
    def test_identical_readings_agree_completely(self):
        r = compare(A, A)
        assert r["agreement"] == 1.0
        assert r["n_only_in_a"] == r["n_only_in_b"] == 0

    def test_a_changed_digit_is_caught(self):
        r = compare(A, A.replace("1.17", "6.1"))
        assert r["only_in_a"] == {"1.17": 1}
        assert r["only_in_b"] == {"6.1": 1}

    def test_it_does_not_say_which_reading_is_right(self):
        """It cannot, and claiming otherwise would be the guess the toolkit
        refuses. The value is reported from both sides."""
        r = compare(A, A.replace("1.17", "6.1"))
        assert r["only_in_a"] and r["only_in_b"]
        assert "cannot be decided" in r["note"]

    def test_a_quiet_reading_cannot_score_well_by_finding_less(self):
        """The rate is over the UNION. A reading that simply drops numbers must
        score worse, or the metric would reward silence -- which is exactly how
        an extraction failure hides."""
        r = compare(A, "Age was 65 years.")
        assert r["agreement"] < 0.6

    def test_thousands_separators_are_not_a_disagreement(self):
        """The two extractors disagree about separators for reasons that have
        nothing to do with the digits."""
        r = compare("a cohort of 1,204 patients", "a cohort of 1204 patients")
        assert r["agreement"] == 1.0

    def test_the_work_list_carries_context(self):
        """A count of disagreements is not actionable: a reader needs the
        sentence to take to the PDF."""
        s = suspect_values(A, A.replace("1.17", "6.1"))
        assert {x["value"] for x in s} == {"1.17", "6.1"}
        assert all(x["context"] for x in s)

    def test_empty_input_does_not_crash_or_claim_agreement(self):
        assert compare("", "")["agreement"] is None


class TestTheBibliographyWasInflatingIt:
    """MEASURED over 21 papers with two commercial extractions each: whole-
    document agreement between Mistral and Mathpix is 0.924, analytic-only is
    0.887. The difference is a reference list.

    Bibliographies and publisher download stamps are plain text that every
    extractor reads identically, so leaving them in adds a block of guaranteed
    agreement and flatters whichever comparison is being run."""

    A = ("# Body\n\n## Results\n\nmean 4.2 and p 0.05\n\n"
         "## References\n\n1. Smith 1999, 12, 345-350\n")
    B = A.replace("4.2", "4.3")

    def test_the_reference_list_is_excluded(self):
        assert compare(self.A, self.B)["agreement"] > \
               compare(self.A, self.B, analytic=True)["agreement"]

    def test_a_download_stamp_is_dropped(self):
        from forensic_metascience_ai_toolkit.agreement import analytic_only
        t = ("# Body\n\n## Results\n\nthe effect was 2.5\n"
             "15525279, 2016, 78, Part_8, Downloaded from onlinelibrary.wiley.com\n")
        out = analytic_only(t)
        assert "2.5" in out and "15525279" not in out

    def test_it_trims_shared_furniture_not_one_side(self):
        """The retained fraction was measured at 70-93% of each document and
        within a few points across sources on the same paper, so this is not
        quietly cutting one extractor more than another."""
        from forensic_metascience_ai_toolkit.agreement import analytic_only
        keep = len(analytic_only(self.A)) / len(self.A)
        assert 0.2 < keep < 1.0

    def test_default_is_unchanged(self):
        """`analytic` is opt-in: existing callers keep whole-document behaviour
        rather than silently changing what their numbers mean."""
        assert compare(self.A, self.B)["agreement"] == \
               compare(self.A, self.B, analytic=False)["agreement"]


class TestTheSignIsPartOfTheNumber:
    """`_numbers` carried its own pattern with no sign in it, so `-1.6` was read
    as `1.6` and two readings of a page that disagreed about a sign were
    reported as AGREEING.

    That blinded this comparison to the one corruption it would be most useful
    for. The documented headline defect of this workstream is exactly a sign
    flip: a printed effect of `-0.85 (95% CI -1.2, -0.3)` reaching a check as
    POSITIVE 0.85, and twenty-one means arriving with the wrong sign in one
    paper's tables. A sign flip inverts a conclusion.

    MEASURED over 2,340 real labels and cells from the eleven-paper run: 73
    parsed differently from `numerals.NUMERAL`, and every single difference was
    a negative number read as its absolute value. Preventive on that corpus --
    the two readings there never disagree about a sign -- and the blindness was
    real regardless.
    """

    def test_a_sign_flip_is_not_reported_as_agreement(self):
        r = compare("the effect was -1.6", "the effect was 1.6")
        assert r["agreement"] < 1.0, "a flipped sign is a disagreement"

    def test_a_negative_number_survives_reading(self):
        from forensic_metascience_ai_toolkit.agreement import _numbers
        assert _numbers("d = -0.85")["-0.85"] == 1
        assert _numbers("d = -0.85")["0.85"] == 0

    def test_an_interval_is_not_read_as_a_negative_number(self):
        """`1.08-1.9` is a range whose upper bound is positive. Allowing a
        leading minus must not turn the separator into one."""
        from forensic_metascience_ai_toolkit.agreement import _numbers
        got = _numbers("CI 1.08-1.9")
        assert got["1.08"] == 1 and got["1.9"] == 1 and got["-1.9"] == 0

    def test_a_hyphenated_word_yields_no_number(self):
        """`COVID-19` is one word. The guard that knows this lives beside the
        pattern in `numerals.tokens`, so a caller cannot take one without the
        other."""
        from forensic_metascience_ai_toolkit.agreement import _numbers
        assert _numbers("COVID-19 patients")["-19"] == 0

    def test_a_leading_plus_is_normalised_but_a_minus_never_is(self):
        """Two extractors disagree about a `+` for reasons that are not about
        the digits. They do not disagree about a `-` for any such reason."""
        assert compare("change of +1.5", "change of 1.5")["agreement"] == 1.0
        assert compare("change of -1.5", "change of 1.5")["agreement"] < 1.0


class TestASharedLexerRemovesIndependenceToo:
    """`_numbers` delegates to `numerals.tokens`, which is right for
    correctness and costs something real: two readings can no longer disagree
    about tokenisation, so a lexer bug corrupts both identically and this
    comparison reports agreement on garbage. It did, on Lancet-style text,
    until `numerals.NUMERAL` learned the middle dot.

    The mitigation is not to stop sharing -- it is to keep the shared lexer
    under test against the conventions the corpus actually contains.
    """

    def test_a_typographic_mark_is_not_a_disagreement_about_the_digits(self):
        r = compare("the estimate was -5·077 (95% CI -7·716 to -2·437)",
                    "the estimate was -5.077 (95% CI -7.716 to -2.437)")
        assert r["agreement"] == 1.0

    def test_but_a_sign_still_is(self):
        assert compare("effect -1.6", "effect 1.6")["agreement"] < 1.0

    def test_a_lancet_reading_is_not_shredded_before_comparison(self):
        from forensic_metascience_ai_toolkit.agreement import _numbers
        assert _numbers("-5·077")["-5.077"] == 1
        assert _numbers("-5·077")["077"] == 0
