"""The value register, drawn ON the paper it was read from.

WHY THIS EXISTS. Greg, 2026-08-25:

    "is it possible to make an inspectable version of the register of values?
     Perhaps mapped onto the converted text and tables? This is the simplest
     way for me to see what the gaps are (e.g. values that reliably don't get
     extracted properly, or at all)"

The register is already complete and already unreadable. `value_register.json`
runs to 860 KB on one 5,000-word paper, and the viewer's Values tab lists its
groups by anchor -- which answers "what did we index?" and cannot answer "what
did we MISS?", because a miss has no row. A gap is invisible in a list of hits.

So this renders the other direction: the paper as we read it, with every
number we found drawn ON it, and every number we found and could not use drawn
in a colour that says so. What is not marked is what nobody looked at.

THE ONE THING THIS MUST NOT DO is imply a join it did not make. Three separate
populations reach this page and they are NOT the same population:

  * `numerals.rows` -- every numeric token in the body, with a character
    offset. The floor. Cannot be silently incomplete, because it is a scan for
    digits.
  * `groups[]` with `anchor.table` -- values typed out of a TABLE cell.
  * `groups[]` with `anchor.table is None` -- values typed out of PROSE.

There is no key linking a numeral row to the prose group that consumed it.
That is a real gap in the register and this page SAYS so rather than inventing
the join: a numeral is coloured by its own `class`, never by a group it was
guessed to belong to. Drawing an unverified join here would be the house
failure -- our bookkeeping presented as a fact about the paper -- on the one
surface built to expose it.

MEASURED before building, on `benchmarks/paper_reviews/runs/apple_cider`: 709 of 709 numeral
offsets land exactly on their printed token in `paper_text()`, so the prose
overlay is exact rather than approximate. And `anchor.col` is None on 711 of
711 values, so the table join keys on `col_label` -- keying on `col` yields a
confident empty grid, which is how this module would have shipped looking
correct and showing nothing.
"""
from __future__ import annotations

import html as _html
import json
from pathlib import Path
from typing import Any

#: What a group's bookkeeping says happened to it. The vocabulary is the
#: coverage strata's, not a fourth one: a page that invents its own words for
#: `n_silent` and `n_no_applicable_tool` is a second denominator.
DISPOSITIONS = {
    "checked": ("A tool ran on this group and returned a verdict.", "ok"),
    "no_applicable_tool": (
        "The dispatcher considered this group and no check applied -- usually "
        "because nothing declared the variable's type.", "none"),
    "silent": (
        "A tool applies, no verdict arrived, and no refusal was recorded. "
        "This is a gap in OUR bookkeeping, not a fact about the paper.", "bad"),
    "not_considered": (
        "The dispatcher never reached this group.", "bad"),
}


def group_disposition(g: dict) -> str:
    """Which stratum this group ended in. Mirrors `values.coverage`."""
    if g.get("checks"):
        return "checked"
    if not g.get("dispatch_considered"):
        return "not_considered"
    if not g.get("applicable_tools"):
        return "no_applicable_tool"
    return "silent"


def _esc(s: Any) -> str:
    return _html.escape("" if s is None else str(s))


