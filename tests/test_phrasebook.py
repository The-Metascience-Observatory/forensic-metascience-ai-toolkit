"""Loader, tokenizer and scanner tests for the tortured-phrases engine.

The dictionary snapshot pin at the bottom is deliberate friction: any edit to
the data files fails here until the pin is updated in the same change, with
the diff visible in review (the registry-snapshot discipline applied to data).
"""

from __future__ import annotations

import pytest

from forensic_metascience_ai_toolkit.phrasebook import (
    DATA_DIR,
    PhrasebookError,
    context_snippet,
    load_phrasebook,
    scan_text,
    tokenize,
)


@pytest.fixture(scope="module")
def book():
    return load_phrasebook()


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class TestTokenizer:
    def test_case_and_offsets_index_the_original(self):
        text = "The Flag to Clamor ratio"
        toks = tokenize(text)
        assert [t.text for t in toks] == ["the", "flag", "to", "clamor",
                                          "ratio"]
        for t in toks:
            assert text[t.start:t.end].lower() == t.text

    def test_hyphen_space_newline_equivalence(self):
        variants = ["signal-to-noise", "signal to noise", "signal\nto noise",
                    "signal- to-noise"]
        assert all([t.text for t in tokenize(v)][:3] == ["signal", "to",
                                                         "noise"]
                   for v in variants)

    def test_curly_apostrophe_normalized_inside_token(self):
        toks = tokenize("don’t stop")
        assert toks[0].text == "don't"

    def test_nfkc_ligature(self):
        toks = tokenize("artiﬁcial intelligence")  # fi ligature
        assert toks[0].text == "artificial"
        # offsets still index the original (ligature = 1 char)
        assert toks[0].end - toks[0].start == len("artiﬁcial")

    def test_linebreak_hyphen_marked(self):
        toks = tokenize("the cla-\nmor of")
        assert [t.text for t in toks] == ["the", "cla", "mor", "of"]
        assert toks[1].line_hyphen_next is True
        assert toks[0].line_hyphen_next is False

    def test_intraline_hyphen_not_marked(self):
        toks = tokenize("signal-to-noise")
        assert not any(t.line_hyphen_next for t in toks)

    def test_raw_preserves_case(self):
        toks = tokenize("Regenerate response")
        assert toks[0].raw == "Regenerate"
        assert toks[0].text == "regenerate"


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class TestScanner:
    def test_exact_hit_with_offsets(self, book):
        text = "We used counterfeit consciousness for detection."
        (m,) = scan_text(text, book)
        assert m.fingerprint.tortured == "counterfeit consciousness"
        assert m.fingerprint.expected == "artificial intelligence"
        assert text[m.start:m.end] == "counterfeit consciousness"
        assert m.variant is None

    def test_expected_phrases_do_not_match(self, book):
        text = ("Artificial intelligence and the signal to noise ratio were "
                "computed with a random forest and deep learning.")
        assert scan_text(text, book) == []

    def test_soft_hyphen_linebreak_reading(self, book):
        text = "the flag to cla-\nmor ratio"
        (m,) = scan_text(text, book)
        assert m.fingerprint.tortured == "flag to clamor"
        assert m.variant == "line_hyphenation"
        assert "cla-\nmor" in m.matched_text

    def test_hard_hyphen_linebreak_reading(self, book):
        # a hyphenated compound split at a line break still matches the
        # space-separated fingerprint (hyphens are separators)
        text = "the flag-\nto-clamor ratio"
        (m,) = scan_text(text, book)
        assert m.fingerprint.tortured == "flag to clamor"

    def test_first_token_split_at_linebreak(self, book):
        text = "used counter-\nfeit consciousness here"
        (m,) = scan_text(text, book)
        assert m.fingerprint.tortured == "counterfeit consciousness"
        assert m.variant == "line_hyphenation"

    def test_plural_variant_reports_canonical(self, book):
        text = "grown from irregular timberlands"
        (m,) = scan_text(text, book)
        assert m.fingerprint.tortured == "irregular timberland"
        assert m.variant == "plural"

    def test_case_insensitive_by_default(self, book):
        (m,) = scan_text("COUNTERFEIT CONSCIOUSNESS", book)
        assert m.fingerprint.tortured == "counterfeit consciousness"

    def test_cs_flag_requires_exact_case(self, book):
        assert scan_text("please regenerate response text", book) == []
        (m,) = scan_text("...Regenerate response...", book)
        assert m.fingerprint.tortured == "Regenerate response"

    def test_repeated_phrase_yields_repeated_matches(self, book):
        text = "bosom peril and bosom peril and bosom peril"
        ms = scan_text(text, book)
        assert len(ms) == 3
        assert len({m.start for m in ms}) == 3

    def test_boilerplate_hits(self, book):
        text = ("As an AI language model, I cannot fulfill this request. "
                "As of my last knowledge update, nothing.")
        names = {m.fingerprint.tortured for m in scan_text(text, book)}
        assert "as an AI language model" in names
        assert "I cannot fulfill this request" in names
        assert "as of my last knowledge update" in names

    def test_context_snippet_collapses_whitespace(self):
        text = "aaa\n\n  bbb ccc   ddd"
        snip = context_snippet(text, text.index("ccc"), text.index("ccc") + 3,
                               width=8)
        assert "\n" not in snip
        assert "ccc" in snip


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class TestLoader:
    def test_missing_dir_is_an_installation_error(self, tmp_path):
        with pytest.raises(PhrasebookError, match="installation"):
            load_phrasebook(tmp_path / "nope")

    def test_empty_dictionary_refuses(self, tmp_path):
        (tmp_path / "manifest.json").write_text('{"version": "0"}')
        with pytest.raises(PhrasebookError, match="refuse"):
            load_phrasebook(tmp_path)

    def test_single_token_without_allow1_rejected(self, tmp_path):
        (tmp_path / "manifest.json").write_text('{"version": "0"}')
        (tmp_path / "fingerprints.tsv").write_text(
            "tortured\texpected\tfamily\n"
            "heartiness\trobustness\ttortured_phrase\n")
        with pytest.raises(PhrasebookError, match="allow1"):
            load_phrasebook(tmp_path)

    def test_blocklist_removes_and_counts(self, tmp_path):
        (tmp_path / "manifest.json").write_text('{"version": "0"}')
        (tmp_path / "fingerprints.tsv").write_text(
            "tortured\texpected\tfamily\n"
            "bosom peril\tbreast cancer\ttortured_phrase\n"
            "flag to clamor\tsignal to noise\ttortured_phrase\n")
        (tmp_path / "blocklist.tsv").write_text(
            "tortured\tfamily\treason\tdate\n"
            "bosom peril\ttortured_phrase\ttest\t2026-08-17\n")
        book = load_phrasebook(tmp_path)
        assert book.n_blocked == 1
        assert book.n_fingerprints == 1
        assert scan_text("a bosom peril here", book) == []

    def test_dictionary_block_carries_version_and_sha(self, book):
        block = book.dictionary_block()
        assert block["version"] == "2026.08"
        assert len(block["sha256"]) == 64
        assert block["n_fingerprints"] == book.n_fingerprints

    def test_ambiguity_field_loaded(self, book):
        by_name = {fp.tortured: fp for fp in book.fingerprints}
        assert by_name["choice tree"].ambiguity == "high"
        assert by_name["bosom peril"].ambiguity == "low"

    def test_boilerplate_subclasses_loaded(self, book):
        by_name = {fp.tortured: fp for fp in book.fingerprints}
        assert (by_name["as an AI language model"].subclass
                == "first_person_disclaimer")
        assert by_name["Regenerate response"].subclass == "chat_artifact"
        assert "cs" in by_name["Regenerate response"].flags

    def test_acronym_column_loaded(self, book):
        by_name = {fp.tortured: fp for fp in book.fingerprints
                   if fp.family == "tortured_acronym"}
        assert by_name["profound learning"].acronym == "DL"


