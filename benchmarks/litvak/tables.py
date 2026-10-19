#!/usr/bin/env python3
"""Render the benchmark tables: markdown, and PDF via LaTeX.

    python benchmarks/litvak/tables.py                 # markdown + tex + pdf
    python benchmarks/litvak/tables.py --no-pdf        # markdown + tex only

Three tables, all built from `results.json` (our runs) and Litvak's stored
per-error results, so a new run appends a ROW and nothing is re-typed:

  1. LEADERBOARD -- every system on all 100 errors, ours interleaved by score,
     with `+X / -Y` against the reference run: errors that system caught and we
     missed, and errors we caught it missed.
  2. BY CATEGORY -- ten categories x every system. This is the table that
     retired the "declared scope" framing: FMA's hits are spread across all ten,
     not concentrated in two.
  3. HARD TAIL -- the errors no system caught, and who caught the rest.

WHY `+X / -Y` AND NOT JUST A TOTAL. Two systems can score 49 and 51 and share
only thirty errors. A totals column ranks; only a set comparison says whether a
system is finding *different* things. On this benchmark that is the interesting
question, because the union of Litvak's fourteen reaches 93 while his best
single reaches 71.

THE COMPARISON IS NOT LIKE-FOR-LIKE and every rendering says so: his systems
read the flattened text PDF from `docx_to_pdf.py`, ours read whatever the
corpus was built from, and his numbers here are recomputed on the scored papers
rather than quoted from his published leaderboard.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import results_store as RS                                     # noqa: E402
import score as S                                              # noqa: E402
import compare as C                                            # noqa: E402
from paths import BenchmarkNotFound, add_bench_arg, resolve_bench  # noqa: E402

REPORTS = Path(__file__).resolve().parent / "reports"

#: The two artefacts are NOT versions of one table -- they are the same corpus
#: scored by two different matchers, and the ranking changes between them. Each
#: gets its own directory and its own filename so neither can silently
#: overwrite the other, and so a file on someone's desktop says which matcher
#: produced it without needing the directory for context.
VARIANTS = {
    "protocol": {
        "dir": "original_haiku_matching",
        "stem": "litvak_haiku_matching",
        "title": "scored by Litvak's protocol (haiku, one call per finding, "
                 "no evidence required)",
        "which": "caught_protocol",
    },
    "verified": {
        "dir": "new_sonnet_matching",
        "stem": "litvak_sonnet_matching",
        "title": "scored by the grounded verifier (sonnet, one call per error, "
                 "verbatim evidence quote required and checked in code)",
        "which": "caught",
    },
}

#: Litvak's own display names, copied from his provider definitions
#: (`benchmark/providers/{anthropic,openai,gemini}_provider.py`) rather than
#: invented here. `test_display_names_match_litvaks_own` pins them against that
#: source, because guessing is how `claude_opus_*` would have been labelled
#: Opus 5 when his config says claude-opus-4-6.
DISPLAY_NAMES = {
    "claude_sonnet_no_thinking":    "Claude Sonnet 4.6 (no thinking)",
    "claude_sonnet_high_thinking":  "Claude Sonnet 4.6 (high thinking)",
    "claude_opus_no_thinking":      "Claude Opus 4.6 (no thinking)",
    "claude_opus_high_thinking":    "Claude Opus 4.6 (high thinking)",
    "claude_opus48_no_thinking":    "Claude Opus 4.8 (no thinking)",
    "claude_opus48_high_thinking":  "Claude Opus 4.8 (high thinking)",
    "openai_gpt54_no_reasoning":    "GPT-5.4 (no reasoning)",
    "openai_gpt54_high_reasoning":  "GPT-5.4 (high reasoning)",
    "openai_gpt55_no_reasoning":    "GPT-5.5 (no reasoning)",
    "openai_gpt55_high_reasoning":  "GPT-5.5 (high reasoning)",
    "gemini_pro":                   "Gemini 3.1 Pro",
    "gemini_flash":                 "Gemini 3 Flash",
    "refine_ink":                   "Refine.ink",
    "reviewer3":                    "Reviewer3",
}


#: Our own engines, same treatment as his. Keyed on the model id the run
#: metadata records, not on a guess.
OUR_NAMES = {
    "claude-opus-5":  "FMA (Claude Opus 5)",
    "claude-opus-4-6": "FMA (Claude Opus 4.6)",
    "claude-sonnet-5": "FMA (Claude Sonnet 5)",
    "grok-4.6":       "FMA (Grok 4.6)",
}


def our_label(row: dict) -> str:
    model = str(row.get("model") or "?")
    if model in OUR_NAMES:
        return OUR_NAMES[model]
    backend = str(row.get("backend") or "?")
    return f"FMA ({model})" + (f" [{backend}]" if backend not in ("claude", "?") else "")


def display_name(raw: str) -> str:
    """A readable label, or the raw name if we have no mapping for it.

    Never a prettified guess: an unmapped provider keeps its identifier so a
    reader can see it is unmapped, rather than being shown a plausible name
    nobody chose.
    """
    return DISPLAY_NAMES.get(raw, raw)


def litvak_flag_counts(bench: Path) -> dict[str, int]:
    """Total issues each system reported over the ten papers.

    From `total_findings` in his summary.csv -- the denominator that makes a
    recall number readable. GPT-5.5 emits 512 flags for 71 matches; Reviewer3
    emits 125 for 30. Without this column a reader cannot tell a precise system
    from a verbose one, and on this benchmark false matching scales with volume
    (r = 0.726 against detections on the clean papers).
    """
    path = bench / "benchmark" / "reports" / "summary.csv"
    out: dict[str, int] = {}
    if not path.is_file():
        return out
    import csv as _csv                                          # noqa: PLC0415
    with open(path, encoding="utf-8") as fh:
        for r in _csv.DictReader(fh):
            name = r.get("provider") or ""
            if name.endswith(("_originals", "_open", "_run2", "_run3")):
                continue
            try:
                out[name] = int(r["total_findings"])
            except (KeyError, ValueError):
                continue
    return out

CAVEATS = [
    "Litvak's figures are recomputed from his stored per-error results on the "
    "papers scored here, not quoted from his published leaderboard.",
    "Different input: his systems read the flattened text PDF from "
    "`docx_to_pdf.py`; ours read whatever the scored corpus was built from. "
    "A layout-preserving conversion favours us on table-bound checks.",
    "Leaderboard and category figures use LITVAK'S PROTOCOL on every row: his "
    "haiku judge, one call per finding, no evidence requirement. That is how "
    "his systems were scored, so it is the only like-for-like comparison.",
    "The `verified` column is a separate, stricter measurement of our runs "
    "only -- one judgement per error, shown every finding for that paper, "
    "required to quote verbatim the words identifying the defect, with the "
    "quote checked in code. It is the better estimate of what we caught and "
    "is NOT comparable to the other rows.",
    "`+X` = errors that system caught and the reference run missed. "
    "`-Y` = errors the reference run caught and it missed.",
    "Litvak's RAW scores are inflated in proportion to how much a system "
    "writes: r(findings, false positives on clean papers) = 0.726 over his 14 "
    "systems. His adjusted table is the defensible ranking, and we cannot yet "
    "appear on it -- we have no clean-control run.",
]


def _category_order(gt_rows) -> list[str]:
    return sorted({r["category"] for r in gt_rows})


def pearson(xs, ys) -> Optional[float]:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    return None if den == 0 else num / den


def adjusted_table(bench: Path, keys, systems) -> dict:
    """`adjusted = modified - originals`, Litvak's own correction.

    He ran every system over the ten UNMODIFIED papers too. Nothing is planted
    there, so every "detection" on that set is the judge matching something to
    NOTHING -- a direct measurement of the matching procedure's false-positive
    rate, not of the system.

    It is not a small correction and it is not uniform: measured over his 14
    systems, r(findings emitted, false positives on clean papers) = 0.726. The
    judge credits a system roughly in proportion to how much it writes, so the
    raw leaderboard rewards volume. Adjusting reorders it by up to six places.

    Our own rows report `not computed`: we have no clean-control run, and a
    blank cell reads as zero false positives, which would flatter us.

    A baseline that does not COVER THE SAME PAPERS is refused the same way.
    `openai_gpt54_high_reasoning` has an originals run over 4 of the 10 papers
    (his quota ran out), so its false-positive count is understated by about
    60% -- and the first version of this function scored it 56 - 6 = 50 and
    ranked it FIRST. That is the wrong-denominator error, committed inside the
    table built to expose the same error in someone else's numbers. Litvak
    excludes that system from his own head-to-head for exactly this reason.
    """
    orig = C.load_litvak(bench, include_originals=True)
    detect_papers = {p for p, _s in keys}
    # Unverified systems have no total under this matcher, so they cannot be
    # ranked or adjusted -- same rule as the leaderboard.
    ranked = [s for s in systems if s.get("total") is not None]
    raw_rank = {s["label"]: i for i, s in enumerate(sorted(
        ranked, key=lambda s: -s["total"]), 1)}
    rows = []
    for s in ranked:
        # Keyed on the RAW provider name, never the display label. Introducing
        # readable names silently broke this lookup and every one of Litvak's
        # systems fell through to "no clean-control run" -- the whole adjusted
        # table read `n/c`. Only rendering the PDF and looking at it caught it.
        fp_map = orig.get(s.get("raw_name") or s["label"])
        why = None
        if fp_map is None:
            why = "no clean-control run"
        elif {p for p, _s in fp_map} < detect_papers:
            covered = len({p for p, _s in fp_map})
            why = (f"baseline covers {covered} of {len(detect_papers)} papers")
        fp = None if why else sum(1 for k in keys if fp_map.get(k, False))
        rows.append({"label": s["label"], "ours": s["ours"], "raw": s["total"],
                     "fp": fp, "why_unscored": why,
                     "adjusted": None if fp is None else s["total"] - fp,
                     "raw_rank": raw_rank[s["label"]],
                     "findings": (s.get("row") or {}).get("n_findings")})
    scored = [r for r in rows if r["adjusted"] is not None]
    scored.sort(key=lambda r: -r["adjusted"])
    for i, r in enumerate(scored, 1):
        r["adj_rank"] = i
        r["shift"] = r["raw_rank"] - i
    unscored = [r for r in rows if r["adjusted"] is None]
    xs = [r["fp"] for r in scored]
    return {"rows": scored + unscored, "n_scored": len(scored),
            "r_findings_fp": None}


def gather(bench: Path, reference: str | None = None,
           variant: str = "protocol"):
    gt_rows = S.ground_truth(bench)
    ours = RS.load()
    if not ours:
        raise SystemExit(
            "No runs recorded in results.json yet. Score a run first:\n"
            "  python benchmarks/litvak/score.py --from-db <corpus>")
    lit = C.load_litvak(bench)

    papers = set()
    for row in ours:
        papers |= {int(k.split("|")[0]) for k in (row.get("caught") or {})}
    keys = [(r["paper"], r["subcategory"]) for r in gt_rows if r["paper"] in papers]

    flags = litvak_flag_counts(bench)
    which = VARIANTS[variant]["which"]

    # `ours` here means OUR SYSTEM'S run, not "a row in our store". A re-scored
    # Litvak condition also lives in results.json, and treating it as ours would
    # bold someone else's system as if it were FMA -- which it did, printing
    # "FMA (reviewer3:journal)" beside the real Reviewer3 row. Rows written
    # before `source` existed default to "ours", correct for them.
    mine = [r for r in ours if r.get("source", "ours") == "ours"]
    rescored = {r.get("condition") or r["corpus"]: r
                for r in ours if r.get("source") == "litvak_rescored"}

    ref = next((r for r in mine if r["run_id"] == reference), mine[0])
    # PROTOCOL map, not the verified one. Litvak's fourteen were scored by a
    # lenient per-finding haiku judge with no evidence requirement; our verified
    # pass is stricter on both counts. Ranking a strict number against lenient
    # ones is not a comparison, it is a handicap -- and it would understate us
    # by 7 on this run alone (42 verified vs 49 protocol).
    ref_caught = RS.caught_map(ref, which)

    systems = []
    for row in mine:
        cm = RS.caught_map(row, which)
        vm = RS.caught_map(row, "caught")
        systems.append({"label": our_label(row), "raw_name": row.get("run_id"),
                        "ours": True, "row": row, "unverified": False,
                        "caught": {k: cm.get(k, False) for k in keys},
                        "verified": sum(1 for k in keys if vm.get(k, False)),
                        "verify_model": row.get("verify_model"),
                        "flags": row.get("n_findings")})
    for name, t in lit.items():
        r = rescored.get(name)
        # NO SILENT FALLBACK. Under `--matcher verified`, a system we have not
        # re-scored has no verified number, and backfilling its protocol figure
        # would print GPT-5.5's unverified 71 in a table headed "scored by the
        # grounded verifier". That is presenting one measurement as another --
        # the exact failure this whole harness exists to prevent, and rendering
        # the table is what exposed it.
        unverified = (variant == "verified" and r is None)
        cm = RS.caught_map(r, which) if r else {}
        vm = RS.caught_map(r, "caught") if r else {}
        systems.append({"label": display_name(name), "raw_name": name,
                        "ours": False, "row": r, "unverified": unverified,
                        "caught": ({} if unverified
                                   else {k: cm.get(k, t.get(k, False)) for k in keys}),
                        "verified": (sum(1 for k in keys if vm.get(k, False))
                                     if r else None),
                        "verify_model": (r or {}).get("verify_model"),
                        "flags": flags.get(name)})
    for s in systems:
        if s.get("unverified"):
            s["total"] = None
            s["plus"] = s["minus"] = None
            s["by_category"] = {}
            continue
        s["total"] = sum(1 for k in keys if s["caught"].get(k))
        s["plus"] = sum(1 for k in keys if s["caught"].get(k) and not ref_caught.get(k))
        s["minus"] = sum(1 for k in keys if ref_caught.get(k) and not s["caught"].get(k))
        by = {}
        for r in gt_rows:
            k = (r["paper"], r["subcategory"])
            if k not in s["caught"]:
                continue
            by[r["category"]] = by.get(r["category"], 0) + (1 if s["caught"].get(k) else 0)
        s["by_category"] = by
    # Unverified rows sort LAST and carry no rank: they have no number in this
    # table, which is different from having a low one.
    systems.sort(key=lambda s: (s.get("unverified", False),
                                -(s["total"] if s["total"] is not None else 0)))
    union = sum(1 for k in keys
                if any(s["caught"].get(k) for s in systems
                       if not s["ours"] and not s.get("unverified")))
    return gt_rows, keys, systems, ref, union, papers


# --------------------------------------------------------------------------
# markdown
# --------------------------------------------------------------------------

def render_markdown(gt_rows, keys, systems, ref, union, papers, adj=None,
                    variant: str = "protocol") -> str:
    cats = _category_order(gt_rows)
    L = [f"# FMA on the Litvak planted-error benchmark",
         "",
         f"**Matcher: {VARIANTS[variant]['title']}.**",
         "",
         f"{len(keys)} planted errors over {len(papers)} paper(s). "
         f"Reference run for `+X / -Y`: **{ref['label']}**.",
         ""]

    unver = [s for s in systems if s.get("unverified")]
    blurb = ("Scored by **Litvak's protocol on every row** -- his haiku judge, "
             "one call per finding, no evidence requirement -- because that is "
             "how his fourteen systems were measured. Our stricter verified "
             "figure is the last column and is **not** comparable to anyone "
             "else's number."
             if variant == "protocol" else
             "Scored by the **grounded verifier on every ranked row**: one call "
             "per planted error, shown every finding for that paper, required "
             "to quote verbatim the words identifying the defect, with the "
             "quote checked in code.")
    L += ["## 1. Leaderboard", "", blurb, ""]
    if unver:
        L += [f"**{len(unver)} of {len(systems)} systems have no verified score "
              f"yet** and are listed unranked at the bottom. Their protocol "
              f"figure is deliberately NOT shown here: printing an unverified "
              f"number in a table headed *verified* presents one measurement "
              f"as another. Run `rescore.py` on them to fill these in.", ""]
    L += ["| system | caught | /100 | total flags | +X | −Y | verified |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for s in systems:
        name = f"**{s['label']}**" if s["ours"] else s["label"]
        fl = "—" if s.get("flags") is None else f"{s['flags']}"
        if s.get("unverified"):
            L.append(f"| {name} | *not verified* | — | {fl} | — | — | — |")
            continue
        ver = "—" if s["verified"] is None else \
            f"{s['verified']} ({s['verify_model']})"
        L.append(f"| {name} | {s['total']} | {100*s['total']//len(keys)}% | "
                 f"{fl} | {s['plus']} | {s['minus']} | {ver} |")
    L += ["",
          f"Union of Litvak's systems: **{union}** of {len(keys)} — the "
          f"empirical ceiling.",
          "",
          "`total flags` is every issue that system reported across the ten "
          "papers, matched or not. It is the column that separates a precise "
          "system from a verbose one: on the unmodified papers, where nothing "
          "is planted, detections correlate with flag count at r = 0.726. "
          "**None of these systems, ours included, has a published precision "
          "figure** — the unmatched flags may be real problems in real papers "
          "or they may be noise, and only the clean-control run distinguishes "
          "them.", ""]

    if adj:
        L += ["## 2. Adjusted leaderboard (Litvak's own correction)", "",
              "`adjusted = detected on modified − detected on the UNMODIFIED "
              "papers`. Nothing is planted in the originals, so every match "
              "there is the judge matching something to nothing.",
              "",
              "**This reorders the raw table by up to six places**, and the "
              "correction is not uniform: across his 14 systems, "
              "r(findings emitted, false positives on clean papers) = **0.726**. "
              "The judge credits a system roughly in proportion to how much it "
              "writes. The raw leaderboard rewards volume.",
              "",
              "| system | raw | FP on clean | adjusted | rank shift |",
              "|---|---:|---:|---:|---:|"]
        for r in adj["rows"]:
            name = f"**{r['label']}**" if r["ours"] else r["label"]
            if r["adjusted"] is None:
                L.append(f"| {name} | {r['raw']} | — | *not computed* "
                         f"({r.get('why_unscored') or 'unknown'})* | — |")
            else:
                L.append(f"| {name} | {r['raw']} | {r['fp']} | {r['adjusted']} "
                         f"| {r['shift']:+d} |")
        L += ["",
              "*not computed* means the correction cannot be made honestly for "
              "that row -- either no clean-control run exists (ours), or its "
              "baseline does not cover the same papers. `openai_gpt54_high_"
              "reasoning` is the latter: its originals run covers 4 of the 10 "
              "papers, so its false-positive count is understated by about 60%, "
              "and Litvak excludes it from his own head-to-head for that reason. "
              "A blank cell would read as zero false positives; it is not.", ""]

    L += ["## 3. By category", "",
          "| system | " + " | ".join(c.replace("_", " ") for c in cats) + " | total |",
          "|---" * (len(cats) + 2) + "|"]
    for s in systems:
        name = f"**{s['label']}**" if s["ours"] else s["label"]
        cells = " | ".join(str(s["by_category"].get(c, 0)) for c in cats)
        L.append(f"| {name} | {cells} | {s['total']} |")
    L += ["", "Each category holds 10 planted errors.", ""]

    # Unverified systems contribute nothing here either: "nobody caught this"
    # must mean nobody who was MEASURED, not nobody we happened to score.
    scored_systems = [s for s in systems if not s.get("unverified")]
    never = [k for k in keys if not any(s["caught"].get(k)
                                        for s in scored_systems)]
    if never:
        by_sub = {(r["paper"], r["subcategory"]): r for r in gt_rows}
        L += ["## 4. Caught by nobody", "",
              "| paper | error | category |", "|---|---|---|"]
        for k in sorted(never):
            r = by_sub[k]
            L.append(f"| {k[0]} | {k[1]} | {r['category'].replace('_',' ')} |")
        L.append("")

    L += ["## Caveats", ""] + [f"{i}. {c}" for i, c in enumerate(CAVEATS, 1)]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------
# latex
# --------------------------------------------------------------------------

def _tex_escape(t: str) -> str:
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                 ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"),
                 ("}", r"\}"), ("~", r"\textasciitilde{}"),
                 ("^", r"\textasciicircum{}")):
        t = t.replace(a, b)
    return t


def ladder(labels: list[str], *, step_mm: float = 4.2,
           gap_mm: float = 3.0) -> tuple[str, str]:
    """Horizontal column names stacked to the LEFT, each with an arrow down to
    its column.

    Returns (header_cells, tikz_overlay). The header row carries invisible
    `\\tikzmark` anchors; the overlay draws the labels and the elbow arrows.

    The labels are staggered so column 1 sits LOWEST and the last sits highest:
    each arrow then runs right along its own free row before turning down, so
    no two paths cross. Reversing that order makes every arrow cross every
    other one, which is why the order is not cosmetic.

    Needs TWO pdflatex passes -- `remember picture` positions are written to
    the .aux on pass one and only resolve on pass two. A single pass silently
    renders the arrows at the origin, in the top-left corner of the page.
    """
    cells = " & ".join(f"\\tikzmark{{cat{i}}}" for i in range(len(labels)))
    lines = ["\\begin{tikzpicture}[remember picture, overlay, "
             ">=stealth, line width=0.5pt]"]
    for i, text in enumerate(labels):
        y = gap_mm + step_mm * (i + 1)
        node = f"L{i}"
        lines.append(
            f"  \\node[anchor=east, font=\\scriptsize, inner sep=1pt] "
            f"({node}) at ([xshift=-2mm, yshift={y:.1f}mm]pic cs:cat{i}) "
            f"{{{_tex_escape(text)}}};")
        lines.append(
            f"  \\draw[->, black] ({node}.east) -| "
            f"([yshift=1.2mm]pic cs:cat{i});")
    lines.append("\\end{tikzpicture}")
    return cells, "\n".join(lines)


def rot(text: str, deg: int = 75) -> str:
    """A rotated table header, so a full category name fits the column width.

    `origin=lB` pins the rotation to the cell's left baseline, which keeps the
    labels aligned with their columns rather than drifting right as they get
    longer.

    75 degrees, not 45 or 60: rotated text still occupies `len * cos(deg)` of
    horizontal space, and at 60 degrees ten full category names pushed the last
    two columns -- `theoretical conceptual` and the row totals -- clean off the
    right edge of a landscape page. The rows then showed nine numbers where
    there should be eleven, which is the kind of silent truncation that reads
    as data rather than as a layout fault.
    """
    return f"\\rotatebox[origin=lB]{{{deg}}}{{{_tex_escape(text)}}}"


def render_latex(gt_rows, keys, systems, ref, union, papers, adj=None) -> str:
    cats = _category_order(gt_rows)
    # FULL names, rotated. Truncating to six characters produced headers like
    # "analyt", "attrit", "constr" and "theore" -- unreadable, and two of them
    # ambiguous between categories. Rotation buys the width instead.
    label = {c: c.replace("_", " ") for c in cats}
    rows1 = "\n".join(
        (f"{'\\bfseries ' if s['ours'] else ''}{_tex_escape(s['label'])} & "
         f"\\emph{{not verified}} & -- & -- & -- \\\\")
        if s.get("unverified") else
        f"{'\\bfseries ' if s['ours'] else ''}{_tex_escape(s['label'])} & "
        f"{s['total']} & "
        f"{'--' if s.get('flags') is None else s['flags']} & "
        f"{s['plus']} & {s['minus']} \\\\"
        for s in systems)
    ladder_cells, ladder_draw = ladder([label[c] for c in cats] + ["total"])
    # Reserve exactly the ladder's own height: the topmost label sits at
    # gap + step*(n), and anything less lets it collide with the section
    # heading above -- silently, since TikZ overlays do not reflow.
    ladder_height = 3 + 4.2 * (len(cats) + 1)
    rows2 = "\n".join(
        f"{'\\bfseries ' if s['ours'] else ''}{_tex_escape(s['label'])} & "
        + " & ".join(str(s["by_category"].get(c, 0)) for c in cats)
        + f" & {s['total']} \\\\"
        for s in systems)
    rows_adj = "\n".join(
        (f"{'\\bfseries ' if r['ours'] else ''}{_tex_escape(r['label'])} & "
         f"{r['raw']} & -- & \\emph{{n/c}} & -- \\\\")
        if r["adjusted"] is None else
        (f"{'\\bfseries ' if r['ours'] else ''}{_tex_escape(r['label'])} & "
         f"{r['raw']} & {r['fp']} & {r['adjusted']} & {r['shift']:+d} \\\\")
        for r in (adj or {}).get("rows", []))
    cav = "\n".join(f"\\item {_tex_escape(c)}" for c in CAVEATS)
    return f"""\\documentclass[10pt]{{article}}