def mark_numerals(text: str, rows: list[dict]) -> tuple[str, int, int, int]:
    """Wrap every indexed numeral in `text`, in one left-to-right pass.

    Returns `(html, n_drawn, n_bad_offset, n_overlapping)`.

    Offsets are verified against the token they claim before use. A row whose
    offset does NOT land on its own `printed` string is dropped and counted --
    silently trusting it would shift every subsequent span and corrupt the
    whole page, and the count is reported so the drop is visible.

    `n_drawn` COUNTS SPANS EMITTED, not rows that survived the offset check.
    A first version returned the latter, so a page that skipped an overlapping
    row still reported it as drawn -- the page's own header over-stating its
    own coverage, on the surface built to expose exactly that. The two numbers
    differ only when the index contains a nested span, which is why the
    distinction survived until a test asked for it.
    """
    good = []
    for r in rows:
        o, e, p = r.get("offset"), r.get("end"), r.get("printed")
        if o is None or e is None or p is None:
            continue
        if text[o:e] != p:          # the guard, not an assumption
            continue
        good.append(r)
    good.sort(key=lambda r: r["offset"])

    out, cur, last_end, n_overlap = [], 0, -1, 0
    for r in good:
        o, e = r["offset"], r["end"]
        if o < last_end:            # overlapping index: keep the first
            n_overlap += 1
            continue
        out.append(_esc(text[cur:o]))
        cls = r.get("class") or "unclassified"
        tip = f"{cls}"
        if r.get("why"):
            tip += f" -- {r['why']}"
        if r.get("section"):
            tip += f" [{r['section']}]"
        out.append(
            f'<span class="num n-{_esc(cls)}" data-id="{_esc(r.get("id"))}"'
            f' title="{_esc(tip)}">{_esc(text[o:e])}</span>')
        cur, last_end = e, e
    out.append(_esc(text[cur:]))
    return "".join(out), len(good) - n_overlap, len(rows) - len(good), n_overlap


def table_cell_index(groups: list[dict]) -> dict:
    """`(table, row, col_label) -> [group, ...]`, the join that actually works.

    Keyed on `col_label` because `anchor.col` is None on every value this
    register has ever produced. Several groups can share one cell (a mean and
    its SD are printed together), so the value is a list -- collapsing it to
    one would silently drop half the register on exactly the densest cells.
    """
    idx: dict[tuple, list] = {}
    for g in groups:
        a = g.get("anchor") or {}
        if not a.get("table"):
            continue
        for v in g.get("values") or []:
            va = v.get("anchor") or {}
            key = (a.get("table"), va.get("row", a.get("row")),
                   va.get("col_label"))
            idx.setdefault(key, [])
            if g not in idx[key]:
                idx[key].append(g)
    return idx


