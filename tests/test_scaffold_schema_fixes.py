"""The four schema fixes from the first JATS end-to-end run (2026-09-06).

Each was a defect the account showed a READER: 15 of 24 comparisons were
abstract/discussion restatements with free-text direction prose; 9 integrity
problems were Methods values naming a paper-level wave with no study; `bounds`
was None on every variable while `levels` gave 1..5; the header read
`.  . DOI not stated` for a paper whose <article-meta> carries all four; and
every location printed `p.?` because XML has no pages.
"""
from __future__ import annotations

from forensic_metascience_ai_toolkit.scaffold import bind as B
from forensic_metascience_ai_toolkit.scaffold import document as D
from forensic_metascience_ai_toolkit.scaffold import render as R
from forensic_metascience_ai_toolkit.scaffold import schema as S


def _cmp(**kw) -> dict:
    c = {"id": "cmp:x", "study_id": "study:a", "outcome_variable_id": None,
         "contrast": {"group_ids": [], "phase_ids": [], "description": "a vs b"},
         "test_type_stated": None, "test_type_quote": None, "post_hoc_stated": None,
         "statistic_printed": "t = 2.1", "df_printed": None, "p_printed": None,
         "p_threshold": None, "significance": "significant", "direction": "first_higher",
         "direction_words": None, "reported_in_kind": "results_text",
         "reported_in": "Results text", "quote": "a was higher than b",
         "detailed_statistics_elsewhere": None}
    c.update(kw)
    return c


def _val(**kw) -> dict:
    v = {"id": "val:x", "variable_id": None, "statistic": "n", "printed": "68", "numeric": 68,
         "coordinate": {"study_id": None, "group_id": None, "phase_id": None}, "quote": "n = 68"}
    v.update(kw)
    return v


def _account(**kw) -> dict:
    a = {k: {} for k in S.ACCOUNT_TOP_LEVEL}
    for k in ("procedures", "phases", "studies", "variables", "values", "comparisons", "claims",
              "figure_panels", "supplements_referenced", "gaps", "accounting"):
        a[k] = []
    a["studies"] = [{"id": "study:a", "groups": [{"id": "grp:g"}], "phases": [{"id": "phase:own"}]}]
    a.update(kw)
    return a


class TestClosedVocabularies:
    def test_design_type_enum_is_exactly_the_template_keys(self):
        enum = S.pass1_schema()["properties"]["studies"]["items"]["properties"]["design_type"]["enum"]
        assert set(enum) == set(S.DESIGN_TEMPLATES), "one definition, not two"
        assert {"longitudinal_panel", "cross_sectional", "parallel_rct"} <= set(enum)

    def test_direction_is_closed_and_a_free_text_one_is_a_problem(self):
        cmp = S.pass3_schema()["properties"]["comparisons"]["items"]["properties"]
        assert cmp["direction"]["enum"] == list(S.DIRECTIONS)
        assert cmp["reported_in_kind"]["enum"] == list(S.REPORTED_IN_KINDS)
        probs = S.validate_account(_account(comparisons=[_cmp(direction="Positive: more X went with more Y")]))
        assert any("direction" in p and "outside the vocabulary" in p for p in probs)
        assert not [p for p in S.validate_account(_account(comparisons=[_cmp()])) if "direction" in p]

    def test_subjects_carry_human_and_organizational_fields(self):
        sub = S.pass1_schema()["properties"]["subjects"]["properties"]
        assert {"population", "unit_of_analysis", "setting", "recruitment", "eligibility",
                "species", "strain"} <= set(sub)


class TestPaperLevelPhases:
    def test_a_methods_value_may_name_a_paper_level_phase(self):
        a = _account(phases=[{"id": "phase:wave1", "label": "Wave 1", "when": "2020"}],
                     values=[_val(coordinate={"study_id": None, "group_id": None, "phase_id": "phase:wave1"})])
        assert not [p for p in S.validate_account(a) if "unknown phase" in p]

    def test_an_undeclared_phase_is_still_a_problem(self):
        a = _account(values=[_val(coordinate={"study_id": None, "group_id": None, "phase_id": "phase:wave9"})])
        assert [p for p in S.validate_account(a) if "unknown phase" in p]

    def test_a_study_listing_no_phases_runs_on_the_papers(self):
        studies = [{"id": "study:a", "design_type": "longitudinal_panel",
                    "groups": [{"id": "g", "assignments": []}], "phases": []}]
        assert B.template_problems(studies, {}, [{"id": "phase:w1"}, {"id": "phase:w2"}]) == []
        assert B.template_problems(studies, {}, []) != []

    def test_phases_is_a_top_level_key_of_the_account(self):
        assert "phases" in S.ACCOUNT_TOP_LEVEL
        assert "phases" in S.pass1_schema()["properties"]


