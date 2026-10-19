"""The floor's completeness claim does not hold on every paper, and now says so.

`numerals.tally` tells a reader that `n_total` "is the one count here that
cannot be silently incomplete", and `register_view` prints that sentence. The
promise rests on the reference cut removing only references.

MEASURED over the 12-paper corpus: SIX papers strand real body prose on the
references side, 27 lines in all. Every two-column PNAS paper does it, because
the converter interleaves the bibliography with the running text -- on
`pnas.0801268105` the discarded tail holds `mean age, 25.6 years of age; SD,
3.3` and the whole `Materials. Training task.` section, sitting after a
`Psychol Rev 51:77-101.` entry with a column separator between them.

The cut is not wrong about where the references START. The document is not in
reading order.
"""

from __future__ import annotations

import pathlib

import pytest

from forensic_metascience_ai_toolkit import completeness, references

CORPUS = pathlib.Path(__file__).resolve().parents[1] / "tests/fixtures/papers/high_value_pdfs_to_run_on"
INTERLEAVED = CORPUS / "10.1073--pnas.0801268105"

pytestmark = pytest.mark.skipif(not CORPUS.is_dir(), reason="corpus not present")


class TestItDetectsStrandedBodyProse:
    def test_the_interleaving_is_a_pdf_converter_artifact(self):
        """It is the CONVERTER that puts the document out of reading order, not
        the paper. Reading the same paper's publisher markup instead cures it.

        MEASURED 2026-09-06 on `pnas.0801268105`, before and after a PMC full
        text was installed beside the PDF:

            docling PDF text   31,727 chars   stranded_lines 8
            PMC HTML           27,461 chars   stranded_lines 0

        and `mean age, 25.6 years of age; SD, 3.3` -- the statistic the old
        assertion named as lost -- survives in the body on both. The Methods
        section survives too: the PDF runs its headings together as
        `Materials. Training task.` while the HTML carries them as real
        headings, which is a structural gain rather than a loss.

        So this class now asserts the CURE where a source exists, and the
        DETECTOR stays covered by the synthetic cases below -- a detector whose
        only test was one corpus paper would silently stop being tested the day
        that paper was upgraded, which is exactly what happened here."""
        if not INTERLEAVED.is_dir():
            pytest.skip("reference paper not present")
        text, source = completeness._read_body(INTERLEAVED), None
        from forensic_metascience_ai_toolkit.extraction.jats import _derive_paper_text
        _, source = _derive_paper_text(INTERLEAVED)
        out = references.stranded_prose(text[0])
        if source == "pdf":
            assert out["n_lines"] >= 5, "the converter artifact should be visible"
            assert out["how"] == "numbered_run"
        else:
            assert out["n_lines"] == 0, (
                f"source={source}: publisher markup is in reading order, so "
                "nothing should be stranded")

    def test_the_statistic_survives_the_upgrade(self):
        """A count is arguable; a printed statistic is not. Whichever source is
        served, the paper's `mean age, 25.6 years of age` must be in the body --
        on the PDF path it is in the STRANDED tail, on the markup path it is in
        the body proper, and either way it must not vanish."""
        if not INTERLEAVED.is_dir():
            pytest.skip("reference paper not present")
        text, _ = completeness._read_body(INTERLEAVED)
        assert "25.6" in text

    def test_the_detector_still_fires_on_an_interleaved_document(self):
        """The synthetic case, so the DETECTOR keeps its own test.

        Built to the real shape rather than tuned until green: body prose sits
        between numbered reference entries AFTER the heading, which is what the
        two-column converter produces. `split` needs the heading past
        `_EARLIEST` (40% of the document), so the body has to be substantial --
        a first draft failed for having too little body, not because the
        detector was broken, and shortening the fixture until it passed would
        have tested nothing."""
        body = ("We tested whether working memory training transfers to fluid "
                "intelligence. Participants completed a battery of tests before "
                "and after training. ") * 22
        refs = [f"{i}. Author{i} AB, Other{i} CD ({1990 + i}) A study of something "
                f"in the field. Journal of Things {40 + i}:{100 + i}-{120 + i}."
                for i in range(1, 10)]
        stranded = [
            "Participants. Twenty-eight volunteers took part in the experiment "
            "(mean age, 25.6 years of age; SD, 3.3).",
            "Materials. Training task. For the training task we used the same "
            "material described previously, a dual n-back task.",
            "Procedure. Participants trained daily except for the weekends, over "
            "a period of nineteen consecutive days.",
        ]
        lines, k = [body, "", "References"], 0
        for i, r in enumerate(refs):
            lines.append(r)
            if i in (2, 4, 6):
                lines.append(stranded[k])
                k += 1
        out = references.stranded_prose("\n".join(lines))
        assert out["n_lines"] == 3, out
        assert out["how"] == "heading"
        assert "25.6" in " ".join(out["lines"])
        assert not any("Journal of Things" in l for l in out["lines"]), (
            "a reference entry must never be counted as stranded prose")

    def test_a_clean_paper_strands_nothing(self):
        """High precision matters more than recall here: this number qualifies
        a completeness claim, and an inflated one makes the qualification
        meaningless."""
        clean = CORPUS / "10.1001--jamanetworkopen.2023.37679"
        if not clean.is_dir():
            pytest.skip("paper not present")
        text, _ = completeness._read_body(clean)
        assert references.stranded_prose(text)["n_lines"] == 0

    def test_a_reference_entry_is_never_counted_as_prose(self):
        entries = "\n".join([
            "1. Carpenter PA, Just MA, Shell P (1990) What one intelligence "
            "test measures: A theoretical account. Psychol Rev 97:404-431.",
            "[12] Smith, J. A. (2011) Some long title that runs on for a while "
            "in a journal. Journal of Things 14:11-29.",
            "Neisser U, Boodoo G (1996) Intelligence: Knowns and unknowns. "
            "Am Psychol 51:77-101.",
        ])
        out = references.stranded_prose("body\n\nReferences\n" + entries)
        assert out["n_lines"] == 0, out["lines"]

    def test_no_boundary_means_nothing_stranded(self):
        assert references.stranded_prose("a paper with no reference list at "
                                         "all, just prose.")["n_lines"] == 0
        assert references.stranded_prose("")["n_lines"] == 0


