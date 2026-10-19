"""Corrupt extracted text must be detected before a finding is believed.

MEASURED across 400 papers: these are broken `ToUnicode` CMaps in the source
PDFs, not typos in the papers, and no text-layer extractor repairs them --
pdfplumber emits `(cid:237)` on exactly the glyphs docling renders as
`GLYPH<237>`.

The worst case: one paper's font maps `-` to `2` and `=` to `5`, so a printed
`-5.50 (-10.1, -0.85); P = 0.003` reaches the model as `2 5.50 ( 2 10.1,
2 0.85); P 5 0.003`. The sign is gone and a digit invented. That is the most
dangerous shape a failure can take here: a wrong number that looks entirely
plausible, on which every downstream check computes confidently.
"""
import pytest

from metascience_agent import glyphs as G
from metascience_agent.glyphs import scan, scan_paper


class TestDetection:
    def test_clean_text_is_clean(self):
        r = scan("The mean was 5.51 (SD 1.20), n = 30, p < .05. " * 5)
        assert r["clean"] and not r["quarantine"]

    def test_unmapped_glyphs(self):
        assert "unmapped glyph" in [h["pattern"] for h in
                                    scan("GLYPH<6> GLYPH<14> GLYPH<237>")["patterns"]]

    def test_equals_as_five_is_quarantine_grade(self):
        r = scan("F (3,252) 5 15, P < 0.001. t (10) 5 1.84, p 5 .09. p 5 .05")
        assert r["quarantine"]

    def test_minus_as_two(self):
        r = scan("2 8.19 ( 2 11.5, 2 4.88) and 2 5.50 ( 2 10.1, 2 0.85) "
                 "and 2 3.40 ( 2 9.1, 2 1.22)")
        assert r["quarantine"]

    def test_plus_minus_as_six(self):
        r = scan("30.7 ( 6 4.0) and 12.1 ( 6 2.2) and 44.9 ( 6 8.1)")
        assert r["quarantine"]


class TestPrecisionOverCoverage:
    """A quarantine signal that fires on half the corpus tells nobody anything.

    Each of these was a real false positive during development.
    """

    def test_ordinary_n_percent_cells_are_not_flagged(self):
        """`157 (60.2)` is an n (%) cell, not a plus-minus corruption."""
        r = scan("| 157 (60.2) | 57 (66.3) | 249 (61.9) | 341 (60.0) |")
        assert not r["quarantine"]

    def test_thousands_separators_are_not_corruption(self):
        """`231 099` is correct typography, not a split number."""
        assert scan("231 099 respondents and 236 551 727 adults")["clean"]

    def test_reference_markers_are_not_flagged(self):
        """`1991. 19 We enrolled` is a superscript citation, not a split decimal."""
        assert not scan("August 31, 1991. 19 We enrolled pregnant women.")["quarantine"]

    def test_a_doi_is_not_flagged(self):
        assert not scan("10.1186/s13293-020-00299-3 . 49 Al-Qaraghouli M")["quarantine"]

    def test_a_lone_occurrence_is_below_the_noise_floor(self):
        assert scan("one stray GLYPH<6> here")["clean"]


class TestReporting:
    def test_digit_corruption_says_why_it_matters(self):
        note = scan("p 5 .05 and t 5 1.2 and F 5 3.4 and p 5 .01")["note"]
        assert "DIGITS" in note
        assert "never printed" in note

    def test_non_digit_corruption_is_reported_but_not_quarantined(self):
        r = scan("n ¼ 68, n ¼ 42, n ¼ 19 were analysed")
        assert not r["clean"]
        assert not r["quarantine"]
        assert "not in the digits" in r["note"]

    def test_examples_are_included(self):
        h = scan("p 5 .05 and t 5 1.2 and F 5 3.4")["patterns"][0]
        assert h["examples"] and h["count"] >= 3

    def test_missing_directory_does_not_raise(self, tmp_path):
        """It must not raise -- and it must not call the paper clean.

        This used to assert `clean` was True, which is what the function did
        return for a directory that does not exist: `paper_text` gives "",
        `scan` finds no corrupt glyphs in the empty string, and the answer came
        back "No character-level corruption detected in the extracted text."
        The test's subject is that it does not RAISE; the `clean` it happened
        to assert along the way was the defect, pinned in place. MEASURED on a
        real corpus PDF whose every extraction path crashes with "Unexpected
        EOF", the same path reported that paper clean too.
        """
        r = scan_paper(tmp_path / "nope")
        assert r["clean"] is False
        assert r["text_available"] is False
        assert "UNKNOWN" in r["note"]


