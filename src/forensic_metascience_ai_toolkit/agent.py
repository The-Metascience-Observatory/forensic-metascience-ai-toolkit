"""
Agent for forensic metascience analysis.

Calls the `claude` CLI as a subprocess (using the user's Claude Code
subscription) with our forensic tools exposed via a stdio MCP server
(see mcp_server.py).

The live pipeline is `mode="parallel"` (v1.0.0, 2026-08-21; see
docs/specs/pipeline.md and parallel.py): two analysts -- a tool expert and a
science-error analyst -- run concurrently with the independent image pipeline,
then an adjudicator merges their findings into a findings-v2 document with a 1-9 severity. This module keeps
the stage driver (`_run_stage`), the annotators, input resolution and the
output writers that `parallel.py` calls.

The serial sweep -> editorial pipeline that used to live here was REMOVED in
v1.27.0, and the readers of its output layout (`report.json`, v1
`findings.json`, `*.stage{1,2}.json`) were removed in 1.100.0, after the
archived runs were converted to findings.v2.json.
"""

import asyncio
import contextvars
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Callable, NamedTuple


# RE-EXPORTS, not leftovers. The legacy body that used these directly is gone
# (v1.27.0), but `parallel.py`, `cli.py` and the tests reach them as
# `agent.<name>` -- 5 uses for `sourcing`, 5 for `severity_reconcile`, 7 for
# `warrants`. Removing them because ruff calls them unused HERE would break
# callers that are using them THERE, so they are marked rather than deleted.
from . import anchoring as _anchoring  # noqa: F401
from . import consequence as _consequence  # noqa: F401
from . import scrub as _scrub  # noqa: F401
from . import severity_reconcile as _severity_reconcile  # noqa: F401
from . import sourcing as _sourcing  # noqa: F401
from . import warrants as _warrants  # noqa: F401
from .extraction.html import find_html
from .extraction.jats import find_body_md, find_xml, paper_text
from .llm_backend import (
    ForensicToolsNeverRan,
    Invocation,
    MCPUnavailable,
    backend_binary_version,
    build_invocation,
    forensic_pythonpath,
    resolve_backend,
    sandbox_limitation_sentence,
)
from .preflight import assert_ready as _assert_ready
# ONE StageError: runtime.py raises it, and every `except StageError` here and
# in the adjudicator's per-paper failure tuple must catch it. This module used
# to declare an identical class of its own, so those handlers caught nothing
# runtime raised: on 2026-10-18 a failed tool-free JSON repair, which
# `_repair_json` means to swallow, failed a whole paper of a Sonnet batch.
from .runtime import StageError
from .registry import STAGE1, STAGE2, stage_tools
from .usage_guard import guard as usage_guard


MCP_SERVER_NAME = "forensic_metascience"


def _mcp(name: str) -> str:
    return f"mcp__{MCP_SERVER_NAME}__{name}"


# Per-stage tool allowlists, DERIVED from the registry.
#
# These were hand-maintained lists, and that is how `parse_cells_typed` and four
# other validated tools ended up served by MCP but absent from STAGE1_TOOLS --
# registered, allowed nowhere, uncallable by the sweep. Stage membership is now
# declared once per tool in `registry.py` and read from there, so the list
# cannot fall behind the tools that exist.
#
# `Read` is the one built-in the stages need (the sweep reads body.md).
# Everything statistical must come from an MCP forensic tool; see DENIED_TOOLS.
STAGE1_TOOLS = ["Read"] + [_mcp(name) for name in stage_tools(STAGE1)]

# Spot-recheck subset for the editorial stage: enough to verify or refute a
# stage-1 finding without redoing the whole sweep.
STAGE2_TOOLS = ["Read"] + [_mcp(name) for name in stage_tools(STAGE2)]

# Backward-compat alias (previous public name).
ALLOWED_TOOLS = STAGE1_TOOLS

# Opus for the analysis. The sweep decides WHICH statistics to check and with
# which guards -- `data_type`, `bound_source`, `design` -- and a wrong guard does
# not degrade a result, it INVERTS it. That judgement is worth more than the
# token saving. (The specificity figures formerly quoted here were unsourced --
# see the 2026-08-12 audit; the direction stands, the magnitude was never
# measured.)
#
# Measured on one nine-study psychology paper with SI, verified against
# `modelUsage` rather than the requested alias: sonnet-5 $4.97, fable-5 $22.01.
# Opus-5 is UNMEASURED here; the nearest datapoint is opus-4-8 at $2.80 on a
# shorter cerebrolysin paper, which is not the same model or the same paper.
# `metascience batch` prefers a corpus's own batch_costs.jsonl over any constant.
DEFAULT_MODEL = "opus"

# Reasoning effort for the `claude` CLI (low|medium|high|xhigh|max). Set explicitly
# so a run does not silently inherit whoever's personal settings.json effortLevel —
# two people running the same corpus should get comparable analyses.
# "max" is rejected by the API when thinking is disabled ("output_config.effort
# 'max' is not supported on this model"), which failed every stage in ~2s with
# a 400 and billed a token for the privilege. "high" is the highest value the
# API currently accepts, and keeps the intent above: pin it here rather than
# inherit whoever's personal settings.json.
DEFAULT_EFFORT = "high"


_SUPPLEMENTARY_RE = re.compile(r"suppl|_si\b|-si\b|\bsi\b|supp_", re.IGNORECASE)


def _is_supplementary(pdf: Path) -> bool:
    return bool(_SUPPLEMENTARY_RE.search(pdf.stem))


# Supplementary formats we can actually open. Anything else present is
# reported as "present but unreadable" rather than passed over in silence --
# "not provided" and "provided but we could not read it" are different facts
# about a paper.
_SI_READABLE = {".docx", ".xlsx", ".xls", ".csv"}
_SI_UNREADABLE = {".doc", ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff",
                  ".zip", ".tex"}


def _supplement_readable_suffixes() -> frozenset[str]:
    """What `extract_supplement` can actually open, read from ITS table.

    Deliberately not `_SI_READABLE` above, which is a narrower hand-maintained
    copy: it lists `.xls`, which `supplements_read` removed on purpose because
    openpyxl cannot read the legacy binary format, and omits `.xlsm`, `.tsv`,
    `.txt` and `.epub`, which it can. Used only for files the operator NAMED
    with `--supplement`; the discovery path still uses `_SI_READABLE` and
    reconciling the two is separate work.
    """
    from .extraction.supplements_read import READABLE, UNREADABLE

    return frozenset(READABLE) - frozenset(UNREADABLE)


class PaperSources(NamedTuple):
    """Everything on disk that a review may draw on."""

    body_md: Path | None
    main_pdf: Path | None
    si_pdfs: list[Path]
    xml: Path | None
    html: Path | None
    si_readable: list[Path]
    si_unreadable: list[Path]


def _merge_supplied(sources: PaperSources, extra) -> PaperSources:
    """Fold `--supplement` paths into the supplementary buckets.

    WHY THIS EXISTS. `--supplement` reached `supplements.gate` and stopped
    there: `analyze_paper` was never passed it and had no parameter to take it,
    so the flag bought a proceed past the refuse-by-default gate for a file the
    sweep never opened. Every path the model can read is one this function put
    in the prompt -- the model has no `Glob`, no `Bash` and no directory-listing
    tool (see `BUILTIN_TOOLS`/`DENIED_TOOLS`), by decision -- so a supplement
    that is not merged here is a supplement that does not exist as far as the
    review is concerned, while the audit says we hold it.

    Classification is by `supplements_read.READABLE`/`UNREADABLE`, the tables
    `extract_supplement` actually dispatches on, rather than by this module's
    `_SI_READABLE`/`_SI_UNREADABLE` -- those are a narrower hand-maintained copy
    that still lists `.xls` (which `extract_supplement` refuses by format) and
    omits `.xlsm`/`.tsv`/`.txt`/`.epub`. Reconciling the two is separate work;
    an operator who NAMES a file has a right to have it read by the widest set
    of readers we have, and a file we cannot classify is listed as unreadable
    rather than dropped, because "present but unreadable" and "not provided" are
    different facts about a paper.
    """
    if not extra:
        return sources
    seen = {
        p.resolve()
        for p in (*sources.si_pdfs, *sources.si_readable, *sources.si_unreadable)
    }
    si_pdfs = list(sources.si_pdfs)
    readable = list(sources.si_readable)
    unreadable = list(sources.si_unreadable)
    for raw in extra:
        p = Path(raw).resolve()
        if p in seen or not p.is_file():
            continue
        seen.add(p)
        suffix = p.suffix.lower()
        if suffix == ".pdf":
            si_pdfs.append(p)
        elif suffix in _supplement_readable_suffixes():
            readable.append(p)
        else:
            unreadable.append(p)
    return sources._replace(
        si_pdfs=si_pdfs, si_readable=readable, si_unreadable=unreadable)


def _resolve_paper_sources(paper_path: str, extra=None) -> PaperSources:
    """
    Locate every input a paper offers: XML full text, fetched HTML full text,
    body markdown, main PDF, and supplementary files (split by whether we can
    open them).

    `extra` is files named with `--supplement`; see `_merge_supplied`. They are
    merged HERE rather than at the call site so that there stays exactly one
    resolution implementation and `_resolve_paper_inputs` cannot drift from it.

    The XML is preferred for text and tables because it is the only source that
    preserves table structure; the PDF is still needed for figures and for
    tables the XML holds only as an image. HTML is the fallback for a paper
    fetched without XML -- but unlike XML, a fetched HTML file can be a landing
    page, cookie gate, or JS-rendered app shell rather than the article, so
    `find_html` only ever returns a path whose content has already passed
    fetchpdf's `validate_t2` decoy check; a page that fails it comes back as
    `None` here, indistinguishable from "no HTML was ever fetched" -- which is
    what lets the existing body.md+PDF branch take over with no special-case
    fallback code. Only attempted when there is no XML: validating HTML costs
    a parse and (when available) a network-free but non-trivial check, and XML
    always wins when both exist.
    """
    p = Path(paper_path).resolve()
    if p.is_dir():
        body_md = find_body_md(p)
        pdfs = sorted(p.glob("*.pdf"))
        si_pdfs = [pdf for pdf in pdfs if _is_supplementary(pdf)]
        main_pdfs = [pdf for pdf in pdfs if not _is_supplementary(pdf)]
        # Prefer the main PDF whose stem matches the directory name.
        main_pdf = next(
            (pdf for pdf in main_pdfs if pdf.stem == p.name),
            main_pdfs[0] if main_pdfs else None,
        )
        others = [
            f for f in sorted(p.iterdir())
            if f.is_file() and f.suffix.lower() not in (".pdf", ".xml", ".html", ".md")
        ]
        xml = find_xml(p)
        html = find_html(p) if xml is None else None
        found = PaperSources(
            body_md,
            main_pdf,
            si_pdfs,
            xml,
            html,
            [f for f in others if f.suffix.lower() in _SI_READABLE],
            [f for f in others if f.suffix.lower() in _SI_UNREADABLE],
        )
        # LINKED DEPOSITS fetchpdf downloaded into `<stem>_data_artifacts/`.
        # Below the top level, so the glob above never saw them: a dataset
        # fetched for the review and then never opened by it. Merged like a
        # `--supplement`, so PDFs reach extraction and the rest are classified
        # by what `extract_supplement` can actually read.
        from .supplements import data_artifact_files

        found = _merge_supplied(found, data_artifact_files(p)[0])
    elif p.suffix.lower() == ".pdf":
        found = (PaperSources(None, None, [p], None, None, [], [])
                 if _is_supplementary(p)
                 else PaperSources(None, p, [], None, None, [], []))
    elif p.suffix.lower() == ".xml":
        found = PaperSources(None, None, [], p, None, [], [])
    elif p.suffix.lower() in (".md", ".markdown"):
        found = PaperSources(p, None, [], None, None, [], [])
    else:
        found = PaperSources(None, None, [], None, None, [], [])
    return _merge_supplied(found, extra)


def _supplement_record(sources: PaperSources, extra=None) -> dict:
    """What the run actually swept, for the run record.

    `supplied_supplement_paths` is separate from the rest because a
    `--supplement` may live anywhere on disk: unlike the discovered files, it
    cannot be recovered by re-listing the paper directory later, so a run whose
    record omits it is not reproducible from its own metadata.
    """
    return {
        "si_data_paths": [str(x) for x in sources.si_readable],
        "si_unreadable_paths": [str(x) for x in sources.si_unreadable],
        "supplied_supplement_paths": [str(Path(x)) for x in (extra or [])],
    }


def _resolve_paper_inputs(
    paper_path: str,
    extra=None,
) -> tuple[Path | None, Path | None, list[Path]]:
    """
    Back-compatible 3-tuple view of :func:`_resolve_paper_sources`.

    Kept as a thin slice so there is exactly one resolution implementation and
    the two cannot drift apart.

    Returns (body_md_path, main_pdf_path, supplementary_pdf_paths).
    """
    sources = _resolve_paper_sources(paper_path, extra)
    return (sources.body_md, sources.main_pdf, sources.si_pdfs)


def _xml_is_primary_text(paper_dir: Path) -> bool:
    """True when JATS XML is present and carries tables or substantial text.

    Used to skip docling the article PDF: the XML is the source of record
    for numbers, and a parallel accepted-manuscript extraction is a worse
    source the model can waste the stage on.
    """
    xml = find_xml(paper_dir)
    if xml is None:
        return False
    try:
        from .extraction.jats import extract_xml_text_with_tables
        result = extract_xml_text_with_tables(xml, tables="full")
    except Exception:  # noqa: BLE001 -- unreadable XML is not primary
        return False
    if not isinstance(result, dict) or result.get("error"):
        return False
    n_tables = len(result.get("tables") or [])
    n_chars = len(result.get("text") or "")
    return n_tables >= 1 or n_chars >= 500


def _pdfs_to_extract(paper_path: str,
                     extra: list[Path] | None = None) -> list[tuple[Path, str]]:
    """Every PDF a review of this paper may read, as `(path, why_it_is_here)`.

    TWO ENUMERATORS, UNIONED, because they answer different questions and each
    one alone leaves a hole the other covers:

      `_resolve_paper_sources`  what the SWEEP PROMPT will name. It globs the
                                directory and splits on a filename regex, so it
                                reaches a supplement nobody declared -- and an
                                undeclared file the model is told to read is
                                exactly the one that would hit a cache-only
                                refusal mid-run.
      `classify_inputs`         what the OPERATOR declared in `inputs.json`.
                                It reaches a supplement whose name carries no
                                `suppl`/`si` marker, which the regex above
                                cannot see.

    `extra` is `--supplement`, which may live outside the paper directory
    entirely; its cache is written beside the FILE, so an out-of-tree
    supplement extracts once and stays extracted.

    Deduplicated on the resolved path, first source winning, so a file named by
    both enumerators is extracted once.
    """
    from . import supplements as _supp

    out: dict[Path, str] = {}

    sources = _resolve_paper_sources(paper_path)
    if sources.main_pdf is not None:
        out.setdefault(sources.main_pdf.resolve(), "article")
    for si in sources.si_pdfs:
        out.setdefault(si.resolve(), "supplement")

    given = Path(paper_path)
    paper_dir = given if given.is_dir() else given.parent
    xml_primary = _xml_is_primary_text(paper_dir)
    if xml_primary and sources.main_pdf is not None:
        out.pop(sources.main_pdf.resolve(), None)

    for row in _supp.classify_inputs(paper_dir).get("files") or []:
        if row.get("role") not in ("article", "supplement", "dataset"):
            continue
        if not str(row.get("name", "")).lower().endswith(".pdf"):
            continue
        if xml_primary and row.get("role") == "article":
            continue
        out.setdefault((paper_dir / row["name"]).resolve(), row["role"])

    for f in (extra or []):
        if f.suffix.lower() == ".pdf" and f.is_file():
            out.setdefault(f.resolve(), "supplement (supplied)")

    # THE ARTICLE FIRST. An interrupted pre-flight then leaves the one file
    # every other stage depends on already cached, rather than a supplement.
    return sorted(out.items(), key=lambda kv: (kv[1] != "article", str(kv[0])))


def ensure_paper_extracted(
    paper_path: str,
    extra: list[Path] | None = None,
    on_event: Callable[[str], None] | None = None,
) -> dict:
    """Fill the docling cache for this paper's PDFs BEFORE anything is spent.

    WHY THIS EXISTS. `extraction.pdf` is docling-only and CACHE-ONLY (Greg,
    2026-08-16: pdfplumber "should never run *anywhere*"), and extraction is a
    deliberate, explicit STEP -- wiring it into a read path took the suite from
    5 minutes to 27, and on the second attempt to 2h10m, with an xdist worker
    collapsing outright. So every read path now REFUSES on an unextracted PDF
    and names the command that fixes it. This is that command, moved to where
    it cannot be forgotten: a refusal that surfaces halfway through a paid run
    costs the run, and a refusal that surfaces in `supplements.gate` is worse
    than that -- it is OUR missing cache reported as "this paper has no text
    layer", which is a fact about us written down as a fact about the paper.

    IDEMPOTENT. A file already cached costs a content hash and a JSON read and
    never loads the layout model, so calling this twice -- the CLI does, once
    before its own gate and once inside `analyze_paper`, which is the entry
    point `batch` uses instead -- is free for everything that succeeded the
    first time. MEASURED over the WSL/Drive mount, median of 5: 0.31 s for a
    1-PDF 0.3 MB paper, 0.36 s for a 3-PDF 1.8 MB one. Extracting those same
    files costs 24-38 s each, and 140 s for a scan that falls through to OCR.

    NEVER ABORTS. A supplement docling cannot read is recorded and the run
    continues, because a supplement we could not open is a fact about US: the
    alternative is refusing the whole paper over one file, and the failure has
    to reach the report either way so that "we did not read it" is never
    mistaken for "the authors did not report it".

    `on_event` receives one plain sentence per file that needs work, BEFORE the
    blocking call, because at 24-140 s a file a silent terminal is
    indistinguishable from a hung one.
    """
    from .extraction import docling_tables as _dl

    def _say(msg: str) -> None:
        if on_event is not None:
            on_event(msg)

    started = time.monotonic()
    checked: list[dict] = []
    pdfs = _pdfs_to_extract(paper_path, extra)

    ok, why = _dl.available()
    if pdfs and not ok:
        # Named, not silent. Without docling every one of these files is
        # unreadable to the whole pipeline, and a review that says nothing
        # about it reads as a review of a paper that happened to be thin.
        _say(f"docling is not installed ({why}); {len(pdfs)} PDF(s) cannot be "
             "extracted and will be UNREADABLE to this review.")
        return {
            "checked": [{"file": p.name, "path": str(p), "role": role,
                         "status": "failed", "seconds": 0.0,
                         "error": f"docling is not installed ({why})"}
                        for p, role in pdfs],
            "n_cached": 0, "n_extracted": 0,
            "failed": [p.name for p, _ in pdfs],
            "seconds": 0.0,
            "note": (f"docling is not installed ({why}), so none of this "
                     f"paper's {len(pdfs)} PDF(s) were read. Their contents are "
                     "UNKNOWN to this review -- that is a gap in OUR "
                     "environment, not a property of the paper."),
        }

    for path, role in pdfs:
        usable, why_not = _dl.cache_status(path)
        if usable:
            checked.append({"file": path.name, "path": str(path), "role": role,
                            "status": "cached", "seconds": 0.0, "error": None})
            continue
        _say(f"extracting {path.name} ({role}) with docling -- {why_not}. "
             "Measured at 24-140 s per file here, and it happens once per file.")
        t0 = time.monotonic()
        try:
            # `use_cache=False` because `cache_status` has ALREADY decided the
            # cache is unusable. Left at the default, a stale schema-2 entry
            # would be served straight back and the file would still be
            # unreadable to `extract_pdf` -- the pre-flight reporting success
            # and the paid run meeting the refusal anyway.
            r = _dl.extract_pdf_tables(path, use_cache=False)
        except Exception as exc:  # noqa: BLE001 -- one bad file must not end the run
            r = {"error": f"{type(exc).__name__}: {exc}"}
        secs = time.monotonic() - t0
        if r.get("error"):
            checked.append({"file": path.name, "path": str(path), "role": role,
                            "status": "failed", "seconds": secs,
                            "error": str(r["error"])})
            _say(f"  FAILED after {secs:.0f}s: {path.name}: {r['error']}")
            continue
        checked.append({"file": path.name, "path": str(path), "role": role,
                        "status": "extracted", "seconds": secs,
                        "n_tables": r.get("n_tables"),
                        "n_text_chars": r.get("n_text_chars"), "error": None})
        _say(f"  done in {secs:.0f}s: {path.name} -- {r.get('n_tables', 0)} "
             f"table(s), {r.get('n_text_chars', 0):,} characters of text.")

    # THE CANONICAL MARKDOWN, once the PDFs are readable and before any agent
    # starts. MEASURED 2026-08-22: 980 of 1,293 paper directories (76%) held no
    # markdown this repo could read, and the agents went looking anyway -- the
    # adjudicator failed 66% of its tool calls on `read_file body.md`,
    # `paper/body.md`, `paper.md`, names it guessed, and one paper stalled
    # mid-thrash and held a worker for 70 minutes. Materialising here is what
    # makes the guess right. Idempotent: a current folder costs one text
    # resolve and a digest compare.
    #
    # Deliberately AFTER the docling loop -- for a PDF-only paper the text
    # comes out of the cache this function just filled, so materialising first
    # would write a body.md from a source that was not yet readable.
    markdown_record: dict = {}
    try:
        from .extraction.markdown_out import materialise
        markdown_record = materialise(paper_path)
    except Exception as exc:  # noqa: BLE001 -- a convenience artifact never ends a run
        markdown_record = {"action": "failed",
                           "reason": f"{type(exc).__name__}: {exc}"}

    failed = [c for c in checked if c["status"] == "failed"]
    n_cached = sum(1 for c in checked if c["status"] == "cached")
    n_extracted = sum(1 for c in checked if c["status"] == "extracted")

    if not checked:
        note = ("No PDF to extract: this paper's text comes from XML, HTML or "
                "markdown, which need no layout model.")
    elif failed:
        # The reason is TRUNCATED here and kept whole in `checked`. This note
        # renders as one bullet under the report's limitations, and a docling
        # ConversionError runs to ~250 characters of stack detail that tells a
        # reader nothing they can act on -- while the file's name tells them
        # everything.
        note = (
            f"{len(failed)} of {len(checked)} PDF(s) could not be read by the "
            "extractor: "
            + "; ".join(f"{c['file']} ({str(c['error'])[:120]})" for c in failed)
            + ". Nothing in this review saw their contents, so any statistic "
            "they carry is UNKNOWN here -- it was NOT checked and found "
            "absent, and must not be reported as something the authors failed "
            "to provide."
        )
    else:
        note = (f"{len(checked)} PDF(s) available to the review "
                f"({n_cached} already extracted, {n_extracted} extracted now).")

    paper_dir = Path(paper_path) if Path(paper_path).is_dir() else Path(paper_path).parent
    skipped_article_pdf = "xml_primary" if _xml_is_primary_text(paper_dir) else None
    if skipped_article_pdf and "Article PDF skipped" not in note:
        note = (note + " Article PDF skipped: JATS XML is the primary text "
                "for numbers; figure harvest is a separate channel.")
    return {"checked": checked, "n_cached": n_cached,
            "n_extracted": n_extracted, "failed": [c["file"] for c in failed],
            "seconds": time.monotonic() - started, "note": note,
            "skipped_article_pdf": skipped_article_pdf,
            "markdown": markdown_record}


def _paper_id(paper_path: str) -> str:
    return Path(paper_path).resolve().name or "paper"


def _si_pass_text(si_pdfs: list[Path], pass_num: int) -> str:
    """Prompt fragment instructing the agent to sweep supplementary PDFs."""
    if not si_pdfs:
        return ""
    listing = "\n".join(f"  - `{p}`" for p in si_pdfs)
    return (
        f"\n\n**Pass {pass_num} — Supplementary information (PDF, read directly):**\n"
        f"Run `extract_pdf` on each supplementary file below. The SI PDF is the "
        f"authoritative source for supplementary tables — their structure is "
        f"preserved there far better than in any markdown. Sweep every "
        f"supplementary table, study, and reported statistic (means, SDs, ns, "
        f"test statistics, p-values, cell counts) and run the appropriate "
        f"forensic tools on each, exactly as for the main tables. SI studies "
        f"often carry the bulk of a paper's numeric claims — do not skip them.\n"
        f"{listing}"
    )


def _si_other_text(readable: list[Path], unreadable: list[Path], pass_num: int) -> str:
    """
    Prompt fragment for non-PDF supplementary files.

    Unreadable formats are named explicitly rather than omitted: a supplement
    that exists but cannot be opened is a coverage gap, and silently dropping it
    would let the review read as though the SI had been checked.
    """
    if not readable and not unreadable:
        return ""
    out = f"\n\n**Pass {pass_num} — Supplementary data files:**\n"
    if readable:
        listing = "\n".join(f"  - `{p}`" for p in readable)
        out += (
            "Run `extract_supplement` on each file below and sweep it exactly as "
            "you would a main table: its `cells` go straight to "
            "`parse_cells_typed`. A spreadsheet of PARTICIPANT-LEVEL data is "
            "worth more than a summary table — it supports checks the paper's "
            "own tables cannot. On participant-level sheets ALSO run "
            "`detect_raw_duplication` with the file path (it loads the grid "
            "itself — never retype cells): duplicated rows, copied runs and "
            "recycled values in raw data are what summary-statistic checks "
            f"cannot see.\n{listing}"
        )
    if unreadable:
        listing = "\n".join(f"  - `{p}` ({p.suffix.lstrip('.')})" for p in unreadable)
        out += (
            "\n\nThese supplementary files are PRESENT but this pipeline cannot "
            "read them (legacy binary formats, or figures supplied as images — "
            "there is no OCR). Record each in `unchecked` with its format as the "
            "reason. Do NOT report the supplement as absent: 'present but "
            f"unreadable' and 'not provided' are different facts.\n{listing}"
        )
    return out


