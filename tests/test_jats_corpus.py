"""
Smoke test over every publisher XML the repository ships.

This is the regression net for publisher-format drift: the unit tests use
hand-written fixtures, so only this notices when a new fetch introduces a
dialect, a namespace or a table shape the parser mishandles. It costs nothing
(pure parsing, no network, no model).
"""

from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit.extraction.jats import extract_xml_text_with_tables

REPO = Path(__file__).resolve().parents[1]
#: Every publisher XML the repository ships: the test fixtures plus the
#: ground-truth papers. The original ~95-paper corpus left the repo on
#: 2026-08-09, and this module skipped on every run from then until
#: 2026-10-16, when it was re-based on the XMLs that are actually here.
ROOTS = [REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on",
         REPO / "tests/fixtures/papers/cerebrolysin_run_2026-08-09",
         REPO / "tests/fixtures/papers/cerebrolysin_run2_datasets_2026-08-09",
         REPO / "eval/ground_truth/papers"]
XMLS = sorted(x for r in ROOTS if r.is_dir() for x in r.glob("*/*.xml"))

# The assertions below are corpus-WIDE (all three publisher dialects present,
# yield does not regress), so a shrunken set silently re-measures a different
# population. That is a FAILURE, not a skip: a skip on a missing corpus is how
# this module stopped running for two months without anyone noticing.
_MIN_CORPUS_XMLS = 74


def test_the_corpus_is_complete():
    assert len(XMLS) >= _MIN_CORPUS_XMLS, (
        f"{len(XMLS)} publisher XMLs found, expected {_MIN_CORPUS_XMLS}")
    stubs = [x for x in XMLS if x.read_bytes()[:40].startswith(b"version https://git-lfs")]
    assert not stubs, f"{len(stubs)} Git LFS pointer stubs: run `git lfs checkout`"


@pytest.fixture(scope="module")
def parsed():
    return {p: extract_xml_text_with_tables(p, max_chars=200_000, tables="full") for p in XMLS}


def test_every_file_parses(parsed):
    broken = {p.parent.name: r["error"] for p, r in parsed.items() if r.get("error")}
    assert not broken


def test_all_three_publisher_dialects_are_recognised(parsed):
    kinds = {r["source_format"] for r in parsed.values()}
    assert kinds == {"jats", "pmc-set", "elsevier-cals"}
    assert "unknown" not in kinds


def test_elsevier_cals_tables_are_not_silently_missed(parsed):
    """
    Elsevier files hold ZERO <table-wrap>; their tables are CALS <tgroup>.
    In the original corpus two of them were the papers with no PDF, so a
    table-wrap-only parser would review those with no tables at all -- a
    coverage hole that reads as a clean paper, which is worse than the crash
    it replaced. The shipped set has one such file, with 5 tables.
    """
    cals = [r for r in parsed.values() if r["source_format"] == "elsevier-cals"]
    assert len(cals) >= 1
    assert all(r["n_tables"] > 0 for r in cals)
    assert sum(r["n_tables"] for r in cals) >= 5


def test_every_grid_is_rectangular(parsed):
    ragged = [
        (p.parent.name, t["label"])
        for p, r in parsed.items()
        for t in r["tables"]
        if not t["image_only"] and len({len(row) for row in t["data"]}) > 1
    ]
    assert not ragged


def test_alignment_uncertain_stays_a_rare_signal(parsed):
    """
    A flag that fires on a third of tables is noise. It fired 160 times when it
    tested for blank cells; testing for rows SHORT IN THE SOURCE brought it to 3.
    """
    flagged = [t for r in parsed.values() for t in r["tables"]
               if t["alignment_uncertain"]]
    assert len(flagged) <= 10


def test_table_and_cell_yield_does_not_regress(parsed):
    total = sum(r["n_tables"] for r in parsed.values())
    cells = sum(len(t["cells"]) for r in parsed.values() for t in r["tables"])
    # Measured 2026-10-16 on the 74 shipped XMLs: 163 tables, 9,118 cells.
    assert total >= 163
    assert cells >= 9_100


def test_image_only_tables_are_identified_and_carry_no_cells(parsed):
    image_only = [t for r in parsed.values() for t in r["tables"] if t["image_only"]]
    assert len(image_only) == 34      # measured 2026-10-16 on the 74 shipped XMLs
    assert all(t["data"] == [] and t["cells"] == [] for t in image_only)


def test_table_placeholders_carry_no_cell_data(parsed):
    """
    One representation of a table, and it is the grid.

    The assertion is on OUR placeholder lines, not on the text as a whole:
    authors legitimately repeat a table value in prose ("...age (F = 2.84;
    p = .04)..."), so finding a cell string anywhere in the body proves
    nothing. What must never happen is our renderer pouring cells into the
    text — which it did until `<table-wrap>` nested inside `<p>` was excluded
    from paragraph flattening.
    """
    for path, result in parsed.items():
        by_label = {
            (t["label"] or f"Table {t['table_num']}"): t
            for t in result["tables"]
        }
        for line in result["text"].splitlines():
            if not (line.startswith("[") and "; see tables]" in line):
                continue
            label = line[1:].split(":", 1)[0]
            table = by_label.get(label)
            if table is None or table["image_only"]:
                continue
            # A spanning header can repeat the caption itself ("Transcription
            # notation" in 10.3389--fpsyg.2019.03052), and the caption belongs
            # in the placeholder; only cell text that is NOT the caption counts.
            caption = (table.get("caption") or "").lower()
            for row in table["rows"]:
                for cell in row[1:]:
                    if cell.lower().rstrip(".") in caption:
                        continue
                    if len(cell) > 12 and cell in line:
                        pytest.fail(
                            f"{path.parent.name}: placeholder for {label} "
                            f"carries cell data {cell!r}"
                        )