class TestTheRegisterSaysSoWhereTheClaimIsMade:
    def test_the_register_records_the_incompleteness(self):
        from forensic_metascience_ai_toolkit import values
        if not INTERLEAVED.is_dir():
            pytest.skip("reference paper not present")
        from forensic_metascience_ai_toolkit.extraction.jats import _derive_paper_text
        _, source = _derive_paper_text(INTERLEAVED)
        reg = values.build_from_paper(INTERLEAVED)
        n = reg.get("numerals_incomplete", {}).get("n_lines", 0)
        if source == "pdf":
            assert n >= 5
        else:
            # Publisher markup is in reading order, so the register should make
            # NO incompleteness claim -- and must not carry a stale one.
            assert n == 0, f"source={source} but the register still claims {n} stranded lines"

    def test_it_also_lands_in_problems_where_a_reader_looks(self):
        from forensic_metascience_ai_toolkit import values
        from forensic_metascience_ai_toolkit.extraction.jats import _derive_paper_text
        if not INTERLEAVED.is_dir():
            pytest.skip("reference paper not present")
        if _derive_paper_text(INTERLEAVED)[1] != "pdf":
            pytest.skip("this paper now reads from publisher markup, which is in "
                        "reading order, so there is no incompleteness to report")
        reg = values.build_from_paper(INTERLEAVED)
        assert any("numeral floor is INCOMPLETE" in p
                   for p in (reg.get("problems") or []))

    def test_a_clean_paper_records_nothing(self):
        """Absence of the key must mean "the claim holds", so it cannot be
        written unconditionally."""
        from forensic_metascience_ai_toolkit import values
        clean = CORPUS / "10.1001--jamanetworkopen.2023.37679"
        if not clean.is_dir():
            pytest.skip("paper not present")
        assert "numerals_incomplete" not in values.build_from_paper(clean)