class TestTheProseFormOfTheLostMinusSign:
    """FOUND BY A PAID RUN, 2026-08-13, and by opening the text it read.

    `minus as digit 2` was written from one paper whose corruption read
    `2 5.50 ( 2 10.1, 2 0.85)`, so it requires the bracketed interval. Kross
    2013 (PLOS ONE) reports inline -- `B = 2 .006, b = 2 .059, t (73) = 1.04`
    -- and has TEN such statistics and ZERO true minus signs. The scan returned
    "the numbers themselves appear intact" and a $7.68 review then made
    forensic claims from that text.

    The two patterns are complementary, and this class pins BOTH directions so
    neither can later be "simplified" into the other.
    """

    KROSS = ("''direct'' social interaction did not predict changes in cognitive "
             "well-being, B = 2 .006, b = 2 .059, t (73) = 1.04, p =.30, and "
             "predicted increases in affective well-being, B = 2 .15. Satisfaction "
             "declined over time, B = 2 .012, b = 2 .124, t (73) = 2 2.39.")

    ORIGINAL = ("a printed -5.50 (-10.1, -0.85); P = 0.003 reaches us as "
                "2 5.50 ( 2 10.1, 2 0.85); P 5 0.003, and again as "
                "2 3.10 ( 2 9.2, 2 0.40), and once more as 2 1.20 ( 2 4.4, 2 0.10)")

    def test_the_inline_form_is_caught_and_quarantined(self):
        from metascience_agent.glyphs import scan
        r = scan(self.KROSS)
        hit = [h for h in r["patterns"] if h["pattern"] == "operator lost before a decimal"]
        assert hit, [h["pattern"] for h in r["patterns"]]
        assert r["quarantine"] is True, "a lost sign corrupts DIGITS"

    def test_the_bracketed_form_is_still_caught(self):
        """The pattern this one was added beside must keep working; a
        replacement dressed as an addition is the failure that produced it."""
        from metascience_agent.glyphs import scan
        r = scan(self.ORIGINAL)
        assert any(h["pattern"] == "minus as digit 2" for h in r["patterns"])

    def test_neither_pattern_catches_the_other_s_case(self):
        """Recorded because it is the REASON both exist. If one day one of them
        does catch both, that is a discovery, not a licence to delete the
        other without re-measuring."""
        import re

        from metascience_agent.glyphs import _PATTERNS
        pat = {label: rx for label, rx, _, _ in _PATTERNS}
        assert not pat["minus as digit 2"].search(self.KROSS)
        assert not pat["operator lost before a decimal"].search(self.ORIGINAL)
        assert isinstance(pat["operator lost before a decimal"], re.Pattern)

    def test_an_ordinary_paper_is_not_flagged(self):
        """The anchor on `=` is what keeps a flattened table row out. Two
        adjacent cells rendered on one line look identical to the corruption
        without it."""
        from metascience_agent.glyphs import scan
        clean = ("Mean age was 42.1 (SD 8.3) and the model gave B = -0.006, "
                 "beta = -0.059, t(73) = -1.04, p = .30. "
                 "| Age | 2 | .006 | 41 | .07 | 2 | .12 |\n" * 4)
        r = scan(clean)
        assert not any(h["corrupts_digits"] for h in r["patterns"]), r["patterns"]

    def test_the_real_paper_now_quarantines(self):
        """The measurement itself, against the file on disk."""
        import pathlib

        from metascience_agent.glyphs import scan
        from metascience_agent.extraction.docling_tables import cached_text
        pdf = (pathlib.Path(__file__).resolve().parents[1]
               / "tests/fixtures/papers/high_value_pdfs_to_run_on/10.1371--journal.pone.0069841"
               / "10.1371--journal.pone.0069841.pdf")
        if not pdf.is_file():
            pytest.skip("paper not in this checkout")
        text, _ = cached_text(pdf)
        if not text:
            pytest.skip("not extracted in this checkout")
        r = scan(text)
        assert r["quarantine"] is True
        hit = next(h for h in r["patterns"] if h["pattern"] == "operator lost before a decimal")
        assert hit["count"] >= 9


