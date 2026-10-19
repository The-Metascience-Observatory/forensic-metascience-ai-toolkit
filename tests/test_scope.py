"""What the toolkit has been tested on, and the document kinds it is not for.

Greg, 2026-08-11: a short-term disclaimer naming the study types the tool has
actually been exercised against; an explicit statement that it is not designed
for narrative reviews; and that auditing a meta-analysis or systematic review is
a separate undertaking rather than something this covers.
"""
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit import scope as S

REPO = Path(__file__).resolve().parents[1]


class TestTheClassifierReadsSelfDescriptionOnly:
    """MEASURED over 374 corpus PDFs: 1 fire, 0 false positives. The 5 papers
    that mention a meta-analysis on page 1 without tripping it were read by hand
    and are all primary studies citing the literature -- which is exactly the
    case a body-text keyword rule would have destroyed."""

    def test_a_meta_analysis_title_is_caught(self):
        r = S.classify_document(
            "Efficacy of cerebrolysin in acute stroke: a systematic review and "
            "meta-analysis of randomised trials")
        assert r["kind"] == "meta_analysis"
        assert r["confidence"] == "high"
        assert "separate undertaking" in r["stance"]

    def test_a_systematic_review_title_is_caught(self):
        r = S.classify_document("Interventions for postpartum depression: a systematic review")
        assert r["kind"] == "systematic_review"

    def test_a_narrative_review_title_is_caught(self):
        r = S.classify_document("Cerebrolysin in neurodegeneration: a narrative review")
        assert r["kind"] == "narrative_review"
        assert r["stance"] == "not designed for"

    @pytest.mark.parametrize("title,abstract", [
        ("Heterogeneous treatment effects of cerebrolysin as an early add-on to "
         "reperfusion therapy: post hoc analysis of the CEREHETIS trial",
         "Previous meta-analyses have reported inconsistent effects."),
        ("Cognitive-behavioral therapy for the prevention of postpartum depression",
         "A recent meta-analysis found a pooled effect of d = 0.34."),
        ("Beyond threshold prevalence: reframing treatment use in student insomnia",
         "Systematic reviews of insomnia prevalence vary widely."),
    ])
    def test_a_primary_study_citing_the_literature_is_not_caught(self, title, abstract):
        """THE FAILURE THAT MATTERS. Labelling a primary study out of scope tells
        a reader to discount a report we stand behind. All three of these are
        real page-1 texts from the corpus."""
        assert S.classify_document(title, abstract)["kind"] is None

    def test_an_abstract_only_match_is_medium_confidence(self):
        """A title is the paper naming itself; an abstract sentence is weaker
        evidence and must not be presented as equally settled."""
        r = S.classify_document("Effects of X on Y",
                                "We conducted a systematic review and meta-analysis of 14 trials.")
        assert r["kind"] == "meta_analysis"
        assert r["confidence"] == "medium"

    def test_meta_analysis_wins_over_systematic_review(self):
        """"A systematic review and meta-analysis" is one document. Reporting
        the vaguer of the two labels would understate what it is."""
        r = S.classify_document("A systematic review and meta-analysis of Z")
        assert r["kind"] == "meta_analysis"

    def test_nothing_said_is_not_the_same_as_primary_research(self):
        r = S.classify_document("", "")
        assert r["kind"] is None
        assert r["notice"] == ""

    def test_it_survives_none_inputs(self):
        assert S.classify_document(None, None)["kind"] is None


class TestTheNoticeSaysWhyNotJustThat:
    def test_narrative_review_names_the_wrong_authors_problem(self):
        n = S.classify_document("Cerebrolysin: a narrative review")["notice"]
        assert "not designed for" in n
        assert "quoted from somebody" in n or "belong to the papers" in n or \
               "did not produce the value" in n

    def test_meta_analysis_names_what_the_real_audit_would_be(self):
        n = S.classify_document("A meta-analysis of X")["notice"]
        for term in ("search completeness", "publication-bias"):
            assert term in n, term

    def test_every_out_of_scope_kind_has_a_stance_and_a_reason(self):
        for kind, spec in S.OUT_OF_SCOPE.items():
            assert spec["label"] and spec["stance"] and len(spec["why"]) > 80, kind