# ---------------------------------------------------------------------------
# Dictionary snapshot pin -- update DELIBERATELY, in the same change as the
# data edit, and say why in the commit. A changed dictionary changes what a
# run can find (MINOR bump).
# ---------------------------------------------------------------------------

EXPECTED_SHA256 = (
    "28e3daaf1914e5177ac1a5061192de604a9d028e527f51d3aeb4587b916fbd86")
EXPECTED_PER_FAMILY = {"tortured_phrase": 31, "llm_boilerplate": 14,
                       "tortured_acronym": 6}


class TestDictionarySnapshot:
    def test_per_family_counts_pinned(self, book):
        assert book.per_family == EXPECTED_PER_FAMILY, (
            "dictionary contents changed -- update the pin AND bump MINOR "
            "(CHANGELOG.md): two runs across a dictionary change are not "
            "comparable")

    def test_sha_pinned(self, book):
        assert book.sha256 == EXPECTED_SHA256, (
            "dictionary bytes changed -- update the pin AND bump MINOR "
            "(CHANGELOG.md)")

    def test_bundled_data_dir_ships(self):
        assert DATA_DIR.is_dir()
        assert (DATA_DIR / "ATTRIBUTION.md").is_file()
        assert (DATA_DIR / "manifest.json").is_file()
