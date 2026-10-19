"""Command-line interface for forensic metascience analysis."""

import asyncio
import hashlib
import json
import traceback
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from . import NOT_RECORDED, __version__
# The ONE source of truth for reasoning effort. Hardcoding "max" here instead
# overrode the safe default on every invocation and failed both stages with a
# 400 in ~2s: "output_config.effort 'max' is not supported when thinking is
# disabled". `agent.py` imports the SDK lazily, so this stays importable in a
# bare environment.
from .agent import DEFAULT_EFFORT, completed_review
from .extraction.pdf import extract_text_with_tables
from .tools import grim as grim_module, ttest as ttest_module, sprite as sprite_module
from .tools import sd_checks, anova as anova_module, csf as csf_module
from .tools import chi_squared, summation as summation_module, stalt as stalt_module
from .tools import ratio as ratio_module
from .tools import flow as flow_module
from .tools import debit as debit_module
from .tools import se_sd as se_sd_module
from .tools import heuristics as heuristics_module
from .tools import rivets as rivets_module
from .tools import continuous_to_categorical as cont_cat_module
from .tools.table1_dispersion import table1_dispersion as _table1_dispersion_fn
from .tools.variance_dispersion import (
    check_variance_dispersion as _variance_dispersion_fn,
)
from .tools import r_wrappers
from .anatomy import StatisticalTest, multiplicity_report as _multiplicity_report_fn

from .tools.severity import SEVERITY_COLORS, SEVERITY_LEVELS, normalize_severity

from .cli_compat import McpFriendlyGroup
from .progress import (  # noqa: F401 -- the three underscore aliases are
    # re-exported for tests/test_progress_callback.py, which imports them
    # FROM cli; ruff --fix deleted them on 2026-09-02 and broke that module.
    LiveBatchStatus,
    fmt_elapsed_clock as _fmt_elapsed,
    fmt_tokens as _fmt_tokens,
    render_stage_line as _render_progress,
)

# `cls=McpFriendlyGroup` makes the CLI accept the shape the MODEL writes --
# MCP parameter names as long flags, values inline -- as well as its own. See
# `cli_compat` for the measurement: 205 of the 360 recorded reproduction
# failures across the archive are argument-SHAPE mismatches on commands whose
# arithmetic was correct.
app = typer.Typer(
    name="metascience",
    help="Forensic metascience analysis of scientific papers",
    add_completion=False,
    cls=McpFriendlyGroup,
)
from . import image_plugin as _image_plugin

if _image_plugin.available():
    # Accelerator resource options and the compute verbs belong to the image
    # analysis package (its broker); without it there is nothing to configure.
    app.callback()(_image_plugin.load("resource_options").resource_options)
    _image_plugin.load("compute.cli").register(app)
else:
    @app.callback()
    def _no_resource_options():
        """Forensic metascience analysis of scientific papers"""


def _image_command(name: str, attr: str, alias: str | None = None) -> None:
    """Register one `image-*` verb from the image analysis package, when it is
    installed; without it the verb does not exist (`metascience --help` lists
    only what can run)."""
    if not _image_plugin.available():
        return
    fn = getattr(_image_plugin.load("cli"), attr)
    globals()[alias or attr] = fn
    app.command(name)(fn)

console = Console()


def _severity_color(severity: str | None) -> str:
    return SEVERITY_COLORS.get(normalize_severity(severity), "white")


def _published_findings(result: dict) -> list:
    """The findings the report published, else the sweep's, else nothing.

    Editorial findings are what a reader of the report sees. A failed
    editorial pass still has a denominator if we fall back to the sweep
    rather than printing five zeros that read as a clean paper.
    """
    report_obj = result.get("report_obj")
    if isinstance(report_obj, dict) and isinstance(report_obj.get("findings"), list):
        return report_obj["findings"]
    findings = result.get("findings")
    if isinstance(findings, dict) and isinstance(findings.get("findings"), list):
        return findings["findings"]
    if isinstance(findings, list):
        return findings
    return []


def _finding_counts(result: dict) -> dict[str, int]:
    """Tally by severity, every rung present at zero.

    Present-at-zero on purpose: a missing key and a zero read differently,
    and only one of them is a claim. Same rule as `webapp_index.severity_counts`.
    """
    counts = {s: 0 for s in SEVERITY_LEVELS}
    for f in _published_findings(result):
        if not isinstance(f, dict):
            continue
        sev = str(f.get("severity") or "").strip().lower()
        if sev in counts:
            counts[sev] += 1
    return counts


def _fmt_runtime(seconds) -> str:
    """`12.3s`, `2m 5s`, `1h 4m 5s` -- hours, minutes and seconds, never `1.1 h`.

    The hour form used to drop seconds (`1h 4m`), so a 66-minute paper and a
    119-minute paper both read as `1h 4m` / `1h 59m` with the leftover
    seconds thrown away. Batch totals live in that range.
    """
    if seconds is None:
        return "not recorded"
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return "not recorded"
    if s < 0 or s != s:  # negative or NaN
        return "not recorded"
    if s < 60:
        return f"{s:.1f}s"
    m, rem = divmod(s, 60)
    if m < 60:
        return f"{int(m)}m {rem:.0f}s"
    h, m = divmod(int(m), 60)
    return f"{h}h {m}m {rem:.0f}s"


def _print_analyze_summary(result: dict) -> None:
    """Verdict, finding counts by severity, runtime. Nothing else."""
    from . import verdicts as _verdicts

    raw = result.get("verdict")
    canon = _verdicts.canonical(raw) if raw else None
    color = {"reconciles": "green", "unresolved": "yellow",
             "does_not_reconcile": "red"}.get(canon, "white")
    if canon:
        shown = canon.replace("_", " ")
        note = (f" [dim](recorded as {str(raw).strip().lower()})[/dim]"
                if _verdicts.is_legacy(raw) else "")
        console.print(f"[bold]Verdict:[/bold] [{color}]{shown}[/{color}]{note}")
    else:
        console.print("[bold]Verdict:[/bold] [dim]none[/dim]")

    if result.get("mode") == "parallel":
        rows = (result.get("findings_v2") or {}).get("findings") or []
        from collections import Counter
        sev9 = Counter(f.get("severity") for f in rows
                       if f.get("outcome") == "problem"
                       and isinstance(f.get("severity"), int))
        adj = (result.get("findings_v2") or {}).get("adjudication") or {}
        console.print("Findings (1-9 ladder):")
        for sev in sorted(sev9, reverse=True):
            console.print(f"  S{sev}: {sev9[sev]}")
        console.print(f"  merged: {adj.get('n_merged', 0)}, "
                      f"discarded: {adj.get('n_discarded', 0)}")
    else:
        console.print("Findings:")
        for sev, n in _finding_counts(result).items():
            col = _severity_color(sev)
            console.print(f"  [{col}]{n} {sev}[/{col}]")
    console.print(f"Runtime: {_fmt_runtime(result.get('total_wall_seconds'))}")
    if result.get("is_error"):
        console.print(
            "[red]Warning: a stage reported an error; output may be partial.[/red]"
        )


def print_severity(result: dict, message: str | None = None) -> None:
    """Print a tool result's severity verdict with the canonical color."""
    sev = normalize_severity(result.get("severity"))
    color = _severity_color(sev)
    # Applicability guards carry their reason in `error`, not `explanation`;
    # falling back keeps a refusal from printing as a bare severity with no cause.
    text = message or result.get("explanation") or result.get("error") or ""
    console.print(f"[{color}]{sev.upper()}[/{color}]: {text}")


def bail_on_error(result: dict) -> None:
    """Exit with an error message if a tool returned a structured error."""
    if result.get("error"):
        console.print(f"[red]Error: {result['error']}[/red]")
        raise typer.Exit(1)


# Severities that constitute an accusation against a paper.
#
# THIS WAS THE HIGHER BAR, UNDER THIS COMMENT. It read
# `{"impossible", "highly_suspicious"}` -- the accusation-GRADE set -- while the
# comment describes the accuses-at-all meaning, and `warn_if_assumed` below acts
# on that meaning: it prints what was ASSUMED whenever an accusation rests on an
# unstated premise. So a `suspicious` verdict resting on an assumed data type
# printed no warning, on every CLI invocation without `--data-type`.
#
# Every other module in the codebase treats `suspicious` as accusing; the CLI
# disagreed with all of them, silently, under a comment agreeing with them.
from .tools.severity import ACCUSES_AT_ALL as ACCUSATORY


def warn_if_assumed(
    result: dict, data_type: str | None, *, scale: str | None = None, effective: str = "",
) -> None:
    """Print what was ASSUMED whenever an accusation rests on an unstated premise.

    Every consistency test needs to know what the numbers are, and a
    misspecified scale bound INVERTS a check rather than weakening it, so a
    verdict carries no weight until the premise is confirmed. (How much it
    inverts by is unmeasured; the specificity figures this line used to quote
    were prose nothing in the tree computed.) When a
    user does not pass --data-type, the tool falls back to the type it is FOR,
    which is exactly the case where a confident verdict is least trustworthy.
    """
    if result.get("severity") not in ACCUSATORY or data_type is not None:
        return
    assumed = effective or result.get("data_type") or result.get("canonical_data_type") or "the tool default"
    console.print(
        f"\n[yellow]Assumption warning:[/yellow] you did not pass [bold]--data-type[/bold], so this "
        f"ran as [bold]{assumed}[/bold] data"
        + (f" on a {scale} scale" if scale else "")
        + ".\n  If that is wrong, so is the verdict. Pass --data-type "
        "(integer|likert|count|binary|proportion|continuous) to make the premise explicit; "
        "GRIM-family checks then REFUSE on non-integer data instead of accusing it."
    )




def _versioned_review_dirname(model: str, config=None) -> str:
    """THE default review-directory name, everywhere: model + pipeline
    version, no date (Dan, 2026-08-22). The name says WHICH experiment the
    folder holds -- two reviews across a version boundary are not
    comparable -- while WHEN lives in run_meta's analysed_at, where a date
    belongs. `analyze` and `batch` both derive from this so the two entry
    points cannot drift apart again."""
    from metascience_agent.version import __version__ as _release
    model_slug = re.sub(r"[^A-Za-z0-9]+", "-", model).strip("-") or "model"
    # A PARTIAL PIPELINE NAMES ITSELF. Its folder must not look like the
    # paper's review: `forensic_review_tools_grim_opus_v1.74.0`, beside the
    # complete review's unchanged `forensic_review_opus_v1.74.0`.
    if config is not None and not config.complete_review:
        name_slug = re.sub(r"[^A-Za-z0-9]+", "-", config.name).strip("-") or "pipeline"
        return f"forensic_review_{name_slug}_{model_slug}_v{_release}"
    return f"forensic_review_{model_slug}_v{_release}"


def _analyze_out_dir(paper_path: Path, output, model: str, config=None):
    """The analyze command's output directory and its same-experiment twins.

    `same_experiment` holds every existing directory for the SAME model at
    the SAME version -- the exact name, plus any date-suffixed variant from
    the brief era when the name carried a date -- which is what the
    pre-spend prompt shows the operator."""
    if output:
        return Path(output), []
    dir_name = _versioned_review_dirname(model, config)
    if Path(paper_path).is_dir():
        out_dir = Path(paper_path) / dir_name
        prefix = ""
    else:
        # BESIDE THE FILE, not in the shell's current directory. The image
        # track already writes `panels/` and `figures/` next to the PDF, so a
        # cwd-relative review split one run across two folders (Dan,
        # 2026-10-05: a PDF in ~/Downloads/testpdf reviewed into ~/).
        paper_file = Path(paper_path)
        out_dir = paper_file.parent / f"{paper_file.stem}_{dir_name}"
        prefix = f"{paper_file.stem}_"
    parent = out_dir.parent
    same = sorted(parent.glob(f"{prefix}{dir_name}*"))
    return out_dir, same


# ---------------------------------------------------------------------------
# ONE LIST PARSER, NOT TWENTY. Twenty call sites each wrote
# `[float(x.strip()) for x in flag.split(",")]`, so any input the CLI did not
# expect raised an unhandled ValueError and printed a Rich TRACEBACK at the
# reader -- from the tool we hand people as "here is how to check this
# yourself".
#
# MEASURED 2026-09-01: `metascience summation --values '[31,31]' ...`, a
# command our own model wrote, died with
# `ValueError: could not convert string to float: '[31'`.
#
# Brackets are stripped because `[31,31]` and `31,31` are two SPELLINGS of one
# list -- the same repair-not-invention line the paper readers follow. What is
# NOT done here is guessing at a value: a token that is not a number raises
# `BadParameter`, naming the flag and the offending token.
# ---------------------------------------------------------------------------

def _parse_number_list(raw: str, flag: str, cast, kind: str) -> list:
    text = (raw or "").strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    if not text.strip():
        return []
    out = []
    for tok in text.split(","):
        tok = tok.strip().strip("'\"")
        try:
            out.append(cast(tok))
        except (TypeError, ValueError, InvalidOperation):
            raise typer.BadParameter(
                f"{flag} expects a comma-separated list of {kind}s "
                f"(e.g. {flag} 12.5,13.1); could not read {tok!r}")
    return out


def _floats(raw: str, flag: str) -> list[float]:
    return _parse_number_list(raw, flag, float, "number")


def _ints(raw: str, flag: str) -> list[int]:
    def whole_number(token: str) -> int:
        # A sample size or decimal precision must not be truncated or rounded
        # through float before the tool sees it. Integral decimal/scientific
        # spellings are fine; a fractional or nonfinite value is not.
        value = Decimal(token)
        if not value.is_finite() or value != value.to_integral_value():
            raise ValueError("expected a finite whole number")
        return int(value)

    return _parse_number_list(raw, flag, whole_number, "whole number")


