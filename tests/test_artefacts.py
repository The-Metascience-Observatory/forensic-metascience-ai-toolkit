"""A paper's linked code, data and registrations must be surfaced.

MEASURED on the 95-paper high-value corpus: 11.6% name a code repository,
32.6% carry a trial registration, 88.4% have a data-availability statement. On
the older cerebrolysin corpus it is ~1%, so this is a property of modern
reporting standards rather than of papers in general.

Nothing here fetches anything. Downloading what a paper links to has its own
consequences and is the operator's decision; this module reads text and reports.
"""
import pytest

from metascience_agent.artefacts import find, find_in_paper


class TestDetection:
    @pytest.mark.parametrize("text,kind", [
        ("code at https://github.com/ofekfink/BMI", "github"),
        ("see https://osf.io/x7g9k for materials", "osf"),
        ("archived at https://gitlab.com/group/proj", "gitlab"),
        ("deposited 10.5281/zenodo.1234567", "zenodo"),
        ("data at https://figshare.com/articles/x/1", "figshare"),
    ])
    def test_repository_kinds(self, text, kind):
        assert kind in find(text)["repositories"]

    @pytest.mark.parametrize("text,kind", [
        ("registered as NCT03020186", "clinicaltrials"),
        ("ISRCTN12345678", "isrctn"),
        ("PROSPERO CRD42020123456", "prospero"),
    ])
    def test_registration_kinds(self, text, kind):
        assert kind in find(text)["registrations"]

    def test_registrations_are_separated_from_repositories(self):
        """They support different checks: a registration bears on outcome
        switching, a repository on the analysis itself."""
        r = find("NCT03020186 and https://github.com/a/b")
        assert r["n_registrations"] == 1 and r["n_repositories"] == 1

    def test_trailing_punctuation_is_stripped(self):
        r = find("available at https://github.com/a/b.")
        assert r["repositories"]["github"] == ["https://github.com/a/b"]

    def test_duplicates_collapse(self):
        r = find("https://osf.io/abc and again https://osf.io/abc")
        assert len(r["repositories"]["osf"]) == 1

    def test_clean_text_finds_nothing(self):
        r = find("The mean was 5.5 (SD 1.2) in Table 2.")
        assert not r["repositories"] and not r["registrations"]


class TestAvailabilityStatement:
    @pytest.mark.parametrize("text", [
        "Data availability: on request.",
        "Code and data sharing statement follows.",
        "The dataset is available from the corresponding author.",
    ])
    def test_detected(self, text):
        assert find(text)["has_availability_statement"]

    def test_absent(self):
        assert not find("Results are shown in Table 1.")["has_availability_statement"]


class TestReporting:
    def test_note_says_nothing_was_fetched(self):
        note = find_in_paper_text("code at https://github.com/a/b")
        assert "Nothing was fetched" in note
        assert "--artefact" in note

    def test_absence_is_reported_as_weak_evidence(self):
        """A dropped data-availability statement looks identical to not having
        one, so the absence must not be stated as a fact about the paper."""
        note = find_in_paper_text("Plain text with no links.")
        assert "weak evidence" in note

    def test_links_without_a_statement_are_qualified(self):
        note = find_in_paper_text("see https://github.com/a/b for the toolbox")
        assert "incidental" in note

    def test_missing_directory_does_not_raise(self, tmp_path):
        assert find_in_paper(tmp_path / "nope")["n_repositories"] == 0


def find_in_paper_text(text):
    from metascience_agent.artefacts import summarise
    return summarise(find(text))


class TestPreregistration:
    """The strongest handle a text-only pass has on OUTCOME SWITCHING.

    A paper that registered one primary outcome and reports another is the
    classic case, and no arithmetic check in this toolkit can see it.
    """

    def _p(self, text):
        from metascience_agent.artefacts import preregistration
        return preregistration(text)

    def test_a_registration_id_means_preregistered(self):
        assert self._p("Registered at ClinicalTrials.gov NCT03020186.")["status"] == \
            "preregistered"

    def test_explicit_denial_is_its_own_state(self):
        """Distinct from silence, and it is CANDOUR rather than a finding."""
        r = self._p("This trial was not registered because data collection began in 1998.")
        assert r["status"] == "explicitly_not_preregistered"
        assert "candour" in r["note"]

    def test_silence_is_reported_as_weak_evidence(self):
        """Registration statements sit in sections extraction often drops, so
        absence here is not evidence that none exists."""
        r = self._p("We measured outcomes at six months.")
        assert r["status"] == "not_mentioned"
        assert "WEAK" in r["note"]

    def test_registered_studies_are_not_treated_as_cleared(self):
        note = self._p("NCT03020186")["note"]
        assert "can still switch outcomes" in note


