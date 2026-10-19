"""A readable HTML article from publisher XML, for the workbench right pane.

Used when a paper has XML and no PDF (166 such directories in the current
papers root). This is a reading copy, not a typeset facsimile: sections and
tables from `extract_xml_text_with_tables`, escaped, no scripts.

The DOI link is how a reviewer fetches the PDF. We do not scrape publishers.
"""

from __future__ import annotations

import re
import html as _html
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from .xml_figures import xml_figures

from .html import find_html
from .jats import (
    extract_xml_text_with_tables, find_pdf, find_xml, paper_text_with_source,
)


def doi_url(doi: str | None) -> str | None:
    if not doi:
        return None
    doi = str(doi).strip().rstrip(".")
    if doi.lower().startswith("https://doi.org/"):
        return doi
    if doi.lower().startswith("http://doi.org/"):
        return "https://" + doi[7:]
    if "/" not in doi:
        return None
    return f"https://doi.org/{doi}"


def doi_from_slug(slug: str) -> str | None:
    if "--" in slug:
        return slug.replace("--", "/", 1)
    return None


def _esc(s: Any) -> str:
    return _html.escape(str(s or ""), quote=True)


def _table_html(table: dict) -> str:
    headers = table.get("headers") or []
    rows = table.get("rows") or []
    data = table.get("data")
    if not rows and isinstance(data, list) and data:
        headers = data[0]
        rows = data[1:]
    if not headers and not rows:
        label = _esc(table.get("label") or f"Table {table.get('table_num')}")
        return (f'<figure class="xml-table"><figcaption>{label} '
                f'{_esc(table.get("caption") or "")}</figcaption>'
                f"<p class='muted'>This table is an image in the XML and has "
                f"no cells.</p></figure>")
    head = ""
    if headers:
        head = "<thead><tr>" + "".join(
            f"<th>{_esc(c)}</th>" for c in headers) + "</tr></thead>"
    # CELL ADDRESSES, so a finding can mark the number it is about. They are
    # the reader's own: body row i is `data[i + 1]`, and a cell's `row` is the
    # index with `data[row - 1][col] == raw` -- hence i + 2. Counted before
    # empty rows are skipped, so a skipped row cannot shift the ones below.
    body = "<tbody>" + "".join(
        f'<tr data-row="{i + 2}">' + "".join(
            f'<td data-row="{i + 2}" data-col="{j}">{_esc(c)}</td>'
            for j, c in enumerate(row)) + "</tr>"
        for i, row in enumerate(rows)
        if any(str(c or "").strip() for c in row)
    ) + "</tbody>"
    label = _esc(table.get("label") or f"Table {table.get('table_num')}")
    caption = _esc(table.get("caption") or "")
    warn = ""
    if table.get("alignment_uncertain"):
        warn = ("<p class='muted'><strong>alignment uncertain</strong> — "
                "columns were inferred; a value may sit under the wrong "
                "heading.</p>")
    return (f'<figure class="xml-table" id="table-{_esc(table.get("table_num"))}" '
            f'data-table-num="{_esc(table.get("table_num"))}">'
            f"<figcaption><strong>{label}</strong> {caption}</figcaption>"
            f"{warn}<table>{head}{body}</table></figure>")


def _xml_article_html(xml: Path, *, paper_dir: Path | None = None, archived_assets=None) -> tuple[str | None, dict, str | None, str | None]:
    """Readable HTML from publisher XML. Returns (html, meta, flavour, error)."""
    extracted = extract_xml_text_with_tables(
        xml, tables="full", max_chars=2_000_000)
    if extracted.get("error"):
        return (f"<p class='muted'>{_esc(extracted['error'])}</p>",
                {}, None, str(extracted["error"]))
    meta = extracted.get("article_meta") or {}
    flavour = extracted.get("source_format")
    figures = xml_figures(xml, paper_dir=paper_dir, archived_assets=archived_assets)
    meta = {**meta, "figures": figures}
    remaining = list(figures)
    by_num = {t.get("table_num"): t
              for t in (extracted.get("tables") or [])
              if isinstance(t, dict)}
    parts: list[str] = []
    title = meta.get("title")
    if title:
        parts.append(f"<h1>{_esc(title)}</h1>")
    authors = meta.get("authors")
    if authors:
        parts.append(f"<p class='byline'>{_esc(authors)}</p>")
    for page in extracted.get("pages") or []:
        if not isinstance(page, dict):
            continue
        n = page.get("page_num")
        sec = page.get("section") or f"Section {n}"
        parts.append(f'<section id="sec-{n}">'
                     f"<h2>{_esc(sec)}</h2>")
        parts.append(_paragraphs_html(page.get("text") or "", remaining))
        for tref in page.get("tables") or []:
            num = tref.get("table_num") if isinstance(tref, dict) else None
            table = by_num.get(num) or tref
            if isinstance(table, dict):
                parts.append(_table_html(table))
        parts.append("</section>")
    parts.extend(_rich_figure_html(f) for f in remaining)
    html_body = "\n".join(parts) or "<p class='muted'>The XML contained no body text.</p>"
    return html_body, meta, flavour, None


#: `[Figure 3: Cost-effectiveness acceptability curve ...]` -- the block shape
#: `jats._fig_block` emits. The label is optional; `FIGURE` is its stand-in.
_FIG_BLOCK = re.compile(r"^\[(FIGURE|Fig[^:\]]*)(?::\s*(.*))?\]$", re.S)


