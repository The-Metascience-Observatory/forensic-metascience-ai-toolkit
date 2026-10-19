"""
Render a forensic review (markdown) to a styled PDF.

Pipeline: markdown -> HTML (python `markdown`) -> PDF (`wkhtmltopdf`), with a
`pandoc` fallback. Rendering is best-effort: if no renderer is available the
functions return None and the caller keeps the markdown report — a missing PDF
must never fail the analysis pipeline.
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from . import consequence as _consequence

# Print CSS: readable, neutral, with visible table borders and severity color
# cues that match the severity vocabulary used throughout the reports.
_CSS = """
@page { size: A4; margin: 20mm 18mm; }
body {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 11pt; line-height: 1.5; color: #1a1a1a; max-width: 100%;
}
h1 { font-size: 19pt; margin: 0 0 4pt; border-bottom: 2px solid #333; padding-bottom: 6pt; }
h2 { font-size: 14pt; margin: 18pt 0 4pt; }
h3 { font-size: 12pt; margin: 14pt 0 4pt; }
p, li { margin: 4pt 0; }
strong { color: #000; }
code { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 9.5pt;
       background: #f2f2f2; padding: 1px 4px; border-radius: 3px; }
pre { background: #f6f8fa; padding: 10px; border-radius: 6px; overflow-x: auto;
      font-size: 9pt; line-height: 1.35; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 9.5pt; }
th, td { border: 1px solid #ccc; padding: 4px 7px; text-align: left; vertical-align: top; }
th { background: #f0f0f0; }
blockquote { border-left: 3px solid #bbb; margin: 8pt 0; padding: 2pt 12pt; color: #444; }
.review-meta { color: #666; font-size: 9pt; margin-bottom: 14pt; }

/* Severity. The comment above this block claimed these existed for a long
   time before they did, so every severity printed identically and a PDF reader
   had only the word itself to go on.

   Two deliberate choices. The palette is the print-safe reading of the
   terminal colours in tools/severity.py -- `yellow` on white is unreadable on
   paper, so `suspicious` becomes a dark amber. And the two accusatory levels
   additionally get a left rule, because a review may well be read in
   greyscale and colour alone must not be what separates "impossible" from
   "consistent". */
.sev-impossible         { color: #8b0000; font-weight: 700; }
.sev-highly_suspicious  { color: #b22222; font-weight: 700; }
.sev-suspicious         { color: #8a5200; font-weight: 600; }
.sev-indeterminate      { color: #0f6674; }
.sev-consistent         { color: #1a6b34; }
.sev-none               { color: #1a6b34; }
h3.sev-impossible, h3.sev-highly_suspicious {
  border-left: 4px solid currentColor; padding-left: 8pt; margin-left: -12pt;
}
h3.sev-suspicious { border-left: 2px solid currentColor; padding-left: 9pt; margin-left: -11pt; }
blockquote.sev-impossible, blockquote.sev-highly_suspicious { border-left-color: currentColor; }
blockquote.sev-suspicious { border-left-color: #8a5200; }
.consequence { font-size: 9.5pt; color: #444; }
.consequence.computed { color: #1a1a1a; font-weight: 600; }
"""

_HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>{css}</style></head>
<body>{meta}{body}</body></html>"""


_SEVERITY_LABEL = {
    "impossible": "IMPOSSIBLE",
    "highly_suspicious": "HIGHLY SUSPICIOUS",
    "suspicious": "SUSPICIOUS",
    "indeterminate": "INDETERMINATE",
    "consistent": "CONSISTENT",
    "none": "NO MAJOR PROBLEM FOUND",
}

# Severity as it appears in the rendered markdown. Matched on the STRUCTURE the
# renderer emits -- a finding heading's `[LABEL | confidence: ...]` suffix and
# the headline blockquote's leading `<strong>LABEL</strong>` -- rather than on
# the bare word, which occurs in ordinary prose throughout a review.
_SEV_CLASS = {label: f"sev-{slug}" for slug, label in _SEVERITY_LABEL.items()}
_SEV_ALTERNATION = "|".join(
    re.escape(x) for x in sorted(_SEV_CLASS, key=len, reverse=True)
)
# `(?:(?!</h3>).)*` -- "any character, as long as `</h3>` does not start here".
# Two properties depend on it, and both were broken by a plain `.*?` under
# DOTALL:
#
#  * The body cannot cross a heading boundary. Every report emits `### Studies`
#    / `### Variables` / `### Tests` for the anatomy section BEFORE the
#    findings, so a lazy match starting at `<h3>Studies` ran all the way to the
#    first finding's label: the section heading was painted as a severe finding
#    and the most severe finding in the document lost its cue entirely.
#  * The body is GREEDY, so the label matched is the LAST one in the heading --
#    the suffix this renderer emits. Titles are model-authored prose quoting the
#    paper, and a title containing "[IMPOSSIBLE | confidence: high]" would
#    otherwise hijack the heading's class from the real verdict.
_H3_BODY = r"(?:(?!</h3>).)*"
_HEADING_SEV_RE = re.compile(
    rf"<h3([^>]*)>({_H3_BODY})\[({_SEV_ALTERNATION})(\s*\|\s*confidence:{_H3_BODY})</h3>",
    re.DOTALL,
)
_HEADLINE_SEV_RE = re.compile(
    rf"<blockquote>(\s*<p>)<strong>({_SEV_ALTERNATION})</strong>"
)


def _apply_severity_classes(body_html: str) -> str:
    """Attach severity classes to the rendered HTML.

    Done here rather than in the markdown so `report.md` stays free of HTML
    spans: it is a deliverable in its own right and a reader opening it in a
    plain editor should not have to read around markup that exists only for
    the PDF.
    """
    def _heading(m: "re.Match[str]") -> str:
        cls = _SEV_CLASS[m.group(3)]
        attrs = m.group(1)
        attrs = (attrs + f' class="{cls}"') if 'class=' not in attrs else attrs
        return (f"<h3{attrs}>{m.group(2)}"
                f'[<span class="{cls}">{m.group(3)}</span>{m.group(4)}</h3>')

    def _headline(m: "re.Match[str]") -> str:
        cls = _SEV_CLASS[m.group(2)]
        return (f'<blockquote class="{cls}">{m.group(1)}'
                f'<strong class="{cls}">{m.group(2)}</strong>')

    return _HEADLINE_SEV_RE.sub(_headline, _HEADING_SEV_RE.sub(_heading, body_html))


def markdown_to_html(markdown_text: str, title: str = "Forensic Review", meta_line: str = "") -> str:
    """Convert markdown to a self-contained styled HTML document."""
    try:
        import markdown as _md
        body = _md.markdown(
            markdown_text or "",
            extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
        )
        body = _apply_severity_classes(body)
    except Exception:
        # Minimal fallback: escape and wrap in <pre> so we still get a PDF.
        import html
        body = f"<pre>{html.escape(markdown_text or '')}</pre>"
    meta = f'<div class="review-meta">{meta_line}</div>' if meta_line else ""
    return _HTML_TEMPLATE.format(title=title, css=_CSS, meta=meta, body=body)


def _render_wkhtmltopdf(html: str, out_path: Path) -> bool:
    exe = shutil.which("wkhtmltopdf")
    if not exe:
        return False
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        html_path = f.name
    try:
        proc = subprocess.run(
            [exe, "--quiet", "--enable-local-file-access",
             "--encoding", "utf-8", html_path, str(out_path)],
            capture_output=True, text=True, timeout=120,
        )
        return proc.returncode == 0 and out_path.exists()
    except (subprocess.TimeoutExpired, OSError):
        return False
    finally:
        Path(html_path).unlink(missing_ok=True)


#: WHY the last PDF render failed, so the CLI can say more than "it failed".
#: The inertness linter flagged the first cut of `_render_weasyprint` three
#: times over -- "an exception is discarded and nothing records that it
#: happened, so a caller cannot tell failure from a clean result" -- and it was
#: right: this whole defect (#163) survived because the one thing a run printed
#: about PDF output was a guess at the cause.
_LAST_PDF_ERROR: str | None = None


def last_pdf_error() -> str | None:
    """The reason the most recent PDF attempt failed, if one did."""
    return _LAST_PDF_ERROR


def _render_weasyprint(html: str, out_path: Path) -> bool:
    """Render OUR styled HTML with WeasyPrint's Python API.

    DIAGNOSED 2026-08-16, closing the "report.pdf skipped" defect. pandoc was
    installed and `report.pdf` never appeared. The cause was two-layered:
    pandoc alone cannot emit a PDF without an engine, and once weasyprint WAS
    installed into the venv, pandoc still reported "weasyprint not found" --
    it does not resolve the engine the way the surrounding shell does.

    Going through the library sidesteps that entirely, and produces a better
    document besides: `markdown_to_html` already applies this project's styling,
    while `--pdf-engine` hands pandoc's own default stylesheet the job.

    Imported lazily. WeasyPrint is a base dependency, but it loads Pango from
    the operating system, and where that is missing or clashes the import
    raises OSError; it must degrade to the next renderer rather than break
    `analyze` for everyone who never asked for a PDF.
    """
    global _LAST_PDF_ERROR
    try:
        from weasyprint import HTML  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001  -- ImportError, or a missing system lib
        _LAST_PDF_ERROR = f"weasyprint unavailable: {type(exc).__name__}: {exc}"
        return False
    try:
        HTML(string=html).write_pdf(str(out_path))
        ok = out_path.exists() and out_path.stat().st_size > 0
        if not ok:
            _LAST_PDF_ERROR = "weasyprint wrote no output"
        return ok
    except Exception as exc:  # noqa: BLE001  -- best-effort, same contract as the others
        _LAST_PDF_ERROR = f"weasyprint failed: {type(exc).__name__}: {exc}"
        return False


def _render_pandoc(markdown_text: str, out_path: Path) -> bool:
    exe = shutil.which("pandoc")
    if not exe:
        return False
    engine = _pandoc_pdf_engine()
    if not engine:
        return False
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(markdown_text or "")
        md_path = f.name
    try:
        cmd = [exe, md_path, "-o", str(out_path)]
        if engine:
            cmd += [f"--pdf-engine={engine}"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        return proc.returncode == 0 and out_path.exists()
    except (subprocess.TimeoutExpired, OSError):
        return False
    finally:
        Path(md_path).unlink(missing_ok=True)


def render_markdown_to_pdf(
    markdown_text: str,
    out_path: str | Path,
    title: str = "Forensic Review",
    meta_line: str = "",
) -> Optional[Path]:
    """Render markdown to a styled PDF at out_path.

    Returns the Path on success, or None if no renderer is available or all
    renderers failed (best-effort — never raises for a rendering failure).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    html = markdown_to_html(markdown_text, title=title, meta_line=meta_line)
    if _render_wkhtmltopdf(html, out_path):
        return out_path
    # Before pandoc: both render OUR html/markdown, but this one keeps this
    # project's stylesheet, and pandoc's engine lookup is the thing that was
    # failing in the first place.
    if _render_weasyprint(html, out_path):
        return out_path
    if _render_pandoc(markdown_text, out_path):
        return out_path
    return None


def _pandoc_pdf_engine() -> Optional[str]:
    """Return a PDF engine pandoc can actually use, if one is installed.

    `pandoc` alone does NOT imply PDF output: without a PDF engine (wkhtmltopdf,
    weasyprint, or a LaTeX engine) it fails at render time. Checking only for
    the pandoc binary made `renderer_available()` report a capability the
    machine did not have, so report.pdf silently never appeared.
    """
    for engine in ("wkhtmltopdf", "weasyprint", "pdflatex", "xelatex", "lualatex", "tectonic"):
        if shutil.which(engine):
            return engine
    return None


# --------------------------------------------------------------------------
# Structured -> markdown rendering
#
# The document is built from the SCHEMA FIELDS, not from the model's prose.
# That is what makes "headline first, findings severity-ordered, limitations
# always stated" an enforceable property rather than a request in a prompt.
# --------------------------------------------------------------------------

SEVERITY_RANK = {
    "impossible": 0,
    "highly_suspicious": 1,
    "suspicious": 2,
    "indeterminate": 3,
    "consistent": 4,
    "none": 5,
}


def severity_rank(value) -> Optional[int]:
    """Rank of a severity string, or None if it does not name one.

    Deliberately NOT `normalize_severity`, which maps EVERY unrecognised string
    onto `indeterminate`. Under that rule a typo would be ranked as a real
    verdict, and the headline invariant below would then fire -- or, worse, be
    satisfied -- on the strength of a spelling mistake. Legacy aliases (`high`,
    `moderate`) are still honoured: those are real verdicts in an older
    vocabulary, not typos.
    """
    # THE NUMERIC LADDER FIRST. v2 severities are INTEGERS 1-9, and this table
    # holds v1 strings, so every current-pipeline finding fell through to
    # `normalize_severity`, came back `indeterminate`, and ranked None.
    #
    # MEASURED on the 12-paper corpus: `worst_severity` is None on every paper
    # with a v2 run, so `sort_papers` -- documented as "Worst first... the paper
    # that most needs a human" -- ranked them 99 and put papers whose only runs
    # are RETIRED at the top of the human triage queue.
    #
    # Mapped rather than compared, so the two vocabularies order together: 9/8
    # are the impossible/misconduct band, 7-5 highly suspicious, 4-3 suspicious,
    # 2 indeterminate, 1 consistent. `severity9.ACCUSATORY_MIN` is 3, which is
    # where `suspicious` begins, and this preserves that boundary.
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        n = int(value)
        if n >= 8:
            return SEVERITY_RANK["impossible"]
        if n >= 5:
            return SEVERITY_RANK["highly_suspicious"]
        if n >= 3:
            return SEVERITY_RANK["suspicious"]
        if n == 2:
            return SEVERITY_RANK["indeterminate"]
        if n == 1:
            return SEVERITY_RANK["consistent"]
        return None

    raw = str(value or "").strip().lower()
    if raw in SEVERITY_RANK:
        return SEVERITY_RANK[raw]
    # A v2 severity that arrived as a numeric STRING ("4" from JSON round-trip).
    if raw.isdigit():
        return severity_rank(int(raw))
    # Imported here, not at module scope: `forensic_metascience_ai_toolkit.tools.__init__`
    # pulls in the whole numpy/scipy tool surface, and this module is a
    # renderer that a caller should be able to import without paying for that.
    from .tools.severity import normalize_severity
    canon = normalize_severity(raw)
    if canon == "indeterminate":     # the catch-all: not a recognised verdict
        return None
    return SEVERITY_RANK.get(canon)


FIGURE_BLINDNESS_NOTE = (
    "This analysis read the paper as text; figures were not inspected, so anomalies "
    "visible only in plots would not be detected."
)

#: Used when figures WERE extracted and read. The old note was appended
#: unconditionally, so a run that had six figure PNGs on disk still told the
#: reader it could not see figures -- and, worse, the model wrote findings
#: consistent with that claim rather than with the files in front of it.
FIGURES_READ_NOTE = (
    "Figures were extracted and inspected. Values PRINTED in a figure -- panel "
    "annotations, group sizes, exact p-values -- are treated as reported values "
    "like any other. Values MEASURED off a plotted mark are not: they carry no "
    "last printed digit, so no granularity or exact-arithmetic check may use "
    "them, and anything resting only on a measured value is reported as such."
)

def _render_checkable_detail(coverage_summary: dict) -> list[str]:
    """The gap, decomposed -- needs a declaration, needs an input, never submitted.

    Three different problems with three different fixes, and reporting one
    number for all of them tells a reader nothing they can act on.
    """
    c = (coverage_summary or {}).get("checkable") or {}
    if not (c.get("n_consumable") or 0):
        return []
    # THE TWO COUNTS ARE NOT DRAWN FROM THE SAME POPULATION, and printing them
    # as a pair implies they are. `n_consumable` is this census -- the cells in
    # the tables we walked. `checked` is what the run submitted, and a run may
    # legitimately submit cells from OUTSIDE those tables: means read out of the
    # prose and sent as a table, a supplement, a table only the PDF carries.
    #
    # Unique row keys (2026-08-12) raised `checked` from 8 to 28 on s11031 and
    # from 12 to 51 on scitotenv -- correctly, those dispositions had been
    # overwriting each other -- and the pairing then read "24 of 24 surveyed;
    # checked: 28", which is not a possible sentence. The old numbers hid the
    # mismatch behind an undercount; they never made the pairing sound.
    #
    # Same rule as `census.summarise` one rung up: where the populations
    # provably differ, state both counts and say so, rather than printing a pair
    # that asserts something we have not established.
    checked = c.get("cells_checked_via_check_table", 0)
    consumable = c["n_consumable"]
    out = [
        f"- **Checkable table cells:** {consumable} of {c.get('n_cells', '?')} "
        f"surveyed; **checked:** {checked}"
    ]
    if checked > consumable:
        out.append(
            f"    - at least {checked - consumable} of the cells checked came from "
            "outside the tables this census walked -- values read from the prose, "
            "a supplement, or a table only the PDF carries. These are two "
            "different populations, so no share of one in the other is stated, "
            "and this does NOT mean every surveyed cell was checked")
    if c.get("blocked_on_declaration"):
        out.append(f"    - {c['blocked_on_declaration']} could not be checked without "
                   f"knowing what kind of quantity the row reports")
    if c.get("blocked_on_input"):
        miss = ", ".join(f"{k} ({v})" for k, v in (c.get("missing_inputs") or {}).items())
        out.append(f"    - {c['blocked_on_input']} were missing an input"
                   + (f": {miss}" if miss else ""))
    if c.get("never_submitted"):
        out.append(f"    - {c['never_submitted']} could have run as they stand and were "
                   f"never submitted to a check")
    return out


class InvalidReportObject(ValueError):
    """The report object is too malformed to render honestly."""


def sort_findings(findings: list[dict]) -> list[dict]:
    """Order findings by severity, then by CONSEQUENCE, then by the model's rank.

    Severity alone left two `suspicious` findings indistinguishable -- one
    flipping a headline result, one a typo'd p-value that changes nothing --
    and their relative order then came down to whichever the model happened to
    rank higher. Consequence is now the second key, with a tool-computed
    consequence ahead of an identical asserted one (see `consequence.rank`).

    So `rank` does NOT set the printed order, and the schema now says so instead
    of "1 is most severe". Measured over the archived reports under
    `high_value_pdfs_to_run_on/` -- 15 DISTINCT reports, 134 findings --
    consequence moves 18 of them (13.4%) off the severity-only order, in 4 of
    the 15 reports. A document that claims only "most severe first" therefore
    cannot account for about one finding in eight, which is why the heading now
    states both keys.

    COUNT THE CORPUS BY CONTENT HASH, NOT BY FILE. 19 `report.json` files sit on
    disk, but 4 of them are byte-identical copies at
    `<review>_bundle/analysis/report.json` of the report in their own
    `<review>/` directory. This measurement was first published as 32 of 170
    (19%) in 6 of 18 reports; 3 of the 4 duplicate pairs are movers, so both the
    numerator and the denominator were inflated. Deduplicate first.

    `rank` stays as the LAST key rather than being deleted, for two reasons.
    It is required by `report.schema.json` under `additionalProperties: false`
    and is asked for by the stage-2 prompt, so dropping it would fail schema
    validation on every report that obeyed its own instructions. And it costs
    nothing: in all 15 distinct archived reports the model emitted findings
    already in rank order, so against Python's stable sort the third key is a
    measured no-op (0 of 15 orders change if it is removed). It is insurance for
    the day a finding arrives out of order, not something doing work today.

    What must never happen is `rank` reaching the reader as a printed number.
    The finding headings are positional (`enumerate` in `render_report`), so
    the integers a reader counts are always the order they are reading in;
    `rank` survives only in report.json, and the findings heading warns about
    that so nobody reading both concludes a finding went missing.
    """
    return sorted(
        findings or [],
        key=lambda f: (
            SEVERITY_RANK.get(str(f.get("severity", "")).lower(), 99),
            _consequence.rank(f),
            f.get("rank", 0),
        ),
    )


# DELETED: `_render_reproduction`, which printed a `**Reproduce:** <cmd>` line
# under the headline and under every finding. The report no longer carries a
# reproduction command anywhere.
#
# The DATA is untouched -- the schema still requires `reproduction`, the stage
# prompts still ask for it, `agent._annotate_reproductions` still validates and
# stamps `reproduction_valid` / `reproduction_problem`, and `findings.json`,
# `run_meta.json` and the viewer bundle still carry all of it. Only this
# document stopped showing it.
#
# The rule that function existed to enforce did NOT go away with it, and still
# governs the viewer's `bundle.reproHtml`: a command that did not validate must
# never be printed as something to paste, because a command that errors on first
# use reads as a broken tool rather than a bad citation. Anything that
# reintroduces a command into this renderer has to reintroduce that check too.
#
# Greg's `_repro_failure_clause` (below) SURVIVES this deletion deliberately.
# It is the measured vocabulary for naming OUR failure -- 461 of 801 archived
# commands invalid, all of them our defect -- and the viewer's `reproHtml`
# mirrors its attribution. The clause table is the single statement of that
# wording; the renderer that used to print it is what went away.


#: What the validator's message means, in the reader's terms. The raw message is
#: our CLI's stderr -- a Rich panel, wrapped, sometimes a traceback -- and it was
#: being pasted into the report verbatim, brace placeholders and all:
#:
#:   **Reproduce:** not independently reproducible as written (exited 2: Usage:
#:   metascience prop-from-normal [OPTIONS] {reported_proportion} {mean}...).
#:
#: Two things wrong with that. It reads as a property of the FINDING -- "not
#: independently reproducible" -- when every one of these is a defect in the
#: command WE wrote. And it hands the reader our internal error text as if it
#: were evidence about the paper. Classify instead, and say whose failure it is.
_REPRO_FAILURE_KINDS = (
    ("contains placeholder", "the review left a placeholder in its own command"),
    ("must invoke `metascience`", "the review did not supply a command here"),
    ("No such option", "the review's command used an option this tool does not have"),
    ("No such command", "the review's command named a tool that does not exist"),
    ("Traceback", "the review's command crashed when run"),
    ("Usage:", "the review's command did not match the tool's arguments"),
)


def _repro_failure_clause(entry: dict) -> str:
    """One clause naming OUR failure, never quoting our stderr.

    MEASURED over every archived findings.json, 2026-08-12: 461 of 801 entries
    carrying a reproduction command (57.6%) fail validation, and the cause is
    ours in all of them -- 313 malformed commands, 104 where prose was written
    where a command belongs, 30 unfilled placeholders. See the registered defect
    on the command generator; this function only stops the report misattributing
    the failure while that is open.
    """
    problem = str(entry.get("reproduction_problem", "") or "")
    for needle, clause in _REPRO_FAILURE_KINDS:
        if needle in problem:
            return f"no runnable command -- {clause}."
    return "no runnable command -- the review could not produce one that runs."


def _render_quote(finding: dict, stage1_findings: dict | None, prefix: str) -> str | None:
    """Surface the backing sweep finding's VERIFIED verbatim quote, if any.

    An editorial finding's `reported` field is the model's restatement of what
    the paper said -- quote-shaped, but never checked against the source, and one
    stage further from the paper than the sweep finding it came from. The sweep
    finding it references (`stage1_finding_ids`) carries a `quote` that the quote
    verifier located in the paper's own text. This surfaces THAT, so a reader has
    a promise they can check ("these words are in the paper") rather than only the
    review's paraphrase of it.

    Only `verbatim` and `elided` are rendered: those are the two verdicts that
    actually located the text, so only they may make the "As printed" promise
    (bundle.py `quoteLabel` draws the same line). A `stitched`/`unverified`
    backing is deliberately NOT shown -- it would add back exactly the kind of
    unlocated, quote-shaped text this fix exists to stop presenting as evidence.
    """
    if not stage1_findings:
        return None
    ids = finding.get("stage1_finding_ids") or []
    # THE TOOL CALL'S PASSAGE COMES FIRST. `sourcing.annotate` puts `source` on
    # a sweep finding by joining it to the validated call that produced it, so
    # that passage is the one the CHECKED NUMBERS were read from -- strictly
    # better provenance for an arithmetic claim than the finding's own `quote`,
    # which is the model's choice of what to quote about the finding. Both are
    # adjudicated by the same verifier, so preferring one costs nothing.
    for verdict in ("verbatim", "elided"):
        for fid in ids:
            src = stage1_findings.get(fid)
            if not isinstance(src, dict):
                continue
            got = src.get("source")
            if not isinstance(got, dict):
                continue
            if (str(got.get("source_quote_verified", "")).lower() == verdict
                    and (got.get("source_quote") or "").strip()):
                return _quote_line(prefix, got["source_quote"],
                                   got.get("source_quote_source"), verdict,
                                   got.get("source_locator"))
    # Prefer a contiguous verbatim match; fall back to an elided one.
    best = None
    for verdict in ("verbatim", "elided"):
        for fid in ids:
            src = stage1_findings.get(fid)
            if not isinstance(src, dict):
                continue
            if str(src.get("quote_verified", "")).lower() == verdict and (src.get("quote") or "").strip():
                best = (src, verdict)
                break
        if best:
            break
    if not best:
        return None
    src, verdict = best
    return _quote_line(prefix, src["quote"], src.get("quote_source"), verdict)


#: A divergence gets its own line ON THE FINDING in exactly two cases.
#:
#: `severity_reconcile` is explicit that it "does not overrule the model" --
#: divergence is often correct and is the whole point of stage 2, since GRIM
#: returns `impossible` on a perfectly ordinary continuous number and
#: downgrading that is the reviewer doing its job. Banner all 39 archived
#: divergences and the commonest case, an explained downgrade, drowns the two
#: that a reader must not miss.
#:
#: UPGRADES, always. The finding asserts more than the check established, and
#: under the cardinal rule -- a false accusation against an honest paper is the
#: worst thing this system can produce -- a reader must be able to see when our
#: own machinery escalated. MEASURED over the archive, 2026-08-12: all 12
#: upgrades are cited by a report finding, so every one of them is a claim a
#: reader already meets, with no sign the check behind it said something milder.
#:
#: UNEXPLAINED, either direction. That is the condition the module was built to
#: detect: the tool disagreed and the finding says nothing about why.
#:
#: An EXPLAINED DOWNGRADE gets no banner and IS counted in the run-level line
#: below. It can only make us gentler on the paper than the tool was, the
#: finding is still printed at its lower severity with the reason the model
#: gave, and 14 of the 26 archived divergences a report finding cites are of
#: this kind -- so a banner on each would be the noise that teaches a reader to
#: skip all of them, including the 12 that matter.
def _quote_line(prefix: str, quote: str, where, verdict: str,
                locator: str | None = None) -> str:
    """One prose line making the "as printed" promise, with where we found it.

    `locator` is the model's own description of where the values sit ("Table 1,
    Age row"). It is NOT verified -- only the quote text is searched for -- so
    it is offered as the author's label for the place, never as a located fact,
    and it is dropped rather than guessed at when absent.

    HTML ENTITIES ARE DECODED, and that makes this line MORE faithful, not less.
    The promise is "as printed in the paper", and the paper printed `P < 0.05`.
    The `&lt;` is our extractor's encoding, not the author's text: MEASURED
    2026-08-16 over the cached docling extractions, 176 `&lt;`/`&gt;` and 201
    `&amp;`, so essentially every threshold p-value in the corpus arrives
    entity-encoded. Four reached the delivered PNAS report as literal `&lt;`.
    This is also consistent with how the quote was VERIFIED: `quotes.py`
    unescapes the haystack before matching, so the two forms are already treated
    as the same text on the checking path.
    """
    quote = _html.unescape(str(quote))
    quote = " ".join(quote.split())  # collapse whitespace for one prose line
    where = str(where or "the paper").strip()
    across = ", across an ellipsis" if verdict == "elided" else ""
    at = f" **{str(locator).strip()}** -- " if isinstance(locator, str) and locator.strip() else " "
    return f'{prefix}**As printed in the paper:**{at}“{quote}” _(found in {where}{across})_'


def resolve_run_stamp(run_meta: dict | None, review_dir: "Path | None" = None) -> dict:
    """Everything the report needs to say about how it was produced.

    Reads what `agent._run_stamp` / `agent._provenance` recorded into
    `run_meta.json`. Absent keys stay absent -- the renderer prints "not
    recorded" for them, because a review that cannot say what produced it should
    say THAT rather than nothing at all.

    THE ONE INFERENCE, AND IT IS LABELLED. A review produced before `_run_stamp`
    existed has no `analysed_at`, and the only date left is the mtime of
    `run_meta.json`. That is a FILE date, not a run date: the two diverge the
    moment the directory is copied or synced, and this corpus lives in Dropbox.
    It is offered because "when was this roughly produced" is worth more than
    silence, and it is stamped `analysed_at_source: "file_mtime"` so the
    renderer can say on the page which of the two a reader is looking at.
    Presenting one as the other unlabelled would be the kind of quiet
    substitution this whole toolkit exists to catch.
    """
    meta = dict(run_meta or {})
    stamp = {
        k: meta.get(k) for k in (
            "analysed_at", "version", "git_sha", "git_dirty",
            "prompt_sha256", "registry_sha256", "effort",
        )
    }
    stamp["analysed_at_source"] = "recorded" if stamp["analysed_at"] else None

    if not stamp["analysed_at"] and review_dir is not None:
        p = Path(review_dir) / "run_meta.json"
        try:
            if p.exists():
                stamp["analysed_at"] = (
                    _dt.datetime.fromtimestamp(p.stat().st_mtime, _dt.timezone.utc)
                    .strftime("%Y-%m-%d %H:%M UTC"))
                stamp["analysed_at_source"] = "file_mtime"
        except OSError:
            pass

    # Every model that ran, not just the one that carried the bill. A stage can
    # resolve more than one, and a reader deciding how much to trust a judgement
    # needs to know which model made it.
    models: dict[str, list] = {}
    for name, stage in (meta.get("stages") or {}).items():
        if isinstance(stage, dict):
            got = stage.get("models_resolved") or (
                [stage["primary_billed_model"]] if stage.get("primary_billed_model") else [])
            if got:
                models[str(name)] = list(got)
    stamp["models"] = models
    return stamp


def _render_check_glossary(cov: dict) -> list[str]:
    """What each check that ran actually does, and what it may conclude.

    `registry.TOOL_INTEGRITY` holds a hand-authored card for all 49 tools --
    purpose, evidence class, assumptions -- and `ToolSpec.integrity_card()`
    derives the rest. Both are complete, both are covered by
    `tests/test_tool_integrity.py`, and until now NEITHER WAS READ BY ANY
    PRODUCTION SURFACE. Eleventh instance in this repo of a thing built,
    tested and never shown to anyone.

    It answers the question a reader of a forensic report most needs answered
    and could not answer before: when this tool says `impossible`, what kind of
    claim is that, and what had to be true for it to be entitled to say it?
    Without the assumptions, `impossible` reads as a fact about the paper; with
    them it reads as a conditional, which is what it actually is.

    Rendered ONCE PER DISTINCT TOOL, not per call. A run uses a median of ~13
    tools and makes several times that many calls, so per-call repetition would
    bury the findings in boilerplate -- the same reason the design review
    settled on "authored once per tool, read many times".

    Joined on `coverage_summary.tools_run`, which is the pipeline's own record
    of what ran. MEASURED across every archived run: 6-22 tools per run and
    every name resolves in the registry, 0 unmapped. The sweep findings'
    `technique` field was the alternative and is NOT usable for this -- only 21
    of its 31 distinct values are registry names, and its most common value by
    far is `manual` (139 findings), which names no tool at all.
    """
    from . import registry as _R

    names = [str(t) for t in (cov or {}).get("tools_run") or []]
    seen: list[str] = []
    for n in names:
        if n not in seen:
            seen.append(n)
    known = [n for n in seen if n in _R.BY_NAME]
    if not known:
        return []

    out = ["## What each check does", ""]
    out.append(
        "One entry per check that ran on this paper. The **assumptions** are the "
        "conditions under which its verdict holds; where one is unmet the verdict "
        "is capped, not merely caveated."
    )
    out.append("")
    for n in sorted(known):
        card = _R.BY_NAME[n].integrity_card()
        out.append(f"### `{n}` — {card.get('evidence', 'unclassified')}")
        out.append("")
        if card.get("purpose"):
            out.append(card["purpose"])
            out.append("")
        if card.get("evidence_meaning"):
            out.append(f"**What its verdict means.** {card['evidence_meaning']}")
            out.append("")
        if card.get("severity_ceiling"):
            out.append(
                f"**Strongest verdict it may reach:** `{card['severity_ceiling']}`"
            )
            out.append("")
        assumptions = [a for a in (card.get("assumptions") or []) if str(a).strip()]
        if assumptions:
            out.append("**It assumes:**")
            for a in assumptions:
                out.append(f"- {a}")
            out.append("")
    unknown = [n for n in seen if n not in _R.BY_NAME]
    if unknown:
        # Named rather than dropped: a tool we cannot describe is a gap in this
        # section, and silently omitting it would make the glossary look
        # complete when it is not.
        out.append(
            f"_{len(unknown)} check(s) ran that this glossary cannot describe: "
            f"{', '.join(sorted(unknown))}._"
        )
        out.append("")
    return out


