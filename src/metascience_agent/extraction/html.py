"""
Publisher HTML full-text extraction — the XML-not-available fallback.

Why this exists: a growing share of the corpus arrives as fetched
``.fulltext.html`` (fetchpdf's T2 tier) rather than JATS/Elsevier XML, and
until this module existed that HTML was invisible to the pipeline — never
read, never checked, never even mentioned to the model. See
:mod:`metascience_agent.extraction.jats` for why a dense cell grid beats a PDF
or markdown extraction for tables; everything there applies to HTML too, so
this module reuses its span-expansion/cell-building machinery directly
(``_expand``, ``_cells_from_grid``, ``_flatten_header``, ``_cell_text``,
``_local``) rather than re-deriving it — jats.py's helpers already operate
through the generic ElementTree element API (``.tag``/``.get``/``.text``/
``.tail``/iteration), which ``lxml.html``'s parse tree implements too.

The one problem XML extraction never had: **a fetched "full text" page can be
a landing page, cookie gate, or JS-rendered app shell that never contains the
article**, and it will look superficially plausible (a real title, a real
abstract, even a nav/metrics table with populated cells). This is why every
call here runs the page through ``fetchpdf``'s ``validate_t2`` FIRST — the
same check fetchpdf itself uses to decide whether to accept a fetch — and
refuses (structured error, not a crash or a false empty success) rather than
sweeping a cookie banner for statistics. See ``fetchpdf/retrieval/validate.py``
for the check's own reasoning and a documented, verified-open gap (a
correctly-identified page whose real body text never rendered).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .jats import (
    _HAS_DIGIT,
    fold_section_bands,
    _Counter,
    _cell_text,
    _cells_from_grid,
    _expand,
    _flatten_header,
    _local,
)

#: Tags whose entire subtree is chrome, never article content. Stripped
#: before both table discovery and text flattening. HTML has no equivalent to
#: JATS's closed tag vocabulary, so this is a a much shorter, coarser list —
#: it only needs to keep obviously-non-article machinery out, not model every
#: publisher template.
_CHROME_TAGS = ("script", "style", "nav", "header", "footer", "aside", "noscript", "form")

_TRUNCATION_NOTE = (
    "\n\n[TEXT TRUNCATED — call extract_html again with first_section/"
    "last_section to fetch the remaining sections]"
)


def find_html(paper_dir: str | Path) -> Path | None:
    """The paper's fetched HTML full text, if any passes the decoy check.

    Mirrors :func:`metascience_agent.extraction.jats.find_xml`'s narrow
    substring-exclusion convention deliberately, not the broader
    ``_SUPPLEMENTARY_RE`` regex ``agent.py`` uses for PDFs — this is a real
    behavioural choice, made for consistency with the XML-finder it sits next
    to in the source-priority chain, not an oversight.

    Unlike ``find_xml``, existence is not enough: a file can be present and
    still be a landing page. This is the ONE place that matters — callers
    (``_resolve_paper_sources``) treat whatever this returns as usable without
    re-checking, so a file that fails validation must come back as `None`
    here, indistinguishable from "nothing was ever fetched". That is what lets
    the XML→HTML→body.md+PDF priority chain fall through with no special-case
    fallback code; a `find_html` that only checked existence would silently
    defeat that design (a real bug once, caught by
    ``_resolve_paper_sources`` returning a decoy page as usable HTML).
    """
    paper_dir = Path(paper_dir)
    if not paper_dir.is_dir():
        return None
    preferred = paper_dir / f"{paper_dir.name}.fulltext.html"
    candidates = [preferred] if preferred.exists() else [
        x for x in sorted(paper_dir.glob("*.html"))
        if "supplementary" not in x.stem.lower()
    ]
    if not candidates:
        return None
    path = candidates[0]
    try:
        content = path.read_bytes()
    except OSError:
        return None
    if _validate_not_a_landing_page(path, content):
        return None
    return path


def _validation_error(html_path: Path, reason: str) -> dict[str, Any]:
    """The shared unreadable-format error shape, per supplements_read.py."""
    return {
        "error": f"HTML failed landing-page validation: {reason}",
        "unreadable_format": ".html",
        "text": "",
        "tables": [],
        "pages": [],
        "num_pages": 0,
        "pages_extracted": [],
        "truncated": False,
        "source_format": "html",
        "unit": "section",
        "article_meta": {},
        "n_tables": 0,
        "n_tables_image_only": 0,
        "warnings": [f"landing-page/decoy check failed: {reason}"],
        "normalizations": {},
    }


#: The floor an ARTICLE's extracted text must clear. Below this the page is not
#: the paper, whatever it is.
#:
#: MEASURED 2026-09-05 over every `*.html` sitting in a paper directory across
#: the Dropbox corpora (frame: a directory holding a `*.pdf` or `*.xml`,
#: excluding our own `forensic_review*` / `_bundle` / viewer output, which a
#: first pass wrongly swept in and which put a 41-character "real" page in the
#: sample). Extracted-article-text length separates cleanly:
#:
#:     decoys        194, 228, 228, 228, 228, 228
#:     real papers   2810 and up
#:
#: A 12x gap. 1,000 sits four-fold clear of both sides. The five at 228 are a
#: Cloudflare "Client Challenge. JavaScript is disabled in your browser."
#: interstitial saved as `<stem>.landing.html`; the 194 is a journal MASTHEAD
#: page (its visible text is 9,721 chars of "Fiziologichnyi Zhurnal is a
#: scientific journal issued by ...", so only the EXTRACTED-ARTICLE length
#: catches it, not a raw-visible-text floor).
#:
#: WHY THIS IS NOT A COVERAGE RISK. Refusing an HTML falls through to the XML
#: or PDF rung, so a false refusal costs nothing we had. Accepting a decoy costs
#: everything: MEASURED, 13 paper directories currently serve those 228
#: characters as the paper's full text, and this toolkit treats absent reported
#: data as a finding -- so the accusation lands on authors for our failed fetch.
_ARTICLE_TEXT_FLOOR = 1000


def article_text_too_short(text: str) -> str | None:
    """The reason this cannot be an article's text, or None.

    Deliberately a length test and nothing cleverer. The decoys have no single
    shared phrase -- a Cloudflare challenge, a Chinese captcha, a Portico stub
    and a journal masthead share only that none of them is a paper -- and a
    phrase list is the per-publisher-forever maintenance this project keeps
    finding at the bottom of its niggling problems.
    """
    n = len(" ".join((text or "").split()))
    if n >= _ARTICLE_TEXT_FLOOR:
        return None
    return (f"the extracted article text is {n} characters, below the "
            f"{_ARTICLE_TEXT_FLOOR}-character floor; the shortest real paper "
            "measured on this corpus was 2,810 and every decoy was under 230")


def manual_fetch_needed(paper_dir: "Path | str") -> dict | None:
    """`{reason, url, doi, path}` when this paper's HTML is a decoy, else None.

    EXISTS BECAUSE THE FIX IS A HUMAN, NOT A RETRY. A bot challenge is not
    something a fetcher can defeat and should not try to -- Greg's ruling,
    2026-09-05: prompt the operator and hand them the URL, which is a minimal
    demand set against being able to read the paper at all. This is the
    machine-readable half of that prompt, so a CLI can list every paper waiting
    on a person instead of the fact being buried in a warning.
    """
    paper_dir = Path(paper_dir)
    if not paper_dir.is_dir():
        return None
    cands = [x for x in sorted(paper_dir.glob("*.html"))
             if "supplementary" not in x.stem.lower()]
    if not cands:
        return None
    path = cands[0]
    try:
        content = path.read_bytes()
    except OSError:
        return None
    # ONE GATE. `_validate_not_a_landing_page` now applies the floor itself, so
    # asking it twice here would be a second copy of the rule.
    reason = _validate_not_a_landing_page(path, content)
    if reason is None:
        return None
    url, doi = _load_provenance_hints(path)
    # A URL IS THE WHOLE POINT OF THIS RECORD, so fall back to the DOI
    # resolver rather than handing the operator a None. `doi_from_slug` is the
    # project's one reader of the directory-name convention -- every `--` is a
    # `/`, and it carries the measurement explaining why replacing only the
    # first one broke 59 directories. Imported, not re-spelled.
    url_source = "provenance_url" if url else None
    prov_doi = bool(doi)
    if not doi:
        from ..paper_metadata import doi_from_slug
        doi = doi_from_slug(paper_dir.name)
        # `~` RESTORED TO `:`. `paper_ids.doi_dirname` encodes only `/`; the `~`
        # is the FETCHER sanitising a colon for the filesystem, and a DOI
        # essentially never contains a tilde while Kluwer-era DOIs
        # (`10.1023/A:1016270626439`) routinely contain a colon. Restoring a
        # character the filesystem destroyed is the sanctioned direction --
        # restore a distinction, never invent one -- and the alternative is
        # handing the operator a URL that resolves nowhere, which is worse than
        # handing them none. VERIFIED: the restored form resolves (doi.org 200
        # -> link.springer.com); the tilde form does not.
        if doi and "~" in doi:
            doi = doi.replace("~", ":")
    if not url and doi:
        url = f"https://doi.org/{doi}"
        # NAME WHERE THE URL CAME FROM. A provenance file records the URL the
        # fetcher actually requested; a DOI resolver link is reconstructed, and
        # a reconstruction that quietly wore the same label as a record would be
        # the "absence presented as measurement" error this project keeps
        # finding. Set here, at the one place the URL is built.
        url_source = url_source or ("doi_from_provenance" if prov_doi
                                    else "derived_from_directory_name")
    return {"reason": reason, "url": url, "url_source": url_source,
            "doi": doi, "path": str(path),
            "action": ("open the URL in a browser, save the article page as HTML, "
                       f"and replace {path.name}")}


def _load_provenance_hints(html_path: Path) -> tuple[str | None, str | None]:
    """Best-effort (url, doi) for the validator, read from a sibling manifest.

    fetchpdf writes ``{stem}.provenance.json`` alongside the HTML with the
    fetch's actual URL and resolved DOI — exactly what validate_t2's url=/doi=
    checks need. Absence must degrade to "not checked", never to a refusal:
    the file may have been placed by something other than fetchpdf.
    """
    import json

    for candidate in html_path.parent.glob("*.provenance.json"):
        try:
            prov = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        url = (prov.get("artifact") or {}).get("request_url")
        doi = (prov.get("identifiers_resolved") or {}).get("doi")
        if url or doi:
            return url, doi
    return None, None


#: Interstitial phrases that belong to a wrapper page, not to an article. Only
#: acted on when they DOMINATE the text -- a paper may legitimately discuss
#: cookies or JavaScript, and rejecting it for saying so would be its own false
#: refusal.
_DECOY_PHRASES = (
    "jump to content", "dismiss this warning", "enable javascript",
    "please enable cookies", "access denied", "just a moment",
    "checking your browser", "captcha", "subscribe to view",
    "purchase this article", "sign in to continue",
)


def _looks_like_boilerplate(text: str) -> str | None:
    """A conservative, dependency-free decoy check. Reason, or None.

    This is the FALLBACK for when fetchpdf's validator is unavailable, not a
    replacement for it. It only fires on the blatant case, because the cost of
    over-refusing here is a paper that cannot be reviewed at all, while the cost
    of under-refusing is bounded by the caller still having PDF and XML routes.

    Two signatures, both requiring DOMINANCE rather than mere presence:

      * one line repeated until it accounts for most of the page -- prose does
        not do this, wrapper chrome does;
      * an interstitial phrase occurring many times over.
    """
    stripped = " ".join(text.split())
    if len(stripped) < 200:
        return None                      # too little to judge; byte floors handle it
    low = stripped.lower()

    lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 15]
    if lines:
        from collections import Counter
        line, hits = Counter(lines).most_common(1)[0]
        if hits >= 5 and (hits * len(line)) / max(1, len(stripped)) > 0.5:
            return (f"one line repeats {hits} times and fills most of the page "
                    f"({line[:60]!r}), which is wrapper chrome rather than prose")

    # SUM the share across every interstitial phrase present, rather than
    # testing each alone. A wrapper page stacks them -- "Just a moment...",
    # "Checking your browser" -- while a paper that legitimately discusses one
    # of them uses that one. Measured on fixtures: a Cloudflare interstitial
    # reaches 0.65 combined share, an article about cookie consent 0.15, so the
    # threshold sits in a real gap rather than being tuned to either.
    hits = {ph: low.count(ph) for ph in _DECOY_PHRASES if low.count(ph)}
    share = sum(n * len(ph) for ph, n in hits.items()) / max(1, len(low))
    if hits and max(hits.values()) >= 5 and share > 0.25:
        worst = ", ".join(f"{ph!r} x{n}" for ph, n in
                          sorted(hits.items(), key=lambda kv: -kv[1])[:3])
        return (f"interstitial phrases fill {share:.0%} of the text ({worst}), "
                "so this is a wrapper page rather than the article")
    return None


def _validate_not_a_landing_page(html_path: Path, content: bytes,
                                 require_article: bool = True) -> str | None:
    """The failure reason if this page is a landing/decoy page, else None.

    TWO LAYERS, because the first one is not always installed. `fetchpdf` is a
    base dependency, but it was once a file:// path on one machine and then an
    extra, and a broken environment can still lack it. Returning None when
    the import fails -- the original behaviour -- left the
    "landing-page defense" silently INERT for everyone who is not its author,
    which is worse than not having it, because the feature is documented as
    present.

    Why this matters more than a normal missing check: other optional checks
    degrade COVERAGE when absent. This one degrades into a FALSE ACCUSATION. If
    an abstract-only stub or a "Jump to Content. Dismiss this warning."
    interstitial is read as the article's full text, then every statistic the
    real paper reports is missing from what we read -- and this toolkit treats
    an absence of reported data as a finding. The accusation lands on the
    authors for our failure to fetch their paper. `supplements.gate` refuses
    rather than warns for exactly this reason.

    So when the validator is present it decides, unchanged. When it is not, a
    conservative built-in check catches the blatant cases rather than waving
    everything through.

    `require_article=False` is for a SUPPLEMENT page, and turns off only the
    fetchpdf validator -- never the boilerplate check. `validate_t2` asks "is
    this the article?" (title, abstract, DOI, body length), and a supplementary
    tables file is legitimately none of those. Running it there would refuse a
    real supplement for not being the paper, which is a false refusal
    manufactured by using the right check on the wrong document. The blatant
    cookie-wall/interstitial check still applies, because a paywall page saved
    under a supplement's filename is exactly as useless as one saved under the
    article's.
    """
    if not require_article:
        return _looks_like_boilerplate(content.decode("utf-8", errors="replace"))
    try:
        from fetchpdf.retrieval.validate import validate_t2
    except ImportError:
        return (_looks_like_boilerplate(content.decode("utf-8", errors="replace"))
                or _article_floor_reason(html_path))
    url, doi = _load_provenance_hints(html_path)
    result = validate_t2(content, url=url, doi=doi)
    if not result.ok:
        return result.reason
    return _article_floor_reason(html_path)


def _article_floor_reason(html_path: Path) -> str | None:
    """The length floor, applied at the ONE gate every caller goes through.

    It lives here rather than in `_derive_paper_text` because `find_html`'s
    contract is that callers treat what it returns as usable without
    re-checking -- and a first attempt that guarded only the TEXT let the same
    decoy supply TABLES through `prepass._article_html_tables`. A test caught
    it. One gate, or the next consumer inherits the hole again.

    Only ever reached with `require_article=True`: a supplement is legitimately
    short and refusing it for not being the paper is a false refusal.
    """
    try:
        res = extract_html_text_with_tables(html_path, max_chars=10_000_000,
                                            require_article=False)
        text = "" if res.get("error") else (res.get("text") or "")
    except (OSError, ValueError):
        return None          # cannot judge; the other layers still apply
    return article_text_too_short(text)


def _strip_chrome(tree) -> None:
    """Remove script/style/nav/header/footer/aside subtrees, in place."""
    for tag in _CHROME_TAGS:
        for el in tree.iter(tag):
            el.drop_tree()
    for el in tree.iter():
        if not isinstance(el.tag, str):  # comments, PIs
            el.drop_tree()


def _table_caption(table_el) -> str:
    for child in table_el:
        if _local(child.tag) == "caption":
            return _cell_text(child)
    return ""


def _tr_cells(tr, in_thead: bool, counts: _Counter) -> list[tuple]:
    """Same shape jats.py's `_tr_cells` builds, read from an HTML `<tr>`."""
    cells: list[tuple] = []
    for cell in tr:
        tag = _local(cell.tag)
        if tag not in ("td", "th"):
            continue
        colspan = _int_attr(cell, "colspan")
        rowspan = _int_attr(cell, "rowspan")
        cells.append((_cell_text(cell, counts), colspan, rowspan, in_thead or tag == "th"))
    return cells


