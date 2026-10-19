"""The text context an image-duplication adjudicator is given per figure.

Two properties carry the module and both are pinned here.

THE LOAD-BEARING ONE: every sentence this module emits -- a citing sentence or
a Methods imaging sentence -- verifies `verbatim` against
`quotes.build_haystack` for the same paper. A quote the verifier cannot certify
is a sentence the adjudicator may be told the paper printed when it did not,
which is the accusation-from-our-own-bug class this repo exists to prevent.

THE OTHER: every absence is named. A caption that could not be found says which
sources were asked and what each one gave -- "the XML has nine captions and
none of them is Figure 9" and "there is no XML" are different facts and license
different conclusions (LESSONS #1).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit import quotes
from forensic_metascience_ai_toolkit.extraction import jats
from metascience_observatory_image_analysis.image_forensics import figure_context as F
from metascience_observatory_image_analysis.image_forensics import pmc_figures

fitz = pytest.importorskip("fitz")


def test_document_scoped_captions_do_not_cross_same_figure_number(tmp_path):
    (tmp_path / "figures").mkdir()
    (tmp_path / "pmc_figures").mkdir()
    (tmp_path / "figures/figures.json").write_text(json.dumps({"figures": [
        {"label": "Figure 2", "caption": "Published PDF gel.", "page": 4}]}))
    (tmp_path / "pmc_figures/manifest.json").write_text(json.dumps({"figures": [
        {"figure_label": "Figure 2", "caption": "Accepted manuscript scatter."}]}))
    main, _ = F.resolve_document_captions(
        tmp_path, {"role": "main", "path": "paper.pdf"}, {"Figure 2"})
    pmc, _ = F.resolve_document_captions(
        tmp_path, {"role": "pmc_render", "path": "pmc_figures/manifest.json"},
        {"Figure 2"})
    assert main["Figure 2"].caption == "Published PDF gel."
    assert pmc["Figure 2"].caption == "Accepted manuscript scatter."


def test_numbered_manuscript_caption_continues_across_lines_and_pages(tmp_path):
    pdf = tmp_path / "numbered.pdf"
    doc = fitz.open()
    pages = [
        ["Figure 3. Expression in the stomach", "and duodenum of control and MS rats.",
         "Panel I is the MS field, n=500.", "", "Figure 4. A caption continuing"],
        ["onto the following page.", "Its numeric result is 123 and must remain.", "",
         "Figure 6. DEX inhibited inflammation.", "(A) MBP expression in duodenum 3 days after DEX",
         "treatment of control and MS rats.", "", "Methods and unrelated text."]]
    number = 683
    for rows in pages:
        pg = doc.new_page()
        for i, line in enumerate(rows):
            y = 100+i*30
            pg.insert_text((105,y), line or " ", fontsize=11)
            pg.insert_text((72,y), str(number), fontsize=10)
            number += 1
    doc.save(pdf)
    doc.close()
    caps, detail = F._captions_from_pdf(pdf)
    assert caps["Figure 3"] == ("Expression in the stomach and duodenum of control and MS rats. Panel I is the MS field, n=500.", 1)
    assert caps["Figure 4"] == ("A caption continuing onto the following page. Its numeric result is 123 and must remain.", 1)
    assert caps["Figure 6"] == ("DEX inhibited inflammation. (A) MBP expression in duodenum 3 days after DEX treatment of control and MS rats.", 2)
    assert "Methods" not in caps["Figure 6"][0]


def test_numeric_prose_is_not_treated_as_a_line_number_column(tmp_path):
    doc = fitz.open()
    pg = doc.new_page()
    for i, text in enumerate(["Figure 1. Counts.", "500", "100", "30", "20", "10"]):
        pg.insert_text((105,100+i*30), text)
    assert F._numbered_caption_blocks(doc) == {}
    doc.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

JATS_XML = """<?xml version="1.0"?>
<article><front><article-meta><title-group>
<article-title>A study of dendritic spines</article-title>
</title-group></article-meta></front>
<body>
<sec><title>Materials and Methods</title>
<p>Sections were stained with antibody X at 40x magnification.</p></sec>
<sec><title>Results</title>
<p>Spine density was higher in the treated group (<xref ref-type="fig" \
rid="F1">Fig. 1</xref>).</p>
<p>Both regions differed from control (<xref ref-type="fig" rid="F1 F2">\
Figs. 1 and 2</xref>).</p>
<fig id="F1"><label>Fig 1</label><caption><p>Golgi-Cox impregnated neurons in \
control rats.</p></caption></fig>
<fig id="F2"><label>Fig 2</label><caption><p>Dendritic spine density after \
treatment.</p></caption></fig>
</sec>
<sec><title>References</title>
<p>Smith J. Figure 7 of that report was reanalysed.</p></sec>
</body></article>
"""

ELSEVIER_XML = """<?xml version="1.0"?>
<full-text-retrieval-response xmlns:ce="http://www.elsevier.com/xml/common/dtd">
<originalText><xocs:doc xmlns:xocs="http://www.elsevier.com/xml/xocs/dtd">
<xocs:serial-item><article xmlns="http://www.elsevier.com/xml/ja/dtd">
<ce:sections>
<ce:section><ce:section-title>Materials and methods</ce:section-title>
<ce:para>Brain sections were immunostained and imaged by confocal \
microscopy.</ce:para></ce:section>
<ce:section><ce:section-title>Results</ce:section-title>
<ce:para>The antibody was specific (<ce:cross-ref refid="fig1">1\
</ce:cross-ref>).</ce:para>
<ce:para>Both markers colocalised (<ce:cross-refs refid="fig1 fig2">\
Figures 1 and 2</ce:cross-refs>).</ce:para>
</ce:section>
</ce:sections>
<ce:figure id="fig1"><ce:label>Figure 1</ce:label><ce:caption>\
<ce:simple-para>Characterization of the antibody.</ce:simple-para>\
</ce:caption><ce:link locator="gr1"/></ce:figure>
<ce:figure id="fig2"><ce:label>Figure 2</ce:label><ce:caption>\
<ce:simple-para>Colocalisation in the cortex.</ce:simple-para>\
</ce:caption><ce:link locator="gr2"/></ce:figure>
</article></xocs:serial-item></xocs:doc></originalText>
</full-text-retrieval-response>
"""


def _paper(tmp_path: Path, name: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    return d


@pytest.fixture
def jats_paper(tmp_path: Path) -> Path:
    d = _paper(tmp_path, "jats_paper")
    (d / "jats_paper.xml").write_text(JATS_XML, encoding="utf-8")
    return d


@pytest.fixture
def elsevier_paper(tmp_path: Path) -> Path:
    d = _paper(tmp_path, "els_paper")
    (d / "els_paper.xml").write_text(ELSEVIER_XML, encoding="utf-8")
    return d


def _write_manifest(d: Path, rows: list[dict]) -> Path:
    out = d / "pmc_figures"
    out.mkdir(exist_ok=True)
    path = out / "manifest.json"
    path.write_text(json.dumps({"schema_version": "1.0", "figures": rows}))
    return path


def _write_figures_json(d: Path, rows: list[dict]) -> Path:
    out = d / "figures"
    out.mkdir(exist_ok=True)
    path = out / "figures.json"
    path.write_text(json.dumps({"success": True, "figures": rows}))
    return path


#: Body prose for the PDF-only fixture. Each entry becomes its own text block,
#: which is what `figures.find_captions_in_blocks` reads.
PDF_BLOCKS = [
    "MATERIALS AND METHODS",
    "Brain sections were stained with cresyl violet and imaged at 20x "
    "magnification on a confocal microscope.",
    "RESULTS",
    "Plaque burden was reduced in the treated animals (Fig. 1A).",
    "The same pattern held across both regions (Figs. 1 and 2).",
    "Figure 1. Representative sections from the frontal cortex of treated "
    "and untreated animals.",
    "Figure 2. Quantification of plaque burden.",
]


def _make_pdf(path: Path, blocks: list[str]) -> Path:
    """One text block per entry, spaced far enough apart that PyMuPDF keeps
    them as separate blocks -- a caption is recognised BY its block."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y = 80.0
    for text in blocks:
        page.insert_textbox(fitz.Rect(60, y, 552, y + 60), text, fontsize=9)
        y += 90
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def pdf_paper(tmp_path: Path) -> Path:
    d = _paper(tmp_path, "pdf_paper")
    _make_pdf(d / "pdf_paper.pdf", PDF_BLOCKS)
    return d