#: The per-paper half of the tools agent's step 2a (1.84.0). The system prompt
#: says WHY; this names the directory to pass. Without it the per-paper text
#: told the model only "parse_cells_typed, then check_table", the more
#: specific instruction, and the declaration step reached it as an
#: afterthought. A pipeline without `declare_table` drops the block
#: (`parallel._restrict_user_prompt`).
TABLE_DECLARATIONS_HEADING = "**Table declarations (GRIM):**"


def table_declarations_text(paper_dir: Path | str) -> str:
    return (
        f"\n\n{TABLE_DECLARATIONS_HEADING} Call `list_tables` with `paper_dir` "
        f"`{paper_dir}`, then `declare_table` once for EVERY table that prints "
        "means or percentages, supplements included: bind each row to the "
        "variable it measures, set `percent_of_units` when bare numbers are "
        "percentages of the participants, and pass any n the paper states only "
        "in Table 1 or its text in `columns`, with the sentence that states it. "
        "The harness runs GRIM on every declared cell and files the failures "
        "itself; do not file them again.")


def _build_sweep_prompt(
    body_md: Path | None,
    pdf: Path | None,
    paper_id: str,
    si_pdfs: list[Path] | None = None,
    *,
    xml: Path | None = None,
    html: Path | None = None,
    si_readable: list[Path] | None = None,
    si_unreadable: list[Path] | None = None,
    paper_dir: Path | str | None = None,
) -> str:
    """Build the per-paper Stage-1 prompt, plus the table-declaration step
    when the paper directory is known."""
    prompt = _build_sweep_prompt_body(
        body_md, pdf, paper_id, si_pdfs, xml=xml, html=html,
        si_readable=si_readable, si_unreadable=si_unreadable)
    return prompt + (table_declarations_text(paper_dir) if paper_dir else "")


def _build_sweep_prompt_body(
    body_md: Path | None,
    pdf: Path | None,
    paper_id: str,
    si_pdfs: list[Path] | None = None,
    *,
    xml: Path | None = None,
    html: Path | None = None,
    si_readable: list[Path] | None = None,
    si_unreadable: list[Path] | None = None,
) -> str:
    """The per-paper Stage-1 prompt for the paper's source layout."""
    si_pdfs = si_pdfs or []
    si_readable = si_readable or []
    si_unreadable = si_unreadable or []
    header = (
        f'Analyze this scientific paper for statistical inconsistencies and '
        f'anomalies. Use paper_id "{paper_id}" in your findings JSON.\n\n'
    )

    if html and not xml:
        # HTML sits between XML and body.md+PDF: it preserves table structure
        # the way XML does (extract_html builds the same cell/span shape), but
        # `_resolve_paper_sources` only ever hands this branch a path that has
        # already passed the landing-page/decoy check -- a page that failed it
        # comes back as `html=None`, indistinguishable from "nothing was
        # fetched", which is what lets this branch fall through to body.md+PDF
        # below with no special-case code.
        passes = [
            f"""**Pass 1 — Full text and tables (HTML):**
Run `extract_html` on `{html}`. Treat its `cells` exactly like `extract_xml`'s: pass them STRAIGHT to `parse_cells_typed`, then `check_table` — do not route them through `parse_table` first. Read each table's `footnotes` before typing, though HTML has no standard footnote convention, so they may be empty even when the table needs one to be read correctly — reconcile against the PDF if a cell's meaning (`n (%)` vs `mean (SD)`) is ambiguous. For NHST verification, run `statcheck` with the `text` argument set to the returned body text.

Respect the per-table flags, same as for XML:
- `spans`: a merged value is placed ONCE, at its anchor; empty continuations are deliberate. Filling them in fabricates identical (mean, SD) pairs that trip `detect_duplication` against a paper that did nothing wrong.
- `alignment_uncertain: true`: ragged source rows, a column label may be shifted by one. Reconcile against the PDF, or record the table as unchecked.
- `image_only: true`: the table element had no populated rows (most likely never rendered by the page's own JavaScript) and has no cells. Get it from the PDF; if there is no PDF, record it in `unchecked`.
- If `extract_html` returns an `error`, the page failed a landing-page/decoy check that runs before any parsing — it is not the article. Do NOT attempt to recover text from the raw file yourself; fall back to `extract_pdf`/`Read` on the paper's PDF or body.md instead, and record why HTML could not be used.
- HTML has no pages. Write `location` as `"Table 2, Age row"` or `"Results, para 2"`, never a page number you did not see."""
        ]
        if pdf:
            passes.append(
                f"""**Pass 2 — PDF cross-check and figures:**
Run `extract_pdf` on `{pdf}` for three specific purposes ONLY: (a) reconcile any table flagged `alignment_uncertain`, passing the PDF grid as `parse_table`'s `cross_check`; (b) recover any table the HTML reports as `image_only`; (c) read figure captions and any statistic that appears only in a figure.

Do NOT re-sweep statistics already checked in Pass 1. The same statistic checked twice produces two findings and inflates the apparent problem count, which is itself a distortion of the paper."""
            )
        else:
            passes.append(
                "**Pass 2 — No PDF available.** This paper has no PDF, so figures "
                "could not be inspected and any `image_only` table could not be "
                "recovered. Record both in `unchecked`, and state the figure "
                "limitation explicitly."
            )
        next_pass = len(passes) + 1
        body = "Conduct a multi-pass sweep.\n\n" + "\n\n".join(passes)
        body += _si_pass_text(si_pdfs, next_pass)
        body += _si_other_text(si_readable, si_unreadable, next_pass + 1)
        body += "\n\nRecord all checks from every pass as findings in a single JSON output."
        return header + body

    if xml:
        # XML first: it is the only source that preserves table structure.
        passes = [
            f"""**Pass 1 — Full text and tables (XML):**
Run `extract_xml` on `{xml}`. This is the authoritative source for BOTH the body text and the tables: merged cells are already expanded and multi-row headers flattened into composite column labels, which no PDF or markdown extraction can reproduce.

For every table it returns, pass the table's `cells` STRAIGHT to `parse_cells_typed`, then run `check_table` once on the typed cells — do not route them through `parse_table` first, and do not check cells one at a time. Read each table's `footnotes` before typing: they define whether a cell is `n (%)` or `mean (SD)`. For NHST verification, run `statcheck` with the `text` argument set to the returned body text.

Respect the per-table flags — each one exists because ignoring it produces a false accusation:
- `spans` lists every merged cell. A merged value is placed ONCE, at its first covered position, and the continuations are empty ON PURPOSE. Do not fill them in: a value spanning four columns is one measurement, and copying it across would create identical (mean, SD) pairs that trip `detect_duplication` — a finding invented by the extraction, against a paper that did nothing wrong.
- `alignment_uncertain: true` means the source rows were ragged and a column label may be shifted by one. A shifted label puts a mean under the wrong group and hands GRIM/GRIMMER a triple the paper never reported. Reconcile against the PDF, or record the table as unchecked.
- `image_only: true` means the table is a picture and has no cells. Get it from the PDF; if there is no PDF, record it in `unchecked` — never report it as checked.
- XML has no pages. Write `location` as `"Table 2, Age row"` or `"Results, para 2"`, never a page number you did not see."""
        ]
        if pdf:
            passes.append(
                f"""**Pass 2 — PDF cross-check and figures:**
Run `extract_pdf` on `{pdf}` for three specific purposes ONLY: (a) reconcile any table flagged `alignment_uncertain`, passing the PDF grid as `parse_table`'s `cross_check`; (b) recover any table the XML reports as `image_only`; (c) read figure captions and any statistic that appears only in a figure.

Do NOT re-sweep statistics already checked in Pass 1. The same statistic checked twice produces two findings and inflates the apparent problem count, which is itself a distortion of the paper."""
            )
        else:
            passes.append(
                "**Pass 2 — No PDF available.** This paper has no PDF, so figures "
                "could not be inspected and any `image_only` table could not be "
                "recovered. Record both in `unchecked`, and state the figure "
                "limitation explicitly."
            )
        next_pass = len(passes) + 1
        body = "Conduct a multi-pass sweep.\n\n" + "\n\n".join(passes)
        body += _si_pass_text(si_pdfs, next_pass)
        body += _si_other_text(si_readable, si_unreadable, next_pass + 1)
        body += "\n\nRecord all checks from every pass as findings in a single JSON output."
        return header + body

    # THE DATA-SUPPLEMENT PASS BELONGS ON EVERY BRANCH, NOT JUST THE STRUCTURED
    # ONES. `_si_other_text` was called only from the XML and HTML branches, so
    # on the body.md+PDF layout -- the legacy corpus layout, and the one where an
    # operator most often reaches for `--supplement` -- a `.xlsx` or `.docx`
    # supplement was never named to the model at all.
    #
    # What was missing is the PATH, not the instruction. `detect_raw_duplication`
    # and `extract_supplement` are described in the standing system prompt
    # (`rulebook.md`), which every run gets. But the model cannot act on either
    # without a file to point them at, and it has no way to find one itself:
    # `Glob` and `Bash` are not in its tool surface, by decision (see
    # `BUILTIN_TOOLS`/`DENIED_TOOLS`). A supplement nothing names is a supplement
    # that does not exist. An unreadable one was dropped the same way, which is
    # the exact "reads as though the SI had been checked" failure this
    # fragment's own docstring argues against.
    if body_md and pdf:
        si_pass = _si_pass_text(si_pdfs, 3)
        si_other = _si_other_text(si_readable, si_unreadable,
                                  4 if si_pdfs else 3)
        return header + f"""Conduct a multi-pass sweep.

**Pass 1 — Clean text:**
Use the Read tool to read `{body_md}` (a high-quality extraction of the paper body). Identify all reported statistics and run the appropriate forensic tools on each. For NHST verification, prefer `statcheck` with the `text` argument set to the body content.

**Pass 2 — Tables and figures:**
Run `extract_pdf` on `{pdf}` to surface tables and content the markdown extraction may have missed (Table 1 baseline characteristics, supplementary statistics, figure captions). Run additional checks on any statistics not seen in pass 1.{si_pass}{si_other}

Record all checks from every pass as findings in a single JSON output."""
    if pdf or si_pdfs:
        targets = [str(x) for x in ([pdf] if pdf else []) + si_pdfs]
        si_note = _si_pass_text(si_pdfs, 2) if si_pdfs else ""
        return header + (
            f"Extract text and tables from each of these PDFs using the "
            f"`extract_pdf` tool: {', '.join(f'`{t}`' for t in targets)}. "
            "Then systematically check the reported statistics with the forensic "
            "tools and emit the findings JSON." + si_note
            + _si_other_text(si_readable, si_unreadable, 3 if si_note else 2)
        )
    if body_md:
        return header + (
            f"Use the Read tool to read `{body_md}`, identify all reported statistics, "
            "run the appropriate forensic tools on each, and emit the findings JSON. "
            "For NHST verification, use `statcheck` with the `text` argument."
            # No `_si_pass_text` here: this branch is only reached when there is
            # no PDF at all, and a non-empty `si_pdfs` would have been caught by
            # the branch above.
            + _si_other_text(si_readable, si_unreadable, 2)
        )
    # No supplement-only branch below on purpose: `analyze_paper` raises
    # FileNotFoundError before reaching here when the paper itself is absent,
    # and a review of the supplement alone is not a review of the paper.
    raise ValueError("No paper input found (no XML, body.md or PDF).")


from . import grace as _grace


def checks_tally(messages: list[dict] | None, findings: dict | None) -> dict:
    """How many checks RAN, and how they came out -- including the ones stage 2
    has never been able to see.

    The verdict is a judgement about a paper, and a judgement needs a
    denominator. Stage 2 receives `findings.json`, which lists every finding
    INCLUDING the `consistent` ones, so the individually-reported passes do
    reach it. What does NOT reach it are the passes `check_table` collapses:
    that tool returns consistent results as a COUNT plus an index rather than
    repeating them, deliberately, to stop the payload re-inflating the context.
    Those live in the tool result, and stage 2 is handed findings, not the
    ledger.

    MEASURED over 21 archived runs: 184 findings reported `consistent`
    individually, while `check_table` collapsed up to 125 MORE in a single run
    (`10.1016/j.scitotenv...`) that stage 2 never saw. A paper with 24 passes
    behind its 8 flags is a different object from one with 3, and the verdict
    could not tell them apart.

    This does NOT change what counts as a finding. It supplies the denominator
    those findings sit in, which is the thing a reader means by "how much of
    this paper actually checked out".
    """
    # TWO VOCABULARIES, AND READING ONLY THE OLDER ONE ZEROED THIS WHOLE TALLY.
    #
    # v1 findings carry a lowercase `severity` string on the
    # `consistent|indeterminate|suspicious|highly_suspicious|impossible` ladder.
    # findings-v2 carries `outcome` (`pass|problem|undecided`) and an INTEGER
    # `severity` 1-9, and the tally is computed BEFORE adjudication, when even
    # that integer is still `provisional_severity`. So `str(f["severity"])` fell
    # through to "unknown" for every v2 finding and `checks_total` came out 0.
    #
    # MEASURED 2026-08-22 over a 9-paper grok-4.6 batch: every paper reported
    # `checks_total 0 / by_severity {"unknown": N}` against a real 124 pass,
    # 61 problem, 28 undecided. That is not cosmetic -- `parallel.py` feeds this
    # dict straight into `adjudicate.build_docket(tally=...)`, so the adjudicator
    # was told on every paper that nothing had passed and nothing was flagged,
    # which is precisely the denominator its verdict rubric needs. Every report
    # also printed "Checks recorded as passing: 0" above ~30 passing checks.
    #
    # Classify on `outcome` when it is present and fall back to the v1 ladder,
    # so archived v1 runs and the legacy serial body keep tallying as before.
    _V1_PASS = {"consistent"}
    _V1_FLAG = {"impossible", "highly_suspicious", "suspicious"}
    _V1_REFUSED = {"indeterminate"}
    _OUTCOME = {"pass": "pass", "problem": "flagged", "undecided": "refused"}

    sev: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    reported_pass = 0
    reported_flag = 0
    reported_refused = 0
    for f in (findings or {}).get("findings") or []:
        if not isinstance(f, dict):
            continue
        raw_sev = f.get("severity")
        if raw_sev is None:
            raw_sev = f.get("provisional_severity")
        k = str(raw_sev) if raw_sev is not None else "unknown"
        sev[k] = sev.get(k, 0) + 1

        bucket = _OUTCOME.get(str(f.get("outcome") or "").strip().lower())
        if bucket is None:
            low = str(raw_sev or "").strip().lower()
            if low in _V1_PASS:
                bucket = "pass"
            elif low in _V1_FLAG:
                bucket = "flagged"
            elif low in _V1_REFUSED:
                bucket = "refused"
        if bucket is None:
            # Neither vocabulary spoke. Counted nowhere rather than guessed:
            # a finding silently binned as a pass is the failure this tally
            # exists to prevent.
            by_outcome["unclassified"] = by_outcome.get("unclassified", 0) + 1
            continue
        by_outcome[bucket] = by_outcome.get(bucket, 0) + 1
        if bucket == "pass":
            reported_pass += 1
        elif bucket == "flagged":
            reported_flag += 1
        else:
            reported_refused += 1

    collapsed = 0
    # THE TRUNCATION SIGNAL LIVES IN THE AGGREGATE, WHICH IS WHY IT IS COUNTED
    # HERE AND NOWHERE ELSE.
    #
    # Greg, 2026-08-10: a value that is impossible under round-half but
    # consistent under truncation "still deserves to be flagged in some way...
    # though I wouldn't want to classify it as suspicious in the findings". So
    # each such value is `consistent` per cell -- it can never become an
    # accusation -- and the fact is carried here instead.
    #
    # ONE rescue is a house style and carries no information. A high RATE does:
    # per Heathers, this class of anomaly is commoner in papers with more
    # serious problems, so the ratio is grounds to look harder rather than a
    # finding on its own. Same shape as `flag_round_n`, documented as "a weak
    # signal that escalates only alongside stronger findings".
    trunc = 0
    pop_sd = 0
    granularity_checks = 0
    # THE RECORDS BEHIND THE RATE, so `grace.summarise` can see a LEAN.
    #
    # The counters above answer "how many were rescued". They cannot answer the
    # question that separates rounding noise from anything else: did the
    # residuals lean one way? Fifty cells within tolerance is noise; forty-seven
    # of fifty leaning the same way is not, and no individual cell can show it.
    #
    # `grace.py` was written for exactly this and shipped with twelve tests and
    # one caller in `tools/regression.py`, reaching no report -- `handoff.py`
    # lists it as this repository's canonical inert module. Building the records
    # here, in the pass that already has every granularity payload in hand,
    # costs one list and makes the aggregate computable.
    grace_records: list[dict] = []
    _GRAN = {"grim_check", "grimmer_check", "grim_percentage", "grim_sweep",
             "debit_check", "sprite_reconstruct", "check_count_percent"}

    def _count_convention(payload: dict) -> None:
        nonlocal trunc, pop_sd, granularity_checks
        if not isinstance(payload, dict):
            return
        granularity_checks += 1
        if (payload.get("failure_mode") == "rounding_convention"
                or payload.get("rounding_convention") == "truncation"
                or payload.get("passes_under_truncation") is True):
            trunc += 1
        # THE POPULATION-SD CONVENTION, counted on exactly the same footing.
        #
        # Greg, 2026-08-10: "regarding the Population-SD convention, I changed
        # my mind and want it applied as well -- it would be inconsistent to do
        # the truncation check but not this." So the per-cell severity is now
        # `consistent` and the fact lives here as a rate, like truncation. A
        # convention that stops being a finding and is not counted anywhere has
        # simply been deleted, and the whole argument for de-escalating it was
        # that the aggregate is where it means something.
        #
        # `consistent_under_population_convention` is DEBIT's flag and is true
        # whenever the population reading works, INCLUDING when the sample
        # reading also works -- which is not the case being counted. Key on the
        # verdict fields, which the three tools set only when the population
        # convention is what CARRIED the value.
        rescued_by = None
        if (payload.get("failure_mode") == "rounding_convention"
                or payload.get("rounding_convention") == "truncation"
                or payload.get("passes_under_truncation") is True):
            rescued_by = "truncation"
        if (payload.get("failure_mode") == "sd_convention"
                or payload.get("outcome") == "sd_convention"
                or payload.get("sd_convention") == "population"):
            pop_sd += 1
            rescued_by = rescued_by or "population_sd"

        # RESIDUALS ONLY WHERE THE PAYLOAD ACTUALLY CARRIES BOTH NUMBERS.
        # `grace.record` computes `reported - nearest_consistent`, and the SIGN
        # is the entire point -- an unsigned magnitude cannot show a lean. Where
        # a tool does not report the nearest consistent value the record still
        # counts, with `residual: None`, and `summarise` runs its sign test over
        # the subset that has one. Inventing a residual to fill the column would
        # manufacture the lean this is built to measure.
        reported = payload.get("reported_mean")
        nearest = payload.get("nearest_consistent")
        if nearest is None:
            nearby = payload.get("possible_means_nearby")
            if isinstance(nearby, (list, tuple)) and len(nearby) == 1:
                nearest = nearby[0]
        try:
            grace_records.append(_grace.record(
                strict_ok=rescued_by is None,
                lenient_ok=True,
                grace=rescued_by,
                reported=reported if isinstance(reported, (int, float)) else None,
                nearest_consistent=nearest if isinstance(nearest, (int, float)) else None,
                note=str(payload.get("technique") or payload.get("failure_mode") or ""),
            ))
        except ValueError:
            pass          # a grace kind outside the closed vocabulary: skip the
                          # record rather than fail a run over bookkeeping

    for call in _tool_call_ledger(messages or [], STAGE1_TOOLS):
        try:
            payload = json.loads(call.get("result") or "{}")
        except (ValueError, TypeError):
            continue
        if call.get("tool_short") in _GRAN:
            _count_convention(payload)
        if call.get("tool_short") != "check_table":
            continue
        collapsed += len(payload.get("consistent_index") or [])
        # `check_table` batches, so most granularity checks never appear as
        # their own ledger entry -- the same batching that hid 96 of SPRITE's
        # 104 invocations from the archive's tool counts.
        for rec in (payload.get("results") or []):
            if isinstance(rec, dict) and rec.get("tool") in _GRAN:
                _count_convention(rec.get("result") or {})

    passed = reported_pass + collapsed
    total = passed + reported_flag + reported_refused
    return {
        "checks_passed": passed,
        "of_which_collapsed_by_check_table": collapsed,
        "checks_refused_indeterminate": reported_refused,
        "checks_flagged": reported_flag,
        "checks_total": total,
        "by_severity": sev,
        # The bucket each finding was actually counted in, so a reader can see
        # WHY a total is what it is -- and `unclassified` names findings whose
        # vocabulary neither branch recognised instead of hiding them in a pass.
        "by_outcome": by_outcome,
        # Reported as a RATE, never as a verdict. A reader who sees 1 of 40 is
        # looking at a house style; one who sees 15 of 20 alongside genuine
        # `impossible` findings is looking at something else.
        "rounding_convention": {
            "n_fit_only_under_truncation": trunc,
            "n_granularity_checks": granularity_checks,
            "note": (
                "Values that fail the round-half convention but are consistent if the "
                "reporter TRUNCATES (SPSS's default, and several journal styles). NOT a "
                "finding and never counted as one: a single instance is a house style. "
                "The RATE is the signal -- this class of anomaly is commoner in papers "
                "with more serious problems, so a high proportion is grounds to look "
                "harder, not evidence in itself."
            ),
        },
        # The SECOND convention, reported the same way and for the same reason
        # (Greg, 2026-08-10). Kept as its own key rather than folded into
        # `rounding_convention`: they are different conventions with different
        # innocent explanations, and a reader who sees a high rate needs to know
        # WHICH -- "this lab reports numpy's std" and "this journal truncates"
        # lead to different follow-up questions.
        # THE SET-LEVEL READING. `n_rescued` here and `n_fit_only_under_*` above
        # count the same events; this block adds the split by allowance and the
        # sign test over whichever residuals were available. No verdict: a lean
        # is evidence for a reader, and this toolkit has no calibrated threshold
        # for one.
        "grace": _grace.summarise(grace_records),
        "sd_convention": {
            "n_fit_only_under_population_sd": pop_sd,
            "n_granularity_checks": granularity_checks,
            "note": (
                "Values that fail under the sample (Bessel, n-1) SD but are consistent "
                "under the POPULATION (n) SD -- numpy's std default and Excel's STDEVP. "
                "NOT a finding and never counted as one: choosing a convention is not "
                "fabrication. The RATE is the signal, on the same reasoning as the "
                "rounding convention above."
            ),
        },
    }


#: How the tool server learns WHICH PAPER this run is about, without the model
#: being able to say. See `_build_mcp_config`.
PAPER_DIR_ENV = "METASCIENCE_PAPER_DIR"

#: Imported, never restated: `run_script` owns this name and reads it.
from .run_script import RUN_SLUG_ENV as _RUN_SLUG_ENV  # noqa: E402


def _build_mcp_config(paper_dir: str | Path | None = None,
                      mcp_stage: str | None = None,
                      run_slug: str | None = None,
                      mcp_tools: list[str] | None = None,
                      brief: bool = False) -> str:
    """Return a JSON string registering our stdio MCP server with the CLI.

    `paper_dir` is handed to the SERVER PROCESS, never to the model, and it is
    what lets `dispatch.check_table` adjudicate a variable's `provenance_quote`
    against the paper BEFORE the checks run rather than hours later.

    WHY THIS EXISTS. `Variable.bounds_are_stated` and
    `Variable.discreteness_source` both demand a pipeline-set
    `provenance_verdict` before they will license `impossible` -- deliberately,
    so the model cannot certify its own quote (#87). But the verdict was written
    by `_annotate_quotes`, which runs AFTER the model's tool calls. MEASURED
    across every archived run: NO variable has ever reached `check_table`
    carrying one. Both gates were therefore ABSOLUTE rather than evidential --
    a granularity or range failure could never reach `impossible` on the table
    path, whatever the paper actually said.

    An environment variable is the right channel precisely because it is the
    process-boundary version of `PIPELINE_ONLY_FIELDS`: the pipeline sets it,
    the model has no way to write it, and a tool that reads it is reading OUR
    claim about the run rather than the model's.
    """
    from .history_runtime import env as history_env
    # BOTH source roots of this tree, not only src/ (`forensic_pythonpath`).
    env = {"PYTHONPATH": forensic_pythonpath(), **history_env()}
    if paper_dir:
        env[PAPER_DIR_ENV] = str(paper_dir)
    if mcp_stage:
        # The server registers ONLY this role's tools (mcp_server.py,
        # MCP_STAGE_ENV). --allowedTools is an auto-approve list under
        # bypassPermissions, not a fence; this is the fence. Measured
        # 2026-08-21: the tool expert executed run_python_script 3x through
        # the unfiltered server.
        env["METASCIENCE_MCP_STAGE"] = str(mcp_stage)
    if run_slug:
        # WHICH RUN, on the same channel and for the same reason as the paper
        # directory: `run_python_script` persists every script under it, so two
        # runs sharing one paper directory stop sharing one scripts directory
        # (and one filename counter). See `run_script.RUN_SLUG_ENV`.
        env[_RUN_SLUG_ENV] = str(run_slug)
    if mcp_tools is not None:
        if not mcp_tools:
            raise ValueError("an empty tool manifest is not a toolset; refusing "
                             "to build a server that would serve nothing or "
                             "everything")
        # A pipeline's toolset: the server narrows the role's surface to it
        # and refuses to start on a manifest it cannot honour (fail-closed,
        # `mcp_server._manifest_tools`). Absent for every full-toolset run,
        # so their config bytes are unchanged.
        from .pipeline_config import MCP_TOOLS_ENV
        env[MCP_TOOLS_ENV] = ",".join(mcp_tools)
    if brief:
        # `tool_access: mcp_brief`: one-line descriptions plus describe_tool.
        env["METASCIENCE_MCP_BRIEF"] = "1"
    from . import integration

    config = {
        "mcpServers": {
            MCP_SERVER_NAME: {
                "command": sys.executable,
                "args": ["-m", integration.forensic_mcp_module],
                "env": env,
            }
        }
    }
    return json.dumps(config)


