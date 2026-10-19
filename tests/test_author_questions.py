"""Fairness of the questions we put to authors.

The sentence that prompted this module, from a real run
(`10.1038--s41537-025-00576-3`, question 7):

    "Supplementary eTable 5 contains the BIC and other fit indices used to
     select the four-class solution. Could those values be reported in the main
     text or supplied as a plain CSV, together with the entropy and average
     class-membership probabilities for the 2- to 6-class models?"

Greg: it "sounds insane because it is seeming to imply that information can be
added to the main text of an article that has already been published (and is
therefore uneditable) and also seems to be impugning the authors for OUR lack of
the supplementary materials!"
"""
import pytest

from forensic_metascience_ai_toolkit import author_questions as AQ

REAL_BAD_QUESTION = (
    "Supplementary eTable 5 contains the BIC and other fit indices used to "
    "select the four-class solution. Could those values be reported in the main "
    "text or supplied as a plain CSV, together with the entropy and average "
    "class-membership probabilities for the 2- to 6-class models?"
)


class TestTheUneditableAskDetector:
    def test_it_catches_the_question_that_started_this(self):
        hits = AQ.find_uneditable_asks([{"question": REAL_BAD_QUESTION}])
        assert len(hits) == 1
        assert hits[0]["index"] == 0
        assert "main" in hits[0]["matched"] and "text" in hits[0]["matched"]
        assert "cannot be edited" in hits[0]["problem"]

    @pytest.mark.parametrize("text", [
        "Could the fit indices be reported in the main text?",
        "Please include these values in the manuscript.",
        "Could Table 3 be added to the paper?",
        "Would you amend the text to give the exact p-value?",
        "Could the degrees of freedom be stated in the article?",
    ])
    def test_asks_aimed_at_the_published_article_are_flagged(self, text):
        assert AQ.find_uneditable_asks([{"question": text}])

    @pytest.mark.parametrize("text", [
        # THE CORRECT FORM, and by far the commonest. A detector that fired on
        # these would flag nearly every legitimate question and be switched off
        # within a week, so its narrowness is the feature.
        "Could you supply the unrounded QALY increments for each of the three ICERs?",
        "Would it be possible to provide the exact p-values and degrees of freedom?",
        "Could you send the participant-level data, or the counts underlying Table 1?",
        "Could you confirm the Day 180 p-value, and state whether 0.54 should read 0.054?",
        # Quoting what the paper ALREADY says is not a request to change it.
        "The Methods state that enrolment was limited to patients in their 20s.",
        "Table 1 and the Results text both give the mean age as 23.9 years.",
        # Asking about the supplement, not the article.
        "Could those values be supplied as a plain CSV?",
    ])
    def test_ordinary_requests_are_not_flagged(self, text):
        assert AQ.find_uneditable_asks([{"question": text}]) == []

    def test_it_reports_the_span_so_a_reader_can_check_the_flag(self):
        """A flag nobody can audit is just an assertion."""
        hit = AQ.find_uneditable_asks([{"question": REAL_BAD_QUESTION}])[0]
        assert hit["matched"] in REAL_BAD_QUESTION

    def test_one_hit_per_question_not_one_per_pattern(self):
        text = "Could this be added to the main text and stated in the manuscript?"
        assert len(AQ.find_uneditable_asks([{"question": text}])) == 1

    def test_empty_and_malformed_input_is_not_a_crash(self):
        assert AQ.find_uneditable_asks(None) == []
        assert AQ.find_uneditable_asks([]) == []
        assert AQ.find_uneditable_asks([{}, {"question": None}, "bare string"]) == []