# ---------------------------------------------------------------------------
# 1. Captions, their provenance, and their precedence
# ---------------------------------------------------------------------------

def test_captions_come_from_jats_fig_with_its_provenance(jats_paper):
    caps, tried = F.resolve_captions(jats_paper, None)
    assert set(caps) == {"Figure 1", "Figure 2"}
    assert caps["Figure 1"].caption.startswith("Golgi-Cox impregnated")
    assert caps["Figure 1"].source == "JATS <fig>"
    assert caps["Figure 1"].path.endswith("jats_paper.xml")
    assert "JATS <fig>: 2 captions" in tried


def test_captions_come_from_the_pmc_manifest(tmp_path):
    d = _paper(tmp_path, "manifest_only")
    _write_manifest(d, [{"figure_label": "Figure 3", "raw_label": "Fig. 3",
                         "caption": "A montage of four panels."}])
    caps, tried = F.resolve_captions(d, None)
    assert caps["Figure 3"].caption == "A montage of four panels."
    assert caps["Figure 3"].source == "pmc_figures/manifest.json"
    assert "pmc_figures/manifest.json: 1 caption" in tried
    assert "JATS <fig>: absent" in tried


def test_captions_come_from_figures_json_with_the_page(tmp_path):
    d = _paper(tmp_path, "figjson_only")
    _write_figures_json(d, [{"label": "Figure 4", "page": 7,
                             "caption": "Western blot of the cortex."}])
    caps, tried = F.resolve_captions(d, None)
    assert caps["Figure 4"].page == 7
    assert caps["Figure 4"].source == "figures/figures.json"
    assert "figures/figures.json: 1 caption" in tried


def test_captions_come_from_pdf_blocks_only_for_a_wanted_missing_figure(pdf_paper):
    caps, tried = F.resolve_captions(pdf_paper, {"Figure 1"})
    assert caps["Figure 1"].source == "PDF text layer"
    assert caps["Figure 1"].page == 1
    assert "Representative sections" in caps["Figure 1"].caption
    assert any(t.startswith("PDF text layer: ") and "caption block" in t
               for t in tried), tried
    # Figure 2's caption block is on the page, but nobody asked for it: the
    # PDF scan is the one source that can invent a figure, so it answers only
    # the question it was asked.
    assert "Figure 2" not in caps


def test_the_pdf_scan_says_it_was_not_consulted_when_nothing_is_missing(pdf_paper):
    _, tried = F.resolve_captions(pdf_paper, None)
    assert "PDF text layer: not consulted (no wanted figure was missing)" in tried


