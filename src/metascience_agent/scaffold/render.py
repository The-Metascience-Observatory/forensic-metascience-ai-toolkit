"""The human view of the account -- and the VERIFICATION INSTRUMENT.

Greg (2026-09-05): the readable form is necessary, not optional. "For
developing the tool, I need a means of actually verifying that any 'machine
food' version is actually correct", and the end user "will have the same concern
if they don't see the scaffold in a human-tractable version." So this rendering
is designed to one acceptance test: CAN A READER CONFIRM THIS ELEMENT AGAINST
THE PAPER IN UNDER A MINUTE? Every element therefore carries its provenance
beside it -- a page number and a short verbatim quote, or a table cell address --
so that checking is a lookup, not a hunt. If a fact is in the JSON but not
visible here, it is unverifiable in practice; section 17 lists what this form
cannot show, so that the gap is stated rather than hidden.

It is a PROJECTION of the account's rows, never a copy: everything printed is
looked up by id from the same JSON, so the two cannot disagree. Organised the
way the paper is -- background, subjects and procedures, the statistical
statement, one block per study, then the variable table, the tables as read,
the figures, the claims, the gaps, the text repairs, the completeness measure
and the residual list, the read-only check census, and the checks that were run.
"""

from __future__ import annotations

from typing import Any

from . import applicability as _app
from . import codestamp as _codestamp
from . import coverage as _coverage


def _esc(s: Any) -> str:
    return str("" if s is None else s).replace("|", "\\|").replace("\n", " ")


def _q(s: Any, n: int = 160) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n - 3] + "..."


def _fmt(v: Any) -> str:
    return "not stated" if v in (None, "") else str(v)


def _pg(p: Any) -> str:
    return f"p.{p}" if p else "p.?"


def _where(rec: Any) -> str:
    """The location handle: a page on a PDF source, `\u00a7 heading` on an XML/HTML
    source that has no pages, `p.?` when neither is known. Accepts a record
    carrying `page`/`section`, or a bare page number."""
    if not isinstance(rec, dict):
        return _pg(rec)
    if rec.get("page"):
        return f"p.{rec['page']}"
    if rec.get("section"):
        return f"\u00a7 {_esc(_q(rec['section'], 40))}"
    return "p.?"


def _prov(rec: Any, quote: Any, n: int = 120) -> str:
    """The provenance cell: location handle and a short verbatim quote."""
    q = _q(quote, n)
    return f"{_where(rec)} \u201c{_esc(q)}\u201d" if q else _where(rec)


def _nloc(g: dict) -> dict:
    """A group's n-quote location, in the shape `_where` reads."""
    return {"page": g.get("n_page"), "section": g.get("n_section")}


def _dir(c: dict) -> str:
    d, w = c.get("direction"), c.get("direction_words")
    if not d or d == "not_stated":
        return f" ({_esc(w)})" if w else ""
    return f" ({d}{': ' + _esc(w) if w else ''})"


def _supp_str(account: dict) -> str:
    supps = account.get("supplements_referenced", []) or []
    if not supps:
        return "none"
    tag = {True: "on disk", False: "not on disk", None: "availability unknown"}
    return "; ".join(f"{s.get('label')} [{tag.get(s.get('available'), 'availability unknown')}]"
                     for s in supps)


def supplements_served_line(doc: dict) -> str:
    """What of each supplement the passes were served, as served-of-available.

    A supplement read whole and a supplement read to 12% of itself used to look
    identical in the account: the reader's cap left a marker sentence inside the
    served text and no number anywhere. Printed per file, with the ratio, so a
    reader deciding whether to trust a coverage figure over a supplement can see
    what that figure was computed over.
    """
    read = doc.get("supplements_read") or []
    withheld = [r for r in read if not r.get("served")]
    spans = doc.get("supplement_spans") or []
    if not spans and not withheld:
        return "no supplement prose served."
    parts = []
    for r in withheld:
        parts.append(f"`{r.get('file')}` **NOT SERVED** -- role `{r.get('role')}`, "
                     f"{(r.get('n_chars_available') or 0):,} chars: {r.get('why')}")
    for sp in spans:
        avail = sp.get("n_chars_available")
        ratio = sp.get("served_of_available")
        if avail is None or ratio is None:
            parts.append(f"`{sp.get('file')}` {sp.get('n_chars', 0):,} chars (extent unknown)")
        elif sp.get("truncated"):
            parts.append(f"`{sp.get('file')}` **{sp.get('n_chars', 0):,} of {avail:,} chars "
                         f"({ratio:.0%}) -- TRUNCATED by the reader's cap**")
        else:
            parts.append(f"`{sp.get('file')}` {sp.get('n_chars', 0):,} of {avail:,} chars (whole)"
                         + (f", role `{sp['role']}`" if sp.get("role") else ""))
    return "Supplement prose served: " + "; ".join(parts) + "."


def _short(vid: Any) -> str:
    return str(vid or "").split(":")[-1] if vid else "--"


def _values_for_study(account: dict, sid: str) -> list[dict]:
    return [v for v in account["values"] if (v.get("coordinate") or {}).get("study_id") == sid]


def _pivot(values: list[dict], study: dict, variables: dict) -> list[str]:
    """Table values pivoted back into the paper's axes: rows variable x statistic,
    columns (group / phase). Each column names the source table so the reader
    checks it against the printed table directly."""
    groups = {g["id"]: g["label"] for g in study.get("groups", [])}
    phases = {p["id"]: p["label"] for p in study.get("phases", [])}
    cols: list[tuple] = []
    for v in values:
        c = v["coordinate"]
        key = (c.get("group_id"), c.get("phase_id"))
        if key not in cols:
            cols.append(key)
    rows: dict[tuple, dict[tuple, str]] = {}
    tables = sorted({v["location"].get("table_id") for v in values})
    for v in values:
        c = v["coordinate"]
        rk = (v.get("variable_id"), v["statistic"])
        rows.setdefault(rk, {})[(c.get("group_id"), c.get("phase_id"))] = v["printed"]
    head = "| variable | statistic | " + " | ".join(
        f"{_esc(groups.get(g, g or 'all'))}" + (f" / {_esc(phases.get(p, p))}" if p else "")
        for g, p in cols) + " |"
    out = [f"Values below are the cells of {', '.join(tables)} at this study's coordinates, "
           f"as printed; verify against the printed table. Dispersion column named as the "
           f"reading typed it (`dispersion_unstated` = the paper does not say SD or SEM).",
           "", head, "|---|---|" + "---|" * len(cols)]
    for (vid, stat), cells in rows.items():
        vname = (variables.get(vid) or {}).get("name", vid or "(no variable)")
        out.append(f"| {_esc(vname)} | {stat} | " + " | ".join(_esc(cells.get(c, "")) for c in cols) + " |")
    return out


def _prose_rows(values: list[dict], variables: dict) -> list[str]:
    out = ["| value (printed) | statistic | variable | group / phase | where | quote |",
           "|---|---|---|---|---|---|"]
    for v in values:
        c = v.get("coordinate") or {}
        where = f"{_where(v)} {v.get('location', {}).get('kind', '')}"
        flag = "" if v.get("printed_in_quote", True) else " **[printed value NOT in its quote]**"
        vq = v.get("quote_verified")
        vflag = "" if vq in ("verbatim", "cell", None) else f" [{vq}]"
        out.append(f"| **{_esc(v['printed'])}**{(' ' + _esc(v['units'])) if v.get('units') else ''}{flag} | "
                   f"{v['statistic']} | {_short(v.get('variable_id'))} | "
                   f"{_short(c.get('group_id'))}{(' / ' + _short(c.get('phase_id'))) if c.get('phase_id') else ''}"
                   f"{' (all groups)' if v.get('applies_to_all_groups') else ''} | {where} | "
                   f"\u201c{_esc(_q(v.get('quote'), 140))}\u201d{vflag} |")
    return out


