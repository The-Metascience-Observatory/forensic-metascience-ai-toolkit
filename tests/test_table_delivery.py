"""Tables were extracted perfectly and delivered by luck.

The XML path returns both of Romano's tables with labels, captions, footnotes,
correctly flattened multi-row headers and a clean cell grid. Nothing was wrong
with the extraction. What failed was the channel: `extract_xml` returned a
184 kB payload, the harness caps tool results, and on a real billed run it
spilled to a file --

    Error: result (160,395 characters across 2,656 lines) exceeds maximum
    allowed tokens. Output has been saved to .../tool-results/...

-- after which the model recovered roughly 40% of it with six blind `Read`
calls at guessed line offsets. Nine of twenty-eight run logs in the working
corpus contain such a spill.

So `extract_xml` now returns an INDEX and `get_table` fetches one table at a
time, carrying the two things that were being lost at the boundary into the
checking tools: the LABEL, so a finding can name its table, and the FOOTNOTES,
which decide whether "142 (71.0)" is `n (%)` or `mean (SD)`.
"""
import json
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit.extraction.jats import (
    extract_xml_text_with_tables,
    get_table,
    table_index_entry,
)

XML = Path("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--eat.24415/10.1002--eat.24415.xml")
pytestmark = pytest.mark.skipif(not XML.exists(), reason="corpus XML not present")

#: The harness cap that started this. Well under it is the whole point.
_SPILL_THRESHOLD = 160_000



#: Every publisher XML the repository ships (the same set as test_jats_corpus).
#: These corpus-wide checks were gated on a 20-XML corpus that left the repo on
#: 2026-08-09 and skipped on every run until 2026-10-16.
_CORPUS_ROOTS = ["tests/fixtures/papers/high_value_pdfs_to_run_on",
                 "tests/fixtures/papers/cerebrolysin_run_2026-08-09",
                 "tests/fixtures/papers/cerebrolysin_run2_datasets_2026-08-09",
                 "eval/ground_truth/papers"]


def _corpus_paper_dirs():
    repo = Path(__file__).resolve().parents[1]
    return [d for r in _CORPUS_ROOTS if (repo / r).is_dir()
            for d in sorted((repo / r).iterdir()) if d.is_dir()]

class TestThePayloadFits:
    def test_the_index_is_far_under_the_cap(self):
        size = len(json.dumps(extract_xml_text_with_tables(XML)))
        assert size < _SPILL_THRESHOLD / 2, f"{size:,} chars"

    def test_it_is_much_smaller_than_returning_every_grid(self):
        idx = len(json.dumps(extract_xml_text_with_tables(XML)))
        full = len(json.dumps(extract_xml_text_with_tables(XML, tables="full")))
        assert idx < full * 0.4, f"index {idx:,} vs full {full:,}"

    def test_one_table_also_fits(self):
        """60x7 with per-cell row and column labels is the big one."""
        assert len(json.dumps(get_table(XML, 2))) < _SPILL_THRESHOLD

    def test_section_text_is_not_duplicated(self):
        """`text` is the join of the per-section texts, so carrying both
        doubled the payload -- 45 kB on this paper, more than the tables."""
        out = extract_xml_text_with_tables(XML)
        assert out["text"]
        assert all("text" not in p for p in out["pages"])


class TestTheIndexSaysWhatEachTableIs:
    def _index(self):
        return extract_xml_text_with_tables(XML)["tables"]

    def test_both_tables_are_listed(self):
        assert len(self._index()) == 2

    def test_each_entry_carries_its_identity(self):
        for t in self._index():
            assert t["label"] and t["caption"]
            assert t["n_rows"] and t["width"]

    def test_it_carries_no_cells(self):
        """That is the point -- the cells are what did not fit."""
        for t in self._index():
            assert "cells" not in t and "data" not in t

    def test_it_says_how_to_get_them(self):
        out = extract_xml_text_with_tables(XML)
        assert "get_table" in (out["how_to_get_a_table"] or "")
        assert out["tables_mode"] == "index"