class TestTheSupplementRequest:
    """GREG'S RULE: where we lack known supplementary material, the FIRST
    question is a polite request for it, assuming the sender lacks access."""

    MISSING = {"missing": True, "reference_count": 4,
               "styles": {"Supplementary Table": 3, "Supplementary Figure": 1}}

    def test_it_fires_when_the_paper_cites_material_we_do_not_hold(self):
        q = AQ.supplement_request(self.MISSING)
        assert q is not None
        assert q["kind"] == "supplement_request"

    def test_it_asks_rather_than_accuses(self):
        q = AQ.supplement_request(self.MISSING)["question"].lower()
        assert q.startswith("would you be able to send")
        # The gap is OURS and the sentence must say so.
        assert "we have not been able to obtain" in q
        # Nothing that reads as a reproach or as a claim about their conduct.
        for reproach in ("fail", "should have", "did not provide", "omitted",
                         "missing from", "not report", "neglect"):
            assert reproach not in q, f"reads as a criticism: {reproach!r}"

    def test_it_never_asks_them_to_change_the_published_article(self):
        """The generated question must itself pass the detector -- otherwise the
        fix reintroduces the defect it exists to remove."""
        q = AQ.supplement_request(self.MISSING)
        assert AQ.find_uneditable_asks([q]) == []

    def test_it_does_not_invent_specifics_about_a_file_it_never_opened(self):
        """Naming 'eTable 5' when the audit only counted references would be us
        asserting a specific about a file we have never read."""
        q = AQ.supplement_request({"missing": True, "reference_count": 2})["question"]
        assert "eTable" not in q
        assert "in 2 places" in q

    def test_no_request_when_nothing_is_missing(self):
        assert AQ.supplement_request({"missing": False, "reference_count": 0}) is None

    def test_no_request_WHEN_WE_COULD_NOT_READ_THE_PAPER(self):
        """`missing is None` means the audit could not answer the question.

        `supplements.audit` is emphatic that None is not "no". It is equally not
        "yes": inventing a request for material we have no evidence exists is a
        different way of being unfair. When we cannot read the paper the honest
        output is the refusal already reported elsewhere.
        """
        assert AQ.supplement_request({"missing": None, "reference_count": 0}) is None

    def test_garbage_in_returns_none_rather_than_a_question(self):
        for bad in (None, {}, [], "supplements", {"missing": "yes"}):
            assert AQ.supplement_request(bad) is None


class TestApply:
    def test_the_request_goes_FIRST(self):
        """Greg: 'the first author question should be a polite request'. It is
        first because everything after it may already be answered by the file,
        and a reader seeing the later questions alone cannot know that."""
        report = {"questions_for_authors": [{"question": "Could you supply the SDs?"}]}
        AQ.apply(report, {"missing": True, "reference_count": 1})
        qs = report["questions_for_authors"]
        assert qs[0]["kind"] == "supplement_request"
        assert len(qs) == 2

    def test_it_reports_uneditable_asks_without_rewriting_them(self):
        """The detector makes the defect COUNTABLE. It does not silently edit an
        outgoing question -- that is its own way of shipping something nobody
        reviewed."""
        report = {"questions_for_authors": [{"question": REAL_BAD_QUESTION}]}
        out = AQ.apply(report, {"missing": False})
        assert len(out["uneditable_asks"]) == 1
        assert report["questions_for_authors"][0]["question"] == REAL_BAD_QUESTION

    def test_a_clean_report_is_untouched(self):
        report = {"questions_for_authors": [{"question": "Could you send Table 2?"}]}
        out = AQ.apply(report, {"missing": False})
        assert out == {"supplement_request_added": False, "uneditable_asks": [],
                       "promoted_refusals": 0}
        assert len(report["questions_for_authors"]) == 1

    def test_a_report_with_no_questions_still_gets_the_request(self):
        """A paper with no findings can still be one whose supplement we lack,
        and that is exactly the case where the request is most obviously not a
        criticism."""
        report = {}
        AQ.apply(report, {"missing": True, "reference_count": 3})
        assert report["questions_for_authors"][0]["kind"] == "supplement_request"

    def test_it_survives_a_missing_or_malformed_report(self):
        assert AQ.apply(None, {"missing": True})["supplement_request_added"] is False
        assert AQ.apply("not a report", {"missing": True})["uneditable_asks"] == []