def _build_claude_cmd(
    system_prompt: str,
    allowed_tools: list[str],
    model: str = DEFAULT_MODEL,
    json_schema: dict | None = None,
    budget_usd: float | None = None,
    effort: str = DEFAULT_EFFORT,
    paper_dir: str | Path | None = None,
    denied_tools: list[str] | None = None,
    backend: "str | None" = None,
    max_turns: int | None = None,
    internet: bool = False,
    mcp_stage: str | None = None,
    vision: bool = False,
    run_slug: str | None = None,
    mcp_tools: list[str] | None = None,
    forensic_mcp: bool = True,
    tool_access: str = "mcp",
) -> Invocation:
    """Build one CLI invocation. Name kept: tests pin the positional signature.

    The PROMPT IS NOT HERE and this function still has no `prompt` parameter.
    Claude reads it from stdin (`-p` is a flag). Grok reads it from
    `--prompt-file`, which `_run_stage` writes just before spawn.

    Returns an ``Invocation`` (not a bare argv) so a Grok workdir cannot be
    silently dropped. Claude argv is byte-identical to the historical
    sequence, including the space-joined `--disallowedTools` quirk.

    `--allowedTools` does NOT restrict anything under `--permission-mode
    bypassPermissions`: it is an auto-approve list, not an allow-list.
    Observed consequence in a real Opus sweep: the model called `Bash` 8
    times and hand-wrote scipy. Restricting the built-in tool set is what
    actually enforces "use the validated implementations".
    """
    be = resolve_backend(backend)
    if tool_access == "skill" and forensic_mcp:
        return _build_skill_cmd(
            be, system_prompt=system_prompt, allowed_tools=allowed_tools,
            model=model, json_schema=json_schema, budget_usd=budget_usd,
            effort=effort, paper_dir=paper_dir, max_turns=max_turns,
            internet=internet, mcp_stage=mcp_stage, run_slug=run_slug,
            mcp_tools=mcp_tools)
    if tool_access == "mcp_brief" and forensic_mcp:
        allowed_tools = list(allowed_tools) + [_mcp("describe_tool")]
    return build_invocation(
        be,
        system_prompt=system_prompt,
        allowed_tools=allowed_tools,
        model=model,
        effort=effort,
        json_schema=json_schema,
        budget_usd=budget_usd,
        paper_dir=paper_dir,
        denied_tools=denied_tools,
        mcp_config_json=_build_mcp_config(paper_dir, mcp_stage=mcp_stage,
                                          run_slug=run_slug,
                                          mcp_tools=mcp_tools,
                                          **({"brief": True}
                                             if tool_access == "mcp_brief" else {})),
        max_turns=max_turns,
        python_executable=sys.executable,
        claude_builtin_tools=BUILTIN_TOOLS,
        claude_denied_tools=DENIED_TOOLS,
        internet=internet,
        mcp_stage=mcp_stage,
        run_slug=run_slug,
        vision=vision,
        **({"mcp_tools": list(mcp_tools)} if mcp_tools is not None else {}),
        **({} if forensic_mcp else {"forensic_mcp": False}),
    )


#: `tool_access: skill`: the only shell commands the agent may run. Under
#: Claude's `dontAsk` mode a command matching none of these is refused, and
#: `metascience tool run` itself serves only the stage's surface.
SKILL_ALLOWED = ("Bash(metascience tool run *)", "Bash(metascience tool describe *)",
                 "Bash(metascience tool list *)")


def _build_skill_cmd(be, *, system_prompt, allowed_tools, model, json_schema,
                     budget_usd, effort, paper_dir, max_turns, internet,
                     mcp_stage, run_slug, mcp_tools) -> Invocation:
    """The `tool_access: skill` launch (docs/specs/tool_access.md): no MCP
    server; `Read`, the web pair when the module has internet, and a shell
    fenced to `metascience tool ...`. The environment carries what the MCP
    config would have -- role, toolset manifest, paper, run -- so the
    command applies the same surface and writes the same receipts."""
    from .history_runtime import env as history_env
    builtin = ["Read", "Bash"] + (["WebSearch", "WebFetch"] if internet else [])
    denied = [t for t in DENIED_TOOLS if t not in builtin]
    allowed = ([t for t in allowed_tools if not t.startswith(MCP_TOOL_PREFIX)]
               + list(SKILL_ALLOWED))
    # `metascience tool run` is a console script: without PYTHONPATH it
    # imports the editable install's tree, not the one this run is from.
    env = {"PYTHONPATH": forensic_pythonpath(), **history_env()}
    if mcp_stage:
        env["METASCIENCE_MCP_STAGE"] = str(mcp_stage)
    if run_slug:
        env[_RUN_SLUG_ENV] = str(run_slug)
    if paper_dir:
        env[PAPER_DIR_ENV] = str(paper_dir)
    if mcp_tools is not None:
        from .pipeline_config import MCP_TOOLS_ENV
        env[MCP_TOOLS_ENV] = ",".join(mcp_tools)
    return build_invocation(
        be, system_prompt=system_prompt, allowed_tools=allowed, model=model,
        effort=effort, json_schema=json_schema, budget_usd=budget_usd,
        paper_dir=paper_dir, denied_tools=denied,
        mcp_config_json=json.dumps({"mcpServers": {}}),   # `{}` is refused by the CLI
        max_turns=max_turns, python_executable=sys.executable,
        claude_builtin_tools=builtin, claude_denied_tools=denied,
        forensic_mcp=False, permission_mode="dontAsk", env_overlay=env,
        settings_json=skill_guard_settings())


def skill_guard_settings() -> str:
    """`--settings` for a skill launch: the PreToolUse hook that is the real
    shell fence (`skill_guard.py` says why the permission pattern is not).
    Run by file path with `-I`, and `|| exit 2` so a guard that cannot run
    blocks instead of letting the command through."""
    import shlex
    from . import skill_guard
    hook = (f"{shlex.quote(sys.executable)} -I "
            f"{shlex.quote(str(Path(skill_guard.__file__).resolve()))} || exit 2")
    return json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": hook}]}]}})


def _build_env() -> dict[str, str]:
    """Env for the subprocess; strip CLAUDECODE so a parent Claude Code session doesn't bleed in."""
    from .history_runtime import env as history_env
    return {**{k: v for k, v in os.environ.items() if k != "CLAUDECODE"}, **history_env()}


def _build_track_env() -> dict[str, str]:
    """`_build_env` for a deterministic track child (`python -m
    forensic_metascience_ai_toolkit.<track>`): it imports the toolkit, so it gets this
    tree's source roots (`forensic_pythonpath`), not the editable install's."""
    return {**_build_env(), "PYTHONPATH": forensic_pythonpath()}


PARTIAL_COVERAGE_NOTE = (
    "PARTIAL COVERAGE: the forensic sweep was stopped early by the spend cap, so the paper "
    "was NOT fully checked. Absence of a finding here is not evidence of absence. Re-run with "
    "a higher --max-budget-usd for full coverage."
)

PARTIAL_COVERAGE_TIMEOUT_NOTE = (
    "PARTIAL COVERAGE: the forensic sweep was stopped because it exceeded the "
    "per-stage wall-clock timeout, so the paper was NOT fully checked. Absence "
    "of a finding here is not evidence of absence. The last tool in flight, if "
    "any, is recorded on the stage in run_meta.json."
)

PARTIAL_COVERAGE_EDITORIAL_TIMEOUT_NOTE = (
    "PARTIAL COVERAGE: the editorial pass was stopped by the per-stage "
    "wall-clock timeout. The sweep findings stand; the narrative may be "
    "incomplete. Absence of a finding in the prose is not evidence of absence."
)

MIN_STAGE2_BUDGET_USD = 0.20
REPAIR_BUDGET_USD = 0.10

# Built-in tools the stages may use. `Read` is required (the sweep reads
# body.md); everything statistical must come from the MCP forensic tools, which
# are supplied separately via --mcp-config and are unaffected by this list.
BUILTIN_TOOLS = ["Read"]

# Explicitly denied as well as excluded, because these are the routes by which
# a model does statistics outside the validated toolkit or reaches the network.
#
# Evidence this is load-bearing, from a real pre-sandbox run
# (cerebrolysin_papers/done/10.1002--adbi.202300439, 2026-07-17): stage 1 made
# SIX Bash calls and stage 2 one more, hand-writing scipy in `python3 -c` for
# the two-tailed lifespan p and the r-squared arithmetic. Two of that report's
# three most prominent findings were therefore computed by model-written code
# rather than by a validated tool, while looking identical in the report.
#
# `ToolSearch` is denied too: it is how a model discovers and loads schemas for
# tools outside the declared surface. The same run used it seven times. The
# allowlist is only meaningful if nothing can extend it at runtime.
DENIED_TOOLS = [
    "Bash", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch", "Task", "ToolSearch",
]

#: STAGE 2 RUNS UNDER THE SAME DENY-LIST, AND A CONSTANT THAT SAID OTHERWISE
#: USED TO SIT HERE. It computed the deny-list minus `Bash`, was passed to
#: nothing, and carried a long argument for a decision that had not been made.
#:
#: The argument came from misreading Greg. He wrote, 2026-08-13, that the second
#: agent should have "as much capability as [me], which is to say as much as
#: possible" -- and I read it as shell access. He corrected it the same day:
#: "what you call Bash access isn't python tool use, but some other means...
#: When I inquired about raising its capability to parity with you, I meant in
#: its ambit for creative, adversarial thinking as governed by the prompt."
#:
#: So the capability gap is real and the remedy is not a shell. A post-hoc
#: reviewer on this same model does catch what the pipeline misses, and the
#: advantage was never intelligence: it is a SECOND PASS over work already
#: written, comparative base rates, and an adversarial frame. All three are
#: given by the prompt and by `second_look`, which hands stage 2 the decidable
#: weaknesses rather than hoping it re-derives them.
#:
#: The dead constant is removed rather than kept "for when we enable it": an
#: unused definition wearing a persuasive rationale is how a decision nobody
#: made becomes one nobody questions.


class BudgetExhausted(RuntimeError):
    """Stage 1 left too little budget for a meaningful editorial pass.

    Raised instead of launching a stage 2 that is guaranteed to die, which
    previously produced a hollow report from a doomed run.
    """


def _safe_on_progress(on_progress, snapshot: dict) -> None:
    """A broken status line must not cost a paid stage or skip extraction."""
    if on_progress is None:
        return
    try:
        on_progress(snapshot)
    except Exception:  # noqa: BLE001 -- a broken display must not cost a run
        pass


def _kill_subprocess_group(proc) -> None:
    """SIGKILL the process group, falling back to the one pid.

    Grok (and Claude) spawn an MCP server as a child. Killing only the CLI
    leaves that grandchild holding stdout, so `proc.wait()` blocks for the
    grandchild's lifetime -- the forensic-track client already measured this.
    `start_new_session=True` on the Popen is what makes the group ours.
    A fake/test proc with no pid still gets `.kill()`.
    """
    import signal
    pid = getattr(proc, "pid", None)
    if pid:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
            return
        except (ProcessLookupError, PermissionError, OSError):
            pass
    try:
        proc.kill()
    except (ProcessLookupError, AttributeError):
        pass


def _live_tool_name(block: dict) -> str:
    """Short name for the live status line from one `tool_use` block.

    After `normalize_event`, a Grok forensic call is already rewritten to
    `mcp__forensic_metascience__grim_check`. Before that rewrite (or for a
    still-wrapped `use_tool`), lift the inner `tool_name`. The status line
    must never show the MCP prefix -- that is plumbing, not what the
    operator is watching for.
    """
    name = str(block.get("name") or "")
    if name == "use_tool":
        inp = block.get("input") if isinstance(block.get("input"), dict) else {}
        raw = inp.get("tool_name") or name
        name = str(raw)
    if "__" in name:
        return name.rpartition("__")[2] or name
    return name


def _stall_seconds() -> float:
    """How long a stage may emit NOTHING before it is treated as dead.

    Separate from the duration timeout on purpose -- see `_watch_for_stall`.
    0 or a bad value disables it, so an operator debugging a slow backend can
    turn it off without also removing the duration cap.
    """
    raw = os.environ.get("METASCIENCE_STAGE_STALL_SECONDS", "")
    try:
        return float(raw) if raw.strip() else STAGE_STALL_SECONDS_DEFAULT
    except ValueError:
        return STAGE_STALL_SECONDS_DEFAULT


#: Ten minutes. The longest quiet gap seen inside a HEALTHY stage on the
#: 2026-08-22 batches was well under a minute (grok emits a stream event per
#: turn and per tool call), so this leaves an order of magnitude of headroom
#: before it can cut a working stage short.
STAGE_STALL_SECONDS_DEFAULT = 600.0


async def _run_stage(cmd, prompt, verbose=False, timeout=None, on_progress=None, stage_label=""):
    from forensic_metascience_ai_toolkit.runtime import _run_stage as run
    return await run(cmd, prompt, verbose, timeout, on_progress, stage_label,
                     preflight=_assert_ready, check_mcp=True, build_env=_build_env,
                     guard=usage_guard, kill=_kill_subprocess_group, stall=_stall_seconds)



#: WHAT THIS RUN HAS SPENT SO FAR, survivable across a crash.
#:
#: A run that dies mid-pipeline used to leave NO cost record at all: run_meta.json
#: is written at the end, so an exception before that point meant real money was
#: spent and nothing said so. Measured: a paper crashed at Popen after a
#: 22-minute stage-1 sweep, and the only evidence it had cost anything was the
#: wall-clock gap in a log.
#:
#: CONTEXT-LOCAL, not module-global, and the difference was $6.96 of phantom
#: spend. As a module global, `batch.py`'s concurrent workers shared one
#: ledger: every `reset_spend()` zeroed every in-flight paper's count, and
#: every `record_spend` landed in whichever papers finished later. MEASURED
#: 2026-08-22 (four-paper grok batch, 4 workers): the first finisher reported
#: total_cost_usd $2.11 while its own stages summed to $0.86, and the four
#: "totals" ($9.70) each approximated the WHOLE BATCH's running spend at that
#: paper's finish -- true spend was ~$0.7/paper, and a published comparison
#: said 7x when the truth was ~2x. asyncio tasks copy the ambient context at
#: creation, so a ContextVar set by `reset_spend()` inside `analyze_paper*`
#: is private to that paper's task tree with no call-site changes anywhere.
#:
#: The FALLBACK dict keeps the old lifetime for callers that never reset: the
#: number still has to outlive the exception that unwinds the pipeline, so a
#: crash record written from an except block sees what was spent.
_SPEND_VAR: "contextvars.ContextVar[dict | None]" = contextvars.ContextVar(
    "metascience_spend", default=None)
_SPEND_FALLBACK: dict = {"usd": 0.0, "stages": []}


def _spend_ledger() -> dict:
    led = _SPEND_VAR.get()
    return led if led is not None else _SPEND_FALLBACK


def reset_spend() -> None:
    """Give the CURRENT context a fresh, private ledger.

    Always REBIND -- never clear an inherited dict in place. A clear-in-place
    variant was tried the day the ContextVar landed (to serve the crash path)
    and it quietly reintroduced the contamination whenever the spawning
    context already carried a ledger: every worker task inherited the SAME
    dict, adopted it, and the batch was shared again -- caught by
    tests/test_spend_ledger.py running under the parallel suite. The crash
    path is served differently: `cli.run_analysis` attaches `spend_so_far()`
    to the escaping exception INSIDE the task (where this context is
    visible), so the number rides the exception across the asyncio.run
    boundary instead of relying on object identity.
    """
    _SPEND_VAR.set({"usd": 0.0, "stages": []})


#: Usage fields copied onto every ledger row. TOKENS BELONG HERE for the same
#: reason cost and wall-clock already do: this is the one place that sees EVERY
#: attempt, including the ones a retry discards. `parallel` briefly carried a
#: `prior_attempt` dict through three return paths to recover a discarded
#: attempt's numbers; that was six plumbing sites duplicating a record this
#: function was already keeping, and it missed the legacy `stage2_editorial`
#: path and the tool agent's internal empty-dump retry, which never pass
#: through it.
_SPEND_USAGE_FIELDS = ("input_tokens", "output_tokens",
                       "cache_creation_input_tokens", "cache_read_input_tokens")


def record_spend(label: str, stage: dict) -> None:
    """Add one completed stage's cost to the running total.

    Called once per ATTEMPT, not once per stage: retries arrive here under
    `f"{label}_retry"`. Two attempts can share a label -- the tool agent
    retries inside `_run_stage_requiring_forensic_tools` and `parallel` retries
    around it -- so a consumer grouping by label must SUM rather than assume
    one row per name.
    """
    led = _spend_ledger()
    usd = float(stage.get("cost_usd") or 0.0)
    led["usd"] += usd
    row = {
        "stage": label,
        "cost_usd": usd,
        "wall_seconds": stage.get("wall_seconds"),
        "return_code": stage.get("return_code"),
        "is_error": stage.get("is_error"),
    }
    for f in _SPEND_USAGE_FIELDS:
        row[f] = stage.get(f)
    led["stages"].append(row)


def spend_so_far() -> dict:
    """A copy, so a caller writing a crash record cannot mutate the ledger."""
    led = _spend_ledger()
    return {"total_cost_usd": round(led["usd"], 6),
            "stages": list(led["stages"])}


from forensic_metascience_ai_toolkit.track_contracts import _FENCED_JSON_RE as _FENCED_JSON_RE


#: Keys that identify one of OUR documents rather than an arbitrary object that
#: happens to be embedded in the transcript (a tool result, an argument blob).
#: A salvaged object must look like the thing the stage was asked to produce.
from forensic_metascience_ai_toolkit.track_contracts import _DOCUMENT_MARKERS as _DOCUMENT_MARKERS


from forensic_metascience_ai_toolkit.track_contracts import _salvage_documents as _salvage_documents


from forensic_metascience_ai_toolkit.track_contracts import _extract_json as _extract_json
from forensic_metascience_ai_toolkit.track_contracts import (
    ACCEPTED_TOOL_CALL_PATH as ACCEPTED_TOOL_CALL_PATH,
    accepted_tool_call_note as accepted_tool_call_note,
    mark_no_document as mark_no_document,
)


async def _repair_json(
    raw_text: str,
    schema: dict,
    model: str,
    verbose: bool,
    timeout: int | None,
    effort: str = DEFAULT_EFFORT,
    backend=None,
    tool_free: bool = False,
) -> dict | None:
    """Last-resort: ask the model to re-emit the JSON conforming to schema.

    `tool_free` (a partial pipeline's repair): no tools at all. Only Claude
    can honour it (`--tools ""`, strict empty MCP config); `parallel` does not
    call this for a partial pipeline on Codex or Grok, whose CLIs keep a
    read-only shell / `read_file` -- it fails closed and names the gap. If a
    caller does pass it there, the forensic MCP server is still withheld. The
    complete review's repair keeps its historical command.
    """
    prompt = (
        "The following analysis output should have been a single JSON document "
        "conforming to the provided schema, but it did not parse. Re-emit ONLY "
        "the JSON (no commentary), preserving all content:\n\n" + raw_text[:100_000]
    )
    be = resolve_backend(backend)
    # Prompt via stdin (Claude) / prompt-file (Grok): this one carries up to
    # 100 KB of raw model output, which is already within a rounding error of
    # the 128 KB per-argument ceiling.
    if be.supports_budget:
        # Claude repair argv kept as the historical sequence: no MCP, a spend
        # cap. Routing it through `_build_claude_cmd` would add --mcp-config
        # and change a path that is supposed to stay byte-identical.
        cmd = [
            "claude",
            "-p",
            "--model", model,
            "--effort", effort,
            # The repair path is itself a recovery from a budget stop, so it must
            # be capped too -- previously it was the one uncapped call in the run.
            "--max-budget-usd", str(REPAIR_BUDGET_USD),
            "--json-schema", json.dumps(schema),
            "--output-format", "stream-json",
            "--verbose",
        ]
        if tool_free:
            # `{}` is not an empty MCP config to the CLI ("mcpServers: expected
            # record, received undefined"); it needs the key. Every partial
            # pipeline's repair failed on it until 2026-10-18.
            cmd += ["--tools", "", "--strict-mcp-config",
                    "--mcp-config", json.dumps({"mcpServers": {}})]
    else:
        # Grok has no spend cap. A turn cap is the honest substitute; record
        # that it is turns, not spend, in the stage meta via max_turns=1.
        cmd = _build_claude_cmd(
            system_prompt="Re-emit only the JSON document, no commentary.",
            allowed_tools=list(BUILTIN_TOOLS),
            model=model,
            effort=effort,
            json_schema=schema,
            backend=be,
            max_turns=1,
            **({"forensic_mcp": False} if tool_free else {}),
        )
    try:
        stage = await _run_stage(cmd, prompt, verbose=verbose, timeout=timeout)
    except (StageError, asyncio.TimeoutError, MCPUnavailable):
        return None
    parsed, _ = _extract_json(stage)
    return parsed


def _stage_meta(stage: dict, model: str, **extra) -> dict:
    meta = {
        "model": model,
        "cost_usd": stage["cost_usd"],
        "input_tokens": stage["input_tokens"],
        "output_tokens": stage["output_tokens"],
        # The variable that DOMINATES spend, and the one this record used to
        # omit entirely. Cache tokens are separate counters in the API's usage
        # block, not a subset of `input_tokens`. MEASURED on the stage-1 sweep
        # of eval/ground_truth/papers/10.3389--fpsyg.2019.02949: input_tokens
        # 22, cache_creation 171,926, cache_read 1,176,684, cost $4.30. Without
        # these two, run_meta.json reported 22 input tokens for a $4.30 stage
        # and no amount of arithmetic on it could explain the bill.
        # `.get` rather than `[]`: results assembled by paths older than this
        # (and every hand-built test fixture) have no such key, and a KeyError
        # here would lose a paid analysis over a metadata field.
        "cache_creation_input_tokens": stage.get("cache_creation_input_tokens", 0),
        "cache_read_input_tokens": stage.get("cache_read_input_tokens", 0),
        "wall_seconds": round(stage["wall_seconds"], 2),
        "return_code": stage["return_code"],
        "is_error": stage["is_error"],
        # Without this, a run killed by the budget cap is indistinguishable
        # from a clean finish in run_meta.json.
        "error_subtype": stage.get("error_subtype"),
        "truncated_by_budget": _stage_hit_budget(stage),
        "truncated_by_timeout": _stage_hit_timeout(stage),
    }
    if stage.get("cost_reported") is False:
        # The backend reported no cost (Codex: tokens only), so `cost_usd`
        # above is 0.0 by default, not a measured zero.
        meta["cost_reported"] = False
    if stage.get("result_event") is False:
        # The stream ended without the CLI's final `result` event: the cost,
        # the token totals and the structured output it carries never came.
        # Recorded only when False, so a complete stage's meta is unchanged.
        meta["result_event"] = False
        if stage.get("stdout_ended_mid_line"):
            meta["stdout_ended_mid_line"] = True
    if stage.get("cli_error_subtype"):
        # The CLI refused the output and `parse_output` proved the refusal
        # wrong (see `_analyst._final_after_placeholders`). Kept as evidence.
        meta["cli_error_subtype"] = stage["cli_error_subtype"]
    if stage.get("budget_cap_usd") is not None:
        # The cap this stage ran under, so a `truncated_by_budget` stage says
        # how much it was allowed (2026-10-18: a tools_only run's tools agent
        # was silently capped at 40% of the paper's budget).
        meta["budget_cap_usd"] = round(stage["budget_cap_usd"], 4)
    if stage.get("current_tool"):
        meta["current_tool"] = stage["current_tool"]
    if stage.get("tool_calls") is not None:
        meta["tool_calls"] = stage["tool_calls"]
    if stage.get("llm_backend"):
        meta["llm_backend"] = stage["llm_backend"]
    if stage.get("mcp_discovery") is not None:
        meta["mcp_discovery"] = stage["mcp_discovery"]
    if stage.get("usage_guard"):
        meta["usage_guard"] = stage["usage_guard"]
    # `model` above is the alias REQUESTED. These are what actually ran, and the
    # two diverge silently whenever the API refuses and the CLI falls back --
    # verified on this repo's own corpus, where a run recorded as `fable` was
    # performed by claude-opus-4-8 and billed $2.799 of its $2.807 to opus.
    meta.update(_resolved_models(stage.get("messages") or []))
    meta.update(extra)
    return meta


def _error_subtype(result_event: dict) -> str | None:
    """What actually went wrong, for a `result` event carrying `is_error`.

    The CLI's `subtype` describes the transport, not the outcome: a hard API
    failure arrives as `subtype="success"` alongside `is_error=True`. Recording
    that verbatim labels a stage that did no work "success", which is how a
    failed run gets mistaken for a committable one -- an eval run that died in
    2.34s on `output_config.effort 'max' is not supported` was written to
    run_meta.json as `error_subtype: "success"`, and the scorecard it produced
    looked like a genuine regression rather than a broken invocation.

    `terminal_reason` ("api_error") is the field that says what happened, so
    prefer it whenever `subtype` would otherwise call a failure a success.
    Real subtypes -- `error_max_budget_usd`, `error_timeout` -- are untouched,
    so `_stage_hit_budget` keeps working.
    """
    subtype = result_event.get("subtype")
    if not subtype or subtype == "success":
        return result_event.get("terminal_reason") or subtype
    return subtype


def _stage_hit_budget(stage: dict) -> bool:
    """True if this stage was cut short by the spend cap rather than finishing."""
    return bool(stage.get("is_error")) and str(stage.get("error_subtype") or "").startswith(
        "error_max_budget"
    )


#: The two ways a stage is CUT OFF rather than finished. They are reported
#: separately (`error_stalled` is a backend that stopped answering,
#: `error_timeout` is a budget decision) but every consumer that asks "was this
#: stage truncated?" must treat them alike -- the PARTIAL COVERAGE limitation,
#: `truncated_by_timeout`, and the report's own honesty about its reach all
#: depend on it. A new subtype that only half the predicates know about is the
#: guard-that-stops-guarding failure, and this one was caught by its own test.
_CUT_OFF_SUBTYPES = ("error_timeout", "error_stalled")


