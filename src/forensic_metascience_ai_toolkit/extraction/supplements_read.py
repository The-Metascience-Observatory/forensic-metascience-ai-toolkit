"""
Supplementary-material readers (.docx, .xlsx/.xls, .csv).

Supplementary files are where a paper's unchecked numbers hide: 50 .docx and 6
.xlsx sit in the working corpus and no code path could open any of them. A
spreadsheet of PARTICIPANT-LEVEL data is worth more than a summary table,
because it supports checks the paper's own tables cannot.

Output matches :mod:`forensic_metascience_ai_toolkit.extraction.jats` table-for-table — the
same `data` grid and the same ready-to-type `cells` — so the downstream chain
(`parse_cells_typed` -> `check_table`) is identical regardless of where a table
came from.

Formats we cannot read REFUSE rather than return nothing: legacy binary `.doc`
has no text we can extract, and reporting it as empty would let a review read as
though the supplement had been checked.

WHAT A "SUPPLEMENT" ARRIVES AS, MEASURED on the corpora in this repo: 357 PDF,
121 JPG, 21 PNG, 15 XML, 7 TXT, 7 HTML, 3 DOCX, 1 XLSX. The reader handled the
DOCX and the XLSX. **The 357 PDFs -- by far the commonest supplement there is --
fell through to "unsupported supplement format '.pdf'"**, and the 142 images
were refused with "there is no OCR in this pipeline". So the two formats that
account for 95% of supplementary material were the two that could not be read,
and a paper whose eTables live in a supplementary PDF was reviewed as though it
had none.

Every format now routes to the reader that already exists for it and comes back
in the SAME table shape, so `parse_cells_typed` -> `check_table` is identical
whatever the file was:

    .pdf            extraction.pdf (text layer) -> OCR seam for image-only pages
    .html/.xhtml    extraction.html (the publisher-HTML table builder)
    .epub           a zip of XHTML; the same table builder, per document
    .xml            extraction.jats
    .txt/.md        text only, and says so -- no table structure to recover
    images          the OCR seam
    .docx/.xlsx/.csv  as before

The OCR seam (`extraction.ocr`) is a seam and not an engine: no OCR engine is
installed here, so image tables come back as a REFUSAL that names the missing
engine rather than as an empty table. `ocr_unavailable` is a distinct key for
that reason -- "we have no OCR" and "this file has no tables" are opposite facts
and a caller that cannot tell them apart writes the second into a review.
"""

from __future__ import annotations

import csv
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from ..atomicio import scratch_sibling as _scratch_sibling
from .jats import _cells_from_grid, _flatten_header
from .jats import header_adjuncts as _jats_header_adjuncts

#: Same test `jats._build_table` uses to decide whether a short row is a
#: benign section label or a row of measurements under the wrong headings.
_HAS_DIGIT = re.compile(r"\d")

#: Placeholder for a column the supplement never labelled -- either because its
#: header cell is blank or because the header row ran short and the grid was
#: PADDED into shape below. `jats` can use `col{i}` because a JATS grid is
#: rectangular by construction and the position IS the column identity; here
#: neither is guaranteed, so `col3` would report a heading the file does not
#: contain. Parallel to the `(unlabelled row)` this codebase already uses.
#:
#: MEASURED over the 56 readable supplement files of the working corpus (283
#: tables, 29,479 cells): 12,292 cells sat under a column reported as unnamed.
#:
#: THAT FIGURE CONFLATED TWO CAUSES, and re-measuring 2026-08-20 separated
#: them. A blank header cell is the FILE's property and this placeholder is the
#: honest answer for it. A stacked header is OURS: the file named the column
#: perfectly well, one row further down, and `_finish` was reading only the
#: first row -- so our own defect was being recorded as a fact about the
#: supplement, which is the absence-as-knowledge failure this codebase exists
#: to avoid.
#:
#: RE-MEASURED on the 8 .docx supplements of the eleven-paper corpus, A/B on
#: the same grids: with `header_rows=1`, 599 of 666 cells (89.9%) sat under an
#: unnamed column; with the depth proven from span markup, 0 of 614. Every one
#: of the 599 was ours. (The cell count falls because 52 cells were header rows
#: being read as data.)
#:
#: THE PLACEHOLDER STILL EARNS ITS PLACE, and the scope of the fix is narrow:
#: the propagation above runs only where a reader hands `_finish` its span
#: markup, which today is `.docx` alone.
#:
#: CORRECTION 2026-08-20: an earlier version of this note said the PDF path
#: "reads a pdfplumber grid". IT DOES NOT. `extract_pdf_tables` routes through
#: `extraction.pdf.extract_text_with_tables`, which is docling-only and
#: cache-only (Greg, 2026-08-16: pdfplumber "should never run *anywhere*").
#: pdfplumber survives in exactly one place, `panels.py`, where it reads
#: embedded image BYTE STREAMS and decodes nothing.
#:
#: THE DOUBLE `_finish` IS CORRECT. DO NOT "FIX" IT. `docling_tables._grid_of`
#: reads header depth from docling's `column_header` flags and passes it to
#: `_finish`; `extraction/pdf.py` then reshapes each table down to
#: `{table_num, data, strategy, label, page}`, dropping `n_header_rows`, and
#: `extract_pdf_tables` below calls `_finish` a SECOND time taking the one-row
#: default.
#:
#: I recorded that on 2026-08-20 as a latent bug that "would silently discard
#: docling's answer", and proposed forwarding the field. BOTH HALVES WERE
#: WRONG, and measuring on 2026-08-21 showed why.
#:
#: Nothing is discarded. `_finish` returns `data` as `[flattened_header] +
#: body`, so docling's composite labels are ALREADY row 0 of the grid handed
#: over, and the second `_finish` adopts them as its header. Measured on
#: `...51752` supplementary_info_1, 21 tables, 7 of them two rows deep:
#: composite labels 33 -> 33, cells 727 -> 727. Only the `n_header_rows` FIELD
#: resets to 1, and for an already-flattened grid that is the true depth.
#:
#: Forwarding the field would DESTROY DATA. Passing docling's depth of 2 makes
#: this `_finish` consume two rows of an already-flattened grid as header:
#: measured, body rows 31 -> 30, one real measurement row eaten per affected
#: table, silently. The one cost of the current arrangement is that
#: `n_header_rows` shown by `cli` understates the ORIGINAL table's depth; the
#: labels a reader and every check actually use are correct.
_UNLABELLED_COL = "(unlabelled column {i})"

#: Extensions this module can actually open.
#:
#: `.xls` is deliberately NOT here. It was, and it dispatched to openpyxl,
#: which cannot read the legacy binary format at all -- so a real spreadsheet
#: came back as a generic "could not read" rather than the named, actionable
#: refusal every other unsupported format gets. Same situation as `.doc`, and
#: it belongs in the same list.
#: Raster formats. Routed to the OCR seam, NOT listed as unreadable: whether
#: they can be read is a property of the machine (is an engine installed?), not
#: of the file, and the two answers must not arrive in the same shape.
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".gif"}

READABLE = ({".docx", ".xlsx", ".xlsm", ".csv", ".tsv", ".pdf", ".html", ".htm",
             ".xhtml", ".epub", ".xml", ".txt", ".md"} | IMAGE_SUFFIXES)