class TestTheScopeStatementIsHonestAboutTheCorpus:
    def test_it_names_the_families_with_no_representation(self):
        md = "\n".join(S.scope_markdown())
        for absent in ("qualitative", "bench chemistry", "genomics"):
            assert absent in md, absent

    def test_it_names_narrative_reviews_and_meta_analyses_explicitly(self):
        md = "\n".join(S.scope_markdown()).lower()
        assert "narrative review" in md
        assert "meta-analysis" in md
        assert "systematic review" in md

    def test_the_prose_denominator_matches_the_table(self):
        """A scope statement whose denominator drifts from its own table is
        worse than none, because it is checkable and wrong. This test caught
        exactly that on the first draft: the table summed to 25 runs while the
        prose above it claimed 36."""
        md = "\n".join(S.scope_markdown())
        assert f"{S.classified_runs()} runs on {S.CLASSIFIED_PAPERS}" in md
        assert f"{S.ARCHIVE_RUNS} runs over {S.ARCHIVE_PAPER_IDS} papers" in md
        assert str(S.classified_runs()) in S.tested_on_sentence()

    def test_the_archive_numbers_are_the_real_ones(self):
        """Measured against this checkout: 36 run_meta records, 19 distinct
        paper_ids (three of them blinded placeholders)."""
        import glob, json
        ids, runs = set(), 0
        for f in glob.glob(str(REPO / "**/run_meta.json"), recursive=True):
            # `scratchpad/` is throwaway. Bundles built there by an analysis
            # agent carry a run_meta.json apiece and inflated this count from
            # 36 to 41 -- scratch is not the archive, and counting it would
            # make the scope statement's denominator drift with whatever
            # somebody happened to be debugging.
            if "scratchpad" in f:
                continue
            try:
                d = json.load(open(f))
            except Exception:  # noqa: BLE001
                continue
            runs += 1
            ids.add(d.get("paper_id"))
        if not runs:
            pytest.skip("no archived runs in this checkout")
        # A FLOOR, NOT AN EQUALITY, and the churn is why. Every analysis run
        # adds a `run_meta.json`, so an equality assertion fails the suite each
        # time anybody analyses a paper -- it broke three times on 2026-08-11
        # alone, and a test that fails for doing the thing the project exists to
        # do is a test people learn to edit rather than read.
        #
        # Understating is the SAFE direction and the only one that matters: the
        # disclaimer says "at least N runs", so reality exceeding N keeps the
        # claim true. The constant exceeding reality would be an overstatement
        # of our own evidence base, which is the thing this module exists to
        # prevent, and that still fails.
        assert S.ARCHIVE_RUNS <= runs, (
            f"scope.ARCHIVE_RUNS claims {S.ARCHIVE_RUNS} runs; the archive holds "
            f"{runs}. Overstating the evidence base is the one direction that "
            "is not allowed.")
        assert S.ARCHIVE_PAPER_IDS <= len(ids), (
            f"scope.ARCHIVE_PAPER_IDS claims {S.ARCHIVE_PAPER_IDS}; the archive "
            f"holds {len(ids)}.")

    def test_the_rct_share_is_stated_rather_than_averaged_away(self):
        """The corpus is not "biomedical research"; it is mostly human RCTs, and
        a reader with a rodent study deserves to know that."""
        biggest = max(S.TESTED_ON, key=lambda t: t[1])
        assert "randomised trials" in biggest[0]
        assert biggest[1] >= sum(c for _, c, _ in S.TESTED_ON) / 3


