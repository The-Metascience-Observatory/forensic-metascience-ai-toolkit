"""Table cells and prose numerals are ONE floor, split beside every total.

Greg, 2026-09-06: "table values and prose values should be combined floors,
but whenever you give the total give the breakdown by source."

WHY THIS NEEDED A RULING. Whether a table's numbers were in the floor at all
was an ACCIDENT OF THE CONVERTER: docling inlines tables as pipe rows, so its
cells were counted; publisher XML and HTML keep tables in their own elements,
so on the 99 XML-sourced corpus papers every article table cell was in NO
denominator. Measured on the 12-paper working corpus before this change:
`table_cell: 0` of 3,218 numerals.

THE TWO HALVES OF THE RULING, each pinned here: (1) one `n_total` spanning
prose and cells, keyed on ONE span rule so an inlined table is never counted
twice; (2) `by_source`, keyed `<source>_<prose|table>`, carried by every
printer of that total -- the tally, the corpus snapshot and its diff, the
register view, and the scaffold account.
"""
from __future__ import annotations

import pathlib

import pytest

from forensic_metascience_ai_toolkit import corpus_state as CS
from forensic_metascience_ai_toolkit import numerals as N
from forensic_metascience_ai_toolkit import values as V

CORPUS = pathlib.Path(__file__).resolve().parents[1] / "tests/fixtures/papers/high_value_pdfs_to_run_on"
AJCP = CORPUS / "10.1002--ajcp.70049"          # XML-sourced: no table is inlined


class TestOneChannelRule:
    def test_the_key_names_source_and_channel(self):
        assert N.source_key({"source": "article", "class": "statistic"}) == "article_prose"
        assert N.source_key({"source": "article", "class": "table_cell"}) == "article_table"
        assert N.source_key({"source": "supplement", "class": "table_cell"}) == "supplement_table"
        assert N.source_key({"class": "unclassified"}) == "article_prose", "source defaults to article"

    def test_a_docling_inlined_cell_is_the_table_channel_too(self):
        # The converter inlined the table, so `index` classes the token
        # `table_cell`; the split must call that a table numeral, exactly as it
        # calls a directly enumerated cell one. Same paper, same split, either
        # converter.
        text = "Results.\n\n| group | mean |\n| A | 41.87 |\n\nThe mean was 41.87."
        rows = N.index(text, tables_available=True)
        keys = {N.source_key(r) for r in rows}
        assert "article_table" in keys and "article_prose" in keys, keys


class TestOneSpanRule:
    def test_an_inlined_table_is_found_and_a_non_inlined_one_is_not(self):
        cells = [{"raw": "group"}, {"raw": "41.87"}]
        inlined = "| group | mean |\n| A | 41.87 |\n"
        assert N.table_span(inlined, cells) is not None
        assert N.table_span("The mean was 41.87 in group A.", cells) is None

    def test_the_scaffold_delegates_rather_than_keeping_a_copy(self):
        from forensic_metascience_ai_toolkit.scaffold import document as D
        import inspect
        src = inspect.getsource(D._table_span)
        assert "_numerals.table_span" in src and "finditer" not in src, (
            "two span rules would drift; the scaffold must call numerals.table_span")


class TestTheTallyCarriesTheSplit:
    def test_one_total_and_the_split_sums_to_it(self):
        body = N.index("Two values: 41.87 and 3.07.")
        cells = N.index_table_cells([{"cells": [{"raw": "12"}, {"raw": "0.5"}]}], "Table 1", "article")
        t = N.tally(body + cells)
        assert t["n_total"] == len(body) + len(cells)
        assert sum(b["n_total"] for b in t["by_source"].values()) == t["n_total"]
        assert set(t["by_source"]) == {"article_prose", "article_table"}


class TestTheCorpusSnapshotSeesIt:
    def _reg(self):
        return {"groups": [], "n_values": 0, "problems": [],
                "numerals": {"n_total": 5, "n_judged": 2,
                             "by_class": {"statistic": 2, "unclassified": 1, "table_cell": 2},
                             "by_source": {"article_prose": {"n_total": 3, "n_judged": 0},
                                           "article_table": {"n_total": 2, "n_judged": 2}}}}

    def test_the_split_is_in_the_snapshot_and_sums_to_the_total(self):
        s = CS.snapshot_register(self._reg())
        assert s["numerals_by_source"] == {"article_prose": 3, "article_table": 2}
        assert sum(s["numerals_by_source"].values()) == s["n_numerals_total"]

    def test_the_diff_names_each_source_so_a_floor_change_is_legible(self):
        before = {"totals": {"n_numerals_total": 3, "numerals_by_source": {"article_prose": 3}}}
        after = {"totals": {"n_numerals_total": 5,
                            "numerals_by_source": {"article_prose": 3, "article_table": 2}}}
        d = CS.diff(before, after)
        assert d["n_numerals_total"]["change"] == 2
        assert d["numsrc:article_prose"]["change"] == 0, "the prose floor did not move"
        assert d["numsrc:article_table"]["before"] is None and d["numsrc:article_table"]["after"] == 2, (
            "a source that joined the floor is NAMED, not folded into the total")