def _by_source_str(comp: dict) -> str:
    """The floor's split, in words, for every place a total is printed."""
    bs = comp.get("numerals_by_source") or {}
    return ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in sorted(bs.items())) or "not split"


def _structure_lines(account: dict) -> list[str]:
    """Section 1. WHICH DECOMPOSITION THIS ACCOUNT SELECTED FROM, and on what
    authority: the version and its status, whether a second reader has been over
    it, whether the served document is still the one it was read from, and what
    the closed vocabulary refused. A reader who wants to know why a value carries
    the variable id it carries starts here."""
    st = account.get("structure")
    L = ["## 1. Structure", ""]
    if not st:
        L += ["This account was assembled WITHOUT a structural account: passes 1 and 2 "
              "decomposed the paper in this run, and no downstream pass selected from a "
              "fixed vocabulary. Two runs of this paper may therefore disagree about the "
              "studies, groups and variables themselves, and every id below is this run's "
              "own (D43). `scaffold/structure.json` is written on the next run.", ""]
        return L
    ids = st.get("ids") or {}
    adj = st.get("adjudication") or {}
    L.append(f"**Version {st.get('version')}, status `{st.get('status')}`**, sha256 "
             f"`{str(st.get('sha256'))[:16]}`"
             + (f", frozen {st.get('frozen_at')}" if st.get("frozen_at") else ", not frozen")
             + ". The studies, groups, phases, variables and levels named anywhere in this "
             "account are this file's, and no pass after it may add one.")
    L.append("")
    if st.get("adjudicated"):
        L.append(f"Adjudicated: {adj.get('rounds')} round(s), {adj.get('applied')} correction(s) "
                 f"applied, {adj.get('skipped')} skipped, {adj.get('conflicts')} conflict(s) "
                 "recorded (a disagreement the evidence does not settle is kept as a conflict, "
                 "not resolved).")
    else:
        L.append("**UNADJUDICATED.** No second reader has been over this decomposition: the "
                 "studies, variables and levels below are one model's reading of the paper, "
                 "frozen so that everything downstream selects from the same one. Freezing "
                 "buys consistency, not correctness.")
    L.append("")
    L.append("| ids declared | studies | groups | phases | variables | levels | tests |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    L.append(f"| n | {ids.get('studies')} | {ids.get('groups')} | {ids.get('phases')} | "
             f"{ids.get('variables')} | {ids.get('levels')} | {ids.get('tests')} |")
    L.append("")
    stale = st.get("stale_document")
    if not stale:
        L.append("Document: unchanged since the decomposition "
                 f"(`{str(st.get('document_sha256'))[:16]}`).")
    else:
        ch = stale.get("changed_by_source") or {}
        L.append("**STALE DOCUMENT.** This structure was read from "
                 f"`{str(stale['document_sha256_in_structure'])[:16]}` and the text served this "
                 f"run is `{str(stale['document_sha256_now'])[:16]}`. Nothing was re-decomposed "
                 "and nothing was re-read; every id above is the vocabulary of the earlier "
                 "document. Characters by source, then and now: "
                 + "; ".join(f"{_esc(k)} {v[0]} -> {v[1]}" for k, v in ch.items()) + ".")
    L.append("")
    cv = st.get("closed_vocabulary") or {}
    n_foreign = cv.get("unbound_foreign_id")
    if n_foreign is None:
        L.append("Closed vocabulary: not recorded for this account.")
    elif not n_foreign:
        L.append("Closed vocabulary: every id the readings and pass 3 emitted is a member of "
                 "this structure; none was refused.")
    else:
        L.append(f"Closed vocabulary: **{n_foreign} id(s)** emitted by a reading or by pass 3 "
                 "are not in this structure and were nulled; the text each was read as is kept "
                 "on the row (`<field>_as_read`) and the value is unbound rather than bound to "
                 "something the decomposition does not contain. By field: "
                 + ", ".join(f"{k} {v}" for k, v in (cv.get("by_field") or {}).items()) + ".")
        for ex in (cv.get("examples") or [])[:8]:
            L.append(f"- `{_esc(ex.get('id_as_read'))}` as {ex.get('field')} in {ex.get('in')}")
    L.append("")
    return L