class TestItReachesTheReader:
    def test_the_standing_disclaimer_carries_the_short_form(self):
        from forensic_metascience_ai_toolkit.disclaimer import DISCLAIMER_LONG
        # Normalised: the constant is hard-wrapped, so a phrase can straddle a
        # newline and a literal `in` check fails on wording that is correct.
        flat = " ".join(DISCLAIMER_LONG.split())
        assert "not designed for narrative reviews" in flat
        assert "separate undertaking" in flat
        assert "human randomised trials" in flat

    def test_the_closing_section_includes_the_full_scope_statement(self):
        from forensic_metascience_ai_toolkit.disclaimer import closing_section_markdown
        md = "\n".join(closing_section_markdown())
        assert "## What this has been tested on" in md
        assert "qualitative" in md

class TestTheRefusalCountIsNotReadAsADefectTally:
    """Greg, 2026-08-11: "it wouldn't do to have the user come away with the
    impression that there were more errors and omissions than there actually
    are." A bare count of checks that did not run is exactly that impression."""

    def _rows(self, *reasons):
        return [{"location": f"L{i}", "reason": r} for i, r in enumerate(reasons)]

    def test_the_reading_names_our_share_against_the_total(self):
        from forensic_metascience_ai_toolkit.viewer_facts import refusal_tally
        t = refusal_tally(self._rows(
            "Not applicable to this design.",
            "The paper reports no standard deviations.",
            "The supplement was not provided to us.",
            "No validated tool exists for this.",
        ))
        assert t["our_shortfall"] == 1
        assert t["not_our_shortfall"] == 3
        assert "1 of them because this toolkit could not do it" in t["reading"]

    def test_when_none_are_ours_it_says_so_first(self):
        from forensic_metascience_ai_toolkit.viewer_facts import refusal_tally
        t = refusal_tally(self._rows("Not applicable.", "The paper prints no exact p."))
        assert t["our_shortfall"] == 0
        assert "None" in t["reading"] and "limitation of this toolkit" in t["reading"]

    def test_an_empty_list_produces_no_sentence(self):
        from forensic_metascience_ai_toolkit.viewer_facts import refusal_tally
        assert refusal_tally([])["reading"] == ""

    def test_unclassified_points_at_the_reason_rather_than_announcing_a_failure(self):
        """"not classified" was our bookkeeping word printed in a column headed
        "whose limit". A reader met it as a defect of unknown kind."""
        from forensic_metascience_ai_toolkit.viewer_facts import classify_refusal, refusal_tally
        c = classify_refusal("something the rules do not match at all zzz")
        assert c["key"] == "unclassified"          # the alarm still keys on this
        assert "classif" not in c["label"].lower()  # ...but the reader does not see it
        assert refusal_tally(self._rows("zzz nothing matches"))["classifier_failing"]

    def test_the_sentence_reaches_the_page(self):
        src = (REPO / "src/forensic_metascience_ai_toolkit/bundle.py").read_text(encoding="utf-8")
        assert '"refusals": _vf.refusal_tally(' in src
        assert "D.facts.refusals.reading" in src