class TestSupplementProseIsServedAndCounted:
    """A supplement's RUNNING PROSE joins the text the passes read and the one
    floor, under a heading naming its file.

    Greg, 2026-09-06: "the supplements/repos aren't 'second-class citizens' in
    the context of the analysis. They are as important as the main text, and
    should be presented to the models in this fashion." Before this the walker
    carried a supplement's TABLES and threw away the `text` the same reader had
    just returned, so a supplement's paragraphs were served to no pass and sat
    in no denominator -- and `10.1111--jcpp.13879`'s supplement carries 47
    distinct p values and no table at all.
    """

    def _paper(self, tmp_path):
        docx = pytest.importorskip("docx")
        (tmp_path / "paper.xml").write_text(
            '<?xml version="1.0"?>\n<article><front><article-meta>'
            '<title-group><article-title>A paper</article-title></title-group>'
            '</article-meta></front><body><sec><title>Results</title>'
            '<p>The mean was 4.17 in the treated group.</p></sec></body></article>',
            encoding="utf-8")
        d = docx.Document()
        d.add_paragraph("Supplementary analyses. The adjusted estimate was 0.031 in the same sample.")
        d.save(str(tmp_path / "paper_supplementary_info_1_s001.docx"))
        # Declared, not guessed: `classify_inputs` takes the operator's word and
        # never a filename (`supplements.read_declaration`).
        (tmp_path / "inputs.json").write_text(
            '{"article": "paper.xml", "supplements": ["paper_supplementary_info_1_s001.docx"]}',
            encoding="utf-8")
        return tmp_path

    def test_the_supplement_is_served_under_a_heading_naming_its_file(self, tmp_path):
        from forensic_metascience_ai_toolkit.scaffold import document as D
        doc = D.build(self._paper(tmp_path))
        assert "## SUPPLEMENT: paper_supplementary_info_1_s001.docx" in doc["text"]
        assert "The adjusted estimate was 0.031 in the same sample." in doc["text"]
        span = doc["supplement_spans"][0]
        assert doc["text"][span["start"]:span["end"]].startswith("Supplementary analyses.")
        assert doc["source"]["n_chars_article"] == span["heading_start"]
        # A HEADING, because `sections.map_sections` reads nothing else -- and
        # the section's role has to be `supplement` rather than inherited, or
        # `bind` and `linear.chunks` drop it as back matter.
        secs = [s for s in doc["sections"] if s["role"] == "supplement"]
        assert secs and secs[0]["name"] == "supplement: paper_supplementary_info_1_s001.docx"

    def test_the_supplements_numerals_are_a_bucket_of_the_one_floor(self, tmp_path):
        from forensic_metascience_ai_toolkit.scaffold import document as D
        doc = D.build(self._paper(tmp_path))
        by = doc["numeral_floor"]["by_source"]
        assert by["supplement_prose"]["n_total"] == 1
        assert sum(b["n_total"] for b in by.values()) == doc["numeral_floor"]["n_total"]
        assert doc["numeral_floor"]["n_supplement_pipe_rows_set_aside"] == 0, (
            "this supplement has no tables, so nothing is counted from its cells instead")
        row = next(r for r in doc["numerals"] if r["printed"] == "0.031")
        assert row["source"] == "supplement" and row["role"] == "supplement"
        assert row["file"] == "paper_supplementary_info_1_s001.docx"
        # The id is the offset into the SERVED text, which is what
        # `linear.chunks` slices by -- so a supplement row must index the joined
        # string, not the part it was found in.
        assert row["id"] == f"num:{row['offset']}"
        assert doc["text"][row["offset"]:row["end"]] == "0.031"

    def test_the_articles_own_rows_do_not_move(self, tmp_path):
        from forensic_metascience_ai_toolkit.scaffold import document as D
        paper = self._paper(tmp_path)
        on, off = D.build(paper), D.build(paper, serve_supplement_text=False)
        keep = ("id", "offset", "end", "class", "printed", "role")
        art = lambda d: [{k: r[k] for k in keep} for r in d["numerals"] if r.get("source") == "article"]
        assert art(on) == art(off), "appending a supplement must not repoint an article offset"
        assert off["text"] == on["text"][:off["source"]["n_chars"]]
        assert off["supplement_spans"] == [] and "SUPPLEMENT:" not in off["text"]
        assert off["numeral_floor"]["by_source"].keys() == {"article_prose"}
        assert any("--no-supplement-text" in p for p in off["problems"]), (
            "an absence has to be stated, not left to be rediscovered")


@pytest.mark.skipif(not (AJCP / "10.1002--ajcp.70049.xml").exists() and not any(AJCP.glob("*.xml")),
                    reason="working-corpus paper not on disk")
class TestTheRegisterFloorOnAnXmlPaper:
    def test_article_table_cells_join_the_register_floor(self):
        reg = V.build_from_paper(AJCP)
        nu = reg["numerals"]
        assert nu["n_offbody_tables"] > 0, "an XML paper inlines no table"
        bs = nu["by_source"]
        assert bs["article_table"]["n_total"] > 0
        assert bs["article_prose"]["n_total"] > 0
        assert sum(b["n_total"] for b in bs.values()) == nu["n_total"]
        cells = [r for r in nu["rows"] if r.get("class") == "table_cell"]
        assert cells and all(r.get("offset") is None and r.get("section") == "table" for r in cells), (
            "a cell has no body offset and is stamped as a table, never as front matter")