def test_precedence_xml_beats_manifest_beats_figures_json_beats_pdf(tmp_path):
    d = _paper(tmp_path, "all_sources")
    (d / "all_sources.xml").write_text(JATS_XML, encoding="utf-8")
    _write_manifest(d, [{"figure_label": "Figure 1", "caption": "from manifest"},
                        {"figure_label": "Figure 3", "caption": "from manifest"}])
    _write_figures_json(d, [{"label": "Figure 1", "page": 2,
                             "caption": "from figures.json"},
                            {"label": "Figure 3", "page": 3,
                             "caption": "from figures.json"},
                            {"label": "Figure 5", "page": 5,
                             "caption": "from figures.json"}])
    _make_pdf(d / "all_sources.pdf", PDF_BLOCKS)
    caps, _ = F.resolve_captions(d, {"Figure 1", "Figure 3", "Figure 5", "Figure 9"})
    assert caps["Figure 1"].source == "JATS <fig>"
    assert caps["Figure 3"].source == "pmc_figures/manifest.json"
    assert caps["Figure 5"].source == "figures/figures.json"
    assert "Figure 9" not in caps


def test_an_unreadable_manifest_is_named_not_silent(tmp_path):
    d = _paper(tmp_path, "broken_manifest")
    (d / "pmc_figures").mkdir()
    (d / "pmc_figures" / "manifest.json").write_text("{not json")
    _, tried = F.resolve_captions(d, None)
    assert "pmc_figures/manifest.json: unreadable (JSONDecodeError)" in tried


def test_an_unreadable_xml_is_named_not_silent(tmp_path):
    d = _paper(tmp_path, "broken_xml")
    (d / "broken_xml.xml").write_text("<article><body><p>unclosed")
    _, tried = F.resolve_captions(d, None)
    assert "JATS <fig>: unreadable (ParseError)" in tried


def test_a_missing_wanted_caption_names_every_source_tried(tmp_path):
    d = _paper(tmp_path, "missing_nine")
    (d / "missing_nine.xml").write_text(JATS_XML, encoding="utf-8")
    ctx = F.build_figure_context(d, wanted=["Figure 9"])
    gap = [g for g in ctx.gaps if g.startswith("Caption NOT FOUND for Figure 9")]
    assert len(gap) == 1, ctx.gaps
    assert "JATS <fig> (2 captions, none labelled Figure 9)" in gap[0]
    assert "pmc_figures/manifest.json (absent)" in gap[0]
    assert "figures/figures.json (absent)" in gap[0]
    assert "PDF text layer (absent)" in gap[0]


def test_an_elsevier_figure_with_no_graphic_is_found_here_and_dropped_there(
        elsevier_paper):
    """The whole reason `jats.figure_captions` exists.

    `pmc_figures.jats_figures` requires a `<graphic xlink:href>` because it
    FETCHES images; Elsevier points at artwork with `<ce:link locator>` and
    ships no `<graphic>` at all, so that rule reads an Elsevier paper as
    having no figures whatsoever.
    """
    xml = jats.find_xml(elsevier_paper)
    assert pmc_figures.jats_figures(xml.read_text(encoding="utf-8")) == []
    figs = jats.figure_captions(xml)
    assert [f["label"] for f in figs] == ["Figure 1", "Figure 2"]
    assert figs[0]["flavour"] == jats.ELSEVIER
    caps, tried = F.resolve_captions(elsevier_paper, None)
    assert caps["Figure 1"].source == "Elsevier <ce:figure>"
    assert "Elsevier <ce:figure>: 2 captions" in tried


def test_figure_id_map_joins_ids_to_labels(elsevier_paper, jats_paper):
    assert jats.figure_id_map(jats.find_xml(jats_paper)) == {
        "F1": "Figure 1", "F2": "Figure 2"}
    assert jats.figure_id_map(jats.find_xml(elsevier_paper)) == {
        "fig1": "Figure 1", "fig2": "Figure 2"}


def test_figure_captions_raises_rather_than_returning_empty_on_a_bad_file(tmp_path):
    bad = tmp_path / "bad.xml"
    bad.write_text("<article><body><p>unclosed")
    with pytest.raises(Exception) as exc:
        jats.figure_captions(bad)
    assert "ParseError" in type(exc.value).__name__


# ---------------------------------------------------------------------------
# 2. Mentions
# ---------------------------------------------------------------------------

def test_a_jats_xref_with_two_rids_yields_both_figures(jats_paper):
    ctx = F.build_figure_context(jats_paper)
    assert ctx.mention_source.startswith("JATS <xref> citations")
    assert set(ctx.mentions) == {"Figure 1", "Figure 2"}
    both = "Both regions differed from control (Figs. 1 and 2)."
    assert both in [m.sentence for m in ctx.mentions["Figure 1"]]
    assert [m.sentence for m in ctx.mentions["Figure 2"]] == [both]


def test_an_elsevier_cross_ref_with_bare_number_inner_text_is_still_a_mention(
        elsevier_paper):
    """The regex cannot see this one, which is why the XML path exists.

    Elsevier renders `<ce:cross-ref refid="fig1">1</ce:cross-ref>` as a bare
    `1`; no regex over the rendered text may claim a lone digit as a figure
    reference without claiming every other number in the paper too.
    """
    ctx = F.build_figure_context(elsevier_paper)
    assert ctx.mention_source.startswith("Elsevier <ce:cross-ref> citations")
    sentences = [m.sentence for m in ctx.mentions["Figure 1"]]
    assert "The antibody was specific (1)." in sentences
    assert F._keys_in("The antibody was specific (1).") == {}