class TestAControlCharacterIsAGlyphIndexNotAnEncoding:
    """MEASURED across both corpora, `\\x06` is TWO characters: `±` in EPIVI7B3,
    YR8VZZRJ and YLHWMEJ3 (255 occurrences, not one literal `±` between them)
    and a DECIMAL POINT in 10.1166--jnn.2011.5114, which prints 471 literal `±`.
    One byte, two meanings, decided by a font we do not have."""

    def test_it_is_detected_and_quarantines(self):
        r = G.scan("significantly, P < 0\x0605; P < 0\x0601, and 1\x062, 3\x064")
        assert r["quarantine"] is True
        assert any(p["pattern"] == "control character in a number"
                   for p in r["patterns"])

    def test_clean_text_is_not_flagged(self):
        r = G.scan("p < 0.05 and 6.0 ± 2.2 MBq, n = 68, 95% CI 1.08-1.9")
        assert not any(p["pattern"] == "control character in a number"
                       for p in r["patterns"])

    def test_a_textual_anchor_proves_the_repair(self):
        """`mean \\x06 SD` puts the glyph between two WORDS, where no digit is at
        stake and only `±` reads."""
        assert G.proven_repairs("Age, mean \x06 SD years; 6.0 \x06 2.2") == {"\x06": "±"}

    def test_a_paper_that_prints_the_character_is_not_also_encoding_it(self):
        """The condition that rules out the counterexample. jnn.2011.5114 has
        471 literal `±`, so its `\\x06` is something else -- a decimal point."""
        assert G.proven_repairs("mean \x06 SD and elsewhere 1.89±0.21") == {}

    def test_probably_is_not_proven(self):
        """YLHWMEJ3 has 50 occurrences that are very likely `±` and no anchor.
        It gets no repair: being nearly sure is still a guess about a digit."""
        assert G.proven_repairs("afrotherians, 0.740 \x06 0.033, p = 0.004") == {}

    def test_the_repair_is_length_preserving(self):
        t = "Age, mean \x06 SD; 6.0 \x06 2.2"
        assert len(G.apply_proven_repairs(t)) == len(t)


class TestATruncatedNumberIsRefusedNotReported:
    def test_a_glyph_split_p_value_is_not_reported_as_p_less_than_zero(self):
        """THE DEFECT THIS PAIR EXISTS FOR. `P < 0\\x0605` is a printed
        `P < 0.05`; the pattern matched to the control character and stopped, so
        the pipeline received a reported p of ZERO. That is impossible, and a
        check comparing reported against computed p can turn it into an
        accusation against an honest paper."""
        from metascience_agent import completeness as C
        items = C._body_items("control group, P < 0\x0605; P < 0\x0601, signif")
        assert not [i for i in items if i["raw"].strip() in ("P < 0", "P<0")]

    def test_the_same_sentence_undamaged_still_reports_both(self):
        from metascience_agent import completeness as C
        items = C._body_items("control group, P < 0.05; P < 0.01, signif")
        assert [i["raw"] for i in items if i["kind"] == "p_value"] == \
            ["P < 0.05", "P < 0.01"]

    def test_a_proven_document_still_yields_its_mean_sd_pairs(self):
        """EPIVI7B3 yields 182 `mean_pm_prose` items once its own text proves
        the glyph. Refusing those would be the opposite error."""
        from metascience_agent import completeness as C
        items = C._body_items(
            "Age, mean \x06 SD years. Weight was 65.2 \x06 1.17 kg overall.")
        assert any(i["kind"] == "mean_pm_prose" for i in items)