#: Present-but-unreadable, with the reason the model should record.
UNREADABLE = {
    ".doc": "legacy binary Word format (only .docx is readable)",
    ".xls": ("legacy binary Excel format; openpyxl reads only .xlsx/.xlsm. "
             "Re-saving it as .xlsx would make it analysable"),
    ".zip": "archive; unpack it before analysing",
    ".tex": "LaTeX source; not a data table",
}


#: Said once, because two paths reach the same conclusion: the depth walker
#: proving row 0 is data, and the post-flatten check on a header that reads as
#: measurements. A second hand-spelled copy is how two ends of a boundary drift.
_NO_HEADER_IN_THE_SOURCE = (
    "the first row reads as measurements, not labels, so this table "
    "has no header in the source -- most often a long table "
    "continued onto a second element without repeating its header. "
    "The row is kept as data and the columns are reported unlabelled "
    "rather than named after it."
)


def _propagated_header(source_rows: list[list[tuple[str, int, int, bool]]],
                       upto: int, width: int) -> list[list[str]]:
    """Header rows repeat a spanning label across every column it covers.

    `jats._expand` states the policy and calls it a correctness guard: header
    rows and column 0 repeat their text across every covered cell, and every
    other body cell is anchor-only. The .docx reader implemented only the body
    half -- it blanks a merge's continuations so one measurement is not counted
    several times, which is right, and then flattened the header from those
    same blanked rows, which is not.

    What that cost on `EAT-58-1072-s001.docx` Table S.4:

        row 1  '' | Within-Person |  |  | Between-Person |  |
        row 2  '' | b (SE) | p | beta | b (SE) | p | beta

    Only the columns holding a span's ANCHOR kept the group, so the labels came
    out `Within-Person | b (SE)`, `p`, `beta`, `Between-Person | b (SE)`, `p`,
    `beta` -- two columns named `p`, two named `beta`, and nothing to tell them
    apart. `_header_depth` describes exactly this as the accusation risk: a
    value taken from one and an n from another are indistinguishable
    afterwards, and a check on that pair calls an honest paper impossible.

    Body rows are NOT passed here and must never be: repeating a spanned value
    is how one `3.7 (0.30)` becomes four identical pairs and
    `detect_duplication` manufactures a finding.
    """
    out: list[list[str]] = []
    for row in source_rows[:upto]:
        cells: list[str] = []
        for cell in row:
            text, colspan = cell[0], max(1, cell[1])
            cells.extend([text] * colspan)
        cells = cells[:width]
        cells.extend([""] * (width - len(cells)))
        out.append([" ".join(("" if c is None else str(c)).split())
                    for c in cells])
    return out


def _spans_out(source_rows: list[list[tuple[str, int, int, bool]]] | None
               ) -> list[dict]:
    """Report the merges the source actually declared, or nothing.

    This field was hard-coded to `[]` on every path through `_finish`, which
    reads as "this table declares no merged cells" -- a positive claim, made
    without looking, about tables that frequently do. Empty stays the honest
    answer for a reader with no span structure to offer (.csv has none); it
    stops being the answer for one that does.
    """
    if not source_rows:
        return []
    out = []
    for r, row in enumerate(source_rows):
        c = 0
        for cell in row:
            text, colspan, rowspan = cell[0], cell[1], cell[2]
            if colspan > 1 or rowspan > 1:
                out.append({"row": r, "col": c, "text": text,
                            "colspan": colspan, "rowspan": rowspan})
            c += max(1, colspan)
    return out