_CSS = """
:root{--bg:#F5F7F9;--sf:#fff;--ink:#111820;--mut:#5A6572;--rule:#DCE2E8;
--ok:#1F7A5A;--ok-bg:#DFF1EA;--none:#8A6A17;--none-bg:#FBF1D8;
--bad:#B03030;--bad-bg:#FBE3E3;--stat:#1F4E79;--stat-bg:#E2EDF7;
--unc:#7A4E9A;--unc-bg:#EFE6F7;--amb:#B4530F;--amb-bg:#FBE9DA}
@media(prefers-color-scheme:dark){:root{--bg:#0F141A;--sf:#161C24;--ink:#E4E9EF;
--mut:#93A0B0;--rule:#28313D;--ok-bg:#12291F;--none-bg:#2A2312;--bad-bg:#2C1616;
--stat-bg:#152537;--unc-bg:#241A31;--amb-bg:#2E1D0F;--ok:#4FB58C;--none:#D0A63C;
--bad:#E96B6B;--stat:#7FB3E3;--unc:#B58AD8;--amb:#E08A45}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 "Public Sans",
system-ui,-apple-system,"Segoe UI",sans-serif}
code,pre,.mono,.num,td,th{font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace}
header{padding:1.6rem 2rem;border-bottom:1px solid var(--rule);background:var(--sf)}
h1{margin:0 0 .3rem;font-size:1.3rem;font-weight:600}
h2{font-size:1.05rem;margin:0 0 .7rem;font-weight:600}
.sub{color:var(--mut);font-size:.85rem;margin:0}
.floor{margin:.9rem 0 0;padding:.6rem .8rem;border-left:3px solid var(--none);
background:var(--none-bg);font-size:.83rem;border-radius:0 4px 4px 0;max-width:90ch}
nav{display:flex;gap:.2rem;padding:0 2rem;background:var(--sf);
border-bottom:1px solid var(--rule);flex-wrap:wrap}
nav button{border:0;background:none;color:var(--mut);font:inherit;font-size:.86rem;
padding:.65rem .9rem;cursor:pointer;border-bottom:2px solid transparent}
nav button.on{color:var(--ink);border-bottom-color:var(--stat);font-weight:600}
main{padding:1.4rem 2rem 5rem}
.pane{display:none}.pane.on{display:block}
.legend{display:flex;flex-wrap:wrap;gap:.35rem;margin:0 0 1rem;font-size:.76rem}
.legend span{padding:.2rem .5rem;border-radius:3px;border:1px solid var(--rule)}
.k-ok{background:var(--ok-bg);color:var(--ok)}.k-none{background:var(--none-bg);color:var(--none)}
.k-bad{background:var(--bad-bg);color:var(--bad)}.k-stat{background:var(--stat-bg);color:var(--stat)}
.k-unc{background:var(--unc-bg);color:var(--unc)}.k-amb{background:var(--amb-bg);color:var(--amb)}
pre.body{background:var(--sf);border:1px solid var(--rule);border-radius:6px;
padding:1.1rem 1.3rem;white-space:pre-wrap;word-wrap:break-word;font-size:.8rem;
line-height:1.85;max-height:none}
.num{border-radius:2px;padding:0 2px;cursor:help}
.n-statistic{background:var(--stat-bg);color:var(--stat);font-weight:600}
.n-unclassified{background:var(--unc-bg);color:var(--unc)}
.n-ordinal,.n-citation_year,.n-scale_anchor,.n-table_cell{background:var(--none-bg);color:var(--none)}
table{border-collapse:collapse;font-size:.76rem;background:var(--sf);width:100%}
.tw{overflow-x:auto;border:1px solid var(--rule);border-radius:6px;margin:0 0 1.3rem}
td,th{border:1px solid var(--rule);padding:.32rem .5rem;text-align:left;vertical-align:top}
th{background:var(--bg);font-weight:600;position:sticky;top:0}
td.d-checked{background:var(--ok-bg)}
td.d-no_applicable_tool{background:var(--none-bg)}
td.d-silent,td.d-not_considered{background:var(--bad-bg)}
td.amb{outline:2px solid var(--amb);outline-offset:-2px}
.cap{font-size:.85rem;font-weight:600;margin:1.4rem 0 .4rem}
.meta{font-size:.75rem;color:var(--mut);margin:0 0 .5rem}
.grid{display:grid;gap:.8rem;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));margin:0 0 1.4rem}
.card{background:var(--sf);border:1px solid var(--rule);border-radius:6px;padding:.7rem .85rem}
.card b{display:block;font-size:1.45rem;font-weight:600;line-height:1.1}
.card span{font-size:.75rem;color:var(--mut)}
.gap{background:var(--sf);border:1px solid var(--rule);border-left:3px solid var(--bad);
border-radius:0 6px 6px 0;padding:.8rem 1rem;margin:0 0 1rem;font-size:.85rem}
.gap h3{margin:0 0 .4rem;font-size:.9rem}
ul.tight{margin:.3rem 0;padding-left:1.1rem}ul.tight li{margin:.15rem 0;font-size:.8rem}
"""

_JS = """
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.classList.remove('on'));
  document.querySelectorAll('.pane').forEach(x=>x.classList.remove('on'));
  b.classList.add('on');document.getElementById(b.dataset.p).classList.add('on');
});
"""