class TestTheCorpusSamplerFrame:
    """`eval/corpus_expansion.py` declares the sampling frame for the families
    `scope.NOT_TESTED` names. It is the answer to the long-term half of Greg's
    2026-08-11 instruction, and its frame is the thing that has to be right --
    a corpus assembled by someone who knows what they are looking for is not a
    sampling frame (#135)."""

    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "corpus_expansion", REPO / "eval/corpus_expansion.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_the_review_exclusion_is_not_silently_inert(self):
        """IT WAS. Assembled through a non-raw string, its leading word boundary
        became a literal backspace (0x08), so the first alternative required a
        control character no title contains -- the filter matched nothing while
        looking like it worked, and "A review on polymeric hydrogel membranes"
        landed in a bucket of primary research."""
        m = self._mod()
        assert "\x08" not in m._REVIEW_TITLE.pattern, "leading \\b became a backspace again"
        for title in ("A review on polymeric hydrogel membranes",
                      "Metal Oxide Nanoparticles: Review of Synthesis",
                      "A survey of deep learning methods",
                      "Breastfeeding and intelligence: a meta-analysis"):
            assert m._REVIEW_TITLE.search(title), title
        for title in ("Green synthesis and characterization of silver nanoparticles",
                      "RNA-seq based detection of differentially expressed genes"):
            assert not m._REVIEW_TITLE.search(title), title

    def test_every_family_in_NOT_TESTED_that_can_be_sampled_has_a_frame(self):
        m = self._mod()
        keys = {f["key"] for f in m.FRAMES}
        for expected in ("qualitative", "bench_chemistry_materials", "genomics_omics",
                         "economics_polisci", "single_case_small_n",
                         "simulation_modelling"):
            assert expected in keys, expected

    def test_the_syntheses_are_in_their_own_bucket(self):
        """Greg: auditing a meta-analysis is a separate undertaking. Sampling
        them into the same file as primary research is how that decision gets
        quietly undone six months from now."""
        m = self._mod()
        sep = {f["key"] for f in m.FRAMES if f["bucket"] == "separate_undertaking"}
        assert sep == {"meta_analysis", "umbrella_meta_meta"}
        assert not any(f["bucket"] == "primary" and "meta" in f["key"]
                       for f in m.FRAMES)

    def test_narrative_reviews_are_not_sampled_at_all(self):
        """No version of the plan runs the toolkit on one, so a corpus of them
        has no use."""
        m = self._mod()
        assert not any("narrative" in f["key"] for f in m.FRAMES)

    def test_the_draw_is_seeded_and_the_seed_is_a_parameter(self):
        """Greg's rule: any simulation supplies and records its seed. A draw
        nobody can reproduce is not a sampling frame either."""
        m = self._mod()
        src = (REPO / "eval/corpus_expansion.py").read_text(encoding="utf-8")
        assert isinstance(m.DEFAULT_SEED, int)
        assert "random.Random(a.seed)" in src
        # Comment lines stripped first: the module DOCUMENTS why it does not
        # call `random.seed()`, and a raw substring check trips on the prose
        # that explains the rule it is enforcing.
        code = "\n".join(l.split("#", 1)[0] for l in src.splitlines())
        assert "random.seed(" not in code, "global RNG"
        assert '"seed": a.seed' in src, "the draw must RECORD its seed, not just use one"