def test_an_elsevier_cross_refs_element_yields_every_id(elsevier_paper):
    ctx = F.build_figure_context(elsevier_paper)
    both = "Both markers colocalised (Figures 1 and 2)."
    assert [m.sentence for m in ctx.mentions["Figure 2"]] == [both]


@pytest.mark.parametrize("sentence,expected", [
    ("The cortex was affected (Fig. 2A).", {"Figure 2": "A"}),
    ("As shown in Figure 2, the effect held.", {"Figure 2": ""}),
    ("Both replicates agreed (Figs. 2 and 3).", {"Figure 2": "", "Figure 3": ""}),
    ("The panels vary (Figure 2A-C).", {"Figure 2": "A-C"}),
    ("The panels vary (Figure 2A–C).", {"Figure 2": "A–C"}),
    ("Details are in eFigure 4 of the supplement.", {"eFigure 4": ""}),
    ("Details are in Figure S3 of the supplement.", {"Figure S3": ""}),
    ("The configuration 3 was unchanged.", {}),
    ("Table 2 lists the cohorts.", {}),
])
def test_the_mention_regex_reads_the_forms_papers_actually_print(sentence, expected):
    assert F._keys_in(sentence) == expected


@pytest.mark.parametrize("sentence,journal,compound", [
    # A journal range stays a range; a dissertation label stays one figure.
    ("Both are shown (Figures 2-4).", {"Figure 2": "", "Figure 4": ""},
     {"Figure 2-4": ""}),
    ("Both are shown (Figures 2-10).", {"Figure 2": "", "Figure 10": ""},
     {"Figure 2-10": ""}),
    ("LRP1 bound MAG (Figure 2-7A).", {"Figure 2": ""}, {"Figure 2-7": "A"}),
    # A dotted chapter number (Dickendesher, U Michigan 2013) is glued: the
    # compound reading takes `2.10a` whole, the journal reading stops at 2,
    # and `Figure 2. Ten` is figure 2 and a sentence end under both.
    ("Binding held (Figure 2.10a) and (Figure 4.2b).",
     {"Figure 2": "", "Figure 4": ""}, {"Figure 2-10": "a", "Figure 4-2": "b"}),
    ("See Figure 2. Ten mice were used.", {"Figure 2": ""}, {"Figure 2": ""}),
    # An appendix letter glued to its digits is part of the number; the `d`
    # of `and` is not.
    ("Tmem125 mice (Figure A1.1b) grew (Figs. 2 and 3).",
     {"Figure A1": "", "Figure 2": "", "Figure 3": ""},
     {"Figure A1-1": "b", "Figure 2": "", "Figure 3": ""}),
    ("As in Figure 2-7 and Figure 2-10, the effect held.",
     {"Figure 2": "", "Figure 7": "", "Figure 10": ""},
     {"Figure 2-7": "", "Figure 2-10": ""}),
    # Panel ranges read the same way under both.
    ("The panels vary (Figure 2A-C).", {"Figure 2": "A-C"}, {"Figure 2": "A-C"}),
    ("Both replicates agreed (Figs. 2 and 3).",
     {"Figure 2": "", "Figure 3": ""}, {"Figure 2": "", "Figure 3": ""}),
])
def test_a_dashed_figure_number_is_read_per_document(sentence, journal, compound):
    """`Figure 2-7` is a RANGE in a journal paper and ONE FIGURE in a
    chapter-numbered dissertation. Nothing in the sentence decides it; the
    document's captions do (`uses_compound_numbers`). MEASURED 2026-09-14 on
    the Stiles (UCSD 2013) thesis: every chapter-2 figure keyed to
    `Figure 2`, so the screening model was handed seven captions under one
    label and no citing sentence could be attributed to the right figure."""
    assert F._keys_in(sentence) == journal
    assert F._keys_in(sentence, compound=True) == compound


def test_compound_numbering_is_decided_by_the_captions():
    assert F.uses_compound_numbers(["Figure 2-7", "Figure 1"]) is True
    assert F.uses_compound_numbers(["Figure S2-7"]) is True
    assert F.uses_compound_numbers(["Figure A1-1"]) is True
    assert F.uses_compound_numbers(["Figure 2", "Figure S1", None, ""]) is False
    assert F.uses_compound_numbers([]) is False


def test_a_chapter_numbered_thesis_keeps_its_captions_and_mentions_apart(tmp_path):
    """End to end on a PDF with `Figure 2-6` and `Figure 2-7` captions: two
    caption keys, and a citing sentence lands under the figure it names."""
    d = _paper(tmp_path, "thesis")
    doc = fitz.open()
    for blocks in (
        # Page 1, the front matter: every figure listed with dot leaders.
        # It is a contents page and must not win the caption lookup.
        ["LIST OF FIGURES",
         "Figure 2-6. RAP blocks MAG binding to LRP1. ............................ 48",
         "Figure 2-7. CCRII and CCRIV bind MAG with high affinity. .............. 51"],
        # Page 2, the body and the real captions.
        ["Results.",
         "LRP1 bound MAG with high affinity (Figure 2-7A).",
         "Binding was RAP-reversible (Figure 2-6).",
         "Figure 2-6 RAP blocks MAG binding to LRP1.",
         "Figure 2-7 CCRII and CCRIV bind MAG with high affinity."],
    ):
        page = doc.new_page(width=612, height=792)
        y = 80.0
        for text in blocks:
            page.insert_textbox(fitz.Rect(60, y, 552, y + 60), text, fontsize=9)
            y += 90
    doc.save(d / "thesis.pdf")
    doc.close()
    ctx = F.build_figure_context(d, wanted=["Figure 2-7", "Figure 2-6"])
    # The caption under the figure, not the contents line (a trailing period
    # is stripped by the caption parser).
    assert ctx.captions["Figure 2-7"].caption == \
        "CCRII and CCRIV bind MAG with high affinity"
    assert ctx.captions["Figure 2-6"].caption == "RAP blocks MAG binding to LRP1"
    assert "...." not in ctx.captions["Figure 2-7"].caption
    assert [m.panels for m in ctx.mentions["Figure 2-7"]] == ["A"]
    assert ctx.mentions["Figure 2-7"][0].sentence == \
        "LRP1 bound MAG with high affinity (Figure 2-7A)."
    assert [m.sentence for m in ctx.mentions["Figure 2-6"]] == \
        ["Binding was RAP-reversible (Figure 2-6)."]
    assert "Figure 2" not in ctx.captions and "Figure 7" not in ctx.mentions


