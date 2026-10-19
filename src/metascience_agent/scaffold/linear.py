"""Linear service: the paper is read in order because the harness serves it in order.

Greg (2026-09-05): "not all of the prose values are properly extracted. I think
that what the model ends up doing is grepping and regex searches, but a human
would read the paper in a linear manner. If there is some technical means by
which to enforce this 'human-like' reading strategy ... I would like to try it."

Two mechanisms, both enforced by the harness rather than asked of the model:

1. NO SEARCH. Every call runs with `--tools ""`, which exposes zero tools
   (measured; see `passes.run_pass`). The model can read only what it is served.

2. ORDERED CHUNKS, EMISSION PER CHUNK. The text is cut into chunks at section
   boundaries and served one at a time in one continuing session (`--resume`),
   so chunk k+1 is not visible until the structured emission for chunk k has
   been returned. Reading order is therefore a property of the run, not a
   strategy the model chooses, and coverage is structural: a run that did not
   visit every chunk did not finish.

Each chunk is served with the numerals the floor found in it, by id, and the
emission must place each one: either it is inside a value the chunk emitted, or
it carries an explicit disposition. `unaccounted` remains a legal disposition --
the point is that a number cannot be passed over silently, not that the model
must invent a home for it.

The first call also carries the pass-1 and pass-2 structure (studies, groups,
phases, variables) and every table's cells, so that a value read in chunk 7 can
be placed at a coordinate defined in chunk 3. The session keeps that context.

Output has the pass-3 shape plus per-chunk dispositions, so `bind.assemble`
consumes it unchanged and the two methods -- whole-text pass 3 and linear pass 3
-- are measured on the same denominator.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from . import passes as _passes
from . import prompts as _prompts
from . import schema as _schema

#: A section shorter than this is merged into the next, so a two-line heading
#: block is not a chunk of its own; a section longer than `_MAX` is split at a
#: paragraph boundary. Sizes in characters.
_MIN = 700
_MAX = 9000


def chunk_schema() -> dict:
    """The pass-3 schema plus the per-chunk numeral dispositions."""
    sch = _schema.pass_schema("pass3")
    sch["properties"]["numeral_dispositions"] = _schema._arr(
        _schema.disposition_row_schema("EXACTLY the id given for this chunk."),
        "One row per numeral id served with this chunk that is NOT inside a value you "
        "emitted: placed (`value`), `ambiguous` with candidates, or `unaccounted` with why.")
    sch["required"].append("numeral_dispositions")
    return sch


def chunks(doc: dict) -> list[dict]:
    """Ordered chunks over the analytic text: sections merged up to `_MIN`,
    split above `_MAX`, back matter excluded."""
    text = doc["text"]
    out: list[dict] = []
    buf_start: int | None = None
    buf_heads: list[str] = []
    for sec in doc["sections"]:
        if sec.get("role") == "back":
            continue
        if buf_start is None:
            buf_start = sec["start"]
        buf_heads.append(sec["name"])
        length = sec["end"] - buf_start
        if length < _MIN:
            continue
        out.append({"start": buf_start, "end": sec["end"], "headings": buf_heads})
        buf_start, buf_heads = None, []
    if buf_start is not None:
        last_end = max(s["end"] for s in doc["sections"] if s.get("role") != "back")
        out.append({"start": buf_start, "end": last_end, "headings": buf_heads})
    # split the long ones at a blank line
    final: list[dict] = []
    for c in out:
        s, e = c["start"], c["end"]
        while e - s > _MAX:
            cut = text.rfind("\n\n", s + _MAX // 2, s + _MAX)
            if cut <= s:
                break
            final.append({"start": s, "end": cut, "headings": c["headings"]})
            s = cut
            c = {**c, "headings": c["headings"][-1:] + ["(continued)"]}
        final.append({"start": s, "end": e, "headings": c["headings"]})
    for i, c in enumerate(final, start=1):
        c["id"] = f"chunk:{i}"
        c["text"] = text[c["start"]:c["end"]]
        # ROWS THAT INDEX THIS STRING, AND THE TEST IS EXPLICIT. A table-cell
        # row carries `offset: None` because its coordinate is (table, cell) and
        # not a byte in the served text; serving one against an offset would
        # file it into whichever chunk spans the same integer and show the model
        # the wrong surrounding text.
        #
        # THE TEST USED TO READ `source == "article"`, which was the same test
        # under a different name for as long as a supplement contributed only
        # cells. Since 2026-09-06 `document.build` serves supplement PROSE
        # inside this string and gives those rows a real offset into it, so
        # keying on the source would serve the supplement's own chunks with an
        # EMPTY numeral list -- asking the model to account for nothing in the
        # part of the paper we had just decided to serve it.
        c["numerals"] = [{"numeral_id": r["id"], "printed": r["printed"],
                          "context": r["context"]}
                         for r in doc["numerals"]
                         if r.get("offset") is not None
                         and c["start"] <= r["offset"] < c["end"]
                         and r.get("role") != "back"]
        c["has_table"] = any(t.get("text_span") and c["start"] <= t["text_span"][0] < c["end"]
                             for t in doc["tables"])
    return final


def _first_prompt(doc: dict, p1: dict, p2: dict, chunk: dict, n_chunks: int) -> str:
    cells_view = []
    for t in doc["tables"]:
        cells_view.append({
            "table_id": t["id"], "label": t["label"], "caption": t.get("caption"),
            "sections": t.get("sections"), "footnotes": t.get("footnotes"),
            "header_rows": t.get("header_rows"), "col_labels": t["col_labels"],
            "row_labels": t["row_labels"],
            "cells": [{"row_label": c.get("row_label"), "col_label": c.get("col_label"),
                       "raw": c.get("raw")} for c in t["cells"]],
        })
    task = f"""\