class TestGetTableCarriesWhatTheCheckersNeed:
    def test_it_returns_the_cells(self):
        """`cells` is windowed and says so; `data` is not."""
        g = get_table(XML, 2)
        assert g["found"]
        assert g["cells_total"] == 288
        assert 0 < len(g["cells"]) <= 288
        assert g["cells_row_window"][0] == 1

    def test_the_grid_is_complete_on_the_first_call(self):
        """THE PROPERTY THAT MATTERS. Every number the paper printed is in
        `data` without the caller following any pointer -- a model that reads
        one result and stops still has the whole table."""
        g = get_table(XML, 2)
        assert g["data_is_complete"] is True
        assert len(g["data"]) == g["rows_total"] == 61

    def test_every_cell_is_reachable_by_following_the_pointer(self):
        """A window is only honest if the rest can actually be fetched."""
        seen, lo, calls = 0, 1, 0
        while True:
            g = get_table(XML, 2, first_row=lo)
            seen += len(g["cells"])
            calls += 1
            if not g.get("how_to_get_more") or calls > 20:
                break
            lo = g["cells_row_window"][1] + 1
        assert seen == 288, "the pointer must reach every cell"

    def test_a_small_table_is_not_windowed_at_all(self):
        g = get_table(XML, 1)
        assert "how_to_get_more" not in g
        assert len(g["cells"]) == g["cells_total"]

    def test_paging_cells_states_its_COST_while_staying_weaker_than_a_lost_grid(self):
        """REWRITTEN 2026-08-12, because the archive falsified the old premise.

        This test used to REQUIRE the phrase "nothing is missing", reasoning
        that alarm here would train a reader to ignore the message that
        matters. The opposite happened. MEASURED over 51 archived get_table
        calls: `cells` delivered 2,269 of 3,714 cells (61%); 10 of 33 tables
        came back short; and in 9 of those 10 the model made exactly ONE call,
        received this note naming the exact continuation, and never made it.
        The reassurance was the sentence being acted on.

        The distinction the old test protected is real and is still pinned
        below -- a truncated GRID is graver than a windowed cell list, and only
        the grid case says printed numbers are absent from the result. But the
        weaker case must still name what skipping it costs, because "page only
        if you are feeding check_table" describes the one thing `cells` is for.
        """
        note = get_table(XML, 2)["how_to_get_more"]
        assert "nothing is missing" not in note
        assert "silently skip" in note, "the cost of not paging must be stated"
        assert "get_table" in note, "the next call must be named"
        # Still strictly weaker than a truncated grid: no claim that printed
        # numbers are absent from this result, because they are not.
        assert "THE GRID IS TRUNCATED" not in note
        assert "IS complete" in note

    def test_a_truncated_grid_says_so_in_the_strongest_terms(self):
        """The other case, where the caller really is missing a number."""
        import forensic_metascience_ai_toolkit.extraction.jats as J

        original = J._TABLE_CHAR_BUDGET
        try:
            J._TABLE_CHAR_BUDGET = 3000          # force the rare path
            g = get_table(XML, 2)
        finally:
            J._TABLE_CHAR_BUDGET = original
        assert g["data_is_complete"] is False
        assert "THE GRID IS TRUNCATED" in g["how_to_get_more"]
        assert "NOT in this result" in g["how_to_get_more"]

    def test_it_returns_the_label_so_a_finding_can_cite_it(self):
        """Once cells entered check_table the table's identity was gone, and a
        finding could only say "a table"."""
        assert get_table(XML, 2)["label"] == "TABLE 2"

    def test_it_returns_the_footnotes(self):
        """These decide whether a cell is n(%) or mean(SD). Getting that wrong
        inverts every granularity check downstream."""
        assert len(get_table(XML, 2)["footnotes"]) == 2

    def test_the_multi_row_header_is_still_flattened(self):
        h = get_table(XML, 2)["headers"]
        assert any("Within" in str(x) and "b (SE)" in str(x) for x in h)

    def test_rows_is_not_duplicated_against_data(self):
        """`rows` was `data[1:]` -- 11 kB of pure duplication on this table."""
        g = get_table(XML, 2)
        assert "data" in g and "rows" not in g

    def test_a_missing_table_lists_the_ones_that_exist(self):
        m = get_table(XML, 99)
        assert m["found"] is False
        assert "2 table(s)" in m["error"]
        assert len(m["available"]) == 2

    def test_an_unparseable_file_does_not_raise(self, tmp_path):
        bad = tmp_path / "bad.xml"
        bad.write_text("<not-xml")
        r = get_table(bad, 1)
        assert r["found"] is False and "error" in r


class TestFullModeStillWorks:
    """The Python API and the CLI have no size cap to cross."""

    def test_full_returns_the_grids(self):
        out = extract_xml_text_with_tables(XML, tables="full")
        assert out["tables_mode"] == "full"
        assert all(t.get("cells") for t in out["tables"])

    def test_the_index_entry_helper_drops_the_cells(self):
        full = extract_xml_text_with_tables(XML, tables="full")["tables"][0]
        entry = table_index_entry(full)
        assert entry["label"] == full["label"]
        assert "cells" not in entry