def test_a_caption_block_is_not_counted_as_a_mention(pdf_paper):
    ctx = F.build_figure_context(pdf_paper)
    caption = ("Figure 1. Representative sections from the frontal cortex of "
               "treated and untreated animals.")
    assert caption not in [m.sentence for m in ctx.mentions.get("Figure 1", [])]
    assert "Plaque burden was reduced in the treated animals (Fig. 1A)." in [
        m.sentence for m in ctx.mentions["Figure 1"]]


def test_a_hit_in_the_references_is_excluded(jats_paper):
    """`Smith J. Figure 7 of that report was reanalysed.` is a citation of
    somebody else's figure, and counting it would put a figure in the context
    that this paper does not have."""
    text = jats.paper_text(jats_paper)
    assert "Figure 7" in text
    mentions, _src = F.extract_mentions(jats_paper, text, F.PAPER_TEXT)
    assert "Figure 7" not in mentions
    assert set(mentions) == {"Figure 1", "Figure 2"}


def test_mentions_carry_the_section_they_were_found_in(jats_paper):
    ctx = F.build_figure_context(jats_paper)
    assert {m.section for ms in ctx.mentions.values() for m in ms} == {"results"}


def test_an_absent_mention_for_a_wanted_figure_is_a_named_gap(jats_paper):
    ctx = F.build_figure_context(jats_paper, wanted=["Figure 9"])
    assert any(g == ("no in-text mention of Figure 9 found in "
                     + ctx.mention_source) for g in ctx.gaps), ctx.gaps


def test_more_mentions_than_fit_are_counted_and_the_file_is_named(tmp_path):
    d = _paper(tmp_path, "many_mentions")
    (d / "many_mentions.xml").write_text(
        '<?xml version="1.0"?><article><body><sec><title>Results</title>'
        + "".join(f"<p>Result number {i} was clear (Fig. 1).</p>"
                  for i in range(1, 5))
        + "</sec></body></article>", encoding="utf-8")
    ctx = F.build_figure_context(d)
    assert len(ctx.mentions["Figure 1"]) == 4
    lines = F.render_group_context(ctx, ["Figure 1"], {})
    shown = [ln for ln in lines if ln.strip().startswith("cited in text:")]
    assert len(shown) == F.MENTIONS_PER_FIGURE
    assert lines[-1].strip() == (f"2 further mention(s) not shown -- Read "
                                 f"{ctx.mentions['Figure 1'][0].path}")


# --- THE LOAD-BEARING TEST -------------------------------------------------

@pytest.mark.parametrize("fixture", ["jats_paper", "pdf_paper"])
def test_every_emitted_sentence_verifies_verbatim_against_the_haystack(
        fixture, request):
    """No sentence reaches the adjudicator that the quote verifier would not
    certify as a contiguous span of this paper."""
    paper_dir = request.getfixturevalue(fixture)
    ctx = F.build_figure_context(paper_dir)
    hay = quotes.build_haystack(paper_dir)
    assert hay, "the haystack itself is empty; the test would pass vacuously"
    folded = quotes.fold_haystack(hay)
    emitted = [m for ms in ctx.mentions.values() for m in ms]
    emitted += list(ctx.methods.imaging_sentences)
    assert emitted, "nothing was emitted; the test would pass vacuously"
    for rec in emitted:
        verdict = quotes.classify(rec.sentence, hay, folded)
        assert verdict["quote_verified"] == "verbatim", (rec.sentence, verdict)


def test_the_pdf_only_paper_falls_back_to_the_text_layer_by_name(pdf_paper):
    """`jats.paper_text` is empty for a PDF that has never been through
    docling. That is UNKNOWN, not an absence of content -- so the text layer
    is read and SAID to be the source."""
    assert jats.paper_text(pdf_paper).strip() == ""
    ctx = F.build_figure_context(pdf_paper)
    assert ctx.paper_text_source == F.PDF_TEXT_LAYER
    assert ctx.paper_text.strip()
    assert ctx.mention_source == ("figure-reference regex over "
                                 "the PDF text layer")


# ---------------------------------------------------------------------------
# 3. Methods
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("heading", [
    "Methods", "Materials and Methods", "Methods and Materials",
    "Materials and methods", "Patients and Methods", "Subjects and Methods",
    "Experimental Procedures", "STAR Methods", "2. Methods",
])
def test_every_widened_methods_heading_is_located(heading):
    text = (f"# Title\n\nAn abstract.\n\n## {heading}\n\n"
            "Sections were stained.\n\n## Results\n\nThe effect held.\n")
    win = F.methods_window(text, "/tmp/p.xml")
    assert win.located, heading
    assert win.heading.lower().endswith(heading.lower().lstrip("2. "))
    assert "Sections were stained." in win.text
    assert "The effect held." not in win.text


