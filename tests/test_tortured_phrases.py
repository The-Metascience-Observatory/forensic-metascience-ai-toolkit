"""Semantics of `detect_tortured_phrases`: every named false-positive class
has a test here, and the pre-registered severity ladder is pinned.

The tool ships QUARANTINED: delivered severity is `indeterminate` whenever the
ladder says anything accusatory, with the raw grade in
`severity_before_quarantine`. Tests assert the LADDER through that key, and
the quarantine mechanics separately -- so releasing the quarantine later is a
one-line change here (swap the helper), not a rewrite.
"""

from __future__ import annotations

import pytest

from metascience_agent.tools.tortured_phrases import detect_tortured_phrases

# Guarded fingerprints from the seed dictionary, one per planted count.
P1 = "counterfeit consciousness"
P2 = "flag to clamor"
P3 = "bosom peril"

FILLER = (
    "We measured the outcome in a randomized trial of adults. "
    "The intervention group received standard care plus the program. ")


def graded(result: dict) -> str:
    """The pre-registered grade: what severity WOULD be without quarantine."""
    return result.get("severity_before_quarantine") or result["severity"]


def run(text: str) -> dict:
    return detect_tortured_phrases(text=text)


class TestLadder:
    def test_zero_matches_is_consistent_with_coverage_caveat(self):
        r = run(FILLER * 3)
        assert r["severity"] == "consistent"
        assert r["n_distinct_fingerprints"] == 0
        assert any("not evidence" in c for c in r["caveats"])

    def test_k1_indeterminate(self):
        r = run(FILLER + f"Using {P1} methods. " + FILLER)
        assert graded(r) == "indeterminate"
        assert r["n_distinct_fingerprints"] == 1

    def test_k2_suspicious(self):
        r = run(FILLER + f"Using {P1} and the {P2} ratio. " + FILLER)
        assert graded(r) == "suspicious"
        assert r["n_distinct_fingerprints"] == 2

    def test_k3_highly_suspicious(self):
        r = run(FILLER + f"{P1}, the {P2} ratio, and {P3} screening. ")
        assert graded(r) == "highly_suspicious"
        assert r["n_distinct_fingerprints"] == 3

    def test_repetition_is_one_event(self):
        r = run(FILLER + f"{P1} and {P1} and {P1}. ")
        assert r["n_distinct_fingerprints"] == 1
        assert r["n_matches"] == 3
        assert graded(r) == "indeterminate"

    def test_impossible_unreachable(self):
        # 5 distinct fingerprints + boilerplate: the strongest possible input
        r = run(f"{P1}. {P2}. {P3}. irregular timberland. cruel temperature. "
                "As an AI language model, I cannot fulfill this request.")
        assert graded(r) == "highly_suspicious"  # the hard cap

    def test_expected_phrases_never_match(self):
        r = run("Artificial intelligence with a signal to noise ratio; "
                "breast cancer screening via random forest.")
        assert r["n_matches"] == 0
        assert r["severity"] == "consistent"


class TestBoilerplate:
    def test_first_person_disclaimer_is_highly_suspicious(self):
        r = run(FILLER + "As an AI language model, I cannot verify this. ")
        assert graded(r) == "highly_suspicious"

    def test_knowledge_cutoff_single_is_suspicious(self):
        r = run(FILLER + "as of my last knowledge update, no data existed. ")
        assert graded(r) == "suspicious"

    def test_llm_topic_paper_drops_one_tier(self):
        text = (FILLER +
                "We study ChatGPT and other LLMs from OpenAI via prompt "
                "engineering. As of my last knowledge update, no data. ")
        r = run(text)
        assert r["paper_discusses_llms"] is True
        assert graded(r) == "indeterminate"
        assert any("discusses LLMs" in c for c in r["caveats"])

    def test_cs_entry_needs_exact_case(self):
        assert run(FILLER + "we regenerate response curves. ")["n_matches"] == 0
        r = run(FILLER + "…Regenerate response… ")
        assert r["n_matches"] == 1

    def test_high_ambiguity_boilerplate_never_counts(self):
        r = run(FILLER + "As a large language model, GPT-4 performs well. ")
        (m,) = r["matches"]
        assert m["suppressed_by"] == "ambiguous_fingerprint"
        assert r["severity"] == "consistent"