class TestRestatementsAreClaims:
    def test_an_abstract_restatement_with_no_evidence_is_demoted(self):
        probs: list[str] = []
        kept, dem = B.demote_restatements(
            [_cmp(id="cmp:a", reported_in_kind="abstract", statistic_printed=None,
                  p_printed=None, p_threshold=None, quote="X was associated with Y")], probs)
        assert kept == [] and len(dem) == 1
        d = dem[0]
        assert (d["demoted_from_comparison"], d["location"], d["kind"], d["study_ids"]) == \
            ("cmp:a", "abstract", "finding", ["study:a"])
        assert d["text"] == "X was associated with Y" and probs

    def test_a_results_sentence_without_a_printed_statistic_is_kept(self):
        kept, dem = B.demote_restatements([_cmp(statistic_printed=None, p_printed=None, p_threshold=None)], [])
        assert len(kept) == 1 and dem == [], "the statistic is usually in a table; the gap records it"

    def test_a_discussion_sentence_carrying_a_threshold_is_kept(self):
        kept, dem = B.demote_restatements([_cmp(reported_in_kind="discussion", statistic_printed=None,
                                                p_printed=None, p_threshold=0.05)], [])
        assert len(kept) == 1 and dem == []

    def test_old_output_without_the_kind_field_is_read_off_the_label(self):
        c = _cmp(reported_in="Discussion text", statistic_printed=None, p_printed=None, p_threshold=None)
        c.pop("reported_in_kind")
        kept, dem = B.demote_restatements([c], [])
        assert dem and not kept


class TestNoBoundIsDerivedFromLevels:
    def test_the_derivation_is_gone_and_the_reason_is_recorded(self):
        # Withdrawn on evidence from the first JATS paper: a level list can be
        # incomplete (6 of 7 levels listed against stated bounds 1..7), so a
        # bound derived from it is tighter than the truth -- the route to a
        # false `impossible`.
        assert not hasattr(B, "derive_bounds_from_levels")
        import inspect
        assert "NO BOUNDS ARE DERIVED FROM LEVELS" in inspect.getsource(B)


class TestLocationHandle:
    def test_a_section_stands_in_when_there_is_no_page(self):
        assert R._where({"page": 3, "section": "Methods"}) == "p.3"
        assert R._where({"page": None, "section": "Methods"}).startswith("§ Methods")
        assert R._where({"page": None, "section": None}) == "p.?"
        assert R._where(7) == "p.7"

    def test_section_at_reads_the_heading_or_falls_back_to_the_kind(self):
        secs = [{"name": "Methods", "kind": "methods", "start": 0, "end": 10},
                {"name": "", "kind": "results", "start": 10, "end": 20}]
        assert D.section_at(secs, 5) == "Methods"
        assert D.section_at(secs, 15) == "results"
        assert D.section_at(secs, None) is None and D.section_at(secs, 99) is None


class TestPaperIdentity:
    def test_front_matter_wins_and_a_disagreement_is_recorded(self):
        probs: list[str] = []
        p = B.paper_identity({"title": "a paper", "journal": None, "year": 2024, "doi": None},
                             {"title": "A Paper", "journal": "J", "year": "2025", "doi": "10.1/x",
                              "source": "<article-meta>"}, probs)
        assert (p["journal"], p["year"], p["doi"]) == ("J", 2025, "10.1/x")
        assert p["identity_source"].startswith("front matter")
        assert any("paper.year" in x for x in probs)
        assert not any("paper.title" in x for x in probs), "case and whitespace are not disagreements"

    def test_no_front_matter_keeps_the_model_reading_and_says_so(self):
        p = B.paper_identity({"title": "T"}, None, [])
        assert (p["identity_source"], p["title"]) == ("model reading", "T")