def _stage_hit_timeout(stage: dict) -> bool:
    """True if this stage was cut off -- by the wall-clock cap OR by silence."""
    return bool(stage.get("is_error")) and str(
        stage.get("error_subtype") or "") in _CUT_OFF_SUBTYPES



def _provenance(backend=None, prompt_blob: str | None = None) -> dict:
    """WHICH CODE AND WHICH PROMPTS produced this run.

    `version` is the package version and moves about once a month; the prompts
    and the registry move several times a day. So two runs of "the same
    toolkit" can be two different experiments and nothing recorded the
    difference.

    THIS IS NOT BOOKKEEPING. It is the precondition for every comparison this
    project needs to make. The three archived same-paper repeat sets cannot be
    used as a run-to-run noise floor -- the thing the whole cheaper-model study
    is gated on -- precisely because no run records a code version or a prompt
    hash, so a difference between two runs cannot be attributed to chance rather
    than to a commit landing between them. Same problem for any before/after
    claim about a fix.

    Hashes rather than the text: the prompts are ~109 KB and nobody wants them
    in every run_meta, but equality is all a comparison needs.
    """
    import hashlib

    # The git probe lives in `version.py` -- it is the same question the version
    # string asks ("what code is this?"), and two copies of a three-state dirty
    # check is two places for one of them to regress to two states. The
    # commentary on why `git_dirty` has three states, and on why the dirty probe
    # needs its own `try`, is there.
    from .version import git_state

    out: dict = dict(git_state())

    try:
        # `prompt_blob` lets the caller name WHICH prompts identify its run:
        # the parallel pipeline hashes tool_expert + science_error +
        # adjudication, because fingerprinting the legacy stage prompts there
        # would leave a science_error.md edit invisible to the recorded hash
        # -- the exact unattributable-difference failure this field exists to
        # prevent.
        #
        # THE DEFAULT IS THE PARALLEL TRIO, changed 2026-09-04 as prerequisite
        # (b) for the legacy deletion. It used to be the legacy stage pair, and
        # the bare `_provenance()` at `cli.py`'s version verb takes the default
        # -- so `metascience --verbose` reported the fingerprint of prompts the
        # live pipeline does not send, and after the deletion would have raised
        # AttributeError on a retired function. The legacy body passes its own
        # blob explicitly and is unaffected while it lives.
        if prompt_blob is None:
            from .core import prompts as _prompts

            prompt_blob = (_prompts.tool_expert_system_prompt(figures=False)
                           + "\x00" + _prompts.science_error_system_prompt()
                           + "\x00" + _prompts.adjudication_system_prompt())
        out["prompt_sha256"] = hashlib.sha256(
            prompt_blob.encode("utf-8")).hexdigest()[:16]
    except Exception:  # noqa: BLE001 -- provenance must never break a run
        pass

    try:
        from . import registry as _registry

        surface = json.dumps(
            [[s.name, sorted(s.schema()), s.description] for s in _registry.SPECS],
            sort_keys=True, default=str,
        )
        out["registry_sha256"] = hashlib.sha256(surface.encode("utf-8")).hexdigest()[:16]
    except Exception:  # noqa: BLE001
        pass

    try:
        be = resolve_backend(backend)
        out["llm_backend"] = be.name
        out["backend_binary_version"] = backend_binary_version(be)
        out["backend_default_model"] = be.default_model
        limitation = sandbox_limitation_sentence(be)
        if limitation:
            out["sandbox_limitation"] = limitation
    except Exception:  # noqa: BLE001 -- provenance must never break a run
        pass
    return out


async def analyze_paper(
    paper_path: str,
    verbose: bool = False,
    timeout: int | None = None,
    mode: str = "two_stage",
    budget_usd: float | None = None,
    model: str | None = None,
    effort: str | None = None,
    figures: bool = False,
    image_forensics: bool = True,
    text_forensics: bool = True,
    on_progress: Callable[[dict], None] | None = None,
    extra_supplements=None,
    backend: str | None = None,
    image_segment_montages: bool = False,
    image_reassemble_tiles: bool = False,
    pipeline=None,
) -> dict:
    """
    Run forensic metascience analysis on a paper.

    `pipeline` (a `pipeline_config.PipelineConfig`) selects the modules that
    run and the tools agent's toolset; when given, it decides `figures`,
    `image_forensics`, `text_forensics` and the image options, and those
    arguments are ignored. None is the complete review the flags describe.

    `image_forensics` runs the independent detection and AI-screening pipeline
    concurrently with the analysts (enabled by default).
    It is a SEPARATE flag from `figures` on purpose:
    `figures` governs the LLM reading values off plots, which is off by
    decision because value-reading is unreliable; pixel comparison has
    neither that failure mode nor that rationale.

    `text_forensics` runs the deterministic tortured-phrases track the same
    way (see `_run_text_track`). Default ON, unlike the
    image track: it is free (no API spend), fast, its findings arrive
    quarantined, and a missed mill paper is the costlier error.

    Args:
        paper_path: Path to a paper directory (containing body.md and a PDF),
                    a PDF file, or a markdown file.
        extra_supplements: Supplementary files named with `--supplement`, which
                    may live outside the paper directory. They are swept exactly
                    as discovered ones are. Passing them is what makes the flag
                    mean anything: it used to reach the gate and stop there, so
                    it bought a proceed for a file the sweep never opened.
        verbose: Print progress messages.
        on_progress: Optional callback receiving live counter snapshots from
                     each stage (tool calls, tokens, elapsed) so a caller can
                     draw a status line. Exceptions raised by it are swallowed
                     -- a display must never cost a paid run.
        timeout: Optional per-stage subprocess timeout in seconds.
        mode: "parallel" -- the only pipeline. `two_stage` is a deprecated
              alias for it; anything else raises.
        budget_usd: Optional total budget, split tool 0.40·B, science 0.25·B,
                    adjudicator the rest with a $0.20 floor.
        model: Claude model alias passed to the CLI.
        effort: Reasoning effort passed to the CLI (low|medium|high|xhigh|max).

    Returns:
        See `parallel.analyze_paper_parallel`.
    """
    if mode not in ("parallel", "two_stage"):
        raise ValueError(
            f"Unknown mode: {mode!r}. The only pipeline is 'parallel'; "
            "'two_stage' is a deprecated alias for it. The serial "
            "sweep -> editorial pipeline was removed in v1.27.0 -- see "
            "CHANGELOG.md, and `metascience runs` for reading its archived "
            "output, which every reader still supports.")
    # `two_stage` is a deprecated ALIAS for the parallel pipeline, not a
    # sibling: the serial body it once named was deleted in v1.27.0.
    from . import parallel as _parallel
    if mode == "two_stage" and verbose:
        print("[deprecation] mode='two_stage' is an alias for 'parallel'")
    result = await _parallel.analyze_paper_parallel(
        paper_path, verbose=verbose, timeout=timeout,
        budget_usd=budget_usd, model=model, effort=effort,
        figures=figures,
        image_forensics=image_forensics, text_forensics=text_forensics,
        on_progress=on_progress, extra_supplements=extra_supplements,
        backend=backend, image_segment_montages=image_segment_montages,
        image_reassemble_tiles=image_reassemble_tiles, pipeline=pipeline)
    result["mode_requested"] = mode
    result["run_meta"]["mode_requested"] = mode
    return result


def _repro_entries(result: dict):
    """Every object in a result that carries a `reproduction` string.

    The HEADLINE was the omission. `report.schema.json` REQUIRES a
    `reproduction` on the headline object, the consumers read
    `reproduction_valid` off it, and this annotator never walked it -- so the
    flag was absent, absence is not `False`, and the single most prominent
    command in the review was offered verbatim no matter what it did. It is the
    one command a reader is most likely to paste.

    `report.md` has since stopped printing any reproduction command, so the
    consumers of this flag are now `findings.json`, `run_meta.reproducibility`
    and the viewer bundle (`bundle.reproHtml`), which is the only surface that
    still hands a reader a command.

    The label yielded for a finding is its identity as `finding_view.ref`
    spells it -- `finding_id` on a v2 row, `id` on an archived v1 row --
    falling back to the row's index. It reaches a reader only inside
    `reproducibility.problems` messages; until 2026-09-05 every v2 row was
    labelled by its INDEX (`finding[0]:`) because this read the v1 `id`.

    Only the `findings` container is walked. This also walked the serial
    pipeline's editorial report (the `report_obj` container); no writer has
    produced that structure since v1.27.0, so the read returned None on every
    run and was residue that `tests/test_v1_residue_ratchet.py` could not see
    while this file was excluded from it by name.
    """
    from . import finding_view as _fv
    container = result.get("findings")
    if not isinstance(container, dict):
        return
    head = container.get("headline")
    if isinstance(head, dict):
        yield "headline", head
    for i, f in enumerate(container.get("findings") or []):
        if isinstance(f, dict):
            yield (_fv.ref(f) or str(i)), f


#: Executed reproduction commands, keyed by the exact command string.
#: The CLI costs ~2.4s of start-up per invocation and a report repeats the same
#: command across containers (the sweep's finding and the editorial finding that
#: cites it), so without this the same subprocess runs two or three times per
#: finding. Only reviewed calculation commands may execute; the execution
#: policy lives in evaluation.deterministic beside the subprocess call.
_REPRO_RUN_CACHE: dict[str, dict] = {}


def _run_repro_cached(command: str, timeout: int = 90,
                      claimed_severity: str | None = None,
                      claimed_outcome: str | None = None) -> dict:
    """`run_reproduction`, memoised, and unable to lose a paid analysis.

    `run_reproduction` catches TimeoutExpired and OSError but calls
    `shlex.split` inside the same try, and shlex raises ValueError -- not an
    OSError -- on an unterminated quote. VERIFIED: `metascience grim 5.5 30
    --note 'oops` passes the static check and then raises `ValueError: No
    closing quotation`. `write_review_outputs` does not guard its annotation
    pass, so before this the write path would have died on a stray apostrophe
    after both stages were billed. `ran: False` leaves the static verdict
    standing, which is the same treatment a timeout gets.
    """
    from .evaluation.deterministic import run_reproduction

    # THE CACHE KEY INCLUDES THE CLAIM, and must. The verdict now depends on
    # what the FINDING asserted, not on the command alone, so two findings
    # citing the same command with different severities are different
    # questions. Keyed on the command only, the second would silently inherit
    # the first one's agreement -- a fresh instance of the bug this change
    # exists to close.
    # The outcome is part of the QUESTION now, so it must be part of the
    # key: two findings sharing a command but claiming different outcomes
    # get different answers, and a shared cache entry would hand the
    # second one the first one's verdict.
    key = (command, claimed_severity, claimed_outcome)
    if key not in _REPRO_RUN_CACHE:
        try:
            out = run_reproduction(command, timeout=timeout,
                                   claimed_severity=claimed_severity,
                                   claimed_outcome=claimed_outcome)
        except Exception as exc:  # noqa: BLE001 -- never lose a paid analysis
            out = {"ran": False, "executed": False, "ok": False, "valid": True,
                   "agrees": None,
                   "problems": [f"could not execute: {exc}"]}
        _REPRO_RUN_CACHE[key] = out
    return _REPRO_RUN_CACHE[key]


def _annotate_quotes(result: dict, paper_path: str | Path | None) -> dict:
    """Say whether each finding's `quote` can actually be found in the paper.

    Same contract as `_annotate_reproductions`: pipeline-set, idempotent, and
    it never raises. A quote the reader is shown as though it were copied out
    of the paper has to have been checked against the paper, and a
    self-assessment written by the model that produced it is not a check.

    Silent on failure BY DESIGN. If the paper cannot be opened, no verdict is
    written at all -- stamping several hundred findings `unverified` because we
    could not read the source would be the house mistake in a new field: our
    failure, reported in the grammar of a claim about their work.

    BUT THE MODEL-SUPPLIED FIELDS ARE STRIPPED UNCONDITIONALLY FIRST, even when
    there is no paper to verify against. The three fields are schema-declared,
    so the model can emit them, and an early return on a missing `paper_path`
    used to let a forged `quote_verified: "verbatim"` survive into the viewer.
    `paper_path` is absent on result-assembly paths that never recorded it, so
    this is reachable. Verified: `_annotate_quotes(result, None)` left a forged
    verdict intact. Silence must mean "we said nothing", not "we passed the
    model's claim through".
    """
    findings = (result.get("findings") or {}).get("findings")
    if isinstance(findings, list):
        for finding in findings:
            if isinstance(finding, dict):
                for stale in ("quote_verified", "quote_source", "quote_problem"):
                    finding.pop(stale, None)
    # The ANATOMY carries quotes too, and one of them is load-bearing for
    # severity: a variable's `provenance_quote` is the evidence that the paper
    # STATED its scale bounds, and stated bounds are what let GRIM/SPRITE reach
    # `impossible` instead of `suspicious`. That promotion used to rest on the
    # model's own `confidence: "high"` with the quote never checked. Strip any
    # model-authored verdict on the same unconditional terms as above.
    anatomy = (result.get("findings") or {}).get("anatomy")
    anatomy_records: list[dict] = []
    if isinstance(anatomy, dict):
        for key in ("variables", "tests", "hypotheses", "studies"):
            for rec in anatomy.get(key) or []:
                if isinstance(rec, dict):
                    rec.pop("provenance_verdict", None)
                    anatomy_records.append(rec)
    if not paper_path:
        return result
    try:
        from . import quotes as _quotes
        pd = Path(paper_path)
        pd = pd if pd.is_dir() else pd.parent
        if isinstance(findings, list):
            _quotes.annotate(findings, pd)
        if anatomy_records:
            hay = _quotes.build_haystack(pd)
            folded = _quotes.fold_haystack(hay) if hay else None
            # An empty haystack means we could not read the paper. Stamping
            # everything `unverified` then would report OUR failure as a fact
            # about their variables -- the same rule the findings pass follows.
            if hay:
                for rec in anatomy_records:
                    quote = rec.get("provenance_quote")
                    if isinstance(quote, str) and quote.strip():
                        rec["provenance_verdict"] = (
                            _quotes.classify(quote, hay, folded)["quote_verified"])
                    # IS THE TEST STATISTIC ONE THE PAPER PRINTED, OR ONE WE
                    # COMPUTED? `statistic_value` is a printed-reading field
                    # with no instruction attached, and the model fills it with
                    # its own Wald z's -- 2.658 = 1.01/0.38 on ajcp.70049, none
                    # of them in the article. A statcheck-style tool fed such a
                    # number checks OUR arithmetic against THEIR p and reports
                    # the answer as a fact about them. Corroboration rather
                    # than a declaration, because a flag the model must set
                    # fails open the moment it forgets.
                    if "statistic_value" in rec:
                        stat = rec.get("statistic_value")
                        if isinstance(stat, (int, float)) and not isinstance(stat, bool):
                            rec["statistic_in_text"] = (
                                "present" if _quotes._number_present(str(stat), hay)
                                else "absent")
    except Exception:  # noqa: BLE001 -- never lose a paid analysis
        pass
    return result


def _script_on_disk(base, rel: str, run_slug: str | None) -> bool:
    """Is a cited `analysis_code/...` script there? THE CITATION IS THE
    ARCHIVED PATH, and annotation runs BEFORE the archive move: during a run,
    `run_python_script` writes under `analysis_code/<run_slug>/` and reports
    the flattened `analysis_code/<name>`, which only exists after
    `write_parallel_outputs` moves it. Checking the flat path alone stamped
    every script citation in every run "cited script not found" (both
    apple_cider runs, 2026-10-13: 4 of 4 and 3 of 3)."""
    import pathlib as _pl
    if (base / rel).is_file():
        return True
    if not run_slug:
        return False
    from .run_script import _slug
    tail = _pl.PurePosixPath(rel)
    if tail.parts[:1] != ("analysis_code",):
        return False
    return (base / "analysis_code" / _slug(run_slug)
            / _pl.PurePosixPath(*tail.parts[1:])).is_file()


def _annotate_reproductions(result: dict, execute: bool = True,
                            paper_dir: object = None,
                            disabled_verbs: "frozenset[str] | None" = None,
                            ledgers: "dict[str, list] | None" = None,
                            run_slug: str | None = None) -> dict:
    """Mark every reproduction command valid or not, in place.

    Adds `reproduction_valid` (bool) and, when false, `reproduction_problem`
    (str) to each finding AND to the headline, plus a `reproducibility` summary
    to run_meta. The renderer uses the flag to avoid printing a command that
    will error, which is the graceful-failure requirement: a malformed command
    is reported as "not independently reproducible", never as something to
    paste.

    WHY THE STATIC CHECK WAS NOT ENOUGH.

    `validate_reproduction` only asks whether the string LOOKS like a CLI call:
    first word `metascience`, second word a known subcommand, no placeholders.
    Every flag, every argument order and every arity is unchecked, and that is
    where the commands actually die.

    MEASURED by executing all 523 distinct `reproduction` strings in this
    repo's archive (815 with duplicates, across every report.json and
    findings.json):

        60  (11.5%)  ran and exited 0
        352 (67.3%)  passed the static check, then exited NON-ZERO
        111 (21.2%)  failed the static check

    The static gate cleared 412 of 523 (78.8%) and 60 of those 412 (14.6%)
    actually run. The other 352 were printed to readers as runnable. Top
    causes, every one of them invisible to a static check: `--expected-total`
    written for `--expected` (57), a flag the subcommand does not define (45),
    and arguments passed as flags where the CLI takes them positionally
    (`extract` 30, `check-ci` 30, `sd-range` 24).

    Running the command catches those errors. Only reviewed calculation verbs
    may execute, with output-file options refused; the CLI also has operational
    commands that must never run while validating a reproduction.

    `execute=False` skips the subprocess; command shape and execution policy
    are still checked. The pipeline normally executes permitted calculations.
    """
    from .evaluation.deterministic import _SCRIPT_RE
    from .evaluation.deterministic import (classify_reproduction,
                                           reproduction_execution_problem,
                                           validate_reproduction)

    # If the CLI is not installed, EVERY command would "fail to execute" and
    # every finding in the report would be stamped unreproducible -- an
    # accusation about the environment dressed up as one about the findings.
    # Decline to execute instead, and say so in the summary.
    cli = shutil.which("metascience") if execute else None
    executing = bool(execute and cli)

    # THREE CAUSES WORE ONE LABEL, and it was the worst of the three.
    #
    # Greg opened a bundle reading "n valid 1, n invalid 34" under the heading
    # "Reproducibility of findings" and read it as near-total failure. Measured
    # over every archived run (633 distinct commands): 127 are the model
    # correctly reporting that no command reproduces a judgement, 205 are a
    # real command written in a shape the CLI does not accept, and 28 never
    # ran at all. Only the last two are defects, and NEITHER is a defect in
    # the finding -- one of the 9 chi-square cases was re-run by hand in the
    # correct argument shape and returned the reported 180.74 exactly.
    #
    # `n_no_command_applies` is deliberately NOT folded into `n_invalid`. A
    # finding that is a reading of the paper has nothing to reproduce, and
    # counting it as an unreproducible finding is a false statement about the
    # review's own work.
    # THREE COUNTS BECAUSE THERE ARE THREE POPULATIONS, and there used to be
    # one wearing the wrong name. `n_findings` was incremented once per walked
    # object, and the headline is walked -- correctly, it carries the single
    # most prominent command in the report -- so `run_meta.json` said
    # `reproducibility.n_findings: 25` in a run holding 24 findings, and
    # `bundle.py` printed "13 of 25 reproduction commands do not run" over a
    # denominator that was not the number of findings. Worse, it was not
    # comparable to itself: the older build did not walk the headline and its
    # `n_findings` excluded it, with nothing in either file marking the change.
    #
    #   n_findings  findings only -- what the name has always claimed
    #   n_headline  0 or 1
    #   n_targets   everything that carries a `reproduction` string, which is
    #               the denominator `n_valid + n_invalid + n_no_command_applies`
    #               actually partitions
    summary = {"n_findings": 0, "n_headline": 0, "n_targets": 0,
               "n_valid": 0, "n_invalid": 0,
               "n_no_command_applies": 0, "n_command_expected": 0,
               "n_unparseable": 0,
               "executed": executing, "n_ran_ok": 0, "n_ran_failed": 0,
               "problems": []}
    if execute and not cli:
        summary["not_executed_reason"] = (
            "`metascience` is not on PATH, so commands were checked statically only"
        )

    for label, entry in _repro_entries(result):
        summary["n_targets"] += 1
        if label == "headline":
            summary["n_headline"] += 1
        else:
            summary["n_findings"] += 1
        command = entry.get("reproduction") or ""

        # AN EMPTY COMMAND ON A TECHNIQUE THAT CANNOT HAVE ONE IS NOT A
        # FAILED REPRODUCTION. The model has two honest ways to say a finding
        # is a reading: write the disclaimer, or leave the field off. Those got
        # OPPOSITE verdicts -- the disclaimer routed to the third state, the
        # omission was validated as a command and came back "empty
        # reproduction command", i.e. `reproduction_valid: false`.
        #
        # MEASURED 2026-09-01 over the five-paper flagged batch: 18 of 150
        # findings, EVERY one `computed_by: model_reading` and every one a
        # technique that is non-computational by definition --
        # `internal_contradiction` (9), `not_computational` (8, the name says
        # it), `factual_claim` (1).
        #
        # DECIDED BY THE SPEC, NOT BY A SECOND LIST HERE. `prompts
        # .NON_TOOL_TECHNIQUES` is the one place membership is stated;
        # `computation.py` already defers to it with "THE MEMBERSHIP IS NOT
        # DECIDED HERE", and this does the same.
        #
        # NARROW ON PURPOSE. A COMPUTATIONAL finding with no command is still a
        # real gap and still fails: a `grim_sweep` that cannot say how it was
        # computed is exactly what this check exists to catch.
        if not command.strip():
            from .core.prompts import NON_TOOL_TECHNIQUES as _NON_TOOL
            if str(entry.get("technique") or "") in _NON_TOOL:
                summary["n_no_command_applies"] += 1
                entry["reproduction_valid"] = None
                entry["reproduction_kind"] = "no_command_applies"
                entry.pop("reproduction_problem", None)
                continue

        if classify_reproduction(command) == "no_command_applies":
            # Not valid, not invalid: a third state. `reproduction_valid` is
            # left None so the viewer can tell "no command applies" apart from
            # "a command that does not work", which is the whole point.
            summary["n_no_command_applies"] += 1
            entry["reproduction_valid"] = None
            entry["reproduction_kind"] = "no_command_applies"
            entry.pop("reproduction_problem", None)
            continue

        if classify_reproduction(command) == "script":
            # A SCRIPT CITATION IS EVIDENCE, NOT A BROKEN COMMAND.
            # `modules/scientific_proofreading_agent/prompt.md` tells the model to name the persisted
            # script for any finding computed by `run_python_script`, and this
            # annotator then demanded `metascience` and stamped the prompt's
            # own prescribed answer `reproduction_valid: false`.
            #
            # VERIFIED BY EXISTENCE, and it FAILS CLOSED. Without a directory
            # to resolve against we record None -- unverified -- rather than
            # True: "we did not check" and "we checked and it is there" are
            # different facts, and the second is the one a reader acts on.
            import pathlib as _pl
            summary["n_script"] = summary.get("n_script", 0) + 1
            entry["reproduction_kind"] = "script"
            _m = _SCRIPT_RE.search(command)
            _rel = _m.group(1) if _m else ""
            _base = None
            if paper_dir:
                _base = _pl.Path(str(paper_dir))
                if _base.is_file():
                    _base = _base.parent
            if _base is None:
                entry["reproduction_valid"] = None
                entry["reproduction_problem"] = (
                    "script citation not verified: no paper directory given")
            elif _rel and _script_on_disk(_base, _rel, run_slug):
                entry["reproduction_valid"] = True
                summary["n_valid"] += 1
                entry.pop("reproduction_problem", None)
            else:
                entry["reproduction_valid"] = False
                summary["n_invalid"] += 1
                _problem = f"cited script not found: {_rel or command[:60]}"
                entry["reproduction_problem"] = _problem
                summary["problems"].append(f"finding[{label}]: {_problem}")
            continue

        summary["n_command_expected"] += 1
        entry["reproduction_kind"] = "command"

        # CODE BUILDS THE COMMAND WHEREVER IT CAN, and the model's string is
        # kept only where it cannot. Same rule as `parse_cells_as_declared`: the
        # model may name the check, it may not write the invocation. It was
        # guessing at signatures it had never been shown -- `metascience extract
        # --pdf-path X` for a verb that takes a bare path.
        #
        # MEASURED 2026-08-13: 461 of 801 archived model-written commands
        # (57.6%) fail validation. Regenerating from the registry and the call's
        # own inputs, then EXECUTING 60 of them: 51 ran clean, 9 failed only
        # because an archived absolute path no longer resolves, and ZERO were
        # malformed. Where no single line can carry the inputs -- `cells`,
        # `rows`, a tool with no CLI verb -- it refuses and says so, which is
        # 54.2% of calls and is the honest answer rather than a guess.
        _inputs = entry.get("inputs")
        # THE GENERATOR WAS DEAD ON THE LIVE PATH, and this is the field that
        # killed it. It keyed on `inputs["tool"]`, a v1 shape; a v2 finding
        # carries its inputs bare and names the check in `technique`. MEASURED
        # 2026-09-01 over the five-paper flagged batch: `reproduction_source`
        # was None on 150 of 150 findings and 0 of the 95 dict-valued `inputs`
        # carried a `tool` key -- so every command shipped was model-written,
        # which is exactly what this block exists to prevent, and the
        # positional-vs-option guesses below it are the visible consequence.
        #
        # VERIFIED BY EXECUTION, not by shape: driving the same generator from
        # `technique` over those runs yields 24 commands, 71 honest refusals
        # (it says why, and a refusal keeps the model's string), 0 exceptions
        # -- and all 24 RUN CLEAN. A technique that names no registry tool
        # refuses like any other, so this cannot invent an invocation.
        _tool = _args = _call = None
        # THE CALL ITSELF FIRST (Phase 3b). When the producer's ledger holds
        # exactly one argument set behind this finding, replay what the tool
        # RECEIVED rather than the model's restatement of it in `inputs`.
        if ledgers and label != "headline":
            from .findings_v2 import backing_call
            _call = backing_call(entry, ledgers.get(entry.get("producer")))
        if _call is not None and isinstance(_call.get("input"), dict):
            _tool, _args = _call.get("tool_short"), dict(_call["input"])
            _source = "generated_from_tool_call"
        elif isinstance(_inputs, dict):
            _tool = _inputs.get("tool") or entry.get("technique")
            _args = {k: v for k, v in _inputs.items() if k != "tool"}
            _source = "generated_from_registry"
        if _tool:
            try:
                from .registry import reproduction_command as _build
                _generated, _why = _build(str(_tool), _args or {})
            except Exception:  # noqa: BLE001
                _generated = _why = None
            if _generated:
                entry["reproduction"] = command = _generated
                entry["reproduction_source"] = _source
                if _source == "generated_from_tool_call":
                    entry["reproduction_call"] = _call.get("seq")
            elif _why:
                entry["reproduction_source"] = "model_written"
                entry["reproduction_not_generatable"] = _why

        check = validate_reproduction(command)
        static_ok = check["valid"]
        execution_problem = reproduction_execution_problem(command) if static_ok else None
        if execution_problem:
            check = {"valid": False, "problems": [execution_problem]}
        # A PIPELINE TOOLSET SCOPES THIS HARNESS PATH TOO. A tools-agent row
        # whose command runs a check the pipeline disabled is not executed:
        # running it would perform, after the fact, the very computation the
        # experiment excluded. The static verdict stands and the skip is named.
        # Other producers keep their own role surfaces.
        _parts = command.split()
        # The verb, or for the generic command the TOOL it runs.
        _verb = (_parts[3] if len(_parts) > 3 and _parts[1:3] == ["tool", "run"]
                 else _parts[1] if len(_parts) > 1 else "")
        if (disabled_verbs and entry.get("producer") == "tool_expert"
                and _parts[:1] == ["metascience"] and _verb in disabled_verbs):
            entry["reproduction_not_executed"] = "tool not enabled in this pipeline"
            summary["n_not_executed_disabled"] = (
                summary.get("n_not_executed_disabled", 0) + 1)
        elif check["valid"] and executing:
            # AGREEMENT IS CHECKED ON FINDINGS, NEVER ON THE HEADLINE, and the
            # first suite run after the change is what showed why. A finding
            # cites the specific check that produced it, so its severity and
            # its command answer the same question. A HEADLINE is a synthesis
            # over several findings, and its vocabulary is not even the same --
            # the schema gives it `none` where the ladder says `consistent`.
            # Comparing a synthesis against one tool's output is a category
            # error, and it flagged our own headline as disagreeing with its
            # own command. A false accusation aimed at ourselves is still one.
            run = _run_repro_cached(
                command,
                claimed_severity=(None if label == "headline"
                                  else entry.get("severity")),
                claimed_outcome=(None if label == "headline"
                                 else entry.get("outcome")))
            if run.get("ran"):
                # EXECUTED AND AGREED ARE NOW DIFFERENT FACTS. `n_ran_ok`
                # keeps counting executability, because the panel that reads it
                # is about whether our commands run at all. Agreement is what
                # decides `reproduction_valid`: a command that ran perfectly
                # and reported a different severity from the finding it is
                # attached to is a FAILURE of that finding's evidence, and
                # used to be scored as a pass.
                if run.get("executed", run.get("ok")):
                    summary["n_ran_ok"] += 1
                else:
                    summary["n_ran_failed"] += 1
                if run.get("agrees") is False:
                    summary["n_disagreed"] = summary.get("n_disagreed", 0) + 1
                if not run.get("valid", True):
                    check = {"valid": False, "problems": run["problems"]}
            # `ran` false with `valid` true means the subprocess itself could
            # not start or timed out. That is our failure, not the finding's,
            # so the static verdict stands.
        entry["reproduction_valid"] = check["valid"]
        if check["valid"]:
            summary["n_valid"] += 1
            entry.pop("reproduction_problem", None)
        else:
            summary["n_invalid"] += 1
            # WHY THE EXECUTED COUNTS NEVER ADDED UP. `n_ran_ok + n_ran_failed`
            # was 31 against 35 findings and the page never said where the
            # other four went: they failed the STATIC check and were therefore
            # never executed. Counted by name now.
            if not static_ok:
                summary["n_unparseable"] += 1
            problem = "; ".join(check["problems"])
            entry["reproduction_problem"] = problem
            summary["problems"].append(f"finding[{label}]: {problem}")

    # GATED ON `n_targets`, NOT `n_findings`. A report whose only reproduction
    # string is on the headline has real work to record, and gating on the
    # findings count would drop it silently.
    if summary["n_targets"]:
        meta = result.setdefault("run_meta", {})
        if isinstance(meta, dict):
            meta["reproducibility"] = summary
    return summary