PASS 3, LINEAR -- VALUES, IN TERMS OF THE STRUCTURE, READ IN ORDER.

You will be served the paper in {n_chunks} chunks, in reading order, one per
message. Read each chunk the way a person reads a page: sentence by sentence,
from the top. For EACH chunk emit, in the schema you are given, everything in
THAT chunk and nothing from any other:

A. TABLE READINGS -- only when the chunk contains a table (its cells are given
   below, under the table id): the READING, not the numbers. For every distinct
   `col_label` (copied exactly) the study, group and phase; for every distinct
   `row_label` (copied exactly) the variable and the statistic form
   (`mean_pm_sem`, `mean_pm_sd`, `mean_pm_unstated` when the table prints
   `x (±y)` and NOWHERE says whether y is SEM or SD, `percentage_of_subjects`,
   `count`, ...). Say whether the table states the n behind each column.

B. PROSE VALUES -- every number in this chunk that is a reported value or a
   design setting: sample sizes (as printed; ranges stay ranges), doses,
   timepoints, durations, thresholds, chance levels, percentages, dimensions,
   concentrations, ages. Variable id (null if none fits), statistic, value
   EXACTLY as printed, coordinate (study, group, phase -- null where the
   sentence does not fix one), verbatim quote, location.

C. COMPARISONS -- every sentence in this chunk saying something was
   significantly different, not different, or a trend, and every starred
   contrast a caption in this chunk describes: study, outcome variable, what is
   compared, the test the paper names FOR THIS comparison as a member of the
   stated set (null when Methods lists tests without saying which applies),
   statistic / df / p AS PRINTED (null when not in the main text), threshold
   when given only as a star, verbal significance, direction, quote.

D. FIGURE PANELS -- for each caption in this chunk: per panel, study, y-axis
   variable, groups, phases, n as printed, error-bar meaning, caption fragment.

E. NUMERAL DISPOSITIONS -- every numeral id served with the chunk that is NOT
   inside a value you emitted gets a disposition: axis_tick, citation_year,
   citation_page, figure_or_table_ref (`Figure 1a`), panel_or_item_label
   (`Test 1`, `E4`), coordinate_label, section_or_list_number, date_or_id,
   affiliation, unit_or_catalog, textual_count, duplicate_of_value (name the
   value), or `unaccounted` when you cannot tell. Do not invent a value to
   empty the list, and do not skip an id.

