"""The document layer's defects found by preparing six representative papers.

Nothing here calls a model. Every fixture is cut verbatim from one of the six
papers named beside it, so a line that reads oddly is the publisher's, not an
invention: `[Figure 1.: ...]` is what `jats._fig_block` writes, and it is the
form that made four figure-bearing papers report no figures at all.
"""

from __future__ import annotations

import pytest

from forensic_metascience_ai_toolkit.scaffold import document as D


# --------------------------------------------------------------------------
# 1. Figure captions on the XML rung
# --------------------------------------------------------------------------

#: One line per paper, copied from its `body.repaired.md`. `_fig_block` writes
#: `[{label}: {caption}]` and the label is the publisher's own `<label>`, so
#: every JATS flavour arrives bracketed and none of them starts a line with a
#: bare `Figure N`.
CAMBRIDGE = "[Figure 1.: Flowchart of the identification of articles.]"
FRONTIERS = ("[FIGURE 1: Novel object recognition and body weight. (Ai) Representative "
             "traces. (B) Body weight over the eight weeks.]")
NATURE = "[Fig. 2: Progression-free survival of the cohort. a Kaplan-Meier curves.]"
#: Nature's Fig. 3, abridged in the middle (marked) so the line fits here; the
#: panel markers and the brackets are the paper's.
NATURE_PANELS = ("[Fig. 3: Progression-free survival based on EGFR genotype. Kaplan-Meier curves "
                 "comparing [...] patients with EGFR exon 19 deletion (ex19del) (a) and patients "
                 "with EGFR L858R (b) treated with mefatinib and gefitinib.]")
JAMA = "[Figure.: Distribution of Nurse-Family Partnership Treatment Effects.]"


class TestFigureCaptionsOnTheXMLRung:
    def test_every_jats_label_flavour_is_a_figure(self):
        text = "\n\n".join([CAMBRIDGE, FRONTIERS, NATURE])
        figs = D.figure_captions(text)
        assert [f["label"] for f in figs] == ["Figure 1", "Figure 1", "Figure 2"]
        assert [f["id"] for f in figs] == ["figure:1", "figure:1", "figure:2"]

    def test_the_caption_and_its_panels_survive_the_brackets(self):
        (fig,) = D.figure_captions(FRONTIERS)
        assert fig["caption"].startswith("FIGURE 1: Novel object recognition")
        assert not fig["caption"].endswith("]"), "the renderer's bracket is not the caption"
        # Frontiers writes its panels `(Ai)`, `(B)`; `_PANEL_MARKER` reads
        # lower-case letters only and still does -- unchanged by this fix, and
        # recorded here so the zero is a known state and not a new one.
        assert fig["panels"] == []
        (nat,) = D.figure_captions(NATURE_PANELS)
        assert nat["panels"] == ["a", "b"] and nat["n_panels"] == 2

    def test_a_single_figure_paper_labels_it_without_a_number(self):
        # JAMA prints `Figure.` when an article has exactly one. A number is
        # not invented for it: the label is what the paper printed.
        (fig,) = D.figure_captions(JAMA)
        assert fig["label"] == "Figure." and fig["id"] == "figure:Figure."
        assert fig["caption"].startswith("Figure.: Distribution")

    def test_prose_naming_a_figure_is_not_a_caption(self):
        # Cambridge's own body sentence, and the reason the unnumbered form is
        # accepted only inside the renderer's brackets.
        prose = ("As shown in Fig. 1, the titles and abstracts of 1886 articles were screened.\n"
                 "Figure: see the supplement for the full flow diagram.")
        assert D.figure_captions(prose) == []

    def test_the_docling_form_still_reads(self):
        # The PDF rung writes the caption as a plain line; it must keep working.
        (fig,) = D.figure_captions("Figure 3. Recall by dose (a) and (b).")
        assert fig["id"] == "figure:3" and fig["panels"] == ["a", "b"]