# ---------------------------------------------------------------------------
# The deterministic image track: client side of the child subprocess
# ---------------------------------------------------------------------------


#: The text track is pure Python; its slow path is the pdfplumber extraction
#: fallback (tens of seconds on a long PDF), so 180s is ~3x headroom.
_TEXT_TRACK_TIMEOUT_DEFAULT = 180.0


def _text_track_command(paper_dir: Path) -> list[str]:
    """The text-track child invocation. `METASCIENCE_TEXT_PYTHON` is the
    symmetry hook with the image track; the text track has no extra
    dependencies (pdfplumber is core), so it normally stays unset."""
    py = os.environ.get("METASCIENCE_TEXT_PYTHON") or sys.executable
    return [py, "-m", "forensic_metascience_ai_toolkit.text_track", str(paper_dir), "--json"]


from forensic_metascience_ai_toolkit.track_contracts import _validate_track_output as _validate_track_output


def _validate_text_track_output(obj) -> tuple[dict, list[dict]]:
    return _validate_track_output(obj, technique="tortured_phrases",
                                  label="text_track")


async def _run_forensic_track(cmd, timeout_s, validate, label, unexamined,
                              verbose=False, on_progress=None):
    from forensic_metascience_ai_toolkit.runtime import _run_forensic_track as run
    return await run(cmd, timeout_s, validate, label, unexamined, verbose, on_progress,
                     build_env=_build_track_env, kill=_kill_subprocess_group)


from forensic_metascience_ai_toolkit.track_contracts import _track_timeout as _track_timeout


async def _run_text_track(paper_dir: Path, timeout_s: float | None = None,
                          verbose: bool = False, on_progress=None) -> dict:
    """The text-track (tortured-phrases) client: `_run_forensic_track` with
    the text constants. See that function and `text_track.py`."""
    if timeout_s is None:
        timeout_s = _track_timeout("METASCIENCE_TEXT_TIMEOUT",
                                   _TEXT_TRACK_TIMEOUT_DEFAULT)
    return await _run_forensic_track(
        _text_track_command(paper_dir), timeout_s,
        _validate_text_track_output, label="text track",
        unexamined="The paper's prose is UNSCREENED", verbose=verbose,
        on_progress=on_progress)


# ---------------------------------------------------------------------------
# Image track and image-finding adjudication: the image analysis package's
# ---------------------------------------------------------------------------

#: Names this module used to re-export from the image package (the image-track
#: client and the image-finding adjudication), now reached through the plugin
#: door, so `agent.X` still works where the package is installed and raises
#: `ImagePluginUnavailable` by name where it is not.
_IMAGE_REEXPORTS = {
    "_IMAGE_TRACK_TIMEOUT_DEFAULT": ("image_forensics.pipeline", "_IMAGE_TRACK_TIMEOUT_DEFAULT"),
    "_image_track_command": ("image_forensics.pipeline", "image_track_command"),
    "_run_image_track": ("image_forensics.pipeline", "run_detection"),
    "_validate_image_track_output": ("image_forensics.pipeline", "validate_image_track_output"),
    **{name: ("legacy_adjudication", name) for name in (
        "_ADJUDICATION_CLEARS", "_ADJUDICATION_TEXT_CATEGORIES",
        "_ADJUDICATION_KIND_CONTRADICTIONS", "_METHODS_NOT_LOCATED", "_fig_key",
        "_context_haystack", "_text_basis_rules", "_figure_prints",
        "_clone_overlay_path", "_image_adjudication_prompt",
        "_check_image_geometry_claims", "_apply_image_adjudication",
        "_run_image_adjudication", "adjudicate_retained_findings",
        "_readjudicate_image_rows")},
}