def _tables_html(tables: list, idx: dict, amb_tables: set) -> str:
    """Each walked table as a grid, tinted by what happened to each cell.

    THE GRID IS REBUILT FROM `col_label`, NOT FROM A COLUMN INDEX. A walked
    cell carries exactly `raw`, `row`, `row_label`, `col_label` -- there is no
    `col`. A first draft of this function read `c["col"]`, which would have
    produced a one-column table on every paper while looking correct. The
    columns are therefore the distinct `col_label`s in order of first
    appearance, which is also precisely the key `table_cell_index` joins on,
    so the grid and the join cannot disagree about what a column is.

    An UNMARKED cell is not a clean cell. It is a cell no group claimed, and
    the legend says so -- the commonest real gap on this page, and the one a
    list of hits can never show.
    """
    out = []
    for t in tables:
        label = t.get("label") or "(unlabelled table)"
        cells = t.get("cells") or []
        if not cells:
            out.append(f'<div class="cap">{_esc(label)}</div>'
                       f'<p class="meta">No cells were extracted from this table. '
                       f'That is an extraction gap, not an empty table.</p>')
            continue

        cols: list = []
        for c in cells:
            cl = c.get("col_label")
            if cl not in cols:
                cols.append(cl)
        rows: list = []
        for c in cells:
            r = c.get("row")
            if r not in rows:
                rows.append(r)
        rows.sort(key=lambda x: (x is None, x))

        by = {(c.get("row"), c.get("col_label")): c for c in cells}
        rowlab = {}
        for c in cells:
            rowlab.setdefault(c.get("row"), c.get("row_label") or "")

        n_marked = 0
        body = []
        for r in rows:
            tds = [f'<th style="text-align:left;font-weight:500">'
                   f'{_esc(rowlab.get(r, ""))}</th>']
            for cl in cols:
                c = by.get((r, cl))
                raw = (c or {}).get("raw", "")
                gs = idx.get((label, r, cl)) or []
                disp = group_disposition(gs[0]) if gs else None
                if disp:
                    n_marked += 1
                cls = f"d-{disp}" if disp else ""
                title = ""
                if gs:
                    kinds = ", ".join(sorted({g.get("kind", "?") for g in gs}))
                    tools = ", ".join(sorted({
                        ch.get("tool", "?") for g in gs
                        for ch in (g.get("checks") or [])})) or "no check ran"
                    title = f"{disp} -- {kinds} -- {tools}"
                tds.append(f'<td class="{cls}" title="{_esc(title)}">'
                           f'{_esc(raw)}</td>')
            body.append("<tr>" + "".join(tds) + "</tr>")

        ths = "<th></th>" + "".join(f"<th>{_esc(c)}</th>" for c in cols)
        src = t.get("extractor") or t.get("source") or "unknown"
        n_cells = len(rows) * len(cols)
        flag = (' <span class="k-amb" style="padding:.1rem .4rem;'
                'border-radius:3px">shared column label</span>'
                if label in amb_tables else "")
        out.append(
            f'<div class="cap">{_esc(label)}{flag}</div>'
            f'<p class="meta">{len(rows)} rows x {len(cols)} columns &middot; '
            f'read by {_esc(src)} &middot; '
            f'<b>{n_marked} of {n_cells}</b> cells were claimed by a register '
            f'group; the rest are unmarked, which means nothing indexed them.'
            f'</p>'
            f'<div class="tw"><table><thead><tr>{ths}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')
    return "".join(out) or '<p class="meta">No tables were walked for this paper.</p>'