class TestTheFetchedImagesJoinTheseCaptions:
    def _manifest(self, *labels):
        return {"source": "pmc_article_page",
                "figures": [{"id": f"fig{i}", "figure_label": l, "file": f"f{i}.jpg",
                             "status": "ok", "caption": ""} for i, l in enumerate(labels, 1)]}

    def test_an_unnumbered_label_joins_its_own_image_rather_than_doubling(self):
        # `Figure.` carries no digit, so a number-keyed join left the caption
        # and its fetched image as two figures on a one-figure paper.
        figs = D.figure_captions(JAMA)
        out = D.merge_pmc_figures(figs, self._manifest("Figure."))
        assert len(out) == 1 and out[0]["image"] == "f1.jpg"

    def test_a_number_still_joins_across_label_flavours(self):
        out = D.merge_pmc_figures(D.figure_captions(NATURE), self._manifest("Figure 2"))
        assert len(out) == 1 and out[0]["image"] == "f1.jpg"


# --------------------------------------------------------------------------
# 2. The supplement prose cap
# --------------------------------------------------------------------------

class TestTheSupplementProseCapIsRecordedNotHidden:
    def _raw(self, kept: int, available: int):
        from forensic_metascience_ai_toolkit.extraction import pdf as _pdf
        return {"text": "x" * kept + _pdf.TRUNCATION_MARKER, "tables": [], "num_pages": 53,
                "truncated": True, "n_chars_available": available, "unreadable": False}

    def test_the_marker_is_not_part_of_the_supplements_prose(self, monkeypatch, tmp_path):
        from forensic_metascience_ai_toolkit.extraction import pdf as _pdf
        from forensic_metascience_ai_toolkit.extraction import supplements_read as SR
        monkeypatch.setattr(_pdf, "extract_text_with_tables",
                            lambda p, *a, **k: self._raw(50_000, 289_222))
        out = SR.extract_pdf_tables(tmp_path / "s001.pdf")
        assert _pdf.TRUNCATION_MARKER not in out["text"], (
            "the marker is an instruction to a tool caller; served as supplement prose it is "
            "a sentence the paper never printed, sitting in the numeral floor's own text")
        assert len(out["text"]) == 50_000
        assert out["text_truncated"] is True
        assert out["n_chars_available"] == 289_222 and out["n_chars_served"] == 50_000

    def test_an_untruncated_supplement_says_so_with_both_numbers(self, monkeypatch, tmp_path):
        from forensic_metascience_ai_toolkit.extraction import pdf as _pdf
        from forensic_metascience_ai_toolkit.extraction import supplements_read as SR
        monkeypatch.setattr(_pdf, "extract_text_with_tables",
                            lambda p, *a, **k: {"text": "abc", "tables": [], "num_pages": 1,
                                                "truncated": False, "n_chars_available": 3,
                                                "unreadable": False})
        out = SR.extract_pdf_tables(tmp_path / "s003.pdf")
        assert out["text_truncated"] is False
        assert out["n_chars_available"] == out["n_chars_served"] == 3


# --------------------------------------------------------------------------
# 6. Table numbering
# --------------------------------------------------------------------------

class TestATableIsNumberedByItsLabelNotItsPosition:
    def test_the_publishers_own_label_is_the_number(self):
        assert D.printed_table_number({"label": "Table 5", "table_id": "Tab5"}) == 5
        assert D.printed_table_number({"label": "TABLE 2", "table_id": None}) == 2
        assert D.printed_table_number({"label": "eTable 3"}) == 3

    def test_the_wrap_id_is_the_fallback_when_there_is_no_label(self):
        assert D.printed_table_number({"label": None, "table_id": "Tab4"}) == 4
        assert D.printed_table_number({"label": "", "table_id": "T12"}) == 12

    def test_a_table_with_no_number_anywhere_is_unnumbered(self):
        # Reported, and the caller falls back to position and says so; a number
        # is not invented from the order.
        assert D.printed_table_number({"label": "Baseline characteristics",
                                       "table_id": "sec-outcomes"}) is None
        assert D.printed_table_number({}) is None

    def test_a_supplement_label_carrying_its_file_still_yields_its_own_number(self):
        assert D.printed_table_number(
            {"label": "40337_2024_968_MOESM1_ESM.docx :: Table 2"}) == 2