def _int_attr(el, name: str) -> int:
    try:
        return max(1, int(el.get(name) or 1))
    except (TypeError, ValueError):
        return 1


def _rows_of(table_el, counts: _Counter) -> list[list[tuple]]:
    """Read an HTML `<table>` into span-annotated rows.

    Walks `thead`/`tbody`/`tfoot` explicitly, same as jats.py's `_rows_html` —
    header membership decides the repeat-vs-anchor fill policy in `_expand`
    and must come from real markup, not a guess.
    """
    rows: list[list[tuple]] = []
    saw_section = False
    for node in table_el:
        tag = _local(node.tag)
        if tag in ("thead", "tbody", "tfoot"):
            saw_section = True
            in_thead = tag == "thead"
            for tr in node:
                if _local(tr.tag) != "tr":
                    continue
                cells = _tr_cells(tr, in_thead, counts)
                if cells:
                    rows.append(cells)
    if not saw_section:
        # Some publisher HTML puts <tr> directly under <table>, no thead/tbody.
        for tr in table_el:
            if _local(tr.tag) != "tr":
                continue
            cells = _tr_cells(tr, False, counts)
            if cells:
                rows.append(cells)
    return rows


def _build_table(table_el, table_num: int, section: str, counts: _Counter) -> dict:
    """Assemble one table dict — same contract as jats.py's `_build_table`."""
    caption = _table_caption(table_el)
    table: dict[str, Any] = {
        "page": None,
        "table_num": table_num,
        "id": table_el.get("id") or "",
        "label": "",
        "caption": caption,
        "section": section,
        "footnotes": [],  # HTML has no standard footnote convention; see module docstring.
        "source": "html",
        "warnings": [],
    }

    source_rows = _rows_of(table_el, counts)
    if not source_rows:
        # A <table> tag that resolved to zero real rows -- most likely a
        # JS-rendered container never filled in. Same treatment jats.py gives
        # a picture-only table: no cells, and say so rather than pretending.
        table.update({
            "data": [], "cells": [], "headers": [], "rows": [],
            "header_rows": [], "n_header_rows": 0, "width": 0, "n_rows": 0,
            "spans": [], "alignment_uncertain": False, "image_only": True,
            "graphic_href": None,
        })
        table["warnings"].append(
            "table element has no populated rows (likely JS-rendered and never "
            "filled in); extract it from the PDF or record it as unchecked"
        )
        return table

    grid, spans, warnings, padded = _expand(source_rows)
    table["warnings"].extend(warnings)

    n_header = 0
    for cells in source_rows:
        if cells and all(c[3] for c in cells):
            n_header += 1
        else:
            break

    width = len(grid[0]) if grid else 0
    if n_header:
        header = _flatten_header(grid[:n_header], width)
        body = grid[n_header:]
    else:
        header = [""] * width
        body = grid
        if grid:
            table["warnings"].append(
                "no <thead>; header may be the first body row — pass "
                "header_row=1 to parse_table if so"
            )

    uncertain = False
    # The printed table stays whole; the fold is a view for typing only.
    _folded, _sections, _kept = fold_section_bands(grid, n_header)
    table["sections"] = _sections
    body_padded = padded[n_header:] if n_header else padded
    for row, was_padded in zip(body, body_padded):
        if not was_padded:
            continue
        numeric = sum(1 for c in row if _HAS_DIGIT.search(c))
        if numeric >= 2:
            uncertain = True
            table["warnings"].append(
                f"ragged row {row[:2]!r}: column labels may be shifted; "
                "reconcile against the PDF before reporting from this table"
            )

    table.update({
        "data": [header] + body,
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
        "cells": _cells_from_grid(header, _folded),
        "headers": header,
        "rows": body,
        "header_rows": grid[:n_header],
        "n_header_rows": n_header,
        "width": width,
        "n_rows": len(body),
        "spans": spans,
        "alignment_uncertain": uncertain,
        "image_only": False,
        "graphic_href": None,
    })
    return table