def test_a_truncated_methods_note_carries_the_path_and_both_numbers():
    filler = ("The animals were housed under standard conditions. " * 200)
    text = "## Methods\n\n" + filler + "\n\n## Results\n\nDone.\n"
    win = F.methods_window(text, "/abs/paper.xml")
    assert win.total_chars > F.METHODS_CHARS
    assert win.note == (f"Methods truncated at 6,000 of {win.total_chars:,} "
                        f"chars -- Read /abs/paper.xml for the rest")
    assert len(win.text) == F.METHODS_CHARS
    assert win.full_text.strip().endswith("standard conditions.")


def test_imaging_sentences_are_drawn_from_beyond_the_shown_window():
    filler = ("The animals were housed under standard conditions. " * 200)
    late = "Sections were counterstained with cresyl violet at 20x magnification."
    text = "## Methods\n\n" + filler + " " + late + "\n\n## Results\n\nDone.\n"
    win = F.methods_window(text, "/abs/paper.xml")
    assert late not in win.text          # it sits past the 6,000-char head
    assert [m.sentence for m in win.imaging_sentences] == [late]
    assert win.imaging_note == "1 of 1 shown"


def test_imaging_sentences_are_capped_and_the_cap_is_reported():
    filler = ("The animals were housed under standard conditions. " * 200)
    late = " ".join(f"Slide {i} was stained overnight." for i in range(20))
    text = "## Methods\n\n" + filler + " " + late + "\n\n## Results\n\nDone.\n"
    win = F.methods_window(text, "/abs/paper.xml")
    assert len(win.imaging_sentences) == F.METHODS_IMAGING_SENTENCES
    assert win.imaging_note == "12 of 20 shown"


def test_no_imaging_sentence_means_an_empty_note():
    text = "## Methods\n\nWe fitted a linear model.\n\n## Results\n\nDone.\n"
    win = F.methods_window(text, "/abs/paper.xml")
    assert win.imaging_sentences == []
    assert win.imaging_note == ""


def test_an_unlocatable_methods_section_says_so_and_shows_the_opening():
    text = "A paper with no headings at all. " * 20
    win = F.methods_window(text, "/abs/paper.pdf")
    assert win.located is False
    assert win.note == ("No Methods section identified (no heading matched); "
                        "showing the opening of the paper")
    assert win.text.startswith("A paper with no headings")


def test_no_text_at_all_is_its_own_named_state():
    win = F.methods_window("", "/abs/paper.pdf")
    assert win.located is False
    assert win.note == "no text could be read for this paper"
    assert win.text == "" and win.total_chars == 0


# ---------------------------------------------------------------------------
# 4. The figure-key vocabulary
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label,key", [
    ("Fig. 2A", "Figure 2"),
    ("Fig 2", "Figure 2"),
    ("Figure 2", "Figure 2"),
    ("FIGURE 3A", "Figure 3"),
    ("Figs. 2 and 3", "Figure 2"),
    ("Figure 2 (cont.)", "Figure 2"),
    ("Figure S1", "Figure S1"),
    ("figure s1", "Figure S1"),
    ("eFigure 4", "eFigure 4"),
    ("Figure supplement 3", "Figure supplement 3"),
    ("Figure 02", "Figure 2"),
    # A dissertation numbers by chapter: one figure, never figures 2 and 7.
    ("Figure 2-7", "Figure 2-7"),
    ("Figure 2\u20137", "Figure 2-7"),
    ("Fig. 2-7A", "Figure 2-7"),
    ("Figure 3-10", "Figure 3-10"),
    # A dotted chapter number and an appendix letter (Dickendesher 2013)
    # spell the same key as the caption parser's label.
    ("Figure 2.10", "Figure 2-10"),
    ("Figure A1.1", "Figure A1-1"),
    ("Fig. A2.1b", "Figure A2-1"),
    ("Figure A1", "Figure A1"),
    ("Figure A.1", "Figure A1"),
    ("Fig. A.1.", "Figure A1"),
    ("Figure legends", None),
    ("panel 2 of the montage", None),
    ("Table 1", None),
    ("", None),
    (None, None),
])
def test_the_figure_key_vocabulary(label, key):
    assert F.figure_key(label) == key


@pytest.mark.parametrize("label", ["Fig. 3", "Figure 3", "FIGURE 3", "Fig 3",
                                   "Figure S1", "eFigure 4", "Figure 2-7",
                                   "Figure 3\u201310", "Figure 2.10",
                                   "Figure A1.1", "Figure A1", "Figure A.1"])
def test_figure_key_agrees_with_the_image_tracks_normaliser_on_plain_labels(label):
    """The figure-level joins in this package are keyed on
    `pmc_figures.normalise_label`; a second spelling of the same figure is a
    join that silently matches nothing."""
    assert F.figure_key(label) == pmc_figures.normalise_label(label)


def test_a_panel_letter_is_dropped_where_the_image_track_keeps_it():
    """The one deliberate divergence, stated so it cannot drift into a bug:
    a duplication between panel A and panel C is a fact about ONE figure, and
    the caption and citing sentences belong to the whole figure."""
    assert pmc_figures.normalise_label("Figure 3A") == "Figure 3A"
    assert F.figure_key("Figure 3A") == "Figure 3"