# --------------------------------------------------------------------------
# 7. The reference list is structure, not body
# --------------------------------------------------------------------------

class TestTheReferenceListLeavesTheServedBody:
    BODY = "## Results\n\nThe effect was 0.42 (95% CI 0.31 to 0.53) in 180 samples."
    REFS = ("\n\n# References\n\n"
            "1. Adenzato M, Manenti R (2019) Transcranial direct current stimulation. "
            "Neuropsychologia 124, 42-51.\n"
            "2. Baron-Cohen S (2001) The Reading the Mind in the Eyes test. "
            "J Child Psychol Psychiatry 42(2), 241-251.\n")

    def test_the_block_the_extractor_appended_is_the_one_that_is_cut(self):
        body, refs = D._split_references(self.BODY + self.REFS)
        assert body == self.BODY
        assert refs["how"] == "appended_heading" and refs["boundary"] == len(self.BODY)
        assert refs["n_chars"] == len(self.REFS) and refs["text"] == self.REFS

    def test_a_text_with_no_such_heading_is_not_cut(self):
        # The docling PDF rung never writes it, and `references.split`'s
        # heuristic cut strands real body prose on a two-column paper -- so a
        # text this rule does not recognise is left whole, deliberately.
        body, refs = D._split_references(self.BODY + "\n\nREFERENCES\n\nAdenzato M (2019).")
        assert refs["boundary"] is None and refs["how"] == "no_reference_block"
        assert body.endswith("Adenzato M (2019).")

    def test_a_paper_that_mentions_references_in_its_prose_is_not_cut_there(self):
        text = ("## Methods\n\n# References were screened by two raters.\n\n"
                "## Results\n\nThe effect was 0.42.")
        body, refs = D._split_references(text)
        assert refs["boundary"] is None and body == text

    def test_the_last_such_heading_wins(self):
        text = self.BODY + "\n\n# References\n\n1. Early list.\n" + self.REFS
        body, refs = D._split_references(text)
        assert refs["text"] == self.REFS

    def test_every_numeral_of_the_cut_block_is_counted_somewhere(self):
        from forensic_metascience_ai_toolkit import numerals as N
        text = self.BODY + self.REFS
        body, refs = D._split_references(text)
        whole = len(N.index(text, tables_available=False))
        assert len(N.index(body, tables_available=False)) + \
            len(N.index(refs["text"], tables_available=False)) == whole, (
            "the cut classifies numerals, it does not suppress them")


# --------------------------------------------------------------------------
# 9. Pictures inside a Word supplement
# --------------------------------------------------------------------------