#: Elements after which a line break is real structure rather than layout.
_BLOCK_TAGS = frozenset({
    "p", "div", "section", "li", "ul", "ol", "blockquote", "figure",
    "figcaption", "br", "h1", "h2", "h3", "h4", "h5", "h6", "dd", "dt",
})

#: Headings, which become markdown markers so the SHARED section mapper works.
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})


def _flatten_text(el, counts: _Counter) -> str:
    """Flatten an element's text, skipping table subtrees (already handled
    separately — pouring table content into prose loses column alignment,
    the exact failure `jats._collect` exists to avoid, same reasoning here).

    BLOCK STRUCTURE IS PRESERVED, and it was not. This collapsed EVERY run of
    whitespace to a single space, so the whole article arrived as one line with
    no paragraph or heading boundaries at all. Two things downstream depend on
    exactly those boundaries and both had silently stopped working on the HTML
    rung:

      * `sections.map_sections` reads `## Heading` markers, the shape docling
        emits. MEASURED on the PMC rendering of Stern 2014: `'## '` occurred 0
        times, so it found ONE section spanning the entire paper.
      * `scaffold.linear.chunks` builds its reading order from those sections
        and splits an over-long one at a blank line. With one section and no
        blank lines it produced ONE CHUNK -- which is precisely the whole-text
        pass that linear reading exists to replace, and Greg asked for it
        because a model handed everything at once reverts to grep-and-regex
        instead of reading. 18 chunks on the PDF path became 1 on the HTML path.

    So headings emit `## `, block elements emit a blank line, and whitespace is
    collapsed WITHIN a block rather than across the document. The marker shape
    is deliberately the one the existing mapper already reads: a second section
    convention would be a second definition of what a section is.
    """
    parts: list[str] = []
    if el.text:
        parts.append(el.text)
    for child in el:
        tag = _local(child.tag)
        if tag == "table":
            pass
        elif tag in _HEADING_TAGS:
            inner = _flatten_text(child, counts)
            if inner:
                parts.append(f"\n\n## {inner}\n\n")
        else:
            inner = _flatten_text(child, counts)
            if inner:
                parts.append(f"\n\n{inner}\n\n" if tag in _BLOCK_TAGS else inner)
        if child.tail:
            parts.append(child.tail)
    text = "".join(parts)
    # Collapse runs WITHIN a line, and runs of blank lines to one, so the
    # document keeps its block boundaries without gaining ragged vertical space.
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_reference_list(root) -> int:
    """Drop the bibliography from the STATISTICS text. Returns how many dropped.

    MIRRORS THE JATS READER, which has skipped `<ref-list>` from the section
    walk since before this module existed, "on purpose -- it carries no
    checkable statistics and would swamp the stage-1 budget". The HTML reader
    had no such skip, so the same paper's bibliography was in the served text
    on one rung and not on the other.

    MEASURED. Hand-classifying 36 unclassified floor numerals drawn in salted
    hash order across the upgraded corpus, **15 (42%) are reference-list
    debris** -- page ranges (`246-250`), volume/issue (`2011;20:246`), DOIs
    (`10.1037/0033-2909`), years. On `pone.0069841` the two rungs differ
    exactly here: HTML serves 403 numerals of which 21 class as `citation_year`,
    the XML serves 225 and zero, and the paper's OWN reported-statistic markers
    go UP (46 -> 52) because the denominator lost what was never the paper's
    measurement.

    That matters for one claim in particular: `numerals.tally`'s `n_total` is
    the denominator of every "numbers we did not check" statement. A
    bibliography inside it makes our coverage look worse than it is AND makes
    the unclassified bucket look like missed statistics when it is mostly
    citations.

    PMC marks it `<section class="ref-list">`, the same semantic name JATS uses,
    so `jats._SKIP_SECTIONS` is imported rather than restated -- a second copy
    of "what counts as the reference list" is the shape this project keeps
    finding at the bottom of its drift.

    NOT DELETED FROM THE FILE, only from the text this function returns. The
    bibliography is needed for citation checking, which is why `jats` keeps
    `extract_references` beside its skip.
    """
    from .jats import _SKIP_SECTIONS

    dropped = 0
    for el in list(root.iter()):
        if not isinstance(el.tag, str):
            continue
        marker = f"{el.get('class') or ''} {el.get('id') or ''}".lower()
        if any(name in marker for name in _SKIP_SECTIONS):
            parent = el.getparent()
            if parent is not None:
                el.drop_tree()
                dropped += 1
    return dropped