def render(account: dict, text: str | None = None, checks: dict | None = None) -> str:
    """The human view of an account.

    `text` is the paper's served text when the caller has it. Section 0 is
    RECOMPUTED from the account either way (`coverage.for_rendering`); the text
    is what lets H2 be recomputed too rather than taken from the account, and a
    stored block written by other code is printed as stale, never as a number.

    `checks` is the checks bridge's own sidecar (`checks.json`) when one has
    been run. It is passed in rather than read out of the account, because
    nothing writes a verdict into the account: the account describes the paper,
    and section 16 is a separate document about what was done TO that
    description. Absent, section 16 says so.
    """
    L: list[str] = []
    p = account.get("paper", {})
    doc = account.get("document", {})
    src = doc.get("source", {})
    comp = account.get("completeness", {})
    variables = {v["id"]: v for v in account.get("variables", [])}
    prov = account.get("provenance") or {}

    L.append(f"# {p.get('title', 'Untitled')} -- scaffold account")
    L.append("")
    L.append(f"_Identity (title, journal, year, DOI) from: {p.get('identity_source', 'model reading')}._")
    L.append("")
    L.append(f"{', '.join(p.get('authors') or [])}. {p.get('journal') or ''} "
             f"{p.get('year') or ''}. DOI {p.get('doi') or 'not stated'}. "
             f"Population: {p.get('species_or_population') or 'not stated'}.")
    L.append("")
    L.append(f"Source: `{src.get('pdf')}`, {src.get('n_pages')} pages, {src.get('n_chars')} characters "
             f"of body text via {src.get('text_channel')}; {doc.get('repairs', {}).get('n_repairs', 0)} "
             f"logged glyph repairs (section 11); {len(doc.get('tables', []))} table(s), "
             f"{sum(f.get('n_panels', 0) for f in doc.get('figures', []))} figure panels in "
             f"{len(doc.get('figures', []))} figure(s), "
             f"{sum(1 for f in doc.get('figures', []) if f.get('image'))} with an image on disk; supplements referenced: "
             f"{_supp_str(account)}. Extracted {prov.get('run_at', '')} with model "
             f"`{prov.get('model', '')}`.")
    L.append("")
    L.append(supplements_served_line(doc))
    L.append("")
    _sf = doc.get("supplement_figures") or []
    if _sf:
        _by = {}
        for f in _sf:
            _by[f["supplement_file"]] = _by.get(f["supplement_file"], 0) + 1
        L.append("Images embedded in a Word supplement (inventoried, never read): "
                 + "; ".join(f"`{k}` {v}" for k, v in _by.items())
                 + ". Some are tables drawn as pictures, which contribute no cells to any count "
                   "here.")
        L.append("")
    # SECTION 0 IS THE HEADLINE, AND THE FLOOR IS NOT IN IT (D34, Greg
    # 2026-09-06). The numeral floor used to stand here, which read as the
    # measure of this account; it is an INVENTORY and now sits under section 11
    # saying so. What a reader should judge the account by is table cells
    # placed, statistic-bearing sentences covered and declared variables with
    # values -- each with its split, none of them the floor.
    L += _coverage.render_lines(_coverage.for_rendering(account, text))
    L.append("## How to verify this account")
    L.append("")
    L.append("Every element below carries a location -- a page number on a PDF source, a section heading "
             "(marked \u00a7) on an XML/HTML source, which has no pages -- and a short verbatim quote (or a table cell "
             "address). To check one: open the PDF at the page, find the quote, and confirm that the "
             "element says what the quote says -- nothing more. `not stated` means the paper does not "
             "give it; that is a claim about the paper and can be checked too. Table values are the "
             "extracted cells themselves, never re-typed by a model; what a model supplied for a table "
             "is the READING in section 7 (which column is which group, which row is which variable, "
             "what the cells' form is), and that is what to check there. Quotes were located in the "
             "text automatically: `verbatim` means found as a contiguous span; anything else is marked "
             "inline. Section 16 says what this form cannot show.")
    L.append("")

    # 1 -----------------------------------------------------------------------
    # THE STRUCTURE COMES FIRST, above everything it governs. Every id in every
    # section below is drawn from it, so a reader who does not know which
    # decomposition this account selected from cannot read the rest.
    L += _structure_lines(account)

    # 2 -----------------------------------------------------------------------
    bg = account.get("background", {})
    L.append("## 2. What the paper is about")
    L.append("")
    L.append(f"**Problem.** {bg.get('problem', '')}")
    L.append("")
    L.append(f"**Gap.** {bg.get('gap', '')}")
    L.append("")
    if bg.get("aims"):
        L.append("**Aims, as stated:**")
        L.append("")
        L.append("| aim | quote |")
        L.append("|---|---|")
        for a in bg["aims"]:
            L.append(f"| {_esc(a['text'])} | \u201c{_esc(_q(a.get('quote'), 200))}\u201d |")
        L.append("")
    if bg.get("prior_findings"):
        L.append("| prior finding the paper builds on | cited as |")
        L.append("|---|---|")
        for pf in bg["prior_findings"]:
            L.append(f"| {_esc(pf.get('statement'))} | {_esc(pf.get('cited_as'))} |")
        L.append("")

    # 2 -----------------------------------------------------------------------
    sub = account.get("subjects", {})
    L.append("## 3. Subjects and procedures")
    L.append("")
    # ONLY WHAT THE PAPER FILLED. Printing `Species not stated` for a study of
    # community coalitions reads as a gap; it is a vocabulary mismatch.
    filled = [(k.replace("_", " "), sub.get(k)) for k in
              ("population", "unit_of_analysis", "setting", "recruitment", "eligibility",
               "species", "strain", "sex", "age", "supplier", "housing")
              if sub.get(k) not in (None, "")]
    L.append(("; ".join(f"{k} {_esc(v)}" for k, v in filled) or "no subject descriptor stated")
             + f". Total n stated anywhere: {sub.get('total_n_stated')}.")
    L.append("")
    L.append(f"> {_q(sub.get('quote'), 300)}")
    L.append("")
    pop = [v for v in account.get("values", []) if v.get("source") == "population"]
    if pop:
        L.append("| population descriptor | printed | where | quote |")
        L.append("|---|---|---|---|")
        for v in pop:
            L.append(f"| {_esc(v['location'].get('name'))} | **{_esc(v['printed'])}**"
                     f"{(' ' + _esc(v['units'])) if v.get('units') else ''} | {_where(v)} | "
                     f"\u201c{_esc(_q(v.get('quote'), 120))}\u201d |")
        L.append("")
    L.append("| procedure | Methods section | scored blind (stated) | summary |")
    L.append("|---|---|---|---|")
    for pr in account.get("procedures", []):
        L.append(f"| `{pr['id']}` {_esc(pr['name'])} | {_esc(pr.get('section_heading'))} | "
                 f"{_fmt(pr.get('scored_blind'))} | {_esc(_q(pr.get('summary'), 200))} |")
    L.append("")
    params = [v for v in account.get("values", []) if v.get("source") == "methods_parameter"]
    if params:
        L.append("**Design parameters (fixed settings), as printed:**")
        L.append("")
        L.append("| procedure | parameter | printed | where | quote |")
        L.append("|---|---|---|---|---|")
        for v in params:
            loc = v.get("location") or {}
            L.append(f"| {_short(loc.get('procedure_id'))} | {_esc(loc.get('name'))} | **{_esc(v['printed'])}**"
                     f"{(' ' + _esc(v['units'])) if v.get('units') else ''} | {_where(v)} | "
                     f"\u201c{_esc(_q(v.get('quote'), 120))}\u201d |")
        L.append("")

    # 3 -----------------------------------------------------------------------
    sa = account.get("statistical_analysis", {})
    L.append("## 4. Statistical analysis, as stated")
    L.append("")
    if account.get("phases"):
        L.append("Paper-level occasions (every study runs on them unless it lists its own): "
                 + "; ".join(f"`{ph['id']}` {_esc(ph.get('label'))} ({_esc(ph.get('when'))})"
                             for ph in account["phases"]))
        L.append("")
    L.append(f"> {_q(sa.get('methods_quote'), 500)}")
    L.append("")
    L.append(f"- Tests named: {', '.join(sa.get('tests_named') or []) or 'none'}")
    L.append(f"- Which test for which experiment stated in the main text: "
             f"{sa.get('test_to_experiment_mapping_in_main_text')}")
    L.append(f"- Alpha declared in words: {_fmt(sa.get('alpha_declared'))}"
             + (f" -- \u201c{_q(sa.get('alpha_quote'), 120)}\u201d" if sa.get("alpha_quote") else ""))
    for l in sa.get("significance_legend", []):
        L.append(f"- Legend `{l['marker']}` = P<{_fmt(l.get('threshold'))} -- \u201c{_q(l.get('quote'), 100)}\u201d")
    L.append(f"- Detailed statistics said to be in: {_fmt(sa.get('detailed_statistics_location'))}")
    L.append("")

    # 4 -----------------------------------------------------------------------
    L.append("## 5. Studies")
    L.append("")
    cmps_by_study: dict[str, list[dict]] = {}
    for c in account.get("comparisons", []):
        cmps_by_study.setdefault(c.get("study_id"), []).append(c)
    claims_by_study: dict[str, list[str]] = {}
    for cl in account.get("claims", []):
        for sid in cl.get("study_ids", []):
            claims_by_study.setdefault(sid, []).append(cl["id"])
    for s in account.get("studies", []):
        L.append(f"### `{s['id']}` -- {s['label']}")
        L.append("")
        L.append(f"**Aim.** {s.get('aim')}")
        rep = "; ".join(f"{r['label']}{(' ' + ''.join(r.get('panels') or [])) if r.get('panels') else ''}"
                        for r in s.get("reported_in", []))
        L.append(f"**Reported in.** {rep}. **Results section.** {s.get('section_heading')}.")
        L.append(f"**Design.** {s.get('design_type')} -- {s.get('design_description')}")
        if any(g.get("n_printed") for g in s.get("groups", [])):
            n_line = "per group, as printed in the group table below"
        elif s.get("n_range_printed"):
            n_line = (f"printed only as a range across groups: **{s['n_range_printed']}** -- "
                      f"\u201c{_q(s.get('n_range_quote'), 100)}\u201d")
        else:
            n_line = "**NOT STATED**"
        L.append(f"**Sample size.** {n_line}.")
        L.append("")
        L.append("| group | label | n (printed) | n quote | factor levels |")
        L.append("|---|---|---|---|---|")
        for g in s.get("groups", []):
            lv = ", ".join(f"{_short(a['variable_id'])}={_short(a['level_id'])}" for a in g.get("assignments", []))
            L.append(f"| `{g['id']}` | {_esc(g['label'])} -- {_esc(_q(g.get('description'), 80))} | "
                     f"{_fmt(g.get('n_printed'))} | {_prov(_nloc(g), g.get('n_quote'), 80) if g.get('n_quote') else '--'} | "
                     f"{_esc(lv) or '--'} |")
        L.append("")
        if s.get("phases"):
            L.append("Phases: " + "; ".join(f"`{ph['id']}` {ph['label']} ({ph.get('when')})" for ph in s["phases"]))
            L.append("")
        L.append("Outcomes: " + (", ".join(f"`{v}`" for v in s.get("outcome_variable_ids", [])) or "none bound"))
        L.append("")
        sv = _values_for_study(account, s["id"])
        tv = [v for v in sv if v["source"] == "table"]
        pv = [v for v in sv if v["source"] != "table"]
        L.append("**Values located at this study's coordinates**")
        L.append("")
        if tv:
            L += _pivot(tv, s, variables)
            L.append("")
        if pv:
            L += _prose_rows(pv, variables)
            L.append("")
        if not sv:
            has_fig = any(r.get("kind") == "figure" for r in s.get("reported_in", []))
            L.append("_No value in the text is located at this study's coordinates"
                     + (": its results are drawn in a figure whose bars are not in the text, and the caption gives only n._"
                        if has_fig else ". Its results are reported elsewhere (a table not yet read, a supplement) or "
                        "only in words._"))
            L.append("")
        cm = cmps_by_study.get(s["id"], [])
        if cm:
            L.append("**Comparisons reported**")
            L.append("")
            L.append("| id | outcome | contrast | result | test named | stat / df / p (printed) | threshold | where | quote |")
            L.append("|---|---|---|---|---|---|---|---|---|")
            for c in cm:
                sdp = " / ".join(_fmt(c.get(k)) for k in ("statistic_printed", "df_printed", "p_printed"))
                vq = c.get("quote_verified")
                vflag = "" if vq == "verbatim" else f" [{vq}]"
                L.append(f"| `{_short(c['id'])}` | {_short(c.get('outcome_variable_id'))} | "
                         f"{_esc(_q(c['contrast'].get('description'), 90))} | {c.get('significance')}"
                         f"{_dir(c)} | "
                         f"{_fmt(c.get('test_type_stated'))} | {sdp} | {_fmt(c.get('p_threshold'))} | "
                         f"{_where(c)} {_esc(c.get('reported_in_kind') or '')} {_esc(c.get('reported_in'))} | "
                         f"\u201c{_esc(_q(c.get('quote'), 140))}\u201d{vflag} |")
            L.append("")
        if s.get("result_summary_quotes"):
            L.append("**Found (authors' words):**")
            for q in s["result_summary_quotes"]:
                L.append(f"> {_q(q, 400)}")
            L.append("")
        if s.get("interpretation_quotes"):
            L.append("**Interpreted as:**")
            for q in s["interpretation_quotes"]:
                L.append(f"> {_q(q, 400)}")
            L.append("")
        if claims_by_study.get(s["id"]):
            L.append("Claims resting on this study: " + ", ".join(f"`{c}`" for c in claims_by_study[s["id"]]))
            L.append("")

    # 5 -----------------------------------------------------------------------
    L.append("## 6. Variables")
    L.append("")
    L.append("Bounds and steps are licensed only by the quote in the last column: `stated` means the "
             "paper prints the numeral, `definitional` means it follows from the paper's own definition, "
             "`not stated` means neither.")
    L.append("")
    L.append("| id | name | role | kind | units | bounds | per-subject step | derivation | levels | evidence |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for v in account.get("variables", []):
        b = v.get("bounds") or {}
        bstr = (f"{_fmt(b.get('lower'))} to {_fmt(b.get('upper'))} ({b.get('source')})"
                if b.get("source") != "not_stated" else "not stated")
        g = v.get("granularity") or {}
        step = _fmt(g.get("per_subject_step"))
        if g.get("basis") and g.get("per_subject_step") is not None:
            step += f" ({_q(g['basis'], 60)})"
        lv = ", ".join(f"{l.get('label')}" for l in v.get("levels", [])[:8])
        if len(v.get("levels", [])) > 8:
            lv += f" (+{len(v['levels']) - 8})"
        vq = v.get("quote_verified")
        vflag = "" if vq == "verbatim" else f" [{vq}]"
        L.append(f"| `{v['id']}` | {_esc(v['name'])} | {v['role']} | {v['kind']} | "
                 f"{_esc(_fmt(v.get('units')))}{' (not stated)' if v.get('units_source') == 'not_stated' and v.get('units') else ''} | "
                 f"{_esc(bstr)} | {_esc(step)} | {_esc(_q(v.get('derivation'), 90))} | "
                 f"{_esc(lv)} | {_prov(v, v.get('quote'), 110)}{vflag} |")
    L.append("")

    # 6 -----------------------------------------------------------------------
    L.append("## 7. Tables, as read")
    L.append("")
    L.append("The cells are the extractor's; the reading (which column is which coordinate, which row "
             "is which variable, what form the cells take) is the model's, and is what to verify here.")
    L.append("")
    for t in doc.get("tables", []):
        reading = next((r for r in account.get("table_readings", []) if r["table_id"] == t["id"]), None)
        L.append(f"### `{t['id']}` ({_where(t)}) {t.get('caption') or t['label']}")
        L.append("")
        L.append(f"{t['n_cells']} cells; {len(t['row_labels'])} row labels; {len(t['col_labels'])} "
                 f"column labels; header depth {t.get('n_header_rows')}; row sections: "
                 f"{'; '.join(s['label'] for s in t.get('sections', [])) or 'none'}; footnotes: "
                 f"{'; '.join(str(f) for f in t.get('footnotes', [])) or 'none'}.")
        L.append("")
        if (t.get("reconstruction") or {}).get("status") == "verified":
            v = (t.get("reconstruction") or {}).get("verification") or {}
            L.append(f"Read by a model from the rendered table and VERIFIED by the walker ({v.get('n_walker_tokens')} "
                     f"digit runs conserved): {v.get('n_entries')} entries in {v.get('n_cells_read')} cells, "
                     f"{v.get('n_sections')} banner(s); the values and their variables, levels and groups are the "
                     "entries in section 8b. No pass-3 column map is needed for this table.")
            L.append("")
        # A DISCARDED READING IS A FACT ABOUT THIS TABLE, not a silence: it is
        # what makes the cells below the walker's rather than a reading's.
        sub = ((t.get("reconstruction") or {}).get("substitution")) or {}
        if sub.get("happened"):
            cost = sub.get("reading_cost_usd")
            L.append("**A reading of this table was bought and DISCARDED.** "
                     f"{sub.get('n_entries_discarded')} entries in {sub.get('n_cells_discarded')} cells"
                     + (f", ${float(cost):.2f}" if cost else "")
                     + (" (reused from an earlier run, not re-bought)"
                        if sub.get("reading_reused") and not cost else "")
                     # NAME THE INSTRUMENT ONLY WHERE ONE RAN. A block that never
                     # came back is refused before any conservation count, so
                     # `basis` is absent and saying which pool it was checked
                     # against would be a false sentence.
                     + (f", refused by the conservation check over the {sub['basis']}: "
                        if sub.get("basis") else ", refused: ")
                     + _esc("; ".join(sub.get("why") or [])[:400])
                     + f". The {sub.get('n_walker_cells_used_instead')} walker cells were kept instead, so "
                     + f"{sub.get('consequence')}. The discarded reading is still on disk at "
                     + f"`{_esc('; '.join(sub.get('reading_kept_at') or []))}`.")
            L.append("")
        if reading:
            L.append(f"n per column stated by the table: **{reading.get('n_per_column_stated')}**. "
                     f"{reading.get('n_note') or ''}")
            L.append("")
            L.append("| column label (as extracted) | study | group | phase |")
            L.append("|---|---|---|---|")
            for c in reading.get("column_map", []):
                L.append(f"| {_esc(c['col_label'])} | {_short(c.get('study_id'))} | {_short(c.get('group_id'))} | {_short(c.get('phase_id'))} |")
            L.append("")
            L.append("| row label (as extracted) | variable | statistic form | dispersion stated where | note |")
            L.append("|---|---|---|---|---|")
            for r in reading.get("row_map", []):
                L.append(f"| {_esc(r['row_label'])} | {_short(r.get('variable_id'))} | {r.get('statistic_form')} | "
                         f"{_esc(_fmt(r.get('dispersion_stated_where')))} | {_esc(r.get('note') or '')} |")
        else:
            L.append("_No reading was produced for this table; its cells are unparsed._")
        unp = [u for u in account.get("unparsed_cells", []) if u.get("table_id") == t["id"]]
        L.append("")
        L.append(f"Cells parsed into values: {t['n_cells'] - len(unp)} of {t['n_cells']}."
                 + (" Unparsed: " + "; ".join(f"r{u['row']}c{u['col']} `{u['raw']}` ({u['why']})" for u in unp[:12])
                    if unp else ""))
        L.append("")

    # 8 -----------------------------------------------------------------------
    L.append("## 8. Figures")
    L.append("")
    L.append("| panel | page | study | y variable | groups | phases | n (caption) | error bar | caption fragment |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    fig_pages = {f["label"]: f.get("page") for f in doc.get("figures", [])}
    for fp in account.get("figure_panels", []):
        L.append(f"| {fp['figure']}{fp['panel']} | {_pg(fig_pages.get(fp['figure']))} | {_short(fp.get('study_id'))} | "
                 f"{_short(fp.get('y_variable_id'))} | {_esc(', '.join(_short(g) for g in fp.get('group_ids', [])))} | "
                 f"{_esc(', '.join(_short(p) for p in fp.get('phase_ids', [])))} | "
                 f"{_fmt(fp.get('n_printed'))} | {_fmt(fp.get('error_bar'))} | "
                 f"\u201c{_esc(_q(fp.get('caption_quote'), 100))}\u201d |")
    L.append("")
    L.append("Bar and point values are drawn, not printed; none is in this account (section 17).")
    L.append("")

    # 8 -----------------------------------------------------------------------
    # 7b ----------------------------------------------------------------------
    te = account.get("table_entries") or {}
    if te.get("entries"):
        L.append("## 8b. Table readings: variable-value entries")
        L.append("")
        L.append(f"{te['entries']} entries were read off the reconstructed tables, each naming its variable, "
                 "level, group and statistic in the paper's own words and carrying the cell it was printed in. "
                 f"Joined to the declared variables (one matcher, no guessing): {te.get('bound_to_a_variable')} "
                 "bound. By binding: " + ", ".join(f"{k} {v}" for k, v in (te.get("by_binding") or {}).items()) + ".")
        L.append("")
        L.append("| table | variable (as read) | level | group | statistic | value | cell | bound to |")
        L.append("|---|---|---|---|---|---|---|---|")
        shown = 0
        for t in doc.get("tables", []):
            for c in t.get("cells") or []:
                for e in c.get("entries") or []:
                    if shown >= 60:
                        break
                    shown += 1
                    L.append(f"| {_short(t['id'])} | {_esc(_q(e.get('variable'), 40))} | {_esc(_q(e.get('level'), 24)) or '--'} | "
                             f"{_esc(_q(e.get('group'), 24)) or '--'} | {e.get('statistic')} | {_esc(e.get('value'))} | "
                             f"{_esc(_q(c.get('raw'), 24))} | {_short(e.get('variable_id')) if e.get('variable_id') else e.get('binding')} |")
        if shown >= 60:
            L.append("| ... | first 60 shown; every entry is in `account.json` -> `document.tables[].cells[].entries` | | | | | | |")
        L.append("")

    L.append("## 9. Claims")
    L.append("")
    L.append("| id | page | where | kind | hedged | beyond sample | causal | rests on | text (verbatim) |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for c in account.get("claims", []):
        vq = c.get("quote_verified")
        vflag = "" if vq == "verbatim" else f" [{vq}]"
        L.append(f"| `{_short(c['id'])}` | {_where(c)} | {c.get('location')} | {c.get('kind')}"
                 f"{(' (restates ' + _short(c['demoted_from_comparison']) + ')') if c.get('demoted_from_comparison') else ''} | {c.get('hedged')} | "
                 f"{c.get('generalizes_beyond_sample')} | {c.get('causal')} | "
                 f"{_esc(', '.join(_short(s) for s in c.get('study_ids', [])))} | "
                 f"\u201c{_esc(_q(c.get('text'), 260))}\u201d{vflag} |")
    L.append("")

    # 9 -----------------------------------------------------------------------
    L.append("## 10. Gaps -- what the paper does not state")
    L.append("")
    by_kind: dict[str, list[dict]] = {}
    for g in account.get("gaps", []):
        by_kind.setdefault(g["kind"], []).append(g)
    for kind, rows in by_kind.items():
        L.append(f"- **{kind}** ({len(rows)}): " + "; ".join(
            _esc(", ".join(f"{k}={_short(v) if k.endswith('_id') else _q(v, 60)}" for k, v in r.items()
                           if k != "kind" and v)) for r in rows[:12])
            + (" ..." if len(rows) > 12 else ""))
    L.append("")

    # 10 ----------------------------------------------------------------------
    L.append("## 11. Repairs made to the text before reading it")
    L.append("")
    fa = doc.get("font_audit", {})
    L.append(f"Symbol-font audit of the PDF: {fa.get('n_suspects')} characters drawn from "
             f"{len([f for f in fa.get('fonts', []) if f.get('symbol_font')])} symbol fonts whose text-layer "
             f"code is a look-alike; {fa.get('n_repaired')} repaired from a human-verified glyph map "
             f"(`scaffold/glyph_map.json`, checked against `scaffold/font_suspects.png`); "
             f"{len(fa.get('unlocated', []))} not located in the body text (figure artwork); "
             f"{len(fa.get('unmapped', []))} unmapped and left as extracted.")
    L.append("")
    L.append("| font | text layer says | drawn glyph | n | pages | example line |")
    L.append("|---|---|---|---:|---|---|")
    repairs = (doc.get("repairs") or {}).get("repairs") or []
    intended: dict[tuple, str] = {}
    for r in repairs:
        # reason text carries "verified as '<x>'"; recover it for the table
        import re as _re
        m = _re.search(r"verified as '(.+?)' by", r.get("reason", ""))
        key = (r.get("reason", "").split("symbol font ")[-1].split(" on page")[0],)
        if m:
            intended.setdefault(key, m.group(1))
    for r in fa.get("suspects_by_glyph", []):
        L.append(f"| {r['font']} | `{_esc(repr(r['char']))}` ({r['codepoint']}) | "
                 f"{_esc(intended.get((r['font'],), '--'))} | {r['n']} | {', '.join(str(p) for p in r.get('pages', []))} | "
                 f"{_esc(_q(r['example'], 90))} |")
    L.append("")
    L.append("Each individual repair -- offset, before, after, reason -- is in `document.json` -> `repairs`.")
    if str(src.get("text_channel") or "").startswith(("xml", "html")):
        L.append(f"The text came from `{src.get('text_channel')}`, not from a PDF text layer, so no "
                 "font-map or glyph repair applies to it.")
    else:
        L.append("A PDF text layer can render the `\u00d7` of dimensions as `-` (`30.5 -24.1 -21.0`), "
                 "which invents minus signs; where that occurred it is among the repairs.")
    L.append("")

    # 12 (rendered before 14 so a reader meets the notes before the residual) --
    rv = account.get("review")
    if rv:
        L.append("## 12. A model's second reading (readings to verify, not computed facts)")
        L.append("")
        L.append(f"A model read this account against the paper (`{rv.get('model')}`, ${rv.get('cost_usd')}). "
                 "Everything in this section is that model's reading: a note is a claim to verify, a "
                 "spot-check verdict is one reader's judgement of one value. Nothing here changes the "
                 "counts above, which are computed without a model.")
        L.append("")
        L.append(f"**Overall.** {_esc(rv.get('overall'))}")
        L.append("")
        if rv.get("notes"):
            L.append("| severity | where | what looks wrong | the paper's evidence | what would settle it |")
            L.append("|---|---|---|---|---|")
            for n in rv["notes"]:
                L.append(f"| {n.get('severity')} | {_esc(_q(n.get('where'), 40))} | {_esc(_q(n.get('what'), 160))} | "
                         f"{_esc(_q(n.get('why'), 160))} | {_esc(_q(n.get('suggested_check'), 100)) or '--'} |")
            L.append("")
        if rv.get("unstable_readings"):
            L.append("**Readings the paper does not support, per the model:**")
            L.append("")
            L.append("| where | the account read | the paper says | confidence |")
            L.append("|---|---|---|---|")
            for u in rv["unstable_readings"]:
                L.append(f"| {_esc(_q(u.get('where'), 40))} | {_esc(_q(u.get('reading'), 100))} | "
                         f"{_esc(_q(u.get('paper_says'), 160))} | {u.get('confidence')} |")
            L.append("")
        bv = rv.get("spot_checks_by_verdict") or {}
        L.append(f"**Spot checks** on {rv.get('n_sampled')} sampled values: "
                 + ", ".join(f"{k} {v}" for k, v in sorted(bv.items())) + ".")
        L.append("")
        bad = [s for s in (rv.get("spot_checks") or []) if s.get("verdict") != "supported"]
        if bad:
            L.append("| value | verdict | evidence |")
            L.append("|---|---|---|")
            for s_ in bad:
                L.append(f"| `{_short(s_.get('value_id'))}` | {s_.get('verdict')} | {_esc(_q(s_.get('evidence'), 200))} |")
            L.append("")

    # 13 ----------------------------------------------------------------------
    adj = account.get("adjudication")
    if adj:
        L.append("## 13. Adjudicated corrections (a model's adjudication of two accounts; every one reversible)")
        L.append("")
        L.append(f"{adj.get('n_applied')} correction(s) applied to this account and {adj.get('n_skipped')} skipped, "
                 "each on the word of a model that read two independent accounts against the paper. A corrected "
                 "record keeps what it said before (`adjudications` on the record); nothing was deleted, and no "
                 "printed number, quote or count was changed.")
        L.append("")
        L.append("Both accounts came from the same pipeline and the same model, so where the two runs AGREE they "
                 "can be wrong together: agreement between two runs is reliability, not accuracy, and it is not "
                 "evidence that either reading is right. What a correction rests on is the anchor named beside it "
                 "-- what in the paper decided it, and whether that thing reaches the record it corrected.")
        L.append("")
        if adj.get("applied"):
            L.append("| target | field | from | to | anchor | evidence | item |")
            L.append("|---|---|---|---|---|---|---|")
            for a_ in adj["applied"]:
                anchor = a_.get("anchor_kind") or "not stated"
                if a_.get("anchor_table_id"):
                    anchor = f"{anchor} ({a_['anchor_table_id']})"
                L.append(f"| `{_short(a_['target'])}` | {a_['field']} | {_esc(a_.get('from'))} | {_esc(a_['to'])} | "
                         f"{_esc(anchor)} | {a_.get('evidence_kind')} | {_esc(_q(a_.get('item'), 120))} |")
            L.append("")
        if adj.get("skipped"):
            L.append("Skipped: " + "; ".join(f"{_esc(_q(s_.get('item'), 60))} ({_esc(s_.get('why'))})" for s_ in adj["skipped"][:20]))
            L.append("")

    # 11 ----------------------------------------------------------------------
    L.append("## 14. Inventory: the numeral floor, and the residual")
    L.append("")
    L.append("**This is an INVENTORY, not the headline coverage measure** (section 0 carries those). "
             "It exists for two jobs a headline number cannot do: digit conservation on a table -- every "
             "digit run the extractor read is in here, so a reading that invents or drops a number shows "
             "up -- and making an under-reading pass visible, because a pass that classifies less pushes "
             "numerals into `unaccounted` instead of leaving the score unchanged. A paper's numerals are "
             "not what a reader wants covered; its table cells, its statistic-bearing sentences and its "
             "declared variables are, and those are section 0.")
    L.append("")
    L.append("The denominator is ONE floor: every numeric token in the text outside the reference list "
             "and back matter (`numerals.index`) plus every cell of a table the text does not inline, "
             "article and supplement alike (`numerals.index_table_cells`), found without a model. The "
             f"split by source is given beside every total: {_by_source_str(comp)}. Each numeral ends in "
             "exactly one disposition; `unaccounted` is one of them and is listed in full.")
    L.append("")
    for k in ("numerals_in_scope", "numerals_by_source", "numerals_accounted", "share_accounted", "numerals_bound_to_a_value",
              "share_bound_to_a_value", "numerals_unaccounted", "values_total", "values_by_source",
              "values_with_variable", "share_values_with_variable", "values_with_study",
              "share_values_with_study", "values_with_study_and_group",
              "share_values_with_study_and_group",
              "values_with_full_coordinate", "share_values_with_full_coordinate",
              "values_with_full_coordinate_incl_phase",
              "share_values_with_full_coordinate_incl_phase", "studies_declaring_a_phase",
              "values_by_coordinate_source",
              "table_cells_total", "table_cells_unparsed", "comparisons_total", "comparisons_with_test_named",
              "comparisons_with_exact_p", "comparisons_with_threshold_only", "claims_total",
              "claims_linked_to_a_study", "studies_total", "variables_total", "quote_verification", "gaps_total",
              "sentences_in_argument_sections", "sentences_covered_by_a_quote", "share_sentences_covered"):
        L.append(f"- {k}: {comp.get(k)}")
    L.append("")
    # THE TWO COORDINATE DEFINITIONS ARE PRINTED WITH THE REASON THEY DIFFER, or
    # the redefined number reads as the old one improving (D47).
    if comp.get("full_coordinate_note"):
        L.append(f"_{comp['full_coordinate_note']}_")
        L.append("")
    gn = comp.get("groups_with_a_parsed_n") or {}
    if gn:
        L.append(f"- Groups with an n parsed from what the paper printed: {gn.get('with_n')} of "
                 f"{gn.get('groups')} ({', '.join(f'{k} {v}' for k, v in (gn.get('by_source') or {}).items())}). "
                 f"{gn.get('note', '')}")
        L.append("")
    L.append("By disposition: " + ", ".join(f"{k} {v}" for k, v in (comp.get("by_disposition") or {}).items()))
    L.append("")
    L.append("| section role | numerals | accounted | bound to a value |")
    L.append("|---|---:|---:|---:|")
    for role, d in (comp.get("by_role") or {}).items():
        L.append(f"| {role} | {d['n']} | {d['accounted']} | {d['value']} |")
    L.append("")
    curve = comp.get("gap_curve") or []
    if curve:
        L.append("### The gap, iteration by iteration")
        L.append("")
        L.append("The unplaced numerals are a work queue: after each pass the account is assembled, "
                 "the numerals still unplaced are served back in reading order with their sentences "
                 "and the scaffold in hand, and the model says where each belongs. The curve is the "
                 "result -- how much of the shortfall was method, and how much is left.")
        L.append("")
        L.append("| iteration | placed as a value | dispositioned (non-measurement) | ambiguous (candidates listed) | unplaced | value rows |")
        L.append("|---:|---:|---:|---:|---:|---:|")
        for g in curve:
            L.append(f"| {g['iteration']} | {g.get('placed', '')} | {g.get('dispositioned', '')} | "
                     f"{g.get('ambiguous', '')} | {g.get('unplaced', g.get('unexplained'))} | {g['values']} |")
        L.append("")
    amb = [r for r in account.get("accounting", []) if r["disposition"] == "ambiguous"]
    L.append(f"### Ambiguous numerals ({len(amb)}) -- the paper does not settle which coordinate")
    L.append("")
    for r in amb:
        cands = "; ".join(
            f"{_short(c.get('study_id'))}/{_short(c.get('group_id'))}/{_short(c.get('phase_id'))} "
            f"{_short(c.get('variable_id'))} {c.get('statistic') or ''} ({_q(c.get('why'), 60)})"
            for c in r.get("candidates", []))
        L.append(f"- `{r['printed']}` [{r.get('role')}] ...{_esc(_q(r.get('context'), 90))}... -- candidates: "
                 f"{_esc(cands)}. Would settle it: {_esc(_q(r.get('distinguisher'), 120))}")
    L.append("")
    un = [r for r in account.get("accounting", []) if r["disposition"] == "unaccounted"]
    L.append(f"### Unplaced numerals ({len(un)}) -- no coordinate in the scaffold fits")
    L.append("")
    for r in un:
        why = f" -- {_esc(_q(r.get('residual_note'), 90))}" if r.get("residual_note") else ""
        L.append(f"- `{r['printed']}` [{r.get('role')}] ...{_esc(_q(r.get('context'), 110))}...{why}")
    L.append("")
    other = [r for r in account.get("accounting", [])
             if r["disposition"] not in ("unaccounted", "ambiguous", "value", "duplicate_of_value",
                                         "coordinate_label", "citation_year")]
    if other:
        L.append(f"### Numerals accounted for as something other than a value ({len(other)})")
        L.append("")
        by_d: dict[str, list[dict]] = {}
        for r in other:
            by_d.setdefault(r["disposition"], []).append(r)
        for d, rows in by_d.items():
            L.append(f"- **{d}** ({len(rows)}): " + "; ".join(f"`{r['printed']}` ({_q(r.get('residual_note') or r.get('context'), 50)})" for r in rows[:15])
                     + (" ..." if len(rows) > 15 else ""))
        L.append("")

    sa_acc = account.get("sentence_accountability") or {}
    L.append("### Sentence accountability (claims are sentences, not numerals)")
    L.append("")
    L.append(f"Of {sa_acc.get('sentences')} sentences in the abstract, results and discussion, "
             f"{sa_acc.get('covered')} ({sa_acc.get('share_covered')}) overlap a quote this account carries "
             f"(a claim, a comparison, a value, a result or interpretation quote). The rest are listed so "
             f"that whether claim coverage needs its own per-sentence pass is a measurement.")
    L.append("")
    for role, d in (sa_acc.get("by_role") or {}).items():
        L.append(f"- {role}: {d['covered']} of {d['sentences']} sentences covered")
    L.append("")
    unc = sa_acc.get("uncovered") or []
    L.append(f"Uncovered sentences ({len(unc)}):")
    L.append("")
    for u in unc:
        L.append(f"- [{u['role']}] {_esc(u['sentence'])}")
    L.append("")
    tp = account.get("template_problems") or []
    L.append("### Design template problems")
    L.append("")
    if tp:
        L.append("A study whose declared design does not have the parts the design template requires; "
                 "either the design is mis-declared or a part is missing.")
        L.append("")
        for t in tp:
            L.append(f"- {_esc(t)}")
    else:
        L.append("None: every study's declared design has the groups, phases and numeric factor its template requires.")
    L.append("")

    # 12 ----------------------------------------------------------------------
    L.append("## 15. Check applicability census (read-only)")
    L.append("")
    L.append(_app.render_markdown(_app.census(account)))
    L.append("")

    # 12b ---------------------------------------------------------------------
    L.append("## 15b. Admission: what each value may be used for")
    L.append("")
    L.append("Every value carries one admission decision (`premise`), computed once by "
             "`scaffold/premises.py` and read by every consumer -- the census above, the "
             "checks below, the coverage headline. `provenance` says whether the paper is "
             "shown to print the number; `binding` says on whose word the value belongs to "
             "the variable it names; `descriptive` says whether the cell is a description "
             "of a measured variable at all. A value refused here is refused everywhere, "
             "which is the point: six readers used to decide this separately and disagreed.")
    L.append("")
    vals = [v for v in account.get("values", []) if isinstance(v.get("premise"), dict)]
    if not vals:
        L.append("Not stamped for this account.")
    else:
        def _tally(key):
            out: dict = {}
            for v in vals:
                out[str(v["premise"].get(key))] = out.get(str(v["premise"].get(key)), 0) + 1
            return ", ".join(f"`{k}`: {n}" for k, n in sorted(out.items(), key=lambda kv: -kv[1]))
        L.append(f"- **provenance** -- {_tally('provenance')}")
        L.append(f"- **binding** -- {_tally('binding')}")
        n_model = sum(1 for v in vals
                      if (v["premise"].get("descriptive") or {}).get("reports_model_output"))
        n_disputed = sum(1 for v in vals if v["premise"].get("disputed"))
        L.append(f"- **model output rather than a description** -- {n_model}")
        L.append(f"- **kind disputed elsewhere in this paper** -- {n_disputed}")
        L.append("")
        # THE LITERAL IS READ TWICE ON PURPOSE, AND A DISAGREEMENT IS THE
        # READER'S BUSINESS. `bind.read_literal` produced the account's own
        # `numeric`/`decimals`; the strict grammar in `premises.read_plain`
        # re-derives both, because a check that inherits the reader it is
        # checking proves nothing. Where the two disagree, neither is declared
        # right here.
        bad = [v for v in vals if (v["premise"].get("literals") or {}).get("agrees") is False
               and v["premise"].get("literal") is not None]
        if bad:
            L.append("**The two readings of a printed literal disagree** on "
                     f"{len(bad)} value(s). The account's own reading and the strict "
                     "grammar are deliberately two implementations of one rule; where "
                     "they differ, one of them is wrong about what the paper prints:")
            L.append("")
            L.append("| value | printed | strict grammar | the account |")
            L.append("|---|---|---|---|")
            for v in bad[:20]:
                lit = v["premise"]["literals"]
                L.append(f"| `{v['id']}` | `{_esc(_q(lit.get('printed'), 24))}` | "
                         f"{lit.get('bridge_value')} ({lit.get('bridge_decimals')} dp) | "
                         f"{lit.get('account_numeric')} ({lit.get('account_decimals')} dp) |")
            if len(bad) > 20:
                L.append(f"| ... | +{len(bad) - 20} more | | |")
            L.append("")
    L.append("")

    # 12c ---------------------------------------------------------------------
    # THE DOCKET FOR THE PAID PREMISE PASS, AND IT EXISTS FOR ONE SENTENCE: a
    # question that was never put is not a question the model answered "no" to.
    # Both end as an absent verdict, both leave the vocabulary's reading standing,
    # and only one of them means the run was short of money. A reader who cannot
    # tell them apart reads a truncated pass as a complete one, which is the
    # failure this section is here to make impossible.
    reading = account.get("premise_reading")
    if isinstance(reading, dict):
        L.append("## 15c. Premises a model was asked about, and what it cost")
        L.append("")
        n_ask = reading.get("n_asked")
        n_cand = reading.get("n_candidates")
        spent = reading.get("cost_usd")
        total = reading.get("cost_usd_total")
        reused = reading.get("n_calls_reused") or 0
        L.append(f"A model was asked {n_ask} of {n_cand} candidate passage(s) in "
                 f"{reading.get('n_calls')} call(s) (`{reading.get('model')}`, prompt "
                 f"`{reading.get('prompt_version')}`) and returned "
                 f"{len(reading.get('verdicts') or [])} verdict(s).")
        if reused:
            L.append(f"Cost: **${spent}** on this run, **${total}** to produce -- "
                     f"{reused} of {reading.get('n_calls')} call(s) were answered from a "
                     f"reply already bought for the identical prompt and cost nothing "
                     f"again.")
        else:
            L.append(f"Cost: **${spent}**.")
        L.append("")
        if reading.get("budget_exhausted"):
            scopes = [r for r in (reading.get("unasked") or []) if isinstance(r, dict)]
            n_var = len({r.get("variable_id") for r in scopes})
            L.append(f"> **THE BUDGET RAN OUT AND {reading.get('n_unasked_over_budget')} "
                     f"QUESTION(S) WERE NEVER PUT.** The per-paper budget is "
                     f"{reading.get('budget')} candidate(s); "
                     f"{reading.get('n_askable')} were askable. The run stopped asking "
                     f"rather than truncating a call, so nothing below is a partial "
                     f"answer -- but {len(scopes)} scope(s) over {n_var} variable(s) were "
                     f"not asked at all. **Every net that writes this record is a REFUSAL "
                     f"net: a verdict can only remove a check. So an unasked question is "
                     f"not a premise the model declined -- it is a check still RUNNING "
                     f"that the model might have withdrawn, and this pass is reduced "
                     f"coverage rather than a clean sweep.** Raise `--premise-budget` to "
                     f"ask them.")
            L.append("")
            L.append("| premise | variable | questions never put |")
            L.append("|---|---|---|")
            for r in scopes[:25]:
                vid = r.get("variable_id")
                L.append(f"| `{_esc(str(r.get('premise')))}` | "
                         f"{'paper-wide' if vid is None else '`' + _esc(str(vid)) + '`'} | "
                         f"{r.get('n_unasked')} |")
            if len(scopes) > 25:
                L.append(f"| ... | +{len(scopes) - 25} more scope(s) | |")
            L.append("")
        elif reading.get("budget") is not None:
            L.append(f"The per-paper budget ({reading.get('budget')} candidate(s)) was not "
                     f"reached, so every askable candidate was put to the model. An absent "
                     f"verdict below is a question asked and unanswered, never a question "
                     f"skipped for money.")
            L.append("")
    L.append("")

    # 13 ----------------------------------------------------------------------
    L.append("## 16. Checks run on the account's own premises")
    L.append("")
    if checks is None:
        L.append("Not run for this account. The bridge (`scaffold/checks.py`) costs nothing "
                 "-- it reads this account and the structure off disk and calls the tool "
                 "registry in process -- so its absence here means it was not asked for, "
                 "never that nothing was checkable. Section 15 says what would bind.")
    else:
        L.append(f"From `checks.json` (structure v{checks.get('structure_version')} "
                 f"{checks.get('structure_status')}, "
                 f"account {str(checks.get('account_sha256') or '')[:12]}, "
                 f"{_codestamp.describe(checks.get('code'))}). "
                 "The checks are a SIDECAR: nothing here is written back into the account, "
                 "so deleting every verdict loses nothing that was extracted.")
        L.append("")
        from . import checks as _checks
        L.append(_checks.render_markdown(checks))
    L.append("")

    # 14 ----------------------------------------------------------------------
    L.append("## 17. What this form cannot show")
    L.append("")
    L.append("- **Values that exist only in figure artwork.** Bar heights, error-bar lengths and "
             "plotted points are not in the text layer; this account records what each panel shows "
             "and the n its caption gives, never a read-off value.")
    L.append("- **Anything in supplements not available to the extraction** (listed in the header). "
             "Where the paper says its test statistics live there, every comparison shows "
             "`not stated` for statistic / df / p, and that is a fact about this extraction's inputs, "
             "not about the paper.")
    L.append("- **The correctness of an id binding is visible only as a label.** A group bound to the "
             "wrong dose level shows as the wrong level name in the group table; check the level "
             "against the group's quote, not against the id.")
    L.append("- **Character offsets** are in the JSON only; the page and quote here are the "
             "human-usable form of the same location.")
    L.append("- **Quote verification is against the repaired text**, so a quote can be `verbatim` here "
             "and differ from the raw PDF text layer by exactly the repairs in section 11.")
    L.append("")
    if account.get("integrity_problems"):
        L.append("## Integrity problems")
        L.append("")
        for pr in account["integrity_problems"]:
            L.append(f"- {pr}")
        L.append("")
    if account.get("problems"):
        L.append("## Problems recorded during extraction")
        L.append("")
        for pr in account["problems"]:
            L.append(f"- {_esc(pr)}")
        L.append("")
    return "\n".join(L)