class TestNamingAReviewIsNotClaimingToBeOne:
    """A citation of the review literature is the most common sentence in a
    primary study's introduction, and the old patterns read it as the paper
    describing its own design. The consequence is not a rounding error: the
    notice lands at `limitations[0]`, so the first thing a reader is told about
    a randomised trial is that this toolkit does not apply to it.

    The shape of the fix is `locate and judge` -- the patterns say only that a
    review design is NAMED, and a separate judge asks whether the clause claims
    it for THIS paper. The judge requires a self-reference rather than listing
    the ways a paper can point elsewhere, so an unrecognised phrasing stays
    silent instead of firing wrongly.
    """

    # (name, title, text) -- every one of these is a primary study.
    NOT_A_REVIEW = [
        ("an RCT whose introduction cites a pooled estimate",
         "Effect of early rehabilitation after stroke: a randomised controlled trial",
         "Background. A recent random-effects meta-analysis of 14 trials reported "
         "a moderate benefit. Methods. We randomised 120 patients..."),
        ("'this systematic review' as anaphora to a cited work",
         "Long-term follow-up of the Olds cohort",
         "This systematic review by Olds et al. summarised earlier findings; here "
         "we report long-term follow-up of our own cohort."),
        ("meta-analyses as the SUBJECT MATTER of a trial",
         "Do meta-analyses overestimate treatment effects? A randomised head-to-head trial",
         ""),
        ("'meta-analytic' as a bare adjective",
         "A meta-analytic framework applied to new trial data", ""),
        ("PRISMA describing how a CITED synthesis was run",
         "Cerebrolysin in acute ischaemic stroke: a randomised trial",
         "Following PRISMA guidance, an earlier synthesis pooled 9 trials. We "
         "conducted a double-blind RCT."),
        ("a plain literature sentence",
         "Effects of X on Y",
         "Several meta-analyses have reported inconsistent effects."),
        ("agreeing with the review literature",
         "Effects of X on Y",
         "Our findings are consistent with the meta-analysis literature."),
        ("excluding studies a previous review covered",
         "Effects of X on Y",
         "We excluded studies already included in the previous meta-analysis."),
        # VERBATIM from cerebrolysin_papers/10.3389--fphar.2023.1288718. The
        # loosened locator DOES match this ("conducted ... meta-analysis"); only
        # the judge stops it. Kept as a test because it is the real-corpus proof
        # that the judge, not the pattern, is what carries the safety.
        ("a primary study USING meta-analytic technique",
         "Heterogeneity of treatment effect in stroke",
         "Heterogeneous treatment effect analysis was conducted using techniques "
         "of meta-analysis and the matching-smoothing method."),
    ]

    IS_A_REVIEW = [
        ("plain meta-analysis title",
         "Cerebrolysin for stroke: a meta-analysis", "", "meta_analysis"),
        # The design contradiction must not swallow this: nearly every medical
        # meta-analysis names randomised trials in its title, as its MATERIAL.
        ("a meta-analysis OF randomised trials",
         "A systematic review and meta-analysis of randomised controlled trials",
         "", "meta_analysis"),
        ("systematic review title",
         "Interventions for postpartum depression: a systematic review",
         "", "systematic_review"),
        ("narrative review title",
         "Cerebrolysin in neurodegeneration: a narrative review",
         "", "narrative_review"),
        ("meta-analytic modifying a review noun",
         "A meta-analytic review of priming effects", "", "meta_analysis"),
        ("self-described in the body",
         "Effects of X on Y",
         "We conducted a systematic review and meta-analysis of 22 trials.",
         "meta_analysis"),
        # The old locator hard-coded "we conducted a meta-analysis" and missed
        # an adverb in the middle; and `search` stopped at the first mention,
        # which here is a citation.
        ("self-description AFTER a citation, with an adverb in the way",
         "Effects of X on Y",
         "A 2019 meta-analysis by Lee et al. found no effect. We therefore "
         "conducted a meta-analysis of 30 newer trials.", "meta_analysis"),
        ("'the present meta-analysis'",
         "Effects of X on Y",
         "In the present meta-analysis we pooled 12 trials.", "meta_analysis"),
    ]

    def test_naming_a_review_does_not_classify_the_paper_as_one(self):
        from forensic_metascience_ai_toolkit.scope import classify_document
        wrong = [(n, classify_document(t, a)["kind"])
                 for n, t, a in self.NOT_A_REVIEW
                 if classify_document(t, a)["kind"] is not None]
        assert not wrong, f"primary studies reclassified as reviews: {wrong}"

    def test_a_paper_that_IS_a_review_is_still_caught(self):
        from forensic_metascience_ai_toolkit.scope import classify_document
        wrong = [(n, classify_document(t, a)["kind"], want)
                 for n, t, a, want in self.IS_A_REVIEW
                 if classify_document(t, a)["kind"] != want]
        assert not wrong, f"real reviews missed or mislabelled: {wrong}"

    def test_the_judge_is_what_stops_the_corpus_near_miss(self):
        """Not the pattern. If someone later tightens the locator and deletes
        the judge, this fails and says which half did the work."""
        import re
        import forensic_metascience_ai_toolkit.scope as S
        s = ("Heterogeneous treatment effect analysis was conducted using "
             "techniques of meta-analysis and the matching-smoothing method.")
        located = [m for _k, pat in S._ABSTRACT_PATTERNS
                   for m in re.finditer(pat, s, re.I)]
        assert located, "expected the locator to match this sentence"
        assert not any(S._mention_is_self_description(s, m.start(), m.end())
                       for m in located)

    def test_a_design_named_as_the_reviews_MATERIAL_is_not_a_contradiction(self):
        import forensic_metascience_ai_toolkit.scope as S
        assert S._names_its_own_primary_design(
            "A meta-analysis of randomised controlled trials") is None
        assert S._names_its_own_primary_design(
            "A randomised controlled trial of X") is not None