class TestTheSignPositionIsTheDangerousHalf:
    """A control character need not sit INSIDE a number to ruin it. In
    `7AP7MG3N`, `\\x00` is a minus (`between +0.345 and \\x00 0.145`, in a paper
    carrying 1052 literal `-` and no unicode `−`) and `\\x18` is `~`
    (`\\x18 70 million neurons`). In `EPIVI7B3` a table row reads
    `\\x00 3.5 \\x06 7.6` for `−3.5 ± 7.6` -- both glyphs at once.

    This file's header calls a lost minus sign "the most dangerous failure this
    pipeline can have: a wrong number that looks entirely plausible, on which
    every downstream check will compute confidently.\""""

    def test_a_glyph_in_sign_position_is_detected(self):
        r = G.scan("coordinates between +0.345 and \x00 0.145, and \x00 4.78, "
                   "and again \x00 1.20 here")
        assert any(p["pattern"] == "control character in a number"
                   for p in r["patterns"])

    def test_a_lost_minus_is_not_reported_as_a_positive_mean(self):
        """MEASURED: 21 `mean_pm_prose` items in EPIVI7B3 sit behind a lost
        minus. Read without this guard, every one arrives with the wrong sign."""
        from metascience_agent import completeness as C
        items = C._body_items("Values are mean \x06 SD. Change was "
                              "\x00 3.5 \x06 7.6 overall.")
        assert not [i for i in items if i["raw"].startswith("3.5")]

    def test_an_approximate_value_is_not_reported_as_exact(self):
        """`\\x18 69%` is `~69%`. The difference between an approximate value
        and an exact one is the difference between a number GRIM may test and
        one it may not."""
        from metascience_agent import completeness as C
        assert C._body_items("brain activation, with \x18 69% of ROIs") == []

    def test_an_ordinary_negative_number_is_untouched(self):
        from metascience_agent import completeness as C
        got = [i["kind"] for i in
               C._body_items("the effect was -0.145 (95% CI -0.3, 0.1)")]
        assert "estimate_ci_prose" in got


class TestTheSameCharacterLeaksTwoWays:
    """One PDF, one character, two corruptions. MEASURED on
    `10.1007--s00702-004-0248-2`: pdf2mdjson's `body.md` reads `65 /C6 1.17`
    (the PostScript glyph NAME) while docling's cells read `65 \\x06 1.17` (the
    raw glyph INDEX). Across the 309-paper corpus `/Cn` sits between two numbers
    233 times in 12 papers.

    Repairing the anchored ones recovers 138 `mean_pm_prose` items and moves no
    other kind at all."""

    def test_a_named_anchor_proves_the_named_glyph(self):
        assert G.proven_repairs("Values are Mean /C6 SD of six animals.") \
            == {"/C6": "±  "}

    def test_the_named_repair_is_length_preserving(self):
        """`/C6` is three characters and `±` is one. `completeness._body_items`
        matches on the repaired string while slicing `raw` from the source at
        the SAME offsets, so a shortened string would move every offset after
        the first repair."""
        t = "Values shown mean /C6 SEM. Age was 65 /C6 1.17 years."
        assert len(G.apply_proven_repairs(t)) == len(t)

    def test_a_paper_printing_the_character_gets_no_repair(self):
        assert G.proven_repairs("Mean /C6 SD, and elsewhere 1.89±0.21") == {}

    def test_no_anchor_no_repair(self):
        """8 of the 12 corpus papers with `/Cn` between numbers have no anchor,
        including 10.1007--s00702-004-0248-2. They keep their damage."""
        assert G.proven_repairs("Age was 65 /C6 1.17 years.") == {}

    def test_a_glyph_name_inside_a_number_quarantines(self):
        """The bare `/Cn` pattern is reported and does not quarantine, which is
        right for a glyph name in prose. Between two digits it is a lost `±`, so
        a dispersion reads as a separate value."""
        r = G.scan("Age 65 /C6 1.17, weight 70 /C6 2.4, dose 5 /C6 0.5")
        assert r["quarantine"] is True
        assert any(p["pattern"] == "glyph name inside a number"
                   for p in r["patterns"])

    def test_a_glyph_name_in_prose_alone_does_not_quarantine(self):
        r = G.scan("the /C6 marker appears in the caption, and /C6 again here")
        assert not any(p["pattern"] == "glyph name inside a number"
                       for p in r["patterns"])

    def test_the_recovered_pair_is_read_as_a_dispersion(self):
        from metascience_agent import completeness as C
        t = "Values are Mean /C6 SD. Age was 65 /C6 1.17 years."
        kinds = [i["kind"] for i in C._body_items(t)]
        assert "mean_pm_prose" in kinds

    def test_raw_is_still_the_source_spelling(self):
        """A reader checking our work has to see what we actually read."""
        from metascience_agent import completeness as C
        t = "Values are Mean /C6 SD. Age was 65 /C6 1.17 years."
        got = [i["raw"] for i in C._body_items(t) if i["kind"] == "mean_pm_prose"]
        assert got == ["65 /C6 1.17"]