# ---------------------------------------------------------------------------
# 5. Rendering
# ---------------------------------------------------------------------------

def test_first_use_prints_the_caption_and_its_mentions(jats_paper):
    ctx = F.build_figure_context(jats_paper)
    seen: dict[str, int] = {}
    lines = F.render_group_context(ctx, ["Figure 1A"], seen)
    assert lines[0] == ('- Figure 1 -- caption (JATS <fig>): "Golgi-Cox '
                        'impregnated neurons in control rats."')
    assert lines[1] == ('    cited in text: "Spine density was higher in the '
                        'treated group (Fig. 1)." (results; the paper\'s text)')
    assert seen == {"Figure 1": 1}


def test_a_second_group_reusing_a_figure_points_at_the_first(jats_paper):
    ctx = F.build_figure_context(jats_paper)
    seen: dict[str, int] = {}
    F.render_group_context(ctx, ["Figure 1A"], seen)
    lines = F.render_group_context(ctx, ["Figure 1C", "Figure 2"], seen)
    assert lines[0] == ('- Figure 1 -- caption: "Golgi-Cox impregnated '
                        'neurons in control rats...." (full caption and '
                        'citing sentences at Group 1)')
    assert lines[1].startswith('- Figure 2 -- caption (JATS <fig>): ')
    assert seen == {"Figure 1": 1, "Figure 2": 2}


def test_an_absent_caption_and_an_absent_mention_render_as_named_absences(
        jats_paper):
    ctx = F.build_figure_context(jats_paper, wanted=["Figure 9"])
    lines = F.render_group_context(ctx, ["Figure 9"], {})
    assert lines[0] == ("- Figure 9 -- caption: NOT FOUND (sources tried: "
                        + "; ".join(ctx.caption_sources_tried) + ")")
    assert lines[1] == ("    cited in text: none found (sources tried: "
                        + ctx.mention_source + ")")


def test_a_long_caption_is_cut_and_the_cut_is_announced(tmp_path):
    d = _paper(tmp_path, "long_caption")
    _write_figures_json(d, [{"label": "Figure 1", "page": 1,
                             "caption": "A" * (F.CAPTION_CHARS + 500)}])
    ctx = F.build_figure_context(d)
    line = F.render_group_context(ctx, ["Figure 1"], {})[0]
    assert line.endswith('[caption truncated at 2,500 chars]"')
    assert line.count("A") == F.CAPTION_CHARS


def test_the_paper_header_lists_absolute_paths_and_the_methods_note(jats_paper):
    ctx = F.build_figure_context(jats_paper)
    head, tail = F.render_paper_context(ctx, {})
    assert head[0] == ("## Where the paper is (absolute paths; `Read` any of "
                       "them)")
    xml = str((jats_paper / "jats_paper.xml").resolve())
    assert f"- XML: {xml}" in head
    assert all(Path(p).is_absolute() for p in ctx.sources.values())
    assert any(ln.startswith("## Methods (Materials and Methods;") for ln in head)
    assert any("Sections were stained with antibody X" in ln for ln in head)
    # Nothing was rendered into a group, so both figures are "other".
    assert tail[0] == "## Other figures (not involved in any group)"
    assert any(ln.startswith("- Figure 2 -- caption (JATS <fig>)") for ln in tail)


def test_the_imaging_block_is_headed_with_its_own_count(tmp_path):
    d = _paper(tmp_path, "imaging_header")
    filler = ("The animals were housed under standard conditions. " * 200)
    late = "Sections were counterstained with cresyl violet."
    (d / "body.md").write_text("")  # not read; the XML below is the source
    (d / "imaging_header.xml").write_text(
        '<?xml version="1.0"?><article><body><sec><title>Methods</title>'
        f"<p>{filler}{late}</p></sec>"
        "<sec><title>Results</title><p>Done.</p></sec></body></article>",
        encoding="utf-8")
    ctx = F.build_figure_context(d)
    head, _tail = F.render_paper_context(ctx, {})
    assert ("### Imaging/staining sentences from the rest of Methods "
            f"({ctx.methods.imaging_note})") in head
    assert any(ln.startswith('- "') and "cresyl violet" in ln for ln in head)


def test_render_context_bounds_the_whole_paper_and_announces_the_cut(tmp_path):
    d = _paper(tmp_path, "huge_captions")
    rows = [{"label": f"Figure {i}", "page": i, "caption": "B" * 2400}
            for i in range(1, 40)]
    _write_figures_json(d, rows)
    ctx = F.build_figure_context(d)
    out = F.render_context(ctx, [["Figure 1"], ["Figure 2"]])
    assert len(out) < F.CONTEXT_CHARS_PER_PAPER + 200
    assert "figure context truncated at 40,000 chars" in out


# ---------------------------------------------------------------------------
# 6. An empty directory
# ---------------------------------------------------------------------------

def test_an_empty_directory_names_every_absence_and_raises_nothing(tmp_path):
    d = _paper(tmp_path, "empty_paper")
    ctx = F.build_figure_context(d, wanted=["Figure 1"])
    assert ctx.captions == {} and ctx.mentions == {}
    assert ctx.paper_text_source == ""
    assert f"No text source in {d}: no XML text and no PDF" in ctx.gaps
    assert "no text could be read for this paper" in ctx.gaps
    assert any(g.startswith("Caption NOT FOUND for Figure 1") for g in ctx.gaps)
    assert any(g.startswith("no in-text mention of Figure 1") for g in ctx.gaps)
    assert ctx.caption_sources_tried == [
        "JATS <fig>: absent", "pmc_figures/manifest.json: absent",
        "publisher_figures/manifest.json: absent",
        "figures/figures.json: absent", "PDF text layer: absent"]