@app.command()
def analyze(
    paper_path: Path = typer.Argument(..., help="Path to a paper directory, PDF, or markdown file"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory for the review files (default: inside a paper directory, or beside a paper file as <paper>_forensic_review_...)"),
    pipeline: Optional[str] = typer.Option(
        None, "--pipeline",
        help="Pipeline to run: a shipped name (`metascience pipeline list`) or a "
             "path to a pipeline YAML. It decides which modules run and the tools "
             "agent's toolset. Default: the complete review (`full`)."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    two_stage: bool = typer.Option(True, "--two-stage", help="Deprecated: the two-analyst review is the only pipeline now; the flag is kept so existing scripts keep working. Its `--single-stage` counterpart was removed in v1.19.0 along with the mode."),
    parallel: bool = typer.Option(False, "--parallel", help="Deprecated: this is the default pipeline now; the flag is kept so existing scripts keep working."),
    budget_usd: Optional[float] = typer.Option(None, "--budget-usd", help="Total budget cap for the analysis"),
    timeout: Optional[int] = typer.Option(None, "--timeout", help="Per-stage timeout in seconds"),
    backend: Optional[str] = typer.Option(
        None, "--backend",
        help="LLM backend, REQUIRED when a model is called: claude, grok, codex, openrouter (our API loop; needs OPENROUTER_API_KEY), or antigravity (Google's agy CLI; `metascience models --backend antigravity` lists its models). A pipeline file's backend also counts; METASCIENCE_LLM_CLI does not."),
    model: Optional[str] = typer.Option(
        None, "--model",
        help="Model alias. Default follows --backend (opus for claude, grok-4.6 for grok, gpt-5.6-sol for codex, anthropic/claude-sonnet-5.5 for openrouter, gemini-4-argon for antigravity; see `metascience models`)."),
    effort: Optional[str] = typer.Option(
        None, "--effort",
        help="Reasoning effort: low|medium|high|xhigh|max "
             f"(default: the pipeline's, else {DEFAULT_EFFORT})"),
    # OFF BY DEFAULT, per Greg 2026-08-13. Measured over every archived run
    # before wiring: the report-stage condition fired on 0 of 47 measurable
    # runs, so it does not kill healthy work -- but a condition that has never
    # fired also has an unmeasured true-positive rate, which is why `warn` is
    # offered and is the setting to use first on real papers.
    tripwire: str = typer.Option(
        "off", "--tripwire",
        help="off|warn|kill -- end the run when information KNOWN to exist did "
             "not arrive (a declared supplement with no cells, tables that "
             "never reach the manifest, XML that yields no text)"),
    pdf: bool = typer.Option(True, "--pdf/--no-pdf", help="Also render report.md to report.pdf"),
    # ON BY DEFAULT, because the viewer is the deliverable. `report.md` is the
    # machine's notes; the bundle is the document a person reads. Behind a
    # second verb, the most useful artefact of a ten-dollar run existed only if
    # somebody remembered to ask for it, and the standing instruction to build
    # one every time is itself evidence that nobody reliably did.
    bundle: bool = typer.Option(
        True, "--bundle/--no-bundle",
        help="Build the offline HTML viewer when the review finishes (default on)"),
    # OFF BY DECISION, NOT BY OVERSIGHT (Greg, 2026-08-10).
    #
    # An audit flagged this default as a self-inflicted limitation: four corpus
    # papers ship a PDF whose only confidence intervals live in figures, and the
    # reviews say so in their own limitations. The flag stays OFF anyway,
    # because reading a value off a plot is still buggy, and a WRONG number
    # extracted from a chart is worse than an acknowledged gap -- it enters the
    # checks with figure-pixel provenance and can produce an accusation from an
    # artefact of our own reader.
    #
    # Turn this on when the extraction is good enough to defend, not before.
    # Until then "figures were not read" is an honest limitation and the correct
    # thing for a review to say.
    figures: bool = typer.Option(False, "--figures/--no-figures", help="Enable the figure pass (default OFF BY DECISION: figure-value extraction is not yet reliable, and a wrong number read off a plot is worse than a stated gap)"),
    # A SEPARATE flag from --figures on purpose: --figures governs the LLM
    # reading VALUES off plots (off because value-reading is unreliable);
    # this runs deterministic pixel/byte comparison in an isolated child
    # process, which has neither that failure mode nor that rationale.
    # Default off until the calibration sweep's release criteria pass
    # (see tools/image_analysis.py docstring).
    image_forensics: bool = typer.Option(
        True, "--image-forensics/--no-image-forensics",
        help="Run independent image detection and AI screening alongside both "
             "analysts (default on). Only screened findings reach adjudication."),
    segment_montages: bool = typer.Option(
        False, "--segment-montages/--no-segment-montages",
        help="With --image-forensics: split multi-panel figures so a "
             "duplication BETWEEN panels of one composite is visible. "
             "Default off on this path until the false-positive side is "
             "gated (measured 2026-09-02: transformed_match fires on 23.8% "
             "of Masliah papers under segmentation, above the 20% alarm); "
             "`metascience image-sweep` runs it on by default."),
    reassemble_tiles: bool = typer.Option(
        False, "--reassemble-tiles/--no-reassemble-tiles",
        help="With --image-forensics: paste each strip-sliced photograph "
             "back into one panel (perceptual tiers only) instead of "
             "withholding its strips. Opt-in; measured 2026-09-11 on ~10 "
             "of 1,086 corpus PDFs (Springer 1998, Wiley, Elsevier 2019, "
             "MDPI 2023-25)."),
    # Default ON: the text track is free (no API
    # spend), fast, its findings arrive quarantined, and a missed mill paper
    # is the costlier error.
    text_forensics: bool = typer.Option(
        True, "--text-forensics/--no-text-forensics",
        help="Run the deterministic tortured-phrases track alongside the "
             "sweep (QUARANTINED: its findings arrive as unvalidated "
             "signals, never findings of record). Default on -- free and "
             "local."),
    supplement: Optional[List[Path]] = typer.Option(
        None, "--supplement", help="Supplementary file(s) to include. Repeatable."),
    ok_if_supplementary_missing: bool = typer.Option(
        False, "--ok-if-supplementary-missing",
        help="Deprecated, no effect: a paper citing supplementary material that is "
             "not supplied is now analysed with a warning and a recorded limitation."),
    artefact: Optional[List[Path]] = typer.Option(
        None, "--artefact",
        help="Unsupported by the parallel pipeline. Use --supplement for "
             "readable supplementary files; repositories and archives need "
             "a separate review."),
    ignore_weekly_limit: bool = typer.Option(
        False, "--ignore-weekly-limit",
        help="Do not stop when the Claude Code weekly /usage gauge is at/over "
             "threshold. Session-window pausing still runs. Use this when extra "
             "usage credits will cover the spend -- the weekly % does not include "
             "them."),
    no_usage_guard: bool = typer.Option(
        False, "--no-usage-guard",
        help="Disable the Claude Code usage guard entirely (session pause and "
             "weekly stop). Prefer --ignore-weekly-limit if you only need to "
             "override a spent weekly quota."),
):
    """
    Analyze a scientific paper for statistical inconsistencies.

    Uses the `claude` CLI to intelligently apply forensic metascience
    techniques and writes report.md / findings.json / run_meta.json.
    """
    from .usage_guard import WeeklyLimitReached, apply_cli_overrides

    apply_cli_overrides(
        no_usage_guard=no_usage_guard,
        ignore_weekly_limit=ignore_weekly_limit,
    )

    if not paper_path.exists():
        console.print(f"[red]Error: Path not found: {paper_path}[/red]")
        raise typer.Exit(1)

    # THE PIPELINE, resolved before anything is read or spent. A pipeline
    # decides the modules; the per-module flags are the pre-pipeline spelling of
    # the same decisions, so combining them is refused rather than merged.
    config = None
    if pipeline is not None:
        from . import pipeline_config as _pc
        try:
            config = _pc.load(pipeline)
        except _pc.PipelineConfigError as exc:
            console.print(f"[red]{escape(str(exc))}[/red]")
            raise typer.Exit(2)
        clashing = [flag for flag, value, default in (
            ("--figures", figures, False),
            ("--no-image-forensics", image_forensics, True),
            ("--no-text-forensics", text_forensics, True),
            ("--segment-montages", segment_montages, False),
            ("--reassemble-tiles", reassemble_tiles, False)) if value != default]
        if clashing:
            console.print(
                f"[red]{', '.join(clashing)} cannot be combined with --pipeline: "
                "the pipeline file decides which modules run and their options. "
                "Edit (or copy) the pipeline file instead.[/red]")
            raise typer.Exit(2)
        figures = config.figures
        image_forensics = config.has("image_analysis")
        text_forensics = config.has("text_forensics")
        # Precedence: CLI flag > pipeline file > environment > default.
        backend, model, effort = _pc.resolve_backend_settings(
            config, backend, model, effort)
        console.print(f"[cyan]Pipeline:[/cyan] {escape(config.describe())}")
    _require_backend(backend, config)
    effort = effort or DEFAULT_EFFORT

    # The old option only printed 'Including ...' and never delivered these
    # paths to either analyst. Refuse before extraction or spend rather than
    # produce a review that appears to have considered the supplied evidence.
    if artefact:
        console.print(
            "[red]--artefact is not supported by the parallel pipeline. "
            "Use --supplement for readable supplementary files. Repositories "
            "and archives require a separate review.[/red]")
        raise typer.Exit(2)

    # The supplement gate, BEFORE anything is spent. Refusing by default is the
    # point: this tool reasons about what a paper does and does not report, so a
    # statistic living in an absent supplement is indistinguishable from one the
    # authors never reported. Running anyway manufactures findings that land as
    # accusations against the authors for the operator's omission.
    paper_dir = paper_path if paper_path.is_dir() else paper_path.parent
    for extra in (supplement or []):
        if not extra.exists():
            console.print(f"[red]Supplement not found: {extra}[/red]")
            raise typer.Exit(1)

    # EXTRACTION FIRST, BEFORE THE GATE BELOW READS THE PAPER.
    #
    # Every read path is now docling-and-cache-only, so an unextracted PDF
    # yields empty text with a reason. The supplement gate consumes that text
    # through `paper_text`, and empty text there means `text_available: False`
    # -> `missing: None` -> "Refusing to analyse a paper whose text could not be
    # read." That refusal is TRUE OF US AND FALSE OF THE PAPER: the PDF has a
    # perfectly good text layer, we simply had not run the extractor yet. Filled
    # first, the gate asks its real question against the real text.
    #
    # It also means the cache-only refusal cannot surface mid-run, where it
    # would cost a paid sweep. Idempotent -- an already-extracted paper costs a
    # content hash and a JSON read per file, and never loads the layout model.
    # MEASURED on this repository's corpora over the WSL/Drive mount, median of
    # 5: `10.3349--ymj.2009.50.1.55`, 1 PDF / 0.3 MB, 0.31 s;
    # `10.1001--jamanetworkopen.2023.37679`, 3 PDFs / 1.8 MB, 0.36 s. Extracting
    # those same files COLD is 24-38 s each, and 140 s for the ymj scan, which
    # falls through to OCR.
    from .agent import ensure_paper_extracted

    _extraction = ensure_paper_extracted(
        str(paper_path), extra=list(supplement or []),
        on_event=lambda msg: console.print(f"[dim]{escape(msg)}[/dim]"))
    if _extraction["failed"]:
        # Warned, not blocked, for the same reason the glyph scan below is: one
        # unreadable supplement does not manufacture findings wholesale, and
        # refusing the whole paper over it would discard the parts we CAN read.
        # The same note travels into the report's limitations.
        console.print(f"\n[red]Unreadable PDF(s).[/red] {_extraction['note']}")

    supplement_gate = _supplement_gate(paper_dir, supplement, ok_if_supplementary_missing)
    if not supplement_gate["proceed"]:
        console.print(f"\n[red]{supplement_gate['message']}[/red]")
        raise typer.Exit(2)
    if supplement_gate["message"]:
        console.print(f"\n[yellow]{supplement_gate['message']}[/yellow]")

    # THE TRIPWIRE, placed here deliberately: after extraction has run and the
    # supplement gate has passed, and BEFORE a single token is spent. Firing it
    # after stage 2 would waste exactly the money it exists to protect.
    from . import tripwire as _tw

    _trips = _tw.check_preflight(paper_dir)
    try:
        _tripwire_report = _tw.enforce(_trips, mode=tripwire)
    except _tw.TripwireError as exc:
        console.print(f"\n[red]{escape(str(exc))}[/red]")
        raise typer.Exit(2)
    if _tripwire_report["tripped"]:
        # Reached only in `off` or `warn`. Printed loudly either way: the point
        # of the recording mode is that the operator SEES the condition on real
        # runs before trusting it to kill one.
        console.print(f"\n[yellow]TRIPWIRE ({tripwire}): "
                      f"{escape(_tripwire_report['note'])}[/yellow]")

    # Character-level corruption in the extracted text. Warned, not blocked:
    # unlike a missing supplement this does not manufacture findings wholesale,
    # but a lost minus sign produces a confident finding about a number the
    # paper never printed, so the operator has to see it before believing the
    # output.
    from .glyphs import scan_paper as _glyph_scan

    # What the paper says it shares. Reported, never fetched: downloading what a
    # paper links to has its own consequences and is the operator's call.
    from .artefacts import find_in_paper as _find_artefacts

    artefact_report = _find_artefacts(paper_dir)
    if artefact_report["n_repositories"] or artefact_report["n_registrations"]:
        console.print(f"\n[cyan]Linked artefacts.[/cyan] {artefact_report['note']}")
        for u in artefact_report["all"][:8]:
            console.print(f"  {u}")

    glyph_report = _glyph_scan(paper_dir)
    if glyph_report["quarantine"]:
        console.print(f"\n[red]Corrupt extracted text.[/red] {glyph_report['note']}")
        for h in glyph_report["patterns"]:
            if h["corrupts_digits"]:
                console.print(f"  [red]{h['pattern']}[/red] x{h['count']}: "
                              f"{h['examples'][0][:70]}")
        console.print("  [dim]Findings from this paper need checking against the "
                      "PDF by eye.[/dim]")

    console.print(Panel(f"Analyzing: [bold]{paper_path}[/bold]", title="Forensic Metascience Analysis"))

    # The figure pass is OFF by default, deliberately. Figure extraction that
    # nobody has checked introduces WRONG-OBJECT errors -- a caption paired with
    # the panel above rather than below, a three-panel figure treated as one --
    # and those are unbounded, unlike the measurement error which is at least
    # computable. An unverified figure pass can make the report worse.
    if figures:
        console.print(
            "\n[yellow]Figure pass enabled.[/yellow] Strongly consider annotating first:\n"
            "  [bold]metascience extract-figures <paper.pdf>[/bold]  then open "
            "figure-extractor.html and correct the bounds, split multi-panel figures\n"
            "  into subfigures, and fix any caption paired with the wrong panel.\n"
            "  Verification removes wrong-object errors. It does NOT make measured values\n"
            "  usable by GRIM/GRIMMER/SPRITE -- a confirmed crop is still not a number the\n"
            "  authors printed -- but it is what makes a coverage claim safe to state.\n"
        )

    from .agent import analyze_paper
    from .llm_backend import BudgetUnsupported, resolve_backend

    be = resolve_backend(backend)
    model = model or be.default_model
    if budget_usd is not None and not be.supports_budget:
        console.print(
            f"[red]{be.name} has no spend cap; re-run without --budget-usd "
            f"or use --backend claude.[/red]")
        raise typer.Exit(2)

    # `two_stage` and `parallel` are both deprecated no-ops now: the parallel
    # pipeline is the only non-legacy body, so neither flag can select
    # anything else. They stay accepted so existing scripts keep working.
    mode = "parallel"

    # OUTPUT DIRECTORY, decided BEFORE any spend. A same-model,
    # same-version output already on disk means a re-run duplicates an
    # existing experiment -- warn in yellow and ask BEFORE spending.
    # Non-interactive callers (the webapp's spawn, scripts) cannot answer a
    # prompt, so they get the warning and proceed.
    out_dir, same_experiment = _analyze_out_dir(paper_path, output, model, config)
    if same_experiment:
        console.print("[yellow]Output for this code version and AI already "
                      "exists:[/yellow]")
        for d in same_experiment:
            console.print(f"  [yellow]{d.name}[/yellow]")
        import sys as _sys
        if _sys.stdin.isatty():
            if not typer.confirm("Proceed with a new run anyway?"):
                raise typer.Exit(0)
        else:
            console.print("[yellow]non-interactive session; proceeding[/yellow]")

    # A preview-stub main PDF is a fact worth knowing BEFORE the spend, not
    # after: the run proceeds (the XML carries the text), but figure checks
    # will be blind and the reviewer may prefer to re-fetch first. Warning
    # only, no prompt -- the run is not wrong, just narrower than it looks.
    try:
        from .webapp_index import probe_main_pdf_stub
        _stub = probe_main_pdf_stub(
            paper_path if paper_path.is_dir() else paper_path.parent)
    except Exception:  # noqa: BLE001 -- a probe must never block a run
        _stub = None
    if _stub and _stub.get("pdf_suspect_stub"):
        console.print(
            f"[yellow]The main PDF here is only "
            f"{_stub.get('main_pdf_pages')} page(s) beside a full-text XML — "
            "it looks like a publisher preview stub. Text comes from the "
            "XML, but figure-dependent checks will be blind; consider "
            "re-fetching the full PDF first.[/yellow]")

    # ONE LINE PER CONCURRENT CHANNEL, keyed by the stage label every snapshot
    # already carries (`_emit_progress`, agent.py). The single cell this
    # replaces is what made the two parallel analysts overwrite each other into
    # one line flickering between them.
    # `live=None` auto-detects: a TTY gets the stacked Rich block, a redirected
    # log gets one plain line per 15 s instead of a screenful of carriage
    # returns. In verbose mode the monitor is never started or updated.
    monitor = LiveBatchStatus(live=None, transient=False, show_key=False)

    def _on_progress(snapshot: dict) -> None:
        monitor.update(str(snapshot.get("stage") or "analysis"), snapshot)

    async def run_analysis(live: bool = False):
        # No redraw loop here. Rich's Live auto-refreshes 4x/s and the widget
        # recomputes each slot's elapsed per frame, so the clocks keep ticking
        # through a long tool call or a slow model turn -- which is exactly
        # when the operator is wondering whether the run has hung.
        try:
            return await analyze_paper(
                str(paper_path),
                verbose=verbose,
                timeout=timeout,
                mode=mode,
                budget_usd=budget_usd,
                model=model,
                effort=effort,
                figures=figures,
                image_forensics=image_forensics,
                text_forensics=text_forensics,
                image_segment_montages=segment_montages,
                image_reassemble_tiles=reassemble_tiles,
                on_progress=_on_progress if live else None,
                # Not just for the gate. Without this the flag satisfied the
                # refusal and the named file was never opened by anything.
                extra_supplements=supplement,
                backend=be.name,
                pipeline=config,
            )
        except (Exception, KeyboardInterrupt, SystemExit) as exc:
            # The spend ledger is a ContextVar the pipeline binds INSIDE
            # this task; the crash handler below runs back in the sync
            # frame, outside that context. Attach the number to the
            # exception so it rides the unwind across asyncio.run -- the
            # crash record's whole purpose is surviving exactly this.
            # (A tuple, not the broadest base class: everything is
            # RE-RAISED either way, but the WeeklyLimitReached-before-
            # crash-record ordering pin keys on the crash handler's own
            # except clause being the first of its spelling in this file.)
            from metascience_agent.agent import spend_so_far as _ssf
            try:
                exc._metascience_spend = _ssf()
            # A failed attach is deliberately silent: the crash handler
            # below falls back to its own spend_so_far() read, so nothing
            # is lost -- and raising here would mask the real failure.
            except Exception:  # noqa: BLE001
                pass
            raise

    # A CRASH MUST STILL SAY WHAT IT COST. run_meta.json is written at the end
    # of a successful run, so an exception before that point left real money
    # spent with nothing to show it -- measured on a paper that died at Popen
    # after a 22-minute sweep. The spend ledger survives the unwind, so the
    # crash record carries the number and the traceback.
    from metascience_agent.agent import reset_spend, spend_so_far

    reset_spend()
    try:
        if verbose:
            # Stream output directly; a live display would fight it.
            result = asyncio.run(run_analysis())
        else:
            # Slots are seeded in DISPLAY order: the two analysts race under
            # `asyncio.gather`, so letting first-snapshot-wins decide would
            # shuffle the lines between runs. Only the parallel pipeline has
            # these stages; the legacy modes emit `sweep`/`editorial` and get
            # their slot on arrival, as before.
            if mode == "parallel":
                if config is None or config.has("tools_agent"):
                    monitor.begin("tool_agent")
                if config is None or config.has("scientific_proofreading_agent"):
                    monitor.begin("science_agent")
                if image_forensics:
                    monitor.begin("image_track")
                if text_forensics:
                    monitor.begin("text_track")
            # The monitor stays INSIDE the crash wrapper: a run that dies
            # mid-stage must still write what it spent, and that is the case
            # where the operator most wants both numbers.
            with monitor:
                result = asyncio.run(run_analysis(live=True))
    except BudgetUnsupported as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2)
    except WeeklyLimitReached as exc:
        # Not a crash: nothing was spent yet (the guard runs before spawn).
        # Writing run_crash.json would file a quota stop as an analysis failure.
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(3)
    except BaseException as exc:  # noqa: BLE001 -- re-raised below, incl. KeyboardInterrupt
        # Prefer the spend the exception carried out of the pipeline's own
        # context (attached in run_analysis); the sync-frame ledger read is
        # the fallback for failures raised outside the run itself.
        spend = getattr(exc, "_metascience_spend", None) or spend_so_far()
        crash_path = out_dir / "run_crash.json"
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            crash_path.write_text(json.dumps({
                "crashed": True,
                "paper": str(paper_path),
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                **spend,
                "note": (
                    "This run did not finish, so there is no report. The cost "
                    "below is what the stages that DID complete already charged; "
                    "a stage interrupted part-way is not counted, so treat it as "
                    "a floor."
                ),
            }, indent=2))
            console.print(
                f"[red]Analysis crashed after ${spend['total_cost_usd']:.2f} of "
                f"completed stages.[/red] Record: {crash_path}")
        except Exception:  # noqa: BLE001 -- never mask the original failure
            console.print(
                f"[red]Analysis crashed after ${spend['total_cost_usd']:.2f}; "
                "the crash record could not be written.[/red]")
        raise

    # out_dir was decided (and collision-checked) before the run started.
    #
    # `analyze_paper` has returned only `mode == "parallel"` results since
    # v1.27.0 deleted the serial writer. Until 2026-09-05 the `else` branch here
    # still called that writer, imported lazily by name at the top of this
    # function -- so `metascience analyze` raised ImportError on EVERY
    # invocation, before any spend, and the suite stayed green because nothing
    # in it runs this verb past its imports. tests/test_lazy_imports_resolve.py
    # now checks every such import statically.
    if result.get("mode") != "parallel":
        raise RuntimeError(
            f"no writer for mode {result.get('mode')!r}: the serial writer was "
            "removed in v1.27.0 and `analyze_paper` produces only 'parallel'")
    from metascience_agent.parallel import write_parallel_outputs
    write_parallel_outputs(result, out_dir, render_pdf=pdf)

    # THE VIEWER IS THE DELIVERABLE, so building it is not a second command.
    #
    # `report.md` is the machine's notes; the bundle is the document a person
    # actually reads -- the paper beside the findings, every tool call with the
    # passage it read, the refusal list with whose limit each one was. Leaving
    # it behind `metascience bundle` meant a run could finish, cost ten dollars,
    # and hand back a directory whose most useful artefact did not exist unless
    # somebody remembered a second verb. Nobody reliably did.
    #
    # FAILURE HERE IS RECORDED, NEVER SWALLOWED, and never fatal: the analysis
    # is already paid for and already written to disk. A bundle that cannot be
    # built says so and names the command to retry, which is strictly more than
    # the silence this replaces. Success is silent: the end-of-run print is
    # verdict, finding counts, and runtime, not paths.
    if bundle:
        try:
            from .bundle import build_bundle
            build_bundle(out_dir, None, paper_path)
        except Exception as exc:  # noqa: BLE001 -- the analysis is already safe
            console.print(
                f"[yellow]Viewer bundle failed: {exc}[/yellow]\n"
                f"[yellow]The review itself is complete and written to "
                f"{out_dir}/. Retry the viewer alone with:[/yellow]\n"
                f"[dim]  metascience bundle {out_dir}[/dim]")

    _print_analyze_summary(result)


@app.command()
def extract(
    pdf_path: Path = typer.Argument(..., help="Path to PDF file"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
):
    """Extract text and tables from a PDF for inspection."""
    if not pdf_path.exists():
        console.print(f"[red]Error: File not found: {pdf_path}[/red]")
        raise typer.Exit(1)

    with console.status("Extracting..."):
        result = extract_text_with_tables(pdf_path)

    if output:
        output.write_text(json.dumps(result, indent=2))
        console.print(f"[green]Extracted to: {output}[/green]")
    else:
        console.print(f"[bold]Pages:[/bold] {result['num_pages']}")
        console.print(f"[bold]Tables:[/bold] {len(result['tables'])}")
        console.print("\n[bold]Text preview:[/bold]")
        console.print(result["text"][:2000] + "..." if len(result["text"]) > 2000 else result["text"])


@app.command("get-table")
def get_table_cmd(
    xml_path: Path = typer.Argument(..., help="Path to publisher XML full text"),
    table_num: int = typer.Argument(..., help="Table number, as listed by extract-xml"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
):
    """One table from an XML, with its label, caption, footnotes and cells."""
    from .extraction.jats import get_table

    if not xml_path.exists():
        console.print(f"[red]Error: File not found: {xml_path}[/red]")
        raise typer.Exit(1)

    result = get_table(xml_path, table_num)
    if not result.get("found"):
        console.print(f"[red]{result.get('error', 'not found')}[/red]")
        raise typer.Exit(1)

    if output:
        output.write_text(json.dumps(result, indent=2))
        console.print(f"[green]Written to: {output}[/green]")
        return

    console.print(f"[bold]{result['label'] or f'Table {table_num}'}[/bold] "
                  f"-- {result['n_rows']} rows x {result['width']} cols")
    if result.get("caption"):
        console.print(f"[dim]{result['caption']}[/dim]")
    t = Table(show_header=True)
    for h in (result.get("headers") or [])[:8]:
        t.add_column(str(h)[:24])
    for row in (result.get("data") or [])[1:21]:
        t.add_row(*[str(c)[:24] for c in row[:8]])
    console.print(t)
    for fn in result.get("footnotes") or []:
        console.print(f"[dim]note: {str(fn.get('text', fn))[:200]}[/dim]")


@app.command("extract-xml")
def extract_xml_cmd(
    xml_path: Path = typer.Argument(..., help="Path to publisher XML full text"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
    tables_only: bool = typer.Option(False, "--tables-only", help="Skip the text preview"),
    full_tables: bool = typer.Option(
        False, "--full-tables",
        help="Include every table grid. Default is an index; use get-table for cells."),
):
    """Extract text and a TABLE INDEX from a JATS / PMC / Elsevier XML full text."""
    from .extraction.jats import extract_xml_text_with_tables

    if not xml_path.exists():
        console.print(f"[red]Error: File not found: {xml_path}[/red]")
        raise typer.Exit(1)

    with console.status("Extracting..."):
        result = extract_xml_text_with_tables(
            xml_path, tables="full" if full_tables else "index")

    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(1)

    if output:
        output.write_text(json.dumps(result, indent=2))
        console.print(f"[green]Extracted to: {output}[/green]")
        return

    console.print(f"[bold]Format:[/bold] {result['source_format']}")
    console.print(f"[bold]Sections:[/bold] {result['num_pages']}")
    console.print(f"[bold]Tables:[/bold] {result['n_tables']}")
    for table in result["tables"]:
        name = table["label"] or f"Table {table['table_num']}"
        if table["image_only"]:
            console.print(
                f"  [red]{name}: image only, no cells "
                f"(get it from the PDF)[/red]"
            )
            continue
        line = (
            f"  {name}: {table['n_rows']}x{table['width']}, "
            f"{table['n_header_rows']} header row(s), "
            f"{len(table['cells'])} cells"
        )
        if table["alignment_uncertain"]:
            console.print(f"[red]{line}  RAGGED — labels may be shifted[/red]")
        else:
            console.print(line)
    for warning in result["warnings"]:
        console.print(f"[yellow]! {warning}[/yellow]")
    if result["normalizations"]:
        console.print(f"[dim]normalizations: {result['normalizations']}[/dim]")

    if not tables_only:
        text = result["text"]
        console.print("\n[bold]Text preview:[/bold]")
        console.print(text[:2000] + "..." if len(text) > 2000 else text)


@app.command("extract-html")
def extract_html_cmd(
    html_path: Path = typer.Argument(..., help="Path to fetched publisher HTML full text"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
    tables_only: bool = typer.Option(False, "--tables-only", help="Skip the text preview"),
):
    """Extract text and tables from fetched publisher HTML full text (XML-not-available fallback)."""
    from .extraction.html import extract_html_text_with_tables

    if not html_path.exists():
        console.print(f"[red]Error: File not found: {html_path}[/red]")
        raise typer.Exit(1)

    with console.status("Extracting..."):
        result = extract_html_text_with_tables(html_path)

    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
        console.print(
            "[yellow]This page failed the landing-page/decoy check -- it is not "
            "the article. Record it in `unchecked` and fall back to extract-pdf "
            "or the paper's body.md.[/yellow]"
        )
        raise typer.Exit(1)

    if output:
        output.write_text(json.dumps(result, indent=2))
        console.print(f"[green]Extracted to: {output}[/green]")
        return

    console.print(f"[bold]Format:[/bold] {result['source_format']}")
    console.print(f"[bold]Sections:[/bold] {result['num_pages']}")
    console.print(f"[bold]Tables:[/bold] {result['n_tables']}")
    for table in result["tables"]:
        name = table["label"] or f"Table {table['table_num']}"
        if table["image_only"]:
            console.print(
                f"  [red]{name}: image only, no cells "
                f"(get it from the PDF)[/red]"
            )
            continue
        line = (
            f"  {name}: {table['n_rows']}x{table['width']}, "
            f"{table['n_header_rows']} header row(s), "
            f"{len(table['cells'])} cells"
        )
        if table["alignment_uncertain"]:
            console.print(f"[red]{line}  RAGGED — labels may be shifted[/red]")
        else:
            console.print(line)
    for warning in result["warnings"]:
        console.print(f"[yellow]! {warning}[/yellow]")
    if result["normalizations"]:
        console.print(f"[dim]normalizations: {result['normalizations']}[/dim]")

    if not tables_only:
        text = result["text"]
        console.print("\n[bold]Text preview:[/bold]")
        console.print(text[:2000] + "..." if len(text) > 2000 else text)


@app.command("stat-to-p")
def stat_to_p_cmd(
    statistic: float = typer.Argument(..., help="The printed test statistic"),
    kind: str = typer.Argument(..., help="t | chi2 | z | r | f"),
    df: Optional[int] = typer.Option(None, "--df", help="Degrees of freedom (t, chi2; numerator df for f)"),
    df2: Optional[int] = typer.Option(None, "--df2", help="Denominator df (f only)"),
    n: Optional[int] = typer.Option(None, "--n", help="Sample size (r only)"),
    reported_p: Optional[float] = typer.Option(None, "--reported-p", help="The p the paper printed"),
    decimals_stat: Optional[int] = typer.Option(None, "--decimals-stat", help="Printed decimals of the statistic"),
    decimals_p: Optional[int] = typer.Option(None, "--decimals-p", help="Printed decimals of the reported p"),
    tails: int = typer.Option(2, "--tails", help="2 or 1; ignored for chi2 and f"),
    df_min: Optional[float] = typer.Option(None, "--df-min", help="Lowest admissible df when --df is not printed (t, chi2; default 1)"),
    df_max: Optional[float] = typer.Option(None, "--df-max", help="Highest admissible df when --df is not printed (default unbounded)"),
):
    """Recompute a p-value from one printed test statistic (t, chi2, z, r, F).

    Without --df, a t or chi2 is bounded over every admissible df."""
    from .tools.stat_to_p import recalc_stat_to_p

    r = recalc_stat_to_p(statistic=statistic, kind=kind, df=df, df2=df2, n=n,
                         reported_p=reported_p, decimals_stat=decimals_stat,
                         decimals_p=decimals_p, tails=tails,
                         df_min=df_min, df_max=df_max)
    console.print(f"[{_severity_color(r['severity'])}]{r['severity']}[/]  "
                  f"{r.get('methodology') or r.get('error','')}")
    for key in ("explanation", "alternative_reading", "tails_note", "df_note"):
        if r.get(key):
            console.print(f"[dim]{r[key]}[/dim]")


@app.command("check-bounds")
def check_bounds_cmd(
    value: float = typer.Argument(..., help="The value as extracted, e.g. 11.3"),
    measure: str = typer.Argument(..., help="What it is meant to be: correlation, "
        "p_value, percentage, proportion, r_squared, kappa, icc, cronbach_alpha, "
        "auc, sd, se, variance, chi_squared, f_statistic, n"),
    verified: bool = typer.Option(False, "--verified",
        help="Set ONLY after re-reading the value in the paper itself and "
             "confirming both the digits and the column."),
):
    """Is a value inside the range its measure logically permits?

    An out-of-bounds value indicts OUR extraction before it indicts the paper:
    a correlation of 11.3 is not an error that survives to publication in an
    honest paper or a fabricated one, so the likeliest author of it is whoever
    read the page. Reports `extraction_suspect` and names the decimal slip that
    would explain it; `--verified` lifts that to `impossible`.
    """
    from .tools.bounds import check_statistic_bounds

    r = check_statistic_bounds(value=value, measure=measure,
                               extraction_verified=verified)
    console.print(f"[{_severity_color(r['severity'])}]{r['severity']}[/]  "
                  f"{measure} = {value}")
    for key in ("explanation", "error"):
        if r.get(key):
            console.print(f"[dim]{r[key]}[/dim]")
    for alt in (r.get("rescalings_that_would_fit") or []):
        console.print(f"  would fit as [bold]{alt['reading']}[/bold] "
                      f"({alt['slip']})")


@app.command("check-count-percent")
def check_count_percent_cmd(
    count: int = typer.Argument(..., help="The numerator the paper printed, e.g. 142"),
    percentage: float = typer.Argument(..., help="The percentage the paper printed, e.g. 73.0"),
    n: int = typer.Argument(..., help="The denominator this percentage is believed to be over"),
    decimals: Optional[int] = typer.Option(None, "--decimals",
        help="Printed decimals of the percentage (`73.0` is 1). REQUIRED for a verdict."),
):
    """Check a printed count against its printed percentage.

    Stronger than GRIM wherever the count is printed: GRIM asks whether the
    percentage is attainable for SOME integer numerator, this asks whether it
    matches THE numerator the paper printed.
    """
    from .tools.count_percent import check_count_percent

    r = check_count_percent(count=count, percentage=percentage, n=n, decimals=decimals)
    console.print(f"[{_severity_color(r['severity'])}]{r['severity']}[/]  "
                  f"{count}/{n} = {r.get('computed_percentage')}  vs printed {percentage}")
    for key in ("explanation", "error", "alternative_reading"):
        if r.get(key):
            console.print(f"[dim]{r[key]}[/dim]")
    if r.get("implied_denominator"):
        console.print(f"implied denominator: [bold]{r['implied_denominator']}[/bold]")


@app.command("get-supplement-table")
def get_supplement_table_cmd(
    path: Path = typer.Argument(..., help="Supplementary .docx/.xlsx/.csv file"),
    table: str = typer.Argument(..., help="Sheet NUMBER (as the index prints it) or sheet NAME"),
    first_row: Optional[int] = typer.Option(None, "--first-row",
        help="1-based, inclusive, over the sheet's DATA rows. The header is always returned."),
    last_row: Optional[int] = typer.Option(None, "--last-row", help="1-based, inclusive"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
):
    """Fetch ONE sheet of a supplement, optionally windowed by row.

    The counterpart to `extract-supplement`, which returns an INDEX for any
    supplement too large to hand back whole. Every spreadsheet supplement in
    the working corpus is too large: they serialise to between 0.5M and 1.9M
    characters. Without this, the honest answer was to refuse them.
    """
    from .extraction.supplements_read import get_supplement_table

    if not path.exists():
        console.print(f"[red]Error: File not found: {path}[/red]")
        raise typer.Exit(1)
    result = get_supplement_table(path, table, first_row=first_row, last_row=last_row)
    if result.get("error"):
        console.print(f"[yellow]{result['error']}[/yellow]")
        for t in result.get("available") or []:
            console.print(f"  [dim]{t['table_num']}: {t['label']}[/dim]")
        raise typer.Exit(1)
    if output:
        output.write_text(json.dumps(result, indent=2))
        console.print(f"[green]Wrote: {output}[/green]")
        return
    w = result.get("row_window") or {}
    console.print(f"[bold]{result.get('label')}[/bold]  "
                  f"rows {w.get('first_row')}-{w.get('last_row')} of {w.get('n_rows_total')}, "
                  f"{result.get('width')} columns, {len(result.get('cells') or [])} cells")
    if result.get("window_note"):
        console.print(f"[dim]{result['window_note']}[/dim]")
    console.print(json.dumps(result, indent=2)[:4000])


@app.command("handoff-audit")
def handoff_audit_cmd(
    paper_dir: Path = typer.Argument(..., help="The paper's directory"),
    review_dir: Optional[Path] = typer.Option(
        None, "--review", "-r",
        help="An archived run, to check the model-dependent hand-offs too"),
):
    """Does every stage hand its work on, and does the next stage read it?

    The house failure is a producer that works and nothing downstream that
    looks -- `grace.py` with 12 tests and no callers, `completeness` written
    into every run and rendered nowhere. Testing each part in isolation cannot
    catch it, because every one of those parts passed its own tests.

    Runs offline and costs nothing, so it can gate a paid run.
    """
    from .handoff import audit as _audit

    if not paper_dir.is_dir():
        console.print(f"[red]Not a directory: {paper_dir}[/red]")
        raise typer.Exit(1)

    r = _audit(paper_dir, review_dir)
    for row in r["rows"]:
        mark = {True: "[green]ok  [/green]", False: "[red]FAIL[/red]",
                None: "[dim]n/m [/dim]"}[row["ok"]]
        console.print(f"  {mark} {row['link'][:56]:56s} "
                      f"[dim]n={row['n']}[/dim]")
        if row.get("error"):
            console.print(f"        [red]{row['error'][:110]}[/red]")
        if row.get("note"):
            console.print(f"        [dim]{row['note'][:110]}[/dim]")
    console.print(f"\n{r['note']}")

    # THE OTHER TWO LEGS. Rows above = is each stage's output produced and
    # consumed. These = can the model call every tool, and did what it asked for
    # arrive. All three are the same def-use question at different scopes.
    _re_ = r.get("reachability") or {}
    if _re_.get("ok") is False:
        console.print(f"[red]Unreachable tools.[/red] {_re_.get('note','')}")
    elif _re_.get("ok"):
        console.print(f"[dim]Tool surface: {_re_.get('n_tool_agent')} tools agent, "
                      f"{_re_.get('n_science_agent')} scientific proofreading agent, "
                      f"{_re_.get('n_adjudicator')} adjudicator, all "
                      f"{_re_.get('n_registered')} registered tools reachable"
                      f"{' (' + str(len(_re_.get('cli_only') or [])) + ' declared CLI-only)' if _re_.get('cli_only') else ''}.[/dim]")
    _dl_ = r.get("delivery") or {}
    if _dl_.get("ok") is False:
        console.print(f"[red]Information that did not arrive.[/red] {_dl_.get('note','')}")
        for _x in (_dl_.get("lost") or [])[:5]:
            console.print(f"        [red]{_x.get('tool')}[/red] "
                          f"[dim]{str(_x.get('detail',''))[:88]}[/dim]")
    elif _dl_.get("ok") is None:
        console.print(f"[dim]{_dl_.get('note','')}[/dim]")
    if r["undeclared_files"]:
        console.print(f"[yellow]Undeclared: {', '.join(r['undeclared_files'])}"
                      "[/yellow]")
    # AN EXIT CODE, because a summary line in stdout cannot gate anything.
    if not r["ready"]:
        raise typer.Exit(2)


@app.command("agreement")
def agreement_cmd(
    paper_dir: Path = typer.Argument(..., help="A paper with 2+ review dirs"),
):
    """pass@K: how much of what this pipeline can find does ONE run find?

    Borrowed from SPOT (Son et al. 2025), which found frontier models "rarely
    rediscover the same errors" across eight runs. Our own Romano study found
    checks with a fixed target recurred 8 of 8 and model-targeted checks 0 of
    10, so this is the number that tells us whether that is improving.

    Reported as an INTERVAL, because matching findings across runs by string is
    unreliable in both directions -- see `evaluation/agreement.py`.
    """
    from .evaluation.agreement import find_runs, from_review_dirs

    runs = find_runs(paper_dir)
    if len(runs) < 2:
        console.print(f"[yellow]{len(runs)} run(s) found. pass@K needs at least "
                      "two runs of one paper; one run is not agreement of "
                      "100%.[/yellow]")
        raise typer.Exit(1)
    r = from_review_dirs(runs)
    console.print(f"runs: {', '.join(r['runs_used'])}\n")
    lo, hi = r["pass_at_1_bracket"]
    console.print(f"  pass@1  [bold]{lo:.0%} to {hi:.0%}[/bold]  "
                  f"[dim](strict to loose matching)[/dim]")
    for k, v in sorted(r["all_findings"]["pass_at"].items()):
        loose = r["all_findings_loose"]["pass_at"].get(k, 0.0)
        console.print(f"  pass@{k}  {v:.0%} to {loose:.0%}")
    console.print(f"\n{r['note']}")


@app.command("extract-tables")
def extract_tables_cmd(
    paper_dir: Path = typer.Argument(..., help="The paper's directory"),
    force: bool = typer.Option(False, "--force", help="Ignore any cached result"),
):
    """Read every declared PDF's tables into the cache, before a review runs.

    EXPLICIT BECAUSE IT IS EXPENSIVE. Table extraction is a layout model and
    takes tens of seconds to minutes per paper; wiring it implicitly into
    `prepass.paper_tables` -- an ordinary "list this paper's tables" call --
    took the test suite from 260 s to 596 s and raced parallel workers into one
    cache file. So enumeration reads the cache and this command fills it.

    Cached by file CONTENT, so re-running is free and a re-fetched or renamed
    file is not re-extracted.
    """
    from . import supplements as _supp
    from .extraction import docling_tables as _dl

    if not paper_dir.is_dir():
        console.print(f"[red]Not a directory: {paper_dir}[/red]")
        raise typer.Exit(1)

    ok, why = _dl.available()
    if not ok:
        console.print(f"[red]docling is not installed: {why}[/red]")
        raise typer.Exit(1)

    c = _supp.classify_inputs(paper_dir)
    pdfs = [paper_dir / f["name"] for f in c["files"]
            if f["role"] in ("article", "supplement", "dataset")
            and f["name"].lower().endswith(".pdf")]
    if c["undeclared"]:
        console.print(f"[yellow]{len(c['undeclared'])} undeclared file(s) were "
                      "NOT extracted. `metascience inputs` says what they "
                      "are.[/yellow]")
    if not pdfs:
        console.print("No declared PDF in this directory (an XML paper needs no "
                      "extraction -- its tables are already marked up).")
        return

    total = 0
    for pdf in pdfs:
        r = _dl.extract_pdf_tables(pdf, use_cache=not force)
        if r.get("error"):
            console.print(f"  [red]{pdf.name}: {r['error']}[/red]")
            continue
        n_cells = sum(len(t.get("cells") or []) for t in r["tables"])
        total += n_cells
        tag = "cached" if r.get("cached") else "extracted"
        console.print(f"  [green]{pdf.name}[/green]: {len(r['tables'])} table(s), "
                      f"{n_cells} cells [dim]({tag})[/dim]")
        for note in (r.get("notes") or []):
            console.print(f"      [dim]{note}[/dim]")
    console.print(f"\n{total} table cell(s) available to the review.")


@app.command("inputs")
def inputs_cmd(
    paper_dir: Path = typer.Argument(..., help="The paper's directory"),
    supplement: list[Path] = typer.Option(
        [], "--supplement", "-s", help="Declare a file supplementary material"),
    dataset: list[Path] = typer.Option(
        [], "--dataset", "-d", help="Declare a file raw data or code"),
    article: Optional[Path] = typer.Option(
        None, "--article", "-a", help="Declare which file is the article itself"),
    ignore: list[Path] = typer.Option(
        [], "--ignore", help="Declare a file no part of this paper"),
):
    """Say what each file in a paper directory IS, before the review runs.

    Greg, 2026-08-13: "The detection of supplements shouldn't be contingent on
    the file naming... this is something the model shouldn't have to deal with.
    The user (or the agent they're interfacing with to use the CLI) should have
    to provide these, and specify."

    Run with no options to see the current state, including anything undeclared.
    """
    from . import supplements as _supp

    if not paper_dir.is_dir():
        console.print(f"[red]Not a directory: {paper_dir}[/red]")
        raise typer.Exit(1)

    if supplement or dataset or article or ignore:
        _supp.write_declaration(
            paper_dir,
            supplements=[str(p) for p in supplement],
            datasets=[str(p) for p in dataset],
            articles=[str(article)] if article else [],
            ignores=[str(p) for p in ignore],
        )
        console.print(f"[green]Recorded in {paper_dir / _supp.INPUTS_FILE}[/green]\n")

    c = _supp.classify_inputs(paper_dir)
    for f in c["files"]:
        colour = {"article": "cyan", "supplement": "green", "dataset": "green",
                  "undeclared": "yellow", "unusable": "red",
                  "ignore": "dim"}.get(f["role"], "white")
        by = f.get("declared_by") or "nobody"
        console.print(f"  [{colour}]{f['role']:<11}[/{colour}] "
                      f"[dim]({by})[/dim]  {f['name']}")
        if f["role"] in ("undeclared", "unusable"):
            console.print(f"      [dim]{f['why']}[/dim]")
    console.print(f"\n{c['note']}")
    # UNDECLARED IS AN EXIT CODE, not a remark. A caller scripting this has to
    # be able to tell "everything is accounted for" from "we quietly used less
    # of this paper than you think", and a sentence in stdout cannot do that.
    if c["undeclared"]:
        raise typer.Exit(2)


@app.command("extract-supplement")
def extract_supplement_cmd(
    path: Path = typer.Argument(..., help="Supplementary .docx/.xlsx/.csv file"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
):
    """Extract tables from a supplementary data file."""
    from .extraction.supplements_read import extract_supplement

    if not path.exists():
        console.print(f"[red]Error: File not found: {path}[/red]")
        raise typer.Exit(1)

    result = extract_supplement(path)
    if result.get("error"):
        # A refusal is a result, not a crash: the caller records it as a
        # coverage gap rather than treating the supplement as absent.
        console.print(f"[yellow]{result['error']}[/yellow]")
        console.print("[dim]Record this in `unchecked`; do not report the "
                      "supplement as absent.[/dim]")
        return

    if output:
        output.write_text(json.dumps(result, indent=2))
        console.print(f"[green]Extracted to: {output}[/green]")
        return

    console.print(f"[bold]Format:[/bold] {result['source_format']}")
    console.print(f"[bold]Tables:[/bold] {result['n_tables']}")
    for table in result["tables"]:
        console.print(
            f"  {table['label']}: {table['n_rows']}x{table['width']}, "
            f"{len(table['cells'])} cells"
        )
        for warning in table["warnings"]:
            console.print(f"    [yellow]! {warning}[/yellow]")


@app.command()
def grim(
    mean: float = typer.Argument(..., help="Reported mean"),
    n: int = typer.Argument(..., help="Sample size"),
    scale_min: int = typer.Option(1, help="Minimum scale value"),
    scale_max: int = typer.Option(7, help="Maximum scale value"),
    decimals: int = typer.Option(2, help="Decimal places in mean"),
    data_type: Optional[str] = typer.Option(None, "--data-type", help="integer|likert|count|binary|proportion|continuous. GRIM REFUSES on non-integer data."),
    bound_source: str = typer.Option("assumed", "--bound-source", help="stated|logically_necessary|assumed -- who supplied scale_min/scale_max"),
    discreteness_source: str = typer.Option("assumed", "--discreteness-source", help="stated|logically_necessary|assumed -- who says the observations are WHOLE NUMBERS. Assumed caps a granularity failure at `suspicious`."),
):
    """Run GRIM test on a single mean."""
    result = grim_module.grim_test(
        mean, n, scale_min, scale_max, decimals,
        data_type=data_type if data_type is not None else "likert",
        bound_source=bound_source,
        discreteness_source=discreteness_source,
    )
    if not result.get("applicable", True):
        print_severity(result)
        console.print(f"\n[dim]{result['methodology']}[/dim]")
        return
    bail_on_error(result)

    if result["consistent"]:
        console.print(f"[green]CONSISTENT[/green]: Mean {mean} is possible for n={n}")
    else:
        # SAY THE SEVERITY THE TOOL RETURNED, not "IMPOSSIBLE" unconditionally.
        # The word was hard-coded, so a verdict the gates had already capped at
        # `suspicious` still printed as an impossibility on this surface -- the
        # overclaim the caps exist to prevent, reintroduced by the renderer.
        sev = result.get("severity")
        console.print(f"[red]INCONSISTENT[/red]: Mean {mean} is "
                      f"{'IMPOSSIBLE' if sev == 'impossible' else sev.upper()} for n={n}")
        console.print(f"  failure mode: [bold]{result.get('failure_mode')}[/bold] "
                      f"(bound_source={result.get('bound_source')}, "
                      f"discreteness_source={result.get('discreteness_source')}, "
                      f"severity={sev})")
        if result.get("discreteness_caveat"):
            console.print(f"  [yellow]{result['discreteness_caveat']}[/yellow]")

    console.print(f"\n[dim]{result['methodology']}[/dim]")
    console.print(f"\nNearby possible means: {result['possible_means_nearby']}")
    warn_if_assumed(result, data_type, scale=f"{scale_min}-{scale_max}", effective="likert")


@app.command()
def ttest(
    mean1: float = typer.Argument(...),
    sd1: float = typer.Argument(...),
    n1: int = typer.Argument(...),
    mean2: float = typer.Argument(...),
    sd2: float = typer.Argument(...),
    n2: int = typer.Argument(...),
    reported_p: Optional[float] = typer.Option(None, "--reported-p", "-p"),
):
    """Recalculate an independent t-test."""
    result = ttest_module.recalc_independent_t(mean1, sd1, n1, mean2, sd2, n2, reported_p)
    bail_on_error(result)

    console.print(f"[bold]Calculated t:[/bold] {result['calculated_t']:.4f}")
    console.print(f"[bold]Calculated df:[/bold] {result['calculated_df']:.2f}")
    console.print(f"[bold]Calculated p:[/bold] {result['calculated_p']:.6f}")

    if reported_p:
        if result.get("p_matches"):
            console.print(f"\n[green]P-value MATCHES reported value ({reported_p})[/green]")
        else:
            console.print(f"\n[red]P-value DOES NOT MATCH reported value ({reported_p})[/red]")
            console.print(f"Difference: {result.get('p_difference', 'N/A'):.6f}")


@app.command()
def sprite(
    mean: float = typer.Argument(...),
    sd: float = typer.Argument(...),
    n: int = typer.Argument(...),
    scale_min: int = typer.Option(1),
    scale_max: int = typer.Option(7),
    num_samples: int = typer.Option(10),
    decimals_sd: Optional[int] = typer.Option(None, "--decimals-sd", help="Decimals in reported SD (as PRINTED; inferred if omitted)"),
    decimals_mean: Optional[int] = typer.Option(None, "--decimals-mean", help="Decimals in reported mean (as PRINTED; inferred if omitted)"),
    data_type: Optional[str] = typer.Option(None, "--data-type", help="integer|likert|count|binary|proportion|continuous. SPRITE REFUSES on non-integer data."),
    discreteness_source: str = typer.Option("assumed", "--discreteness-source", help="stated|logically_necessary|assumed -- who says the observations are WHOLE NUMBERS. Assumed caps a bound-free failure at `suspicious`."),
):
    """Reconstruct possible distributions using SPRITE."""
    with console.status("Reconstructing..."):
        result = sprite_module.sprite_reconstruct(
            mean, sd, n, scale_min, scale_max, num_samples,
            decimals_sd=decimals_sd, decimals_mean=decimals_mean,
            data_type=data_type if data_type is not None else "integer",
            discreteness_source=discreteness_source,
        )

    if not result.get("applicable", True):
        print_severity(result)
        return

    if not result.get("success"):
        outcome = result.get("outcome", "failed")
        # Only `no_solution_proven` is evidence. A search that ran out of time is not.
        color = "red" if outcome == "no_solution_proven" else "yellow"
        console.print(f"[{color}]{outcome}[/{color}]: {result.get('explanation') or result.get('error')}")
        if outcome != "no_solution_proven":
            console.print("[dim]Not evidence of anything: the search did not PROVE that no "
                          "dataset exists. Only `no_solution_proven` is a finding.[/dim]")
        raise typer.Exit(1 if outcome == "no_solution_proven" else 0)

    console.print(f"[bold]Generated {result['num_valid_samples']} valid distributions[/bold]")

    if result.get("is_bimodal"):
        console.print("[yellow]WARNING: Distributions are bimodal (unusual pattern)[/yellow]")

    console.print("\n[bold]Example distributions:[/bold]")
    for i, dist in enumerate(result["example_distributions"][:3], 1):
        # Create a simple histogram
        counts = {v: dist.count(v) for v in range(scale_min, scale_max + 1)}
        hist = " ".join(f"{v}:{counts[v]}" for v in counts if counts[v] > 0)
        console.print(f"  {i}. {hist}")

    console.print("\n[bold]Value frequencies across samples:[/bold]")
    for val, freq in result["value_frequencies"].items():
        bar = "█" * int(freq["mean_count"])
        console.print(f"  {val}: {bar} ({freq['mean_count']:.1f})")


@app.command("sd-range")
def sd_range(
    sd: float = typer.Argument(..., help="Reported standard deviation"),
    min_val: float = typer.Argument(..., help="Minimum possible value"),
    max_val: float = typer.Argument(..., help="Maximum possible value"),
    n: Optional[int] = typer.Option(None, "--n", help="Sample size for more precise calculation"),
    decimals_sd: Optional[int] = typer.Option(
        None, "--decimals-sd", help="Printed decimals of sd, read from the literal"),
    bound_source: str = typer.Option(
        "assumed", "--bound-source",
        help="stated | logically_necessary | assumed. The ceiling comes ENTIRELY from "
             "[min_val, max_val], so a range the paper never stated caps the verdict at "
             "highly_suspicious rather than impossible."),
):
    """Check if a standard deviation is plausible given the data range."""
    result = sd_checks.check_sd_range(sd, min_val, max_val, n, decimals_sd,
                                      bound_source=bound_source)
    bail_on_error(result)

    if result["is_plausible"]:
        console.print(f"[green]PLAUSIBLE[/green]: SD {sd} is possible for range [{min_val}, {max_val}]")
    else:
        console.print(f"[red]IMPLAUSIBLE[/red]: SD {sd} is too large for range [{min_val}, {max_val}]")
        console.print(f"[bold]Severity:[/bold] {result['severity']}")

    console.print(f"\n[bold]Max possible SD:[/bold] {result['max_possible_sd']:.4f}")
    console.print(f"[bold]SD as fraction of max:[/bold] {result['sd_as_fraction_of_max']:.2%}")
    console.print(f"\n{result['explanation']}")
    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command()
def anova(
    means: str = typer.Option(..., "--means", "-m", help="Comma-separated group means"),
    sds: str = typer.Option(..., "--sds", "-s", help="Comma-separated group standard deviations"),
    ns: str = typer.Option(..., "--ns", "-n", help="Comma-separated group sample sizes"),
    reported_f: Optional[float] = typer.Option(None, "--reported-f", "-f", help="Reported F statistic"),
    reported_p: Optional[float] = typer.Option(None, "--reported-p", "-p", help="Reported p-value"),
):
    """Recalculate one-way ANOVA from group statistics."""
    means_list = _floats(means, "--means")
    sds_list = _floats(sds, "--sds")
    ns_list = _ints(ns, "--ns")

    result = anova_module.recalc_one_way_anova(means_list, sds_list, ns_list, reported_f, reported_p)
    bail_on_error(result)

    console.print(f"[bold]Calculated F:[/bold] {result['calculated_f']:.4f}")
    console.print(f"[bold]Calculated p:[/bold] {result['calculated_p']:.6f}")
    console.print(f"[bold]df (between, within):[/bold] ({result['df_between']}, {result['df_within']})")

    if reported_f is not None:
        if result.get("f_matches"):
            console.print(f"\n[green]F-statistic MATCHES reported value ({reported_f})[/green]")
        else:
            console.print(f"\n[red]F-statistic DOES NOT MATCH reported value ({reported_f})[/red]")

    if reported_p is not None:
        if result.get("p_matches"):
            console.print(f"[green]P-value MATCHES reported value ({reported_p})[/green]")
        else:
            console.print(f"[red]P-value DOES NOT MATCH reported value ({reported_p})[/red]")

    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("duplication-detect")
def duplication_detect_cmd(
    json_path: Path = typer.Argument(..., help="JSON file with a list of blocks"),
    decimals_mean: int = typer.Option(2, "--dm"),
    decimals_sd: int = typer.Option(2, "--ds"),
    no_near_match: bool = typer.Option(False, "--no-near-match"),
):
    """Detect duplicated/copy-pasted summary statistics within and across tables.

    JSON root: a list of blocks. Each block is
        {"label": "Table S1", "sample_id": "study1a", "independent": true,
         "cells": [{"label": "clarity/unethical", "value": 5.38, "sd": 1.17}, ...]}
    Blocks sharing a sample_id describe the SAME participants (matches expected).
    """
    from .tools.duplication import detect_duplication

    if not json_path.exists():
        console.print(f"[red]File not found: {json_path}[/red]")
        raise typer.Exit(1)
    blocks = json.loads(json_path.read_text())
    if not isinstance(blocks, list):
        console.print("[red]JSON root must be a list of block dicts[/red]")
        raise typer.Exit(1)

    result = detect_duplication(
        blocks, decimals_mean=decimals_mean, decimals_sd=decimals_sd,
        near_match=not no_near_match,
    )
    bail_on_error(result)
    print_severity(result)
    console.print(f"\n[bold]Max identical pairs (independent):[/bold] {result['max_identical_pairs']}")
    if result.get("chance_probability") is not None:
        console.print(f"[bold]Coincidence probability:[/bold] {result['chance_probability']:.2g}")
    console.print(f"[bold]Comparisons:[/bold] {result['n_comparisons']}")
    if result["duplicate_groups"]:
        console.print("\n[bold]Duplicate groups:[/bold]")
        for g in result["duplicate_groups"]:
            color = _severity_color(g["severity"])
            if g["kind"] == "cross_source_pair":
                console.print(
                    f"  [{color}]{g['severity']}[/{color}] {g['kind']}: "
                    f"{g['k_pairs']} identical pair(s) in '{g['block_a']}' & '{g['block_b']}'"
                    + (" [same-sample: expected]" if g["same_sample_caveat"] else "")
                    + f"  values={g['values']}"
                )
            elif g["kind"].startswith("within_table"):
                console.print(
                    f"  [{color}]{g['severity']}[/{color}] {g['kind']}: "
                    f"labels {g['labels']} ({g['n_identical_cells']} identical cells) in '{g['block']}'"
                )
            else:
                console.print(f"  [{color}]{g['severity']}[/{color}] {g['kind']}: {g}")
    console.print(f"\n[dim]{result['methodology']}[/dim]")
    for cav in result.get("caveats", []):
        console.print(f"[yellow]Caveat:[/yellow] {cav}")


_image_command("image-analysis", "image_analysis_cmd")


@app.command("tortured-phrases")
def tortured_phrases_cmd(
    target: Path = typer.Argument(
        ..., help="A paper directory (read via paper_text's fallback chain) "
                  "or a single .md/.txt/.xml/.pdf file"),
    family: Optional[List[str]] = typer.Option(
        None, "--family",
        help="Show only this family (tortured_phrase | llm_boilerplate | "
             "tortured_acronym). Repeatable. Display filter only -- counts "
             "and severity always reflect every family."),
    include_references: bool = typer.Option(
        False, "--include-references/--no-include-references",
        help="Also LIST references-section matches (they are always recorded "
             "but never counted toward severity: a tortured phrase in a "
             "cited title indicts the cited paper, not this one)."),
    context: int = typer.Option(80, "--context", help="Context chars shown around each match"),
    limit: Optional[int] = typer.Option(
        None, "--limit",
        help="Display at most N matches. Display cap only -- the result and "
             "counts are never truncated."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
):
    """Screen a paper's prose for tortured phrases / LLM boilerplate (QUARANTINED).

    The delivered severity is always `indeterminate` while the screen's
    false-positive classes are unmeasured on this pipeline; the pre-registered
    grade is printed as `severity_before_quarantine`. Release gates live in
    the tool's module docstring; `examples/calibrate_tortured_phrases.py`
    produced the evidence (deleted 2026-10-16 with examples/; recover it from git history).
    """
    from .tools.tortured_phrases import detect_tortured_phrases

    if not target.exists():
        console.print(f"[red]Not found: {target}[/red]")
        raise typer.Exit(1)

    if target.is_dir():
        result = detect_tortured_phrases(paper_dir=str(target))
    else:
        suffix = target.suffix.lower()
        if suffix in (".md", ".txt"):
            text = target.read_text(encoding="utf-8", errors="replace")
        elif suffix == ".xml":
            from .extraction.jats import extract_xml_text
            text = extract_xml_text(target)
        elif suffix == ".pdf":
            from .extraction.pdf import extract_text
            text = extract_text(target)
        else:
            console.print(f"[red]Unsupported file type {suffix!r}: pass a "
                          f"paper directory or .md/.txt/.xml/.pdf[/red]")
            raise typer.Exit(1)
        result = detect_tortured_phrases(text=text)

    bail_on_error(result)
    print_severity(result)
    if result.get("quarantined"):
        console.print(
            f"[yellow]QUARANTINED[/yellow] — pre-registered grade: "
            f"[bold]{result.get('severity_before_quarantine')}[/bold]")
    d = result.get("dictionary", {})
    console.print(
        f"[bold]Matches:[/bold] {result.get('n_matches', 0)} "
        f"({result.get('n_matches_references', 0)} in references)  "
        f"[bold]Distinct guarded (k):[/bold] "
        f"{result.get('n_distinct_fingerprints', 0)}  "
        f"[bold]Words:[/bold] {result.get('n_words_scanned', 0)}  "
        f"[bold]Dictionary:[/bold] {d.get('version')} "
        f"({d.get('n_fingerprints')} fingerprints)")
    shown = 0
    for m in result.get("matches", []):
        if family and m["family"] not in family:
            continue
        if not include_references and m["section"] == "references":
            continue
        if limit is not None and shown >= limit:
            console.print(f"[dim]... display capped at {limit}; the counts "
                          f"above are complete[/dim]")
            break
        shown += 1
        arrow = f" -> [green]{m['expected']}[/green]" if m["expected"] else ""
        tags = [t for t in (
            m["section"] if m["section"] != "body" else None,
            f"suppressed: {m['suppressed_by']}" if m["suppressed_by"] else None,
            m["variant"], "extraction-risk" if m["extraction_risk"] else None,
            "quoted" if m["in_quotation"] is True else None,
        ) if t]
        tag_s = f" [dim]({', '.join(tags)})[/dim]" if tags else ""
        console.print(f"  [{_severity_color('suspicious')}]{m['matched_text']}"
                      f"[/{_severity_color('suspicious')}]{arrow} "
                      f"[dim]\\[{m['family']}][/dim]{tag_s}")
        snippet = m["context"]
        if context != 80:
            lo = max(0, len(snippet) // 2 - context)
            snippet = snippet[lo:lo + 2 * context]
        console.print(f"      [dim]{snippet}[/dim]")
    for c in result.get("caveats") or []:
        console.print(f"[dim]caveat: {c}[/dim]")

    if output:
        output.write_text(json.dumps(result, indent=2, default=str))
        console.print(f"[green]Written: {output}[/green]")


_image_command("image-corpus", "image_corpus_cmd")



_image_command("image-sweep", "image_sweep_cmd")
_image_command("image-complete", "image_complete_cmd")



_image_command("image-dataset-fetch", "image_dataset_fetch_cmd")


_image_command("image-dataset-prepare", "image_dataset_prepare_cmd")


_image_command("image-dataset-run", "image_dataset_run_cmd")


_image_command("image-benchmark", "image_benchmark_cmd")
_image_command("image-reviews-export", "image_reviews_export_cmd")
_image_command("image-benchmark-compare", "image_benchmark_compare_cmd")
_image_command("image-gate", "image_gate_cmd")
_image_command("image-cache-prune", "cache_prune_cmd", "image_cache_prune_cmd")
_image_command("image-dataset-compose", "image_dataset_compose_cmd")
_image_command("image-panel-benchmark", "image_panel_benchmark_cmd")
_image_command("image-overlap-bench", "image_overlap_bench_cmd")


_image_command("image-labels", "image_labels_cmd")



_image_command("image-fetch-pmc-figures", "image_fetch_pmc_figures_cmd")



_image_command("image-fetch-publisher-figures", "image_fetch_publisher_figures_cmd")


def _parse_models(spec: str) -> list[tuple[str, str]]:
    """`claude:sonnet,codex:gpt-5.6-luna` -> [(backend, model), ...]; a bare
    model name means the claude backend."""
    out: list[tuple[str, str]] = []
    for item in (spec or "").split(","):
        item = item.strip()
        if not item:
            continue
        backend, _, model = item.partition(":")
        if not model:
            backend, model = "claude", backend
        out.append((backend.strip(), model.strip()))
    if not out:
        raise typer.BadParameter("at least one backend:model is required")
    return out


_image_command("image-adjudicate", "image_adjudicate_cmd")


_image_command("image-screen", "image_screen_cmd")


_image_command("image-repair-source-identity", "image_repair_source_identity_cmd")


_image_command("image-adjudicate-cross", "image_adjudicate_cross_cmd")


_image_command("image-rebuild-exhibits", "image_rebuild_exhibits_cmd")


_image_command("image-figure-sources", "image_figure_sources_cmd")


_image_command("image-identity-backfill", "image_identity_backfill_cmd")


_image_command("image-render-videos", "image_render_videos_cmd")


_image_command("image-blot-scan", "image_blot_scan_cmd")


_image_command("image-blot-benchmark", "image_blot_benchmark_cmd")


@app.command("raw-duplication-detect")
def raw_duplication_detect_cmd(
    path: Path = typer.Argument(..., help="Supplementary data file (.xlsx/.csv/.tsv/.docx)"),
    sheet: Optional[str] = typer.Option(None, "--sheet", help="Restrict to one worksheet"),
    exclude_column: Optional[List[str]] = typer.Option(
        None, "--exclude-column", "-x",
        help="Column shared BY DESIGN (ID, coordinates, site covariate). Repeatable."),
    data_context: str = typer.Option(
        "unknown", "--data-context",
        help="raw_participant_level | pooled_or_meta_analysis | unknown"),
    highlight_out: Optional[Path] = typer.Option(
        None, "--highlight-out",
        help="Also write a highlighted .xlsx copy marking every match group"),
    max_row_pairs: Optional[int] = typer.Option(
        None, "--max-row-pairs",
        help="Row-pair comparison budget (default 5000). Row-pair search is "
             "O(n^2): a 15k-row file exhausts the default and says so in a "
             "caveat. Raise it to trade runtime for coverage."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
):
    """Detect duplicated raw data (rows, runs, values) in a supplement file.

    Note --max-row-pairs is a CLI-only flag: it stays withheld from the model's
    tool schema, because a caller that can tune how hard the search tries can
    tune until it gets the verdict it wants. A human at a terminal is not that
    threat model.
    """
    from copy_paste_detector import detect_raw_duplication

    if not path.exists():
        console.print(f"[red]File not found: {path}[/red]")
        raise typer.Exit(1)

    extra = {} if max_row_pairs is None else {"max_row_pairs": max_row_pairs}
    result = detect_raw_duplication(
        str(path), sheet=sheet, exclude_columns=exclude_column,
        data_context=data_context, **extra,
    )
    bail_on_error(result)
    print_severity(result)
    console.print(
        f"[bold]Tables:[/bold] {result['n_tables']}  "
        f"[bold]Numeric cells:[/bold] {result['n_numeric_cells']}  "
        f"[bold]Groups:[/bold] {result['n_duplicate_groups']}"
    )
    if result.get("excluded_columns"):
        console.print(f"[dim]Excluded columns: {', '.join(result['excluded_columns'])}[/dim]")
    # Which columns the findings come from, before the findings themselves --
    # a hundred cell refs from nine columns is one fact, not a hundred.
    if len(result.get("by_column") or ()) > 1:
        console.print("[bold]By column:[/bold]")
        for entry in result["by_column"][:10]:
            console.print(f"  [dim]{entry['n_groups']:>5} group(s)[/dim]  {entry['column']}")
    for g in result["duplicate_groups"][:25]:
        color = _severity_color(g["severity"])
        if g["kind"] == "row_pair":
            rows = ", ".join(f"{r['sheet']}!{r['cell']}" for r in g["rows"])
            console.print(
                f"  [{color}]{g['severity']}[/{color}] row_pair: "
                f"{len(g['rows'])} rows share {g['n_shared_columns']} column(s) "
                f"[score {g['adjusted_score']}] at {rows}"
            )
        elif g["kind"] == "column_sequence":
            console.print(
                f"  [{color}]{g['severity']}[/{color}] column_sequence: "
                f"{g['length']} consecutive values, '{g['column_a']}' "
                f"({g['start_a']['sheet']}!{g['start_a']['cell']}) = '{g['column_b']}' "
                f"({g['start_b']['sheet']}!{g['start_b']['cell']}) "
                f"[score {g['adjusted_score']}]"
            )
        else:
            console.print(
                f"  [{color}]{g['severity']}[/{color}] repeated_value: "
                f"{g['value']} x{g['occurrences_in_file']} "
                f"({g['significant_digits']} sig digits, "
                f"{g['n_columns']} column(s)) [score {g['adjusted_score']}]"
            )
    if result["n_duplicate_groups"] > 25:
        console.print(f"  [dim]... and {result['n_duplicate_groups'] - 25} more[/dim]")
    console.print(f"\n[dim]{result['methodology']}[/dim]")
    for cav in result.get("caveats", []):
        console.print(f"[yellow]Caveat:[/yellow] {cav}")

    if highlight_out is not None:
        from copy_paste_detector import highlight_workbook
        h = highlight_workbook(path, result["duplicate_groups"], highlight_out)
        if h.get("error"):
            console.print(f"[yellow]Highlight not written: {h['error']}[/yellow]")
        else:
            console.print(f"[green]Highlighted workbook: {h['path']} "
                          f"({h['n_groups_highlighted']} group(s), "
                          f"{h['n_groups_skipped']} skipped)[/green]")
    if output:
        output.write_text(json.dumps(result, indent=2, default=str))
        console.print(f"[green]JSON written to: {output}[/green]")


@app.command("parse-table")
def parse_table_cmd(
    path: Path = typer.Argument(..., help="Markdown/text file containing one table"),
    source_format: str = typer.Option("auto", "--format", help="auto|markdown|grid|text"),
    label: str = typer.Option("table", "--label"),
    cross_check: Optional[Path] = typer.Option(None, "--cross-check", help="Same table from the other extraction, to reconcile"),
):
    """Parse a summary-statistics table into normalized cells (+ optional reconcile)."""
    from .tools.tableparse import parse_table

    if not path.exists():
        console.print(f"[red]File not found: {path}[/red]")
        raise typer.Exit(1)
    cc = cross_check.read_text() if (cross_check and cross_check.exists()) else None
    result = parse_table(
        path.read_text(), source_format=source_format, source_label=label,
        cross_check=cc,
    )
    bail_on_error(result)
    console.print(f"[bold]Parsed {result['n_numeric_cells']} numeric cells[/bold] from '{label}'")
    console.print(f"[bold]Rows:[/bold] {result['row_labels']}")
    console.print(f"[bold]Cols:[/bold] {result['col_labels']}")
    for c in result["cells"][:20]:
        sd = f" (sd {c['sd']})" if c["sd"] is not None else ""
        console.print(f"  {c['row_label']} | {c['col_label']} = {c['value']}{sd}")
    if result.get("warnings"):
        for w in result["warnings"]:
            console.print(f"[yellow]warning:[/yellow] {w}")
    if result.get("reconciliation"):
        rec = result["reconciliation"]
        color = _severity_color(rec["severity"])
        console.print(f"\n[{color}]Reconcile:[/{color}] {rec['explanation']}")
        for d in rec["disagreements"]:
            console.print(f"  [red]{d['row_label']}|{d['col_label']}[/red]: "
                          f"{d['value_a']} vs {d['value_b']} ({d['kind']})")


@app.command("variance-dispersion")
def variance_dispersion_cmd(
    sds: str = typer.Option(
        ..., "--sds",
        help="Comma-separated standard deviations, AS PRINTED (e.g. 25.09,24.58,25.65). "
             "The literals matter: printed precision decides whether identical SDs are a "
             "signature or a rounding artifact, and it cannot be recovered from a float.",
    ),
    ns: str = typer.Option(..., "--ns", help="Comma-separated sample size per group"),
    homogeneous_variances: bool = typer.Option(
        None, "--homogeneous/--heterogeneous",
        help="REQUIRED. Are these groups expected to share a population variance? The "
             "source paper's own preregistered analysis scored AUROC 0.264 -- inverted -- "
             "from getting this wrong, and a violated assumption makes the test BLIND, so "
             "leaving it unset refuses in BOTH directions (no `consistent` either).",
    ),
    design: str = typer.Option(
        None, "--design",
        help="Trial design AS STATED (parallel_rct, cluster, stepped_wedge, crossover, "
             "matched_pairs, stratified, minimised). Designs that constrain variances by "
             "construction are refused outright.",
    ),
    iterations: int = typer.Option(100_000, "--iterations", help="Bootstrap draws for the null"),
    seed: int = typer.Option(0, "--seed"),
):
    """Are these standard deviations too SIMILAR to have arisen by sampling?

    Standardises each variance by the within mean square and compares
    max_z - min_z against a parametric bootstrap of the chi-square null.
    One-sided, for excessive consistency.

    Hartgerink et al. (2019) measured this as the best-performing fabrication
    detector tested (AUROC 1.00 on raw data). That result was RELATIVE: it ranks
    candidates against known-genuine reference data; it does not convict.
    """
    sd_texts = [x.strip() for x in sds.split(",") if x.strip()]
    try:
        sd_values = [float(x) for x in sd_texts]
        n_values = _ints(ns, "--ns")
    except ValueError as exc:
        console.print(f"[red]Could not parse --sds/--ns: {exc}[/red]")
        raise typer.Exit(1)

    result = _variance_dispersion_fn(
        sd_values,
        n_values,
        sd_texts=sd_texts,
        design=design,
        homogeneous_variances=homogeneous_variances,
        iterations=iterations,
        seed=seed,
    )

    if homogeneous_variances is None:
        console.print(
            "\n[yellow]Assumption warning:[/yellow] you did not pass "
            "[bold]--homogeneous[/bold] or [bold]--heterogeneous[/bold], so this check "
            "declined in BOTH directions.\n  A violated equal-variance assumption does not "
            "make this test accusatory -- it makes it BLIND (measured 0.0% detection), so a "
            "`consistent` verdict would be a silent all-clear from a test that could not see."
        )

    print_severity(result)
    if result.get("applicable"):
        console.print(
            f"\n[bold]Dispersion p:[/bold] {result['dispersion_p']:.4g} "
            "(small ⇒ SDs too similar)"
        )
        console.print(
            f"[bold]max_z − min_z:[/bold] {result['dispersion_statistic']:.4f}   "
            f"[dim](SD_z secondary: {result['sd_z_secondary']:.4f})[/dim]"
        )
        console.print(f"[bold]MS_within:[/bold] {result['ms_within']:.4f}")
        console.print(
            "[bold]Standardised variances z²:[/bold] "
            + ", ".join(f"{v:.3f}" for v in result["z_squared"])
        )
        worst = [g for g in result["granularity_ratios"] if g is not None]
        if worst:
            console.print(
                f"[bold]Coarsest rounding step:[/bold] {max(worst):.4g} of the SD "
                f"[dim](refused above 0.25)[/dim]"
            )
        console.print(
            "\n[yellow]Reference required:[/yellow] this verdict is RELATIVE. In the "
            "validating study every dataset -- genuine and fabricated alike -- looked "
            "significant against the theoretical null; only comparison with known-genuine "
            "data from the same measure separated them."
        )

    console.print(f"\n[dim]{result['methodology']}[/dim]")
    if result.get("caveat"):
        console.print(f"\n[yellow]Caveat: {result['caveat']}[/yellow]")


@app.command("table1-dispersion")
def table1_dispersion_cmd(
    json_path: Path = typer.Argument(..., help="JSON file with a list of Table 1 rows"),
    num_bootstrap: int = typer.Option(1000, "--bootstrap"),
    ci_level: float = typer.Option(0.95, "--ci"),
    seed: int = typer.Option(0, "--seed"),
    design: str = typer.Option(
        None, "--design",
        help="Trial design AS STATED by the paper (parallel_rct, cluster, stepped_wedge, "
             "crossover, matched_pairs, stratified, minimised). Designs that force baseline "
             "balance by construction are refused outright; without this the verdict is "
             "capped below highly_suspicious.",
    ),
    correlation: float = typer.Option(
        None, "--correlation",
        help="Correlation among baseline rows, if genuinely known or estimable. Omit to get "
             "a sensitivity profile across a rho grid instead of one assumed value.",
    ),
):
    """Bayesian-style Table 1 dispersion (precision multiplier) from a JSON spec.

    JSON schema: a list of row dicts. Each row is either
        {"label": "age", "means": [...], "sds": [...], "ns": [...]}   # continuous
    or
        {"label": "sex", "counts": [[r1c1, r1c2, ...], [r2c1, r2c2, ...]]}  # categorical
    """
    if not json_path.exists():
        console.print(f"[red]File not found: {json_path}[/red]")
        raise typer.Exit(1)
    rows = json.loads(json_path.read_text())
    if not isinstance(rows, list):
        console.print("[red]JSON root must be a list of row dicts[/red]")
        raise typer.Exit(1)

    # Keyword arguments deliberately: this was a positional call, and the
    # signature has since grown `design`, `correlation` and `rho_grid`. Appended
    # parameters kept it working by luck, not by design.
    result = _table1_dispersion_fn(
        rows,
        num_bootstrap=num_bootstrap,
        ci_level=ci_level,
        seed=seed,
        design=design,
        correlation=correlation,
    )
    if design is None:
        console.print(
            "\n[yellow]Assumption warning:[/yellow] you did not pass [bold]--design[/bold], so "
            "this verdict is capped below [bold]highly_suspicious[/bold].\n  Cluster, "
            "stepped-wedge, crossover, matched-pairs, stratified and minimised allocation "
            "force baseline balance BY CONSTRUCTION -- any of them would explain an "
            "under-dispersed Table 1 innocently."
        )
    sev = result["severity"]
    color = _severity_color(sev)
    console.print(f"[{color}]{sev.upper()}[/{color}]: {result['explanation']}")
    if "precision_multiplier" in result:
        console.print(f"\n[bold]Precision multiplier τ̂:[/bold] {result['precision_multiplier']:.3f}")
        console.print(f"[bold]CI ({int(ci_level*100)}%, exact χ²):[/bold] "
                      f"[{result['precision_multiplier_ci'][0]:.3f}, "
                      f"{result['precision_multiplier_ci'][1]:.3f}]")
        console.print(f"[bold]mean(z²):[/bold] {result['mean_z_squared']:.4f}")
        console.print(f"[bold]K-S vs U(0,1):[/bold] D={result['ks_statistic']:.3f}, p={result['ks_p_value']:.4g}")
        console.print("\n[bold]Per-row:[/bold]")
        for row in result["per_row"]:
            if "error" in row:
                console.print(f"  [red]{row['label']}: ERROR {row['error']}[/red]")
            else:
                console.print(f"  {row['label']:>15s} ({row['kind']:>11s}): "
                              f"p={row['p_value']:.4f}, z={row['z_two_sided']:.3f}")
    if result.get("errors"):
        console.print(f"\n[yellow]Errors:[/yellow] {result['errors']}")
    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("prop-from-normal")
def prop_from_normal_cmd(
    reported_proportion: float = typer.Argument(..., help="Reported proportion (0..1)"),
    mean: float = typer.Argument(..., help="Reported sample mean"),
    sd: float = typer.Argument(..., help="Reported sample SD"),
    n: int = typer.Argument(..., help="Sample size"),
    threshold: float = typer.Option(..., "--threshold", "-t", help="Cut-off value"),
    direction: str = typer.Option("below", "--direction", "-d", help="'below' or 'above'"),
    num_simulations: int = typer.Option(10_000, "--samples"),
    seed: int = typer.Option(0, "--seed"),
):
    """Test whether a reported categorical % is consistent with a normal continuous summary."""
    result = cont_cat_module.check_proportion_from_normal(
        reported_proportion, mean, sd, n, threshold, direction, num_simulations, seed
    )
    sev = result["severity"]
    color = _severity_color(sev)
    console.print(f"[{color}]{sev.upper()}[/{color}]: {result['explanation']}")
    if "theoretical_proportion" in result:
        console.print(f"\n[bold]Theoretical proportion:[/bold] {result['theoretical_proportion']:.4f}")
        console.print(f"[bold]Observed:[/bold] {result['observed_count']}/{n} = {reported_proportion:.4f}")
        console.print(f"[bold]Binomial p (two-sided):[/bold] {result['binomial_p_two_sided']:.4g}")
        console.print(f"[bold]Binomial 95% CI:[/bold] [{result['binomial_ci_95'][0]:.4f}, {result['binomial_ci_95'][1]:.4f}]")
        console.print(f"[bold]MC 95% CI:[/bold] [{result['mc_ci_95'][0]:.4f}, {result['mc_ci_95'][1]:.4f}]")
    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("rivets-t")
def rivets_t_cmd(
    mean1: float = typer.Argument(...),
    sd1: float = typer.Argument(...),
    n1: int = typer.Argument(...),
    mean2: float = typer.Argument(...),
    sd2: float = typer.Argument(...),
    n2: int = typer.Argument(...),
    reported_t: Optional[float] = typer.Option(None, "--reported-t", "-t"),
    reported_p: Optional[float] = typer.Option(None, "--reported-p", "-p"),
    decimals_mean: int = typer.Option(2, "--dm", help="Decimals in reported means"),
    decimals_sd: int = typer.Option(2, "--ds", help="Decimals in reported SDs"),
    decimals_t: int = typer.Option(3, "--dt", help="Decimals in reported t"),
    decimals_p: int = typer.Option(3, "--dp", help="Decimals in reported p"),
    num_samples: int = typer.Option(10_000, "--samples", help="Monte Carlo iterations"),
    seed: int = typer.Option(0, "--seed"),
):
    """RIVETS analysis for an independent two-sample t-test."""
    result = rivets_module.rivets_independent_t(
        mean1, sd1, n1, mean2, sd2, n2, reported_t, reported_p,
        decimals_mean, decimals_sd, decimals_t, decimals_p,
        use_welch=None, num_samples=num_samples, seed=seed,
    )
    sev = result["severity"]
    color = _severity_color(sev)
    console.print(f"[{color}]{sev.upper()}[/{color}]: {result['explanation']}")
    console.print(f"\n[bold]Point t (at truncated inputs):[/bold] {result['point_t_at_truncated']:.{decimals_t}f}")
    console.print(f"[bold]Analytic interval:[/bold] t ∈ [{result['t_min']:.{decimals_t}f}, {result['t_max']:.{decimals_t}f}],   p ∈ [{result['p_min']:.{decimals_p}f}, {result['p_max']:.{decimals_p}f}]")
    if reported_t is not None:
        mc = result["monte_carlo"]
        console.print(f"[bold]Reported t in range:[/bold] {result['reported_t_in_range']}")
        console.print(f"[bold]Point matches reported t:[/bold] {result['point_matches_reported_t']}")
        console.print(f"[bold]MC hit rate (reported t):[/bold] {mc['fraction_match_reported_t']:.3%}")
    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("rivets-anova")
def rivets_anova_cmd(
    means: str = typer.Option(..., "--means", "-m"),
    sds: str = typer.Option(..., "--sds", "-s"),
    ns: str = typer.Option(..., "--ns", "-n"),
    reported_f: Optional[float] = typer.Option(None, "--reported-f", "-f"),
    reported_p: Optional[float] = typer.Option(None, "--reported-p", "-p"),
    decimals_mean: int = typer.Option(2, "--dm"),
    decimals_sd: int = typer.Option(2, "--ds"),
    decimals_f: int = typer.Option(3, "--df"),
    decimals_p: int = typer.Option(3, "--dp"),
    num_samples: int = typer.Option(5000, "--samples"),
    seed: int = typer.Option(0, "--seed"),
):
    """RIVETS analysis for a one-way ANOVA."""
    means_l = _floats(means, "--means")
    sds_l = _floats(sds, "--sds")
    ns_l = _ints(ns, "--ns")
    result = rivets_module.rivets_anova(
        means_l, sds_l, ns_l, reported_f, reported_p,
        decimals_mean, decimals_sd, decimals_f, decimals_p,
        num_samples=num_samples, seed=seed,
    )
    sev = result["severity"]
    color = _severity_color(sev)
    console.print(f"[{color}]{sev.upper()}[/{color}]: {result['explanation']}")
    console.print(f"\n[bold]Point F:[/bold] {result['point_f_at_truncated']:.{decimals_f}f}")
    console.print(f"[bold]MC F range:[/bold] [{result['f_min']:.{decimals_f}f}, {result['f_max']:.{decimals_f}f}]")
    console.print(f"[bold]MC p range:[/bold] [{result['p_min']:.{decimals_p}f}, {result['p_max']:.{decimals_p}f}]")
    if reported_f is not None:
        mc = result["monte_carlo"]
        console.print(f"[bold]MC hit rate (reported F):[/bold] {mc['fraction_match_reported_f']:.3%}")
    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("grim-sweep")
def grim_sweep_cmd(
    values: str = typer.Option(..., "--values", "-v", help="Comma-separated percentages (or proportions)"),
    n_max: int = typer.Option(..., "--n-max", help="Largest candidate n (inclusive)"),
    n_min: int = typer.Option(2, "--n-min", help="Smallest candidate n"),
    decimals: int = typer.Option(1, "--decimals", "-d", help="Decimals in reported values"),
    value_type: str = typer.Option("percentage", "--value-type", help="'percentage' (0-100) or 'proportion' (0-1)"),
    n_max_source: str = typer.Option(
        "assumed", "--n-max-source",
        help="stated | logically_necessary | assumed. An empty intersection only reaches "
             "'impossible' when n-max is the paper's OWN total N; emptiness inside a range "
             "we chose is a fact about the search, not the paper."),
):
    """GRIM sweep: find joint viable ns for several reported percentages."""
    vals = _floats(values, "--values")
    result = grim_module.grim_sweep(vals, n_max, n_min, decimals, value_type,
                                    n_max_source=n_max_source)

    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(1)

    sev = result["severity"]
    color = _severity_color(sev)
    console.print(f"[{color}]{sev.upper()}[/{color}]: {result['explanation']}")
    console.print("\n[bold]Per-value viable ns (first 20):[/bold]")
    for entry in result["per_value"]:
        ns = entry["viable_ns"][:20]
        console.print(f"  value={entry['value']}: {ns} (total {entry['n_viable']})")
    console.print(f"\n[bold]Joint viable ns:[/bold] {result['joint_viable_ns']}")
    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("reconstruct-2x2")
def reconstruct_2x2_cmd(
    pct_col1: float = typer.Argument(..., help="Column-1-conditional percentage (e.g., 63.7)"),
    pct_col2: float = typer.Argument(..., help="Column-2-conditional percentage (e.g., 44.9)"),
    n_total: int = typer.Argument(..., help="Total N"),
    decimals: int = typer.Option(1, "--decimals", "-d", help="Decimals in reported percentages"),
    value_type: str = typer.Option("percentage", "--value-type"),
    reported_chi2: Optional[float] = typer.Option(None, "--chi2", help="Reported chi-squared (filter)"),
    chi2_tolerance: float = typer.Option(0.05, "--chi2-tol", help="Chi-squared match tolerance"),
    balance_ratio_max: float = typer.Option(4.0, "--balance-max", help="Max col1/col2 ratio (filter)"),
):
    """Reconstruct a 2×2 contingency table from row-percentages and a total."""
    result = grim_module.reconstruct_2x2(
        pct_col1, pct_col2, n_total, decimals, value_type,
        reported_chi2, chi2_tolerance, balance_ratio_max,
    )
    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(1)

    sev = result["severity"]
    color = _severity_color(sev)
    console.print(f"[{color}]{sev.upper()}[/{color}]: {result['explanation']}")
    if result.get("chi2_filter_note"):
        console.print(f"  [dim]{result['chi2_filter_note']}[/dim]")

    for c in result["candidates"]:
        line = (f"  A={c['A']}, B={c['B']}, C={c['C']}, D={c['D']} "
                f"(col1={c['col1_total']}, col2={c['col2_total']})")
        if "calculated_chi2" in c:
            mark = "[green]✓[/green]" if c.get("chi2_match") else "[red]✗[/red]"
            line += f" χ²={c['calculated_chi2']:.4f} {mark}"
        console.print(line)
    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("flag-uninformative")
def flag_uninformative_cmd(
    means: str = typer.Option(..., "--means", "-m"),
    sds: str = typer.Option(..., "--sds", "-s"),
    ns: str = typer.Option(..., "--ns", "-n"),
    reported_p: Optional[float] = typer.Option(None, "--reported-p", "-p"),
    decimals_mean: int = typer.Option(2, "--dm"),
    decimals_sd: int = typer.Option(2, "--ds"),
    significance_threshold: float = typer.Option(0.05, "--alpha"),
    p_range_warn: float = typer.Option(0.5, "--p-range-warn"),
    num_samples: int = typer.Option(3000, "--samples"),
    seed: int = typer.Option(0, "--seed"),
):
    """Flag NHST comparisons whose precision is too coarse to pin down the result."""
    means_l = _floats(means, "--means")
    sds_l = _floats(sds, "--sds")
    ns_l = _ints(ns, "--ns")
    result = heuristics_module.flag_uninformative_stat(
        means_l, sds_l, ns_l, reported_p, decimals_mean, decimals_sd,
        significance_threshold=significance_threshold,
        p_range_warn=p_range_warn, num_samples=num_samples, seed=seed,
    )
    sev = result["severity"]
    color = _severity_color(sev)
    console.print(f"[{color}]{sev.upper()}[/{color}]: {result['explanation']}")
    console.print(f"\n[bold]Implied p range:[/bold] [{result['p_min']:.4f}, {result['p_max']:.4f}]")
    console.print(f"[bold]Implied F range:[/bold] [{result['f_min']:.4f}, {result['f_max']:.4f}]")
    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("flag-round-n")
def flag_round_n_cmd(
    ns: str = typer.Option(..., "--ns", help="Comma-separated sample sizes (e.g., '100,200,300')"),
    moderate_modulus: int = typer.Option(50, "--moderate", help="Modulus for the 'suspicious' tier"),
    strong_modulus: int = typer.Option(100, "--strong", help="Modulus for the 'highly_suspicious' tier"),
):
    """Heuristic flag for suspiciously round sample sizes."""
    n_list = _ints(ns, "--ns")
    result = heuristics_module.flag_round_n(n_list, moderate_modulus, strong_modulus)
    sev = result["severity"]
    color = _severity_color(sev)
    console.print(f"[{color}]{sev.upper()}[/{color}]: {result['explanation']}")
    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("sd-or-se")
def sd_or_se(
    reported_value: float = typer.Argument(..., help="Reported dispersion value"),
    n: int = typer.Argument(..., help="Sample size"),
    reported_as: str = typer.Option("unknown", "--as", help="How the paper labels it: 'SD', 'SE', or 'unknown'"),
    plausible_sd_max: Optional[float] = typer.Option(None, "--max-sd", help="Hard upper bound on plausible SD"),
    range_min: Optional[float] = typer.Option(None, "--range-min", help="Variable minimum (with --range-max)"),
    range_max: Optional[float] = typer.Option(None, "--range-max", help="Variable maximum (with --range-min)"),
    decimals: Optional[int] = typer.Option(None, "--decimals", help="Printed decimals of the reported value. Under the SE reading the rounding interval is stretched by sqrt(n); without this the ceiling gets a flat 1% margin, which is a guess."),
    bound_source: str = typer.Option("assumed", "--bound-source", help="stated|logically_necessary|assumed -- who supplied the range/ceiling. A 'neither reading fits' verdict against an assumed bound caps at 'suspicious'."),
):
    """Adjudicate whether a reported value is more plausibly an SD or an SE."""
    rng = (range_min, range_max) if (range_min is not None and range_max is not None) else None
    result = se_sd_module.check_sd_or_se(
        reported_value, n, reported_as, plausible_sd_max, rng, decimals=decimals,
        bound_source=bound_source,
    )

    sev = result["severity"]
    color = _severity_color(sev)
    console.print(f"[{color}]{sev.upper()}[/{color}]: likely interpretation = "
                  f"{result['likely_interpretation']}")
    console.print(f"\n[bold]As SD:[/bold] SD={result['as_sd']['implied_sd']:.4g}, "
                  f"implied SE={result['as_sd']['implied_se']:.4g}, "
                  f"plausible={result['as_sd'].get('sd_plausible')}")
    console.print(f"[bold]As SE:[/bold] SE={result['as_se']['implied_se']:.4g}, "
                  f"implied SD={result['as_se']['implied_sd']:.4g}, "
                  f"plausible={result['as_se'].get('sd_plausible')}")
    console.print(f"\n{result['explanation']}")
    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command()
def debit(
    mean: float = typer.Argument(..., help="Reported mean (proportion in [0,1])"),
    sd: float = typer.Argument(..., help="Reported standard deviation"),
    n: int = typer.Argument(..., help="Sample size"),
    decimals_mean: int = typer.Option(2, "--decimals-mean", help="Decimal places in reported mean"),
    decimals_sd: int = typer.Option(2, "--decimals-sd", help="Decimal places in reported SD"),
    data_type: Optional[str] = typer.Option(None, "--data-type", help="binary|proportion. DEBIT REFUSES on anything else."),
):
    """Run DEBIT on a binary 0/1 variable's mean+SD+n."""
    result = debit_module.debit_test(
        mean, sd, n, decimals_mean, decimals_sd,
        data_type=data_type if data_type is not None else "binary",
    )
    if not result.get("applicable", True):
        print_severity(result)
        console.print(f"\n[dim]{result.get('methodology', '')}[/dim]")
        return

    if result["consistent"]:
        console.print(f"[green]CONSISTENT[/green]: {result['explanation']}")
    else:
        console.print(f"[red]IMPOSSIBLE[/red]: {result['explanation']}")

    if result.get("candidates"):
        console.print("\n[bold]Candidate (k → expected SD) for the reported mean:[/bold]")
        for c in result["candidates"][:10]:
            mark = "[green]✓[/green]" if c["consistent"] else " "
            console.print(
                f"  {mark} k={c['k']:>4d}, prop={c['implied_proportion']:.4f}, "
                f"expected SD={c['expected_sample_sd']:.{decimals_sd + 2}f}, "
                f"|Δ|={c['deviation']:.{decimals_sd + 2}f}"
            )

    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("effect-size-from-f")
def effect_size_from_f_cmd(
    f_value: float = typer.Argument(..., help="Reported F statistic"),
    df1: int = typer.Argument(..., help="Numerator degrees of freedom. REQUIRED -- assuming 1 collapses the formula to F/(F+df2)"),
    df2: int = typer.Argument(..., help="Denominator (error) degrees of freedom"),
    reported: Optional[float] = typer.Option(None, "--reported", "-e", help="The effect size the paper printed"),
    measure: str = typer.Option("partial_eta_squared", "--measure", "-m", help="partial_eta_squared | cohens_f (others are refused by name)"),
    decimals_f: Optional[int] = typer.Option(None, "--decimals-f", help="Printed decimals of the F"),
    decimals_effect_size: Optional[int] = typer.Option(None, "--decimals-effect-size", help="Printed decimals of the effect size"),
):
    """Reconcile a printed effect size against the F and df beside it."""
    from .tools.effect_size_from_f import effect_size_from_f

    result = effect_size_from_f(
        f_value, df1, df2, reported_effect_size=reported, measure=measure,
        decimals_f=decimals_f, decimals_effect_size=decimals_effect_size)
    bail_on_error(result)
    print_severity(result)
    if result.get("applicable"):
        lo, hi = result["achievable_interval"]
        console.print(f"\n[bold]F({df1}, {df2}) = {f_value}[/bold]  "
                      f"[dim]{result['formula']}[/dim]")
        console.print(f"[bold]{result['canonical_measure']}:[/bold] "
                      f"{result['computed']:.4g}  "
                      f"achievable [{lo:.4g}, {hi:.4g}]")
    if result.get("alternative_reading"):
        console.print(f"\n[dim]{result['alternative_reading']}[/dim]")


@app.command("f-to-p")
def f_to_p(
    f_value: float = typer.Argument(..., help="Reported F statistic"),
    df1: int = typer.Argument(..., help="Numerator degrees of freedom (between)"),
    df2: Optional[int] = typer.Argument(
        None, help="Denominator degrees of freedom (within), ONLY if the "
                   "paper prints it. Omit when unstated: the check then "
                   "sweeps every df2 and accuses only when none explains "
                   "the reported p. An inferred df2 is an assumed bound."),
    reported_p: Optional[float] = typer.Option(None, "--reported-p", "-p", help="Reported p-value"),
    decimals_p: Optional[int] = typer.Option(None, "--decimals-p", help="Printed decimals of reported_p."),
    decimals_f: Optional[int] = typer.Option(None, "--decimals-f", help="Printed decimals of the F statistic."),
):
    """Verify F-to-p conversion (works for one-way, two-way, or N-way ANOVA)."""
    result = anova_module.recalc_f_to_p(f_value, df1, df2, reported_p,
                                        decimals_p=decimals_p, decimals_f=decimals_f)
    bail_on_error(result)
    if df2 is None:
        lo, hi = result["achievable_p_range_over_df2"]
        console.print(f"[bold]F({df1}, ?):[/bold] {f_value}  [dim](df2 unstated)[/dim]")
        console.print(f"[bold]Achievable p over all df2:[/bold] [{lo:.3g}, {hi:.3g}]")
    else:
        console.print(f"[bold]F({df1}, {df2}):[/bold] {f_value}")
        console.print(f"[bold]Calculated p:[/bold] {result['calculated_p']:.6g}")
    if reported_p is not None:
        if result.get("p_matches"):
            console.print(f"\n[green]MATCHES reported p ({reported_p})[/green]")
        else:
            console.print(f"\n[red]DOES NOT MATCH reported p ({reported_p})[/red]")
    if result.get("explanation"):
        console.print(f"\n{result['explanation']}")
    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command()
def csf(
    p_values: str = typer.Option(..., "--p-values", "-p", help="Comma-separated p-values from baseline comparisons"),
    method: str = typer.Option("stouffer", "--method", "-m", help="Combination method: 'stouffer' or 'fisher'"),
    design: Optional[str] = typer.Option(None, "--design", help="e.g. parallel_rct, cluster_randomized, stratified. Cluster/stratified/crossover/matched break independence BY DESIGN and are REFUSED."),
    correlation: Optional[float] = typer.Option(None, "--correlation", help="Equicorrelation among baseline variables, if genuinely known. Omitted -> sensitivity analysis across rho."),
):
    """Test for suspiciously uniform baseline distributions (CSF test)."""
    p_list = _floats(p_values, "--p-values")

    result = csf_module.csf_test(p_list, method, correlation=correlation, design=design)

    if result.get("applicable") is False:
        print_severity(result)
        console.print(f"\n[dim]{result.get('methodology', '')}[/dim]")
        return

    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Similarity p-value:[/bold] {result['similarity_p']:.6f} (small ⇒ groups too similar)")
    console.print(f"[bold]Method:[/bold] {result['method']}")
    console.print(f"[bold]Number of tests:[/bold] {result['num_tests']}")
    console.print(f"[bold]Mean p-value:[/bold] {result['mean_p']:.4f}")

    if result.get("sensitivity_profile"):
        prof = result["sensitivity_profile"]
        console.print(f"[bold]Evaluated at rho:[/bold] {result['correlation_used']}"
                      + ("" if result.get("correlation_assumed") else " (verdict rho)"))
        console.print("[bold]Sensitivity across rho:[/bold] "
                      + "  ".join(f"{r}:{p:.4g}" for r, p in sorted(prof.items())))

    console.print()
    print_severity(result)

    if design is None:
        console.print(
            "\n[yellow]Design not stated:[/yellow] pass [bold]--design[/bold]. Stratified, minimised, "
            "cluster and matched allocation force baseline balance BY CONSTRUCTION and would explain "
            "extreme uniformity innocently, so an unstated design caps the verdict below "
            "`highly_suspicious`."
        )

    console.print(f"\n[dim]{result['methodology']}[/dim]")
    if result.get("caveat"):
        console.print(f"\n[yellow]Caveat: {result['caveat']}[/yellow]")


@app.command()
def multiplicity(
    p_values: str = typer.Option(..., "--p-values", "-p", help="Comma-separated p-values for ONE family of tests. Entries written as thresholds ('<.05') are dropped, not coerced, and counted separately."),
    family_label: str = typer.Option(..., "--family-label", help="Describe the family you chose (e.g. 'nine cognitive outcomes, 3x3 design'). Family definition is a judgement the tool cannot make for you."),
    alpha: float = typer.Option(0.05, "--alpha", "-a", help="Significance threshold the paper used"),
):
    """Multiple-comparisons arithmetic for one family: FWER, Bonferroni, Holm, BH, BY."""
    # Typer's `...` makes the FLAG required, not its VALUE. `--family-label ""`
    # satisfied it and printed the whole correction table -- FWER, Bonferroni,
    # Holm, BH, BY and a claim-loss count -- under `Family:` and nothing else.
    # The MCP adapter (`registry._multiplicity_adapter`) refuses that same call,
    # so one surface answered what the other declined; the gate has to hold on
    # both or it does not hold. Wording is kept in step with that adapter.
    if not family_label.strip():
        console.print(
            "[red]Error: --family-label must NAME the family; it has no default.[/red]"
        )
        console.print(
            "Not evaluated. What counts as a FAMILY of tests is a judgement the tool cannot "
            "make for you, and the same p-values give different answers under different "
            "families. Name the family you chose -- 'the nine cognitive outcomes of the 3x3 "
            "design', 'the six post-hoc contrasts within the significant omnibus F' -- and run "
            "this once per family. A blank label pools the paper into one family, which is the "
            "lumping this tool exists to prevent."
        )
        raise typer.Exit(1)

    tests: List[StatisticalTest] = []
    n_threshold = 0
    for i, raw in enumerate(p_values.split(","), start=1):
        token = raw.strip()
        if not token:
            continue
        # A threshold is a BOUND, not a value. Treating "p < .05" as p = .05
        # would silently change which results are counted as surviving, so it
        # is excluded and reported instead.
        if token[0] in "<>≤≥":
            n_threshold += 1
            continue
        try:
            p = float(token)
        except ValueError:
            console.print(f"[red]Error: could not read '{token}' as a p-value.[/red]")
            raise typer.Exit(1)
        tests.append(StatisticalTest(id=f"t{i}", test_type="unspecified", location="", p_value=p))

    result = _multiplicity_report_fn(tests, alpha=alpha, family_label=family_label)
    if result.get("n_tests", 0) == 0:
        console.print(f"[yellow]{result.get('note', 'nothing to compute')}[/yellow]")
        return

    console.print(f"[bold]Family:[/bold] {result['family']}")
    console.print(f"[bold]Uncorrected tests:[/bold] {result['n_tests']} at alpha={result['alpha']}")
    console.print(f"[bold]FWER if independent:[/bold] {result['fwer_if_independent'] * 100:.1f}% "
                  "[dim](upper bound)[/dim]")
    console.print(f"[bold]Expected false positives:[/bold] {result['expected_false_positives']:.1f}")
    console.print(f"[bold]Bonferroni threshold:[/bold] {result['bonferroni_threshold']:.6g}")
    # Each step-up/step-down threshold is the value the LAST surviving test had
    # to clear, so `none` means no p-value cleared the first step -- printed
    # rather than blanked, because a reader reproducing this needs to know the
    # method ran and rejected nothing.
    for label, key in (("Holm threshold (last step)", "holm_threshold"),
                       ("BH threshold", "bh_threshold"),
                       ("BY threshold", "by_threshold")):
        v = result.get(key)
        console.print(f"[bold]{label}:[/bold] {v:.6g}" if v is not None else
                      f"[bold]{label}:[/bold] none (no p-value clears the step)")

    console.print()
    lost = result["n_claims_lost_to_correction"]
    color = "red" if lost else "green"
    console.print(f"[bold]Significant uncorrected:[/bold] {result['n_significant_uncorrected']}")
    console.print(f"[bold]Survive Bonferroni:[/bold] {result['n_significant_bonferroni']} "
                  "[dim](family-wise)[/dim]")
    console.print(f"[bold]Survive Holm:[/bold] {result['n_significant_holm']} "
                  "[dim](family-wise, step-down; never fewer than Bonferroni)[/dim]")
    console.print(f"[bold]Survive Benjamini-Hochberg:[/bold] {result['n_significant_bh']} "
                  "[dim](FDR)[/dim]")
    console.print(f"[bold]Survive Benjamini-Yekutieli:[/bold] {result['n_significant_by']} "
                  "[dim](FDR under arbitrary dependence -- the honest one for correlated "
                  "outcomes)[/dim]")
    console.print(f"[bold]Surviving claims:[/bold] between {result['n_surviving_floor']} "
                  f"({result['floor_method']}) and {result['n_surviving_ceiling']} "
                  f"({result['ceiling_method']})")
    console.print(f"[{color}]Claims lost to correction: {lost}[/{color}] "
                  "[dim](read off Benjamini-Hochberg, the most permissive of the four, so "
                  "this is the smallest loss they support)[/dim]")

    if result.get("internal_inconsistency"):
        console.print("[red]Internal inconsistency: BH rejected more than the uncorrected rule. "
                      "The arithmetic is wrong -- do not report this.[/red]")
    if result.get("n_missing_p"):
        console.print(f"[yellow]{result['n_missing_p']} test(s) in the family had no readable "
                      "p-value; they widen the family but cannot be counted as significant.[/yellow]")
    if n_threshold:
        console.print(f"[yellow]{n_threshold} test(s) reported p as a threshold rather than a "
                      "value and were excluded; the family is that much larger than counted "
                      "here.[/yellow]")

    console.print()
    console.print(f"[dim]{result['interpretation']}[/dim]")
    for caveat in result.get("caveats", []):
        console.print(f"[dim]- {caveat}[/dim]")


@app.command()
def chi2(
    observed: str = typer.Option(..., "--observed", "-o", help="Contingency table: semicolon-separated rows, comma-separated values (e.g., '10,20;15,25')"),
    reported_chi2: Optional[float] = typer.Option(None, "--reported-chi2", "-c", help="Reported chi-squared statistic"),
    reported_p: Optional[float] = typer.Option(None, "--reported-p", "-p", help="Reported p-value"),
    yates: bool = typer.Option(False, "--yates", "-y", help="Apply Yates' continuity correction"),
):
    """Recalculate chi-squared test from contingency table."""
    rows = [[int(x.strip()) for x in row.split(",")] for row in observed.split(";")]

    result = chi_squared.recalc_chi_squared(rows, reported_chi2, reported_p, yates)
    bail_on_error(result)

    console.print(f"[bold]Calculated chi²:[/bold] {result['calculated_chi2']:.4f}")
    console.print(f"[bold]Calculated p:[/bold] {result['calculated_p']:.6f}")
    console.print(f"[bold]Degrees of freedom:[/bold] {result['df']}")
    console.print(f"[bold]Test type:[/bold] {result['test_type']}")

    if "fisher_p" in result:
        console.print(f"[bold]Fisher's exact p:[/bold] {result['fisher_p']:.6f}")

    if reported_chi2 is not None:
        if result.get("chi2_matches"):
            console.print(f"\n[green]Chi² MATCHES reported value ({reported_chi2})[/green]")
        else:
            console.print(f"\n[red]Chi² DOES NOT MATCH reported value ({reported_chi2})[/red]")

    if reported_p is not None:
        if result.get("p_matches"):
            console.print(f"[green]P-value MATCHES reported value ({reported_p})[/green]")
        else:
            console.print(f"[red]P-value DOES NOT MATCH reported value ({reported_p})[/red]")

    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command()
def grimmer(
    mean: float = typer.Argument(..., help="Reported mean"),
    sd: float = typer.Argument(..., help="Reported standard deviation"),
    n: int = typer.Argument(..., help="Sample size"),
    scale_min: int = typer.Option(1, "--scale-min", help="Minimum scale value"),
    scale_max: int = typer.Option(7, "--scale-max", help="Maximum scale value"),
    decimals: int = typer.Option(2, "--decimals", help="Decimal places in reported mean (as PRINTED)"),
    decimals_sd: Optional[int] = typer.Option(None, "--decimals-sd", help="Decimal places in reported SD (as PRINTED; inferred if omitted)"),
    data_type: Optional[str] = typer.Option(None, "--data-type", help="integer|likert|count|binary|proportion|continuous. GRIMMER REFUSES on non-integer data."),
    discreteness_source: str = typer.Option("assumed", "--discreteness-source", help="stated|logically_necessary|assumed -- who says the observations are WHOLE NUMBERS. Assumed caps a granularity failure at `suspicious`."),
):
    """Run GRIMMER test to check if SD is consistent with integer data."""
    result = sd_checks.grimmer_test(
        mean, sd, n, scale_min, scale_max, decimals, decimals_sd,
        data_type=data_type if data_type is not None else "integer",
        discreteness_source=discreteness_source,
    )
    if not result.get("applicable", True):
        print_severity(result)
        console.print(f"\n[dim]{result.get('methodology', '')}[/dim]")
        return
    bail_on_error(result)

    if result["consistent"]:
        console.print(f"[green]CONSISTENT[/green]: SD {sd} is possible for mean={mean}, n={n}")
    else:
        # The severity the tool returned, not a hard-coded "IMPOSSIBLE" -- same
        # renderer overclaim `metascience grim` had.
        sev = result.get("severity")
        console.print(f"[red]INCONSISTENT[/red]: SD {sd} is "
                      f"{'IMPOSSIBLE' if sev == 'impossible' else str(sev).upper()} "
                      f"for mean={mean}, n={n}")
        if result.get("failure_reason"):
            console.print(f"  [red]{result['failure_reason']}[/red]")
        if result.get("discreteness_caveat"):
            console.print(f"  [yellow]{result['discreteness_caveat']}[/yellow]")

    console.print(f"\n[bold]Reported mean:[/bold] {result['reported_mean']}")
    console.print(f"[bold]Reported SD:[/bold] {result['reported_sd']}")
    console.print(f"[bold]GRIM-consistent sums:[/bold] {result['candidate_sums']}")
    console.print(f"[bold]Implied sum of squares (point):[/bold] {result['implied_sum_squares']:.4f}")

    if result.get("working_combinations"):
        console.print("\n[bold]Valid (sum, sum-of-squares) combinations:[/bold]")
        for combo in result["working_combinations"]:
            console.print(
                f"  S={combo['sum']}, Q={combo['sum_squares']} → "
                f"mean={combo['exact_mean']}, SD={combo['exact_sd']}"
            )

    console.print(f"\n[dim]{result['methodology']}[/dim]")
    warn_if_assumed(result, data_type, scale=f"{scale_min}-{scale_max}", effective="integer")


@app.command("regression-batch")
def regression_batch_cmd(
    json_path: Path = typer.Argument(..., help="JSON file: a list of coefficient rows"),
):
    """Verify every regression coefficient in one pass.

    JSON schema: a list of
        {"b": B, "se": SE, "reported_t": t, "reported_p": p, "df": N, "label": "..."}

    Pass `df` where the paper gives it: without it a t cannot be converted to a
    p, and the row is reported `indeterminate` with nothing checked.
    """
    if not json_path.exists():
        console.print(f"[red]File not found: {json_path}[/red]")
        raise typer.Exit(1)
    rows = json.loads(json_path.read_text())
    if not isinstance(rows, list):
        console.print("[red]JSON root must be a list of row objects[/red]")
        raise typer.Exit(1)

    from .tools import regression as _reg

    result = _reg.check_regression_batch(rows)
    color = _severity_color(result["severity"])
    console.print(f"[{color}]{result['severity'].upper()}[/{color}]: {result['explanation']}")

    table = Table(title="Regression coefficients")
    for c in ("row", "label", "B", "SE", "computed t", "reported", "verdict"):
        table.add_column(c)
    for r in result["results"]:
        rep = r.get("reported_t")
        if rep is None:
            rep = r.get("reported_p")
        table.add_row(
            str(r.get("row")), str(r.get("label", "")),
            f"{r['b']:g}" if "b" in r else "-",
            f"{r['se']:g}" if "se" in r else "-",
            f"{r['calculated_t']:.4g}" if "calculated_t" in r else "-",
            "-" if rep is None else f"{rep:g}",
            str(r.get("severity", r.get("error", "?"))),
        )
    console.print(table)


@app.command("summation-batch")
def summation_batch_cmd(
    json_path: Path = typer.Argument(..., help="JSON file: a list of summation rows"),
    tolerance: Optional[float] = typer.Option(None, "--tolerance", "-t",
                                    help="Batch-wide EXPLICIT window. Omit it: without a "
                                         "tolerance each row's window is computed from its "
                                         "own printed precision, which is what you want. "
                                         "Setting it overrides every row's `decimals`."),
):
    """Check every summation in one pass.

    JSON schema: a list of
        {"values": [..], "expected_sum": N, "description": "...",
         "decimals": 1, "decimals_total": 0, "tolerance": 0.5}

    Give `decimals` per row -- the window a sum is allowed depends on how many
    addends there are and how precisely each was printed, so one window across
    a whole batch is wrong for most of it. A row with no precision and no
    tolerance returns `indeterminate` rather than guessing.

    `--tolerance` defaulted to 0.5, which is not None, so it silently overrode
    every row's `decimals` and the printed-precision window could never fire on
    this path. It is now opt-in.
    """
    if not json_path.exists():
        console.print(f"[red]File not found: {json_path}[/red]")
        raise typer.Exit(1)
    rows = json.loads(json_path.read_text())
    if not isinstance(rows, list):
        console.print("[red]JSON root must be a list of row objects[/red]")
        raise typer.Exit(1)

    result = summation_module.check_summation_batch(rows, tolerance)
    color = _severity_color(result["severity"])
    console.print(f"[{color}]{result['severity'].upper()}[/{color}]: {result['explanation']}")

    table = Table(title="Summations")
    for c in ("row", "description", "actual", "expected", "difference", "verdict"):
        table.add_column(c)
    # Never scientific notation: these are participant counts and percentages,
    # and "3.051e+05" is unreadable where "305085" is the number in the paper.
    def fmt(x, signed=False):
        if x is None:
            return "-"
        s = f"{x:+.6g}" if signed else f"{x:.6g}"
        return s if "e" not in s else (f"{x:+,.2f}" if signed else f"{x:,.2f}")

    for r in result["results"]:
        table.add_row(
            str(r.get("row")), str(r.get("description", "")),
            fmt(r.get("actual_sum")), fmt(r.get("expected_sum")),
            fmt(r.get("difference"), signed=True),
            str(r.get("severity", r.get("error", "?"))),
        )
    console.print(table)


@app.command("findings-query")
def findings_query_cmd(
    project_dir: Path = typer.Argument(..., help="Corpus root"),
    technique: Optional[str] = typer.Option(None, "--technique"),
    min_severity: Optional[int] = typer.Option(None, "--min-severity", min=1, max=9),
    producer: Optional[str] = typer.Option(None, "--producer"),
    journal: Optional[str] = typer.Option(None, "--journal", help="Substring match on the normalized journal name"),
    year: Optional[int] = typer.Option(None, "--year"),
    impossible_only: bool = typer.Option(False, "--impossible-only"),
    from_db: Optional[bool] = typer.Option(
        None, "--from-db/--files",
        help="Answer from the local findings database / from a file scan. "
             "Default: the DB whenever a URL resolves (env or repo .env), "
             "files otherwise."),
):
    """Query findings-v2 documents across a corpus; JSON rows to stdout.

    The DB is the primary path (same semantics, SQL); the file scan is the
    offline fallback and stays byte-comparable -- `--from-db`/`--files`
    forces either side, which is how the two implementations are checked
    against each other.
    """
    from metascience_agent import db_push as _db
    if from_db is None:
        from_db = bool(_db.resolve_db_url())
    if from_db:
        try:
            rows = _db.query_findings(
                project_dir.name, technique=technique,
                min_severity=min_severity, producer=producer,
                journal=journal, year=year, impossible_only=impossible_only)
        except _db.DbUnavailable as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)
        print(json.dumps(rows, indent=2, default=str))
        return
    import glob as _glob
    rows = []
    for fp in sorted(_glob.glob(str(project_dir / "*" / "findings.v2.json"))) +             sorted(_glob.glob(str(project_dir / "*" / "forensic_review*" / "findings.v2.json"))):
        try:
            doc = json.loads(Path(fp).read_text())
        except Exception:
            continue
        pm = doc.get("paper_metadata") or {}
        j = pm.get("journal_normalized") or pm.get("journal") or ""
        for f in doc.get("findings") or []:
            if not isinstance(f, dict) or f.get("outcome") != "problem":
                continue
            if (f.get("adjudication") or {}).get("action") == "discarded":
                continue
            sev = f.get("severity")
            if technique and f.get("technique") != technique:
                continue
            if producer and f.get("producer") != producer:
                continue
            if min_severity and not (isinstance(sev, int) and sev >= min_severity):
                continue
            if journal and journal.lower() not in j.lower():
                continue
            if year and pm.get("year") != year:
                continue
            if impossible_only and not f.get("impossible"):
                continue
            rows.append({"finding_id": f.get("finding_id"),
                         "paper_id": doc.get("paper_id"),
                         "run_id": doc.get("run_id"),
                         "technique": f.get("technique"),
                         "producer": f.get("producer"),
                         "severity": sev,
                         "severity_is_provisional": f.get("severity_is_provisional"),
                         "impossible": f.get("impossible"),
                         "title": f.get("title"),
                         "journal": j, "year": pm.get("year")})
    print(json.dumps(rows, indent=2, default=str))


@app.command("draft-pubpeer")
def draft_pubpeer_cmd(
    paper_dir: Path = typer.Argument(...),
    findings: Optional[str] = typer.Option(None, "--findings", help="Comma-separated finding_ids or slugs (default: every kept problem)"),
    model: str = typer.Option("sonnet", "--model"),
    json_out: bool = typer.Option(False, "--json", help="Emit the result record as JSON"),
):
    """Draft a PubPeer comment from stored findings. NEVER posts anywhere."""
    from metascience_agent import drafts as _d
    rec = _d.generate(paper_dir, "pubpeer",
                      finding_ids=findings.split(",") if findings else None,
                      model=model)
    if json_out:
        print(json.dumps(rec, default=str))
        raise typer.Exit(0 if rec.get("ok") else 2)
    if not rec.get("ok"):
        console.print(f"[red]{rec['error']}[/red]")
        raise typer.Exit(2)
    console.print(f"[green]draft written:[/green] {rec['path']} "
                  f"({rec['n_findings']} finding(s))")


@app.command("draft-letter")
def draft_letter_cmd(
    paper_dir: Path = typer.Argument(...),
    findings: Optional[str] = typer.Option(None, "--findings"),
    model: str = typer.Option("sonnet", "--model"),
    json_out: bool = typer.Option(False, "--json", help="Emit the result record as JSON"),
):
    """Draft a letter to the editor from stored findings. NEVER posts."""
    from metascience_agent import drafts as _d
    rec = _d.generate(paper_dir, "letter",
                      finding_ids=findings.split(",") if findings else None,
                      model=model)
    if json_out:
        print(json.dumps(rec, default=str))
        raise typer.Exit(0 if rec.get("ok") else 2)
    if not rec.get("ok"):
        console.print(f"[red]{rec['error']}[/red]")
        raise typer.Exit(2)
    console.print(f"[green]draft written:[/green] {rec['path']}")


@app.command("gen-webapp-constants")
def gen_webapp_constants_cmd():
    """Regenerate the checked-in ladder artifacts from the Python sources.

    Writes BOTH `webapp/lib/constants.gen.ts` (typed, for the Next.js app)
    and `docs/severity_ladder.json` (for everything else). Both are CHECKED
    IN -- the webapp must work on a checkout with no Python -- and
    tests/test_webapp_constants.py regenerates and byte-compares each, so
    forgetting to run this fails the suite instead of shipping a divergent
    ladder.
    """
    from metascience_agent.webapp_constants import write
    for path in write():
        console.print(f"wrote {path}")


@app.command("db-push")
def db_push_cmd(
    target: Path = typer.Argument(..., help="A paper directory or a corpus root"),
    db_url: Optional[str] = typer.Option(None, "--db-url", help="Postgres connection string (default: $METASCIENCE_DB_URL)"),
    retry_pending: bool = typer.Option(False, "--retry-pending", help="Drain the corpus's db_push_pending.jsonl instead of pushing fresh"),
):
    """Push findings-v2 documents into the local findings database.

    One transaction per run, replace-within-run; screens are never touched
    by file pushes; orphaned review verdicts are PRINTED, never dropped.
    Best-effort at run completion (the auto-push hook); this verb is the
    explicit/bulk form.
    """
    from metascience_agent import db_push as _db
    try:
        if retry_pending:
            rec = _db.retry_pending(target, db_url=db_url)
            console.print(f"retried {rec['retried']}, remaining {rec['remaining']}")
            return
        if not target.is_dir():
            console.print(f"[red]Not a directory: {target}[/red]")
            raise typer.Exit(1)
        if list(target.glob("forensic_review*")) \
                or (target / "findings.v2.json").exists():
            papers = [target]
        else:
            # The canonical enumeration -- done/<slug> and batch folders
            # hold papers too (the flat scan left every archived paper
            # out of the database; caught by corpus-stats --verify).
            from metascience_agent.webapp_index import iter_paper_dirs
            papers = iter_paper_dirs(target)
        n_runs = 0
        orphans = 0
        for paper in papers:
            for rec in _db.push_paper(paper, db_url=db_url,
                                      corpus=target.name):
                if "reviews" in rec:      # the per-paper review-mirror record
                    r = rec["reviews"]
                    if r.get("pushed"):
                        console.print(f"[green]{rec['paper']}[/green]: "
                                      f"{r['pushed']} review verdict(s) mirrored")
                    for key in r.get("unmatched") or []:
                        console.print(f"[yellow]review verdict with no DB "
                                      f"run[/yellow] {rec['paper']}: {key}")
                    continue
                n_runs += 1
                for key in rec.get("review_orphans") or []:
                    orphans += 1
                    console.print(f"[yellow]orphaned review verdict[/yellow] "
                                  f"{rec['paper']}: {key}")
        console.print(f"pushed {n_runs} run(s) from {len(papers)} paper(s); "
                      f"{orphans} orphaned review verdict(s) reported")
    except _db.DbUnavailable as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2)


@app.command("migrate-v2")
def migrate_v2_cmd(
    target: Path = typer.Argument(..., help="A paper directory or a corpus root"),
    force: bool = typer.Option(False, "--force", help="Re-convert even when the source is unchanged"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Report what would convert; write nothing"),
):
    """One-way legacy conversion: v1 findings -> findings.v2.json beside them.

    Never overwrites a v1 file and never rewrites review.json. Runs with no
    version number get pipeline_version 0.0.1; mtime-backdated dates carry
    analysed_at_source "file_mtime". Unconvertible runs get a named
    findings.v2.skipped.json, and the corpus report counts review-verdict
    orphans (a human decision that no longer joins to any converted row).
    """
    from metascience_agent import migrate_v2 as _m
    if not target.exists():
        console.print(f"[red]Not found: {target}[/red]")
        raise typer.Exit(1)
    if (target / "review.json").exists() or list(target.glob("forensic_review*")) \
            or (target / "image_duplication_findings.json").exists():
        report = _m.convert_paper(target, force=force, dry_run=dry_run)
        console.print_json(json.dumps(report, default=str))
        return
    report = _m.convert_tree(target, force=force, dry_run=dry_run)
    console.print(
        f"converted {report['n_converted']}, skipped {report['n_skipped']}, "
        f"review orphans {report['n_review_orphans']}"
        + (" (dry run -- nothing written)" if dry_run else
           f" -> {target / 'migration_report.json'}"))
    for reason, n in sorted(report["by_reason"].items()):
        console.print(f"  skipped {n}: {reason}")


@app.command("corpus-stats")
def corpus_stats_cmd(
    root: Path = typer.Argument(..., help="Corpus root (papers as subdirectories)"),
    out: Optional[Path] = typer.Option(None, "--out", "-o",
                                       help="Write corpus_stats.json here (default: <root>/corpus_stats.json)"),
    stdout: bool = typer.Option(False, "--stdout", help="Print the JSON instead of summarizing"),
    from_db: bool = typer.Option(
        False, "--from-db",
        help="Aggregate from the local findings database instead of the "
             "file tree (same counting code, different rows)."),
    verify: bool = typer.Option(
        False, "--verify",
        help="Run BOTH modes and diff them (the two-source drift check); "
             "exits non-zero on any disagreement beyond the documented "
             "n_papers difference."),
):
    """Per-corpus fire-rate statistics from findings-v2 documents.

    Every rate names its denominator; "ran" includes ran_result_discarded
    (a channel that ran and retained nothing STILL RAN); discarded-by-
    adjudicator is split out of fires; screen flags are a funnel, never
    fires.
    """
    from metascience_agent import corpus_stats as _cs
    if not root.is_dir():
        console.print(f"[red]Not a directory: {root}[/red]")
        raise typer.Exit(1)
    if verify:
        from metascience_agent import db_push as _dbp
        try:
            file_stats = _cs.compute(root)
            db_stats = _cs.compute_from_db(root.name)
        except _dbp.DbUnavailable as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)
        diffs = _cs.diff_stats(file_stats, db_stats)
        if diffs:
            console.print(f"[red]DRIFT between file and DB stats "
                          f"({len(diffs)} difference(s)):[/red]")
            for d in diffs[:40]:
                console.print(f"  {d}")
            raise typer.Exit(1)
        console.print(
            f"[green]file and DB stats agree[/green] "
            f"({file_stats['n_papers_with_v2']} papers with v2; file "
            f"n_papers {file_stats['n_papers']} vs DB {db_stats['n_papers']} "
            "-- the documented unpushed-paper difference)")
        return
    if from_db:
        from metascience_agent import db_push as _dbp
        try:
            stats = _cs.compute_from_db(root.name)
        except _dbp.DbUnavailable as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)
    else:
        stats = _cs.compute(root)
    dest = out or (root / "corpus_stats.json")
    dest.write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")
    if stdout:
        console.print_json(json.dumps(stats, default=str))
        return
    console.print(f"{stats['corpus']}: {stats['n_papers_with_v2']}/"
                  f"{stats['n_papers']} papers with v2 findings -> {dest}")
    table = Table(title="Fires per technique")
    for c in ("technique", "computed_by", "ran", "fired", "rate",
              "impossible", "discarded"):
        table.add_column(c)
    for r in stats["per_technique"]:
        table.add_row(r["technique"], r["computed_by"],
                      str(r["n_papers_ran"]), str(r["n_papers_fired"]),
                      "-" if r["fire_rate"] is None else f"{r['fire_rate']:.1%}",
                      str(r["n_impossible"]),
                      str(r["n_discarded_by_adjudicator"]))
    console.print(table)


@app.command("flow-check")
def flow_check_cmd(
    json_path: Path = typer.Argument(
        ..., help="JSON file: the flow cascade -- either the stages list "
                  "itself or {\"stages\": [...], \"randomized_label\": ...}"),
    randomized_label: Optional[str] = typer.Option(
        None, "--randomized-label",
        help="Which stage anchors the analyzed<=randomized check, when no "
             "stage label contains 'random'."),
):
    """Reconcile a CONSORT/participant-flow cascade by exact integer arithmetic.

    JSON schema, top-down as the diagram reads:
        [{"label": "assessed", "n": 240,
          "excluded": [{"reason": "declined", "n": 12}],
          "arms": [{"label": "treatment", "n": 100}]}, ...]

    Counts of people carry no rounding window, so there is no tolerance. A
    missing or fractional n makes the check refuse rather than accuse; a drop
    with no stated exclusions is at most `suspicious`.
    """
    if not json_path.exists():
        console.print(f"[red]File not found: {json_path}[/red]")
        raise typer.Exit(1)
    payload = json.loads(json_path.read_text())
    if isinstance(payload, dict):
        stages = payload.get("stages")
        randomized_label = randomized_label or payload.get("randomized_label")
    else:
        stages = payload
    result = flow_module.check_flow_arithmetic(
        stages, randomized_label=randomized_label)
    print_severity(result)
    if result.get("failures"):
        table = Table(title="Flow identities that do not hold")
        for c in ("failure_mode", "stage", "expected", "observed", "difference"):
            table.add_column(c)
        for f in result["failures"]:
            table.add_row(f["failure_mode"], str(f.get("stage")),
                          str(f.get("expected")), str(f.get("observed")),
                          f"{f.get('difference'):+d}")
        console.print(table)
    bail_on_error(result)


@app.command()
def summation(
    values: str = typer.Option(..., "--values", "-v", help="Comma-separated values to sum"),
    expected: float = typer.Option(..., "--expected", "-e", help="Expected sum (e.g., 100 for percentages)"),
    tolerance: Optional[float] = typer.Option(None, "--tolerance", "-t", help="EXPLICIT window, overriding the rounding calculation. Use it only where something other than rounding sets the window -- a count column that must hold exactly takes --tolerance 0."),
    description: str = typer.Option("values", "--description", "-d", help="Description of what the values represent"),
    decimals: Optional[str] = typer.Option(None, "--decimals", help="Printed decimals of the addends: one int, or a comma-separated list, one per value. Without it the check REFUSES -- twenty values at 1 dp permit the total to be off by 1.0, two at 2 dp permit 0.01, and there is no safe default between them."),
    decimals_total: Optional[int] = typer.Option(None, "--decimals-total", help="Printed decimals of the expected sum. A percentage column is often totalled as a bare 100, which is 0 dp and worth 0.5 on its own."),
):
    """Check if values sum to expected total (e.g., percentages to 100)."""
    values_list = _floats(values, "--values")
    dp = None
    if decimals is not None:
        parts = _ints(decimals, "--decimals")
        dp = parts[0] if len(parts) == 1 else parts

    result = summation_module.check_summation(
        values_list, expected, tolerance, description,
        decimals=dp, decimals_total=decimals_total,
    )
    if result.get("severity") == "indeterminate" and result.get("error"):
        console.print(f"[cyan]INDETERMINATE[/cyan]: {result['error']}")
        console.print(f"\n[dim]{result['methodology']}[/dim]")
        raise typer.Exit(0)
    bail_on_error(result)

    if result["is_consistent"]:
        console.print(f"[green]CONSISTENT[/green]: {description} sum to {result['actual_sum']:.2f} (expected {expected})")
    else:
        console.print(f"[red]INCONSISTENT[/red]: {description} sum to {result['actual_sum']:.2f}, not {expected}")

    console.print(f"\n[bold]Actual sum:[/bold] {result['actual_sum']:.4f}")
    console.print(f"[bold]Expected sum:[/bold] {result['expected_sum']}")
    console.print(f"[bold]Difference:[/bold] {result['difference']:.4f}")

    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("check-ratio")
def check_ratio_cmd(
    numerator: float = typer.Option(..., "--numerator", help="Printed numerator (e.g. an incremental cost)"),
    denominator: float = typer.Option(..., "--denominator", help="Printed denominator (e.g. an incremental QALY)"),
    reported_ratio: float = typer.Option(..., "--reported-ratio", help="The ratio as printed (e.g. the ICER)"),
    decimals_numerator: Optional[int] = typer.Option(None, "--decimals-numerator", help="Printed decimals of the numerator. REQUIRED -- without it the check refuses."),
    decimals_denominator: Optional[int] = typer.Option(None, "--decimals-denominator", help="Printed decimals of the denominator. REQUIRED -- a quotient's tolerance depends on the denominator's magnitude as well as its precision."),
    decimals_ratio: Optional[int] = typer.Option(None, "--decimals-ratio", help="Printed decimals of the reported ratio. REQUIRED."),
    description: str = typer.Option("ratio", "--description", "-d", help="What the ratio represents"),
):
    """Verify a printed ratio against its own numerator and denominator.

    For ICERs, rates and any "X per Y". Read `implied_denominator` out of the
    output: across a TABLE of ratios, rows implying different values for a
    quantity that can only have one is the strong signal, not a single miss.
    """
    result = ratio_module.check_ratio(
        numerator=numerator, denominator=denominator,
        reported_ratio=reported_ratio,
        decimals_numerator=decimals_numerator,
        decimals_denominator=decimals_denominator,
        decimals_ratio=decimals_ratio, description=description,
    )
    if result.get("severity") == "indeterminate" and result.get("error"):
        console.print(f"[cyan]INDETERMINATE[/cyan]: {result['error']}")
        raise typer.Exit(0)
    bail_on_error(result)
    print_severity(result)
    lo, hi = result["attainable_ratio_interval"]
    console.print(f"\n[bold]Computed:[/bold] {result['computed_ratio']:.6g}   "
                  f"[bold]Reported:[/bold] {result['reported_ratio']:g}")
    console.print(f"[bold]Attainable over printed precision:[/bold] [{lo:.6g}, {hi:.6g}]")
    if result.get("implied_denominator") is not None:
        console.print(f"[bold]Denominator implied by the reported ratio:[/bold] "
                      f"{result['implied_denominator']:.6g} (printed {denominator})")
    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command()
def stalt(
    calculated_p: float = typer.Argument(..., help="The actual calculated p-value"),
    reported_threshold: str = typer.Option("<0.05", "--reported-threshold", "-t", help="How p-value was reported (e.g., '<0.05', '<0.001')"),
):
    """Detect suspiciously small p-values hidden behind thresholds (STALT)."""
    result = stalt_module.stalt_check(calculated_p, reported_threshold)
    bail_on_error(result)

    print_severity(result)

    console.print(f"\n[bold]Calculated p:[/bold] {result['calculated_p']:.2e}")
    console.print(f"[bold]Reported threshold:[/bold] {result['reported_threshold']}")
    console.print(f"[bold]Orders of magnitude smaller:[/bold] {result['orders_of_magnitude_smaller']:.1f}")

    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command()
def grimu(
    n1: int = typer.Argument(..., help="First group size"),
    n2: int = typer.Argument(..., help="Second group size"),
    reported_p: str = typer.Argument(..., help="Reported p-value, e.g. 0.171 or '<0.001'"),
    decimals: Optional[int] = typer.Option(None, "--decimals", "-d", help="Decimals in reported p (inferred if omitted)"),
    cc: str = typer.Option("both", "--cc", help="Continuity correction: none|cc|both"),
    method: str = typer.Option("normal", "--method", help="Reference engine: normal|exact|both"),
    one_sided: bool = typer.Option(False, "--one-sided", help="Reported p is one-sided"),
    test_type: str = typer.Option("mann_whitney", "--test-type", help="mann_whitney|wilcoxon; anything else is refused"),
    reported_z: Optional[float] = typer.Option(None, "--reported-z", help="The normal-approximation Z printed beside the p, if there is one"),
    p_source: str = typer.Option("unspecified", "--p-source", help="u_statistic|normal_z|unspecified"),
    ties_possible: bool = typer.Option(False, "--ties-possible", help="Outcome is a small-integer/ordinal scale, so ranks tie"),
):
    """GRIM-U: check a Mann-Whitney U / Wilcoxon rank-sum p-value against achievable granular values."""
    from .tools import grimu as grimu_module

    result = grimu_module.grimu_check(
        n1, n2, reported_p, decimals=decimals,
        continuity_correction=cc, method=method, one_sided=one_sided,
        test_type=test_type, reported_z=reported_z, p_source=p_source,
        ties_possible=ties_possible or None,
    )
    bail_on_error(result)
    print_severity(result)
    # A REFUSAL HAS NO LATTICE TO PRINT. `mU`/`sdU`/`floor_p` only exist on an
    # evaluated result; reaching for them after an applicability guard fired
    # turned a clean refusal into a KeyError traceback.
    if result.get("applicable") is False:
        console.print(f"\n[dim]{result.get('methodology', '')}[/dim]")
        return
    console.print(f"\n[bold]mU:[/bold] {result['mU']:g}  [bold]sdU:[/bold] {result['sdU']:.4f}  "
                  f"[bold]floor p (U=0):[/bold] {result['floor_p']:.6g}  "
                  f"[bold]distinct p:[/bold] {result['n_achievable_p']}")
    if result["matched"]:
        m = result["matched"][0]
        console.print(f"[green]Matched U={m['U']:g}[/green] → p={m['p']:.6g} ({result['matched_convention']})")
    else:
        nb, na = result.get("nearest_below"), result.get("nearest_above")
        if nb and na:
            console.print(f"[yellow]No achievable U reproduces it[/yellow]; bracketed by "
                          f"U={nb['U']:g}→{nb['p']:.4g} and U={na['U']:g}→{na['p']:.4g}")
    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("grimu-coexist")
def grimu_coexist(
    n1: int = typer.Argument(..., help="First group size"),
    n2: int = typer.Argument(..., help="Second group size"),
    p: list[str] = typer.Option(..., "--p", help="A reported p-value from the same sample (repeatable)"),
    decimals: Optional[int] = typer.Option(None, "--decimals", "-d"),
    cc: str = typer.Option("both", "--cc"),
    p_source: str = typer.Option("unspecified", "--p-source", help="u_statistic|normal_z|unspecified"),
    ties_possible: bool = typer.Option(False, "--ties-possible", help="Outcome is a small-integer/ordinal scale, so ranks tie"),
):
    """GRIM-U co-existence: same-n rank-sum p-values that differ minimally but can't both be achievable."""
    from .tools import grimu as grimu_module

    result = grimu_module.grimu_coexistence(
        n1, n2, list(p), decimals=decimals, continuity_correction=cc,
        p_source=p_source, ties_possible=ties_possible or None,
    )
    bail_on_error(result)
    print_severity(result)
    if result.get("applicable") is False:
        console.print(f"\n[dim]{result.get('methodology', '')}[/dim]")
        return
    for v in result["coexistence_violations"]:
        console.print(f"  [red]{v['reason']}[/red]")
    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command()
def statcheck(
    input_path: Optional[Path] = typer.Argument(None, help="Path to PDF or text file to check"),
    text: Optional[str] = typer.Option(None, "--text", "-t", help="Raw text to check (use '-' for stdin)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
    use_python: bool = typer.Option(True, "--python/--r", "-p/-r", help="Use Python (default) or R implementation"),
):
    """
    Run statcheck to find and verify statistics.

    Extracts NHST results (t-tests, F-tests, correlations, chi-squared, etc.)
    and recalculates p-values to detect inconsistencies.

    Input can be:
    - A PDF file: metascience statcheck paper.pdf
    - A text/markdown file: metascience statcheck paper.md
    - Raw text: metascience statcheck --text "t(28) = 2.34, p = .05"
    - Stdin: cat paper.txt | metascience statcheck --text -

    Uses Python statcheck by default. Use --r for R implementation.
    """
    import sys

    # Determine input source
    if text is not None:
        # Text input mode
        if text == "-":
            # Read from stdin
            text_content = sys.stdin.read()
        else:
            text_content = text

        console.print(Panel("Running statcheck on text input", title="Statcheck Analysis"))

        with console.status("[bold green]Analyzing statistics..."):
            result = r_wrappers.python_statcheck_text(text_content)

    elif input_path is not None:
        if not input_path.exists():
            console.print(f"[red]Error: File not found: {input_path}[/red]")
            raise typer.Exit(1)

        # Check if it's a text file (not PDF)
        suffix = input_path.suffix.lower()
        is_text_file = suffix in [".txt", ".md", ".markdown", ".rst", ".text"]

        if is_text_file:
            # Read as text file
            console.print(Panel(f"Running statcheck on: [bold]{input_path}[/bold] (text)", title="Statcheck Analysis"))
            text_content = input_path.read_text()

            with console.status("[bold green]Analyzing statistics..."):
                result = r_wrappers.python_statcheck_text(text_content)
        else:
            # Treat as PDF
            console.print(Panel(f"Running statcheck on: [bold]{input_path}[/bold] (PDF)", title="Statcheck Analysis"))

            with console.status("[bold green]Extracting and verifying statistics..."):
                if use_python:
                    result = r_wrappers.python_statcheck(str(input_path))
                else:
                    result = r_wrappers.r_statcheck(str(input_path))
    else:
        console.print("[red]Error: Provide a file path or use --text[/red]")
        raise typer.Exit(1)

    if not result.get("success"):
        console.print(f"[red]Error: {result.get('error')}[/red]")
        if "not installed" in result.get("error", ""):
            if use_python:
                console.print("[dim]Install with: pip install statcheck[/dim]")
            else:
                console.print("[dim]Install R statcheck: install.packages('statcheck')[/dim]")
                console.print("[dim]Or use --python flag for Python implementation[/dim]")
        raise typer.Exit(1)

    # Display summary
    stats_found = result.get("stats_found", 0)
    errors_found = result.get("errors_found", 0)
    decision_errors = result.get("decision_errors", 0)

    console.print(f"\n[bold]Statistics found:[/bold] {stats_found}")
    console.print(f"[bold]Errors:[/bold] {errors_found}")
    console.print(f"[bold]Decision errors:[/bold] {decision_errors}")

    if stats_found == 0:
        console.print("\n[yellow]No NHST statistics found in APA format.[/yellow]")
    else:
        # Display table of results
        console.print("\n[bold]Results:[/bold]")
        for stat in result.get("statistics", []):
            raw = stat.get("raw", "")[:50]
            reported = stat.get("reported_p", "")
            computed = stat.get("computed_p", "")
            is_error = stat.get("error", False)
            is_decision = stat.get("decision_error", False)

            if is_decision:
                status = "[red]DECISION ERROR[/red]"
            elif is_error:
                status = "[yellow]ERROR[/yellow]"
            else:
                status = "[green]OK[/green]"

            console.print(f"  {raw}...")
            console.print(f"    Reported p: {reported}, Computed p: {computed} → {status}")

    # Save to file if requested
    if output:
        output.write_text(json.dumps(result, indent=2))
        console.print(f"\n[green]Results saved to: {output}[/green]")


@app.command("eval")
def eval_cmd(
    paper: Optional[str] = typer.Option(None, "--paper", help="Run only this fixture (apple_cider | airforce | wound_healing | cerebrolysin_flow)"),
    budget_usd: float = typer.Option(
        8.0, "--budget-usd",
        help="Per-paper analysis budget. DEFAULT RAISED FROM 3.0, 2026-08-22: the parallel pipeline splits it (tool 0.40, science 0.25), and the archived apple_cider run spent $2.81 on the tool agent alone -- so at $3.00 its cap was $1.20 and the stage was BUDGET-TRUNCATED before emitting any findings, with the science agent's CLI exiting 1 beside it. CLAUDE.md instructs exactly `metascience eval --paper apple_cider` as the post-prompt-change check, and that documented command could not complete on its largest fixture. $7.01 is the break-even for that run; 8.0 leaves headroom. A cap is not a spend -- the other three fixtures cost $0.70-$0.81 and are unaffected."),
    timeout: int = typer.Option(1800, "--timeout", help="Per-stage timeout in seconds"),
    # Was "opus" here against harness.py's "sonnet" default for the same flag,
    # so `metascience eval` and `python -m ...evaluation.harness` scored the same
    # fixtures on different models -- and the CLI always forwards --model, so the
    # expensive one always won. Measured per-paper cost on a nine-study paper
    # with SI: $4.97 on sonnet, $22.01 on fable. Default None resolves in the
    # HARNESS per backend (sonnet on claude, the backend default otherwise) --
    # forwarding "sonnet" to grok errored with "unknown model id".
    model: Optional[str] = typer.Option(None, "--model"),
    backend: Optional[str] = typer.Option(
        None, "--backend",
        help="LLM backend for the ANALYSIS: claude (default), grok, codex, openrouter, or antigravity. The judge does not follow it: see --judge-backend."),
    judge_backend: Optional[str] = typer.Option(
        None, "--judge-backend",
        help="Backend that grades the review. Default claude, whatever --backend produced it, so recall is comparable across backends."),
    judge_model: Optional[str] = typer.Option(
        None, "--judge-model", help="Judge model. Default sonnet."),
    pipeline: Optional[str] = typer.Option(
        None, "--pipeline",
        help="A complete-review pipeline to score (shipped name or YAML path), "
             "e.g. full_brief or full_skill; default: the flag default."),
    skip_analysis: bool = typer.Option(
        False, "--skip-analysis",
        help="Rescore existing eval runs. Refuses if a selected fixture has no "
             "forensic_review/report.md -- it will NOT silently run the paid pipeline. "
             "Still costs money: the LLM judge runs either way."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Run the evaluation harness against the gold-standard papers (costs money)."""
    from .evaluation.harness import (
        FIXTURES_DIR, RUNS_DIR, load_fixtures, repo_root, review_layout)
    from .evaluation.harness import main as eval_main

    review_dirname, _ = review_layout("parallel")

    # --skip-analysis means "do not run the paid pipeline". The harness reads it
    # as "reuse the run IF one exists, otherwise run it", so on a fixture with no
    # report.md the flag did the exact thing it was passed to prevent, silently.
    # Measured 2026-08-07 on this repo: 2 of the 3 fixtures (airforce,
    # wound_healing) have no forensic_review/report.md, so the plain documented
    # invocation `metascience eval --skip-analysis` would have launched two full
    # two-stage analyses. Refuse instead and name the missing files.
    if skip_analysis:
        root = repo_root()
        fixtures = load_fixtures(root / FIXTURES_DIR, only=paper)
        if not fixtures:
            console.print(f"[red]No fixtures found{f' for paper={paper}' if paper else ''}.[/red]")
            raise typer.Exit(1)
        missing = [
            f["paper"] for f in fixtures
            if not (root / RUNS_DIR / f["paper"] / review_dirname / "report.md").exists()
        ]
        if missing:
            console.print(
                "\n[red]Refusing --skip-analysis: no existing run to rescore for "
                f"{', '.join(missing)}.[/red]\n"
                "[red]Rescoring these would mean running the full paid two-stage "
                "pipeline, which is what --skip-analysis exists to avoid.[/red]\n"
                "Run them deliberately with `metascience eval --paper <name>` (this "
                "costs money), or pass --paper to rescore only a fixture that has "
                f"benchmarks/paper_reviews/runs/<paper>/{review_dirname}/report.md."
            )
            raise typer.Exit(2)

    argv = []
    if paper:
        argv += ["--paper", paper]
    argv += ["--budget-usd", str(budget_usd), "--timeout", str(timeout), "--model", model]
    if backend:
        argv += ["--backend", backend]
    if pipeline:
        argv += ["--pipeline", pipeline]
    if judge_backend:
        argv += ["--judge-backend", judge_backend]
    if judge_model:
        argv += ["--judge-model", judge_model]
    if skip_analysis:
        argv.append("--skip-analysis")
    if verbose:
        argv.append("--verbose")
    raise typer.Exit(eval_main(argv))


@app.command()
def version(
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Also show the prompt and registry hashes, which move far faster "
             "than the release number.",
    ),
):
    """Show what version of the pipeline this checkout is.

    The composite -- release number, git sha, dirty flag -- is what a report
    stamps on itself, so this is how you check whether a report came from this
    checkout. `--verbose` adds the prompt and registry hashes: two runs are
    directly comparable only when those match too.
    """
    from .version import pipeline_version

    console.print(f"forensic-metascience-ai-toolkit {pipeline_version()}")
    if verbose:
        from .agent import _provenance

        prov = _provenance()
        console.print(f"  prompts:  {prov.get('prompt_sha256') or NOT_RECORDED}")
        console.print(f"  registry: {prov.get('registry_sha256') or NOT_RECORDED}")
        console.print(f"  release:  {__version__}  (bump rules: CHANGELOG.md)")


@app.command("benchmark")
def benchmark_cmd(
    clean: int = typer.Option(60, "--clean", help="Number of negative-control papers"),
    flawed: int = typer.Option(15, "--flawed", help="Flawed papers per flaw kind"),
    seed: int = typer.Option(1000, "--seed", help="Base RNG seed (deterministic)"),
):
    """Measure the false-positive rate on synthetic papers with known ground truth.

    Negative controls have statistics computed from real integer samples, so any
    accusation is a false positive by definition. Free, offline, no API calls.
    """
    from .simulation import benchmark as run_benchmark

    result = run_benchmark(n_clean=clean, n_flawed_per_kind=flawed, seed0=seed)

    spec = result["specificity"]
    color = "green" if spec == 1.0 else ("yellow" if spec >= 0.95 else "red")
    console.print(Panel(
        f"[bold {color}]Specificity: {spec * 100:.1f}%[/bold {color}]\n"
        f"{result['clean_papers']} honest papers screened, "
        f"{result['false_positive_papers']} falsely accused",
        title="False-positive rate (negative controls)",
    ))
    for detail in result["false_positive_detail"]:
        console.print(f"  [red]FALSE POSITIVE[/red] {detail['paper_id']}: {detail['rows']}")

    table = Table(title="Detection of injected flaws (positive controls)")
    table.add_column("flaw kind")
    table.add_column("caught", justify="right")
    table.add_column("rate", justify="right")
    # WHAT THE DENOMINATOR EXCLUDES, SHOWN. `benchmark` drops cases its own
    # generator could not actually flaw -- a transposition that yields the same
    # mean is undetectable by anyone, so counting it would measure the
    # generator rather than the tool. That exclusion is right and it was
    # INVISIBLE: the table printed `9/11` for a `--flawed 15` request, so the
    # rate ROSE as the generator got worse, which is the one property a
    # coverage number must not have.
    table.add_column("not flawed", justify="right")
    for kind, s in result["sensitivity"].items():
        undetectable = s.get("undetectable") or 0
        table.add_row(kind, f"{s['caught']}/{s['total']}",
                      f"{s['rate'] * 100:.0f}%",
                      str(undetectable) if undetectable else "-")
    if any((s.get("undetectable") or 0) for s in result["sensitivity"].values()):
        console.print(
            "[dim]`not flawed` counts cases the generator could not actually "
            "break -- a transposition that leaves the mean unchanged, say. They "
            "are excluded from the rate because nothing could catch them, and "
            "shown because a denominator that shrinks silently makes a falling "
            "detector look like a rising one.[/dim]")
    console.print(table)

    if result["false_positive_papers"]:
        raise typer.Exit(1)


@app.command("anatomy")
def anatomy_cmd(
    findings_path: Path = typer.Argument(..., help="Path to a findings.json emitted by the sweep"),
    alpha: float = typer.Option(0.05, "--alpha", help="Significance threshold for multiplicity"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write markdown here"),
):
    """Render a paper's statistical anatomy: test table, multiplicity, assumption audit."""
    from .anatomy import anatomy_from_findings, render_anatomy_markdown

    if not findings_path.exists():
        console.print(f"[red]Not found: {findings_path}[/red]")
        raise typer.Exit(1)
    data = json.loads(findings_path.read_text())
    anat = anatomy_from_findings(data)
    if anat is None:
        console.print(
            "[yellow]This findings.json has no `anatomy` block.[/yellow]\n"
            "The sweep ran without enumerating studies/variables/tests, which means the "
            "forensic tools used DEFAULT data types and scale bounds. Re-run with the "
            "current prompt to get a typed anatomy."
        )
        raise typer.Exit(2)
    md = render_anatomy_markdown(anat, alpha=alpha)
    if output:
        output.write_text(md)
        console.print(f"[green]Written to {output}[/green]")
    else:
        console.print(Markdown(md))


@app.command("parse-cells")
def parse_cells_cmd(
    json_path: Path = typer.Argument(..., help="JSON file: list of {raw, row_label, col_label}"),
    show: int = typer.Option(20, "--show", help="How many parsed cells to print"),
):
    """Type table cells, refusing to guess on ambiguous ones.

    JSON root: a list of cell dicts, e.g.
        [{"raw": "142 (71.0)", "row_label": "Male, n (%)", "col_label": "Arm A"}]

    Run this BEFORE any other check. `142 (71.0)` read as mean=142, sd=71.0
    manufactures impossibilities out of an entirely ordinary clinical table.
    """
    from .tools.celltypes import parse_cells

    if not json_path.exists():
        console.print(f"[red]File not found: {json_path}[/red]")
        raise typer.Exit(1)
    cells = json.loads(json_path.read_text())
    if not isinstance(cells, list):
        console.print("[red]JSON root must be a list of cell dicts[/red]")
        raise typer.Exit(1)

    result = parse_cells(cells)
    cov = result["coverage"]
    color = "green" if cov >= 0.9 else ("yellow" if cov >= 0.6 else "red")
    console.print(f"[bold]Cells:[/bold] {result['n_cells']}   "
                  f"[bold]Coverage:[/bold] [{color}]{cov:.1%}[/{color}]   "
                  f"[bold]Unusable:[/bold] {result['n_unusable']}")

    table = Table(title="Cell kinds")
    table.add_column("kind")
    table.add_column("count", justify="right")
    for kind, count in sorted(result["kind_counts"].items(), key=lambda kv: -kv[1]):
        table.add_row(kind, str(count))
    console.print(table)

    console.print("\n[bold]Parsed cells:[/bold]")
    for c in result["cells"][:show]:
        kind = c["kind"]
        mark = "[red]" if kind in ("ambiguous", "non_numeric") else "[green]"
        detail = ", ".join(f"{k}={c[k]}" for k in
                           ("value", "sd", "se", "percent", "count", "low", "high") if k in c)
        console.print(f"  {mark}{kind}[/] {c['raw']!r} -> {detail or '(nothing usable)'}")
        if c.get("candidates"):
            console.print(f"      [yellow]candidates:[/yellow] {', '.join(c['candidates'])}")
    if len(result["cells"]) > show:
        console.print(f"  [dim]... {len(result['cells']) - show} more (raise --show)[/dim]")

    for w in result.get("warnings", []):
        console.print(f"[yellow]warning:[/yellow] {w}")
    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("parse-cells-as")
def parse_cells_as_cmd(
    json_path: Path = typer.Argument(..., help="JSON file: list of {raw, row_label, col_label}"),
    declared: str = typer.Option(..., "--declared",
                                 help="Format name, <pairing>:<delimiter>, e.g. mean_sd:brace"),
    min_fit: float = typer.Option(0.8, "--min-fit",
                                  help="Fraction of cells the format must fit to be applied"),
    show: int = typer.Option(20, "--show", help="How many parsed cells to print"),
):
    """Re-parse cells under a DECLARED format from the closed vocabulary.

    For a table typeset in a convention `parse-cells` does not recognise --
    `5.38 {1.17}`, `5.38 <1.17>` -- name the format rather than editing a regex:

        metascience parse-cells-as cells.json --declared mean_sd:brace

    Pass `--declared list` to print the vocabulary. The declaration is tested
    against the cells before it is applied, and refused if it fits too few.
    """
    from .tools.cellformat import apply_format, vocabulary

    if declared.strip().lower() in ("list", "?", "help"):
        vocab = vocabulary()
        t = Table(title=f"Declarable formats ({vocab['n_formats']} combinations)")
        t.add_column("pairing")
        t.add_column("arity", justify="right")
        t.add_column("what the numbers mean")
        for name, info in vocab["pairings"].items():
            t.add_row(name, str(info["arity"]), info["means"])
        console.print(t)
        d = Table(title="Delimiters")
        d.add_column("delimiter")
        d.add_column("second value looks like")
        for name, shown in vocab["delimiters"].items():
            # ESCAPED: `[value]` is rich's own markup syntax, so the bracket
            # delimiter -- one of the eight this table exists to advertise --
            # rendered as an empty cell.
            d.add_row(name, escape(shown))
        console.print(d)
        console.print(f"\n[dim]{vocab['syntax']}[/dim]")
        return

    if not json_path.exists():
        console.print(f"[red]File not found: {json_path}[/red]")
        raise typer.Exit(1)
    cells = json.loads(json_path.read_text())
    if not isinstance(cells, list):
        console.print("[red]JSON root must be a list of cell dicts[/red]")
        raise typer.Exit(1)

    result = apply_format(cells, declared, min_fit=min_fit)
    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(1)

    colour = "green" if result["applied"] else "red"
    console.print(
        f"[bold]Declared:[/bold] {result['declared']}   "
        f"[bold]Fit:[/bold] [{colour}]{result['n_fit']}/{result['n_cells']} "
        f"({result['fit_rate']:.0%})[/{colour}]   "
        f"[bold]Applied:[/bold] [{colour}]{result['applied']}[/{colour}]   "
        f"[bold]Newly readable:[/bold] {result['n_recovered']}"
    )
    for c in result["cells"][:show]:
        detail = ", ".join(f"{k}={c[k]}" for k in
                           ("value", "sd", "se", "percent", "count", "low", "high") if k in c)
        console.print(f"  [green]{c['kind']}[/] {c['raw']!r} -> {detail}")
    if result["misfits"]:
        console.print("\n[bold]Did not fit:[/bold]")
        for m in result["misfits"][:show]:
            console.print(f"  [red]{m['raw']!r}[/red] -- {m['why']}")
    for w in result.get("warnings", []):
        console.print(f"[yellow]warning:[/yellow] {w}")
    console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("replay")
def replay_cmd(
    target: Path = typer.Argument(..., help="An archived run directory, or a corpus root"),
    stage: str = typer.Option("stage1", "--stage", help="stage1 or stage2"),
    json_out: bool = typer.Option(False, "--json", help="Emit the full record as JSON"),
):
    """Re-run an archived run's tool calls at HEAD and diff the verdicts.

    Answers "would my change actually have altered the output?" in seconds and
    for nothing, against REAL calls on REAL papers, with the model held fixed --
    the alternative being a $9-10, 26-minute paid run whose model is also a
    fresh roll of the dice.

        metascience replay tests/fixtures/papers/high_value_pdfs_to_run_on
        metascience replay tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--eat.24415/forensic_review

    Read the BECAME ACCUSATORY block first: a change that turns a clean call
    into an accusation has to be justified cell by cell before it ships.
    """
    from .evaluation import replay as _replay

    if not target.exists():
        console.print(f"[red]Not found: {target}[/red]")
        raise typer.Exit(1)
    single = (target / f"toolcalls.{stage}.json").exists()
    summary = (_replay.replay_run(target, stage) if single
               else _replay.replay_corpus(target, stage))
    if json_out:
        console.print_json(json.dumps(summary))
        return
    if summary.get("error"):
        console.print(f"[red]{summary['error']}[/red]")
        raise typer.Exit(1)
    split = _replay.classify(summary)
    console.print(escape(_replay.render(summary)))
    # Non-zero ONLY when something became an accusation. A replay that merely
    # withdraws accusations or adds refusals is a good outcome and must not
    # fail a developer's loop.
    if split["became_accusatory"]:
        raise typer.Exit(2)


@app.command("check-ci")
def check_ci_cmd(
    estimate: float = typer.Argument(..., help="Reported point estimate"),
    ci_low: float = typer.Argument(..., help="Lower confidence bound"),
    ci_high: float = typer.Argument(..., help="Upper confidence bound"),
    measure: Optional[str] = typer.Option(None, "--measure", "-m", help="e.g. OR, RR, HR, IRR, MD, SMD"),
    reported_p: Optional[float] = typer.Option(None, "--reported-p", "-p"),
    reported_p_operator: str = typer.Option(
        "=", "--p-op",
        help="Comparison the paper printed with the p: '=', '<', '<=', '>' or "
             "'>='. For 'P < .001' pass --reported-p 0.001 --p-op '<'."),
    confidence_level: float = typer.Option(0.95, "--level", help="Confidence level (default 0.95)"),
    null_value: Optional[float] = typer.Option(None, "--null", help="Null value (default 1 for ratios, 0 otherwise)"),
    decimals: Optional[int] = typer.Option(None, "--decimals", help="Printed decimals of the COARSEST of the three numbers. Without it the tolerance is re-derived from the parsed floats, which reads a bound printed 1.40 as one decimal and one printed 5 as one decimal."),
):
    """Reconcile a point estimate against its own confidence interval.

    Pass --measure for ratio measures: OR/RR/HR confidence intervals are
    symmetric in LOG space, and a linear-symmetry check misfires on roughly a
    third of hazard ratios at SE_log = 0.4.
    """
    from .tools.estimates import check_estimate_ci

    result = check_estimate_ci(
        estimate, ci_low, ci_high, measure=measure, reported_p=reported_p,
        reported_p_operator=reported_p_operator,
        confidence_level=confidence_level, null_value=null_value, decimals=decimals,
    )
    print_severity(result)
    for key, label in (("recovered_se", "Recovered SE"), ("recovered_p", "Recovered p"),
                       ("implied_midpoint", "CI midpoint"), ("scale", "Scale")):
        if result.get(key) is not None:
            val = result[key]
            console.print(f"[bold]{label}:[/bold] {val:.6g}" if isinstance(val, float)
                          else f"[bold]{label}:[/bold] {val}")
    for prob in result.get("problems", []):
        console.print(f"  [red]-[/red] {prob}")
    for note in result.get("notes", []):
        console.print(f"  [dim]note: {note}[/dim]")
    if result.get("methodology"):
        console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("absence-of-evidence")
def absence_of_evidence_cmd(
    ci_low: float = typer.Argument(..., help="Lower confidence bound"),
    ci_high: float = typer.Argument(..., help="Upper confidence bound"),
    measure: Optional[str] = typer.Option(None, "--measure", "-m", help="e.g. OR, RR, HR, MD"),
    sesoi: Optional[float] = typer.Option(None, "--sesoi", help="Smallest effect size of interest"),
    null_value: Optional[float] = typer.Option(None, "--null"),
):
    """Test a 'no effect' claim against what its interval actually permits.

    Without --sesoi this describes the interval and DECLINES to judge:
    equivalence cannot be claimed against an unstated threshold.
    """
    from .tools.estimates import absence_of_evidence

    result = absence_of_evidence(
        ci_low, ci_high, measure=measure, sesoi=sesoi, null_value=null_value,
    )
    print_severity(result)
    if result.get("largest_compatible_effect") is not None:
        console.print(f"\n[bold]Largest effect not ruled out:[/bold] "
                      f"{result['largest_compatible_effect']:.4g}")
    if result.get("includes_null") is not None:
        console.print(f"[bold]Interval includes null:[/bold] {result['includes_null']}")
    if result.get("methodology"):
        console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("power-check")
def power_check_cmd(
    test_type: str = typer.Argument(..., help="two_sample_t|one_sample_t|paired_t|anova_oneway|correlation|chi_square|two_proportions"),
    effect_size: Optional[float] = typer.Option(None, "--effect-size", "-e"),
    alpha: Optional[float] = typer.Option(None, "--alpha", "-a"),
    target_power: Optional[float] = typer.Option(None, "--power"),
    n_reported: Optional[int] = typer.Option(None, "--n-reported", "-n"),
    per_group: bool = typer.Option(False, "--per-group", help="n_reported is per-group, not total"),
    tails: Optional[int] = typer.Option(
        None, "--tails",
        help="1 or 2, ONLY as stated by the paper. Unset, the check tries both and "
             "refuses rather than accuse a paper for our assumed convention."),
    groups: int = typer.Option(2, "--groups"),
    df: Optional[int] = typer.Option(None, "--df"),
    no_attrition: bool = typer.Option(False, "--no-attrition", help="Do not allow N inflated for attrition"),
):
    """Recompute a paper's stated power analysis against the N it recruited.

    Returns `indeterminate` unless every input needed to reproduce the
    calculation was actually stated. Most published power statements cannot be
    checked at all -- that is a reportable finding, not a tool failure.
    """
    from .tools.power_check import verify_power_analysis

    result = verify_power_analysis(
        test_type=test_type, effect_size=effect_size, alpha=alpha,
        target_power=target_power, n_reported=n_reported,
        n_reported_is_per_group=per_group, tails=tails, groups=groups, df=df,
        allows_attrition_inflation=not no_attrition,
    )
    # A missing input is a legitimate `indeterminate` verdict, not a CLI error:
    # "the paper never stated alpha" is a finding worth printing, so only a
    # genuine failure (bad test_type, out-of-range alpha) exits non-zero.
    if result.get("error") and not result.get("missing_inputs"):
        bail_on_error(result)
    print_severity(result)
    if result.get("missing_inputs"):
        console.print(f"\n[yellow]Not stated by the paper:[/yellow] {', '.join(result['missing_inputs'])}")
    for key, label in (("n_required_per_group", "Required n/group"),
                       ("n_required_total", "Required n total"),
                       ("achieved_power", "Power at reported N")):
        if result.get(key) is not None:
            console.print(f"[bold]{label}:[/bold] {result[key]}")
    if result.get("methodology"):
        console.print(f"\n[dim]{result['methodology']}[/dim]")


@app.command("required-n")
def required_n_cmd(
    test_type: str = typer.Argument(..., help="two_sample_t|one_sample_t|paired_t|anova_oneway|correlation|chi_square|two_proportions"),
    effect_size: float = typer.Argument(..., help="Effect size (d, f, r, w, or h)"),
    alpha: float = typer.Option(0.05, "--alpha", "-a"),
    power: float = typer.Option(0.80, "--power"),
    tails: int = typer.Option(2, "--tails"),
    groups: int = typer.Option(2, "--groups"),
    df: Optional[int] = typer.Option(None, "--df"),
):
    """Smallest sample size meeting a target power (exact noncentral distributions)."""
    from .tools.power_check import required_n

    result = required_n(test_type, effect_size, alpha=alpha, power=power,
                        tails=tails, groups=groups, df=df)
    bail_on_error(result)
    if result.get("n_per_group") is not None:
        console.print(f"[bold]Required n per group:[/bold] {result['n_per_group']}")
    console.print(f"[bold]Required n total:[/bold] {result['n_total']}")
    console.print(f"[bold]Achieved power at that n:[/bold] {result['achieved_power']}")


def _corpus_mean_cost(corpus: Path, model: str | None = None) -> tuple[float, int] | None:
    """Mean cost per paper from this corpus's own batch_costs.jsonl, for `model`.

    A corpus's own history beats a global constant: cost tracks table count and
    SI length, and the constants come from a handful of papers.

    MODEL-SPECIFIC ON PURPOSE. This used to average every row regardless of
    model, and the caller then overwrote the per-model constant with it
    unconditionally -- so the moment any history existed, `--model` stopped
    changing the estimate at all and a sonnet-built history silently priced an
    opus run at half its cost. Measured on this corpus: sonnet $5.22/paper
    against opus $11.52.

    Rows written before the `model` column existed are SKIPPED rather than
    guessed at. Returning a smaller honest sample -- or None, which falls
    through to the measured constants -- beats blending two models into one
    meaningless average. Returns (mean, n) so the caller can show the sample it
    is quoting from.
    """
    path = corpus / "batch_costs.jsonl"
    if not path.exists():
        return None
    costs = []
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if model is not None and row.get("model") != model:
            continue
        c = row.get("total_cost_usd")
        if c:
            costs.append(float(c))
    return (sum(costs) / len(costs), len(costs)) if costs else None


@app.command("batch")
def batch_cmd(
    corpus: Path = typer.Argument(..., help="Directory of paper subdirectories"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Only the first N papers (default: all)"),
    # `--workers` is an ALIAS, not a second knob. One worker analyses one paper
    # start-to-finish (`async with sem` in batch.process_paper wraps the
    # whole paper), so "N workers" and "N papers in flight" are the same number.
    # Two names because the pool framing is the one people reach for; two
    # SETTINGS would let a caller ask for 4 workers and 2 concurrent papers and
    # be silently obeyed by whichever the code happened to read.
    concurrency: int = typer.Option(
        10, "--workers", "--concurrency", "-j",
        help="Papers analysed in parallel, one paper per worker. Default 10 -- "
             "a ten-paper benchmark corpus finishes in one paper's wall time "
             "instead of ten. Each worker is an LLM CLI subprocess at roughly "
             "0.5-1 GB, so the ceiling is RAM: drop it on a small machine."),
    budget_usd: Optional[float] = typer.Option(None, "--budget-usd", help="Per-paper budget cap"),
    pipeline: Optional[str] = typer.Option(
        None, "--pipeline",
        help="Pipeline to run per paper: a shipped name (`metascience pipeline "
             "list`) or a YAML path. Default: the complete review. For a "
             "partial pipeline, only runs of that same pipeline count as done."),
    image_forensics: bool = typer.Option(
        True, "--image-forensics/--no-image-forensics",
        help="Run independent image detection and AI screening per paper (default on)."),
    timeout: int = typer.Option(1800, "--timeout", help="Per-stage timeout in seconds"),
    backend: Optional[str] = typer.Option(
        None, "--backend",
        help="LLM backend, REQUIRED when a model is called: claude, grok, codex, openrouter (our API loop; needs OPENROUTER_API_KEY), or antigravity (Google's agy CLI; `metascience models --backend antigravity` lists its models). A pipeline file's backend also counts; METASCIENCE_LLM_CLI does not."),
    model: Optional[str] = typer.Option(
        None, "--model",
        help="Model alias. Default follows --backend (opus for claude, grok-4.6 for grok, gpt-5.6-sol for codex, anthropic/claude-sonnet-5.5 for openrouter, gemini-4-argon for antigravity; see `metascience models`)."),
    effort: Optional[str] = typer.Option(
        None, "--effort",
        help=f"low|medium|high|xhigh|max (default: the pipeline's, else {DEFAULT_EFFORT})"),
    subdir_name: Optional[str] = typer.Option(
        None, "--subdir-name",
        help="Output dir inside each paper (default: "
             "forensic_review_<model>_v<version> -- the folder names its "
             "experiment)"),
    skip_existing: bool = typer.Option(True, "--skip-existing/--redo", help="Skip papers already analysed by the same pipeline, backend and model (resumable)"),
    archive: bool = typer.Option(False, "--move-to-done/--no-move-to-done", help="Move finished papers into done/"),
    dry_run: bool = typer.Option(False, "--dry-run", help="List what WOULD run, with a cost estimate, then exit"),
    ok_if_supplementary_missing: bool = typer.Option(
        False, "--ok-if-supplementary-missing",
        help="Deprecated, no effect: papers citing supplementary material that is not "
             "present are now analysed with a warning and a recorded limitation."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    ignore_weekly_limit: bool = typer.Option(
        False, "--ignore-weekly-limit",
        help="Do not stop when the Claude Code weekly /usage gauge is at/over "
             "threshold. Session-window pausing still runs. Use this when extra "
             "usage credits will cover the spend -- the weekly % does not include "
             "them."),
    no_usage_guard: bool = typer.Option(
        False, "--no-usage-guard",
        help="Disable the Claude Code usage guard entirely (session pause and "
             "weekly stop). Prefer --ignore-weekly-limit if you only need to "
             "override a spent weekly quota."),
):
    """Analyse every paper in a directory. One command, fully automated.

    Analyses 10 papers at once by default (--workers 10), one paper per
    worker; a terminal shows a live grid with a row per stage of every paper
    in flight. Use --workers 1 when the binding constraint is a shared token
    budget rather than wall-clock time.

    Resumable: papers that already have a report from the same pipeline,
    backend and model are skipped, so an interrupted run is restarted with the
    same command and nothing is paid for twice. A different model or backend
    is a new run and needs no --redo.

        metascience batch tests/fixtures/papers/high_value_pdfs_to_run_on --dry-run
        metascience batch tests/fixtures/papers/high_value_pdfs_to_run_on --budget-usd 3
        metascience batch tests/fixtures/papers/high_value_pdfs_to_run_on --workers 4
    """
    from argparse import Namespace
    from .llm_backend import resolve_backend
    from .usage_guard import apply_cli_overrides

    apply_cli_overrides(
        no_usage_guard=no_usage_guard,
        ignore_weekly_limit=ignore_weekly_limit,
    )

    if not corpus.is_dir():
        console.print(f"[red]Not a directory: {corpus}[/red]")
        raise typer.Exit(1)

    config = None
    if pipeline is not None:
        config = _load_pipeline_or_exit(pipeline)
        if not image_forensics:
            console.print("[red]--no-image-forensics cannot be combined with "
                          "--pipeline: the pipeline decides the modules.[/red]")
            raise typer.Exit(2)
        from . import pipeline_config as _pc
        backend, model, effort = _pc.resolve_backend_settings(
            config, backend, model, effort)
    _require_backend(backend, config)
    effort = effort or DEFAULT_EFFORT
    be = resolve_backend(backend)
    model = model or be.default_model
    subdir_name = subdir_name or _versioned_review_dirname(model, config)
    if budget_usd is not None and not be.supports_budget:
        console.print(
            f"[red]{be.name} has no spend cap; re-run without --budget-usd "
            f"or use --backend claude.[/red]")
        raise typer.Exit(2)

    from metascience_agent.batch import pick_papers, run_batch

    papers = pick_papers(corpus, limit, None)
    if not papers:
        console.print(f"[red]No paper directories found in {corpus}[/red]")
        raise typer.Exit(1)

    # `completed_review` (agent.py), not `(p / subdir_name).exists()`: the bare
    # name misses every `metascience analyze` run, whose output directory carries
    # the model and date, and an empty directory from a crashed run is not a
    # review. Both call sites now share the one definition.
    pending = ([p for p in papers
                if completed_review(p, subdir_name, pipeline=config,
                                    backend=be.name, model=model) is None]
               if skip_existing else list(papers))
    already = len(papers) - len(pending)

    # Two gates run across the corpus BEFORE any spend, in this order.
    #
    # `_resolve_paper_sources` is the same resolver `analyze_paper` uses, so the
    # full-text gate asks precisely the question the pipeline will ask, not an
    # approximation.
    from .agent import _resolve_paper_sources, ensure_paper_extracted
    from .extraction.jats import find_body_md
    from .supplements import gate as _supp_gate

    # 1. FULL TEXT FIRST. The supplement gate answers "is this paper complete?"
    # and says nothing about whether there is a paper at all. `pick_papers` takes
    # every subdirectory of the corpus, so a directory holding only extracted
    # figures, only a previous forensic_review/, or nothing, sails through the
    # supplement gate and is counted as runnable, priced into the estimate, and
    # paid for -- a sweep whose whole input is "no readable source", which is
    # exactly the run whose empty findings read as a clean paper.
    #
    # The supplement gate now refuses unreadable papers too, but it is refusable:
    # --ok-if-supplementary-missing suppresses it wholesale, and that flag is about
    # trading partial coverage for a run. There is nothing to trade when there is
    # no text. So the full-text check runs FIRST and unconditionally.
    #
    # MEASURED 2026-08-07 on eval/ground_truth/papers/: 8 of 78 directories have
    # no XML, no body.md and no main PDF. Before this, `metascience batch
    # eval/ground_truth/papers --ok-if-supplementary-missing` listed all 78 as runnable
    # and would have paid for those 8 (~$40 at the measured $5/paper) to sweep
    # nothing.

    def _has_fulltext(p: Path) -> bool:
        s = _resolve_paper_sources(str(p))
        return bool(s.xml or s.body_md or s.main_pdf)

    def _duplicate_text_groups(dirs: list[Path]) -> list[list[Path]]:
        """Directories whose extracted text is byte-identical to another's.

        Exact, not heuristic. Every attempt at a STRUCTURAL test for "is this
        document actually a paper" was measured and rejected: on the 309-paper
        cerebrolysin corpus, "no statistical markers" flags 85 of 286 real
        papers, "no IMRaD headings" flags 130, and the conjunction still flags
        49 -- and inspecting those shows the false positives are concentrated
        in RUSSIAN-LANGUAGE papers, which score zero only because the heading
        vocabulary is English. A gate that quietly deprioritises non-English
        work is worse than no gate. Byte-equality carries none of that: it
        makes no claim about what a paper should look like.

        Reads the pre-extracted markdown when there is one (cheapest), and
        falls back to the docling cache's body text when there is none: a
        corpus fetched PDF-only carries no body.md at all, and the
        markdown-only version of this screen silently gave such a corpus no
        duplicate check whatsoever. Cache-only via `cached_text` -- this is a
        planning screen the operator is waiting at, so it must never run the
        extractor; a paper with neither markdown nor cache is simply not
        screened here, and the plan already names it as "not extracted yet".
        Opening 300 PDFs to compare them would cost minutes.
        """
        from .extraction.docling_tables import cached_text

        seen: dict[str, list[Path]] = {}
        for d in dirs:
            body = find_body_md(d)
            if body is not None:
                try:
                    digest = hashlib.md5(body.read_bytes()).hexdigest()
                except OSError:
                    continue
            else:
                pdf = _resolve_paper_sources(str(d)).main_pdf
                if pdf is None:
                    continue
                text, _why = cached_text(pdf)
                if not text:
                    continue
                digest = hashlib.md5(text.encode("utf-8")).hexdigest()
            seen.setdefault(digest, []).append(d)
        return [g for g in seen.values() if len(g) > 1]

    skips: list[tuple[Path, str]] = []
    already_papers = [p for p in papers if p not in pending] if skip_existing else []
    for p in already_papers:
        skips.append((p, "already analysed"))

    no_fulltext = [p for p in pending if not _has_fulltext(p)]
    if no_fulltext:
        for p in no_fulltext:
            skips.append((p, "no full text -- no XML, body.md or PDF"))
        skipped = set(no_fulltext)
        pending = [p for p in pending if p not in skipped]

    # 2. The supplement gate. An incomplete paper does not merely get partial
    # coverage: a statistic living in an absent supplement is indistinguishable
    # from one the authors never reported, so the run manufactures findings
    # against them. On the high-value corpus this excludes roughly three papers
    # in four -- which is the honest number, and better seen before paying than
    # after.
    # TWO DIFFERENT REFUSALS SHARED ONE ROW, AND ONE OF THEM WAS OVERRIDABLE
    # WHEN IT MUST NOT BE. `gate` refuses both a paper whose supplement is
    # missing and a paper whose text could not be read at all -- the second via
    # `missing: None`, meaning the question was never answered. Both landed in
    # `incomplete`, so `--ok-if-supplementary-missing` waved both through.
    #
    # The comment on `_has_fulltext` above says that check runs "FIRST and
    # unconditionally" precisely because there is nothing to trade when there
    # is no text. But it tests whether a FILE EXISTS, and a scanned paper has a
    # perfectly good PDF -- it just has no text in it. So a scan passed gate 1,
    # was pooled with the supplement cases at gate 2, and
    # `batch --ok-if-supplementary-missing` would have paid to sweep it.
    #
    # `audit` already returns `text_available` and the gate is already called
    # once per paper, so separating them costs nothing. Reading the PDF to
    # decide would have cost a full pdfplumber pass per paper (a measured
    # median of 6.6 s -- half an hour of staring at a planning screen for a
    # 300-paper corpus).
    #
    # LIVE RUNS EXTRACT FIRST, same order as `analyze`. An unextracted PDF
    # yields empty text, which this gate used to file as "scanned or corrupt"
    # -- TRUE OF US AND FALSE OF THE PAPER. Dry-run does not extract (too
    # slow for a 300-paper table) and instead keeps cache-miss papers in
    # `pending` rather than skipping them as scans.
    if not dry_run:
        for p in pending:
            rec = ensure_paper_extracted(
                str(p),
                on_event=lambda msg: console.print(f"[dim]{escape(msg)}[/dim]"),
            )
            if rec.get("failed"):
                console.print(f"[red]Unreadable PDF(s) in {p.name}.[/red] "
                              f"{rec.get('note', '')}")

    gates = {p: _supp_gate(p) for p in pending}
    not_extracted = [p for p in pending
                     if gates[p]["audit"].get("text_status") == "not_extracted"]
    not_extracted_set = set(not_extracted)
    unreadable = [p for p in pending
                  if not gates[p]["proceed"]
                  and gates[p]["audit"].get("text_available") is False
                  and p not in not_extracted_set]
    unreadable_set = set(unreadable)
    # A cited, absent supplement WARNS and runs (Dan, 2026-10-18): keyed on
    # the audit, because the gate now proceeds for these papers and a
    # `not proceed` filter would come back empty.
    incomplete = [p for p in pending
                  if gates[p]["audit"].get("missing") is True
                  and p not in unreadable_set
                  and p not in not_extracted_set]

    if unreadable:
        # No override, for the same reason gate 1 has none.
        for p in unreadable:
            skips.append((p, "no readable text -- scanned or corrupt "
                          "(extracted, empty)"))
        pending = [p for p in pending if p not in unreadable_set]
    for p in incomplete:
        console.print(f"[yellow]WARNING[/yellow] {p.name}: cites supplementary "
                      "material that is not here; analysing the main text anyway "
                      "(recorded as a limitation).")
    # Cache-miss papers stay in `pending`. The table names them as not
    # extracted yet so the operator can see they will cost an extract.

    # Per-paper cost. Prefer this corpus's OWN history over any constant -- the
    # constants are two datapoints on two papers and generalise badly.
    #
    # Verified against `modelUsage` rather than the requested alias (a run
    # recorded as one model can be billed to another after a refusal fallback):
    #   claude-sonnet-5   $5.22   mean of 24 runs, 2026-08-14 (median $4.66,
    #                             range $0.68-$11.99), two corpora
    #   claude-opus-5    $11.52   mean of 12 runs (median $11.44, range
    #                             $4.83-$18.00), two corpora
    #   claude-fable-5   $22.01   one paper
    #
    # The opus-5 figure replaces an explicit "UNMEASURED" note that fell through
    # to the sonnet constant. Opus is the DEFAULT model for both `analyze` and
    # `batch`, so every opus quote was ~2.3x low. All 36 runs behind these means
    # were checked for refusal fallbacks: there were none, and no run's billed
    # model differed from the one requested.
    #
    # Opus costs ~2.2x sonnet, not the ~5x list pricing implies, because spend is
    # dominated by how many tool calls the sweep makes rather than by per-token
    # price -- the sweep is 86% of the bill.
    MEASURED = {"sonnet": 5.2, "opus": 11.5, "fable": 22.0}
    measured_model = model in MEASURED
    # A missing key must render "unknown", never 0 or a silent sonnet fallback.
    # Grok per-paper cost is unmeasured until a live run; quoting 5.2 would
    # be LESSONS §1 in a dry-run whose only job is to say what a batch costs.
    per_paper = MEASURED.get(model) if measured_model else None

    # History only counts if it is history for THIS model; see _corpus_mean_cost.
    history = _corpus_mean_cost(corpus, model)
    history_n = None
    if history is not None:
        per_paper, history_n, measured_model = history[0], history[1], True
    if per_paper is None:
        est_low = est_high = None
    else:
        est_low, est_high = len(pending) * per_paper * 0.5, len(pending) * per_paper * 1.5

    # No header: the columns are a label and its value, and blank column
    # titles rendered as an empty boxed row under the title.
    plan = Table(title=f"Batch plan: {corpus.name}", show_header=False)
    plan.add_column("", style="bold"); plan.add_column("", justify="right")
    plan.add_row("papers found", str(len(papers)))
    plan.add_row("already analysed (skipped)", str(already))
    # No --without-fulltext escape hatch on purpose: --ok-if-supplementary-missing trades
    # partial coverage for a run, but there is nothing to trade here. A paper
    # with no readable source cannot be analysed at all.
    if no_fulltext:
        plan.add_row(
            "[red]no full text -- nothing to read[/red]",
            f"[red]{len(no_fulltext)}  (skipped)[/red]",
        )
    if unreadable:
        plan.add_row(
            "[red]no readable text -- scanned or corrupt[/red]",
            f"[red]{len(unreadable)}  (skipped)[/red]",
        )
    if not_extracted:
        plan.add_row(
            "[yellow]PDF not extracted yet[/yellow]",
            f"[yellow]{len(not_extracted)}  (will extract)[/yellow]",
        )
    if incomplete:
        plan.add_row(
            "[yellow]supplement cited and missing[/yellow]",
            f"[yellow]{len(incomplete)}  (INCLUDED, warned)[/yellow]",
        )
    # 3. Two directories holding the SAME text cannot both be the paper their
    # own DOI names. Warned rather than skipped: at most one of the pair is
    # wrong, nothing here can tell which, and silently dropping a good paper is
    # its own error. Repairing the corpus is the operator's call, and this is
    # the screen they read before agreeing to spend.
    #
    # MEASURED 2026-08-07 on `cerebrolysin_papers/` (309 directories): 19 hold
    # publisher furniture instead of an article, and 14 of those are
    # byte-identical to another directory -- 8 DOIs across five journals all
    # holding the same Lippincott author-permission page, and 5 holding the
    # same Bentham Science media kit, which is an advertising brochure. Every
    # one passes the full-text and supplement gates, because they contain
    # plenty of readable text; it is simply not the paper's. A forensic sweep
    # of an advertisement completes cheaply and reports no problems found.
    duplicates = _duplicate_text_groups(pending)
    if duplicates:
        n_dupes = sum(len(g) for g in duplicates)
        plan.add_row(
            "[red]same text in >1 directory[/red]",
            f"[red]{n_dupes} in {len(duplicates)} group(s)  (INCLUDED)[/red]",
        )
    # 4. Supplement integrity, READ BACK from fetchpdf's manifests (the
    # 30-LFS-stub lesson: integrity metadata that is only written protects
    # nothing). Best-effort and informational in every branch: a damaged
    # supplement never blocks its paper -- the run proceeds, and this screen
    # is where the operator learns the bytes it would read are not the bytes
    # that were fetched. An unimportable auditor is a NAMED absence with the
    # standalone command, printed below the table.
    integrity = _supplement_integrity(corpus)
    n_damaged = sum(sum(v.values()) for v in integrity.get("damaged", {}).values())
    if integrity["status"] != "checked":
        plan.add_row("[yellow]supplement integrity[/yellow]",
                     "[yellow]UNCHECKED[/yellow]")
    elif n_damaged:
        plan.add_row(
            "[red]supplement files damaged on disk[/red]",
            f"[red]{n_damaged} in {len(integrity['damaged'])} paper(s)  (INCLUDED)[/red]",
        )
    elif integrity["n_files"]:
        # Intact and unverifiable are different facts: an older manifest with
        # no size or digest recorded proves nothing about its file.
        extra = (f", {integrity['n_unverifiable']} unverifiable"
                 if integrity["n_unverifiable"] else "")
        plan.add_row("supplement integrity",
                     f"{integrity['n_intact']} file(s) intact{extra}")
    else:
        # Distinct from "all intact": nothing was verified because nothing
        # claims to be verifiable. A corpus fetched without manifests gets
        # this row, not a clean bill.
        plan.add_row("supplement integrity", "no manifests to verify")
    plan.add_row("to run", str(len(pending)))
    plan.add_row("model / effort", f"{model} / {effort}")
    plan.add_row("workers", f"{concurrency}" + ("  (serial)" if concurrency == 1 else "  (papers in parallel)"))
    # THE PER-STAGE TIMEOUT IS THE ONLY RUNAWAY GUARD, and it is per STAGE, not
    # per paper. MEASURED 2026-08-22: a 10-paper grok batch run with
    # `--timeout 60000` left one adjudicator streaming for 71 minutes against a
    # docket its siblings had cleared in 6-10, with its MCP server frozen (zero
    # forensic calls) -- a 16.7-hour leash on a stage that has no business
    # outrunning the sweeps that fed it. Say so on the screen where the
    # operator agrees to spend, rather than in the flag's one-line help.
    if timeout and timeout > _TIMEOUT_WARN_SECONDS:
        plan.add_row(
            "[yellow]per-stage timeout[/yellow]",
            f"[yellow]{timeout}s  (runaway guard effectively off)[/yellow]")
    else:
        plan.add_row("per-stage timeout",
                     f"{timeout}s" if timeout else "none")
    plan.add_row("per-paper budget", f"${budget_usd:.2f}" if budget_usd else "uncapped")
    # The basis NAMES THE MODEL in every branch. It used to say only "this
    # corpus's own history", which read as if the figure were for the model you
    # asked for when the history could have been built entirely on another one.
    basis = (f"this corpus's own history ({model}, n={history_n})" if history is not None
             else f"measured on {model}" if measured_model
             else f"UNMEASURED for {model}")
    if est_low is None:
        plan.add_row("estimated total", "[yellow]unknown[/yellow]")
    else:
        plan.add_row("estimated total", f"${est_low:,.0f} - ${est_high:,.0f}")
    plan.add_row("estimate basis", basis)
    plan.add_row("backend", be.name)
    console.print(plan)

    _print_skip_list(skips, dest=None if dry_run else corpus / "skipped.jsonl")
    if not_extracted:
        console.print(
            f"\n[yellow]{len(not_extracted)} PDF(s) not extracted yet "
            "(will extract if you run):[/yellow]")
        for p in not_extracted[:_SKIP_PRINT_CAP]:
            console.print(f"[yellow]  {p.name}[/yellow]")
        extra = len(not_extracted) - _SKIP_PRINT_CAP
        if extra > 0:
            console.print(f"[yellow]  ... and {extra} more[/yellow]")

    if duplicates:
        # The count in the table is not actionable on its own -- the operator
        # has to be able to go and look at the directories.
        console.print(
            "\n[red bold]The same text appears in more than one paper "
            "directory.[/red bold]\n"
            "  At most one of each group can be the paper its DOI names, and "
            "nothing here can tell\n"
            "  which. In the corpus where this was first measured, every such "
            "group turned out to be\n"
            "  publisher furniture -- an author-permission page, a media kit -- "
            "fetched in place of the\n"
            "  article. Such a sweep completes cheaply and reports no problems "
            "found, about a document\n"
            "  that is not the paper. Check these before spending:")
        for group in duplicates[:6]:
            console.print(f"    [dim]{len(group)} directories share one text:[/dim]")
            for d in group[:8]:
                console.print(f"      {d.name}")
            if len(group) > 8:
                console.print(f"      [dim]... and {len(group) - 8} more[/dim]")
        if len(duplicates) > 6:
            console.print(f"    [dim]... and {len(duplicates) - 6} more group(s)[/dim]")

    if integrity["status"] != "checked":
        console.print(f"\n[yellow]Supplement integrity unchecked: "
                      f"{integrity['detail']}[/yellow]")
    elif integrity["damaged"]:
        console.print(
            "\n[red bold]Supplement files on disk no longer match what was "
            "fetched.[/red bold]\n"
            "  The manifests prove these bytes were downloaded and hashed "
            "intact; something since\n"
            "  replaced or truncated them (a git-lfs stub, a bad sync). Their "
            "papers still run, but a\n"
            "  check that reads a damaged supplement reads the wrong bytes. "
            "Repair before trusting:")
        for paper, verdicts in sorted(integrity["damaged"].items())[:_SKIP_PRINT_CAP]:
            detail = ", ".join(f"{v} x{n}" for v, n in sorted(verdicts.items()))
            console.print(f"    {paper}: {detail}")
        more = len(integrity["damaged"]) - _SKIP_PRINT_CAP
        if more > 0:
            console.print(f"    [dim]... and {more} more paper(s)[/dim]")
        console.print(f"  [dim]Per-file detail: fetchpdf-verify {corpus}[/dim]")

    if not pending:
        console.print("[green]Nothing to do -- every paper already has a report.[/green]")
        return
    if dry_run:
        console.print("\n[bold]Would analyse:[/bold]")
        for p in pending[:20]:
            console.print(f"  {p.name}")
        if len(pending) > 20:
            console.print(f"  [dim]... and {len(pending) - 20} more[/dim]")
        console.print("\n[dim]Dry run -- nothing analysed, nothing spent.[/dim]")
        return

    # EVERY FIELD `batch.py` READS, not just the ones this command has a
    # flag for. It reads `args` as though argparse had built it, and five
    # fields were missing here: `metascience batch` failed on EVERY paper with
    # `'Namespace' object has no attribute 'image_forensics'` before reaching a
    # single API call. Found 2026-08-19 on an 11-paper run; the whole command
    # -- "One command, fully automated" -- could not analyse anything.
    #
    # The two track flags take `analyze`'s own defaults, so the two entry points
    # do the same thing: image detection and screening ON,
    # and text forensics ON (free, local, and a missed mill paper is the
    # costlier error). The three usage-guard fields are read only by the
    # standalone script's `main()`, never on this path, but they are supplied
    # anyway so this Namespace is a complete stand-in for the argparse one --
    # which is the invariant `test_batch_namespace_is_complete` now checks.
    args = Namespace(
        corpus=corpus, limit=limit, seed=None, subdir_name=subdir_name,
        skip_existing=skip_existing, no_move_to_done=not archive,
        concurrency=concurrency, timeout=timeout, budget_usd=budget_usd,
        mode="parallel", model=model, effort=effort, verbose=verbose,
        backend=be.name,
        image_forensics=image_forensics, text_forensics=True,
        pipeline=pipeline,
        no_usage_guard=False, usage_threshold=None, usage_max_wait_min=None,
        ignore_weekly_limit=False,
        # Global resource options have already configured the environment.
        device=None, gpu_memory_gib=None, gpu_reserve_gib=None,
    )
    # The plan above already dropped no-full-text and incomplete papers from
    # `pending`. `run_batch` used to call `pick_papers` on the corpus again,
    # so the table said "to run: 3" and then "Analyzing 6 papers" -- and the
    # skipped directories hit FileNotFoundError / ForensicToolsNeverRan as
    # if they were failures of analysis. Measured 2026-08-20 on grok_test.
    rc = asyncio.run(run_batch(args, papers=pending))
    _print_batch_usage(corpus)
    raise typer.Exit(rc)


_SKIP_PRINT_CAP = 20

#: Above this, `--timeout` stops being a guard and becomes a formality:
#: a stage that has hung is not distinguishable from one that is slow,
#: and nothing else in the batch will stop it. One hour is already far
#: above the slowest healthy stage measured here (997 s).
_TIMEOUT_WARN_SECONDS = 3600


def _supplement_integrity(corpus: Path) -> dict:
    """Do the supplements on disk still match what fetchpdf fetched?

    Why this exists (the 30-LFS-stub lesson): a real corpus held 30 git-lfs
    pointer stubs where its supplementary spreadsheets should have been, each
    130 bytes standing in for tens of KB, and every pointer's oid matched the
    sha256 the manifest recorded -- proof the bytes were downloaded intact and
    something afterward replaced them. Nothing noticed, because the integrity
    metadata was only ever written, never read back. A hollow supplement reads
    downstream as "this paper published no data", which this toolkit treats
    as a finding against the authors. So the batch plan reads it back.

    Best-effort in every branch: verify failures inform a batch, they never
    block one. The auditor lives in the SEPARATE fetchpdf repo (console
    script `fetchpdf-verify`) and is importable only where that package is
    installed -- the same guarded-import seam as `extraction/html.py`'s
    landing-page validator. When it is not importable, the absence is NAMED
    with the standalone command to run, never silent.

    Returns one of:
      {"status": "unavailable", "detail": str}   # fetchpdf not importable
      {"status": "error", "detail": str}         # audit crashed; still named
      {"status": "checked", "n_files": int, "n_intact": int,
       "n_unverifiable": int,
       "damaged": {paper_dir_name: {verdict: count}}}
    where the damage verdicts are fetchpdf's own vocabulary (lfs_pointer,
    hash_mismatch, size_mismatch, absent, ...), passed through unrenamed so
    this screen and `fetchpdf-verify` can never disagree about a file.
    """
    standalone = f"fetchpdf-verify {corpus}"
    try:
        from fetchpdf.retrieval.verify import INTACT, UNVERIFIABLE, audit_tree
    except ImportError:
        return {"status": "unavailable", "damaged": {},
                "detail": f"fetchpdf is not importable here. "
                          f"Run the standalone auditor: {standalone}"}
    try:
        results = audit_tree(str(corpus))
    except Exception as exc:  # noqa: BLE001 -- best-effort: inform, never block
        return {"status": "error", "damaged": {},
                "detail": f"audit failed ({type(exc).__name__}: {exc}). "
                          f"Run the standalone auditor: {standalone}"}

    damaged: dict[str, dict[str, int]] = {}
    n_intact = n_unverifiable = 0
    root = corpus.resolve()
    for path, verdict in results:
        if verdict == INTACT:
            n_intact += 1
            continue
        if verdict == UNVERIFIABLE:
            # An older manifest with nothing recorded to check against.
            # Not damage -- but not "intact" either, so it is counted apart.
            n_unverifiable += 1
            continue
        try:
            rel = Path(path).resolve().relative_to(root)
            paper = rel.parts[0] if len(rel.parts) > 1 else "(corpus root)"
        except ValueError:
            paper = Path(path).parent.name
        per = damaged.setdefault(paper, {})
        per[verdict] = per.get(verdict, 0) + 1
    return {"status": "checked", "n_files": len(results), "n_intact": n_intact,
            "n_unverifiable": n_unverifiable, "damaged": damaged}


def _print_skip_list(skips: list[tuple[Path, str]], *, dest: Path | None) -> None:
    """Name every skipped folder. A count in the plan table is not actionable."""
    if not skips:
        return
    console.print(f"\n[red bold]Skipped {len(skips)} folder(s).[/red bold]")
    for paper, reason in skips[:_SKIP_PRINT_CAP]:
        console.print(f"[red]SKIP  {paper.name}[/red]")
        console.print(f"[red]      {reason}[/red]")
    extra = len(skips) - _SKIP_PRINT_CAP
    if extra > 0:
        console.print(f"[red]      ... and {extra} more[/red]")
    if dest is None:
        return
    when = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with dest.open("a", encoding="utf-8") as fh:
            for paper, reason in skips:
                fh.write(json.dumps({
                    "paper": paper.name, "reason": reason, "when": when,
                }) + "\n")
        console.print(f"[dim]Skip list: {dest}[/dim]")
    except OSError:
        pass


def _print_batch_usage(corpus: Path) -> None:
    """Tokens and API-equivalent spend for a corpus, from batch_costs.jsonl.

    Runs go through a Claude Code subscription, so the dollar figure is what the
    same work WOULD have cost on the API. It is a planning and reporting number,
    not an invoice -- worth saying plainly, because a bare "$" in a report reads
    as money that left an account.
    """
    costs_path = corpus / "batch_costs.jsonl"
    if not costs_path.exists():
        return
    rows = []
    for line in costs_path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not rows:
        return

    n = len(rows)
    cost = sum(float(r.get("total_cost_usd") or 0) for r in rows)
    # Cache-read/creation ARE input. Counting only `input_tokens` made a
    # prompt-cached sweep look like it read nothing -- the live status line
    # already sums the three fields; this table has to agree with it.
    tin = sum(
        int(r.get("input_tokens") or 0)
        + int(r.get("cache_creation_input_tokens") or 0)
        + int(r.get("cache_read_input_tokens") or 0)
        for r in rows)
    tout = sum(int(r.get("output_tokens") or 0) for r in rows)

    # Every row is a CORPUS total over the whole ledger, every batch ever run
    # here, and is labelled so: it is printed right under a batch's own
    # "Batch cost (this run)", and a bare "papers analysed: 39" beside a
    # ten-paper corpus (three batches of the same ten) read as this run's
    # count. `n` counts ledger rows, i.e. paper RUNS, not distinct papers.
    n_papers = len({r.get("paper") for r in rows})
    t = Table(title="Usage for this corpus (all recorded runs)",
              show_header=False)
    t.add_column("", style="bold"); t.add_column("", justify="right")
    t.add_row("paper runs recorded", f"{n:,}  ({n_papers:,} distinct papers)")
    t.add_row("input tokens", f"{tin:,}")
    t.add_row("output tokens", f"{tout:,}")
    t.add_row("total tokens", f"{tin + tout:,}")
    t.add_row("average tokens in per paper run", f"{round(tin / n):,}")
    t.add_row("average tokens out per paper run", f"{round(tout / n):,}")
    t.add_row("API-equivalent cost, all runs", f"${cost:,.2f}")
    t.add_row("mean per paper run", f"${cost / n:,.2f}")
    timed = [float(r.get("total_wall_seconds") or 0) for r in rows]
    timed = [s for s in timed if s > 0]
    if timed:
        total_secs = sum(timed)
        t.add_row("runtime summed over paper runs", _fmt_runtime(total_secs))
        t.add_row("average runtime per paper run",
                  _fmt_runtime(total_secs / len(timed)))

    # Per model, because one blended mean over a corpus run partly on each
    # describes neither. Measured here: sonnet $5.22/paper vs opus $11.52.
    by_model: dict[str, list[float]] = {}
    for r in rows:
        by_model.setdefault(r.get("model") or "unrecorded", []).append(
            float(r.get("total_cost_usd") or 0))
    if len(by_model) > 1 or "unrecorded" not in by_model:
        for name, cs in sorted(by_model.items()):
            t.add_row(f"  {name}", f"{len(cs)} run{'s' if len(cs) != 1 else ''}, "
                                   f"${sum(cs):,.2f}, "
                                   f"${sum(cs) / len(cs):,.2f}/run")
    console.print(t)
    console.print(f"[dim]Per-paper detail: {costs_path}[/dim]")


@app.command("usage")
def usage_cmd(
    corpus: Path = typer.Argument(..., help="Corpus directory containing batch_costs.jsonl"),
):
    """Report tokens and API-equivalent spend for a corpus already analysed."""
    if not (corpus / "batch_costs.jsonl").exists():
        console.print(f"[yellow]No batch_costs.jsonl in {corpus} -- nothing recorded yet.[/yellow]")
        raise typer.Exit(1)
    _print_batch_usage(corpus)


@app.command("effect-size")
def effect_size_cmd(
    d: Optional[float] = typer.Option(None, "--d", help="Cohen's d, if already computed"),
    field: Optional[str] = typer.Option(None, "--field", help="social_psychology|cognitive_psychology|medicine_rct|education|psychotherapy (psychology_general withdrawn 2026-08-16: its median came from a correlation read as a d)"),
    mean1: Optional[float] = typer.Option(None, "--mean1"),
    sd1: Optional[float] = typer.Option(None, "--sd1"),
    n1: Optional[int] = typer.Option(None, "--n1"),
    mean2: Optional[float] = typer.Option(None, "--mean2"),
    sd2: Optional[float] = typer.Option(None, "--sd2"),
    n2: Optional[int] = typer.Option(None, "--n2"),
    design: Optional[str] = typer.Option(None, "--design"),
    provenance: str = typer.Option("printed_text", "--provenance", help="printed_text|printed_table|printed_figure|measured_vector|measured_raster"),
):
    """Is this effect size unusual for its field?

    Pass --field, or the tool reports the value and declines to judge: "large"
    is meaningless without a stated comparison class.

    Works on figure-derived values -- gross implausibility survives digitization
    error -- unlike GRIM/GRIMMER/SPRITE, which refuse them outright.
    """
    from .tools.effect_size import available_fields, check_effect_plausibility

    result = check_effect_plausibility(
        d=d, field=field, mean1=mean1, sd1=sd1, n1=n1,
        mean2=mean2, sd2=sd2, n2=n2, design=design, provenance=provenance,
    )
    if result.get("error") and "abs_d" not in result:
        console.print(f"[red]{result['error']}[/red]")
        console.print(f"[dim]Fields with benchmarks: {', '.join(available_fields())}[/dim]")
        raise typer.Exit(1)

    print_severity(result)
    console.print(f"\n[bold]|d|:[/bold] {result['abs_d']:.3f}")
    if result.get("computed_from_group_stats"):
        c = result["computed_from_group_stats"]
        console.print(f"[bold]Cohen's d:[/bold] {c['d']:.3f}   "
                      f"[bold]Hedges' g:[/bold] {c.get('hedges_g', float('nan')):.3f}  "
                      f"(J={c.get('hedges_correction_j', float('nan')):.4f})")
    if result.get("benchmark_source"):
        console.print(f"\n[bold]Benchmark:[/bold] {result['benchmark_source']}")
    if result.get("provenance_note"):
        console.print(f"\n[yellow]Provenance:[/yellow] {result['provenance_note']}")
    if result.get("note"):
        console.print(f"\n[yellow]{result['note']}[/yellow]")
    console.print(f"\n[dim]{result.get('methodology', '')}[/dim]")


@app.command("extract-figures")
def extract_figures_cmd(
    pdf_path: Path = typer.Argument(..., help="PDF to extract figures from"),
    out_dir: Optional[Path] = typer.Option(None, "--out-dir", "-o"),
    dpi: int = typer.Option(150, "--dpi"),
    no_pages: bool = typer.Option(False, "--no-pages", help="Skip full-page renders, crops only"),
):
    """Locate figures, crop them, and pair each with its caption.

    Local, free, no API. Caption-anchored rather than embedded-image based,
    because most journal charts are vector linework that image extraction
    cannot see at all.
    """
    from .image_plugin import load as _image_load
    _m = _image_load("extraction.figures")
    extract_figures, write_figures_json = _m.extract_figures, _m.write_figures_json

    if not pdf_path.exists():
        console.print(f"[red]Not found: {pdf_path}[/red]")
        raise typer.Exit(1)

    with console.status("Extracting figures..."):
        result = extract_figures(pdf_path, out_dir=out_dir, dpi=dpi, render_pages=not no_pages)
    if not result.get("success"):
        console.print(f"[red]{result.get('error')}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]{result['n_figures']} figures[/bold] -> {result['output_dir']}")
    table = Table()
    table.add_column("figure"); table.add_column("page", justify="right")
    table.add_column("error bars"); table.add_column("caption")
    for f in result["figures"]:
        meaning = f["error_bar_meaning"] or "[yellow]unstated[/yellow]"
        table.add_row(f["label"], str(f["page"]), meaning, (f["caption"] or "")[:58])
    if result["figures"]:
        console.print(table)
    for f in result["figures"]:
        for w in f["warnings"]:
            console.print(f"[yellow]{f['label']}:[/yellow] {w}")
    for w in result.get("warnings", []):
        console.print(f"[dim]{w}[/dim]")
    path = write_figures_json(result, result["output_dir"])
    console.print(f"\n[green]{path}[/green]")
    console.print("[dim]Caption text is PRINTED. Anything later read off the marks is "
                  "measured, and is refused by GRIM, GRIMMER, SPRITE and DEBIT.[/dim]")

    from .image_plugin import load as _image_load
    to_annotation_project = _image_load("extraction.figures").to_annotation_project
    project_path = Path(result["output_dir"]) / "figure_project.json"
    project_path.write_text(json.dumps(to_annotation_project(result), indent=2))
    console.print(
        f"\n[bold]Next -- verify before trusting any of this:[/bold]\n"
        f"  1. Open [bold]figure-extractor.html[/bold] and load {project_path}\n"
        f"  2. Correct bounds, split multi-panel figures into subfigures, fix mispaired captions\n"
        f"  3. Export annotations.json alongside it\n"
        f"[dim]Corrections come back as captionSource='manual' and are recorded as "
        f"human-verified. Figures left untouched are recorded as ai_proposed -- NOT the same "
        f"thing, because 'not contradicted' is not 'confirmed'.[/dim]"
    )


@app.command("check-table")
def check_table_cmd(
    json_path: Path = typer.Argument(..., help="JSON: {cells, variables, bindings, provenance}"),
    provenance: str = typer.Option("printed_table", "--provenance"),
):
    """Run every applicable check on a whole table in one go.

    Which checks apply is DETERMINED by cell kind x declared variable family --
    you do not choose them, and neither does the model. Refusals are generated
    per (cell, check) with a reason, so coverage does not depend on anything
    being remembered.
    """
    from .dispatch import check_table

    if not json_path.exists():
        console.print(f"[red]Not found: {json_path}[/red]")
        raise typer.Exit(1)
    spec = json.loads(json_path.read_text())
    r = check_table(spec.get("cells", []), spec.get("variables"),
                    spec.get("bindings"), provenance=spec.get("provenance", provenance))

    print_severity(r, f"{r['n_checks_run']} checks run, {r['n_not_run']} refused")
    if r["results"]:
        table = Table(title="Findings")
        table.add_column("tool"); table.add_column("severity"); table.add_column("cell")
        for x in r["results"]:
            table.add_row(x["tool"], x["severity"], str(x["cell"].get("row_label"))[:34])
        console.print(table)
    console.print(f"\n[bold]Consistent:[/bold] {len(r['consistent_index'])}")
    if r["not_run"]:
        console.print("\n[bold]Not run[/bold] (machine-generated reasons):")
        for x in r["not_run"]:
            console.print(f"  [dim]{str(x['cell'])[:26]:<26} {x['reason'][:88]}[/dim]")
    console.print(f"\n[dim]{r['methodology']}[/dim]")


@app.command("figures-verify")
def figures_verify_cmd(
    annotations: Path = typer.Argument(..., help="annotations.json exported from figure-extractor"),
):
    """Ingest human corrections from figure-extractor and record the verification.

    `load_annotations` has existed and been tested since the gate was built, and
    was reachable from nothing -- no CLI command, no pipeline call. This is its
    entry point.
    """
    from .image_plugin import load as _image_load
    load_annotations = _image_load("extraction.figures").load_annotations

    if not annotations.exists():
        console.print(f"[red]Not found: {annotations}[/red]")
        raise typer.Exit(1)
    out = load_annotations(json.loads(annotations.read_text()))

    color = {"human_verified": "green", "ai_proposed": "yellow", "unverified": "red"}
    console.print(f"[{color.get(out['verification'],'white')}]{out['verification'].upper()}"
                  f"[/{color.get(out['verification'],'white')}]: "
                  f"{out['n_human_verified']}/{out['n_figures']} figures corrected by a person, "
                  f"{out['n_subfigures']} subfigures")
    table = Table()
    table.add_column("figure"); table.add_column("status"); table.add_column("panels", justify="right")
    table.add_column("error bars")
    for f in out["figures"]:
        table.add_row(f["label"], f["verification"], str(f["n_subfigures"]),
                      f["error_bar_meaning"] or "[yellow]unstated[/yellow]")
    if out["figures"]:
        console.print(table)
    if out["verification"] != "human_verified":
        console.print(
            "\n[yellow]Not a verified pass.[/yellow] Figures left untouched are recorded as "
            "`ai_proposed`, never `human_verified` -- 'not contradicted' is not 'confirmed', "
            "and collapsing the two would let a rubber-stamped pass launder extraction error "
            "into apparent human confirmation."
        )
    console.print(f"\n[dim]{out['methodology']}[/dim]")


@app.command("repair-register")
def repair_register_cmd(
    review_dir: Path = typer.Argument(..., help="A forensic_review* directory"),
    paper_dir: Optional[Path] = typer.Option(
        None, help="Paper directory (default: the review's parent)"),
) -> None:
    """Build the value register for a review that was written without one.

    WHY THIS EXISTS. `write_review_outputs` builds the register only when it is
    told which paper the review is of, and `metascience batch` never told it --
    so every paper the batch analysed was written with no register at all, and
    no note saying so. The viewer then reported that the values were not
    registered, which reads as a fact about the paper rather than a gap in ours.

    NOTHING IS RE-ANALYSED AND NOTHING IS PAID FOR. The register is built from
    the tool calls and anatomy the run already saved beside the review, through
    the SAME `build_value_register` a live run uses -- a second implementation
    would make repaired reviews incomparable with fresh ones.
    """
    from .agent import build_value_register

    review_dir = review_dir.resolve()
    if not review_dir.is_dir():
        console.print(f"[red]Not a directory: {review_dir}[/red]")
        raise typer.Exit(1)
    paper = (paper_dir or review_dir.parent).resolve()

    def _load(name: str):
        f = review_dir / name
        if not f.is_file():
            return None
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]{name} is unreadable: {exc}[/red]")
            raise typer.Exit(1)

    findings = _load("findings.json")
    if findings is None:
        # REFUSED, not built empty. Without the anatomy there are no variables
        # to bind to, and a register built anyway would report every value as
        # unbound -- our missing file rendered as the paper's missing structure.
        console.print(f"[red]No findings.json in {review_dir}; nothing to "
                      "build a register from.[/red]")
        raise typer.Exit(1)

    # THE LEDGER THE RUN ALREADY WROTE. `toolcalls.*.json` records each call's
    # `input`, its `result` and whether that result was truncated -- 90.7% of
    # them parse, against 45% read back off the message stream, where a long
    # result arrives cut mid-JSON. Without it every verdict is dropped at a
    # silent parse and the register reports zero checks attached.
    ledger = (_load("toolcalls.stage1.json") or []) + (_load("toolcalls.stage2.json") or [])
    result = {"findings": findings,
              "_toolcall_ledger": ledger,
              "stage1": {"messages": _load("messages.stage1.json") or []},
              "stage2": {"messages": _load("messages.stage2.json") or []}}
    written = build_value_register(result, str(paper), review_dir)
    if not written:
        console.print("[red]Nothing was written -- see the code path.[/red]")
        raise typer.Exit(1)
    for name, path in written.items():
        console.print(f"  {name}: {path}")
    reg = written.get("value_register")
    if reg:
        d = json.loads(reg.read_text(encoding="utf-8"))
        cov = d.get("coverage") or {}
        console.print(
            f"  values {d.get('n_values')}  groups {d.get('n_groups')}  "
            f"design {d.get('n_design_values')}  "
            f"bound {d.get('n_values_bound_to_a_variable')}  "
            f"checked {cov.get('n_checked')}/{cov.get('n_table_groups')}")
        if cov.get("n_silent"):
            # The register's own note: any number above zero here is a bug in
            # this bookkeeping, not a finding about the paper. Printed rather
            # than left in the JSON, because a summary that shows only the
            # flattering counts is how a gap goes unnoticed.
            console.print(f"  [yellow]{cov['n_silent']} group(s) silent -- "
                          "a tool applied, no verdict, no recorded refusal. "
                          "That is our gap, not the paper's.[/yellow]")


@app.command("bundle")
def bundle_cmd(
    review_dir: Path = typer.Argument(..., help="A forensic_review* directory"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Bundle destination"),
    paper_dir: Optional[Path] = typer.Option(
        None, "--paper-dir", help="Paper directory (default: the review's parent)"),
    open_it: bool = typer.Option(False, "--open", help="Open the viewer afterwards"),
):
    """Assemble a self-contained review bundle with a browser viewer.

    Everything needed to audit a finding ends up in one directory: the paper,
    the text extracted from it, every analysis file, and the full tool-call
    chain. `viewer.html` is self-contained -- no server, no network, no install
    -- so double-clicking it works.
    """
    from .bundle import build_bundle

    if not review_dir.is_dir():
        console.print(f"[red]Not a directory: {review_dir}[/red]")
        raise typer.Exit(1)
    try:
        out = build_bundle(review_dir, output, paper_dir)
    except Exception as exc:
        console.print(f"[red]Could not build the bundle: {exc}[/red]")
        raise typer.Exit(1)

    viewer = out / "viewer.html"
    size_mb = viewer.stat().st_size / 1e6
    console.print(f"[green]Bundle written:[/green] {out}")
    console.print(f"  viewer.html  {size_mb:.1f} MB -- open this in a browser")
    win = _windows_path(viewer)
    if win:
        console.print(f"  [dim]Windows path:[/dim] {win}")
    if open_it:
        import webbrowser
        webbrowser.open(viewer.resolve().as_uri())


def _supplement_gate(paper_dir: Path, supplied, allow_incomplete: bool) -> dict:
    """Run the supplement gate, counting explicitly supplied files as present.

    A file passed with --supplement satisfies the requirement even if it lives
    outside the paper directory, so an operator is never forced to shuffle files
    around to get an honest run.

    THIS USED TO DECIDE THE ANSWER ITSELF, AND THE ANSWER WAS A CLAIM NOTHING
    HAD CHECKED. It overwrote `files_present` with the supplied paths and forced
    `missing = False` after testing only `Path.exists()` -- so a zero-byte
    `etable.xlsx` passed a gate that the identical file sitting IN the paper
    directory is refused by, `_unusable_because` never having run on it. The
    merge now happens inside `supplements.audit`, which applies the same
    usability verdict to a supplied file as to a discovered one, so there is one
    answer about which files we hold rather than two that can disagree.
    """
    from .supplements import gate

    return gate(paper_dir, allow_incomplete=allow_incomplete, extra=supplied)


def _windows_path(p: Path) -> Optional[str]:
    """Translate /mnt/c/... to C:\\... -- a WSL path is not openable from Windows."""
    s = str(p.resolve())
    if s.startswith("/mnt/") and len(s) > 6 and s[6] == "/":
        return s[5].upper() + ":" + s[6:].replace("/", "\\")
    return None


pipeline_app = typer.Typer(
    help="Pipelines: which modules a run uses and the tools agent's toolset.",
    no_args_is_help=True)
app.add_typer(pipeline_app, name="pipeline")


@app.command("run", context_settings={"allow_extra_args": True,
                                      "ignore_unknown_options": True})
def run_pipeline(
    ctx: typer.Context,
    pipeline: str = typer.Argument(..., help="A shipped pipeline name "
                                   "(`metascience pipeline list`) or a pipeline YAML path"),
    paper_path: str = typer.Argument(..., help="Paper directory, PDF or markdown file"),
):
    """Run a pipeline on a paper: `metascience run tools_grim paper.pdf`.

    The same as `metascience analyze PAPER --pipeline PIPELINE`; any further
    `analyze` option (`--backend grok`, `-o DIR`, ...) is passed through.
    """
    from typer.main import get_command
    analyze_cmd = get_command(app).commands["analyze"]
    analyze_cmd.main(args=[paper_path, "--pipeline", pipeline, *ctx.args],
                     prog_name="metascience run")


def _require_backend(backend: Optional[str], config) -> None:
    """A run that calls a model must NAME its backend (--backend or the
    pipeline file); there is no silent default to Claude Code. A pipeline that
    calls no model (image_detect, raw_data_only) needs none."""
    if backend or (config is not None and not config.uses_llm):
        return
    console.print(
        "[red]--backend is required: claude, codex, grok or openrouter "
        "(e.g. --backend claude).[/red]")
    raise typer.Exit(2)

from .tool_cli import tool_app  # noqa: E402
app.add_typer(tool_app, name="tool")


def _load_pipeline_or_exit(name_or_path: str):
    from . import pipeline_config as _pc
    try:
        return _pc.load(name_or_path)
    except _pc.PipelineConfigError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(2)


@pipeline_app.command("list")
def pipeline_list_cmd():
    """The shipped pipelines."""
    from . import pipeline_config as _pc
    for name in _pc.available():
        config = _pc.load(name)
        scope = "complete review" if config.complete_review else "partial"
        console.print(f"[bold]{name}[/bold]  ({scope})  {escape(config.description)}")


@pipeline_app.command("validate")
def pipeline_validate_cmd(
    pipeline: str = typer.Argument(..., help="Shipped pipeline name or path to a YAML file"),
):
    """Validate a pipeline and print the resolved plan. Calls no model."""
    config = _load_pipeline_or_exit(pipeline)
    console.print(escape(config.describe()))


@pipeline_app.command("show")
def pipeline_show_cmd(
    pipeline: str = typer.Argument(..., help="Shipped pipeline name or path to a YAML file"),
):
    """Print the resolved pipeline as JSON (what a run records)."""
    config = _load_pipeline_or_exit(pipeline)
    print(json.dumps(config.record(), indent=2))


@pipeline_app.command("tools")
def pipeline_tools_cmd():
    """The tools agent's tools and the named toolsets."""
    from . import pipeline_config as _pc
    console.print("[bold]Always included[/bold] (readers and check_table): "
                  + ", ".join(sorted(_pc.CORE_TOOLS)))
    console.print("[bold]Figure pass only[/bold] (options: {figures: true}): "
                  + ", ".join(sorted(_pc.FIGURE_TOOLS)))
    checks = [t for t in _pc._tool_agent_tools()
              if t not in _pc.CORE_TOOLS and t not in _pc.FIGURE_TOOLS]
    console.print(f"[bold]Checks[/bold] ({len(checks)}): " + ", ".join(checks))
    for name, tools in _pc.load_toolsets().items():
        console.print(f"[bold]toolset {name}[/bold]: " + ", ".join(tools))


@app.command("python")
def python_cmd():
    """Print the interpreter this CLI runs under. Use it as `PY=$(metascience python)`.

    The shell idiom it replaces, `$(head -1 $(which metascience) | tr -d '#!')`,
    returns `/bin/sh` when the console script is a shell shim (Dan's
    `~/.local/bin/metascience` is one). An agent then ran
    `$PY - <<'EOF' / import json ...` and `/bin/sh` executed `import json` as
    ImageMagick's screen grabber, leaving a 48 MB screenshot named `json` in
    the repo root (2026-10-18). `sys.executable` is answered by the interpreter
    itself, so no shim can stand in for it.
    """
    import sys
    print(sys.executable)


@app.command("models")
def models_cmd(
    backend: Optional[str] = typer.Option(
        None, "--backend",
        help="Backend to list models for (default: every backend). `antigravity` "
             "(alias `agy`) asks `agy models` live."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output"),
):
    """The model selector: which `--model` values each backend takes. Free.

    For antigravity the list is LIVE (`agy models`): it depends on the sign-in,
    so a static table would go stale. A slug such as `gemini-4-argon-high`
    fixes its own effort; a base name such as `gemini-4-argon` takes the
    pipeline's `--effort`, clamped to the levels that model offers. The other
    backends take their own CLI's aliases; only their default is shown.
    """
    import json as _json

    from .llm_backend import (
        ANTIGRAVITY_MODELS, _BACKENDS, list_antigravity_models, resolve_backend)

    names = [resolve_backend(backend).name] if backend else list(_BACKENDS)
    report: dict = {}
    for name in names:
        be = _BACKENDS[name]
        entry: dict = {"binary": be.binary, "default_model": be.default_model}
        if name == "antigravity":
            try:
                entry["models"] = [{"model": slug, "label": label}
                                   for slug, label in list_antigravity_models()]
            except RuntimeError as exc:
                entry["error"] = str(exc)
            entry["base_models"] = {k: list(v) for k, v in ANTIGRAVITY_MODELS.items()}
        report[name] = entry
    if as_json:
        print(_json.dumps(report, indent=2))
        return
    for name, entry in report.items():
        console.print(f"[bold]{name}[/bold] ({entry['binary']}): default "
                      f"[cyan]{entry['default_model']}[/cyan]")
        if "error" in entry:
            console.print(f"  [red]{entry['error']}[/red]")
        for m in entry.get("models", []):
            console.print(f"  {m['model']:<28} {m['label']}")
        if name == "antigravity" and entry.get("models"):
            console.print("  Pass a slug (`--model gemini-4-argon-high`) or a base name "
                          "(`--model gemini-4-argon`, effort from --effort).")


@app.command("backends")
def backends_cmd(
    backend: Optional[str] = typer.Option(
        None, "--backend", help="Show one backend only (default: all five)."),
    no_models: bool = typer.Option(
        False, "--no-models", help="Skip the model listings (no CLI/API calls "
                                   "beyond `--version`)."),
    all_models: bool = typer.Option(
        False, "--all", help="Print every OpenRouter model, not the first 15."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output"),
):
    """Which LLM backends are usable on THIS machine, and their models. Free.

    For each backend: whether its CLI is on PATH (OpenRouter: whether
    OPENROUTER_API_KEY is set), its version, the toolkit's default model, and
    the models it offers. Lists are LIVE where the backend can answer
    (`grok models`, `codex debug models`, `agy models`, OpenRouter's public
    catalog) and so reflect your sign-in; Claude Code has no listing command,
    so its aliases are shown. A default model absent from a live list is
    flagged: `--model` must then be given explicitly.
    """
    import json as _json

    from .llm_backend import (
        _BACKENDS,
        backend_binary_version,
        backend_installed,
        list_backend_models,
        resolve_backend,
    )

    names = [resolve_backend(backend).name] if backend else list(_BACKENDS)
    report: dict = {}
    for name in names:
        be = _BACKENDS[name]
        usable, where = backend_installed(be)
        entry: dict = {"usable": usable, "where": where,
                       "default_model": be.default_model}
        has_cli = name == "openrouter" or usable
        if has_cli:
            entry["version"] = backend_binary_version(be)
        if not no_models and has_cli:
            try:
                models, source = list_backend_models(name)
                entry["models"] = [{"model": m, "label": lbl} for m, lbl in models]
                entry["models_source"] = source
                if source == "live" and models:
                    entry["default_listed"] = any(
                        m == be.default_model or m.startswith(be.default_model + "-")
                        for m, _ in models)
            except RuntimeError as exc:
                entry["models_error"] = str(exc)
        report[name] = entry
    if as_json:
        print(_json.dumps(report, indent=2))
        return

    def out(*args):  # one line per model, never wrapped mid-label
        console.print(*args, soft_wrap=True)

    for name, e in report.items():
        mark = "[green]available[/green]" if e["usable"] else "[red]unavailable[/red]"
        out(f"[bold]{name}[/bold]  {mark}  {e['where']}"
                      + (f"  ({e['version']})" if e.get("version") else ""))
        default = f"  default --model [cyan]{e['default_model']}[/cyan]"
        if e.get("default_listed") is False:
            default += "  [yellow](not in this account's list)[/yellow]"
        out(default)
        if "models_error" in e:
            out(f"  [red]{e['models_error']}[/red]")
        models = e.get("models", [])
        shown = models if (all_models or name != "openrouter") else models[:15]
        if models:
            out(f"  models ({len(models)}, {e['models_source']}):")
        for m in shown:
            out(f"    {m['model']:<34} {m['label']}")
        if len(shown) < len(models):
            out(f"    ... {len(models) - len(shown)} more (--all)")
        out()


@app.command("preflight")
def preflight_cmd(
    corpus: Optional[Path] = typer.Argument(None, help="Corpus directory (optional)"),
    backend: Optional[str] = typer.Option(
        None, "--backend",
        help="LLM backend: claude (default), grok, codex, openrouter (our API loop; needs OPENROUTER_API_KEY), or antigravity (Google's agy CLI; `metascience models --backend antigravity` lists its models). The CLI-binary row follows this."),
    model: Optional[str] = typer.Option(
        None, "--model",
        help="Model alias used only for the corpus cost estimate. Default follows --backend."),
):
    """Check readiness BEFORE spending anything. Free.

    The statcheck check alone justifies this command: when statcheck is missing
    from the interpreter running the pipeline it returns `success: false`, and a
    whole corpus then reads as "contains no NHST statistics". That is a paid run
    producing confidently wrong coverage, detectable in milliseconds.

    The FATAL rows below are also enforced automatically before every paid run
    (see `preflight.assert_ready`, called from `agent._run_stage`), so a missing
    dependency stops the run instead of silently emptying it. This command
    remains the only way to check readiness WITHOUT starting one, and the only
    place the non-fatal rows and the corpus cost estimate are shown.
    """
    from .preflight import backend_reachable_row, fatal_checks, optional_checks
    from .llm_backend import resolve_backend

    be = resolve_backend(backend)
    model = model or be.default_model

    ok = True
    table = Table(title="Preflight")
    table.add_column("check"); table.add_column("status"); table.add_column("detail")

    def row(name, good, detail, fatal=True):
        nonlocal ok
        if not good and fatal:
            ok = False
        table.add_row(name, "[green]OK[/green]" if good else
                      ("[red]FAIL[/red]" if fatal else "[yellow]--[/yellow]"), detail)

    # Rendered from the SAME functions the automatic gate uses, so what this
    # command reports and what blocks a run cannot drift apart. `refresh=True`
    # because an operator running preflight after a `pip install` is asking
    # about the environment as it is NOW, not as it was at import time.
    for name, good, detail in fatal_checks(refresh=True, backend=be):
        row(name, good, detail)
    for name, good, detail in [backend_reachable_row(backend)] + optional_checks():
        row(name, good, detail, fatal=False)


    console.print(table)

    if corpus and corpus.is_dir():
        hist = _corpus_mean_cost(corpus, model)
        papers = len([d for d in corpus.iterdir() if d.is_dir()])
        console.print(f"\n[bold]Corpus:[/bold] {papers} directories")

        # WHAT THE MODEL WILL BE HANDED, before anything is spent. Numbers only
        # and no colour that means "bad": see `preflight.conversion_rows`, and
        # `corpus_state.render_diff` for why this project renders no verdict on
        # a measurement whose direction is ambiguous.
        from .preflight import conversion_rows
        rows = conversion_rows(corpus)
        if rows:
            console.print(
                "\n[bold]Conversion[/bold] -- what each run will actually read. "
                "No verdict is implied: 0 tables can mean the article prints "
                "none OR that the extractor could not see them, and only you "
                "can tell which.")
            console.print(
                f"  {'paper':<26} {'channel':<17} {'chars':>7} {'tbl':>4}"
                f"{'cap':>5}{'note':>5}{'degen':>6}{'dup':>5}")
            for r in rows:
                name, channel, chars = str(r[0])[:26], str(r[1])[:17], r[2]
                rest = ["-" if v is None else str(v) for v in r[3:]]
                console.print(
                    f"  {name:<26} {channel:<17} {chars:>7} {rest[0]:>4}"
                    f"{rest[1]:>5}{rest[2]:>5}{rest[3]:>6}{rest[4]:>5}",
                    highlight=False)

        if hist:
            mean, n = hist
            console.print(f"  measured mean this corpus ({model}, n={n}): ${mean:,.2f}/paper "
                          f"-> ~${mean*papers:,.0f} for all of them")
        else:
            console.print(f"  [yellow]no {model} history in batch_costs.jsonl[/yellow] -- cost for "
                          f"{model} is UNMEASURED on THIS corpus. Run `--limit 3` first and the "
                          "estimate becomes real.")

    console.print(f"\n[bold]{'READY' if ok else 'NOT READY'}[/bold]")
    raise typer.Exit(0 if ok else 1)


@app.command("lint-inert")
def lint_inert_cmd(
    detector: Optional[str] = typer.Option(
        None, "--detector", "-d",
        help="Run one detector only. Names: " + ", ".join(
            __import__("metascience_agent.inertness", fromlist=["DETECTORS"]).DETECTORS)),
    certain_only: bool = typer.Option(
        False, "--certain-only",
        help="Suppress the worklist and show only proven findings."),
    json_out: Optional[Path] = typer.Option(
        None, "--json", help="Write the full result as JSON."),
    fail_on_certain: bool = typer.Option(
        False, "--fail-on-certain",
        help="Exit non-zero if any `certain` finding exists. For CI."),
):
    """Scan OUR OWN code for machinery that looks like it works and does not.

    Not about a paper. This hunts the defect this project keeps finding by
    accident: a regex that cannot match, a function nothing calls, an exception
    that leaves no trace, a check that has never once returned anything but a
    pass. Every instance so far has had the same failure mode -- silence.

    `certain` findings are proven properties of the code. `worklist` findings
    are candidates a person must settle, and are the majority by design: a
    linter that overclaims gets switched off, and a switched-off linter is the
    very defect it exists to catch.
    """
    from .inertness import scan

    res = scan(only=[detector] if detector else None)
    rows = [f for f in res["findings"]
            if not certain_only or f["confidence"] == "certain"]

    for name, n in res["by_detector"].items():
        console.print(f"  [dim]{name:<28}[/] {n}")
    console.print()

    for f in sorted(rows, key=lambda r: (r["confidence"] != "certain", r["where"])):
        colour = "red" if f["confidence"] == "certain" else "yellow"
        console.print(f"[{colour}]{f['confidence']:<9}[/] [bold]{f['where']}[/]")
        console.print(f"            {f['what']}")
        console.print(f"            [dim]{f['evidence']}[/]")
    console.print(
        f"\n{len(rows)} shown  "
        f"({res['by_confidence'].get('certain', 0)} certain, "
        f"{res['by_confidence'].get('worklist', 0)} worklist)")

    if json_out:
        json_out.write_text(json.dumps(res, indent=2), encoding="utf-8")
        console.print(f"[dim]wrote {json_out}[/]")

    if fail_on_certain and res["by_confidence"].get("certain", 0):
        raise typer.Exit(1)


def main():
    """Entry point."""
    app()


@app.command("webapp-index")
def webapp_index_cmd(
    corpus: Optional[list[Path]] = typer.Argument(
        None, help="One or more corpus roots (a project each)"),
    output: Path = typer.Option(
        Path("webapp/data/index.json"), "--output", "-o",
        help="Where to write the index the workbench reads"),
    limit: Optional[int] = typer.Option(
        None, "--limit", help="Stop after this many papers per corpus (for a smoke test)"),
    projects_root: Optional[Path] = typer.Option(
        None, "--projects-root",
        help="Parent of project folders (masliah_papers, cerebrolysin_papers, …). "
             "When set, corpus arguments are ignored."),
    to_stdout: bool = typer.Option(
        False, "--stdout", help="Print JSON to stdout instead of (or as well as) writing a file"),
):
    """Scan corpora into the index the review workbench reads.

    Local, free and offline: it reads small JSON and calls `stat`. It does NOT
    call `bundle.collect`, which renders every PDF page to a JPEG -- right for
    one paper on demand, ruinous across four hundred.

    The counts it prints are the point. A corpus is rarely "N papers analysed":
    it is N papers of which some were never fetched, some had one check run and
    the answer discarded, and some have been reviewed three times across a
    version boundary that makes the three incomparable.
    """
    from .webapp_index import scan_corpus, scan_projects, sort_papers

    if projects_root is not None:
        from .atomicio import file_lock, atomic_write_text
        with file_lock(output.with_suffix(".lock")):
            payload = scan_projects(projects_root, limit=limit)
            for proj in payload["projects"]:
                proj["corpus"]["papers"] = sort_papers(proj["corpus"]["papers"])
                if not to_stdout:
                    console.print(
                        f"[bold]{proj['name']}[/bold] — {proj['n_papers']} papers  "
                        f"pdf {proj['n_pdf']}  xml {proj['n_xml']}  "
                        f"agent {proj['n_agent_run']}  reviewed {proj['n_human_reviewed']}")
            output.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(output, json.dumps(payload, indent=2, default=str))
        if to_stdout:
            # JSON only: the workbench parses stdout. Pretty tables go to stderr
            # via Console only when a human is watching.
            print(json.dumps(payload, default=str))
            return
        console.print(f"\nWrote [bold]{output}[/bold] "
                      f"({payload['n_projects']} projects, "
                      f"{payload['n_papers']} papers)")
        return

    if not corpus:
        console.print("[red]pass one or more corpus roots, or --projects-root[/red]")
        raise typer.Exit(2)

    corpora = []
    for root in corpus:
        ix = scan_corpus(root, limit=limit)
        ix["papers"] = sort_papers(ix["papers"])
        corpora.append(ix)
        T = ix["totals"]
        console.print(f"\n[bold]{root}[/bold] — {T['n_papers']} papers")

        src = T["sources"]
        held, missing = src["held"], src["not_fetched"]
        console.print(f"  held: {held}   not fetched: "
                      + (f"[yellow]{missing}[/yellow]" if missing else "0")
                      + f"   empty: {src['empty']}")
        if missing:
            console.print("    [dim]a landing page and no PDF -- the publisher "
                          "served an interstitial. Our gap, not the paper's.[/dim]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("channel")
        # EVERY state, from the declared vocabulary rather than a literal four.
        # `unknown` was omitted here, and `cross_paper` emits it for a whole
        # corpus at a time (an unswept root): those papers would have been
        # absent from every column, so the row would have summed to less than
        # the corpus and nothing would have said why.
        from .webapp_index import CHANNEL_STATES as _CS
        for st in _CS:
            table.add_column(st.replace("_", " "), justify="right")
        for ch, states in T["channels"].items():
            table.add_row(ch, *[str(states.get(s, 0)) for s in _CS])
        console.print(table)

        unswept = T["channels"].get("cross_paper", {}).get("unknown", 0)
        if unswept:
            console.print(
                f"  [yellow]{unswept} paper(s): no cross-paper sweep has run "
                f"over this corpus.[/yellow]\n"
                "    [dim]The sweep writes into a paper only when it MATCHES, "
                "so 'no file' cannot distinguish a paper cleared against 400 "
                "others from one never compared. It is local and free: "
                "metascience image-corpus <corpus-root>[/dim]")

        discarded = T["channels"]["image_forensics"]["ran_result_discarded"]
        if discarded:
            console.print(
                f"  [yellow]{discarded} paper(s) ran the image detector and "
                f"retained no result.[/yellow]\n"
                "    [dim]Not 'found nothing' and not 'did not run': what it "
                "concluded is unrecoverable without re-running it. The panels "
                "are still on disk, so re-running is cheap and local.[/dim]")

        if T["total_cost_usd"]:
            console.print(f"  spent so far: ${T['total_cost_usd']}")
        if ix["errors"]:
            console.print(f"  [red]{len(ix['errors'])} directory(ies) could not "
                          f"be read[/red]")

    payload = {"schema_version": corpora[0]["schema_version"],
               "corpora": corpora,
               "n_papers": sum(c["totals"]["n_papers"] for c in corpora)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, default=str))
    if to_stdout:
        print(json.dumps(payload, default=str))
    size = output.stat().st_size / 1024
    console.print(f"\nWrote [bold]{output}[/bold] ({size:.0f} KB, "
                  f"{payload['n_papers']} papers)")


@app.command("paper-issues")
def paper_issues_cmd(
    paper_dir: Path = typer.Argument(..., help="Paper directory"),
):
    """Unified, prioritized issues for the rapid reviewer (JSON on stdout)."""
    from .review_issues import collect_issues
    print(json.dumps(collect_issues(paper_dir), default=str))


@app.command("locators")
def locators_cmd(
    paper_dir: Path = typer.Argument(..., help="Paper directory"),
):
    """Page/section locators for each reviewable issue (JSON on stdout)."""
    from .locators import locators_for_paper
    from .review_issues import collect_issues
    issues = collect_issues(paper_dir)["issues"]
    print(json.dumps(locators_for_paper(paper_dir, issues), default=str))


@app.command("review-write")
def review_write_cmd(
    paper_dir: Path = typer.Argument(..., help="Paper directory"),
    patch: str = typer.Option(..., "--patch", help="JSON patch to merge into review.json"),
):
    """Merge a human-review patch into review.json beside the paper.

    The file is MASTER; when a database URL resolves the merged verdicts
    are also mirrored into the findings database best-effort (append-only, change-detected)
    so SQL sees decisions at click time rather than at the next bulk push.
    """
    from .review_io import write_review
    try:
        body = json.loads(patch)
    except ValueError as exc:
        console.print(f"[red]bad --patch JSON: {exc}[/red]")
        raise typer.Exit(2)
    merged = write_review(paper_dir, body)
    from . import db_push as _db
    mirror = _db.mirror_review(paper_dir)
    out = dict(merged)
    out["db_mirror"] = mirror        # printed only, never written to disk
    print(json.dumps(out, default=str))


_image_command("image-review-items", "image_review_items_cmd")


_image_command("image-review-write", "image_review_write_cmd")


_image_command("image-summary-figure", "image_summary_figure_cmd")


@app.command("view-record")
def view_record_cmd(
    paper_dir: Path = typer.Argument(..., help="Paper directory"),
    viewer: Optional[str] = typer.Option(
        None, "--viewer", help="Who opened it; omit for an anonymous view"),
    at: Optional[str] = typer.Option(
        None, "--at", help="ISO timestamp; defaults to now (UTC)"),
):
    """Record that somebody opened this paper's results page.

    Writes `views.json` beside the paper. NOT `review.json`: opening a paper
    is not judging it, and the workbench must never report a passer-by as a
    reviewer. Unlike `review-write` this refreshes no index and mirrors to no
    database -- the project table rescans on every load.
    """
    from .views_io import record_view
    print(json.dumps(record_view(paper_dir, viewer=viewer, at=at),
                     default=str))


@app.command("article-html")
def article_html_cmd(
    paper_dir: Path = typer.Argument(..., help="Paper directory"),
):
    """Right-pane source: PDF path, or XML/HTML render, plus a DOI download link."""
    from .extraction.xml_html import article_view
    print(json.dumps(article_view(paper_dir), default=str))


@app.command("sheet-view")
def sheet_view_cmd(
    paper_dir: Path = typer.Argument(..., help="Paper directory"),
    file: str = typer.Option(..., "--file", help="Paper-relative path to the spreadsheet"),
    sheet: Optional[str] = typer.Option(None, "--sheet"),
    highlights: Optional[str] = typer.Option(
        None, "--highlights", help="JSON array of {sheet,cell,row,col}"),
):
    """Read-only grid of one worksheet for the review workbench."""
    from .finding_files import read_sheet, relativize, resolve
    spec = relativize(file, paper_dir)
    found, reason = resolve(paper_dir, spec)
    if found is None:
        print(json.dumps({"error": reason, "sheets": [], "rows": []}))
        return
    cells = []
    if highlights:
        try:
            cells = json.loads(highlights)
        except ValueError:
            cells = []
    print(json.dumps(read_sheet(found, sheet, cells), default=str))


@app.command("paper-view")
def paper_view_cmd(
    paper_dir: Path = typer.Argument(..., help="Paper directory"),
    run: Optional[str] = typer.Option(
        None, "--run",
        help="Serve this review directory by name (the GUI run picker); "
             "an unknown name falls back to the newest usable run."),
):
    """Issues, locators and article HTML in one JSON object (one process)."""
    from .extraction.xml_html import article_view
    from .locators import locators_for_paper
    from .review_issues import collect_issues
    issues = collect_issues(paper_dir, run=run)
    print(json.dumps({
        "issues": issues,
        "locators": {} if issues.get("archived_article") else locators_for_paper(paper_dir, issues["issues"]),
        "article": issues.get("archived_article") or article_view(paper_dir),
    }, default=str))


@app.command("fetch-metadata")
def fetch_metadata_cmd(
    paper_dir: Optional[Path] = typer.Argument(
        None, help="One paper directory. Omit when using --project-dir."),
    project_dir: Optional[Path] = typer.Option(
        None, "--project-dir",
        help="Fetch for every paper under this project (reads cache; network only when missing)."),
    projects_root: Optional[Path] = typer.Option(
        None, "--projects-root",
        help="Parent of project folders; fetches every paper in every project."),
    force: bool = typer.Option(
        False, "--force", help="Re-fetch even when metadata.json already has a title."),
    limit: Optional[int] = typer.Option(
        None, "--limit", help="Stop after this many network fetches (for a smoke test)."),
    offline: bool = typer.Option(
        False, "--offline", help="XML and cache only; do not call the DOI APIs."),
):
    """Pull bibliographic metadata (title, authors, journal, volume, issue, year).

    Uses the observatory DOI cascade (DataCite → Crossref → Unpaywall →
    PubMed → …). Writes `metadata.json` beside the paper. The workbench
    index only READS that file — scan after a batch fetch to refresh the
    table.
    """
    from .paper_metadata import ensure_metadata, has_displayable
    from .webapp_index import iter_paper_dirs

    if paper_dir is not None and project_dir is None and projects_root is None:
        rec = ensure_metadata(paper_dir, force=force, network=not offline)
        print(json.dumps(rec, default=str))
        return

    targets: list[Path] = []
    if projects_root is not None:
        from .webapp_index import _NOT_A_PROJECT
        root = Path(projects_root)
        for child in sorted(root.iterdir()):
            if child.is_dir() and not child.name.startswith(".") \
                    and child.name not in _NOT_A_PROJECT:
                targets.extend(iter_paper_dirs(child))
    elif project_dir is not None:
        targets = iter_paper_dirs(project_dir)
    else:
        console.print("[red]pass a paper directory, --project-dir, or --projects-root[/red]")
        raise typer.Exit(2)

    ok = failed = 0
    for i, d in enumerate(targets, start=1):
        rec = ensure_metadata(d, force=force, network=not offline)
        if has_displayable(rec):
            ok += 1
        else:
            failed += 1
            console.print(f"[yellow]{d.name}[/yellow]  {rec.get('error') or 'no title'}")
        if i % 25 == 0 or i == len(targets):
            line = f"  {i}/{len(targets)}  {ok} with title  {failed} without"
            console.print(line)
            print(line, flush=True)
        if limit is not None and (ok + failed) >= limit:
            break
    console.print(f"{ok} with title  {failed} without  of {ok + failed}")
    print(json.dumps({"n_ok": ok, "n_failed": failed, "n": ok + failed},
                     default=str))


@app.command("needs-fetch")
def needs_fetch_cmd(
    target: Path = typer.Argument(..., help="A paper directory, or a corpus of them."),
    json_out: Optional[Path] = typer.Option(
        None, "--json", help="Write the records here as JSON."),
):
    """Papers whose fetched HTML is not the article, and the URL to fetch by hand.

    THE FIX FOR A BOT CHALLENGE IS A PERSON, NOT A RETRY. Greg's ruling,
    2026-09-05: a Cloudflare interstitial is unavoidable, so prompt the operator
    and hand them the URL rather than escalating to a headed browser. That is a
    minimal demand set against being able to read the paper at all.

    WHY IT IS NOT COSMETIC. MEASURED 2026-09-05 on the cerebrolysin corpus: 16
    directories hold an HTML file that `find_html` accepts as the article, and
    on 13 of them `_derive_paper_text` returned it -- 228 characters reading
    "Client Challenge. JavaScript is disabled in your browser." served as the
    paper's full text. This toolkit reports absent data as a finding, so a paper
    read from an interstitial produces accusations against its authors for our
    failed fetch. Those papers now serve NO text, which is honest, and appear
    here, which is actionable.
    """
    import json as _json
    from .extraction.html import manual_fetch_needed

    base = Path(target)
    if not base.is_dir():
        typer.echo(f"not a directory: {base}")
        raise typer.Exit(2)
    dirs = [base] if (list(base.glob("*.pdf")) or list(base.glob("*.xml"))) else \
        [d for d in sorted(base.iterdir()) if d.is_dir()]
    rows = []
    for d in dirs:
        rec = manual_fetch_needed(d)
        if rec:
            rec["paper"] = d.name
            rows.append(rec)
    if not rows:
        typer.echo(f"{len(dirs)} paper(s) checked; none is waiting on a manual fetch.")
        return
    typer.echo(f"{len(rows)} of {len(dirs)} paper(s) need the article page fetched by hand:\n")
    for r in rows:
        typer.echo(f"  {r['paper']}")
        typer.echo(f"      why : {r['reason']}")
        typer.echo(f"      url : {r['url']}  ({r['url_source']})")
        typer.echo(f"      then: {r['action']}")
    if json_out:
        Path(json_out).write_text(_json.dumps(rows, indent=1), encoding="utf-8")
        typer.echo(f"\nwrote {json_out}")


@app.command("runs")
def runs_cmd(
    target: Path = typer.Argument(..., help="A paper directory, or a corpus of them."),
    horizon_days: Optional[int] = typer.Option(
        None, "--horizon-days",
        help="Override the 14-day default. Use --all to disable entirely."),
    show_all: bool = typer.Option(
        False, "--all", help="List stale runs too, with their ages."),
):
    """Which runs describe the system as it is now, and which do not.

    A run older than two weeks is output from code that may no longer exist.
    Reading one is how a fixed defect gets rediscovered: on 2026-08-28 an agent
    censused 416 findings from 16 archived runs, concluded the severity gate had
    never governed a shipped finding, and was wrong twice -- the gate postdated
    every run in the census, and the current pipeline writes a different file.

    This is the sanctioned way to ask. Prefer it to globbing `forensic_review*`,
    which cannot tell you a directory's age: measured 2026-08-29, all 15
    archived run directories carry the same mtime from a bulk copy while their
    own recorded dates span six days.
    """
    from . import runs as _runs

    base = Path(target)
    papers = ([base] if list(base.glob("forensic_review*"))
              else sorted(d for d in base.iterdir() if d.is_dir()))
    n_cur = n_stale = 0
    for paper in papers:
        part = _runs.current_runs(
            paper, horizon_days=(None if horizon_days is None else horizon_days))
        if not part["current"] and not part["stale"]:
            continue
        n_cur += part["n_current"]; n_stale += part["n_stale"]
        console.print(f"\n[bold]{paper.name}[/bold]")
        for d in part["current"]:
            when, how = _runs.run_date(d)
            console.print(f"  [green]current[/green]  {d.name}"
                          f"   {str(when)[:10]} ({how})", highlight=False)
        if show_all:
            for d in part["stale"]:
                console.print(f"  [yellow]stale  [/yellow]  {d.name}"
                              f"   {part['why'][str(d)]}", highlight=False)
    # NEVER SILENT. "No runs" and "nine runs, all stale" are different facts,
    # and a shorter list renders the second as the first.
    console.print(f"\n{n_cur} current run(s), {n_stale} excluded as stale.")
    if n_stale and not show_all:
        console.print("[dim]Re-run with --all to see them and their ages. "
                      "They are output from code that may no longer exist; "
                      "do not argue from them without saying you did.[/dim]")


@app.command("corpus-state")
def corpus_state_cmd(
    corpus: Path = typer.Argument(..., help="Directory of paper directories."),
    out: Optional[Path] = typer.Option(
        None, "--out", help="Write the snapshot as JSON."),
    baseline: Optional[Path] = typer.Option(
        None, "--baseline", help="A snapshot to compare against."),
):
    """Snapshot what the register says about a corpus, or diff two snapshots.

    Built for one job: telling an improvement from a regression ACROSS A MERGE.
    Every number this project holds is a claim about the code that produced it,
    and 2026-08-20 produced three cases of such a claim being falsified by a
    change made elsewhere. Write the before down, merge, run it again, read the
    difference.

    IT RENDERS NO VERDICT, deliberately. `n_ambiguous_columns` rising could mean
    the reader got worse or that it began reading tables it used to skip --
    opposite conclusions from one delta. A tool that judged would invite tuning
    until the judgement was green.
    """
    import json as _json

    from . import corpus_state as _cs

    snap = _cs.snapshot_corpus(corpus)
    t = snap["totals"]
    console.print(f"[bold]{t['n_papers']} paper(s)[/bold] under {corpus}"
                  + (f"  [red]({t['n_papers_failed']} failed)[/red]"
                     if t.get("n_papers_failed") else ""))
    for k in ("n_groups", "n_values", "n_table_groups", "n_ambiguous_columns",
              "n_untyped_groups", "n_cells_with_no_value",
              "n_stale_cache_warnings",
              # THE NUMERAL FLOOR. `n_numerals_total` is the denominator of
              # every "numbers we did not check" claim, and it was absent from
              # this summary AND from the baseline -- so a repackaging pass that
              # shrank it upstream of indexing would have printed nothing at all.
              "n_numerals_total", "n_numerals_judged"):
        console.print(f"  {k:<26} {t.get(k, 0)}")
    roles = t.get("roles") or {}
    if roles:
        console.print("  roles: " + ", ".join(
            f"{k}={v}" for k, v in sorted(roles.items(), key=lambda kv: -kv[1])))
    for f in snap.get("failed") or []:
        console.print(f"  [red]FAILED[/red] {f['paper']}: {f['error']}")

    if out:
        out.write_text(_json.dumps(snap, indent=1), encoding="utf-8")
        console.print(f"\nwrote {out}")

    if baseline:
        before = _json.loads(Path(baseline).read_text(encoding="utf-8"))
        console.print("\n[bold]diff against " + str(baseline) + "[/bold]")
        console.print(_cs.render_diff(_cs.diff(before, snap)))


@app.command("paired-d-interval")
def paired_d_interval_cmd(
    dz: float = typer.Option(None, "--dz", help="Cohen's dz, as the paper reports it"),
    t: float = typer.Option(None, "--t", help="paired t statistic (with --n, if dz is absent)"),
    n: int = typer.Option(None, "--n", help="number of pairs"),
    r: float = typer.Option(None, "--r", help="pre-post correlation, IF the paper reports one"),
):
    """What a within-subjects d could be when the correlation is unreported.

    d_av = d_z * sqrt(2*(1-r)), and papers reporting d_z almost never report r.
    Use `ttest --within` first: when both pre and post SDs are printed it
    RECOVERS r, which beats assuming it. This is for when they are not, and it
    reports the interval rather than picking a point inside it.
    """
    from .tools.effect_size import paired_d_interval as _pdi

    result = _pdi(dz=dz, t=t, n=n, r=r)
    bail_on_error(result)
    print_severity(result)
    console.print_json(data=result)


@app.command("package-tables")
def package_tables_cmd(
    paper_dir: Path = typer.Argument(..., help="Paper directory"),
    out: Path = typer.Option(None, "--out", help="Where to write; default <paper>/tables/"),
):
    """Write the printed tables, plus a DERIVED split of composite ones.

    A journal prints several logical tables as one physical table, separated by
    a banner row. This materialises both: `printed/` holds each table as the
    paper printed it, `blocks/` holds each recovered section, and every block
    records which printed table and which of its rows it came from.

    The printed table is canonical. Nothing in `blocks/` is evidence, no value
    is ever anchored to a block, and a finding may only cite the printed table
    -- which is what lets the split exist without breaking provenance.
    """
    from . import table_package as _tp

    idx = _tp.build(paper_dir, out)
    if idx.get("error"):
        console.print(f"[red]{idx['error']}[/red]")
        raise typer.Exit(code=1)
    console.print(
        f"[green]{len(idx['printed'])}[/green] printed table(s), "
        f"[green]{len(idx['blocks'])}[/green] derived block(s) -> "
        f"{out or (Path(paper_dir) / _tp.PACKAGE_DIR)}")


@app.command("lint-handoff")
def lint_handoff_cmd(
    review_dir: Path = typer.Argument(..., help="A forensic_review* directory"),
    paper_dir: Path = typer.Option(None, "--paper-dir",
                                   help="The paper directory, for contracts that need it"),
    fail_on_violation: bool = typer.Option(
        False, "--fail", help="Exit non-zero when any contract is violated"),
):
    """Did each stage's work ARRIVE, or was it computed and dropped?

    `inertness` proves a name is referenced nowhere. This asks a different
    question that no syntax tree can answer: a producer WAS called, and its
    output reaches no consumer. `grace.py` is the case that motivated it --
    called by `tools/regression.py`, reaching no report, invisible to a
    call-graph scan.

    Three states, and the third is what keeps it usable: a contract whose
    producing situation never arose reports `precondition_absent`, not a
    violation. A linter that fires on every ordinary paper gets switched off.
    """
    from . import handoff_contracts as _hc

    run = _hc.load_run(review_dir, paper_dir)
    results = _hc.audit(run)
    console.print(_hc.render(results))
    if fail_on_violation and any(r.state == _hc.VIOLATED for r in results):
        raise typer.Exit(code=1)


@app.command("register-view")
def register_view_cmd(
    paper_dir: Path = typer.Argument(..., help="Paper directory"),
    review_dir: Path = typer.Option(
        None, "--review-dir",
        help="Which review's register to draw. Default: the most recent "
             "forensic_review* directory that actually has one."),
    out: Path = typer.Option(
        None, "--out", help="Where to write the HTML. Default: beside the register."),
):
    """Draw the value register ON the paper, so gaps are visible as gaps.

    The register answers "what did we index?". A list of what we indexed
    cannot show what we MISSED, because a miss has no row. This renders the
    other direction: the extracted body text with every indexed numeral
    marked, and every walked table tinted by what happened to each cell.
    An unmarked cell is one no register group claimed.
    """
    from . import register_view as _rv

    written = _rv.build(paper_dir, review_dir, out)
    console.print(f"[green]wrote[/green] {written}")


@app.command("history-import")
def history_import_cmd(root: Path, dry_run: bool = typer.Option(False, "--dry-run")):
    """Inventory/import saved runs without rerunning analysis or screening."""
    from .analysis_history import import_history
    print(json.dumps(import_history(root, dry_run=dry_run)))


@app.command("copy-paste")
def copy_paste_history_cmd(path: Path, project_root: Path = typer.Option(..., "--project-root"),
                          paper: Path = typer.Option(..., "--paper"),
                          sheet: Optional[str] = None, data_context: str = "unknown",
                          max_row_pairs: int = 5000,
                          exclude_column: Optional[list[str]] = typer.Option(None, "--exclude-column"),
                          highlight_out: Optional[Path] = typer.Option(None, "--highlight-out")):
    """Run the standalone detector and preserve its versioned project history."""
    from copy_paste_detector import detect_raw_duplication, highlight_workbook
    from .analysis_runs import Archive, provenance, now
    from .analysis_history import capture_copy
    history = Archive(project_root)
    parameters = dict(sheet=sheet, data_context=data_context, max_row_pairs=max_row_pairs, exclude_columns=exclude_column)
    e = history.execution("copy_paste", components=["copy_paste"], configuration=parameters, provenance=provenance("copy_paste"))
    run = history.start(e["id"], "copy_paste", paper.resolve().relative_to(history.root).as_posix(), provenance=provenance("copy_paste", parameters=parameters))
    try:
        from .history_runtime import snapshot_copy_input
        captured_path = snapshot_copy_input(history, run, path) or path
        result = detect_raw_duplication(str(captured_path), **parameters)
        if highlight_out and not result.get("error"):
            result["highlight"] = highlight_workbook(captured_path, result["duplicate_groups"], highlight_out)
        saved = capture_copy(history.root, paper, result, captured_path, run=run, highlight=highlight_out)
        history.finish_execution(e["id"], saved["status"])
        from .history_db import try_sync
        saved["sync"] = try_sync(history.root, [saved["id"]])
        print(json.dumps({"run_id": saved["id"], "execution_id": e["id"], "result": result}, default=str))
    except BaseException as exc:
        if not (history.base / "runs" / f"{run['id']}.json").exists():
            history.seal(run, status="failed", detail=str(exc), completed_at=now())
        raise


@app.command("history-db-migrate")
def history_db_migrate_cmd(dry_run: bool = typer.Option(False, "--dry-run")):
    """Apply the additive component-history database migration."""
    from .history_db import migration_sql, migrate
    from . import db_push
    if dry_run:
        print(migration_sql())
    else:
        with db_push._connect(None, connect_timeout=10) as conn:
            print(json.dumps(migrate(conn)))


@app.command("history-sync")
def history_sync_cmd(root: Path):
    from .history_db import try_sync
    print(json.dumps(try_sync(root)))


@app.command("history-import-copy")
def history_import_copy_cmd(source: Path, project_root: Path = typer.Option(..., "--project-root"),
                            paper: Path = typer.Option(..., "--paper")):
    """Import portable copy/paste output or an older detector JSON file."""
    from .analysis_history import import_copy
    print(json.dumps(import_copy(project_root, paper, source), default=str))


if __name__ == "__main__":
    main()