class TestAGlyphNameInSignPositionLosesTheSign:
    """`/C0` is a MINUS. MEASURED over the 309-paper corpus, it appears 112
    times: `stored at /C0 70 /C14 C` is -70 degrees, `r = /C0 0.74` is a
    correlation of MINUS 0.74, and `Apoe /C0 = /C0 mice` is `Apoe -/- mice`.

    Unlike `±`, no textual anchor proves it, so nothing is repaired -- the
    numbers are refused and the paper quarantines."""

    def _items(self, s):
        from metascience_agent import completeness as C
        return [(i["kind"], i["raw"]) for i in C._body_items(s)]

    def test_a_sign_flipped_effect_size_is_refused(self):
        """The worst case found: a printed -0.85 with CI [-1.2, -0.3] was
        emitted as `estimate_ci_prose` 0.85 -- POSITIVE, with a confidence
        interval attached, which is exactly what a forensic check computes on."""
        assert self._items(
            "the effect was /C0 0.85 (95% CI /C0 1.2, /C0 0.3)") == []

    def test_a_sign_flipped_percentage_is_refused(self):
        assert self._items("burden was reduced by /C0 43% in the young group") == []

    def test_the_same_sentence_undamaged_is_unaffected(self):
        got = self._items("the effect was -0.85 (95% CI -1.2, -0.3)")
        assert [k for k, _ in got] == ["estimate_ci_prose"]

    def test_a_footnote_asterisk_does_not_condemn_the_p_value(self):
        """THE OVER-REFUSAL THIS PINS. `10.1007--s00702-003-0025-7` prints a
        legend reading `/C3 ¼ p < 0.05` -- that is `* = p < 0.05`, where `/C3`
        is the ASTERISK and the p-value is perfectly intact. A first cut
        searched seven characters back, reached past the `=`, and threw away
        four undamaged p-values. The glyph must END where the number begins."""
        got = self._items("/C3 ¼ p &lt; 0.05 by one-way ANOVA with Tukey")
        assert ("p_value", "p &lt; 0.05") in got

    def test_it_quarantines(self):
        r = G.scan("a /C0 43% and b /C0 1.2 and c /C0 0.3 here")
        assert r["quarantine"] is True


class TestOcrTrustIsTheOtherDirection:
    """Everything else in `glyphs` detects a corrupt TEXT LAYER. This detects a
    corrupt PIXEL reading, and it belongs in the same module because a caller
    asks one question: may I compute on this?

    MEASURED on the 22 papers whose numbers the text layer corrupts: full-page
    OCR cleared all 988 glyph artefacts and recovered 14% more statistics, and
    in 6 of the 22 it invented CJK characters INSIDE numeric table cells. A
    printed `1.9 ± 0.1` came back as `1'0<CJK>61`. The gate accepts 16 and
    refuses 6."""

    GARBLED = "| 2.0±0 | 10干61 | 1’0干61 | (6 t 1) 11) |"

    def test_invented_characters_are_refused(self):
        r = G.ocr_trust(self.GARBLED)
        assert r["usable"] is False
        assert {m["marker"] for m in r["markers"]} >= {"CJK in a latin document"}

    def test_a_clean_reading_is_accepted(self):
        assert G.ocr_trust("| 2.0±0 | 1.9±0.1 | 11 (1 of 9) |")["usable"]

    def test_a_document_that_really_contains_cjk_is_not_accused(self):
        """The text layer is how we know the difference. A paper with Chinese in
        it is not evidence that the recogniser invented Chinese, and accusing it
        would be this repository's own failure mode pointed at itself."""
        assert G.ocr_trust("研究 shows 2.0±0",
                           compare_with="研究 shows 2.0 /C6 0")["usable"]

    def test_without_a_comparison_the_marker_is_reported_as_unverified(self):
        """Absence of a comparison is not absence of a problem."""
        r = G.ocr_trust(self.GARBLED)
        assert r["markers"][0]["verified_against_text_layer"] is False

    def test_a_clean_reading_is_not_called_accurate(self):
        """It is the absence of the failures we can detect, which is a weaker
        claim and the only one available."""
        note = G.ocr_trust("plain text, 2.0 ± 0.1")["note"]
        assert "not a guarantee" in note

    def test_the_refusal_says_to_fall_back_to_the_corrupt_reading(self):
        """Corrupt text ANNOUNCES itself; invented text does not. Between the
        two, the one that can be detected downstream is the safer input."""
        assert "ANNOUNCES" in G.ocr_trust(self.GARBLED)["note"]