\\usepackage[margin=2cm,landscape]{{geometry}}
\\usepackage{{booktabs}}
\\usepackage{{amsmath}}   % \\text in math mode
\\usepackage{{graphicx}}
\\usepackage{{tikz}}      % callout ladder over the category columns
\\usetikzlibrary{{tikzmark}}
\\usepackage[T1]{{fontenc}}
\\renewcommand{{\\arraystretch}}{{1.15}}
\\setlength{{\\parindent}}{{0pt}}
\\begin{{document}}

\\section*{{FMA on the Litvak planted-error benchmark}}

{len(keys)} planted errors over {len(papers)} paper(s).
Reference run for $+X / -Y$: \\textbf{{{_tex_escape(ref['label'])}}}.
Union of Litvak's systems: \\textbf{{{union}}} of {len(keys)} -- the empirical ceiling.
\\emph{{total flags}} is every issue reported across the ten papers, matched or not:
the column that separates a precise system from a verbose one. No system here,
ours included, has a published precision figure.

\\subsection*{{1. Leaderboard}}
\\begin{{tabular}}{{lrrrr}}
\\toprule
system & caught & total flags & $+X$ & $-Y$ \\\\
\\midrule
{rows1}
\\bottomrule
\\end{{tabular}}

\\subsection*{{2. Adjusted (Litvak's correction: modified minus originals)}}
Nothing is planted in the unmodified papers, so every match there is the judge
matching something to nothing. Across his 14 systems,
$r(\\text{{findings}}, \\text{{false positives}}) = 0.726$: the raw leaderboard
rewards volume. \\emph{{not computed}} = no clean-control run exists for that row.

\\begin{{tabular}}{{lrrrr}}
\\toprule
system & raw & FP clean & adjusted & shift \\\\
\\midrule
{rows_adj}
\\bottomrule
\\end{{tabular}}

\\subsection*{{3. By category (10 planted errors each)}}

\\vspace{{{ladder_height}mm}}

{{\\small\\setlength{{\\tabcolsep}}{{4pt}}
\\begin{{tabular}}{{l{'r' * len(cats)}r}}
\\toprule
system & {ladder_cells} \\\\
\\midrule
{rows2}
\\bottomrule
\\end{{tabular}}}}
% The overlay lives OUTSIDE the tabular: a tikzpicture between rows is not a
% legal table element and pdflatex dies on the next \\midrule. `remember
% picture` resolves the marks by name, so its position in the source is free.
{ladder_draw}

\\subsection*{{Caveats}}
\\begin{{enumerate}}
{cav}
\\end{{enumerate}}

\\end{{document}}
"""


def build_pdf(tex: str, out_pdf: Path) -> tuple[bool, str]:
    """pdflatex in a tempdir. Returns (ok, detail) -- never raises.

    Best-effort by contract, like the rest of this repo's PDF rendering: a
    missing LaTeX must not cost you the markdown you already have.
    """
    exe = shutil.which("pdflatex")
    if not exe:
        return False, "pdflatex is not on PATH; markdown and .tex were written"
    with tempfile.TemporaryDirectory(prefix="litvak-tex-") as tmp:
        d = Path(tmp)
        (d / "t.tex").write_text(tex, encoding="utf-8")
        # TWICE. `remember picture` writes node positions to the .aux on the
        # first pass and only resolves them on the second; a single pass draws
        # every callout arrow at the page origin instead of at its column, and
        # does so WITHOUT erroring -- a silent wrong render.
        for _pass in range(2):
            proc = subprocess.run(
                [exe, "-interaction=nonstopmode", "-halt-on-error", "t.tex"],
                cwd=d, capture_output=True, text=True, timeout=180)
        made = d / "t.pdf"
        if not made.is_file():
            tail = (proc.stdout or "")[-500:]
            return False, f"pdflatex produced no PDF: {tail}"
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(made, out_pdf)
    return True, str(out_pdf)


def main() -> int:
    ap = argparse.ArgumentParser()
    add_bench_arg(ap)
    ap.add_argument("--matcher", choices=sorted(VARIANTS), default="protocol",
                    help="Which matcher ranks the leaderboard. `protocol` is "
                         "Litvak's haiku pass, the only one every system has. "
                         "`verified` is the grounded sonnet pass -- available "
                         "for a system only once `rescore.py` has run on it.")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="Default: reports/<variant dir>, so the two matchers "
                         "cannot overwrite each other.")
    ap.add_argument("--reference", default=None,
                    help="run_id whose +X/-Y column the leaderboard uses "
                         "(default: the highest-scoring recorded run)")
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()

    try:
        bench = resolve_bench(a.bench)
    except BenchmarkNotFound as exc:
        print(exc, file=sys.stderr)
        return 1

    v = VARIANTS[a.matcher]
    data = gather(bench, a.reference, a.matcher)
    adj = adjusted_table(bench, data[1], data[2])
    data = data + (adj,)
    out_dir = a.out_dir or (REPORTS / v["dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    md, tex = out_dir / f"{v['stem']}.md", out_dir / f"{v['stem']}.tex"
    md.write_text(render_markdown(*data, variant=a.matcher), encoding="utf-8")
    tex.write_text(render_latex(*data), encoding="utf-8")
    print(f"markdown : {md}")
    print(f"latex    : {tex}")
    if not a.no_pdf:
        ok, detail = build_pdf(tex.read_text(encoding="utf-8"),
                               out_dir / f"{v['stem']}.pdf")
        print(f"pdf      : {detail}" if ok else f"pdf      : NOT BUILT -- {detail}")
    _gt, keys, systems, ref, union, papers, _adj = data
    print(f"matcher  : {a.matcher} -- {v['title']}")
    print(f"\n{len(systems)} system(s) over {len(keys)} errors, "
          f"{sum(1 for s in systems if s['ours'])} of them ours. "
          f"Reference: {ref['label']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