class TestNoTableCanSpill:
    """The whole point of `get_table`, restated as a property.

    The A2 commit claimed one table at a time "cannot spill". A paid validation
    run on this very paper disproved it: 69,971 characters, refused by the
    harness. The claim is only true if it is enforced, so it is measured here
    over every table in the corpus rather than asserted in a docstring.
    """

    #: Below the 69,971 that was refused, with room for the token/character
    #: ratio of a table of numbers being worse than prose.
    CEILING = 40_000

    def test_no_corpus_table_exceeds_the_ceiling(self):
        import json as _json

        from forensic_metascience_ai_toolkit.extraction.jats import (
            extract_xml_text_with_tables as _index,
        )
        from forensic_metascience_ai_toolkit.extraction.jats import find_xml as _find

        # Completeness is pinned by test_jats_corpus.test_the_corpus_is_complete;
        # the `n` floor below fails if the set shrinks.
        worst, n = 0, 0
        for d in _corpus_paper_dirs():
            xml = _find(d)
            if xml is None:
                continue
            try:
                idx = _index(str(xml))
            except Exception:
                continue
            for entry in idx.get("tables") or []:
                try:
                    size = len(_json.dumps(get_table(str(xml), entry["table_num"])))
                except Exception:
                    continue
                n += 1
                worst = max(worst, size)
        assert n >= 160, "this test is pointless without the corpus"  # 163 on 2026-10-16
        assert worst <= self.CEILING, (
            f"largest table payload is {worst:,} characters over {n} tables"
        )

    def test_repeated_warnings_are_collapsed(self):
        """235 copies of one fact is not 235 facts. That table's warnings were
        36,445 characters -- three times the size of the grid they described."""
        from forensic_metascience_ai_toolkit.extraction.jats import _collapse_warnings

        got = _collapse_warnings([f"ragged row ['r{i}', '']: labels may shift"
                                  for i in range(235)])
        assert len(got) == 1
        assert got[0].startswith("235x ")

    def test_a_lone_warning_is_left_exactly_as_written(self):
        from forensic_metascience_ai_toolkit.extraction.jats import _collapse_warnings

        assert _collapse_warnings(["table is an image"]) == ["table is an image"]


class TestEveryTableArrivesWhole:
    """The user's requirement, as a property over the whole corpus.

    Two separate guarantees, measured rather than asserted:

    1. THE GRID IS COMPLETE ON THE FIRST CALL for every table. This is the one
       that matters -- `data` carries every number the paper printed, so a
       caller that reads one result and stops is not missing anything. It is
       affordable because the grid is small: median 2,018 characters across the
       corpus, and the largest is 30,393.
    2. EVERY CELL IS RECOVERABLE by following `how_to_get_more`, and no hop
       exceeds the payload ceiling.

    When the two conflict -- one 236x13 table -- everything else yields to the
    grid: `spans` is shed first, then `cells` is squeezed. Shedding spans is
    exactly what takes this from 474 of 475 to 475 of 475.
    """

    CEILING = 40_000

    def _tables(self):
        from forensic_metascience_ai_toolkit.extraction.jats import (
            extract_xml_text_with_tables as index,
        )
        from forensic_metascience_ai_toolkit.extraction.jats import find_xml
        for d in _corpus_paper_dirs():
            xml = find_xml(d)
            if xml is None:
                continue
            try:
                idx = index(str(xml))
            except Exception:
                continue
            for entry in idx.get("tables") or []:
                yield str(xml), entry["table_num"], d.name

    def test_every_grid_is_complete_on_the_first_call(self):
        partial, n = [], 0
        for xml, num, name in self._tables():
            try:
                g = get_table(xml, num)
            except Exception:
                continue
            n += 1
            if not g["data_is_complete"] or len(g["data"]) != g["rows_total"]:
                partial.append(f"{name} t{num}")
        assert n >= 160, "this test is pointless without the corpus"  # 163 on 2026-10-16
        assert not partial, f"{len(partial)} of {n} grids truncated: {partial[:5]}"

    def test_every_cell_is_recoverable_and_no_hop_can_spill(self):
        bad, worst = [], 0
        for xml, num, name in self._tables():
            lo, seen, calls = 1, 0, 0
            while calls < 300:
                try:
                    g = get_table(xml, num, first_row=lo)
                except Exception:
                    break
                worst = max(worst, len(json.dumps(g)))
                seen += len(g["cells"])
                calls += 1
                if not g.get("how_to_get_more"):
                    break
                nxt = g["cells_row_window"][1] + 1
                if nxt <= lo:                       # would loop forever
                    bad.append(f"{name} t{num} STALLED at row {lo}")
                    break
                lo = nxt
            else:
                bad.append(f"{name} t{num} needed over 300 calls")
            if g.get("cells_total") and seen != g["cells_total"]:
                bad.append(f"{name} t{num}: {seen} of {g['cells_total']} cells")
        assert not bad, bad[:5]
        assert worst <= self.CEILING, f"largest hop was {worst:,} characters"