def _finish(
    grid: list[list[str]],
    table_num: int,
    label: str,
    caption: str,
    section: str,
    source: str,
    warnings: list[str] | None = None,
    provenance: str | None = None,
    page: int | None = None,
    header_rows: int | None = None,
    source_rows: list[list[tuple[str, int, int, bool]]] | None = None,
) -> dict:
    """Wrap a raw grid in the same table dict shape `jats.py` produces.

    `provenance` stamps every cell AND the table. It is `None` for every reader
    that works off a text layer -- those cells are `printed_table` by default and
    the callers already assume it -- and `ocr_table` for anything transcribed
    from an image. The stamp has to ride on the CELL, not only on the table,
    because `check_table` receives a flat cell list and would otherwise have no
    way to know which of its cells were read by a machine.

    `header_rows` DEFAULTS TO 1 AND MUST BE PROVEN TO BE MORE. It was hard-coded
    at 1, which is right for the .docx/.csv/.xlsx readers whose sources have no
    span structure to read. It is wrong for any grid whose first row spans
    columns: there the row below carries the only labels the columns have, and
    taking one row files those labels as DATA. `jats._header_depth` is the proof
    -- see its docstring for what the one-row reading costs, measured.
    """
    # Collapse internal whitespace: a merged docx cell joins its parts with a
    # newline, and a raw "12.3\n4.5" would read as one glued number downstream.
    grid = [
        [" ".join(("" if c is None else str(c)).split()) for c in row]
        for row in grid
    ]
    grid = [row for row in grid if any(row)]
    width = max((len(r) for r in grid), default=0)

    # WHICH ROWS WERE SHORT IN THE SOURCE, recorded BEFORE the pad, because
    # afterwards the information is gone. `jats._expand` keeps exactly this and
    # `jats._build_table` acts on it; this path threw it away and then declared
    # `alignment_uncertain: False` unconditionally -- a positive assertion that
    # the columns line up, made without looking. A .docx or .csv row that ran
    # short is padded on the RIGHT, so every value in it after the gap sits one
    # or more columns left of its heading, and a (mean, sd, n) triple read out
    # of it is a triple the supplement never reported. GRIM/GRIMMER would then
    # call it impossible -- against authors whose file was merely ragged.
    padded = [len(r) < width for r in grid]
    for row in grid:
        row.extend([""] * (width - len(row)))

    warnings = list(warnings or [])

    # DEPTH IS PROVEN FROM THE MARKUP WHERE THE MARKUP EXISTS. `header_rows`
    # was a plain int defaulting to 1, and the docstring justified that for the
    # .docx/.xlsx readers on the grounds that their sources have "no span
    # structure to read". That is true of .csv and FALSE of .docx: an OOXML
    # merge is exactly what `python-docx` exposes, and `extract_docx_tables`
    # was ALREADY computing it -- it blanks a merged cell's continuations so one
    # measurement is not counted several times -- and then dropped the fact
    # before this function could use it. Information computed correctly and
    # lost at a seam.
    #
    # `jats._header_depth` is reused rather than reimplemented: it carries the
    # two brakes that stop the walk swallowing a row of measurements into the
    # header, and a second hand-spelled copy of that rule is precisely how the
    # two ends of a boundary drift apart.
    if header_rows is None:
        header_rows = 1
        if source_rows and grid:
            from .jats import _header_depth
            header_rows = _header_depth(source_rows, grid)
    # FLOORED AT ZERO, NOT AT ONE. This clamp was independent of
    # `_header_depth`'s own floor and undid it: a depth of 0, meaning the walker
    # PROVED row 0 is data, arrived here and was raised straight back to 1, so
    # the first data row became the column labels anyway. The min still applies
    # -- a header cannot be deeper than the grid -- and 1 remains the default for
    # every reader that offers no proof either way; only a proven zero survives.
    header_rows = max(0, min(int(header_rows), len(grid))) if grid else 1
    if grid and header_rows == 0:
        warnings.append(_NO_HEADER_IN_THE_SOURCE)
    # A LEADING ROW THAT SPANS EVERY COLUMN IS A TITLE, NOT A HEADER LEVEL.
    # JATS carries the caption in its own element, so this never arises there;
    # a .docx table routinely prints it as the first row. Such a row cannot
    # distinguish any two columns -- that is what full width MEANS -- so
    # joining it into each label adds the whole caption to every column name
    # and identifies nothing. It stays counted in `header_rows` (it is not
    # data), its text is kept as the caption, and only the LABELS skip it, so
    # nothing the file printed is discarded.
    label_start = 0

    # A CAPTION ROW WITH NO SPAN MARKUP TO PROVE IT. The branch below reads the
    # proof off OOXML spans; a spreadsheet has none -- openpyxl reports
    # `merged=[]` on the sheets that motivated this -- so the caption there has
    # to be recognised structurally or not at all.
    #
    # MEASURED 2026-08-22 on `10.1038--s41537-025-00576-3`'s supplementary
    # .xlsx, the largest supplement in the corpus at 2,983 register groups.
    # Every sheet reads:
    #
    #     row 0   'eTable 1. Proportion of ...'      (rest of the row empty)
    #     row 1   'ICD-10 code' | 'Diagnosis' | 'Cases (n)' | 'Prevalence (%)'
    #
    # With one header row the CAPTION became the labels, so 2,983 of 2,983
    # values (100%) sat under a column with no name. That is not only untidy:
    # those sheets pair `Cases (n)` with `Prevalence (%)`, the count/percent
    # relationship `check_count_percent` exists to verify, and it cannot fire
    # on a column it cannot name.
    #
    # THE TEST FAILS CLOSED. It requires the row BELOW to read as labels rather
    # than measurements -- `jats._reads_as_measurements`, reused rather than
    # re-spelled -- because a header that swallows a data row is the worse
    # error: a measurement that leaves the body stops existing for every check.
    if grid and not source_rows and header_rows == 1 and width > 1 and len(grid) > 2:
        from .jats import _reads_as_measurements
        first = [c for c in grid[0] if str(c).strip()]
        below = [c for c in grid[1] if str(c).strip()]
        if (len(first) == 1 and str(grid[0][0]).strip()
                and len(below) >= 2
                and not _reads_as_measurements(grid[1])):
            if not caption:
                caption = " ".join(str(grid[0][0]).split())
            header_rows = 2
            label_start = 1

    # A HEADER ROW THAT REPEATS ITSELF IS A SPAN, and the row below names the
    # columns it covers. Docling propagates a spanning cell across every column
    # it spans, so the repeat IS the span markup -- and then reports
    # `n_header_rows: 1`, leaving the only row that tells those columns apart
    # in the body.
    #
    # MEASURED 2026-08-22, ambiguity by the TABLE's source rather than the
    # paper's: article 7.5%, docx-supp 7.8%, xlsx-supp 0%, and pdf-supp 50.9%
    # -- seven times worse than anything else. On `...51752` supplementary_2
    # Table 3 the header is `Mothers of Girls` four times over
    # `Baseline | MC | MT | p-v | MHT`, so four columns share one name and a
    # value from one cannot be told from a value in another.
    #
    # THE TWO BRAKES ARE THE POINT. The row below is promoted only when it does
    # NOT read as measurements -- a header that swallows a data row deletes a
    # measurement from every check, the worse error by far -- and only when it
    # ADDS distinctions. A candidate that disambiguates nothing is not a header
    # level, and moving it would cost a row for nothing.
    if grid and not source_rows and header_rows == 1 and len(grid) > 2 and width > 1:
        from .jats import _reads_as_measurements
        top = [str(c).strip() for c in grid[0]]
        filled = [c for c in top if c]
        cand = [str(c).strip() for c in grid[1]]
        # NOT ONE MEASUREMENT-SHAPED CELL, which is stricter than
        # `_reads_as_measurements` and had to be. That helper asks whether a row
        # reads as measurements ON BALANCE, and on `...37679` supplement Table 4
        # docling had glued a header and its data into one row: 14 of 19 cells
        # were text, so the helper said "not measurements" and the rule promoted
        # a row still holding `226150662 7250065 ...` and
        # `97.1 (97.0-97.2) 2.1 (2.0-2.2) ...`. Those values would have left the
        # body and stopped existing for every check -- the exact error the brake
        # is for, waved through by a majority test.
        #
        # A genuine inner header level is labels: `MC | MT | p-v | MHT`. If even
        # one cell starts like a number, this is not one, and the cost of
        # refusing is an ambiguous column -- visible, and reported by
        # `ambiguous_columns` -- against the cost of accepting, which is a
        # measurement silently deleted.
        import re as _re
        numeric_cell = _re.compile(r"^[<>=]?\s*-?\d")
        if (filled and len(set(filled)) < len(filled)          # the span's repeat
                and any(cand)
                and not any(numeric_cell.match(c) for c in cand if c)
                and not _reads_as_measurements(grid[1])
                and len(set(zip(top, cand))) > len(set(top))):  # it disambiguates
            header_rows = 2

    if source_rows and grid:
        while (label_start < header_rows - 1
               and label_start < len(source_rows)
               and len(source_rows[label_start]) == 1
               and source_rows[label_start][0][1] >= width > 1):
            if not caption:
                caption = " ".join(str(grid[label_start][0]).split())
            label_start += 1
    # The header is flattened from SPAN-PROPAGATED rows where the source
    # declared spans, so a group label reaches every column beneath it. Falls
    # back to the blanked grid when there is no span markup to propagate.
    header_source = (_propagated_header(source_rows, header_rows, width)
                     if source_rows and grid else grid[:header_rows])
    header = (_flatten_header(header_source[label_start:], width)
              if grid else [])

    # A HEADER THAT READS AS MEASUREMENTS IS NOT A HEADER, IT IS THE FIRST DATA
    # ROW -- and taking it as labels is strictly worse than having no labels at
    # all, because the cells beneath then carry a CONFIDENT wrong name.
    #
    # The brake already existed and was only ever asked the narrower question.
    # `_reads_as_measurements` is used above to decide whether to PROMOTE a
    # second header row; nothing asked whether the FIRST row was a header.
    #
    # MEASURED 2026-09-05 on Stern 2014's Supplementary Table S1. Word splits a
    # long table across two `<w:tbl>` elements and does NOT repeat the header on
    # the second, so table 2's first row is `CFC - IGF-IIR | 7-9 | % Freezing |
    # Test 1 | IgG/Veh | 43.83 | 3.64 | ...`. All 1,704 of its cells were being
    # labelled with that row: `43.83` and `IgG/Veh` read as COLUMN NAMES, and a
    # mean paired with the wrong denominator is the documented route from a
    # coverage win to a false accusation (`25e2f9f`, reverted once for exactly
    # this).
    #
    # COST, measured over every fast-format supplement we hold: 293 tables carry
    # a header and exactly ONE trips this -- 0.3%. So it buys the correctness at
    # almost no coverage.
    #
    # THE ROW GOES BACK TO THE BODY rather than being dropped. `header_rows`
    # returns to 0, so those twelve measurements stay checkable; only the LABELS
    # go, and `_cells_from_grid` names the columns `(unlabelled column N)`. A
    # header that swallows a data row deletes a measurement from every check,
    # which this module already calls the worse error.
    #
    # DELIBERATELY NOT JOINED TO THE PRECEDING TABLE'S HEADER. That would SUPPLY
    # premises the table does not carry, and a derived boundary may narrow a
    # premise, never supply one. Recognising the continuation is a separate,
    # evidence-gated change.
    if grid and header and any(str(h).strip() for h in header):
        from .jats import _reads_as_measurements as _rm
        if _rm([str(h or "").strip() for h in header]):
            warnings.append(_NO_HEADER_IN_THE_SOURCE)
            header_rows = 0
            label_start = 0
            header = [""] * width

    # SECTION BANDS JOIN THE ROW LABEL, AND LEAVE THE BODY. A band like
    # `Sex, n (%)` or `NIHSS (M, IQR)` governs the rows under it and carries the
    # CELL FORMAT that `celltypes` reads off the label. Leaving it as its own
    # row loses that: `39 (33.3)` under a bare `Male` types `ambiguous` and the
    # percentage is dropped, while `Sex, n (%) | Male` types `n_percent` and
    # keeps it. See `jats.section_bands` for what that cost, measured.
    #
    # Joined with the same ` | ` that `_flatten_header` uses for a stacked
    # header, because it is the same act: a label printed once, above, applying
    # to everything beneath it.
    from .jats import fold_section_bands as _fold

    folded, sections, _kept = _fold(grid, header_rows) if grid else ([], [], [])
    body = grid[header_rows:] if grid else []

    # Same rule and same wording as the JATS path: a row that was short AND
    # carries two or more numbers is the alignment risk; a one-cell section
    # label is benign and stays silent.
    uncertain = False
    for row, was_padded in zip(body, padded[header_rows:]):
        if not was_padded:
            continue
        if sum(1 for c in row if _HAS_DIGIT.search(c)) >= 2:
            uncertain = True
            warnings.append(
                f"ragged row {row[:2]!r}: column labels may be shifted; "
                "reconcile against the source file before reporting from this table"
            )
    if grid and any(padded[:header_rows]):
        # The HEADER row itself ran short, so the columns past its end have no
        # label at all in the file. Naming them anyway is what produced column
        # headings the supplement never wrote.
        uncertain = True
        warnings.append(
            "the header row was shorter than the widest data row, so the "
            "right-hand columns are unlabelled in the source; they are reported "
            "as '(unlabelled column N)' and their values may belong under a "
            "heading this file does not contain"
        )

    # THE FOLD IS OFF. It is detected and REPORTED (`sections`), and it does not
    # touch the cells.
    #
    # WHY, measured 2026-08-20: folding the band into the row label made rows
    # checkable that were not before, and `check_count_percent` then paired
    # them with the COLUMN's n. On two honest papers that produced two false
    # accusations -- `Radiotherapy history | Yes`, count 10, percentage 2.9,
    # against the column header's `n = 352`. 10/352 is 2.84%, so the check
    # fired. But the paper is consistent with its own denominator: any n from
    # 339 to 350 prints 2.9%, and 587/590 prints 99.5% exactly. The rows have a
    # smaller denominator than the column total because some patients' history
    # is unknown -- ordinary, and none of our business to override.
    #
    # `test_and_accuses_nobody` caught it. A false accusation against an honest
    # paper is the worst thing this pipeline can produce, and a typing
    # improvement that buys it is not an improvement.
    #
    # `composite.split_sections` already solves the half that matters: it
    # derives a section's n by summing its exhaustive categories and VALIDATES
    # that n against the paper's own printed percentages before any check may
    # use it. The format-marker inheritance belongs there, behind that
    # validation -- not here, ahead of it.
    cells = (_cells_from_grid(header, folded, unlabelled_col=_UNLABELLED_COL)
             if grid else [])
    if provenance:
        cells = [{**c, "provenance": provenance} for c in cells]

    out = {
        "page": page,
        "table_num": table_num,
        "id": "",
        "label": label,
        "caption": caption,
        "section": section,
        "footnotes": [],
        "source": source,
        "data": ([header] + body) if grid else [],
        "cells": cells,
        "headers": header,
        "rows": body,
        "header_rows": grid[:header_rows] if grid else [],
        "n_header_rows": header_rows if grid else 0,
        # PARITY WITH THE XML READER, and the third time this seam has cost a
        # field. `jats.header_adjuncts` is a pure function of the grid and the
        # header depth, and `jats._build_table` calls it -- so a stranded
        # header row like `n = 64`, sitting in the body with an empty stub, is
        # named on a publisher-XML paper and invisible on a PDF one. The fact
        # is surfaced, NOT wired to any check: an adjunct row's scope is as
        # unstated as a footnote's, and promoting one to a denominator was
        # measured to buy two false `suspicious` on an honest table.
        "header_adjuncts": (_jats_header_adjuncts(grid, header_rows)
                            if grid else []),
        "width": width,
        "n_rows": len(body),
        "spans": _spans_out(source_rows),
        "sections": sections,
        "alignment_uncertain": uncertain,
        "image_only": False,
        "graphic_href": None,
        "warnings": warnings,
    }
    if provenance:
        out["provenance"] = provenance
    return out