def __getattr__(name):
    if name in _IMAGE_REEXPORTS:
        from .image_plugin import load
        module, attr = _IMAGE_REEXPORTS[name]
        return getattr(load(module), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def completed_review(
    paper_dir: str | Path, subdir_name: str = "forensic_review",
    pipeline=None, backend: str | None = None, model: str | None = None,
) -> Path | None:
    """The finished review inside `paper_dir`, or None if there is not one.

    ONE definition of "already analysed", because there used to be two and they
    disagreed about money. Both entry points now stamp the model and pipeline
    version into the directory name (`forensic_review_<model>_v<release>`,
    `cli._versioned_review_dirname`), but ANY era's finished review counts:
    the skip exists to protect spend ("nothing is paid for twice"), not to
    scope experiments -- a version-comparison rerun says `--redo`. The first
    regression here was exactly this shape: `batch --skip-existing` tested
    only its own bare `forensic_review` name, every `analyze`-stamped run was
    invisible to it, and ten completed papers reported "skipped: 0" -- a
    silent double-charge; narrowing the glob to the CURRENT experiment's name
    would have recreated it the day the version bumped.

    A directory alone does NOT count -- it must hold a `report.md`. The two old
    call sites disagreed here too (one tested the directory, one the file), which
    made a crashed run that left an empty directory "done" to one and "pending"
    to the other. The file is the honest test: it is written last.

    Returns the most recently modified match so a re-analysed paper reports its
    newest review rather than an arbitrary one.

    PIPELINES. A partial pipeline's run (one tool, no adjudicator, ...) is not
    a review of the paper, so by default it does not count: a full batch must
    not skip a paper because a GRIM-only experiment once touched it. With
    `pipeline` (a `PipelineConfig`), only runs of that same resolved
    configuration count -- the skip still protects spend, now per experiment.
    Runs that predate pipelines are complete reviews.

    BACKEND AND MODEL. With `backend` and/or `model`, a finished run counts
    only if it was made by that backend and model, for complete reviews and
    partial pipelines alike (Dan, 2026-10-18): a different model is a different
    experiment, not a rerun, so it must not need `--redo`. Found when a Grok
    `tools_only` batch would have skipped every paper a Sonnet `tools_only`
    batch had just finished. The model matches the alias the run recorded
    (`run_meta.model`, e.g. "sonnet") or any model that actually answered
    (`models_resolved`). A run that records neither backend nor model predates
    the record and still counts, as before -- old corpora are not re-paid.
    Callers that pass neither get the old behaviour.
    """
    paper_dir = Path(paper_dir)
    if not paper_dir.is_dir():
        return None
    candidates: dict = {}
    for pattern in {f"{subdir_name}*", "forensic_review*"}:
        for d in paper_dir.glob(pattern):
            candidates[d.name] = d
    found = [
        d for d in candidates.values()
        # `forensic_review_*_bundle/` is the viewer, not a review; it carries a
        # copy of the analysis but is not what "analysed" means.
        if d.is_dir() and not d.name.endswith("_bundle")
        and (d / "report.md").is_file()
        and _counts_as_done(d, pipeline)
        and _same_engine(d, backend, model)
    ]
    if not found:
        return None
    return max(found, key=lambda d: (d / "report.md").stat().st_mtime)


def _same_engine(review_dir: Path, backend: str | None, model: str | None) -> bool:
    """Was this run made by `backend` and `model`? (None: not asked.)

    Reads `run_meta.json`. A field the run did not record is not a mismatch:
    an unreadable run_meta, or one with neither `llm_backend` nor `model`, is a
    pre-record run and counts -- see `completed_review`."""
    if backend is None and model is None:
        return True
    try:
        meta = json.loads((review_dir / "run_meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    if not isinstance(meta, dict):
        return True
    rec_backend, rec_model = meta.get("llm_backend"), meta.get("model")
    if rec_backend is None and rec_model is None:
        return True
    if backend is not None and rec_backend is not None and str(rec_backend) != str(backend):
        return False
    if model is not None and rec_model is not None:
        want = str(model).lower()
        resolved = {str(m).lower()
                    for stage in (meta.get("stages") or {}).values()
                    if isinstance(stage, dict)
                    for m in (stage.get("models_resolved") or [])}
        if want != str(rec_model).lower() and want not in resolved:
            return False
    return True


def _counts_as_done(review_dir: Path, pipeline) -> bool:
    """Does this finished review satisfy a request for `pipeline`? An
    unreadable run_meta.json counts as a legacy (complete) review, which is
    what every pre-pipeline directory is -- the old rule, unchanged."""
    # BOTH documents carry the block, and they are read together: a missing,
    # unreadable or malformed run_meta must not promote a run that
    # findings.v2.json records as partial (or the reverse). A block counts only
    # if it states its scope; a partial claim from either side wins. Only a
    # directory where NEITHER states a scope is pre-pipeline, i.e. complete.
    blocks = []
    for name in ("run_meta.json", "findings.v2.json"):
        try:
            doc = json.loads((review_dir / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        block = doc.get("pipeline") if isinstance(doc, dict) else None
        if isinstance(block, dict) and isinstance(block.get("complete_review"), bool):
            blocks.append(block)
    partial = [b for b in blocks if b["complete_review"] is False]
    recorded = partial[0] if partial else (blocks[0] if blocks else None)
    complete = not partial
    if pipeline is None or pipeline.complete_review:
        # Any complete review protects the spend, whatever its options (image
        # track on or off, figures): the historical rule.
        return complete
    # A partial experiment counts only as ITSELF, and only if it did not fail.
    # `incomplete` (e.g. image candidates left unresolved by AI screening) is
    # done, exactly as a complete review with a partial status is: re-running
    # it would pay for the same screening again. `error` is not done.
    return (isinstance(recorded, dict)
            and recorded.get("digest") == pipeline.digest
            and recorded.get("outcome") != "error")


#: The parallel run's stage records, in the keys `parallel.analyze_paper_parallel`
#: returns them under. The value register reads all three.
_AGENT_STAGES = ("tool_agent", "science_agent", "adjudicator")


def _values_calls(result: dict, ledger: list[dict] | None = None) -> list[dict]:
    """Every tool call this run made, with its arguments and result.

    ALL of them, not only `check_table`. Measured on a real run: 41 calls, none
    of them `check_table`. A register that joins only the batch path shows a
    paper's every check as absent.

    Read from the stage messages rather than from a side channel, so a call the
    model made is a call this sees -- there is no second bookkeeping path to
    drift from the first.
    """
    def _blocks(msg):
        """Content blocks, whichever shape the message arrived in.

        A saved run holds SDK STREAM EVENTS -- `{"type": "assistant",
        "message": {"content": [...]}}` -- not plain messages. Reading
        `msg["content"]` found nothing and reported it as a run that made no
        tool calls, which is indistinguishable from a run whose calls we failed
        to parse. Both shapes are handled rather than guessed at.
        """
        if not isinstance(msg, dict):
            return []
        inner = msg.get("message")
        if isinstance(inner, dict) and isinstance(inner.get("content"), list):
            return inner["content"]
        return msg.get("content") or []

    out: list[dict] = []
    for stage in _AGENT_STAGES:
        for msg in ((result.get(stage) or {}).get("messages") or []):
            for block in _blocks(msg):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    out.append({"id": block.get("id"),
                                "name": block.get("name"),
                                "input": block.get("input") or {},
                                "cells": (block.get("input") or {}).get("cells")})
    # Pair each call with its result block, which arrives in a later message.
    by_id = {c["id"]: c for c in out if c.get("id")}
    for stage in _AGENT_STAGES:
        for msg in ((result.get(stage) or {}).get("messages") or []):
            for block in _blocks(msg):
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                call = by_id.get(block.get("tool_use_id"))
                if call is None:
                    continue
                content = block.get("content")
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            try:
                                call["result"] = json.loads(part["text"])
                            except Exception:  # noqa: BLE001
                                pass
                elif isinstance(content, dict):
                    call["result"] = content
    # THE LEDGER IS THE BETTER READING OF THE SAME MESSAGES. `_tool_call_ledger`
    # extracts every call with its `input`, its `result` and an explicit
    # `result_truncated` flag; this function grew its own parse beside it and
    # swallowed every failure in a bare `except: pass`.
    #
    # MEASURED 2026-08-20, and the gap is not marginal. Over the nine registers
    # of the eleven-paper run: `n_checks_attached` was **0 on every paper**,
    # while 27 to 53 calls per paper reported "no matchable value". Reading the
    # stream, 25 of 56 results parsed on the paper I probed; reading the ledger,
    # 1,008 of 1,111 parse across all reviews (90.7%), with only 4.6% flagged
    # truncated. The verdicts were computed, saved, and then dropped at a parse
    # nobody was told about.
    #
    # Falls back to whatever the stream gave when no ledger is available, and
    # COUNTS what it could not parse either way -- a call whose result we could
    # not read is not a call that returned nothing, and the two must not look
    # the same to `coverage()`.
    unparsed = 0
    if ledger:
        by_use = {r.get("tool_use_id"): r for r in ledger if r.get("tool_use_id")}
        for call in out:
            row = by_use.get(call.get("id"))
            if row is None:
                continue
            call.setdefault("input", row.get("input") or {})
            if call.get("cells") is None:
                call["cells"] = (row.get("input") or {}).get("cells")
            if call.get("result") is not None:
                continue
            text = row.get("result")
            if isinstance(text, dict):
                call["result"] = text
                continue
            try:
                call["result"] = json.loads(text)
            except Exception:  # noqa: BLE001
                call["result_unreadable"] = (
                    "truncated" if row.get("result_truncated") else "unparseable")
                unparsed += 1
    for call in out:
        if call.get("result") is None and "result_unreadable" not in call:
            call["result_unreadable"] = "no result block was paired to this call"

    # A CALL WITH NO PARSED RESULT IS STILL A CALL. Filtering them out made a
    # run whose results we could not parse look like a run that made no calls.
    return out


def build_value_register(result: dict, paper_path, out_dir: Path) -> dict:
    """Build this run's value register and write it beside the review.

    EXTRACTED SO THERE IS ONE OF IT. `write_review_outputs` owned this inline
    and `metascience batch` never passed it a `paper_path`, so every paper the
    batch analysed came out with no register at all -- silently, because the
    whole thing sat behind `if paper_path:`. Rebuilding a register for a review
    that already exists must run the SAME code that a live run runs, or the two
    drift and the repaired ones are not comparable with the rest.

    Returns `{name: Path}` for whatever it wrote, the same shape
    `write_review_outputs` collects.
    """
    written: dict[str, Path] = {}
    if True:
        try:
            from . import values as _values
            anatomy_obj = (result.get("findings") or {}).get("anatomy") or {}
            variables = anatomy_obj.get("variables") or []
            # A row label binds to a variable by NAME here: the anatomy names
            # its variables and the tables label their rows, and `check_table`
            # takes the same mapping.
            bindings = {str(v.get("name")): str(v.get("id"))
                        for v in variables
                        if isinstance(v, dict) and v.get("name") and v.get("id")}
            register = _values.build_from_paper(
                paper_path, variables=variables, bindings=bindings)

            # JOIN THIS RUN'S VERDICTS ONTO IT. Without them every group reads
            # `silent`, which `coverage()` declares to be a bug in the
            # bookkeeping -- and it would have been right.
            #
            # A `check_table` call does not record which table it ran on, so
            # each is matched back by its printed cell texts. NO MATCH MEANS NO
            # ATTACHMENT: a verdict placed on a guessed table is a guessed
            # accusation, and the count of unmatched calls is published instead.
            # THE LEDGER. A caller may pass `_toolcall_ledger`; otherwise it
            # is rebuilt from each agent's messages, the reading that handles
            # truncation.
            _ledger_problems: list[str] = []
            _ledger = result.get("_toolcall_ledger")
            if _ledger is None:
                _ledger = []
                for _k in _AGENT_STAGES:
                    _st = result.get(_k) or {}
                    if not _st.get("messages"):
                        continue
                    try:
                        _ledger += _tool_call_ledger(_st["messages"], [])
                    except Exception as exc:  # noqa: BLE001
                        # RECORDED, not passed. This whole commit exists because
                        # a parse failure was swallowed and every verdict went
                        # missing; discarding THIS one would hide the same thing
                        # one layer up. `lint-inert` caught it, correctly.
                        _ledger_problems.append(
                            f"{_k}: could not rebuild the tool-call ledger "
                            f"({type(exc).__name__}: {exc}), so verdicts from "
                            "that stage cannot be joined to values")
            run_calls = _values_calls(result, ledger=_ledger)
            unmatched = ct_joined = 0
            for call in run_calls:
                if not str(call.get("tool") or call.get("name")
                           or "").endswith("check_table"):
                    continue
                table = _values.table_for_cells(register, call.get("cells"))
                if table is None:
                    unmatched += 1
                    continue
                ct_joined += 1
                out = call.get("result") or {}
                _values.attach_checks(register, out.get("results"), table=table,
                                      consistent=out.get("consistent_index"))
                _values.attach_not_run(register, out.get("not_run"), table=table)
            # THE PATH THE MODEL ACTUALLY USES. Per-cell calls carry no cell
            # coordinates, so they are joined by the numbers they consumed.
            _values.attach_calls_by_value(
                register, [c for c in run_calls
                           if not str(c.get("tool") or c.get("name")
                                      or "").endswith("check_table")])
            _values.dedupe_checks(register)
            register["n_check_table_calls_unmatched"] = unmatched
            # A CALL, not the rows it carried. See `call_ledger_balance`.
            register["n_check_table_calls_joined"] = ct_joined
            # TWO READINGS OF ONE PAGE, AND WHERE THEY DISAGREE ABOUT A NUMBER.
            # `agreement.py` was written for exactly this and had ZERO importers
            # -- built, tested, and called by nothing.
            #
            # WHY IT MATTERS, measured 2026-08-20. On two of the eleven papers
            # the two readings differ only in PRECISION: `body.md` reads `35.4`
            # where docling reads `35.40`, `1.09` against `1.090`, `3.4` against
            # `3.40`. That is not corruption, and it is not harmless: GRIM's
            # granularity is a function of the decimal count, and over 3,606
            # means at six sample sizes, **13% flip their GRIM verdict between
            # one and two decimals -- every one of them from consistent to
            # INCONSISTENT**. An extractor's trailing zero is therefore a
            # false-accusation pathway against an honest paper.
            #
            # Recorded, not acted on. Which reading is right cannot be decided
            # from the text, and guessing is the thing this toolkit refuses.
            try:
                from . import agreement as _agree
                from .extraction import docling_tables as _dl2
                _base = Path(paper_path)
                _body_f = _base / "body.md"
                _pdfs = sorted(_base.glob(f"{_base.name}.pdf"))
                if _body_f.is_file() and _pdfs:
                    _dtext = (_dl2.extract_pdf_tables(
                        _pdfs[0], allow_extract=False).get("text") or "")
                    if _dtext:
                        register["reading_agreement"] = _agree.compare(
                            _body_f.read_text(encoding="utf-8", errors="replace"),
                            _dtext, label_a="body.md", label_b="docling",
                            analytic=True)
            except Exception as exc:  # noqa: BLE001
                register["reading_agreement"] = {
                    "error": f"could not compare the two readings: "
                             f"{type(exc).__name__}: {exc}"}
            # THE CONSERVATION LAW. Every call must end in exactly one state,
            # and they must sum. See `values.call_ledger_balance`.
            register["calls"] = _values.call_ledger_balance(register, run_calls)
            if _ledger_problems:
                register["ledger_problems"] = _ledger_problems
            # BINDING IS REPORTED, NOT ASSUMED. Row labels are bound to
            # variables by NAME here, and on a real paper that matched NOTHING:
            # an anatomy names its variables in prose ("Self-evaluation (own
            # attractiveness, single item)") while a table labels its rows in a
            # word. A silent zero read as "this paper has no typed variables"
            # rather than "our binding rule does not fit this anatomy".
            register["bindings"] = {
                "rule": "row label equals variable name, exactly",
                "n_variables_declared": len(variables),
                "n_row_labels_matched": register.get(
                    "n_values_bound_to_a_variable", 0) and sum(
                    1 for g in (register.get("groups") or [])
                    if g.get("variable_id")) or 0,
                "note": ("Zero matches does not mean the paper has no typed "
                         "variables. It means no table row label equalled a "
                         "declared variable name, which is the common case when "
                         "the anatomy describes a variable rather than naming "
                         "the row it sits in."),
            }
            register.pop("_table_cells", None)
            # THE ARITHMETIC NOBODY RAN. 125 checkable values in the
            # eleven-paper run were offered to the model and never checked;
            # where the column header states its own n, no model is needed.
            # BEFORE `coverage`, so what it checks counts as checked.
            register["stated_denominator_checks"] = (
                _values.check_stated_denominators(register))
            register["coverage"] = _values.coverage(register)
            # ARITHMETIC THE NUMBERS MUST SATISFY, CHECKED EVERY RUN. See
            # `values.check_invariants` -- the one rule of this kind that
            # already existed caught a real corruption, in the test suite, days
            # late, and only because the corpus happened to grow.
            register["invariants"] = _values.check_invariants(register)
            # THE RESIDUE, HANDED OVER AFTER THE ANATOMY EXISTS. Greg's
            # ordering constraint, and this is the point that satisfies it: the
            # anatomy's `variables` are in hand here, so the model classifying
            # these numbers has something to classify them AGAINST rather than
            # inferring measurement levels and bounds from the digits.
            #
            # `context` is dropped from each item because it is already carried
            # verbatim on `numerals.rows` under the same `id` -- keeping both
            # costs 21% of the artefact to say one thing twice. A consumer joins
            # on `id`.
            batch = _values.classification_batch(register, variables=variables)
            batch["items"] = [{k: v for k, v in it.items() if k != "context"}
                              for it in (batch.get("items") or [])]
            batch["context_is_on"] = ("numerals.rows, joined by `id` -- not "
                                      "duplicated here")
            register["classification"] = batch
            reg_path = out_dir / "value_register.json"
            reg_path.write_text(json.dumps(register, indent=2, default=str))
            written["value_register"] = reg_path
        except Exception as exc:  # noqa: BLE001
            (out_dir / "value_register.error.txt").write_text(
                "The value register could not be built for this run, so this "
                "review has no per-value coverage. This is OUR gap, not a fact "
                f"about the paper:\n{exc!r}\n")
            written["value_register_error"] = out_dir / "value_register.error.txt"
    return written


def _render_report_pdf(result: dict, report_md: str, out_dir: Path) -> Path | None:
    """Best-effort render of report.md to report.pdf. Never raises."""
    try:
        from .report_render import render_markdown_to_pdf

        from .report_render import resolve_run_stamp
        from .version import NOT_RECORDED, pipeline_version

        run_meta = result.get("run_meta") or {}
        paper_id = run_meta.get("paper_id") or "paper"
        verdict = result.get("verdict")
        meta_bits = [f"Paper: {paper_id}"]
        if verdict:
            meta_bits.append(f"Verdict: {verdict} ({result.get('confidence', '?')})")
        # The date and the version go in the PDF's own header band as well as in
        # the markdown. Belt and braces on purpose: this band is the only stamp a
        # degenerate report gets -- `_findings_only_result` renders a one-line
        # banner with no title block for the markdown stamp to sit under -- and
        # the markdown is the only stamp the pandoc fallback engine gets, since
        # it never sees this HTML.
        stamp = resolve_run_stamp(run_meta, out_dir)
        meta_bits.append(f"Analysed: {stamp.get('analysed_at') or NOT_RECORDED}")
        meta_bits.append(f"Pipeline: {pipeline_version(stamp)}")
        cost = result.get("total_cost_usd")
        if cost is not None:
            meta_bits.append(f"Analysis cost: ${cost:.2f}")
        path = render_markdown_to_pdf(
            report_md,
            out_dir / "report.pdf",
            title=f"Forensic Review — {paper_id}",
            meta_line="  ·  ".join(meta_bits),
        )
        if path is None:
            _record_pdf_error(result, None)
        return path
    except Exception as exc:  # noqa: BLE001 -- best-effort by contract
        _record_pdf_error(result, exc)
        return None


def _record_pdf_error(result: dict, exc: BaseException | None) -> None:
    """Say WHY there is no report.pdf, in run_meta, where a reader looks.

    `report_render.last_pdf_error()` has carried the reason since defect #163
    and nothing called it: a missing PDF was a missing file with no sentence
    beside it. Written into `result["run_meta"]` BEFORE run_meta.json is
    serialised (both writers render the PDF first), so the reason reaches
    disk and the viewer's provenance block.
    """
    from .report_render import last_pdf_error
    # THIS render's exception first. `last_pdf_error()` is module-global
    # state that only the weasyprint path sets and nothing clears, so on a
    # long batch it can describe an earlier paper's failure; the test that
    # caught this saw "no cairo" reported for a renderer that had raised
    # "no engine". The global is the fallback for a renderer that returned
    # None without raising, which is the only case it was written for.
    if exc is not None:
        reason = f"{type(exc).__name__}: {exc}"
    else:
        reason = last_pdf_error()
    meta = result.get("run_meta")
    if not isinstance(meta, dict):
        meta = result["run_meta"] = {}
    meta["pdf_error"] = reason or "renderer returned no file and recorded no reason"


_MAX_LOGGED_TOOL_RESULT = 2000


MCP_TOOL_PREFIX = f"mcp__{MCP_SERVER_NAME}__"

# Bulk tools whose results embed the paper and would bloat every ledger.
# Forensic tool results are small JSON and are recorded in full, because they
# ARE the evidence -- truncating them was how a finding's provenance got lost.
_BULK_TOOLS = {"extract_pdf", "Read", "statcheck"}

# Tools that can COMPUTE a statistic outside the validated forensic surface.
# A call to one of these can silently corrupt a finding; a call to something
# merely off-allowlist (e.g. ToolSearch) widens the surface without doing the
# arithmetic. The audit grades them differently so the severe case stays visible.
_COMPUTE_TOOLS = {"Bash", "Edit", "Write", "NotebookEdit", "Task"}

#: CODEX'S SHELL IS ALSO ITS ONLY FILE READER (`llm_backend.CODEX`:
#: `builtin_tools=("Bash",)`, decided 2026-09-01). Filing every shell call as a
#: severe breach made a Codex run's audit read "BREACH (severe)" whenever an
#: agent looked at a file: MEASURED 2026-10-11, a gpt-5.6-terra review's seven
#: shell calls were all `rg`, `sed -n 'N,Mp'` and `pdftotext` over the paper.
#: A call made ONLY of these, joined by pipes, is the Read analog. Anything
#: else -- awk, python, a redirect, `;`/`&&`, command substitution, `rg --pre`,
#: `find -exec`, `sed` with a script that is not a print -- stays a breach.
_SHELL_READ_COMMANDS = frozenset({
    "rg", "grep", "egrep", "fgrep", "cat", "head", "tail", "ls", "wc", "nl",
    "pdftotext", "pdfinfo", "file", "stat", "find", "sed",
})
_SHELL_WRAPPERS = frozenset({"bash", "sh", "zsh", "dash"})
_SED_PRINT = re.compile(r"^(\d+|\$)(,(\d+|\$))?p$|^/[^/]*/p$")
_FIND_ACTIONS = ("-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint",
                 "-fprintf", "-fls")


def _shell_reads_only(tool_input) -> bool:
    """True when a shell call only reads text (see `_SHELL_READ_COMMANDS`).

    Conservative by construction: an unparseable command, or any construct
    this cannot prove harmless, returns False and the call stays a breach.
    """
    import shlex
    cmd = (tool_input or {}).get("command") if isinstance(tool_input, dict) else None
    if isinstance(cmd, list):
        cmd = shlex.join(str(c) for c in cmd)
    if not isinstance(cmd, str) or not cmd.strip():
        return False
    try:
        outer = shlex.split(cmd)
    except ValueError:
        return False
    script = cmd
    if outer and os.path.basename(outer[0]) in _SHELL_WRAPPERS:
        if len(outer) != 3 or outer[1] not in ("-c", "-lc"):
            return False
        script = outer[2]
    if "$(" in script or "`" in script or "<(" in script:
        return False
    try:
        lexer = shlex.shlex(script, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return False
    segments: list[list[str]] = [[]]
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if tok in ("|", ";", "&&", "||"):
            segments.append([])         # each side is checked on its own
        elif tok in (">", ">>") and nxt == "/dev/null" or tok == ">&" and nxt.isdigit():
            # Discarding output (`2>/dev/null`, `2>&1`) writes nothing; the
            # file-descriptor digit before it is not a command argument.
            if segments[-1] and segments[-1][-1].isdigit():
                segments[-1].pop()
            i += 1
        elif tok and set(tok) <= set("();<>|&"):
            return False                    # > file, <, &, ( ), anything else
        else:
            segments[-1].append(tok)
        i += 1
    for seg in segments:
        if not seg or os.path.basename(seg[0]) not in _SHELL_READ_COMMANDS:
            return False
        name, args = os.path.basename(seg[0]), seg[1:]
        if name == "rg" and any(a == "--pre" or a.startswith("--pre=")
                                for a in args):
            return False
        if name == "find" and any(a.startswith(_FIND_ACTIONS) for a in args):
            return False
        if name == "sed":
            if "-n" not in args or any(a.startswith(("-i", "--in-place"))
                                       for a in args):
                return False
            scripts = [args[i + 1] for i, a in enumerate(args[:-1]) if a == "-e"]
            if not scripts:
                scripts = [next((a for a in args if not a.startswith("-")), "")]
            if not all(_SED_PRINT.match(s) for s in scripts):
                return False
    return True

# The harness's own channels. `StructuredOutput` is HOW a schema-constrained
# answer is returned -- it is required, not optional, and it computes nothing.
# Counting it as a breach made every clean run report "BREACH (surface): 3
# call(s) extended the tool surface", which is the sort of false alarm that
# teaches a reader to skip the audit entirely. The three flagged calls on the
# run that prompted this were all of them this.
_HARNESS_TOOLS = {"StructuredOutput", "search_tool"}

#: Tools whose output is the AGENT'S OWN CODE, not our arithmetic. The science
#: agent's sandboxed script runner is the only member, and it reaches the model
#: over the forensic MCP server -- which is exactly why it needs naming here:
#: the prefix test would otherwise file it as validated forensic evidence.
#: `docs/specs/pipeline.md §9` (the locked decision).
AGENT_CODE_TOOLS = {"run_python_script"}

#: Web retrieval. `validated` False for the same reason: text fetched from the
#: internet is not arithmetic this toolkit performed.
_WEB_SURFACE_TOOLS = {"WebSearch", "WebFetch", "web_search", "web_fetch"}
_MAX_LEDGER_RESULT = 4000

#: ONE NAME PER TOOL, ACROSS BACKENDS. `tool_short` is what every per-tool
#: aggregation counts -- `coverage.tools_run`, `_WEB_TOOLS` in parallel.py,
#: the figure-read detector, the exposure audit -- and it was whatever the
#: backend happened to call the tool.
#:
#: MEASURED 2026-08-22 over the 24 archived ledgers of a 10-paper grok-4.6
#: run (2,196 tool calls). Grok reported `Read` and `WebFetch` under Claude's
#: names, so those counters were fine; ONE name disagreed, and it was not a
#: name at all but a DISPLAY STRING -- `"Web search:"`, trailing colon
#: included, 7 calls. Those 7 scored `surface: "UNVALIDATED"`, the surface
#: reserved for a tool the stage never declared, so legitimate web searches
#: by the science agent were filed as a list breach. They were also invisible
#: to `_WEB_TOOLS`, which decides what the adjudicator is told the agent
#: actually visited.
#:
#: `read_file` and `web_fetch` are Grok's own builtin names (see
#: `GROK_BUILTIN_TOOLS` / `GROK_DENIED_TOOLS`) -- absent from this run's
#: stream but emittable, so they are mapped rather than waited for.
#:
#: DENIED TOOLS ARE NOT ALIASED. Mapping `run_terminal_cmd` onto `Bash` would
#: fold a backend-specific breach into a name some caller might recognise;
#: an unvalidated shell call must stay conspicuous under whatever name it
#: arrived with.
#:
#: `tool` keeps the RAW name: that is the record of what the model asked for,
#: and normalising it would erase evidence. Only `tool_short` is canonical.
_TOOL_ALIASES = {
    "read_file": "Read",
    "web_fetch": "WebFetch",
    "web search": "WebSearch",
    "web_search": "WebSearch",
    "websearch": "WebSearch",
}


def _canonical_tool(short: str) -> str:
    """Backend-neutral name for one tool. Unknown names pass through."""
    cleaned = (short or "").strip().rstrip(":").strip()
    return _TOOL_ALIASES.get(cleaned.lower(), cleaned or short)


def _checked_cell_key(prefix: str, cells: list, call_id) -> tuple:
    """Identify the CELL a `check_table` result row adjudicated.

    `dispatch.check_table` stamps `check_id = f"r{i}.{tool}"`, where `i` is the
    index into the `cells` list of THAT CALL. The prefix is therefore a
    position, not an identity, and two calls both have an `r0`.

    Resolving the position back through the call's own arguments gives the
    printed value and its row and column headers, which is what "the same cell"
    means to a reader. Verified against the archive: for all 199 result rows
    that carry a `cell.row_label` of their own, `cells[i]["row_label"]` is the
    same string -- 199 of 199, no disagreements -- so the index really does
    address the argument list.

    Falls back to `(call, id, prefix)` when the arguments are unavailable or
    the cell is blank in all three fields. The fallback is per-call unique, so
    a missing argument list costs the deduplication and never the row: it can
    over-count a re-submitted cell but it cannot delete one. It is a different
    arity from the identity key so the two can never be confused, and it did
    not fire once on the 657 archived result rows.
    """
    if prefix.startswith("r") and prefix[1:].isdigit():
        i = int(prefix[1:])
        if 0 <= i < len(cells) and isinstance(cells[i], dict):
            key = ("cell",
                   str(cells[i].get("row_label") or ""),
                   str(cells[i].get("col_label") or ""),
                   str(cells[i].get("raw") or ""))
            if any(key[1:]):
                return key
    return ("call", str(call_id), prefix)


def _text_provenance(paper_path) -> dict:
    """Which reader produced the text for each PDF in this paper directory.

    `docling` means operators and signs survived; `pdfplumber` means the
    higher-fidelity read was never run for that file, and a reader should treat
    a quiet result with more suspicion. Reported per file, because a paper can
    easily have a docling-read article and a pdfplumber-read supplement.
    """
    from .extraction import docling_tables as _dl

    base = Path(paper_path)
    base = base if base.is_dir() else base.parent
    out: dict = {"by_file": {}, "docling_version": _dl._current_version()}
    n_doc = n_plumb = 0
    for pdf in sorted(base.glob("*.pdf")):
        text, why = _dl.cached_text(pdf)
        if text:
            out["by_file"][pdf.name] = {"extractor": "docling",
                                        "n_chars": len(text)}
            n_doc += 1
        else:
            out["by_file"][pdf.name] = {"extractor": "pdfplumber", "why": why}
            n_plumb += 1
    out["n_docling"], out["n_pdfplumber"] = n_doc, n_plumb
    out["all_high_fidelity"] = n_plumb == 0 and n_doc > 0
    out["note"] = (
        f"{n_doc} file(s) read by docling, {n_plumb} by pdfplumber."
        + ("" if n_plumb == 0 else
           " A pdfplumber read loses the characters that carry meaning -- "
           "comparators and MINUS SIGNS arrive stripped -- so an absent "
           "finding in those files may be an absent character rather than a "
           "clean result. Re-run `metascience extract-tables` to upgrade."))
    return out


def _number_haystack(paper_path, manifest: dict | None) -> tuple[str | None, str | None]:
    """Everything a reported figure could honestly have been copied FROM,
    and -- separately -- what we failed to read.

    Two sources, and both are needed. `paper_text` returns the prose and the
    article's own tables, which is where a figure quoted in a sentence lives.
    The manifest's rows are the only enumeration that has already walked the
    SUPPLEMENTS -- 90.4% of the checkable items in supplement-carrying papers
    are in those files -- so a number transcribed from Table S3 is findable
    only through them, and only for free because the manifest was built above.

    THE SECOND RETURN VALUE EXISTS BECAUSE A PARTIAL HAYSTACK LIES. If the
    prose cannot be read and only the table cells arrive, a figure quoted in a
    sentence is not found, and the audit reports it as arithmetic the agent
    invented -- our extraction failure recorded as a property of the finding,
    which is the house failure mode by name. The first cut of this function
    swallowed that exception silently and `lint-inert` caught it.

    Returns `(None, why)` rather than `("", ...)` when neither source yields
    anything: an empty haystack would make every figure look invented.
    """
    parts: list[str] = []
    problems: list[str] = []
    try:
        txt = paper_text(Path(paper_path) if Path(paper_path).is_dir()
                         else Path(paper_path).parent)
        if txt:
            parts.append(txt)
        else:
            problems.append("the paper's own text came back empty")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"the paper's text could not be read "
                        f"({type(exc).__name__}: {exc})")
    n_cells = 0
    for item in ((manifest or {}).get("items") or []):
        raw = isinstance(item, dict) and (item.get("raw") or "")
        if raw:
            parts.append(str(raw))
            n_cells += 1
    if not parts:
        return None, "; ".join(problems) or "no readable source for this paper"
    if problems:
        return "\n".join(parts), (
            "; ".join(problems) + f" -- only the {n_cells} enumerated table "
            "cell(s) were available to check figures against, so a figure "
            "quoted from the PROSE cannot be found here and will be reported "
            "as the agent's own. That is OUR gap.")
    return "\n".join(parts), None


def _tool_events(messages: list[dict] | None = None,
                 ledger: list[dict] | None = None) -> list[dict]:
    """Every tool call as `{short, name, input, id, result}`, from either source.

    The census's three counters were written against raw stage `messages`, and
    reading them there has two costs the LEDGER does not have.

    * A LEDGER CAN BE RE-READ FROM AN ARCHIVE; messages cannot. `_slim_messages`
      empties large `tool_result` payloads before they are persisted -- MEASURED
      2026-09-03 on `benchmarks/paper_reviews/runs/wound_healing`: the three archived `check_table`
      results are **0 chars** in `messages.tool_agent.json` and 25,519 / 21,809
      / 9,774 chars, untruncated, in `toolcalls.tool_agent.json`. So a census
      computed from an archived run silently reports nothing checked. That is
      how this function's own numbers were nearly misdiagnosed as broken.
    * The ledger carries the CANONICAL short name (`_canonical_tool`), which the
      old `name.split("__")[-1]` does not: a backend that reports a display
      string rather than a tool name was filed as a breach for exactly this
      reason (see `TestLedgerToolNamesAreBackendNeutral`).

    Both are accepted, and when both are given the ledger supplies identity
    while the MESSAGE supplies the result whenever the ledger's copy was
    truncated (`_BULK_TOOLS`, capped at `_MAX_LEDGER_RESULT`). Measured on the
    archive, only `Read` and `extract_pdf` ever truncate and neither feeds a
    counter here -- but `statcheck` is a bulk tool and does feed one, so the
    preference is structural rather than a bet on the corpus staying this way.
    """
    from_messages: dict[str, str] = {}
    for event in (messages or []):
        if event.get("type") != "user":
            continue
        for block in (event.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                inner = block.get("content")
                from_messages[block.get("tool_use_id")] = (
                    "".join(p.get("text", "") for p in inner if isinstance(p, dict))
                    if isinstance(inner, list)
                    else (inner if isinstance(inner, str) else ""))

    if ledger:
        out = []
        for row in ledger:
            cid = row.get("tool_use_id")
            res = row.get("result") or ""
            if row.get("result_truncated") and from_messages.get(cid):
                res = from_messages[cid]
            out.append({"short": str(row.get("tool_short") or ""),
                        "name": str(row.get("tool") or ""),
                        "input": row.get("input") if isinstance(row.get("input"), dict) else {},
                        "id": cid, "result": res})
        return out

    out = []
    for event in (messages or []):
        if event.get("type") != "assistant":
            continue
        for block in (event.get("message") or {}).get("content") or []:
            if not (isinstance(block, dict) and block.get("type") == "tool_use"):
                continue
            name = str(block.get("name", ""))
            out.append({"short": name.split("__")[-1], "name": name,
                        "input": block.get("input") if isinstance(block.get("input"), dict) else {},
                        "id": block.get("id"),
                        "result": from_messages.get(block.get("id"), "")})
    return out


def _checkable_coverage(paper_dir, messages: list[dict] | None = None,
                        ledger: list[dict] | None = None) -> dict | None:
    """How many cells COULD have been checked, beside how many were.

    `coverage_summary` has only ever counted effort: `stats_checked` is the
    model's own tally of what it noticed, and `tables_checked` lists the tables
    a call was made against whether or not one cell inside them ran. On
    10.3390--jpm11060545 that printed three table names while 0 of 79 consumable
    cells received a cell-level check. A denominator of effort cannot tell a
    thorough run from a lazy one, and cannot show a regression.

    The census reads the paper's own tables and needs no model. Returns None
    when there are no XML tables to survey -- silence, rather than a zero that
    would read as "nothing was checkable".
    """
    from . import census as _census

    try:
        # ONE WALK OF THE TABLES, SHARED WITH `prepass`. The paging and the
        # `*.xml` selection used to live here and were about to be copied into
        # the exhaustive sweeps -- two walks would be two denominators, and this
        # file has already published one coverage figure computed against a
        # different denominator from the one printed beside it.
        from . import prepass as _prepass
        # SUPPLEMENTS COUNT TOWARDS THE DENOMINATOR, because they are part of
        # the paper's claims. Excluding them did not make coverage good, it made
        # it unmeasured: MEASURED 2026-08-13, 90.4% of the checkable items in
        # supplement-carrying papers live in the supplement, and the archive
        # contains TWELVE `extract_supplement` calls in total -- none on the two
        # papers holding 13,064 of those items.
        #
        # This makes the reported coverage figure FALL, and that is the point.
        # The old number was computed against the smaller half of the paper and
        # was flattering by construction. `run_exhaustive` walks with the same
        # flag, so the two denominators still cannot diverge.
        tables = _prepass.paper_tables(paper_dir, include_supplements=True)
        if not tables:
            return None
        entries: list[dict] = []
        for tab in tables:
            entries += _census.cell_census(tab["cells"], table=tab["label"])
        if not entries:
            return None

        # Distinct cells that reached a check THROUGH check_table. Named for
        # exactly what it counts: per-cell direct calls are invisible here, so
        # this understates coverage rather than flattering it.
        #
        # KEYED BY THE CELL, NOT BY ITS POSITION IN ONE CALL. `check_id` is
        # `r{i}.{tool}` where `i` indexes THAT CALL's `cells` list (see
        # `dispatch.check_table`), so `r0` names a different cell in every call
        # and a set of bare prefixes silently collapses them. MEASURED over the
        # archive, 2026-08-12: 8 runs made a `check_table` call that produced
        # results, and across them the prefix set held 116 keys against 195
        # (cell, call) adjudications -- 79 dispositions, 40%, absorbed by the
        # collision, all of it in 2 runs (51 -> 12 and 48 -> 8). That number
        # then divides `n_consumable` and prints as this paper's coverage, so
        # our keying bug was published as a fact about the paper.
        #
        # WHY NOT SIMPLY KEY BY THE CALL. `(call_id, "r{i}")` is unique, but it
        # changes what is counted: a run that re-submits the same table -- the
        # s11031 sweep re-ran three of its tables against a second candidate
        # `n` -- would count each of those cells once per submission, giving
        # 195 where the truth is 175 distinct cells, coverage inflated by 11%.
        # Over-claiming coverage is the direction that supports a false
        # all-clear, so the key is the cell's own identity: the value, in the
        # row and column it was printed in. One cell checked twice is one cell.
        #
        # AND THE REMAINING COLLAPSE RISK IS THE SAFE ONE. Two cells in
        # different tables printing the same value under identically-named row
        # and column headers still merge, which undercounts. `source_locator`
        # was the obvious discriminator and was measured and rejected: it is
        # absent on 20 of the archive's 61 `check_table` calls, so including it
        # would split one cell between a call that named its table and a call
        # that did not -- and on every run where it IS present it changes no
        # count at all (51/51, 28/28, 16/16, 8/8, 11/11, 15/15, 25/25, 21/21).
        checked: set[tuple] = set()
        events = _tool_events(messages, ledger)
        for ev in events:
            if not ev["short"].endswith("check_table"):
                continue
            try:
                payload = json.loads(ev["result"] or "{}")
            except (ValueError, TypeError):
                continue
            cells = ev["input"].get("cells")
            if not isinstance(cells, list):
                cells = []
            for rec in (payload.get("results") or []) + (
                    payload.get("consistent_index") or []):
                cid = str(rec.get("check_id") or "")
                if "." in cid:
                    checked.add(_checked_cell_key(
                        cid.split(".", 1)[0], cells, ev["id"]))

        # SUMMARISE ONCE, WITH `n_checked`. This used to call `summarise` twice:
        # the result WITHOUT `n_checked` was the one published, and the complete
        # one was computed on the next line and thrown away except for its
        # rendered prose. So `n_checked`, `coverage` and `never_submitted` never
        # reached the payload, and `_render_checkable_detail`'s branch for
        # `never_submitted` -- "N could have run as they stand and were never
        # submitted to a check" -- has never printed on a real run.
        #
        # That is the number this whole census exists to produce. It measures
        # available work the model skipped, as distinct from work it attempted
        # and the dispatcher refused, and it is the evidence for whether tool
        # use needs to be made programmatic rather than left to the model.
        # THE OTHER TOOLS THAT CONSUME TABLE CELLS, counted separately because
        # they cannot be counted together honestly.
        #
        # MEASURED on 10.1002--eat.24415, 2026-08-11, and this is the defect
        # Greg read off the page: `check_table` reached 21 cells and
        # `check_regression_batch` reached 68 MORE -- the whole of Table 2's
        # coefficient block, which the census files as `mean_se` and writes off
        # as "blocked on n". The report then printed "21 of 110 checkable cells
        # were checked. The verdict above does not cover the other 89", 480
        # lines above its own sentence "All 68 coefficient rows in Table 2 ...
        # reproduce -- 68 of 68".
        #
        # WHY THESE ARE NOT SUMMED. A batch tool reports how many ROWS it
        # checked; it does not return census cell ids, so `21 + 68` would be an
        # invented union that could double-count any cell both tools touched.
        # Reporting the two populations side by side, each named for what it
        # counts, is the honest version -- and the rendered sentence below no
        # longer claims the remainder went unchecked, because we now know it
        # did not.
        batch_rows, batch_tools, batch_ids = 0, {}, set()
        for ev in events:
            name = ev["short"]
            if name == "check_table" or not (
                    name.endswith("_batch") or name in ("statcheck",)):
                continue
            try:
                payload = json.loads(ev["result"] or "{}")
            except (ValueError, TypeError):
                continue
            n = payload.get("n_rows") or payload.get("n_tests") or 0
            if isinstance(n, int) and n > 0:
                batch_rows += n
                batch_tools[name] = batch_tools.get(name, 0) + n
                    # PER CALL, not per tool. A batch call that reported no row
                    # count is not represented here at all, and the per-cell
                    # counter below has to be free to pick it up -- otherwise a
                    # run whose only checks were batch calls with unreadable
                    # results falls into neither population and gets the denial.
                batch_ids.add(ev["id"])

        # THE THIRD POPULATION: PER-CELL CALLS, which neither counter above can
        # see. `checked` counts only tools whose name ends `check_table`;
        # `batch_rows` only `*_batch` and `statcheck`. Every other way a number
        # off this paper reaches a check -- `check_summation`,
        # `check_estimate_ci`, `grimmer_check`, `grim_percentage`, `grim_sweep`,
        # `stalt_check`, `flag_round_n`, `detect_duplication` and the rest --
        # was invisible to both, and the report then printed, in bold,
        # "**NOTHING IN THE TABLES WAS CHECKED.**"
        #
        # MEASURED over the archived ledgers, 2026-08-12: 3 of the 18 runs with
        # a checkable census printed that denial, having made 125, 122 and 14
        # calls to tools that consume the paper's own reported numbers.
        #
        # THE SET IS ASKED FOR, NOT RESTATED. `registry.cell_consuming_tools()`
        # derives it from a per-spec declaration that every tool must make, so
        # adding a tool cannot silently shrink it -- which is how the two
        # name-pattern counters above came to be wrong.
        #
        # COUNTED AS CALLS, NOT CELLS, and named so. These tools take loose
        # values and return no census cell ids, so any cell figure derived from
        # them would be invented. What the number licenses is a REFUSAL to
        # claim the tables went unchecked -- not a coverage figure.
        from . import registry as _registry

        _consumers = _registry.cell_consuming_tools()
        direct_calls, direct_tools = 0, {}
        for ev in events:
            name = ev["short"]
            # Disjoint from the two populations above, by CALL: a cell
            # already counted through `check_table` or as batch rows must
            # not be counted a second time here.
            if (name not in _consumers or name.endswith("check_table")
                    or ev["id"] in batch_ids):
                continue
            direct_calls += 1
            direct_tools[name] = direct_tools.get(name, 0) + 1

        summary = _census.summarise(entries, n_checked=len(checked))
        summary["cells_checked_via_check_table"] = len(checked)
        if batch_rows:
            summary["rows_checked_by_batch_tools"] = batch_rows
            summary["batch_tools"] = batch_tools
        if direct_calls:
            summary["direct_check_calls"] = direct_calls
            summary["direct_check_tools"] = direct_tools
        summary["note"] = _census.render(summary)
        return summary
    except Exception:
        return None


def _machine_refusals(messages: list[dict], limit: int = 40) -> list[dict]:
    """Every check the dispatcher declined to run, harvested from the sweep.

    `dispatch.check_table` builds a per-(cell, check) `not_run` record with a
    reader-grade reason, precisely so that coverage does not depend on the model
    remembering what it skipped. NOTHING CONSUMED IT. Zero references in this
    module, in report_render, in bundle, or in severity_reconcile -- the record
    existed only inside the archived tool result.

    The consequence is the one complaint this project keeps hearing. A run that
    submitted three tables and had every cell inside them refused still reported
    `tables_checked: ["Table 1", "Table 2", "Table 3"]`, because "checked" meant
    "attempted". A reader could not distinguish "checked and clean" from "never
    actually checked", and the two are not remotely the same claim.

    Parsed from the raw messages rather than from `_tool_call_ledger`, whose
    result field is truncated for bulk tools -- and `check_table` is one, so the
    refusals would be cut off exactly on the tables big enough to matter.

    Rows are grouped by (tools, reason) so a table with 34 identically-refused
    cells contributes one entry naming 34 rows, not 34 entries.
    """
    results: dict[str, str] = {}
    for event in messages:
        if event.get("type") != "user":
            continue
        content = (event.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                inner = block.get("content")
                if isinstance(inner, list):
                    text = "".join(p.get("text", "") for p in inner if isinstance(p, dict))
                else:
                    text = inner if isinstance(inner, str) else ""
                results[block.get("tool_use_id")] = text

    grouped: dict[tuple[str, str], list[str]] = {}
    for event in messages:
        if event.get("type") != "assistant":
            continue
        content = (event.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else []:
            if not (isinstance(block, dict) and block.get("type") == "tool_use"):
                continue
            name = block.get("name", "")
            if not name.endswith("check_table"):
                continue
            try:
                payload = json.loads(results.get(block.get("id"), "") or "{}")
            except (ValueError, TypeError):
                continue
            for entry in payload.get("not_run") or []:
                if not isinstance(entry, dict):
                    continue
                reason = str(entry.get("reason") or "").strip()
                if not reason:
                    continue
                tools = ", ".join(entry.get("tools") or []) or "no applicable check"
                grouped.setdefault((tools, reason), []).append(str(entry.get("cell")))

    out = []
    for (tools, reason), rows in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        shown = ", ".join(rows[:6]) + (f" and {len(rows) - 6} more" if len(rows) > 6 else "")
        out.append({
            "location": f"table rows {shown}",
            "reason": f"{tools} not run: {reason}",
            "n_cells": len(rows),
            "source": "dispatcher",
        })
    return out[:limit]


def _skill_call(call_input) -> "tuple[str, dict] | None":
    """`(tool, args)` when a Bash call is exactly `metascience tool run <tool>
    --json '<object>'`, else None. Exactness is the point: anything else in
    the command line is not a call our tool layer answered as recorded."""
    import shlex
    cmd = call_input.get("command") if isinstance(call_input, dict) else None
    if not isinstance(cmd, str):
        return None
    try:
        parts = shlex.split(cmd)
    except ValueError:
        return None
    if len(parts) != 6 or parts[:3] != ["metascience", "tool", "run"] or parts[4] != "--json":
        return None
    try:
        args = json.loads(parts[5])
    except ValueError:
        return None
    return (parts[3], args) if isinstance(args, dict) else None


def _skill_manual_call(call_input) -> bool:
    cmd = call_input.get("command") if isinstance(call_input, dict) else None
    return isinstance(cmd, str) and cmd.strip().startswith(
        ("metascience tool describe", "metascience tool list"))


def _tool_call_ledger(messages: list[dict], allowed: list[str]) -> list[dict]:
    """One record per tool call: what was asked, what came back, was it validated.

    This is the audit trail. A finding is only as trustworthy as the call that
    produced it, and until this existed there was no way to tell -- in a real run
    the model hand-wrote scipy in `python3 -c` for two of its three headline
    findings, and the report looked identical to one where it had not.

    FOUR SURFACES, AND THERE USED TO BE THREE. `forensic_mcp` was assigned to
    any name carrying the MCP prefix, which answers "is this one of our tools"
    and not "is this on the list this stage declared". They are different
    questions with different answers: stage 2 called `absence_of_evidence`,
    which is on stage 1's allowlist and not on stage 2's, and the audit printed
    `n_unvalidated: 0` and the word "clean" beside a 35-name list the call was
    not on. `forensic_mcp_offlist` separates them. It stays `validated` -- the
    arithmetic really was done by our tool, so no finding is discredited by it
    -- but it is no longer invisible.

    WITH NO DECLARED LIST there is nothing to be off, so an empty `allowed` maps
    every MCP call to `forensic_mcp`. Several internal callers build a ledger
    with `allowed=[]` purely to read results back; inventing a breach for them
    would be an accusation manufactured by our own bookkeeping.
    """
    allowed_set = set(allowed or [])
    declares_mcp = any(t.startswith(MCP_TOOL_PREFIX) for t in allowed_set)
    ledger: list[dict] = []
    results: dict[str, dict] = {}

    # First pass: index tool_result blocks by the id they answer.
    for event in messages:
        if event.get("type") != "user":
            continue
        content = (event.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                inner = block.get("content")
                if isinstance(inner, list):
                    text = "".join(
                        p.get("text", "") for p in inner if isinstance(p, dict)
                    )
                elif isinstance(inner, str):
                    text = inner
                else:
                    text = ""
                results[block.get("tool_use_id")] = {
                    "text": text,
                    "is_error": bool(block.get("is_error")),
                }

    seq = 0
    for event in messages:
        if event.get("type") != "assistant":
            continue
        content = (event.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else []:
            if not (isinstance(block, dict) and block.get("type") == "tool_use"):
                continue
            seq += 1
            name = block.get("name", "?")
            call_input = block.get("input")
            via = None
            # `tool_access: skill`: a shell call of the generic tool command IS
            # a forensic call -- recorded under the tool's MCP name with its
            # parsed arguments, so every consumer of the ledger reads it as
            # one. `describe`/`list` (and brief mode's describe_tool) are
            # reading the manual, not checking the paper.
            skill = _skill_call(call_input) if name == "Bash" else None
            if skill is not None:
                name, call_input, via = MCP_TOOL_PREFIX + skill[0], skill[1], "cli"
            short = name[len(MCP_TOOL_PREFIX):] if name.startswith(MCP_TOOL_PREFIX) else name
            if not name.startswith(MCP_TOOL_PREFIX):
                # Our own tool names are already canonical; only the backends'
                # built-ins disagree with each other.
                short = _canonical_tool(short)
            if short == "describe_tool" or (
                    short == "Bash" and _skill_manual_call(call_input)):
                surface = "harness"
            elif short in AGENT_CODE_TOOLS:
                # AD-HOC CODE IS NOT A FORENSIC TOOL, even though
                # `run_python_script` rides the forensic MCP server and so
                # matched the prefix test below. docs/specs/pipeline.md §9
                # is explicit: `agent_code` (science agent only), `validated`
                # False, "web text and ad-hoc code are never validated
                # evidence". MEASURED 2026-09-03 before this landed: all six
                # `run_python_script` calls across the four archived parallel
                # runs were filed `forensic_mcp`, `validated: True`, so a
                # finding resting on a script the model wrote itself was
                # indistinguishable from one resting on a tool we wrote and
                # test. That is the surface `_unbacked_findings` reads.
                surface = "agent_code"
            elif short in _WEB_SURFACE_TOOLS:
                # Same rule, other half of the same spec line: web text is
                # never validated evidence either.
                surface = "web" if (name in allowed_set or short in allowed_set
                                    or not allowed_set) else "UNVALIDATED"
            elif name.startswith(MCP_TOOL_PREFIX):
                surface = ("forensic_mcp"
                           if not declares_mcp or name in allowed_set
                           else "forensic_mcp_offlist")
            elif short in _HARNESS_TOOLS:
                surface = "harness"
            elif (short == "Bash" and "Read" in allowed_set
                  and _shell_reads_only(block.get("input"))):
                # Codex's Read analog: the stage may read files, and this call
                # only read them (`_shell_reads_only`). Not validated evidence,
                # and not a breach.
                surface = "builtin_allowed"
            elif name in allowed_set or short in allowed_set:
                # `short` as well as `name`: the allowlist is written in
                # canonical names, and a backend that reports a display string
                # would otherwise have every call it makes filed as a breach.
                surface = "builtin_allowed"
            else:
                surface = "UNVALIDATED"

            res = results.get(block.get("id"), {})
            text = res.get("text", "")
            if via == "cli":
                # `tool run` prints the verdict line, then the MCP text.
                text = text.split("\n", 1)[1] if "\n" in text else text
            keep_full = short not in _BULK_TOOLS
            truncated = not keep_full and len(text) > _MAX_LEDGER_RESULT
            ledger.append({
                "seq": seq,
                "tool": name,
                "tool_short": short,
                "surface": surface,
                # OFF-LIST IS STILL VALIDATED, deliberately. `validated` answers
                # "was this arithmetic done by a tool we wrote and test", which
                # is what `_unbacked_findings` needs; being called by the wrong
                # stage does not make the computation wrong. The list breach is
                # reported through `surface`, where it cannot discredit a
                # finding that is in fact backed.
                # `agent_code` and `web` are deliberately absent: the spec
                # locks both to False. Off-list forensic calls stay True --
                # being called by the wrong stage does not make our own
                # arithmetic wrong; the breach is reported through `surface`.
                "validated": surface in ("forensic_mcp", "forensic_mcp_offlist"),
                "tool_use_id": block.get("id"),
                "input": call_input,
                **({"via": via, "command": (block.get("input") or {}).get("command")}
                   if via else {}),
                "result": text[:_MAX_LEDGER_RESULT] if truncated else text,
                "result_truncated": truncated,
                "result_chars": len(text),
                "is_error": res.get("is_error", False),
            })
    return ledger


def _assert_forensic_tools_ran(stage: dict, allowed: list[str], stage_label: str) -> None:
    """Fail closed if stage 1 declared MCP tools and none on its list ran.

    Counts `forensic_mcp` (on-list) only. Off-list MCP — including the
    CLI-only image and text tools — stays `validated` on the ledger so a
    finding those tools computed is not discredited, but it does not prove
    the sweep reached its numeric surface. A Grok run that only called
    `analyze_paper_images` / `detect_tortured_phrases` and dumped empty
    coverage used to pass this gate.

    Stage 2 / adjudication / repair are exempt: an editorial pass may
    legitimately make no forensic calls. Measured 2026-08-18: 59 archived
    stage-1 ledgers, min 14 validated calls, never zero.
    """
    if stage_label not in ("sweep", "analysis"):
        return
    if stage.get("is_error"):
        # An errored stage's ledger is empty BECAUSE the call failed (API
        # error, timeout); the error path already carries the true
        # diagnosis. Raising "plumbing failure" here mislabels it AND
        # turns the both-stages-failed -> partial-report contract into a
        # crash (this is what kept test_stage_failure_paths red). The
        # plumbing guard is for stages that "succeeded" while calling
        # nothing -- and _retryable_empty_forensic_dump already excluded
        # errored stages from its retry for the same reason.
        return
    if not any(str(t).startswith(MCP_TOOL_PREFIX) for t in (allowed or [])):
        return
    ledger = _tool_call_ledger(stage.get("messages") or [], allowed)
    n_on_list = sum(1 for row in ledger if row.get("surface") == "forensic_mcp")
    if n_on_list == 0:
        raise ForensicToolsNeverRan(
            f"Stage {stage_label!r} declared forensic MCP tools but the "
            f"ledger recorded 0 on-list calls. That is a plumbing failure "
            f"(MCP never reached the model, or the model only invoked "
            f"CLI-only / off-list tools), not a paper with nothing to "
            f"check. Refuse rather than publish a clean review.",
            stage=stage,
        )


#: Grok 4.6 has been observed (2026-08-20) to satisfy `--json-schema` on
#: turn 1 with the empty findings skeleton and zero tool calls, MCP live.
#: Claude's archived stage-1 ledgers never did this (min 14 on-list, n=59,
#: 2026-08-18). One extra attempt, new sandbox. A timeout or CLI error is
#: not that dump and is not retried.
GROK_EMPTY_DUMP_RETRIES = 1


def _retryable_empty_forensic_dump(stage: dict, backend) -> bool:
    """True when a 0-tool refuse is the empty-JSON dump, not a hang or crash."""
    if getattr(backend, "name", None) != "grok":
        return False
    if stage.get("error_subtype") in _CUT_OFF_SUBTYPES:
        return False
    if stage.get("is_error"):
        return False
    return True


async def _run_stage_requiring_forensic_tools(
    *,
    build_cmd,
    prompt: str,
    allowed_tools: list[str],
    stage_label: str,
    backend,
    spend_label: str | None = None,
    verbose: bool = False,
    timeout: int | None = None,
    on_progress: "Callable[[dict], None] | None" = None,
) -> dict:
    """Run a forensic stage; on Grok, retry once if it dumped empty JSON.

    `build_cmd` must return a FRESH Invocation each call. Grok's sandbox is
    deleted when `_run_stage` returns, so reusing the first cmd writes the
    prompt into a directory that no longer exists.
    """
    extra = (
        GROK_EMPTY_DUMP_RETRIES
        if getattr(backend, "name", None) == "grok"
        else 0
    )
    attempts = 1 + extra
    label = spend_label or stage_label
    prior: list[dict] = []
    for attempt in range(1, attempts + 1):
        inv = build_cmd()
        stage = await _run_stage(
            inv, prompt, verbose=verbose, timeout=timeout,
            on_progress=on_progress, stage_label=stage_label,
        )
        record_spend(
            label if attempt == 1 else f"{label}_retry",
            stage,
        )
        try:
            _assert_forensic_tools_ran(stage, allowed_tools, stage_label)
        except ForensicToolsNeverRan as exc:
            if (
                attempt < attempts
                and _retryable_empty_forensic_dump(stage, backend)
            ):
                if verbose:
                    print(
                        f"[{stage_label}] 0 on-list forensic calls on "
                        f"attempt {attempt}; retrying once (empty JSON "
                        "dump, not a paper with nothing to check)."
                    )
                prior.append(stage)
                continue
            exc.prior_stages = list(prior)
            raise
        if prior:
            stage["retried_after_empty_dump"] = len(prior)
        return stage
    raise RuntimeError("_run_stage_requiring_forensic_tools: no attempts")


#: (tool, guard) pairs whose DEFAULT is the right answer for the input the tool
#: is defined over, mapped to why. Same shape, and the same reason, as
#: `_HARNESS_TOOLS`: an audit that fires on every clean run teaches its reader to
#: skip it, and then it is worse than absent.
#:
#: MEASURED on the three wave-3 papers: 23/26 guard slots supplied (88%), which
#: is under the 0.9 threshold, so all three runs printed "A defaulted guard is
#: the most likely cause of a false accusation". All three misses were the SAME
#: slot -- `check_table`'s `provenance`, once per paper -- and every one of the
#: other seven guarded slots was supplied 100% of the time. The alarm was firing
#: on a correct default and nothing else.
#:
#: The audit's own premise is INVERSION: a guard earns an alarm because a wrong
#: value flips a check's answer rather than blurring it. `provenance` has exactly
#: one behavioural branch inside `check_table` (dispatch.py: `measured =
#: provenance in ("measured_raster", "measured_vector", "figure_pixels")`), and
#: it decides whether to stamp `uncertainty` and let the registry's gate REFUSE
#: the exact-arithmetic checks. On a table of printed literals -- which is what
#: `cells` is -- running them is the correct answer, and `printed_table` gives
#: it. Calling that a breach is not caution, it is a miscount.
#:
#: Rejected the alternative fix (make the model pass `provenance="printed_table"`
#: explicitly): that types out the default and changes nothing the tool computes,
#: so the audit would read 26/26 while measuring strictly less than before.
#: Ceremony is not evidence.
#:
#: This excusal is CONDITIONAL -- see `_guard_audit`. The default is only correct
#: while no figure-measured value can have reached the table.
#: `provenance` was extended from `check_table` alone to every exact-arithmetic
#: check on 2026-08-07, so a figure-measured value is refused on the DIRECT
#: single-tool path too -- which is the only path stage 2 has. That gate is
#: right, but on its own it would have re-created the alarm this list exists to
#: silence: fifteen further guarded slots, defaulted on essentially every call.
#:
#: The dividing line is the one written above -- is the default an ANSWER or an
#: admission of ignorance? `printed_text` is an answer, and it is the correct one
#: for the overwhelming majority of values a paper reports. The excusal is still
#: WITHDRAWN the moment the ledger shows a figure image was opened, which is the
#: only circumstance in which a defaulted provenance can be the wrong reading.
_PROVENANCE_DEFAULT_IS_SOUND = (
    "the default is the correct reading for a value PRINTED in the paper, and "
    "the overwhelming majority are. This guard decides only whether the "
    "exact-arithmetic checks are REFUSED, and on a printed value they should "
    "run. Withdrawn as soon as this run opens a figure image."
)

_SOUND_GUARD_DEFAULTS = {
    ("check_table", "provenance"): (
        "`cells` is a table of printed literals, so `printed_table` is the correct "
        "reading; the only thing this guard changes is whether the exact-arithmetic "
        "checks are refused, and on printed values they should run."
    ),
}


#: The one exact-arithmetic check whose defaulted `provenance` is NOT excused.
#: `check_effect_plausibility` is the check BUILT to accept figure-derived
#: input -- a digitised value arriving there is the designed route, not an edge
#: case, so "the caller did not say where this came from" is a real omission
#: rather than a sound default. Excusing it would disarm the guard on the one
#: tool where measured values are expected.
_PROVENANCE_ALWAYS_ALARMS = {"check_effect_plausibility"}


def _extend_sound_defaults() -> None:
    """Every guarded `provenance` slot inherits the excusal above.

    Derived from the registry rather than listed, so a tool that gains the guard
    later cannot silently re-arm the false alarm -- and so that the one
    deliberate exception has to be named rather than merely omitted.
    """
    try:
        from .registry import SPECS
    except Exception:                      # pragma: no cover - import cycle
        return
    for spec in SPECS:
        key = (spec.name, "provenance")
        if spec.name in _PROVENANCE_ALWAYS_ALARMS:
            continue
        if key not in _SOUND_GUARD_DEFAULTS and any(
            p.name == "provenance" and p.guard for p in spec.params
        ):
            _SOUND_GUARD_DEFAULTS[key] = _PROVENANCE_DEFAULT_IS_SOUND


_extend_sound_defaults()


def _guard_audit(ledger: list[dict]) -> dict:
    """For each call to a guarded tool: was the guard supplied, or defaulted?

    WHY THIS IS THE MEASUREMENT THAT MATTERS.

    A guard is a precondition without which a check does not degrade -- it
    INVERTS. At most 0.31% of numeric cells in a real corpus are GRIM-eligible
    at all, so a defaulted `data_type` is not a minor omission; it is the single
    most likely cause of a false accusation. The specificity figures that used
    to appear here (0.846 / 0.0000) were UNSOURCED -- nothing in this tree
    computes them -- and were removed on 2026-08-12.

    Nobody currently knows how often the model defaults them, because the
    model's own anatomy has never been compared against anything. This makes it
    a number instead of an argument.

    It is also the cheap experiment that settles a live design disagreement.
    Dan's position is that the CLI is sufficient and the agent should just run;
    the counter-proposal is a human-authored run-spec declaring the guards. If
    this audit shows guards are near-always supplied, Dan is right and the spec
    is unnecessary. If they are often defaulted, this number is the argument for
    it. Free, always on, and it needs no spec file to produce.

    WHICH GUARDS STILL RAISE THE ALARM, AND WHY.

    Every one of them except the single pair in `_SOUND_GUARD_DEFAULTS`, and the
    dividing line is whether the default is an ANSWER or an admission:

    * `data_type='unknown'` (debit, GRIM, GRIMMER, SPRITE) and
      `bound_source='assumed'` (GRIM) are ignorance sentinels. RE-MEASURED
      2026-08-07: `data_type='unknown'` is now REFUSED by every applicability
      guard -- mean 128.43, sd 15.21, n 100 returns `indeterminate`,
      `applicable: false` from grim, grimmer and sprite alike. Still
      alarm-worthy, but for the opposite reason to the one this docstring used
      to give: the cost is a check that silently did not happen, not a false
      accusation. `bound_source='assumed'` is the one that still changes an
      answer -- it caps an out-of-range finding at `suspicious`, where
      'stated' licenses `impossible` (29/495 sample sizes vs 495/495 on those
      same numbers). See `_GUARD_CONSEQUENCE`.
    * `variables`, `bindings`, `field`, `measure`, `design`, `decimals`,
      `decimals_sd`, `test_type` have no default at all -- defaulting them means
      the tool never learned the thing it needed. Alarm-worthy.
    * `check_effect_plausibility`'s `provenance` looks like the excused pair and
      is deliberately NOT excused. That tool is the one built to accept
      figure-derived inputs -- its own description says so -- so a digitised
      effect arriving there is the designed route, not an edge case, and letting
      `printed_text` stand silently relabels a measured value as a printed one.
      (Measured: supplied 2/2 in wave 3, so excusing it would buy nothing
      anyway.)
    * `multiplicity_report`'s `family_label` names WHICH family the correction
      covers, i.e. the denominator that decides how many claims are lost.
      Substantive-looking default, but a wrong family changes the number.
      Alarm-worthy. (Measured: supplied 10/10 in wave 3.)
    """
    from .registry import BY_NAME

    per_tool: dict[str, dict] = {}
    defaulted: list[dict] = []
    excused: list[dict] = []
    supplied = total = 0

    # A sound default stops being sound the moment a figure-measured value could
    # have reached the tool, so this is decided from the ledger rather than
    # asserted. `check_table` is stage-1-only and so is every figure read, so the
    # per-stage ledger this runs on already contains both if either happened.
    # MEASURED in wave 3: `extract_figures` ran once per paper and not one crop
    # was ever opened, so no figure-derived number existed to mislabel.
    figures_seen = _figures_were_read(ledger)

    for call in ledger:
        spec = BY_NAME.get(call.get("tool_short", ""))
        if spec is None or not spec.guards():
            continue
        args = call.get("input") or {}
        for guard in sorted(spec.guards()):
            row = per_tool.setdefault(
                spec.name, {"supplied": 0, "defaulted": 0, "excused": 0})
            sound = _SOUND_GUARD_DEFAULTS.get((spec.name, guard))
            if guard in args and args[guard] not in (None, ""):
                total += 1
                supplied += 1
                row["supplied"] += 1
            elif sound and not figures_seen:
                # Recorded, not counted -- exactly as a `StructuredOutput` call
                # stays in the ledger tagged `harness` instead of vanishing.
                # Hiding the slot would make the excusal itself unauditable.
                row["excused"] += 1
                excused.append({
                    "seq": call.get("seq"),
                    "tool": spec.name,
                    "guard": guard,
                    "default": next((p.default for p in spec.params
                                     if p.name == guard), None),
                    "why_sound": sound,
                })
            else:
                total += 1
                row["defaulted"] += 1
                defaulted.append({
                    "seq": call.get("seq"),
                    "tool": spec.name,
                    "guard": guard,
                    "consequence": _GUARD_CONSEQUENCE.get(
                        guard, "the tool ran on its default for this precondition"),
                })

    rate = (supplied / total) if total else None
    return {
        "n_guarded_calls": sum(1 for c in ledger
                               if (BY_NAME.get(c.get("tool_short", "")) or
                                   type("x", (), {"guards": lambda self: set()})()).guards()),
        # `n_guard_slots` is the denominator of `supplied_rate`, because the
        # viewer prints them as one sentence ("N of M guard slots supplied
        # (P%)"). Excused slots are carried in their own keys instead, so the
        # sentence stays arithmetically true and the excusals stay visible.
        "n_guard_slots": total,
        "n_supplied": supplied,
        "n_defaulted": total - supplied,
        "supplied_rate": round(rate, 4) if rate is not None else None,
        "per_tool": per_tool,
        "defaulted_calls": defaulted[:50],
        "n_excused": len(excused),
        "excused_calls": excused[:50],
        "verdict": (
            ("no guarded tools were called" if not excused else
             f"{len(excused)} guard slot(s) took a default that is correct for the "
             "input; none needed supplying")
            if not total else
            f"{supplied}/{total} guard slots were supplied ({rate:.0%})"
            + (f"; a further {len(excused)} took a default that is correct for the "
               "input and is not counted against the run" if excused else "")
            + ". "
            + ("A defaulted guard is the most likely cause of a false accusation: "
               "a misspecified scale bound inverts a check rather than weakening it."
               if rate < 0.9 else
               "Guards were supplied consistently; a declared run-spec would add little here.")
        ),
    }


#: What a defaulted guard actually costs, per guard. Used in the audit output so
#: the number comes with its consequence rather than as a bare count.
_GUARD_CONSEQUENCE = {
    # RE-MEASURED 2026-08-07. The previous text said the tools "ran assuming
    # INTEGER data on a 1-7 scale" and cited "verified: systolic BP 128.43 +/-
    # 15.21 returns `impossible`". Both halves were stale, and a stale
    # "verified" is worse than no claim, so it is replaced by what the code
    # does now:
    #
    #   * The registry default for `data_type` is 'unknown' on grim_check,
    #     grimmer_check, sprite_reconstruct and debit_check, and
    #     `canonical_data_type('unknown')` is refused by every applicability
    #     guard. Measured on mean=128.43, sd=15.21, n=100 with the guard
    #     defaulted: grim, grimmer and sprite all return `indeterminate`,
    #     `applicable: false`. Nothing is manufactured, because nothing runs.
    #   * Forcing data_type='likert'/'integer' on the same numbers returns
    #     `suspicious`, not `impossible` -- `bound_source` defaults to
    #     'assumed', and rulebook rule 4 caps an invented bound at
    #     `suspicious`. Sweeping n = 5..499: `impossible` at 29 of 495 sample
    #     sizes with bound_source='assumed', and at 495 of 495 with
    #     bound_source='stated'.
    #
    # So defaulting this guard costs COVERAGE, not specificity: the granularity
    # check silently declines. The false-accusation risk sits on the other
    # side, in asserting integer/likert for a continuous measure.
    "data_type": "GRIM/GRIMMER/SPRITE/DEBIT refused to run: 'unknown' fails every "
                 "applicability guard, so the check returned `indeterminate` and the "
                 "cell went unchecked. Measured: mean 128.43, sd 15.21, n 100 with the "
                 "guard defaulted returns `indeterminate` from all three; the same "
                 "numbers asserted as integer/likert return `suspicious`, and "
                 "`impossible` at 29 of 495 sample sizes n=5..499 (495/495 once a "
                 "bound is claimed as stated).",
    "bound_source": "an out-of-range finding was treated as resting on a bound the "
                    "paper stated, when it may be one we invented (rulebook rule 4).",
    "design": "the CSF baseline test ran without knowing the allocation. Cluster and "
              "stratified designs force baseline balance BY CONSTRUCTION; uncorrected "
              "this flagged a correctly-randomised cluster trial ~71% of the time.",
    "measure": "an effect estimate's CI was checked on the LINEAR scale. Ratio "
               "measures (OR/RR/HR) are log-symmetric; this misfires on ~1/3 of "
               "hazard ratios at SE_log = 0.4.",
    "field": "an effect size was judged large or small with no stated comparison class.",
    "decimals": "precision was assumed rather than read from the printed literal, "
                "which shrinks the rounding interval and manufactures impossibilities.",
    "decimals_sd": "SD precision was assumed rather than read from the printed literal.",
    "provenance": "a value's origin was unrecorded, so figure-measured and printed "
                  "numbers were treated alike.",
    "p_relation": "whether the p was printed exact ('p = ') or as a bound ('p < ') was "
                  "not stated. A value that is no conventional bound was read as exact; "
                  "one at .05/.01/.001 was given the bound reading, so an EXACT p there "
                  "larger than its statistic allows went unchecked (the under-claim "
                  "direction).",
}


#: A `Read` whose path ends in one of these opened an image, not a text file.
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def _figures_were_read(ledger: list[dict] | None) -> bool:
    """Did the run actually OPEN a figure, as against merely extracting one?

    Extraction is not inspection, and the distinction is the whole point. On the
    run that prompted this, `extract_figures` wrote six PNGs and none of them
    was ever read -- while the report told the reader that figures had not been
    inspected, which was true, and then wrote findings asserting values were
    "never stated anywhere in the paper" when the figures printed them.

    Decided from the ledger rather than from a flag, because a flag records
    what we intended and the ledger records what happened.
    """
    for call in ledger or []:
        if not isinstance(call, dict):
            continue
        if str(call.get("tool_short") or "") != "Read":
            continue
        args = call.get("input") or {}
        path = str(args.get("file_path") or args.get("path") or "").lower()
        if path.endswith(_IMAGE_SUFFIXES):
            return True
    return False


def _sweep_source_coverage(ledgers, paper_path) -> dict | None:
    """How many checks recorded the passage their numbers came from.

    Shaped like `write_review_outputs`' `source_coverage` -- stage key to
    summary -- so `report_render` takes one argument whichever caller built it.

    TAKES EVERY STAGE, AND USED TO TAKE ONE. It accepted a bare stage-1 ledger
    and hardcoded `{"stage1": ...}`, so `report.md` and the
    `source_coverage.json` written beside it counted different populations and
    disagreed in every run that had a stage 2. The direction of the error is
    what makes it worth a paragraph: the number under-reported is the count of
    quotations the REVIEW assembled rather than lifted from the paper, so the
    reader was given fewer caveats than the evidence warranted. A bare list is
    still accepted and still read as stage 1, because archived callers pass one.

    Returns None, never a zeroed summary, when the paper cannot be read. A
    report that says "0 of 31 checks were traceable" because WE could not open
    the PDF is a false statement about the review in exactly the grammar this
    document uses for findings about the authors.

    Never raises: this runs after both stages are billed, and no coverage
    statistic is worth losing a paid analysis over.
    """
    if isinstance(ledgers, list):
        ledgers = {"stage1": ledgers}
    by_stage = {k: v for k, v in (ledgers or {}).items() if v}
    if not by_stage or not paper_path:
        return None
    try:
        from . import quotes as _quotes_mod
        pdir = Path(paper_path)
        pdir = pdir if pdir.is_dir() else pdir.parent
        hay = _quotes_mod.build_haystack(pdir) or None
        if not hay:
            return None
        return {k: _quotes_mod.verify_ledger(v, hay) for k, v in by_stage.items()}
    except Exception:  # noqa: BLE001
        return None


def _unbacked_findings(ledger: list[dict], findings: list[dict] | None) -> list[dict]:
    """Findings that name a tool no call in the ledger can account for.

    THIS is the failure the audit was supposed to catch. Watching for `Bash`
    detects a model that runs its own code; it does not detect the easier and
    likelier thing, which is a model that simply ASSERTS arithmetic it never
    performed and labels it with a technique. On the run where the MCP server
    failed to start, seventeen findings were hand-computed and labelled `grim`,
    `grimmer` and `statcheck` -- and the sandbox audit returned the same
    verdict it returns on a clean run, because no forbidden tool was called.

    A finding tagged `manual` is honest and is not counted. One naming a real
    technique with no matching validated call is the thing to look at.
    """
    from .finding_view import effective_severity, ref
    from .core.prompts import NON_TOOL_TECHNIQUES
    from .severity_reconcile import _candidate_tools

    ran = {c.get("tool_short") for c in ledger
           if isinstance(c, dict) and c.get("validated")}
    out: list[dict] = []
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        technique = f.get("technique")
        # A TECHNIQUE THAT CANNOT HAVE A TOOL IS NOT AN UNBACKED ONE. The
        # docstring above names `manual` as the honest label, and v2 DELETED
        # `manual`: `internal_contradiction`, `not_computational` and
        # `factual_claim` are the v2 spellings, and none of them has a
        # candidate tool to match. Relying on `_candidate_tools` returning
        # empty stopped being enough the moment the vocabulary moved.
        #
        # MEASURED on the ten control runs: 137 of 141 rows this counted as
        # "unbacked" were non-tool techniques. So the naive repair of the id
        # bug below would have replaced a false all-clear with a false alarm
        # eight times larger -- which is why both halves ship together.
        if str(technique or "") in NON_TOOL_TECHNIQUES:
            continue
        candidates = _candidate_tools(technique)
        if not candidates:          # no tool claims this technique at all
            continue
        if not any(t in ran for t in candidates):
            # `ref`, not `f.get("id")`: a v2 row carries `finding_id`, so this
            # wrote `id: None` on every row and the audit's headline counted
            # zero -- reporting "clean: every tool call was on the validated
            # forensic surface" on runs whose own stage records said
            # `BREACH (unbacked): 8`. Verified on all nine control runs.
            out.append({"id": ref(f), "technique": technique,
                        "severity": effective_severity(f),
                        "location": f.get("location")})
    return out


#: Severities that make a claim about the paper rather than about our reach.
from .tools.severity import ACCUSES_AT_ALL as _ACCUSATORY  # one definition; see severity.py


def unbacked_accusations(ledger: list[dict], findings: list[dict] | None) -> list[dict]:
    """The unbacked findings that actually ACCUSE. This is the gateable subset.

    A run linter must fire on this list, NOT on the raw sandbox verdict, and the
    difference is the whole point.

    MEASURED over 25 archived runs: 21 of 24 carry a BREACH verdict (88%), but 9
    of those are `level: surface` -- tool-allowlist bookkeeping whose own text
    says "no statistic was computed off-tool". Of the genuinely unbacked
    findings, there are 33 in the entire corpus and 25 of them are
    `indeterminate` or `consistent`, i.e. our own refusals and passes. Only 8 of
    239 accusations are unbacked, and 5 of those sit in one run.

    A gate on the raw verdict therefore fires on ~88% of runs, which guarantees
    it gets ignored -- the lesson the guard alarm already taught this repo. Worse,
    it fires for the wrong reason: the 2026-08-10 control run breached on two
    `indeterminate` findings (`duplication_not_assessable`,
    `no_power_analysis_stated`) while its three `grim_sweep` `impossible`
    findings were verbatim-quoted, reproduction-valid, tool-backed and CORRECT
    on hand-checked arithmetic. An `exit 1` on BREACH would have blocked a run
    whose headline finding was right, for reasons unrelated to it.

    An unbacked `indeterminate` is a refusal we could not attribute -- worth
    logging, not worth stopping a run. An unbacked `impossible` is arithmetic
    asserted and never performed, against a named paper, at the top of the
    ladder. Those are not the same event and must not share a gate.
    """
    return [f for f in _unbacked_findings(ledger, findings)
            if str(f.get("severity") or "") in _ACCUSATORY]


#: What each stage's `unbacked` count is a count OF. Written into
#: sandbox_audit.json so the artefact says which list it scored instead of
#: leaving a reader to assume both stages measured the same thing -- the exact
#: assumption that made the old number wrong.
_FINDINGS_SCORED = {
    "stage1": ("the sweep's own findings (findings.schema.json), which is the "
               "only schema carrying a `technique` to check a tool against"),
    "stage2": ("the editorial report's own findings (report.schema.json). That "
               "schema has no `technique` field, so a stage-2 finding names no "
               "check and none can be scored unbacked; the count is 0 by "
               "construction, not by verification"),
}


def compose_sandbox_audit(audits: dict[str, dict], head_key: str) -> dict:
    """The `sandbox_audit.json` document, from per-stage audits.

    ONE SOURCE FOR THE VERDICT WORDING, shared by the legacy serial writer and
    `parallel.write_parallel_outputs`. The parallel pipeline wrote no sandbox
    audit at all until v1.22.0 even though `docs/specs/pipeline.md §13`
    requires one and `README.md` calls it the artifact to read; duplicating
    this block to fix that would have let the two writers drift in what a
    breach is CALLED, which is the part a reader acts on.

    `head_key` names the producer whose unbacked findings are the headline --
    `stage1` on the legacy path, `tool_expert` on the parallel one. Only the
    producer that CLAIMS a check ran can have named one that did not; scoring
    another agent's findings against this agent's ledger measures the
    difference between two allowlists. That correction was measured on the
    archive: 29 top-level unbacked findings fell to 6 under per-stage scoring,
    so 23 of 29 were artefacts of the union rule.

    `severe`, `n_unvalidated` and off-list counts are summed across EVERY
    agent: a `Bash` call is a real breach wherever it happens.
    """
    breaches = sum(a.get("n_unvalidated", 0) for a in audits.values())
    severe = sum(a.get("n_severe", 0) for a in audits.values())
    offlist = sum(a.get("n_off_allowlist", 0) for a in audits.values())
    head = audits.get(head_key) or next(iter(audits.values()))
    unbacked_ids = {u["id"] for u in (head.get("unbacked_findings") or [])
                    if u.get("id")}
    unbacked = len(unbacked_ids)
    level = ("severe" if severe else "unbacked" if unbacked
             else "surface" if breaches
             else "off_allowlist" if offlist else "clean")
    return {
        "level": level,
        "verdict": {
            "severe": (f"BREACH (severe): {severe} call(s) could compute statistics "
                       "outside the validated tools; affected findings need re-checking"),
            "unbacked": (f"BREACH (unbacked): {unbacked} finding(s) name a check that "
                         "never ran -- the arithmetic was asserted, not performed"),
            "surface": (f"BREACH (surface): {breaches} call(s) extended the tool surface "
                        "at runtime, but no statistic was computed off-tool"),
            "off_allowlist": (f"OFF-LIST: {offlist} call(s) used a forensic tool the "
                              "stage did not declare. No finding is in doubt; the "
                              "published allowlist is not what ran"),
            "clean": "clean: every tool call was on the validated forensic surface",
        }[level],
        "n_unbacked_findings": unbacked,
        "unbacked_finding_ids": sorted(x for x in unbacked_ids if x),
        "n_unvalidated_total": breaches,
        "n_severe_total": severe,
        "n_off_allowlist_total": offlist,
        "stages": audits,
    }


def sandbox_run_meta(audit_doc: dict) -> dict:
    """The `run_meta.sandbox` block: every count the verdict can rest on.

    It carried `n_unvalidated` alone, so a run whose verdict read "BREACH
    (unbacked): 3" published `{"verdict": "...BREACH...", "n_unvalidated": 0}`
    -- a breach with nothing but a zero beside it, which a reader scanning for
    numbers takes for an empty alarm.
    """
    return {
        "verdict": audit_doc["verdict"],
        "level": audit_doc["level"],
        "n_unvalidated": audit_doc["n_unvalidated_total"],
        "n_severe": audit_doc["n_severe_total"],
        "n_unbacked_findings": audit_doc["n_unbacked_findings"],
        "n_off_allowlist": audit_doc["n_off_allowlist_total"],
    }


def _sandbox_audit(ledger: list[dict], allowed: list[str],
                   findings: list[dict] | None = None) -> dict:
    """Did anything run outside the validated surface? Answer it mechanically.

    `--allowedTools` does NOT restrict under `--permission-mode
    bypassPermissions`, so the allowlist alone is not proof. This checks what
    actually ran, which is the only thing that settles it.

    Two different questions, because they have two different answers:

    * Did a call go through a tool that could compute off-surface? (`Bash`)
    * Does a finding CLAIM a tool that never ran? (`_unbacked_findings`)

    The second is the one that catches a model asserting arithmetic, and until
    now nothing asked it.
    """
    breaches = [c for c in ledger if c["surface"] == "UNVALIDATED"]
    by_tool: dict[str, int] = {}
    for c in ledger:
        by_tool[c["tool_short"]] = by_tool.get(c["tool_short"], 0) + 1

    # Not all breaches are equal, and an audit that cries wolf gets ignored.
    # `Bash` and friends can COMPUTE a statistic outside the validated tools --
    # that directly corrupts findings. `ToolSearch` only widens the surface; it
    # is a real problem, but a different one, and conflating them would bury the
    # severe case under routine noise.
    severe = [c for c in breaches if c["tool_short"] in _COMPUTE_TOOLS]
    surface = [c for c in breaches if c["tool_short"] not in _COMPUTE_TOOLS]
    # OUR OWN TOOL, THE WRONG STAGE'S LIST. Ranked below every other breach
    # because the arithmetic is still ours and still tested, so no finding is
    # in doubt. It is here at all because the object PUBLISHES
    # `declared_allowlist` and used to print `n_unvalidated: 0` and the word
    # "clean" beside it while stage 2 ran `absence_of_evidence`, which is on
    # stage 1's list and not on stage 2's. A reader who checks the list against
    # the verdict was told the run stayed inside a boundary it had left.
    offlist = [c for c in ledger if c["surface"] == "forensic_mcp_offlist"]

    unbacked = _unbacked_findings(ledger, findings)

    if severe:
        verdict = (
            f"BREACH (severe): {len(severe)} call(s) could compute statistics outside "
            "the validated tools. Any finding derived from them was produced by "
            "model-written code and must be re-checked before it is reported."
        )
        level = "severe"
    elif unbacked:
        verdict = (
            f"BREACH (unbacked): {len(unbacked)} finding(s) name a check that never "
            "ran. No forbidden tool was called -- the arithmetic was asserted rather "
            "than performed, which is the likelier failure and the one a tool-surface "
            "check cannot see. Treat those findings as unverified."
        )
        level = "unbacked"
    elif surface:
        verdict = (
            f"BREACH (surface): {len(surface)} call(s) extended the tool surface at "
            "runtime. No statistic was computed off-tool, but the declared allowlist "
            "was not the whole story."
        )
        level = "surface"
    elif offlist:
        names = sorted({c["tool_short"] for c in offlist})
        verdict = (
            f"OFF-LIST: {len(offlist)} call(s) used a forensic tool this stage "
            f"did not declare ({', '.join(names)}). The arithmetic is still "
            "ours and still tested, so no finding is in doubt -- but the "
            "allowlist printed beside this verdict is not what the stage ran."
        )
        level = "off_allowlist"
    else:
        verdict = "clean: every tool call was on the validated forensic surface"
        level = "clean"

    # NOT SUMMED INTO `n_unvalidated`, and the restraint is the point. That
    # field means "ran outside the forensic toolkit"; folding a stage-discipline
    # breach into it would inflate the number every downstream reader treats as
    # the count of untrustworthy computations, which is the same shape of error
    # as the coverage numerator that counted one tool against every tool's
    # denominator.
    return {
        "declared_allowlist": list(allowed or []),
        "denied_tools": list(DENIED_TOOLS),
        "n_calls": len(ledger),
        # THE THREE HEADLINE COUNTS DO NOT PARTITION `n_calls` AND CANNOT.
        # `n_validated + n_unvalidated` fell short of `n_calls` in all six
        # archived stage blocks -- by 8, 7, 3, 2, 4 and 2 -- because `Read` and
        # `StructuredOutput` are harness plumbing and belong to neither bucket.
        # Rather than redefine a count other things read, name the residual:
        # `by_surface` sums to `n_calls` by construction, so a reader who tries
        # the arithmetic gets an answer instead of a discrepancy.
        "by_surface": {s: sum(1 for c in ledger if c["surface"] == s)
                       for s in sorted({c["surface"] for c in ledger})},
        "n_validated": sum(1 for c in ledger if c["validated"]),
        "n_unvalidated": len(breaches),
        "n_severe": len(severe),
        "n_surface": len(surface),
        "n_off_allowlist": len(offlist),
        "off_allowlist_calls": [
            {"seq": c["seq"], "tool": c["tool_short"],
             "input_preview": str(c.get("input"))[:200]}
            for c in offlist
        ],
        "n_unbacked_findings": len(unbacked),
        "unbacked_findings": unbacked,
        "level": level,
        "calls_by_tool": by_tool,
        "unvalidated_calls": [
            {"seq": c["seq"], "tool": c["tool"],
             "severity": "severe" if c["tool_short"] in _COMPUTE_TOOLS else "surface",
             "input_preview": str(c.get("input"))[:200]}
            for c in breaches
        ],
        "verdict": verdict,
    }


def _stage1_tools(figures: bool) -> list[str]:
    """The sweep's allowlist, minus figure tools when the pass is off.

    Removing it from the PROMPT is not enough -- a tool that is offered can be
    called. Default-off has to mean unavailable, not merely unmentioned.
    """
    if figures:
        return STAGE1_TOOLS
    drop = {_mcp("extract_figures")}
    return [t for t in STAGE1_TOOLS if t not in drop]


def _resolved_models(messages: list[dict]) -> dict:
    """Which model ACTUALLY ran, from the stream events -- not which was requested.

    A verified case from this repo's own corpus: a run recorded as `model: fable`
    in run_meta.json, in the report, and in its own directory name
    (`forensic_review_fable_07_17_2026`) was in fact performed almost entirely by
    `claude-opus-4-8`. Both stages emitted `model_refusal_fallback` with
    `api_refusal_category: "bio"` -- a cerebrolysin mouse study -- and
    `modelUsage` shows $2.799 of the $2.807 went to opus.

    So every cost and quality conclusion drawn from that run and attributed to
    Fable was wrong, including the "$22/paper on Fable" figure quoted in this
    repo's own documentation. Recording the REQUESTED alias and calling it the
    model is not a rounding error; it silently misattributes the work.

    The `bio` refusal category on a biomedical paper means this will recur
    across this corpus rather than being a one-off.
    """
    resolved: set[str] = set()
    fallbacks: list[dict] = []
    usage: dict = {}

    def walk(o):
        if isinstance(o, dict):
            if o.get("subtype") == "model_refusal_fallback":
                fallbacks.append({
                    "original_model": o.get("original_model"),
                    "fallback_model": o.get("fallback_model"),
                    "trigger": o.get("trigger"),
                    "api_refusal_category": o.get("api_refusal_category"),
                })
                if o.get("fallback_model"):
                    resolved.add(o["fallback_model"])
            if o.get("type") == "system" and o.get("model"):
                resolved.add(o["model"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
            return
        # modelUsage is the authoritative record: it is keyed by the model that
        # was actually billed.
        if isinstance(o, dict) and isinstance(o.get("modelUsage"), dict):
            for name, u in o["modelUsage"].items():
                resolved.add(name)
                # OUTPUT TOKENS ARE RECORDED, NOT JUST COST, and they are the
                # field that answers a question cost cannot. A secondary model
                # doing housekeeping and a secondary model summarising the
                # conversation cost about the same; what separates them is how
                # much they WROTE. See `tripwire.check_run`, which fails a run
                # where a non-primary model emits real content.
                usage.setdefault(name, {"costUSD": 0.0, "outputTokens": 0,
                                        "inputTokens": 0})
                usage[name]["costUSD"] += float(u.get("costUSD") or 0)
                usage[name]["outputTokens"] += int(u.get("outputTokens") or 0)
                usage[name]["inputTokens"] += int(u.get("inputTokens") or 0)

    walk(messages)
    billed = max(usage, key=lambda k: usage[k]["costUSD"], default=None)
    return {
        "models_resolved": sorted(resolved),
        "model_usage": usage,
        "primary_billed_model": billed,
        "fallbacks": fallbacks,
        "model_switched": len(resolved) > 1,
    }


def _slim_messages(messages: list[dict]) -> list[dict]:
    """Truncate tool_result payloads in persisted logs (they embed the paper)."""
    slimmed = []
    for event in messages:
        if event.get("type") == "user":
            content = (event.get("message") or {}).get("content")
            if isinstance(content, list):
                event = json.loads(json.dumps(event))  # deep copy
                for block in event["message"]["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        inner = block.get("content")
                        if isinstance(inner, list):
                            for part in inner:
                                if (
                                    isinstance(part, dict)
                                    and isinstance(part.get("text"), str)
                                    and len(part["text"]) > _MAX_LOGGED_TOOL_RESULT
                                ):
                                    part["text"] = (
                                        part["text"][:_MAX_LOGGED_TOOL_RESULT]
                                        + f" …[log truncated, {len(part['text'])} chars]"
                                    )
                        elif isinstance(inner, str) and len(inner) > _MAX_LOGGED_TOOL_RESULT:
                            block["content"] = (
                                inner[:_MAX_LOGGED_TOOL_RESULT]
                                + f" …[log truncated, {len(inner)} chars]"
                            )
        slimmed.append(event)
    return slimmed


def analyze_paper_sync(
    paper_path: str,
    verbose: bool = False,
    timeout: int | None = None,
    mode: str = "two_stage",
    budget_usd: float | None = None,
    model: str | None = None,
    effort: str = DEFAULT_EFFORT,
    figures: bool = False,
    backend: str | None = None,
) -> dict:
    """Synchronous wrapper for analyze_paper."""
    return asyncio.run(
        analyze_paper(
            paper_path,
            verbose=verbose,
            timeout=timeout,
            mode=mode,
            budget_usd=budget_usd,
            model=model,
            effort=effort,
            figures=figures,
            backend=backend,
        )
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m forensic_metascience_ai_toolkit.agent <paper_path>")
        print("  paper_path: a paper directory, a PDF, or a markdown file")
        sys.exit(1)

    paper_path = sys.argv[1]
    run_mode = sys.argv[2] if len(sys.argv) > 2 else "two_stage"

    print(f"Analyzing: {paper_path}")
    print("=" * 60)

    result = analyze_paper_sync(paper_path, verbose=True, mode=run_mode)

    print("\n" + "=" * 60)
    print("Analysis complete!")
    print(f"  cost: ${result['total_cost_usd']:.4f}")
    print(f"  tokens: {result['input_tokens']} in / {result['output_tokens']} out")
    if result.get("verdict"):
        print(f"  verdict: {result['verdict']} ({result.get('confidence')})")

    out_dir = Path(f"{_paper_id(paper_path)}_forensic_review")
    from .parallel import write_parallel_outputs
    written = write_parallel_outputs(result, out_dir)
    print(f"Outputs written to: {out_dir}/")
    for name, path in written.items():
        print(f"  {name}: {path.name}")
