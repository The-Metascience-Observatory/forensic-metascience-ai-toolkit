"""The six representative papers, read from disk with NO network and no model.

Gated on the corpus being present (`METASCIENCE_WAVE2B_CORPUS`, default
`/tmp/jats1/wave2b`), in the shape `test_jats_corpus.py` already uses: the unit
tests beside this file pin the rules on fixtures cut from these papers, and this
one is the check that the rules still hold on the whole document each fixture
came out of.

Every assertion here is a fact about a file on disk. The figure counts are the
`<fig>` elements the publisher's own XML declares, so a paper reporting fewer
figures than its markup declares is reporting our reading, not the paper.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit.extraction import jats as _jats
from forensic_metascience_ai_toolkit.scaffold import document as D

CORPUS = Path(os.environ.get("METASCIENCE_WAVE2B_CORPUS", "/tmp/jats1/wave2b"))
PAPERS = sorted(p for p in CORPUS.glob("10.*") if p.is_dir()) if CORPUS.is_dir() else []

pytestmark = pytest.mark.skipif(len(PAPERS) < 6,
                                reason=f"the wave 2b corpus is not present at {CORPUS}")


def _article_text(paper: Path) -> str:
    text, source = _jats._derive_paper_text(paper)
    assert source == "xml_publisher", f"{paper.name} is not on the XML rung ({source})"
    return text


@pytest.mark.parametrize("name", [p.name for p in PAPERS])
def test_the_declared_figures_are_found_with_no_network(name):
    paper = CORPUS / name
    xml = _jats.find_xml(paper)
    declared = len(_jats.figure_captions(xml))
    found = D.figure_captions(_article_text(paper))
    assert len(found) == declared, (
        f"{name}: the XML declares {declared} figure(s) and the document layer read "
        f"{len(found)} from the served text -- every figure record on this paper "
        "would exist only because the PMC image fetch had run")


JAMA = "10.1001--jamanetworkopen.2023.51752"


@pytest.fixture(scope="module")
def jama_document():
    return D.build(CORPUS / JAMA)


def test_the_truncated_supplement_reports_served_of_available(jama_document):
    # Its first supplement is 289,222 characters; 50,000 were served. Before
    # this the only trace was a marker sentence inside the served text.
    spans = {s["file"]: s for s in jama_document["supplement_spans"]}
    s001 = next(s for f, s in spans.items() if f.endswith("s001.pdf"))
    assert s001["n_chars_available"] == 289_222
    assert s001["n_chars"] == 50_000 and s001["truncated"] is True
    assert 0.17 < s001["served_of_available"] < 0.18
    s003 = next(s for f, s in spans.items() if f.endswith("s003.pdf"))
    assert s003["truncated"] is False
    assert s003["n_chars"] == s003["n_chars_available"] == 1587


def test_no_truncation_marker_reaches_the_served_text_or_the_floor(jama_document):
    from forensic_metascience_ai_toolkit.extraction.pdf import TRUNCATION_MARKER

    assert "[TEXT TRUNCATED" not in jama_document["text"]
    assert TRUNCATION_MARKER not in jama_document["text"]


def test_the_document_says_which_supplements_were_cut_and_by_how_much(jama_document):
    src = jama_document["source"]
    assert src["n_supplements_truncated"] == 2
    assert src["n_chars_supplements"] == 101_587
    assert src["n_chars_supplements_available"] == 400_968
    cut = [p for p in jama_document["problems"] if "characters served" in p]
    assert len(cut) == 2 and any("289,222" in p for p in cut)


def test_two_tables_on_one_supplement_page_are_drawn_separately(jama_document):
    """s001 page 15 carries eTable 2 and eTable 3. Both were drawn as the same
    whole-page image -- byte-identical PNGs, one per table."""
    fitz = pytest.importorskip("fitz", reason="PyMuPDF is not installed")
    from forensic_metascience_ai_toolkit.scaffold import reconstruct as RC

    tables = jama_document["tables"]
    p15 = [t for t in tables if t.get("source") == "supplement"
           and str(t.get("supplement_file") or "").endswith("s001.pdf")
           and t.get("supplement_page") == 15]
    assert len(p15) == 2, "the page the defect was found on carries exactly two walked tables"
    path = CORPUS / JAMA / p15[0]["supplement_file"]
    locs = [RC.locate_pdf_table(path, t, siblings=[o]) for t, o in (p15, p15[::-1])]
    assert all(l["pages"] == [15] and l.get("clip") for l in locs)
    with fitz.open(str(path)) as doc:
        page = doc[14]
        seen = [RC._squash(page.get_text(clip=fitz.Rect(*l["clip"]))) for l in locs]
    for i, (t, txt) in enumerate(zip(p15, seen)):
        mine = RC._table_needles(t)
        theirs = RC._table_needles(p15[1 - i]) - mine
        assert sum(1 for n in mine if n in txt) >= 0.8 * len(mine), "its own strings are in its render"
        assert not [n for n in theirs if n in txt], (
            f"{t['id']}'s render carries the other table's strings; that is the render that made "
            "a reading of one table an answer about the other")


META = "10.1017--s0033291723003501"


def test_the_meta_analysis_table_2_is_drawn_whole(tmp_path):
    """237 rows, 6,824 px of content, drawn into a 5,000 px window: the last
    ~60 rows were absent from the image and no error said so."""
    import xml.etree.ElementTree as ET

    from forensic_metascience_ai_toolkit.scaffold import reconstruct as RC

    if not RC.chrome_binary():
        pytest.skip("no headless Chromium on this machine")
    pytest.importorskip("PIL", reason="Pillow is not installed; clipping cannot be detected")
    paper = CORPUS / META
    root = ET.parse(str(_jats.find_xml(paper))).getroot()
    html = RC.table_html(RC.table_element(root, "T2", 2))
    assert html and html.count("<tr") == 237
    old, new = {}, {}
    RC.render_png(html, tmp_path / "old.png", height=5000, meta=old)
    assert RC.render_png(html, tmp_path / "new.png", meta=new) is None
    from PIL import Image
    with Image.open(tmp_path / "new.png") as im:
        drawn = im.size[1]
    assert new["render_attempts"] == 1 and new["clipped"] is False
    assert drawn == 6824, "the table's full drawn height, measured"
    assert old["render_attempts"] >= 2, "the fixed 5,000 px window did not hold it"


PSYCHOMETRIC = "10.1186--s40337-024-00968-3"


def test_a_publisher_that_lists_tab5_before_tab4_still_numbers_them_right():
    """This paper's markup lists `Tab5` fourth and `Tab4` fifth. Numbered by
    position, its Table 5 was labelled "Table 4" -- so `context_for` served the
    reading of one table the sentences that cite the other."""
    doc = D.build(CORPUS / PSYCHOMETRIC)
    article = [t for t in doc["tables"] if t.get("source") != "supplement"]
    assert [t["wrap_id"] for t in article] == ["Tab1", "Tab2", "Tab3", "Tab5", "Tab4"], (
        "the walk order is the publisher's, and it is out of order")
    assert [t["label"] for t in article] == ["Table 1", "Table 2", "Table 3", "Table 5", "Table 4"]
    assert [t["table_num"] for t in article] == [1, 2, 3, 5, 4]
    assert [t["position"] for t in article] == [1, 2, 3, 4, 5]
    assert {t["table_number_from"] for t in article} == {"label"}
    tab5 = next(t for t in article if t["wrap_id"] == "Tab5")
    assert tab5["caption"].startswith("Concurrent validity")
    assert tab5["id"] == "table:4", "the id stays an index into this list, which is what it is"


def test_the_meta_analysis_body_loses_its_bibliography_and_only_that():
    """53% of everything the passes were served on this paper was a list of
    other papers' titles, years, volumes and page ranges."""
    from forensic_metascience_ai_toolkit import numerals as N

    doc = D.build(CORPUS / META)
    ladder, _ = _jats.paper_text_with_source(CORPUS / META)
    assert len(ladder) == 92_333, "the text the ladder returns, before the cut"
    assert doc["source"]["n_chars_article"] == 43_238
    assert doc["references"]["how"] == "appended_heading"
    assert doc["references"]["n_chars"] == 49_095
    assert 0.53 < doc["references"]["share"] < 0.54

    floor = doc["numeral_floor"]
    before = len(N.index(ladder, tables_available=True))
    assert floor["n_reference_numerals_set_aside"] == 1415
    assert before - floor["n_reference_numerals_set_aside"] == 456, (
        "n_total moves by the reference numerals and by nothing else")
    assert floor["reference_numerals_by_class"] == {
        "citation_year": 82, "ordinal": 5, "unclassified": 1328}
    itemized = [p for p in doc["problems"] if "reference list are counted here" in p]
    assert len(itemized) == 1 and "citation_year 82" in itemized[0]