def test_the_summary_keys_are_the_contract_another_surface_reads(jats_paper):
    s = F.build_figure_context(jats_paper, wanted=["Figure 1"]).summary()
    assert set(s) == {"captions", "caption_sources_tried", "mentions",
                      "mention_source", "methods", "sources",
                      "paper_text_source", "paper_text_chars", "gaps"}
    assert set(s["captions"]["Figure 1"]) == {"caption", "source", "path", "page"}
    assert set(s["mentions"]["Figure 1"][0]) == {"sentence", "section",
                                                     "source", "path", "offset",
                                                     "panels"}
    assert set(s["methods"]) == {"text", "note", "heading", "path", "located",
                                 "full_text", "imaging_sentences",
                                 "imaging_note"}
    assert set(s["methods"]["imaging_sentences"][0]) == {"sentence", "source"}
    assert json.dumps(s)  # the whole thing is JSON-able


# ---------------------------------------------------------------------------
# The sentence splitter, which every emitted sentence passes through
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "The effect held (see Fig. 2A) across both cohorts.",
    "The effect held (Figs. 2 and 3) across both cohorts.",
    "As Masliah et al. 2005 reported, the effect held across both cohorts.",
    "Markers, e.g. GFAP, were unchanged across both cohorts.",
    "Markers, i.e. GFAP and NeuN, were unchanged in both cohorts.",
    "Treated vs. untreated animals differed across both cohorts.",
    "Sections were cut ca. 40 um thick from both cohorts.",
    "Sections were cut approx. 40 um thick from both cohorts.",
    "Grant No. 12345 supported this work in both cohorts.",
])
def test_the_splitter_does_not_cut_at_the_abbreviations_papers_use(text):
    """A sentence cut at `Fig.` loses the half that names the figure, which is
    the only half this module is looking for."""
    assert [F._slice(text, a, b) for a, b in F._sentences(text)] == [text]


def test_the_splitter_does_cut_at_a_real_sentence_end():
    text = "The effect held (Fig. 2A). The control was unchanged."
    assert [F._slice(text, a, b) for a, b in F._sentences(text)] == [
        "The effect held (Fig. 2A).", "The control was unchanged."]


@pytest.mark.parametrize("heading", ["## Immunohistochemistry",
                                     "IMMUNOHISTOCHEMISTRY"])
def test_a_heading_line_is_not_glued_onto_the_sentence_below_it(heading):
    """MEASURED 2026-09-02 on `10.1016--j.ajpath.2012.11.018`: an imaging
    sentence came back as `## Mass Spectrometry Recombinant a-syn (...) was
    electrophoresed ...`, our section heading presented to the adjudicator as
    part of the authors' sentence. A PDF text layer does the same with its
    all-caps headings and no blank line at all."""
    text = f"An opening line.\n\n{heading}\nSections were stained overnight.\n"
    got = [F._slice(text, a, b) for a, b in F._sentences(text)]
    assert "Sections were stained overnight." in got
    assert not any(g.startswith(heading.lstrip("# ")) for g in got), got


# ---------------------------------------------------------------------------
# 6. One canonical form for supplementary figures (2026-09-14)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label,key", [
    # MEASURED on 10.1016--j.jalz.2018.02.017: consuming the prefix filed
    # three appendix figures under the main text's labels (six figures,
    # three labels). The S-form is the publisher manifest's spelling.
    ("Supplementary Figure 3", "Figure S3"),
    ("Supplemental Fig. 2A", "Figure S2"),
    ("Supp. Fig. 4", "Figure S4"),
    ("Supporting Figure 1", "Figure S1"),
    ("Supplementary Figure S3", "Figure S3"),      # never doubled
    ("Supplementary Figure 2-3", "Figure S2-3"),   # S is not a chapter letter
    ("Figure S3", "Figure S3"),
    ("Extended Data Fig. 2", "Figure 2"),          # today's form, deliberately
    ("Figure supplement 3", "Figure supplement 3"),  # eLife: a different thing
    ("Figure 2—figure supplement 1", "Figure 2"),
    ("eFigure 4", "eFigure 4"),
])
def test_supplementary_figures_have_one_canonical_key(label, key):
    assert F.figure_key(label) == key


@pytest.mark.parametrize("label", ["Supplementary Figure 3", "Supplemental Fig. 2",
                                   "Supporting Figure 1", "Supplementary Figure S3"])
def test_the_three_normalisers_agree_on_the_supplementary_form(label):
    from metascience_observatory_image_analysis.extraction.figures import _parse_caption_block
    assert F.figure_key(label) == pmc_figures.normalise_label(label)
    assert _parse_caption_block(label + ". A caption body.")[0] == F.figure_key(label)


def test_a_mention_of_a_supplementary_figure_cites_its_own_key():
    """`Supplementary Figures 3 and 4` cites S3 and S4, the keys their
    captions carry; read as `Figure 3` the mention joined the main figure."""
    assert F._keys_in("As shown in Supplementary Figure 3 and Figure S4.") == \
        {"Figure S3": "", "Figure S4": ""}
    assert F._keys_in("Supplementary Figures 3 and 4 show it; Figure 2A too.") == \
        {"Figure S3": "", "Figure S4": "", "Figure 2": "A"}
    assert F._keys_in("Figure 2—figure supplement 1 shows") == \
        {"Figure 2": "", "Figure supplement 1": ""}