def extract_docx_tables(path: str | Path) -> dict[str, Any]:
    """Tables and paragraph text from a Word (.docx) supplement."""
    path = Path(path)
    try:
        from docx import Document
    except ImportError:
        return {
            "error": "python-docx is not installed; cannot read .docx",
            "tables": [], "text": "", "n_tables": 0,
        }

    document = Document(str(path))
    tables = []
    for i, table in enumerate(document.tables, 1):
        grid: list[list[str]] = []
        # The SPAN WIDTHS, kept rather than discarded. The duplicate test below
        # already establishes which grid positions one <w:tc> covers; counting
        # them is the colspan, and `_finish` needs it to know how many leading
        # rows are header. Shape matches `jats._header_depth`'s input:
        # (text, colspan, rowspan, is_header).
        source_rows: list[list[tuple[str, int, int, bool]]] = []
        for row in table.rows:
            cells: list[str] = []
            seen: list[Any] = []
            anchors: list[list[Any]] = []
            for cell in row.cells:
                # python-docx REPEATS a merged cell once per grid position it
                # covers. Keeping those copies would turn one measurement into
                # several identical (mean, SD) pairs and trip
                # `detect_duplication` -- a finding invented by the reader. Keep
                # the anchor, blank the continuations, exactly as jats.py does.
                #
                # Compare the underlying <w:tc> elements by identity. `id()` is
                # NOT safe here: `cell._tc` hands back a transient proxy, and a
                # freed one's id can be reused by an unrelated cell.
                element = cell._tc
                duplicate = any(element is s for s in seen)
                cells.append("" if duplicate else cell.text)
                seen.append(element)
                if duplicate and anchors and anchors[-1][0] is element:
                    anchors[-1][2] += 1
                elif duplicate:
                    for a in anchors:
                        if a[0] is element:
                            a[2] += 1
                            break
                else:
                    anchors.append([element, cell.text, 1])
            grid.append(cells)
            source_rows.append(
                [(txt, span, 1, False) for _el, txt, span in anchors])
        tables.append(_finish(grid, i, f"Table {i}", "", path.name, "docx",
                              source_rows=source_rows))

    text = "\n\n".join(p.text for p in document.paragraphs if p.text.strip())
    return {
        "text": text,
        "tables": tables,
        "n_tables": len(tables),
        "source_format": "docx",
    }