Use the study, group, phase, variable and procedure ids from the two JSON
documents below exactly. Emit only for the chunk you have just been served.
"""
    return (_prompts.PREAMBLE + "\n" + task
            + _prompts._fence("TABLES (cells, exact labels)", json.dumps(cells_view, indent=1, ensure_ascii=False))
            + _prompts._fence("PASS 1 OUTPUT (comprehension)", json.dumps(p1, indent=1, ensure_ascii=False))
            + _prompts._fence("PASS 2 OUTPUT (variables)", json.dumps(p2, indent=1, ensure_ascii=False))
            + _chunk_block(chunk, n_chunks))


def _chunk_block(chunk: dict, n_chunks: int) -> str:
    k = int(chunk["id"].split(":")[-1])
    nums = json.dumps(chunk["numerals"], indent=0, ensure_ascii=False)
    return (f"\n\n===== CHUNK {k} of {n_chunks} -- {' / '.join(chunk['headings'])} =====\n"
            f"{chunk['text']}\n===== END CHUNK {k} =====\n"
            f"\n===== NUMERALS IN CHUNK {k} (id, printed, context) =====\n{nums}\n"
            f"===== END NUMERALS =====\n"
            f"\nEmit the structured output for chunk {k} now: table readings only if this "
            f"chunk holds a table, prose values, comparisons, figure panels, and a "
            f"disposition for every numeral id above that is not inside a value you emit.")


def run(doc: dict, p1: dict, p2: dict, out_dir: str | Path, *, model: str = _passes.DEFAULT_MODEL
        ) -> dict[str, Any]:
    """Serve every chunk in order in one continuing session. Returns the merged
    pass-3-shaped dict plus `residual` (the chunk dispositions in the shape
    `bind.apply_residual` takes) and `linear_meta`."""
    out = Path(out_dir) / "linear"
    out.mkdir(parents=True, exist_ok=True)
    cs = chunks(doc)
    sch = chunk_schema()
    merged: dict[str, list] = {"table_readings": [], "prose_values": [], "comparisons": [],
                               "figure_panels": []}
    dispositions: list[dict] = []
    meta: list[dict] = []
    session: str | None = None
    t0 = time.time()
    seen_ids: set[str] = set()
    for i, c in enumerate(cs):
        name = f"chunk_{i + 1:02d}"
        prompt = (_first_prompt(doc, p1, p2, c, len(cs)) if i == 0
                  else _chunk_block(c, len(cs)))
        got = _passes.run_pass(name, prompt, out, model=model, schema=sch,
                               resume_session=session, persist_session=(i == 0))
        session = got["meta"].get("session_id") or session
        data = got["data"]
        k = i + 1
        for key in ("table_readings", "prose_values", "comparisons", "figure_panels"):
            for row in data.get(key, []):
                if "id" in row:
                    if row["id"] in seen_ids:
                        row["id"] = f"{row['id']}:c{k}"
                    seen_ids.add(row["id"])
                row["_chunk"] = c["id"]
                merged[key].append(row)
        for d in data.get("numeral_dispositions", []):
            d["_chunk"] = c["id"]
            dispositions.append(d)
        meta.append({"chunk": c["id"], "headings": c["headings"], "chars": c["end"] - c["start"],
                     "n_numerals_served": len(c["numerals"]),
                     "n_values": len(data.get("prose_values", [])),
                     "n_comparisons": len(data.get("comparisons", [])),
                     "n_dispositions": len(data.get("numeral_dispositions", [])),
                     "elapsed_s": got["meta"]["elapsed_s"], "cost_usd": got["meta"].get("cost_usd"),
                     "schema_problems": got["problems"]})
        (out / "linear_meta.json").write_text(json.dumps({"chunks": meta, "session": session},
                                                         indent=1), encoding="utf-8")
    merged_out = {**merged, "residual": {"dispositions": dispositions, "new_values": []},
                  "linear_meta": {"chunks": meta, "n_chunks": len(cs), "session": session,
                                  "elapsed_s": round(time.time() - t0, 1),
                                  "cost_usd": sum((m.get("cost_usd") or 0) for m in meta)}}
    (out / "pass3_linear.json").write_text(json.dumps(merged_out, indent=1, ensure_ascii=False),
                                           encoding="utf-8")
    return merged_out