class TestTheImagesInsideAWordSupplementAreInventoried:
    def _docx(self, tmp_path, images, order_ids=None, name="s1.docx"):
        """A minimal .docx: only the parts the enumerator reads."""
        import zipfile
        path = tmp_path / name
        rels = "".join(
            f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/'
            f'officeDocument/2006/relationships/image" Target="media/{n}"/>'
            for i, n in enumerate(images, start=1))
        body = "".join(f'<w:drawing><a:blip r:embed="rId{i}"/></w:drawing>'
                       for i in (order_ids or range(1, len(images) + 1)))
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("word/_rels/document.xml.rels", f"<Relationships>{rels}</Relationships>")
            z.writestr("word/document.xml", f"<w:document><w:body>{body}</w:body></w:document>")
            for n in images:
                z.writestr(f"word/media/{n}", b"\x89PNG" + b"0" * 40)
        return path

    def test_every_embedded_picture_is_listed_in_document_order(self, tmp_path):
        from forensic_metascience_ai_toolkit.extraction import supplements_read as SR
        path = self._docx(tmp_path, ["image1.png", "image2.tiff", "image3.png"],
                          order_ids=[3, 1, 2])
        got = SR.docx_images(path)
        assert [g["name"] for g in got] == ["image3.png", "image1.png", "image2.tiff"]
        assert [g["index"] for g in got] == [1, 2, 3]
        assert {g["order"] for g in got} == {"document"}
        assert [g["format"] for g in got] == ["png", "png", "tiff"]
        assert all(g["n_bytes"] > 0 for g in got)

    def test_a_docx_whose_relationships_cannot_be_read_says_which_order_it_used(self, tmp_path):
        import zipfile
        from forensic_metascience_ai_toolkit.extraction import supplements_read as SR
        path = tmp_path / "s2.docx"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("word/media/image2.png", b"x" * 10)
            z.writestr("word/media/image1.png", b"x" * 10)
        got = SR.docx_images(path)
        assert [g["name"] for g in got] == ["image1.png", "image2.png"]
        assert {g["order"] for g in got} == {"file_name"}

    def test_a_docx_with_no_pictures_yields_none(self, tmp_path):
        from forensic_metascience_ai_toolkit.extraction import supplements_read as SR
        assert SR.docx_images(self._docx(tmp_path, [])) == []

    def test_the_inventory_says_it_does_not_know_what_the_picture_is(self, tmp_path):
        # A supplementary table drawn as a PNG and a supplementary figure are
        # the same object here, and saying which would be a reading. The
        # directory and the file name follow the fetcher's own convention,
        # because `supplements.present_files` reads a file's ROLE from a
        # declaration and never from its suffix.
        import json
        paper = tmp_path / "paper"
        paper.mkdir()
        self._docx(paper, ["image1.png"], name="paper_supplementary_info_1_s1.docx")
        (paper / "inputs.json").write_text(
            json.dumps({"supplements": ["paper_supplementary_info_1_s1.docx"]}), encoding="utf-8")
        got = D.supplement_figures(paper)
        assert len(got) == 1
        (f,) = got
        assert f["kind"] == "supplement_figure" and f["is_figure_or_table"] == "unknown"
        assert f["supplement_file"].endswith("s1.docx") and f["index"] == 1
        assert f["id"].startswith("supplement_figure:") and f["image"] == "image1.png"
        assert f["values_readable_from_text"] is False


# --------------------------------------------------------------------------
# 10. A supplement's role, and what it decides
# --------------------------------------------------------------------------

class TestASupplementHasARole:
    def _role(self, text, name="s1.docx"):
        from forensic_metascience_ai_toolkit import supplements as S
        return S.classify_role(name, text)

    def test_a_document_that_names_itself_a_protocol_is_one(self):
        # 10.1038/s41392-026-02904-0's second supplement, first lines verbatim.
        text = ("New Drug Category: Chemical Drug: Category 1.1\n\n"
                "Clinical Acceptance No.: CXHB1800089 (Strength 60 mg)\n\n"
                "Clinical Study Protocol\n\n"
                "A Randomized, Parallel-Controlled, Double-Blind, Double-Dummy, ...")
        got = self._role(text)
        assert got["role"] == "protocol" and got["basis"] == "title_line"
        assert got["matched"] == "Clinical Study Protocol"

    def test_a_results_supplement_that_MENTIONS_a_protocol_is_not_one(self):
        # The FIRST supplement of the same paper: 14,607 characters of results
        # with eleven tables, and every protocol keyword in it. A keyword count
        # cannot tell the two apart; the title line can.
        text = ("Supplementary Materials for\n\nMefatinib versus Gefitinib as First-Line "
                "Treatment for Advanced EGFR-Mutated Non-Small Cell Lung Cancer\n\n"
                "Appendix 1. List of participating centers, study protocol approval details, "
                "and principal/sub investigator\n\nInformed consent, version 3, inclusion "
                "criteria and exclusion criteria are listed below.")
        assert self._role(text)["role"] == "results"

    def test_every_role_is_in_the_closed_set(self):
        from forensic_metascience_ai_toolkit import supplements as S
        cases = ["Supplementary Table 1. Distribution of cancer types",
                 "Supplementary data: The impact of probiotic supplementation\n\nNMR extraction",
                 "## Data Sharing Statement\n\nData available: yes",
                 "Clinical Study Protocol", ""]
        for text in cases:
            assert self._role(text)["role"] in S.SUPPLEMENT_ROLES

    def test_a_spreadsheet_is_data_by_its_format(self):
        got = self._role("id,age,score\n1,22,4.5", name="participants.csv")
        assert got == {"role": "data", "basis": "format", "matched": ".csv"}

    def test_nothing_matched_is_other_and_never_a_guess(self):
        got = self._role("A one-page note about the study.")
        assert got["role"] == "other" and got["matched"] is None
        assert got["basis"] == "no_positive_test_matched"

    def test_a_data_sharing_statement_is_not_data(self):
        # It lists "Deidentified participant data, Data dictionary" in its body
        # and is a statement ABOUT data; its headings say what it is.
        text = ("## Data Sharing Statement\n\nConti. Early Home Visits. JAMA Netw Open.\n\n"
                "## Data\n\nData available:\n\nYes\n\nData types:\n\n"
                "Deidentified participant data, Data dictionary\n")
        assert self._role(text, name="s003.pdf")["role"] != "data"