class TestPreregistrationPrecision:
    """Each of these was a false positive found while calibrating on the corpus."""

    def _p(self, text):
        from metascience_agent.artefacts import preregistration
        return preregistration(text)

    def test_as_predicted_prose_is_not_the_aspredicted_platform(self):
        """`as ?predicted` matched "was predicted by the Papini et al. model"."""
        r = self._p("whether the effect was predicted by the Papini et al. model")
        assert r["status"] == "not_mentioned"
        assert not r["aspredicted"]

    def test_deviations_from_normality_are_not_protocol_deviations(self):
        assert not self._p(
            "MANOVA is fairly robust to deviations from normality")["deviation_passages"]

    def test_bare_post_hoc_is_not_a_deviation(self):
        """Post-hoc analysis is ordinary, and reporting it is good practice."""
        assert not self._p("Post hoc analyses showed a booster effect.")["deviation_passages"]


class TestDeviationDisclosure:
    def _p(self, text):
        from metascience_agent.artefacts import preregistration
        return preregistration(text)

    def test_explicit_deviation_is_caught(self):
        r = self._p("We deviated from the preregistered analysis plan by adding covariates.")
        assert r["deviation_passages"]

    def test_analyses_first_word_order(self):
        """Papers write "the secondary analyses ... were not pre-registered" at
        least as often as the reverse, and requiring only the reverse order
        missed every real instance in the corpus."""
        r = self._p("Registered NCT02737566. The secondary analyses described in "
                    "this manuscript were not pre-registered.")
        assert r["status"] == "preregistered"
        assert r["deviation_passages"], "mixed case: registered trial, unregistered analyses"

    def test_a_disclosed_deviation_is_surfaced_in_the_note(self):
        r = self._p("NCT03020186. We deviated from the registered protocol in two ways.")
        assert "departures" in r["note"]


class TestAvailableFromIsHowAPaperNamesItsSupplier:
    """`has_availability_statement` suppresses the caveat "the links may be
    incidental rather than a sharing commitment", and makes bundle.py assert "A
    data-availability statement is present but names no repository" -- a claim
    about the authors' reporting conduct. It was decided by a pattern with no
    SUBJECT: `availab\\w+ (from|at|on|upon|via)`, which is also how a paper says
    where it bought its reagents.
    """

    NOT_A_STATEMENT = [
        # Ubiquitous in this repo's own corpus.
        "Cerebrolysin was available from EVER Pharma (Unterach, Austria).",
        "Recruitment flyers are available upon request from the first author.",
        "All reagents were available from Sigma-Aldrich.",
        # Publisher boilerplate -- the single commonest hit in the corpus.
        "Contents lists available at ScienceDirect",
        "Full list of author information is available at the end of the article",
        # Verbatim from cerebrolysin_papers/10.1007--s00429-015-1015-x.
        "The rats were familiarized to the maze with 0.1 g chocolate pieces "
        "freely available on the arms.",
        # Verbatim from cerebrolysin_papers/10.1007--s10072-019-04053-5.
        "Patients were assigned the lowest patient number available from the "
        "treatment packs at the site.",
    ]
    IS_A_STATEMENT = [
        "Data availability: the dataset is deposited at OSF.",
        "Code and materials sharing is described below.",
        "Data are available from the corresponding author upon request.",
        "Analysis code is available at github.com/lab/study.",
        "The analysis scripts are available upon request.",
        "De-identified participant data are available from the authors on request.",
    ]

    def test_a_supply_sentence_is_not_a_data_availability_statement(self):
        from metascience_agent.artefacts import has_availability_statement
        fooled = [t for t in self.NOT_A_STATEMENT if has_availability_statement(t)]
        assert not fooled, f"read as availability statements: {fooled}"

    def test_a_real_statement_is_still_recognised(self):
        from metascience_agent.artefacts import has_availability_statement
        missed = [t for t in self.IS_A_STATEMENT
                  if not has_availability_statement(t)]
        assert not missed, f"real statements missed: {missed}"

    def test_bare_materials_does_not_carry_the_prose_form(self):
        """"Materials were available from Sigma-Aldrich" is a reagent-supply
        sentence. `materials` stays in the HEADING pattern, where the words
        only co-occur when the paper is making the statement. The two errors
        do not cost the same: a miss adds a conservative caveat, a false
        positive asserts something about the authors' conduct."""
        from metascience_agent.artefacts import has_availability_statement
        assert not has_availability_statement(
            "Materials were available from Sigma-Aldrich.")
        assert has_availability_statement("Materials availability statement")

    def test_find_reports_the_judged_value(self):
        from metascience_agent.artefacts import find
        assert find("Cerebrolysin was available from EVER Pharma."
                    )["has_availability_statement"] is False