def _article_root(tree):
    """The article element, or the whole tree when the page does not mark one.

    WITHOUT THIS THE WHOLE PAGE IS THE PAPER. MEASURED on the PMC rendering of
    Stern 2014, the served text began: "Skip to main content Official websites
    use .gov A .gov website belongs to an official government organization in
    the United States. Secure .gov websites use HTTPS A lock (Lock Locked
    padlock icon)..." -- federal navigation boilerplate entering both the text
    the model reads and the numeral floor's denominator.

    `_CHROME_TAGS` could not catch it: it strips `nav`/`header`/`footer`/`aside`
    and NCBI's banner is in neither. Selecting the article root is the positive
    form of the same intent and does not need a per-publisher list.

    Falls back to the whole tree, so a page with no `<article>`/`<main>` behaves
    exactly as before -- this can narrow what is read, never widen it.
    """
    for tag in ("article", "main"):
        found = [el for el in tree.iter(tag)]
        if found:
            # The LARGEST such element, because PMC nests a short `<article>`
            # for the citation block inside the real one.
            #
            # NOT WRAPPED IN A try/except. The first draft had a helper that
            # caught everything and returned "" -- `test_inertness` failed it,
            # correctly: a swallowed exception scores the element at zero length,
            # so the REAL article would silently lose the max() to the citation
            # stub and we would read the wrong root while reporting success.
            # `itertext()` on a parsed element does not raise; if it ever does,
            # the traceback is the useful outcome.
            return max(found, key=lambda e: len("".join(e.itertext())))
    return tree