def extract_xlsx_tables(path: str | Path) -> dict[str, Any]:
    """One table per worksheet from a spreadsheet supplement."""
    path = Path(path)
    try:
        import openpyxl
    except ImportError:
        return {
            "error": "openpyxl is not installed; cannot read .xlsx",
            "tables": [], "text": "", "n_tables": 0,
        }

    # data_only: read the cached VALUE of a formula, not its source. A forensic
    # check needs the number the authors published.
    book = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    tables = []
    for i, sheet in enumerate(book.worksheets, 1):
        grid = [
            ["" if v is None else str(v) for v in row]
            for row in sheet.iter_rows(values_only=True)
        ]
        table = _finish(grid, i, sheet.title, "", path.name, "xlsx")
        if table["n_rows"] > 200:
            # Participant-level data rather than a summary table. Say so: it
            # supports checks the paper's own tables cannot.
            table["warnings"].append(
                f"{table['n_rows']} data rows — this looks like participant-level "
                "data, not a summary table"
            )
        tables.append(table)
    book.close()
    return {
        "text": "",
        "tables": tables,
        "n_tables": len(tables),
        "source_format": "xlsx",
    }


def extract_csv_tables(path: str | Path) -> dict[str, Any]:
    """A delimited-text supplement as a single table."""
    path = Path(path)
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        grid = [row for row in csv.reader(handle, delimiter=delimiter)]
    return {
        "text": "",
        "tables": [_finish(grid, 1, path.name, "", path.name, "csv")],
        "n_tables": 1,
        "source_format": "csv",
    }


def extract_pdf_tables(path: str | Path) -> dict[str, Any]:
    """Tables from a supplementary PDF, via the SAME reader the paper uses.

    THE BIGGEST HOLE THIS MODULE HAD. 357 of the supplementary files in the
    corpora here are PDFs and every one of them fell through to "unsupported
    supplement format '.pdf'" -- so `extract_supplement` refused the commonest
    supplement format there is, and the sweep prompt told the model to reach for
    `extract_pdf` instead, which returns a DIFFERENT shape (`data` grids, no
    `cells`) and so cannot be handed to `parse_cells_typed`. The numbers were
    reachable but not in the form any check consumes.

    Routing through `extraction.pdf.extract_text_with_tables` rather than
    re-implementing means the supplement reads from the same docling extraction
    cache the paper does, with the same refusal when nobody has extracted it.

    A PDF WITH NO TEXT LAYER is where OCR belongs, and it is reported as its own
    fact (`no_text_layer`) rather than as an empty result. A scanned appendix
    and a born-digital PDF with no tables produce the same empty `tables` list
    and mean opposite things.
    """
    path = Path(path)
    from .pdf import extract_text_with_tables

    raw = extract_text_with_tables(path)
    if raw.get("unreadable"):
        # "WE HAVE NOT EXTRACTED IT" IS NOT "IT HAS NO TEXT LAYER", and
        # conflating them was costly in both directions.
        #
        # Reads became cache-only on 2026-08-16 (pdfplumber is gone), so an
        # un-extracted or stale-cached supplement now reports `unreadable`.
        # This branch then OCR'd it page by page and stamped
        # `no_text_layer: True` -- a POSITIVE, FALSE claim about a born-digital
        # file, with the OCR'd numbers carrying `ocr_table` provenance into
        # forensic checks. That is our gap recorded as a property of the
        # publication, which is the failure this file's own docstring warns
        # about a few lines above.
        #
        # It was also ruinous in practice: MEASURED, `build_manifest` on the
        # JAMA eAppendices rendered a 1.1 MB, 62-table supplement to PNG and
        # OCR'd every page, pinning four xdist workers for over an hour each
        # and wedging the suite at 98%.
        #
        # So OCR only when the file genuinely has no text layer. When the cache
        # is merely absent, say so and name the command that fixes it.
        # WHETHER WE LOOKED, not whether looking succeeded. `cache_status`
        # answers the second and is right to -- its callers need text they can
        # read. Here the question is different: a genuine scan HAS been
        # extracted and produced nothing, and that emptiness IS the finding.
        # Keying on usability would send every scan down the unextracted branch
        # and lose `no_text_layer` entirely, which is the fact that tells a
        # reader OCR is the only route in.
        from .docling_tables import _cache_path
        _looked = _cache_path(path).is_file()
        _why_not = "not extracted"
        if not _looked:
            return {
                "tables": [], "text": "", "source_format": "pdf",
                # UNKNOWN, not False-as-a-fact: we have not looked.
                "no_text_layer": False,
                "unextracted": True,
                "pdf_error": (
                    f"{path.name} has not been extracted ({_why_not}), so its "
                    "contents are UNKNOWN. This is OUR gap, not a property of "
                    "the file: it is NOT evidence that the supplement is a "
                    "scan, and NOT evidence that it has no tables. Run "
                    "`metascience extract-tables` on the paper directory."),
            }
        # A usable extraction that still yields nothing readable IS the scan
        # case, and the original handling is right for it: the pages are
        # images. Hand back whatever the OCR seam can.
        result = ocr_pdf_tables(path)
        result.setdefault("no_text_layer", True)
        result["text"] = ""
        result["source_format"] = "pdf"
        result["pdf_error"] = raw.get("error", "")
        return result

    tables = []
    for i, t in enumerate(raw.get("tables") or [], 1):
        # No `text_alignment` handling here any more: `extraction.pdf` is
        # docling-only and docling reads the document's own ruled structure, so
        # every grid arrives `strategy: "docling"` and the pdfplumber-era
        # inferred-columns warning could never fire.
        table = _finish(
            [list(r) for r in (t.get("data") or [])], i,
            f"Table {i} (p. {t.get('page')})", "", path.name, "pdf",
            page=t.get("page"))
        table["grid_strategy"] = t.get("strategy") or "ruled"
        tables.append(table)

    # THE CAP IS A FACT ABOUT US, RECORDED, NOT A SENTENCE IN THE PAPER. The
    # reader's own truncation marker used to travel into this `text`, which
    # `prepass` hands on as the supplement's running prose and `numerals.index`
    # counts -- so jamanetworkopen.2023.51752 served a line telling the reader to
    # call `extract_pdf` again, inside the text the account measures the paper
    # by, while 239,222 characters were gone with nothing anywhere saying how
    # many. The marker comes off and the two numbers go on the record instead,
    # so a caller can print `served_of_available` rather than discover the loss
    # by counting.
    from .pdf import TRUNCATION_MARKER

    text = raw.get("text") or ""
    if raw.get("truncated") and text.endswith(TRUNCATION_MARKER):
        text = text[:-len(TRUNCATION_MARKER)]
    return {
        "text": text,
        "text_truncated": bool(raw.get("truncated")),
        "n_chars_served": len(text),
        # UNKNOWN IS NOT WRITTEN AS A NUMBER: a reader that predates this field
        # returns None here rather than claiming the served length is all there
        # was.
        "n_chars_available": raw.get("n_chars_available"),
        "tables": tables,
        "n_tables": len(tables),
        "source_format": "pdf",
        "num_pages": raw.get("num_pages"),
        # `tables_error_note`/`tables_rejected_note` were pdfplumber outputs
        # that `extraction.pdf` no longer emits.
        "warnings": [],
    }