class TestPromotingRefusalsIntoQuestions:
    """A refusal is not automatically a criticism, and most of them are not
    questions either.

    A check declined because the paper does not print an input says something
    about the publication -- but "statcheck found zero statistics to verify" put
    to an author is a remark about their reporting style wearing a question
    mark, and that is the shape of unfairness this module exists to prevent.

    MEASURED over 128 distinct `paper`-typed refusals in the archive: 15 are
    "the paper says it did X and does not print the numbers", 10 are "the values
    exist only as marks on a chart", and 101 are neither. Only the first two are
    promoted -- both are named by the taxonomy's own definition of the bucket,
    and both are answerable by sending a number.
    """

    STATED = {
        "location": "Latent class analysis",
        "reason": ("The paper states the four-class solution was chosen by "
                   "smallest BIC \"and other fit indices\" but prints no BIC, no "
                   "entropy, no likelihood and no membership probabilities."),
    }
    FIGURE = {
        "location": "Fig. 2",
        "reason": ("These values exist only as bars in the figure. The text "
                   "gives summary ranges only."),
    }
    NOT_A_QUESTION = {
        "location": "statcheck across the full body text",
        "reason": ("statcheck ran successfully and found zero statistics to "
                   "verify. This is a property of the paper's reporting style "
                   "rather than a tool failure: the chi-squared values appear "
                   "nowhere."),
    }
    OUR_OWN_LIMIT = {
        "location": "All figures",
        "reason": ("No figure of any kind was viewed in this review. Where a "
                   "paper presents an outcome only as a chart, the group means "
                   "and dispersion needed for an effect size often appear "
                   "nowhere in the text."),
    }

    def test_a_stated_but_unshown_method_is_promoted(self):
        out = AQ.promotable_refusals([self.STATED])
        assert len(out) == 1
        assert out[0]["shape"] == "stated_but_not_shown"

    def test_values_that_exist_only_as_marks_on_a_chart_are_promoted(self):
        out = AQ.promotable_refusals([self.FIGURE])
        assert len(out) == 1
        assert out[0]["shape"] == "only_in_a_figure"

    def test_a_bare_reporting_style_remark_is_NOT_promoted(self):
        """It is typed `paper` and it is true, and it is still not a question.
        Asking an author why they reported no test statistics is a criticism."""
        assert AQ.promotable_refusals([self.NOT_A_QUESTION]) == []

    def test_OUR_limit_is_never_promoted_even_when_it_mentions_charts(self):
        """THE FAIRNESS GUARD. This row is about our pass, not the article.
        Promoted, it asks the authors to account for a gap we created -- the
        exact defect that produced this module."""
        assert AQ.promotable_refusals([self.OUR_OWN_LIMIT]) == []

    def test_a_refusal_that_is_NOT_the_papers_limit_is_never_promoted(self):
        for reason in ("Supplement 2 was not provided.",
                       "No tool in this kit converts a chi-squared to a p-value.",
                       "Not applicable. This is a cross-sectional analysis."):
            assert AQ.promotable_refusals([{"reason": reason}]) == []

    def test_the_question_text_is_FIXED_and_asserts_nothing_about_the_paper(self):
        """The pipeline does not write prose about a paper it has not verified.
        The only claim the sentence makes is about US -- that we did not locate
        the values -- which is true by construction, since it is why the check
        was refused."""
        q = AQ.promotable_refusals([self.STATED])[0]["question"]
        assert "may well be somewhere we did not look" in q
        for accusatory in ("failed to", "should have", "omitted", "did not report",
                           "missing from", "neglected"):
            assert accusatory not in q.lower()

    def test_the_reviews_own_words_are_quoted_not_paraphrased(self):
        """If the reason is mistaken -- and it is unverified model prose -- the
        author must be able to see exactly what was claimed and correct it."""
        rec = AQ.promotable_refusals([self.STATED])[0]
        assert self.STATED["reason"] in rec["why"]
        assert "not a verified fact about the article" in rec["why"]

    def test_the_location_travels_so_the_ask_is_specific(self):
        assert AQ.promotable_refusals([self.FIGURE])[0]["question"].startswith("Fig. 2:")

    def test_garbage_rows_are_skipped_rather_than_raising(self):
        assert AQ.promotable_refusals(None) == []
        assert AQ.promotable_refusals(["a string", None, {}, {"reason": ""}]) == []


class TestPromotionIsWiredIntoApply:
    """Built, tested, never invoked is this repo's recurring failure. These
    assert on `apply`, which is what the pipeline actually calls."""

    def _report(self):
        return {
            "questions_for_authors": [{"question": "A question the model wrote."}],
            "not_checked": [TestPromotingRefusalsIntoQuestions.STATED,
                            TestPromotingRefusalsIntoQuestions.FIGURE,
                            TestPromotingRefusalsIntoQuestions.NOT_A_QUESTION],
        }

    def test_apply_promotes_and_counts(self):
        report = self._report()
        out = AQ.apply(report, {"missing": False})
        assert out["promoted_refusals"] == 2
        assert len(report["questions_for_authors"]) == 3

    def test_promoted_questions_go_LAST(self):
        """The model looked at this paper and chose not to ask these. A
        pipeline-generated request must not outrank a reviewer's judgement."""
        report = self._report()
        AQ.apply(report, {"missing": False})
        kinds = [q.get("kind") for q in report["questions_for_authors"]]
        assert kinds == [None, "unreported_value_request", "unreported_value_request"]

    def test_the_supplement_request_still_comes_first_of_all(self):
        report = self._report()
        AQ.apply(report, {"missing": True, "reference_count": 2})
        kinds = [q.get("kind") for q in report["questions_for_authors"]]
        assert kinds[0] == "supplement_request"
        assert kinds[-1] == "unreported_value_request"

    def test_a_report_with_no_refusals_is_unchanged(self):
        report = {"questions_for_authors": [], "not_checked": []}
        assert AQ.apply(report, {"missing": False})["promoted_refusals"] == 0