def test_the_cut_bibliography_is_written_beside_the_body(tmp_path):
    doc = D.build(CORPUS / META)
    paths = D.save(doc, tmp_path)
    refs = Path(paths["references"]).read_text(encoding="utf-8")
    assert refs.startswith("\n\n# References") and len(refs) == 49_095
    body = Path(paths["text"]).read_text(encoding="utf-8")
    assert "# References" not in body


NATURE = "10.1038--s41392-026-02904-0"


def test_the_two_empty_supplement_tables_are_not_rendered_or_read(tmp_path):
    from forensic_metascience_ai_toolkit.scaffold import reconstruct as RC

    doc = D.build(CORPUS / NATURE)
    empty = [t for t in doc["tables"] if not t.get("cells")]
    assert len(empty) == 2, "this paper's walk returns two supplement tables with no cells"
    problems: list[str] = []
    for t in empty:
        rec = RC.reconstruct_table(CORPUS / NATURE, t, t["position"], tmp_path / "tables",
                                   model="sonnet", root=None, problems=problems)
        assert rec["status"] == "empty_after_walk" and rec["png"] is None
    assert len(problems) == 2 and all("empty_after_walk" in p for p in problems)
    assert not (tmp_path / "tables").exists()


FRONTIERS = "10.3389--fnins.2022.843105"