def ocr_pdf_tables(path: str | Path) -> dict[str, Any]:
    """OCR every page of a scanned PDF supplement, page by page.

    Rendering to an image and OCR'ing is the only route into a document whose
    pages are pictures. With no engine installed this is a refusal that names
    the engine; the code above it is real so that installing one is the whole
    change.
    """
    path = Path(path)
    from . import ocr as _ocr

    status = _ocr.engine_status()
    if not status["available"]:
        out = _ocr.unavailable_result(f"the scanned pages of {path.name}")
        out["source_format"] = "pdf"
        return out

    try:
        import fitz
    except ImportError:                                   # pragma: no cover
        return {"error": "PyMuPDF is not installed; cannot render PDF pages "
                         "for OCR", "tables": [], "text": "", "n_tables": 0}

    tables: list[dict] = []
    texts: list[str] = []
    with fitz.open(path) as doc:
        for i in range(doc.page_count):
            pix = doc[i].get_pixmap(dpi=_OCR_DPI)
            # A UNIQUE scratch name. This used to be deterministic, so two
            # runs OCR-ing the same supplement wrote the same PNG: one read the
            # other's page image, and whichever finished first unlinked it out
            # from under the other.
            tmp = _scratch_sibling(path, f"ocr-p{i + 1}", ".png")
            try:
                pix.save(tmp)
                page = ocr_image_tables(tmp, page_num=i + 1)
            finally:
                tmp.unlink(missing_ok=True)
            texts.append(page.get("text") or "")
            for t in page.get("tables") or []:
                t["table_num"] = len(tables) + 1
                tables.append(t)
    return {
        "text": "\n\n".join(x for x in texts if x),
        "tables": tables,
        "n_tables": len(tables),
        "source_format": "pdf",
        "provenance": "ocr_table",
        "warnings": [_OCR_PROVENANCE_NOTE],
    }


#: Rendering resolution for OCR. 300 dpi is the floor every engine's own
#: documentation gives for reliable digit recognition; below it the difference
#: between an 8 and a 3 is a few pixels, which is exactly the error that turns
#: an honest SD into an `impossible` verdict.
_OCR_DPI = 300

_OCR_PROVENANCE_NOTE = (
    "These cells were TRANSCRIBED BY MACHINE from an image, not read from a "
    "text layer. Every one carries provenance 'ocr_table', and the "
    "exact-arithmetic checks (GRIM, GRIMMER, SPRITE, DEBIT, GRIM-U) REFUSE "
    "them: the paper did print a last digit, but we do not know we read it "
    "correctly, and this family's verdict turns entirely on that digit. To "
    "reach a verdict, confirm the cell against the image yourself and re-submit "
    "it as provenance='printed_table'."
)


def ocr_image_tables(path: str | Path, page_num: int | None = None) -> dict[str, Any]:
    """Digitize a table printed as an image, into the same cells as any table.

    This is the function Greg's request names: an image supplement should come
    back as STRUCTURED CELLS a check can consume, not as a blob of text. So the
    OCR words go through `ocr.words_to_grid` (column reconstruction) and then
    through the same `_finish` every other reader uses -- one grid, one `cells`
    list, one contract.

    What it will NOT do is return a grid it does not believe. A table read below
    the confidence floor is refused whole; a cell read below the per-cell floor
    is blanked and listed. A blank is a visible gap a reader can go and fill; a
    confidently wrong numeral is a finding against an honest paper.
    """
    path = Path(path)
    from . import ocr as _ocr

    got = _ocr.ocr_words(path)
    if got.get("error"):
        out = dict(got)
        out.setdefault("source_format", path.suffix.lstrip(".").lower())
        return out

    words = got["words"]
    if not words:
        return {
            "text": "", "tables": [], "n_tables": 0,
            "source_format": path.suffix.lstrip(".").lower(),
            "ocr_engine": got.get("engine"),
            "warnings": [
                f"The {got.get('engine')} engine ran on {path.name} and "
                "recognised NO text. That is a fact about this image (blank, a "
                "photograph, or unreadable at this resolution) and not a "
                "statement that the file has no tables."
            ],
        }

    laid = _ocr.words_to_grid(words)
    grid, dropped, median_conf = _ocr._gate_confidence(
        laid["grid"], laid["confidences"])
    text = "\n".join(" ".join(c for c in row if c) for row in grid)

    if median_conf is not None and median_conf < _ocr._MIN_MEDIAN_CONF:
        return {
            "error": (
                f"OCR of {path.name} came back at median confidence "
                f"{median_conf}%, below the {_ocr._MIN_MEDIAN_CONF}% floor. The "
                "transcription is not trustworthy enough to hand to any check, "
                "so it is refused whole rather than returned. Nothing here says "
                "the file has no tables -- only that we could not read them."
            ),
            "ocr_low_confidence": True,
            "ocr_median_confidence": median_conf,
            "ocr_engine": got.get("engine"),
            "tables": [], "text": "", "n_tables": 0,
            "source_format": path.suffix.lstrip(".").lower(),
        }

    warnings = [_OCR_PROVENANCE_NOTE]
    if laid["n_cuts"] == 0:
        warnings.append(
            "No column structure was found: no vertical gap recurred across "
            "enough lines to be a column break. What follows is one column of "
            "lines, which is the right answer for a page of prose and the wrong "
            "one for a table whose columns are too close together to separate. "
            "Do not read the single column as a table."
        )
    if laid["straddled"]:
        warnings.append(
            f"{laid['straddled']} recognised word(s) straddle a column "
            "boundary, so those rows may be shifted relative to their headings. "
            "A shifted row yields a (mean, SD, n) triple the paper never "
            "reported -- reconcile against the image before reporting from it."
        )
    if dropped:
        warnings.append(
            f"{len(dropped)} cell(s) were read below the "
            f"{_ocr._MIN_CELL_CONF}% per-cell confidence floor and are BLANK in "
            "the grid rather than filled with a guess: "
            + ", ".join(f"{d['text']!r} at {d['confidence']}%" for d in dropped[:6])
            + ("..." if len(dropped) > 6 else "")
        )

    table = _finish(grid, 1, path.name, "", path.name, "ocr",
                    warnings=warnings, provenance="ocr_table", page=page_num)
    if laid["straddled"]:
        table["alignment_uncertain"] = True
    return {
        "text": text,
        "tables": [table] if table["n_rows"] else [],
        "n_tables": 1 if table["n_rows"] else 0,
        "source_format": path.suffix.lstrip(".").lower(),
        "provenance": "ocr_table",
        "ocr_engine": got.get("engine"),
        "ocr_median_confidence": median_conf,
        "ocr_cells_dropped": dropped,
        "warnings": warnings,
    }


def extract_html_tables(path: str | Path) -> dict[str, Any]:
    """A supplementary HTML page, through the publisher-HTML table builder.

    `require_article=False`: `validate_t2` asks whether a page IS the article,
    and a supplementary tables page legitimately is not. Running that check here
    would refuse real supplements for failing to be the paper.
    """
    path = Path(path)
    from .html import extract_html_text_with_tables

    raw = extract_html_text_with_tables(path, require_article=False)
    if raw.get("error"):
        return {**raw, "n_tables": 0, "tables": []}
    return {
        "text": raw.get("text") or "",
        "tables": raw.get("tables") or [],
        "n_tables": raw.get("n_tables") or 0,
        "source_format": "html",
        "warnings": raw.get("warnings") or [],
    }