class TestGuards:
    def test_references_section_excluded(self):
        text = (FILLER + "\n\n# References\n\n"
                f"1. Smith J. The {P1} approach. Retracted J. 2021.\n")
        r = run(text)
        assert r["references_delimited"] is True
        assert r["n_matches_references"] == 1
        assert r["n_distinct_fingerprints"] == 0
        assert r["severity"] == "consistent"
        (m,) = r["matches"]
        assert m["section"] == "references"
        assert m["suppressed_by"] == "references_section"

    def test_no_references_heading_announces_blindness(self):
        r = run(FILLER + f"{P1}. " + FILLER)
        assert r["references_delimited"] is False
        assert any("references_not_delimited" in c for c in r["caveats"])

    def test_quoted_match_suppressed(self):
        text = (FILLER +
                f'Cabanac calls this pattern "{P1}" in his survey of mills. ')
        r = run(text)
        (m,) = r["matches"]
        assert m["in_quotation"] is True
        assert m["suppressed_by"] == "quotation"
        assert r["n_distinct_fingerprints"] == 0

    def test_quote_detection_unknown_without_glyphs(self):
        r = run(FILLER + f"{P1} appears here. " + FILLER)
        (m,) = r["matches"]
        assert m["in_quotation"] == "unknown"
        # unknown is stated, never suppresses
        assert m["suppressed_by"] is None

    def test_metadiscussion_paper_fully_context_flagged(self):
        text = ('This survey of tortured phrases produced by paper mills '
                f'catalogues specimens such as {P1}, {P2} and {P3}. ' + FILLER)
        r = run(text)
        assert r["metadiscussion_context"] is True
        assert r["n_distinct_fingerprints"] == 0
        assert all(m["suppressed_by"] == "metadiscussion"
                   for m in r["matches"])
        assert r["severity"] == "consistent"
        assert any("fire brigade" not in c and "specimens" in c
                   for c in r["caveats"])

    def test_high_ambiguity_phrase_reported_not_counted(self):
        r = run(FILLER + "a choice tree analysis was performed. ")
        (m,) = r["matches"]
        assert m["suppressed_by"] == "ambiguous_fingerprint"
        assert r["n_distinct_fingerprints"] == 0

    def test_extraction_risk_alone_cannot_cross_a_threshold(self):
        # k=3 but the third fingerprint exists only via a line-break join:
        # severity holds at the k=2 tier with a named caveat.
        text = (FILLER + f"{P1} and the {P2} ratio and bosom pe-\nril here. ")
        r = run(text)
        assert r["n_distinct_fingerprints"] == 3
        assert r["n_distinct_fingerprints_solid"] == 2
        assert graded(r) == "suspicious"
        assert any("extraction_risk" in c for c in r["caveats"])


class TestAcronyms:
    def test_expansion_with_acronym_present(self):
        r = run(FILLER + "trained with profound learning (DL) methods. ")
        (m,) = r["matches"]
        assert m["family"] == "tortured_acronym"
        assert m["acronym_present"] is True
        assert r["n_distinct_fingerprints"] == 1

    def test_expansion_without_acronym_still_counts(self):
        r = run(FILLER + "trained with profound learning methods. ")
        (m,) = r["matches"]
        assert m["acronym_present"] is False
        assert r["n_distinct_fingerprints"] == 1


class TestQuarantine:
    def test_accusatory_grade_delivered_indeterminate(self):
        r = run(FILLER + f"{P1}, {P2} and {P3}. ")
        assert r["severity"] == "indeterminate"
        assert r["quarantined"] is True
        assert r["severity_before_quarantine"] == "highly_suspicious"
        assert "calibrate_tortured_phrases" in r["quarantine_reason"]

    def test_consistent_passes_through_untouched(self):
        r = run(FILLER * 2)
        assert r["severity"] == "consistent"
        assert "quarantined" not in r


class TestRefusals:
    def test_missing_dir_is_no_text_source(self, tmp_path):
        r = detect_tortured_phrases(paper_dir=str(tmp_path / "nope"))
        assert r["success"] is False
        assert r["refusal"] == "no_text_source"
        assert r["severity"] == "indeterminate"
        # An unread paper must not impersonate a clean one: no counting keys.
        assert "n_matches" not in r
        assert "n_distinct_fingerprints" not in r

    def test_empty_dir_is_no_text_source(self, tmp_path):
        r = detect_tortured_phrases(paper_dir=str(tmp_path))
        assert r["refusal"] == "no_text_source"

    def test_unreadable_candidates_is_text_unreadable(self, tmp_path):
        (tmp_path / "paper.pdf").write_bytes(b"not a real pdf")
        r = detect_tortured_phrases(paper_dir=str(tmp_path))
        assert r["refusal"] == "text_unreadable"
        assert "UNKNOWN" in r["error"]

    def test_missing_dictionary_is_installation_fact(self, tmp_path):
        r = detect_tortured_phrases(text="anything",
                                    data_dir=str(tmp_path / "nope"))
        assert r["refusal"] == "dictionary_missing"
        assert "installation" in r["explanation"]

    def test_paper_dir_mode_reads_body_md(self, tmp_path):
        (tmp_path / "body.md").write_text(
            FILLER + f"{P1} and the {P2} ratio.", encoding="utf-8")
        r = detect_tortured_phrases(paper_dir=str(tmp_path))
        assert r["success"] is True
        assert r["text_source"] == "body_md"
        assert r["n_distinct_fingerprints"] == 2


class TestResultContract:
    def test_counting_keys_distinct(self):
        r = run(FILLER + f"{P1} and {P1}. ")
        assert r["n_matches"] == 2
        assert r["n_distinct_fingerprints"] == 1
        assert r["n_matches_body"] == 2
        assert r["n_matches_references"] == 0

    def test_dictionary_identity_travels(self):
        r = run(FILLER)
        assert r["dictionary"]["version"]
        assert len(r["dictionary"]["sha256"]) == 64

    def test_match_record_fields(self):
        r = run(FILLER + f"see the {P2} ratio. ")
        (m,) = r["matches"]
        assert m["fingerprint"] == P2
        assert m["expected"] == "signal to noise"
        assert P2 in m["context"]
        assert m["section"] == "body"
        assert m["extraction_risk"] is False
