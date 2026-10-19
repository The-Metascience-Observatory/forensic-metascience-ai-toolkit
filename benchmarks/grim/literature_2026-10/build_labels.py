"""Build labels.jsonl from the research records in sources/.

The records (sources/*.json, assembled 2026-10-17) are what three literature
searches found: each cell copied from a named critique, notice or PubPeer
comment, with its URL. This script turns them into one label per paper and
records, IN CODE, every judgement made on top of them, so each one can be
read and argued with:

  STATUS        how far each paper's error is established, per DOI
  PREMISE       cells whose integer premise is not applicable or doubtful
  n_source      whether the cell's n is printed in the paper or inferred by
                the critic (another paper, an assumed split, df, a design
                reading) -- mapped from the record's `n_basis`
  VALUE_CHECK   cells the automatic text search missed, settled by reading
                the paper: garbled text layer, or not printed there at all
  MANUAL        the 2026-10-18 pass that read each paper for the premise its
                label lacked (n, whole-number data), confirming or not

Nothing here is evidence that a cell is wrong. verify_labels.py recomputes
the arithmetic, and checks each value against the paper's own text once the
paper is on disk.

    python benchmarks/grim/literature_2026-10/build_labels.py   # writes labels.jsonl
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = ("wansink.json", "brown_heathers.json", "pubpeer_audits.json")

# confirmed_error     a correction, retraction notice or the authors' own data
#                     confirms the printed statistics are wrong (often the n)
# journal_action      an expression of concern or retraction that cites, or
#                     follows a report of, the inconsistencies, without
#                     confirming them cell by cell
# published_critique  a peer-reviewed or preprint critique, no journal action
#                     on the statistics
# unresolved_concern  a blog post or PubPeer comment only
STATUS = {
    "10.1111/joss.12117": ("confirmed_error",
        "2017 erratum cites the critique and gives per-row n"),
    "10.1108/JPBM-01-2015-0802": ("confirmed_error",
        "2017 correction says Table I reported the wrong n"),
    "10.1186/s40795-015-0030-x": ("confirmed_error", "2017 retraction notice cites the critique"),
    "10.1038/oby.2008.286": ("confirmed_error",
        "2017 corrigendum: column n were maxima, gives true per-cell n"),
    "10.1016/j.foodqual.2004.06.005": ("confirmed_error",
        "2017 corrigendum; it also says Table 1 holds adjusted means"),
    "10.1177/0956797611398497": ("confirmed_error",
        "authors' dataset: group sizes swapped in the text"),
    "10.7759/cureus.53725": ("confirmed_error",
        "2026 retraction notice cites mathematically impossible percentages"),
    "10.3389/fpsyg.2016.01298": ("confirmed_error",
        "2017 retraction after an expert audit of the raw data"),
    "10.1037/0022-3514.75.1.33": ("confirmed_error",
        "authors' reply from surviving data; cells only on OSF"),
    "10.1080/00224545.2011.605398": ("journal_action",
        "2023 retraction notice cites impossible mean/SD combinations"),
    "10.1086/661890": ("journal_action",
        "2023 retraction at the authors' request after a report including GRIM"),
    "10.1177/0956797611432497": ("journal_action",
        "2021 expression of concern itemises the GRIM failures"),
    "10.5178/lebs.2012.17": ("journal_action", "2020 expression of concern itemises both cells"),
    "10.5812/aapm.5(3)2015.22367": ("journal_action",
        "2026 expression of concern, assessment ongoing"),
    "10.1007/s00404-012-2277-7": ("journal_action",
        "2026 expression of concern cites discrepancies"),
    "10.1080/1612197X.2021.1877325": ("journal_action",
        "2021 expression of concern; 2024 correction of unclear scope"),
    "10.1891/1933-3196.10.2.59": ("journal_action",
        "retracted: editors lost confidence in the data"),
    "10.1007/s40806-015-0035-3": ("published_critique",
        "Statistical heartburn (BMC Nutrition 2017); editorial note silent on statistics"),
    "10.1093/eurjhf/hfq095": ("published_critique",
        "three peer-reviewed critiques; journal acted only on duplicate publication"),
    "10.1016/j.jacc.2009.02.051": ("published_critique", "Francis et al. 2013"),
    "10.1038/sj.ijo.0803217": ("unresolved_concern", "Anaya blog post"),
    "10.1162/REST_a_00057": ("unresolved_concern", "Anaya blog post"),
    "10.1016/j.amepre.2006.04.003": ("unresolved_concern", "Anaya blog post"),
    "10.1111/j.1540-4560.2005.00405.x": ("unresolved_concern",
        "Brown blog post; the 2016 corrigendum left the means unchanged"),
    "10.1037/h0041593": ("unresolved_concern", "Heino's annotated table"),
    "10.1016/0191-8869(92)90072-W": ("unresolved_concern",
        "Brown blog post; he calls 7 of 30 'close to a toss-up'"),
    "10.1016/j.rbmo.2014.03.011": ("unresolved_concern",
        "Brown spreadsheet; the retraction was for unrelated reasons"),
    "10.1111/j.1447-0756.2012.02016.x": ("unresolved_concern", "Brown spreadsheet"),
    "10.1177/0305735606067168": ("unresolved_concern", "critique gives counts only"),
}

# (doi, value as printed) -> (premise, reason). Everything else is "ok".
PREMISE = {
    **{("10.1016/j.foodqual.2004.06.005", v): (
        "not_applicable",
        "the 2017 corrigendum says these are model-adjusted means, which GRIM cannot test")
       for v in ("6.66", "6.83", "4.47", "6.44", "6.09")},
    ("10.1007/s40806-015-0035-3", "463.61"): ("doubtful",
        "free-text calorie estimate; the integer premise is the critics'"),
    ("10.1007/s40806-015-0035-3", "111.71"): ("doubtful",
        "free-text calorie estimate; the integer premise is the critics'"),
    ("10.1162/REST_a_00057", "4.52"): ("doubtful", "pieces of pizza taken can be fractional"),
    ("10.1162/REST_a_00057", "5.75"): ("doubtful",
        "a numeric estimate; the integer premise is the critic's"),
    **{("10.1891/1933-3196.10.2.59", v): (
        "doubtful", "Quality of Life Index may be weighted; the critic says 'seemingly' integer")
       for v in ("13.82", "13.05", "13.52")},
    ("10.5178/lebs.2012.17", "0.58"): ("doubtful",
        "consistent if each value averages two coders (23/40 = 0.575)"),
    **{("10.1016/j.rbmo.2014.03.011", v): (
        "doubtful", "whole-year ages or durations are the critic's assumption")
       for v in ("27.54", "29.23", "4.43")},
    ("10.1111/j.1447-0756.2012.02016.x", "31.38"): ("doubtful",
        "whole-year ages are the critic's assumption"),
}

N_SOURCE = {"stated per cell": "printed"}   # every other n_basis is inferred

# (doi, value) -> (outcome, note) for the cells verify_labels.py could not find
# in the paper's extracted text (2026-10-18, papers fetched by fetchpdf2).
#   eye           present, read on the extracted line; the text layer garbles it
#   not_in_paper  not printed in this paper at all: the cell is excluded
VALUE_CHECK = {
    **{("10.1038/sj.ijo.0803217", v): (
        "eye", "the PDF font maps the plus-minus sign to '7': 4.96 +/- 2.55 extracts "
               "as '4.9672.55'; all 11 values read at their labelled row and column")
       for v in ("4.96", "3.91", "3.74", "4.39", "3.96", "2.04", "5.61", "3.86",
                 "8.09", "2.96", "8.04")},
    ("10.1037/h0041593", "5.18"): ("eye", "the scan's OCR reads 5.18 as 'S.18'"),
    **{("10.1016/0191-8869(92)90072-W", v): (
        "eye", "the scan's OCR reads the leading 1 as 'I ' (e.g. 'I .50')")
       for v in ("1.50", "1.20", "1.83")},
    **{("10.1108/JPBM-01-2015-0802", v): (
        "not_in_paper", "Table I has no gender row: the critics' statement that it copies "
                        "the 2014 paper's Table 1 verbatim does not hold for this cell")
       for v in ("57.4", "47.9")},
}

# Manual confirmation pass, 2026-10-18: each paper whose label rested on an
# unconfirmed premise was read for that premise. `cells` overrides fields on
# every cell (or on the named values); `paper_verified` records a paper-level
# proof where no single cell can be pinned; `note` is what was found either way.
MANUAL = {
    "10.5812/aapm.5(3)2015.22367": {
        "note": "n confirmed: Results print 'Fifty patients received ketamine and 50 "
                "received magnesium', with no exclusions. The values are Table 1's Male %, "
                "not Table 2 as the notice says; at n = 50 a percentage is a multiple of 2.",
        "cells": {
            "55": {"n_source": "printed",
                   "location": "Table 1, 'Male, %', Magnesium group (n = 50)"},
            "52.5": {"n_source": "printed",
                     "location": "Table 1, 'Male, %', Ketamine group (n = 50)"},
        }},
    "10.1038/sj.ijo.0803217": {
        "note": "n confirmed as printed: 40 participants in a within-subject design, each "
                "given the 9-point questionnaire every week, analysed by repeated-measures "
                "MANOVA (complete cases, so one common n of at most 40). At n = 40, 11 of the "
                "32 Table 1 means fail both conventions -- exactly the 11 labelled. Of every "
                "n from 5 to 40, only n = 23 fits: 0 fail both, 3 fail round-half. The means "
                "were almost certainly computed on 23 responses; the printed n is 40.",
        "cells_all": {"n_source": "printed"}},
    "10.1037/h0041593": {
        "note": "premise confirmed: each subject 'was asked to rate his opinion or reaction "
                "on an 11-point scale' (-5..+5 or 0..10), and 'There remain, for analysis, "
                "20 Ss in each' condition. At n = 20 a mean is a multiple of .05.",
        "cells_all": {"premise": "ok", "premise_reason": None}},
    "10.1177/0956797611432497": {
        "note": "Study 2 confirmed at paper level; Study 1 not (several splits of N = 40 "
                "fit 5.3 and 4.71).",
        "paper_verified": "Study 2 (N = 74 from t(72)): no split of 74 between the two "
                          "conditions makes all six single-item 7-point means (lamp 2.34/4.16, "
                          "candle 2.37/3.62, flashlight 2.35/4.33) GRIM-consistent, under "
                          "round-half or truncation; at least two fail at every split. Agrees "
                          "with the journal's 2021 expression of concern."},
    "10.1111/j.1540-4560.2005.00405.x": {
        "note": "NOT confirmable: the df-implied split 18/19/18 fails, but 19/18/18 makes all "
                "three composite means (7.47, 6.85, 6.59; 3 items each) consistent and needs "
                "only the second t's df to be 35 instead of the printed 34."},
    "10.1016/0191-8869(92)90072-W": {
        "note": "NOT confirmable: values confirmed at their cells on the scan (Table 2), but "
                "each respondent ranks three groups, so complete answers make a row's three "
                "means sum to 6.00; the Oriental rows sum to 5.92-6.00, so items had missing "
                "or tied answers and the per-item n is not 73. The cells also fail only "
                "round-half."},
    "10.1016/j.rbmo.2014.03.011": {
        "note": "NOT confirmable: Table 1 prints 'Age (years)' and 'Duration of infertility "
                "(years)' as mean +/- SD; nothing says they were recorded in whole years."},
    "10.1111/j.1447-0756.2012.02016.x": {
        "note": "NOT confirmable: ages printed as mean +/- SD with no statement that they "
                "were recorded in whole years."},
}


def slug(doi: str) -> str:
    """The paper's folder name. Lower case, as fetchpdf writes it: DOIs are
    case-insensitive, and fetchpdf2 saved `10.1162/REST_a_00057` as
    `10.1162--rest_a_00057`."""
    return doi.lower().replace("/", "--")


def _value(cell: dict) -> tuple[str, str]:
    raw = str(cell.get("mean_as_printed") or cell.get("value_as_printed") or "").strip()
    kind = str(cell.get("value_kind") or "mean")
    if kind.startswith("perc") or raw.endswith("%"):
        return raw.rstrip("%").strip(), "percentage"
    return raw, "proportion" if kind.startswith("prop") else "mean"


def build() -> list[dict]:
    papers: dict[str, dict] = {}
    for name in SOURCES:
        for rec in json.loads((HERE / "sources" / name).read_text())["papers"]:
            doi = rec["doi"]
            if doi not in STATUS:
                raise KeyError(f"{doi} ({name}) has no STATUS decision")
            if doi in papers:
                # The same paper from a second search: keep the first record's
                # cells, add the second's sources.
                papers[doi]["evidence"] += rec.get("sources") or []
                papers[doi]["research_records"].append(name)
                continue
            status, why = STATUS[doi]
            cells = []
            for i, c in enumerate(rec.get("grim_cells") or [], 1):
                value, kind = _value(c)
                premise, premise_why = PREMISE.get((doi, value), ("ok", ""))
                cells.append({
                    "id": f"c{i:03d}",
                    "location": c.get("location"),
                    "value": value,
                    "kind": kind,
                    "n": int(c["n"]),
                    "items_k": int(c.get("items_k") or 1),
                    "decimals": int(c["decimals"]),
                    "n_source": N_SOURCE.get(c.get("n_basis"), "inferred"),
                    "n_basis": c.get("n_basis"),
                    "premise": premise,
                    "premise_reason": premise_why or None,
                    "why_integer": c.get("why_integer"),
                    "critic_verdict": c.get("critic_verdict"),
                    "doubt": c.get("doubt") or None,
                    "source_url": c.get("source_url"),
                    "value_check": dict(zip(("outcome", "note"),
                                            VALUE_CHECK[(doi, value)]))
                                   if (doi, value) in VALUE_CHECK else None,
                    "value_verified": False,
                })
            manual = MANUAL.get(doi) or {}
            for cell in cells:
                cell.update(manual.get("cells_all") or {})
                cell.update((manual.get("cells") or {}).get(cell["value"]) or {})
            papers[doi] = {
                "paper_id": slug(doi), "doi": doi, "title": rec.get("title"),
                "manual_check": manual.get("note"),
                "paper_verified": manual.get("paper_verified"),
                "year": rec.get("year"), "journal": rec.get("journal"),
                "status": status, "status_reason": why,
                "outcome": rec.get("outcome"), "outcome_url": rec.get("outcome_url"),
                "fulltext_url": rec.get("fulltext_url"),
                "evidence": list(rec.get("sources") or []),
                "n_question": rec.get("n_question"),
                "cells_not_itemised": rec.get("grim_cells_not_itemised") or None,
                "notes": rec.get("notes"),
                "research_records": [name],
                "cells": cells,
            }
    missing = set(STATUS) - set(papers)
    if missing:
        raise KeyError(f"STATUS names papers no record has: {sorted(missing)}")
    return list(papers.values())


def main() -> int:
    papers = build()
    (HERE / "labels.jsonl").write_text(
        "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in papers))
    print(f"{len(papers)} papers, {sum(len(p['cells']) for p in papers)} cells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