def extract_epub_tables(path: str | Path) -> dict[str, Any]:
    """An EPUB supplement: a ZIP of XHTML, read with the tools already here.

    NO NEW DEPENDENCY. `ebooklib` is not installed and is not needed: an EPUB is
    a zip whose content documents are XHTML, and `extraction.html` already knows
    how to turn XHTML tables into cells. Reading the spine order out of the OPF
    would be tidier; reading the documents in archive order is enough to get the
    tables, and the table LABEL records which document each came from.
    """
    import zipfile

    path = Path(path)
    from .html import _build_table, _flatten_text, _strip_chrome
    from .jats import _Counter

    tables: list[dict] = []
    texts: list[str] = []
    try:
        import lxml.html
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist()
                     if n.lower().endswith((".xhtml", ".html", ".htm"))]
            for name in sorted(names):
                try:
                    tree = lxml.html.fromstring(z.read(name))
                except Exception:
                    # One unparseable chapter must not cost the others.
                    continue
                _strip_chrome(tree)
                counts = _Counter()
                for el in tree.iter("table"):
                    t = _build_table(el, len(tables) + 1, section=name,
                                     counts=counts)
                    t["label"] = t["label"] or f"Table {len(tables) + 1} ({name})"
                    t["source"] = "epub"
                    tables.append(t)
                texts.append(_flatten_text(tree, counts))
    except zipfile.BadZipFile:
        return {"error": f"{path.name} is not a readable EPUB (not a zip archive)",
                "tables": [], "text": "", "n_tables": 0, "source_format": "epub"}

    return {
        "text": "\n\n".join(t for t in texts if t),
        "tables": tables,
        "n_tables": len(tables),
        "source_format": "epub",
    }


def extract_xml_tables(path: str | Path) -> dict[str, Any]:
    """A supplementary XML file, through the JATS/Elsevier reader.

    `tables="full"`, deliberately. The XML reader defaults to an INDEX because a
    90-page article's tables do not fit in one tool result; a supplement goes
    through `_index_if_oversized` immediately below, which applies the same
    policy from one place and with the same `get_supplement_table` escape hatch.
    Taking the index here as well would hand back an index OF an index, and the
    inner one carries no `cells` at all.
    """
    path = Path(path)
    from .jats import extract_xml_text_with_tables

    raw = extract_xml_text_with_tables(path, tables="full")
    if raw.get("error"):
        return {**raw, "tables": raw.get("tables") or [],
                "n_tables": raw.get("n_tables") or 0}
    return {
        "text": raw.get("text") or "",
        "tables": raw.get("tables") or [],
        "n_tables": raw.get("n_tables") or 0,
        "source_format": "xml",
        "warnings": raw.get("warnings") or [],
    }


#: The relationship type Word gives an embedded picture.
_DOCX_IMAGE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
_R_EMBED = re.compile(r'r:(?:embed|link)="([^"]+)"')


def docx_images(path: str | Path) -> list[dict[str, Any]]:
    """Every picture embedded in a Word supplement, in the order it appears.

    AN INVENTORY, NOT A READING. A .docx supplement carries figures, and it
    carries TABLES DRAWN AS PICTURES -- 10.3389/fnins.2022.843105 puts its
    Tables S1 and S2 in as PNGs, so a reader of that paper's account was told
    the supplement had three tables when it prints five and two of them are
    pixels. Nothing here opens an image or reads a value from one; the point is
    that a file we hold and cannot read is recorded as such rather than being
    indistinguishable from a file that does not exist.

    Document order comes from `word/document.xml`: the `r:embed` ids in the
    order they are drawn, resolved through the relationships part. A file whose
    relationships cannot be read falls back to the media directory's own names
    and says which order it used, because a wrong order silently renumbering
    "Figure S3" would be worse than admitting the order is the zip's.
    """
    path = Path(path)
    out: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            media = sorted(n for n in names if n.startswith("word/media/"))
            if not media:
                return []
            targets: list[str] = []
            order = "file_name"
            if "word/document.xml" in names and "word/_rels/document.xml.rels" in names:
                rels = {}
                for m in re.finditer(r'<Relationship\b[^>]*>',
                                     z.read("word/_rels/document.xml.rels").decode("utf-8", "replace")):
                    tag = m.group(0)
                    rid = re.search(r'Id="([^"]+)"', tag)
                    typ = re.search(r'Type="([^"]+)"', tag)
                    tgt = re.search(r'Target="([^"]+)"', tag)
                    if rid and tgt and typ and typ.group(1) == _DOCX_IMAGE_REL:
                        rels[rid.group(1)] = "word/" + tgt.group(1).lstrip("/")
                doc = z.read("word/document.xml").decode("utf-8", "replace")
                seen: set[str] = set()
                for m in _R_EMBED.finditer(doc):
                    t = rels.get(m.group(1))
                    if t and t in names and t not in seen:
                        seen.add(t)
                        targets.append(t)
                if targets:
                    order = "document"
            for t in media:
                if t not in targets:
                    targets.append(t)
            for i, t in enumerate(targets, start=1):
                try:
                    size = z.getinfo(t).file_size
                except KeyError:
                    continue
                out.append({"index": i, "name": t.rsplit("/", 1)[-1], "path_in_docx": t,
                            "n_bytes": size, "order": order,
                            "format": t.rsplit(".", 1)[-1].lower() if "." in t else ""})
    except (OSError, zipfile.BadZipFile, KeyError):
        return []
    return out


def extract_text_supplement(path: str | Path) -> dict[str, Any]:
    """A plain-text or markdown supplement. Text only, and it says so.

    Deliberately does NOT try to recover a table from aligned whitespace or from
    markdown pipes. A `.txt` supplement is usually a readme or a codebook, and a
    column-guessing pass over one produces a grid nobody printed -- the same
    invention `_looks_tabular` exists to stop on the PDF path. Returning the
    text with an explicit "no table structure was recovered" lets the model read
    the numbers in context and stops any check being handed a fabricated grid.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "text": text,
        "tables": [],
        "n_tables": 0,
        "source_format": path.suffix.lstrip(".").lower(),
        "warnings": [
            "Plain text: NO table structure was recovered, and none was "
            "guessed. An empty `tables` list here means this reader does not "
            "infer columns from whitespace, not that the file contains no "
            "tabulated numbers -- read them out of `text`, with their headings."
        ],
    }


def _read_by_format(path: Path) -> dict[str, Any]:
    """Dispatch on suffix. One table, shared by the index and the full read."""
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return extract_docx_tables(path)
    if suffix in (".xlsx", ".xlsm"):
        return extract_xlsx_tables(path)
    if suffix in (".csv", ".tsv"):
        return extract_csv_tables(path)
    if suffix == ".pdf":
        return extract_pdf_tables(path)
    if suffix in (".html", ".htm", ".xhtml"):
        return extract_html_tables(path)
    if suffix == ".epub":
        return extract_epub_tables(path)
    if suffix == ".xml":
        return extract_xml_tables(path)
    if suffix in (".txt", ".md"):
        return extract_text_supplement(path)
    if suffix in IMAGE_SUFFIXES:
        return ocr_image_tables(path)
    return {
        "error": f"unsupported supplement format {suffix!r}",
        "unreadable_format": suffix,
        "tables": [], "text": "", "n_tables": 0,
    }


def extract_supplement(path: str | Path) -> dict[str, Any]:
    """
    Read a supplementary file of any supported format.

    Dispatches on suffix and returns the same shape as `extract_xml`. An
    unsupported format returns a structured error naming the format, so the
    sweep records it in `unchecked` instead of treating the supplement as
    absent -- "present but unreadable" and "not provided" are different facts
    about a paper.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Supplement not found: {path}")

    suffix = path.suffix.lower()
    if suffix in UNREADABLE:
        return {
            "error": f"cannot read {suffix}: {UNREADABLE[suffix]}",
            "unreadable_format": suffix,
            "tables": [], "text": "", "n_tables": 0,
            "source_format": suffix.lstrip("."),
        }

    try:
        result = _read_by_format(path)
    except Exception as exc:
        # A corrupt supplement must not burn a billed stage.
        return {
            "error": f"could not read {path.name}: {type(exc).__name__}: {exc}",
            "tables": [], "text": "", "n_tables": 0,
        }

    result["path"] = str(path)
    return _index_if_oversized(result, path)