# --------------------------------------------------------------------------
# 11. A supplement PDF with no extraction cache
# --------------------------------------------------------------------------

class TestAnUnextractedSupplementIsARefusalNotAZero:
    def _paper(self, tmp_path):
        """A paper directory whose supplement PDF has never been extracted.

        The XML is the article, so the document layer has a text to build on;
        the PDF is a real one-page PDF with no docling cache beside it, which
        is what `extract_pdf_tables` reports as `unextracted`.
        """
        import json
        fitz = pytest.importorskip("fitz", reason="PyMuPDF is not installed")
        paper = tmp_path / "paper"
        paper.mkdir()
        (paper / "paper.xml").write_text(
            "<article><front><article-meta><title-group><article-title>T</article-title>"
            "</title-group></article-meta></front><body><sec><title>Results</title>"
            "<p>The effect was 0.42 in 180 samples.</p></sec></body></article>",
            encoding="utf-8")
        doc = fitz.open()
        doc.new_page().insert_text((72, 100), "eTable 1. Outcomes", fontsize=11)
        doc.save(str(paper / "paper_supplementary_info_1_s001.pdf"))
        doc.close()
        (paper / "inputs.json").write_text(
            json.dumps({"supplements": ["paper_supplementary_info_1_s001.pdf"]}), encoding="utf-8")
        return paper

    def test_the_build_refuses_and_names_the_file_and_the_command(self, tmp_path):
        paper = self._paper(tmp_path)
        with pytest.raises(RuntimeError) as exc:
            D.build(paper)
        msg = str(exc.value)
        assert "paper_supplementary_info_1_s001.pdf" in msg
        assert "metascience extract-tables" in msg and "UNKNOWN" in msg
        assert "indistinguishable from a supplement that has neither" in msg

    def test_it_can_be_accepted_knowingly_and_is_then_recorded(self, tmp_path):
        paper = self._paper(tmp_path)
        doc = D.build(paper, allow_unextracted_supplements=True)
        assert doc["unextracted_supplements"] == ["paper_supplementary_info_1_s001.pdf"]
        assert any("UNEXTRACTED" in p and "UNKNOWN" in p for p in doc["problems"]), (
            "0 characters and 0 tables is served, and the account says why")

    def test_the_walker_reports_it_rather_than_passing_over_it(self, tmp_path):
        from forensic_metascience_ai_toolkit import prepass as P
        paper = self._paper(tmp_path)
        walked = P.paper_tables(paper, include_supplements=True)
        assert walked.unextracted_supplements == ["paper_supplementary_info_1_s001.pdf"]
        assert any("has NOT been extracted" in p for p in walked.problems)
        assert not walked.supplement_texts, "nothing is served for a file nobody has read"