def _figure_html(label: str, caption: str) -> str:
    """A caption is TEXT the authors wrote, and it has to be on the page.

    A table placeholder is still skipped -- the real grid is spliced in after
    the prose, so rendering the placeholder too would show the table twice.
    A figure has no such second rendering: we do not reproduce the image, so
    if the caption is dropped here it appears nowhere, and a finding that
    quotes it cannot be highlighted however well it is anchored.
    """
    label = label.strip()
    if label.upper() == "FIGURE":
        label = "Figure"
    body = f"<figcaption><b>{_esc(label)}</b>"
    if caption:
        body += f" {_esc(caption.strip())}"
    return f"<figure class='xml-figure'>{body}</figcaption></figure>"


def _rich_figure_html(figure: dict) -> str:
    images = []
    for graphic in figure["graphics"]:
        if graphic["relpath"]:
            # Only the source service creates URLs. Other renderer callers get
            # the same caption and an explicit unavailable-image placeholder.
            images.append(f'<span data-xml-media="{_esc(graphic["relpath"])}" '
                          f'data-label="{_esc(figure["label"])}">Image available in the workbench.</span>')
        else:
            images.append(f'<p class="muted">{_esc(graphic["status"])}</p>')
        if graphic['status'] == 'local_current':
            images.append('<p class="muted">Current local image; not archived evidence.</p>')
    return (f'<figure class="xml-figure" id="{_esc(figure["anchor"])}">'
            + "".join(images) + f'<figcaption><b>{_esc(figure["label"])}</b> '
            + _esc(figure["caption"]) + '</figcaption></figure>')


def article_media(article: dict, project: str, directory: str) -> dict:
    """Bind safe relative references to the existing validated media endpoint."""
    body = article.get('html')
    if not body:
        return article
    def image(match):
        ref, label = (_html.unescape(v) for v in match.groups())
        url = _esc('/api/media?' + urlencode({'project': project, 'dir': directory, 'f': ref}))
        return (f'<a href="{url}" target="_blank" rel="noreferrer" title="Open full-size image">'
                f'<img src="{url}" alt="{_esc(label)}" loading="lazy" /></a>')
    body = re.sub(r'<span data-xml-media="([^"]*)" data-label="([^"]*)">Image available in the workbench.</span>', image, body)
    return {**article, 'html': body}


def _paragraphs_html(text: str, remaining: list | None = None) -> str:
    parts = []
    for block in (text or "").split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("[Table "):
            continue                      # the real grid is spliced in below
        if remaining is not None:
            matches = [f for f in remaining if block.startswith(f'[{f["label"]}:')]
            if len(matches) == 1:
                parts.append(_rich_figure_html(matches[0]))
                remaining.remove(matches[0])
                continue
        fig = _FIG_BLOCK.match(block)
        if fig:
            parts.append(_figure_html(fig.group(1), fig.group(2) or ""))
            continue
        parts.append(f"<p>{_esc(block)}</p>")
    return "\n".join(parts)


def article_view(paper_dir: str | Path) -> dict[str, Any]:
    """What the right-hand pane should show, and how to get a PDF if we can.

    `mode` is `pdf` | `xml` | `html` | `text` | `none`. Absence of a PDF is
    never reported as a clean paper; it is a named gap plus a DOI link.
    """
    paper_dir = Path(paper_dir)
    pdf = find_pdf(paper_dir)
    xml = find_xml(paper_dir)
    html_path = find_html(paper_dir)

    slug = paper_dir.name
    doi = doi_from_slug(slug)
    title = None
    flavour = None
    html_body = None
    figures = []
    mode = "none"
    warning = None

    if pdf is not None:
        mode = "pdf"
    if xml is not None:
        html_body, meta, flavour, xml_err = _xml_article_html(xml, paper_dir=paper_dir)
        figures = meta.get("figures", [])
        title = meta.get("title") or title
        doi = meta.get("doi") or doi
        if pdf is None:
            mode = "xml"
            warning = xml_err or (
                "PDF not available, using XML. Try downloading the PDF here:"
            )
    elif pdf is None and html_path is not None:
        mode = "html"
        try:
            from ..bundle import _safe_html
            raw = html_path.read_bytes()
            html_body = _safe_html(raw) or None
        except Exception as exc:
            warning = f"HTML full text could not be rendered: {exc}"
        if html_body is None and warning is None:
            warning = "HTML full text could not be rendered."
        if warning is None:
            warning = (
                "PDF not available, using publisher HTML. "
                "Try downloading the PDF here:"
            )
    elif pdf is None:
        text, source = paper_text_with_source(paper_dir)
        if text and source:
            mode = "text"
            html_body = "<pre class='body-md'>" + _esc(text[:200_000]) + "</pre>"
            warning = (
                "PDF not available; showing extracted text. "
                "Try downloading the PDF here:"
            )
        else:
            mode = "none"
            warning = (
                "No PDF, XML, or extracted text on disk. "
                "Try downloading the PDF here:"
            )

    url = doi_url(doi)
    return {
        "mode": mode,
        "has_pdf": pdf is not None,
        "has_xml": xml is not None,
        "pdf_relpath": pdf.name if pdf else None,
        "xml_relpath": xml.name if xml else None,
        "html": html_body,
        "title": title,
        "doi": doi,
        "doi_url": url,
        "flavour": flavour,
        "figures": figures,
        "warning": warning,
    }