#: A supplement result bigger than this comes back as an INDEX instead of in
#: full. The harness caps a tool result; a payload over the cap spills to a
#: temporary file and the model is told to read it back by line offset -- which
#: is sampling, not extraction, so the honest answer has been to refuse.
#:
#: MEASURED on every spreadsheet supplement in this corpus:
#:   fnins.2023.1186751   2 sheets, 1,193 rows  ->  1,879,198 chars
#:   pone.0254493         3 sheets,   282 rows  ->  1,383,602 chars
#:   healthcare11101497   2 sheets,   386 rows  ->    498,993 chars
#: All three exceed any plausible cap. This was never one unlucky paper: EVERY
#: spreadsheet supplement was unreadable for the same reason.
_OVERSIZED_CHARS = 120_000


def supplement_index_entry(t: dict[str, Any]) -> dict[str, Any]:
    """One sheet's identity and shape, with enough rows to recognise it by.

    The preview is what lets a caller CHOOSE: a sheet called `Sheet1` is
    identified by what is in it, not by its name.
    """
    grid = t.get("rows") or t.get("data") or []
    return {
        "table_num": t.get("table_num"),
        "label": t.get("label") or "",
        "n_rows": t.get("n_rows"),
        "width": t.get("width"),
        "warnings": list(t.get("warnings") or []),
        # THE COLUMN NAMES ARE THE MOST IDENTIFYING THING ABOUT A SHEET, and
        # the first version left them out because `rows` is the BODY. Caught by
        # a test asking whether the index could tell the fit-indices sheet from
        # the participant listing: it could not, because "BIC" is a heading. An
        # index a caller cannot choose from is not an index.
        "headers": [str(c)[:60] for c in (t.get("headers") or [])[:20]],
        "first_rows": [[str(c)[:60] for c in row[:12]] for row in grid[:5]],
    }


def _index_if_oversized(result: dict[str, Any], path: Path) -> dict[str, Any]:
    """Return an index rather than a payload nobody can receive.

    THE FAILURE THIS CLOSES. On 10.1038/s41537-025-00576-3 the supplement held
    eTable 5 -- the latent-class model-selection statistics (BIC and the other
    fit indices) justifying the four-class solution the ENTIRE paper rests on.
    Extraction succeeded, the result was 1,114,127 characters, it spilled to a
    temp file, and the review recorded: "reading it back by line offset would
    sample rather than extract, so no check was run." The single most
    consequential check in the paper was skipped because the reader handed back
    everything at once.

    The paper path solved this long ago -- `extract_xml` returns an index and
    `get_table` fetches one table. Supplements had no equivalent, so the
    architecture that makes a 90-page article tractable was missing for a
    spreadsheet.

    NOT A TRUNCATION. Every sheet's identity, shape and first rows are here,
    with an explicit instruction naming the call that fetches the rest. A
    truncated payload that LOOKED complete would be far worse than the refusal
    it replaces.
    """
    try:
        size = len(json.dumps(result, default=str))
    except (TypeError, ValueError):
        return result
    if size <= _OVERSIZED_CHARS:
        return result
    tables = result.get("tables") or []
    return {
        **{k: v for k, v in result.items() if k not in ("tables", "text")},
        "oversized": True,
        "full_size_chars": size,
        "n_tables": len(tables),
        "tables": [supplement_index_entry(t) for t in tables],
        "text": (result.get("text") or "")[:2000],
        "note": (
            f"This supplement is {size:,} characters in full, over the "
            f"{_OVERSIZED_CHARS:,}-character limit for one tool result, so what "
            "you have is an INDEX: every sheet, its shape, and its first rows. "
            "Nothing has been dropped. Call "
            f"get_supplement_table({str(path)!r}, <sheet>) for any sheet in "
            "full, with first_row/last_row to window a long one. Do NOT treat "
            "this index as the supplement's contents."
        ),
    }


def extract_supplement_full(path: str | Path) -> dict[str, Any]:
    """`extract_supplement` WITHOUT the oversize index.

    Exists so `get_supplement_table` can reach the whole workbook. A caller
    that asks for everything should expect to have to handle everything.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Supplement not found: {path}")
    suffix = path.suffix.lower()
    if suffix in UNREADABLE:
        return {"error": f"cannot read {suffix}: {UNREADABLE[suffix]}",
                "unreadable_format": suffix, "tables": [], "text": "", "n_tables": 0}
    try:
        return _read_by_format(path)
    except Exception as exc:
        return {"error": f"could not read {path.name}: {type(exc).__name__}: {exc}",
                "tables": [], "text": "", "n_tables": 0}


def get_supplement_table(path: str | Path, table: int | str,
                         first_row: int | None = None,
                         last_row: int | None = None) -> dict[str, Any]:
    """One sheet of a supplement, by number or by name, optionally windowed.

    The counterpart to the index, and the reason a spreadsheet supplement is
    reachable at all. `table` takes either the 1-based number the index prints
    or the sheet's name: a caller that has just read an index holds both and
    should not have to guess which is wanted.

    `first_row`/`last_row` are 1-based and inclusive over the sheet's own rows,
    so a 30,000-row participant listing can be read in pieces rather than
    refused whole.
    """
    path = Path(path)
    full = extract_supplement_full(path)
    if full.get("error"):
        return full
    tables = full.get("tables") or []
    want = next(
        (t for t in tables
         if str(t.get("table_num")) == str(table)
         or str(t.get("label") or "").strip().lower() == str(table).strip().lower()),
        None)
    if want is None:
        return {
            "error": f"no sheet {table!r} in {path.name}",
            "available": [{"table_num": t.get("table_num"), "label": t.get("label")}
                          for t in tables],
        }
    body = want.get("rows") or []
    header = want.get("headers") or []
    total = len(body)
    lo = max(1, first_row or 1)
    hi = min(total, last_row or total)
    windowed = body[lo - 1:hi]

    # EVERY VIEW OF THE TABLE, WINDOWED THE SAME WAY. A table dict carries the
    # same rows three times -- `rows` (body), `data` (`[header] + body`) and
    # `cells` (one record per non-empty cell) -- and the first version sliced
    # only `rows`. Asking for five rows of an 86-row sheet returned 1,252,595
    # characters, because `cells` still held all of them: the exact defect the
    # window exists to prevent, reintroduced one field over.
    #
    # `cells[].row` is 1-based into `data`, so body row i (1-based) is
    # `row == i + 1`. Sharing one coordinate is what makes this possible; see
    # `jats._cells_from_grid`.
    out = dict(want)
    out["rows"] = windowed
    out["data"] = ([header] + windowed) if header else windowed
    out["cells"] = [c for c in (want.get("cells") or [])
                    if lo + 1 <= (c.get("row") or 0) <= hi + 1]
    out["header_rows"] = want.get("header_rows") or []
    out["n_rows"] = len(windowed)
    out["row_window"] = {"first_row": lo, "last_row": hi, "n_rows_total": total}
    if (lo, hi) != (1, total):
        # A window that did not say it was a window would be a silent
        # truncation wearing the shape of a complete answer.
        out["window_note"] = (
            f"Rows {lo}-{hi} of {total}. The rest were not returned and say "
            "nothing either way; ask for another window to see them."
        )
    out["path"] = str(path)
    return out