def extract_html_text_with_tables(
    html_path: str | Path,
    max_chars: int = 50000,
    first_section: int | None = None,
    last_section: int | None = None,
    require_article: bool = True,
) -> dict[str, Any]:
    """
    Extract body text and tables from fetched publisher HTML full text.

    Same return contract as
    :func:`metascience_agent.extraction.jats.extract_xml_text_with_tables` —
    callers and prompts treat the two interchangeably. ``first_section``/
    ``last_section`` are accepted for interface parity; HTML is treated as a
    single section (publisher HTML has no reliable, cross-template section
    boundary the way JATS `<sec>` does), so both are effectively no-ops here
    beyond bounding an already-one-item list.

    A page that fails the landing-page/decoy check (see module docstring)
    returns a structured `error`, the same shape
    `extraction.supplements_read.extract_supplement` already uses for an
    unreadable format — callers already know to route that into `unchecked`
    rather than treating it as "checked, zero tables found".
    """
    html_path = Path(html_path)
    if not html_path.exists():
        raise FileNotFoundError(f"HTML not found: {html_path}")

    content = html_path.read_bytes()
    reason = _validate_not_a_landing_page(html_path, content,
                                          require_article=require_article)
    if reason:
        return _validation_error(html_path, reason)

    import lxml.html

    try:
        tree = lxml.html.fromstring(content)
    except Exception as exc:
        return _validation_error(html_path, f"HTML parse failed: {exc}")

    _strip_chrome(tree)

    counts = _Counter()
    # A DISPLAYED EQUATION IS NOT A TABLE. PMC wraps `<disp-formula>` in a
    # one-cell `<table class="disp-formula">` holding an image of the equation --
    # measured on PMC2747164, which reported `n_tables: 1` for a paper whose only
    # `<table>` is the formula `m_i is the number of media...`. Harmless for
    # checking (a zero-cell table offers nothing to check) and NOT harmless for
    # counting: "this paper has 1 table" is then false, and table counts feed
    # coverage claims.
    #
    # Keyed on the class marker, which is positive evidence the publisher wrote.
    # "has no text cells" would also skip a genuinely image-only DATA table,
    # which `image_only` exists to record rather than discard.
    def _is_layout_table(el) -> bool:
        cls = (el.get("class") or "").lower()
        return "disp-formula" in cls or "inline-formula" in cls

    table_els = [el for el in tree.iter("table") if not _is_layout_table(el)]
    tables = [
        _build_table(el, i, section="Body", counts=counts)
        for i, el in enumerate(table_els, start=1)
    ]

    root = _article_root(tree)
    _strip_reference_list(root)
    body_text = _flatten_text(root, counts)
    refs = []
    for t in tables:
        name = t["label"] or f"Table {t['table_num']}"
        shape = (
            "image only, no cells" if t["image_only"]
            else f"{t['n_rows']} rows x {t['width']} cols"
        )
        refs.append(f"[{name}: {t['caption']} — {shape}; see tables]")
    if refs:
        body_text = (body_text + "\n\n" + "\n".join(refs)).strip()

    truncated = False
    if len(body_text) > max_chars:
        truncated = True
        body_text = body_text[:max_chars] + _TRUNCATION_NOTE

    image_only = sum(1 for t in tables if t["image_only"])
    warnings: list[str] = []
    if image_only:
        warnings.append(
            f"{image_only} table(s) had no populated rows (likely JS-rendered "
            "and never filled in); get them from the PDF or record them as "
            "unchecked"
        )
    uncertain = sum(1 for t in tables if t["alignment_uncertain"])
    if uncertain:
        warnings.append(
            f"{uncertain} table(s) had ragged rows (alignment_uncertain); "
            "reconcile against the PDF before reporting from them"
        )
    warnings.append(
        "HTML has no standard footnote convention; table footnotes (which "
        "often define whether a cell is n (%) or mean (SD)) may be missing — "
        "reconcile against the PDF if a table's meaning is ambiguous"
    )

    page = {
        "page_num": 1,
        "unit": "section",
        "section": "Body",
        "text": body_text,
        "tables": [{"table_num": t["table_num"], "data": t["data"]} for t in tables],
    }

    return {
        "text": body_text,
        "tables": tables,
        "pages": [page],
        "num_pages": 1,
        "pages_extracted": [1, 1],
        "truncated": truncated,
        "source_format": "html",
        "unit": "section",
        "article_meta": {},
        "n_tables": len(tables),
        "n_tables_image_only": image_only,
        "warnings": warnings,
        "normalizations": dict(counts),
    }