def render(register: dict, text: str, text_source: str | None,
           tables: list, paper_id: str = "") -> str:
    """The whole page. Best-effort by contract -- it never raises on a gap."""
    G = register.get("groups") or []
    nums = ((register.get("numerals") or {}).get("rows")) or []
    numinfo = register.get("numerals") or {}
    amb = register.get("ambiguous_columns") or {}
    amb_tables = set((amb.get("tables") or {}).keys())

    marked, n_ok, n_dropped, n_overlap = (
        mark_numerals(text, nums) if text else ("", 0, 0, 0))
    idx = table_cell_index(G)

    disp_counts: dict[str, int] = {}
    for g in G:
        d = group_disposition(g)
        disp_counts[d] = disp_counts.get(d, 0) + 1
    table_groups = sum(1 for g in G if (g.get("anchor") or {}).get("table"))
    prose_groups = len(G) - table_groups

    cards = "".join(
        f'<div class="card"><b>{v:,}</b><span>{k}</span></div>' for k, v in [
            ("numerals indexed (the floor)", numinfo.get("n_total", 0)),
            *[(f"  of which {k.replace('_', ' ')}", (v or {}).get("n_total", 0))
              for k, v in sorted((numinfo.get("by_source") or {}).items())],
            ("register groups", len(G)),
            ("  of which from tables", table_groups),
            ("  of which from prose", prose_groups),
            ("values", register.get("n_values", 0)),
            ("groups checked", disp_counts.get("checked", 0)),
            ("no applicable tool", disp_counts.get("no_applicable_tool", 0)),
            ("silent (our gap)", disp_counts.get("silent", 0)
             + disp_counts.get("not_considered", 0)),
        ])

    gaps = []
    unclass = numinfo.get("by_class", {}).get("unclassified", 0)
    if unclass:
        ex = [r for r in nums if r.get("class") == "unclassified"][:12]
        gaps.append(
            f'<div class="gap"><h3>{unclass:,} numerals were indexed and never '
            f'classified</h3><p>The floor found them; nothing said what they '
            f'are. Each is a number in this paper that no check could reach. '
            f'First few, with context:</p><ul class="tight">' + "".join(
                f'<li><b>{_esc(r.get("printed"))}</b> &mdash; '
                f'{_esc((r.get("context") or "")[:90])}</li>' for r in ex)
            + '</ul></div>')

    if disp_counts.get("silent") or disp_counts.get("not_considered"):
        n = disp_counts.get("silent", 0) + disp_counts.get("not_considered", 0)
        gaps.append(
            f'<div class="gap"><h3>{n} groups ended SILENT</h3><p>A tool '
            f'applies, no verdict arrived, and no refusal was recorded. Per '
            f'<code>values.coverage</code>: any number above zero here is a bug '
            f'in our bookkeeping, not a finding about the paper.</p></div>')

    ur = register.get("unbound_rows") or []
    if ur:
        gaps.append(
            f'<div class="gap"><h3>{len(ur)} row labels bound to no declared '
            f'variable</h3><p>The register found these rows and refused to '
            f'guess which variable they are. Until one is declared, no '
            f'type-dependent check can run on them.</p><ul class="tight">'
            + "".join(f'<li>{_esc(r.get("row_label"))} '
                      f'<span style="opacity:.6">({r.get("n_candidates", 0)} '
                      f'candidates, {_esc(r.get("status"))})</span></li>'
                      for r in ur[:15]) + '</ul></div>')

    if amb.get("n_groups"):
        gaps.append(
            f'<div class="gap"><h3>{amb["n_groups"]} groups sit under a '
            f'shared column label</h3><p>{_esc(amb.get("note", ""))}</p></div>')

    if n_dropped:
        gaps.append(
            f'<div class="gap"><h3>{n_dropped} numeral offsets did not land on '
            f'their own token</h3><p>Dropped rather than drawn. An offset that '
            f'has drifted would shift every later highlight on the page.</p>'
            f'</div>')

    if n_overlap:
        gaps.append(
            f'<div class="gap"><h3>{n_overlap} numerals are indexed INSIDE '
            f'another numeral</h3><p>Only the outer span is drawn. A nested '
            f'index means the floor counted one printed number more than '
            f'once, so <code>n_total</code> is high by that much.</p></div>')

    if not gaps:
        gaps.append('<div class="gap" style="border-left-color:var(--ok)">'
                    '<h3>No bookkeeping gaps of the kinds this page checks</h3>'
                    '<p>That is a statement about four specific checks, not a '
                    'claim that the register is complete.</p></div>')

    src_line = (f"read from <b>{_esc(text_source)}</b>" if text_source
                else "<b>no source could be read</b> -- which is UNKNOWN, not "
                     "an absence of text")

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Register &middot; {_esc(paper_id)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>{_CSS}</style></head><body>
<header>
<h1>Value register, drawn on the paper</h1>
<p class="sub">{_esc(paper_id)} &middot; body text {src_line} &middot;
{n_ok:,} numeral highlights placed</p>
<p class="floor"><b>Everything here is a lower bound.</b>
{_esc(register.get('is_a_floor') or '')}</p>
</header>
<nav>
<button class="on" data-p="p-sum">Summary</button>
<button data-p="p-gap">Gaps</button>
<button data-p="p-tab">Tables</button>
<button data-p="p-txt">Body text</button>
</nav>
<main>
<div class="pane on" id="p-sum"><div class="grid">{cards}</div>
<h2>How to read this</h2>
<p style="max-width:74ch;font-size:.9rem">Three separate populations are drawn
here and they are <b>not</b> the same population. The <b>numerals</b> are every
numeric token in the body, found by scanning for digits, so that count cannot be
silently incomplete. The <b>groups</b> are what the typer could name. There is
no key joining a numeral to the prose group that consumed it, so this page does
not draw that join -- a numeral is coloured by its own class only.</p>
<p style="max-width:74ch;font-size:.9rem">On the <b>Tables</b> tab, an unmarked
cell is not a clean cell: it is a cell no register group claimed.</p>
<div class="legend">
<span class="k-ok">checked</span><span class="k-none">no applicable tool</span>
<span class="k-bad">silent / not considered</span>
<span class="k-stat">numeral: statistic</span>
<span class="k-unc">numeral: unclassified</span>
<span class="k-amb">shared column label</span></div>
</div>
<div class="pane" id="p-gap"><h2>What this paper's register could not do</h2>
{"".join(gaps)}</div>
<div class="pane" id="p-tab"><h2>Tables, tinted by disposition</h2>
{_tables_html(tables, idx, amb_tables)}</div>
<div class="pane" id="p-txt"><h2>Body text, with every indexed numeral marked</h2>
<p class="meta">Hover any highlight for its class and why. Unhighlighted digits
are numerals the floor did not index -- if you find one, that is a real gap.</p>
<pre class="body">{marked}</pre></div>
</main>
<script>{_JS}</script></body></html>"""


def build(paper_dir: Path, review_dir: Path | None = None,
          out: Path | None = None) -> Path:
    """Write the inspector for one paper. Returns the path written."""
    from .extraction import jats
    from . import prepass

    paper_dir = Path(paper_dir)
    review_dir = Path(review_dir) if review_dir else _latest_review(paper_dir)
    reg_path = review_dir / "value_register.json" if review_dir else None
    register: dict = {}
    if reg_path and reg_path.exists():
        try:
            register = json.loads(reg_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            register = {}

    try:
        text, src = jats.paper_text_with_source(paper_dir)
    except Exception:                                        # noqa: BLE001
        text, src = "", None
    try:
        tables = list(prepass.paper_tables(paper_dir, include_supplements=True))
    except Exception:                                        # noqa: BLE001
        tables = []

    out = Path(out) if out else (review_dir or paper_dir) / "register_view.html"
    out.write_text(render(register, text, src, tables, paper_dir.name),
                   encoding="utf-8")
    return out


def _latest_review(paper_dir: Path):
    """The most recent CURRENT `forensic_review*` directory that has a register.

    NOT BY MTIME, AND THAT IS A CORRECTION. This sorted on `st_mtime`, which
    dates the file rather than the run. Measured 2026-08-29: all 15 archived run
    directories under `high_value_pdfs_to_run_on/` carry an mtime of 2026-08-22
    from a bulk copy, while their own recorded `git_sha` values span 08-11 to
    08-16 -- so mtime ordering put a two-week-old run at the top and called it
    latest. `runs.run_date` reads the run's own `analysed_at` instead.

    It also refuses a run older than the horizon rather than returning it as the
    best available: a register from code that no longer exists is not a view of
    this system, and reading one is how a fixed defect gets rediscovered.
    """
    from . import runs as _runs

    part = _runs.current_runs(paper_dir)
    cands = [d for d in part["current"] if (d / "value_register.json").exists()]
    return cands[0] if cands else None