def test_the_docx_supplement_that_holds_its_tables_as_pngs_is_inventoried():
    """This paper's supplementary Tables S1 and S2 are pictures inside a .docx.
    The account said the supplement had three tables; it prints more, and some
    of them are pixels."""
    doc = D.build(CORPUS / FRONTIERS)
    imgs = doc["supplement_figures"]
    assert len(imgs) == 9
    assert {i["supplement_file"] for i in imgs} == {
        f"{FRONTIERS}_supplementary_info_2_Table_1.docx"}
    assert [i["index"] for i in imgs] == list(range(1, 10))
    assert {i["order"] for i in imgs} == {"document"}
    assert {i["is_figure_or_table"] for i in imgs} == {"unknown"}, "nothing here opens an image"
    assert any("embedded image" in p for p in doc["problems"])
    # And they are NOT article figures: the seven the article declares stand.
    assert len(doc["figures"]) == 7


def test_the_trial_protocol_is_classified_and_its_prose_is_not_served():
    """194,792 characters of sponsor's procedures, four times the article, and
    about $19.50 of the $50.73 this paper's reading was priced at."""
    doc = D.build(CORPUS / NATURE)
    read = {r["file"].split("_")[-2] + "_" + r["file"].split("_")[-1]: r
            for r in doc["supplements_read"]}
    prot = next(r for r in doc["supplements_read"] if r["role"] == "protocol")
    assert prot["role_basis"] == "title_line" and prot["role_matched"] == "Clinical Study Protocol"
    assert prot["served"] is False and prot["n_chars_served"] == 0
    assert prot["n_chars_available"] == 194_792
    assert prot["file"] not in {sp["file"] for sp in doc["supplement_spans"]}
    other = next(r for r in doc["supplements_read"] if r["role"] != "protocol")
    assert other["served"] is True and other["role"] == "results"
    assert doc["source"]["n_chars"] == 54_913, "the served text, protocol prose excluded"
    assert any("classified `protocol`" in p for p in doc["problems"])
    assert read, "every readable supplement is on the record, served or not"


def test_the_protocols_tables_are_walked_and_counted_either_way():
    without = D.build(CORPUS / NATURE)
    with_it = D.build(CORPUS / NATURE, serve_protocol_text=True)
    assert len(without["tables"]) == len(with_it["tables"]) == 34
    assert with_it["source"]["n_chars"] == 249_804
    assert with_it["source"]["n_chars"] - without["source"]["n_chars"] == 194_792 + len(
        D.SUPPLEMENT_DELIMITER.format(file=next(r["file"] for r in without["supplements_read"]
                                                if r["role"] == "protocol")))


def test_a_withheld_supplements_numerals_are_counted_beside_the_total():
    """`n_total` moves when a supplement's prose is not served, so the number it
    moved by is on the record with the file that carries it."""
    without = D.build(CORPUS / NATURE)
    with_it = D.build(CORPUS / NATURE, serve_protocol_text=True)
    f = without["numeral_floor"]
    protocol = next(r["file"] for r in without["supplements_read"] if not r["served"])
    assert f["withheld_supplement_numerals_by_file"][protocol] == 1110
    assert f["n_withheld_supplement_numerals"] == 1110
    assert with_it["numeral_floor"]["n_total"] - f["n_total"] == 1110
    assert with_it["numeral_floor"]["n_withheld_supplement_numerals"] == 0
    assert any("not served" in p and "1,110" in p for p in without["problems"])
