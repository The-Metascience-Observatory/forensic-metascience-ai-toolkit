"""
Environment readiness checks, run automatically before anything is spent.

The dependencies this pipeline needs fail QUIETLY, which is why this exists as
a gate and not merely as documentation. A missing `statcheck` does not raise --
the tool returns `success: false` with an empty result, and a whole corpus then
reads as "contains no NHST statistics". That mistake has been made here: a
95-paper corpus briefly read as containing zero test statistics.

The same class of failure hit supplements. `python-docx` and `openpyxl` are
declared HARD dependencies in pyproject.toml, but the venv was built by uv with
an editable install, which does not re-resolve when the manifest changes. They
were declared, absent, and invisible: 56 supplements (50 .docx, 6 .xlsx) read as
empty, `extract_supplement` returned a structured error that looked like a
property of the FILE rather than of the environment, and a 1.77 MB Word
supplement holding 3 tables and 11,198 characters was reduced to nothing in a
billed run.

Two design decisions, both deliberate:

- **Fatal vs non-fatal is decided by whether a missing dependency makes a run
  WRONG, not merely worse.** Absent R, `wkhtmltopdf` or PyMuPDF degrades a run
  (no cross-check, no `report.pdf`, no figure pass) and is always reported but
  never blocks. Absent `statcheck` or `python-docx` makes the output
  confidently wrong while still looking complete, so it blocks.
- **This fails CLOSED, unlike `usage_guard`.** The usage guard fails open on
  purpose: a `/usage` probe that breaks must never stop a batch, because the
  worst case there is wasted spend. Here the worst case is a paid run that
  silently checked nothing, so refusing is the safe direction. Set
  `METASCIENCE_SKIP_PREFLIGHT=1` to override for a deliberate partial install.
"""

import importlib
import os
import json
from pathlib import Path

import shutil
import subprocess

#: (name, ok, detail) for one check.
CheckRow = tuple[str, bool, str]

#: Cached result of :func:`fatal_checks`, keyed by backend name. `_run_stage`
#: fires 2-3 times per paper and the batch runner reuses one process across
#: many papers; imports are idempotent, so re-running them per stage is pure
#: waste. Keyed by backend so a process that switches engines re-probes.
_CACHE: dict[str, list[CheckRow]] | None = None


class PreflightError(RuntimeError):
    """A dependency needed for correct output is missing.

    Raised instead of returned so it propagates out of `_run_stage` before a
    subprocess is launched. The batch runner special-cases this the way it does
    `WeeklyLimitReached`: it is an environment fault affecting every paper, not
    a per-paper failure, so it must not be recorded in `failed.jsonl` as a
    retryable paper -- retrying cannot fix a missing library, and a queue full
    of papers that were never really attempted is worse than a loud stop.
    """


def _module_check(name: str, module: str, detail_ok: str, detail_bad: str) -> CheckRow:
    try:
        importlib.import_module(module)
        return (name, True, detail_ok)
    except ImportError:
        return (name, False, detail_bad)


def fatal_checks(refresh: bool = False, backend=None) -> list[CheckRow]:
    """The checks whose failure makes a run silently WRONG.

    Cached after the first call unless ``refresh`` is set. Never raises: the
    caller decides what a failure means, so the `preflight` command can render
    every row while `assert_ready` aborts on the same data.

    The CLI binary row is the *resolved* backend's -- a missing `grok` is as
    fatal as a missing `claude` when that is the engine that would run.
    """
    from .llm_backend import (
        antigravity_config_isolation_row,
        codex_config_isolation_row,
        grok_mcp_isolation_row,
        resolve_backend,
    )

    global _CACHE
    be = resolve_backend(backend)
    cache = _CACHE if isinstance(_CACHE, dict) else None
    if cache is not None and be.name in cache and not refresh:
        return cache[be.name]

    if be.name == "openrouter":
        # Our own loop runs in this interpreter; what can be missing is the key.
        has_key = bool((os.environ.get("OPENROUTER_API_KEY") or "").strip())
        backend_row: CheckRow = (
            "OpenRouter API key", has_key,
            "OPENROUTER_API_KEY set" if has_key else
            "OPENROUTER_API_KEY is not set; the agent pipeline cannot run with "
            "--backend openrouter")
    else:
        binary = shutil.which(be.binary)
        backend_row = (
            f"{be.binary} CLI", binary is not None,
            binary or f"not on PATH; the agent pipeline cannot run with --backend {be.name}")
    rows: list[CheckRow] = [
        backend_row,
        _module_check(
            "statcheck importable", "statcheck", "in THIS interpreter",
            "MISSING here -- statcheck returns success:false and the corpus will "
            "read as containing no NHST statistics",
        ),
        _module_check(
            "claude_agent_sdk", "claude_agent_sdk", "present", "absent",
        ),
        _module_check(
            "python-docx (.docx supplements)", "docx", "present",
            "MISSING -- every .docx supplement reads as empty, and the report "
            "cannot tell that apart from a paper that supplied none",
        ),
        _module_check(
            "openpyxl (.xlsx supplements)", "openpyxl", "present",
            "MISSING -- every .xlsx/.xlsm supplement reads as empty, and the "
            "report cannot tell that apart from a paper that supplied none",
        ),
    ]
    if be.name == "grok":
        rows.append(grok_mcp_isolation_row())
    if be.name == "codex":
        rows.append(codex_config_isolation_row())
    if be.name == "antigravity":
        rows.append(antigravity_config_isolation_row())

    try:
        from .registry import TOOL_AGENT, SPECS, stage_tools
        rows.append(("registry", True,
                     f"{len(SPECS)} tools, tools agent {len(stage_tools(TOOL_AGENT))}"))
    except Exception as exc:  # noqa: BLE001 -- any import-time fault is fatal
        rows.append(("registry", False, str(exc)[:60]))

    if _CACHE is None or not isinstance(_CACHE, dict):
        _CACHE = {}
    _CACHE[be.name] = rows
    return rows


#: R packages the cross-check tools actually import, and the tool each backs.
_R_PACKAGES = {"scrutiny": "r_grim_ground_truth",
               "rsprite2": "r_sprite_ground_truth"}


def _r_crosscheck_status() -> tuple[bool, str]:
    """Is the R cross-check usable -- meaning the PACKAGES, not just Rscript?

    THIS USED TO CHECK `shutil.which("Rscript")` AND NOTHING ELSE, and printed
    the bare detail "present". MEASURED consequence: on a machine with R but
    without `scrutiny`, preflight reported `R (cross-checks) | OK | present`
    while every `r_grim_ground_truth` call returned an empty error. The
    prompts instruct the model to cross-check every GRIM `impossible` before
    reporting it, so the gate said the confirming engine was healthy, the
    engine silently returned nothing, and real `impossible` findings were
    downgraded to `suspicious` across a whole corpus. A check that reports a
    capability the machine does not have is worse than no check.

    Stays NON-fatal: an absent cross-check degrades a run, it does not make
    the output wrong -- now that the wrappers say so out loud.
    """
    if shutil.which("Rscript") is None:
        return False, ("absent; GRIM/SPRITE cross-checks cannot run, so those "
                       "findings rest on the Python engine alone")

    missing = []
    for pkg in _R_PACKAGES:
        try:
            probe = subprocess.run(
                ["Rscript", "-e",
                 f'cat(requireNamespace("{pkg}", quietly=TRUE))'],
                capture_output=True, text=True, timeout=30,
            )
            if "TRUE" not in probe.stdout:
                missing.append(pkg)
        except Exception:  # noqa: BLE001 -- an unprobeable package is a missing one
            missing.append(pkg)

    if not missing:
        return True, f"present; {', '.join(_R_PACKAGES)} installed"

    tools = ", ".join(_R_PACKAGES[p] for p in missing)
    return False, (
        f"Rscript present but R package(s) missing: {', '.join(missing)} -- "
        f"{tools} return 'unavailable' and CANNOT confirm a finding. "
        f"Install: R -e \"install.packages(c({', '.join(chr(39) + p + chr(39) for p in missing)}))\""
    )


def backend_reachable_row(backend=None) -> CheckRow:
    """Can the backend's ACCOUNT actually serve a request?

    `fatal_checks` asks only whether the binary is on PATH. Present is not the
    same as able: on 2026-08-23 preflight said READY for grok while the xAI
    balance was exhausted, and the batch then produced twenty identical 402s
    across ten papers. Same shape as the R invariant in CLAUDE.md, where
    `shutil.which("Rscript")` printed "present" while the package was missing
    and every GRIM cross-check silently returned nothing.

    OPTIONAL, not fatal, and it makes NO call here. The fatal checks are local
    and free by design; a billable network round trip on every `_run_stage`
    would change what preflight is. `batch` does the one live probe, at the
    point where money is about to be spent.
    """
    from .llm_backend import resolve_backend

    be = resolve_backend(backend)
    return (f"{be.binary} account reachable", True,
            "not probed here -- `metascience batch` makes one live check "
            "before it spends; an exhausted balance or a bad key stops the "
            "batch there in one line")


def optional_checks() -> list[CheckRow]:
    """Checks that are reported but never block a run.

    Each of these degrades the output in a way the report can state plainly, so
    blocking on them would refuse work that is still valid.
    """
    r_ok, r_detail = _r_crosscheck_status()
    renderer = shutil.which("wkhtmltopdf") or shutil.which("pandoc")

    # OCR. Probed rather than imported, because `engine_status()` reports WHICH
    # engine is present and what the smallest install would be, and an operator
    # who cannot see that will not know one pip install changes it.
    try:
        from .extraction.ocr import engine_status
        ocr = engine_status()
    except Exception as exc:                              # pragma: no cover
        ocr = {"available": False, "engine": None,
               "smallest_install": f"probe failed: {exc}"}

    # Image-duplication track. Probed through the panels seam so this row and
    # the track's own refusals cannot drift; the absence wording matters
    # because "no engine" must never be read as "no duplicated panels".
    from .image_plugin import available as image_available, load as image_load
    try:
        pst = image_load("image_forensics.panels").panel_engine_status()
    except Exception as exc:                              # pragma: no cover
        pst = {"available": False, "transformed_tier_available": False,
               "engines": [], "probe_error": str(exc)}
    if not image_available():
        panel_detail = ("image analysis package not installed; the image panel "
                        "check cannot run -- a paper with duplicated panels is "
                        "reported UNCHECKED, not clean")
    elif pst["available"] and pst["transformed_tier_available"]:
        panel_detail = ("PyMuPDF + OpenCV present; exact, near-duplicate and "
                        "transformed match tiers all available")
    elif pst["available"]:
        panel_detail = ("PyMuPDF only: exact/near-duplicate tiers available; "
                        "the transformed-match tier (rotated/flipped panels) "
                        "is not -- pip install opencv-python-headless")
    else:
        panel_detail = ("absent; the image panel check cannot run -- a paper "
                        "with duplicated panels is reported UNCHECKED, "
                        "not clean")

    compute_rows = []
    if not image_available():
        # The accelerator broker ships with the image package; docling then
        # runs in-process on the CPU (`extraction.document_compute`).
        compute_rows.append(('Compute: document', True,
                             'cpu (in-process); no accelerator broker: the image '
                             'analysis package is not installed'))
    for workload in (('craft', 'panel', 'document') if image_available() else ()):
        resolve = image_load("compute.devices").resolve
        try:
            execution = resolve(workload)
            compute_rows.append((f'Compute: {workload}', True,
                                 f'{execution.device}; {execution.reason}; see compute-status for runtime details'))
        except Exception as exc:
            compute_rows.append((f'Compute: {workload}', False,
                                 f'{exc}; affected work remains incomplete; use compute-status'))

    return [
        _module_check("PyMuPDF (PDF pages)", "fitz", "present",
                      "absent (it is a base dependency: reinstall with "
                      "`pip install -e .`); quotes get no page number, the "
                      "viewer has no page images, scanned PDFs cannot be OCR'd"),
        ("Panel duplication (image forensics)", pst["available"], panel_detail),
        ("R (cross-checks)", r_ok, r_detail),
        ("PDF renderer", renderer is not None,
         "present" if renderer else "absent; report.pdf will be skipped"),
        # THESE TWO CAME BACK FROM THE INLINE VERSION IN `cli.py` (merge of
        # 73c1b13, 2026-08-11). Moving the checks into this module was the right
        # call -- one definition, so the command and the gate cannot drift -- but
        # the move predated these two rows and would silently have dropped them.
        # Both are NON-fatal and both must stay VISIBLE, for the same reason:
        # each marks a whole class of input that goes unread on this machine
        # while the run still reports success.
        _module_check(
            "fetchpdf (HTML landing-page check)", "fetchpdf.retrieval.validate",
            "present; full validation",
            "absent; HTML falls back to the built-in decoy check, which catches "
            "blatant stubs only -- prefer PDF or JATS XML for HTML-only papers"),
        # Integrity metadata must be READ BACK, not only written: a real corpus
        # held 30 git-lfs pointer stubs where its supplements should have been,
        # every oid matching the manifest, and nothing noticed. When the package
        # is importable, `metascience batch` audits the corpus in its plan; when
        # it is not, the absence is NAMED and the standalone command given --
        # never silence.
        _module_check(
            "fetchpdf-verify (supplement integrity)", "fetchpdf.retrieval.verify",
            "present; `metascience batch` audits supplements against their "
            "manifests in the batch plan",
            "absent; supplement integrity manifests cannot be read back here -- "
            "a git-lfs stub or truncated file reads as the paper's data. Run "
            "the standalone auditor from the fetchpdf repo: "
            "fetchpdf-verify <corpus-root>"),
        ("OCR engine (image supplements)", ocr["available"],
         f"{ocr['engine']}; scanned tables can be transcribed" if ocr["available"]
         else ("absent -- an image supplement, or a PDF whose pages are pictures, "
               "is reported UNREAD rather than empty. " + ocr["smallest_install"])),
        database_row(),
    ] + compute_rows


def database_row() -> CheckRow:
    """The findings database: set up (`ready`) or deliberately off (`off`)
    both pass. Never fatal -- a run without a database is still correct -- but
    every other state means finished runs are not reaching it."""
    from . import db_setup
    st = db_setup.status()
    return ("Findings database", st["state"] in ("ready", "off"), st["detail"])


#: One paper's conversion, as numbers. `(paper, channel, chars, tables,
#: captions, footnotes, degenerate_rows, duplicated_rows)`.
ConversionRow = tuple


def conversion_rows(corpus: str | Path) -> list[ConversionRow]:
    """What the model will actually be handed, per paper, BEFORE the spend.

    GREG FITZGERALD, 2026-08-27, naming this the project's top priority:

        "I am quite sure that if I was to inspect much of the input of past
         runs, it would be obvious to me that the run was not going to be
         successful owing to the poor quality/organization of the converted
         files."

    He is right that it would be obvious, and the reason it was not visible is
    that nothing counted it. This does, at the one moment when knowing is still
    free: `metascience preflight <corpus>` costs nothing and runs before any
    paid stage.

    NUMBERS ONLY, NO VERDICT, and that is deliberate. `corpus_state.render_diff`
    already establishes the rule for this project and the reasoning transfers
    exactly: a count rising can mean the converter got worse OR that it stopped
    dissolving tables into prose, and a row that rendered a judgement would be
    tuned toward green instead of read. The operator judges; this reports.

    WHAT EACH COLUMN IS FOR.
      channel   -- which reader won. `body_md_degraded` means an ingested
                   markdown was demoted; XML beating a PDF extractor is the
                   good case.
      chars     -- the size of what the model reads. A 3,000-character body for
                   a full paper is a failed conversion wearing a success.
      tables    -- how many the walker found. ZERO IS AMBIGUOUS BY CONSTRUCTION
                   and `prepass` says so in prose it cannot act on: "either the
                   article genuinely prints none or the extractor could not see
                   them." Four PNAS caches in this corpus report zero over five
                   pages with no error.
      captions / footnotes -- how many tables carry theirs. Only the XML path
                   fills these, so a PDF-extracted corpus reads zero here
                   honestly rather than as a gap. A table's footnote is where a
                   stated N lives ("Note: N = 107"), which is the denominator
                   every count check otherwise has to infer.
      degenerate / duplicated -- `jats.ingested_markdown_degeneracy` on the body
                   text: pipe rows that carry no data, and repeated rows. These
                   are the shape a dissolved table leaves behind.

    Never raises: a paper that cannot be read reports what failed and the sweep
    continues, because the operator wants all twelve rows, not the first error.
    """
    from .extraction import markdown_out

    out: list[ConversionRow] = []
    base = Path(corpus)
    papers = sorted(d for d in base.iterdir() if d.is_dir()) if base.is_dir() else []
    for d in papers:
        try:
            src = json.loads((d / markdown_out.MARKDOWN_DIRNAME / markdown_out.SOURCE_NAME)
                             .read_text(encoding="utf-8"))
            channel = str(src.get("source_channel") or "?")
            chars = int(src.get("n_chars") or 0)
        except FileNotFoundError:
            # NOT AN ERROR ROW. `markdown/` is written at run start, so its
            # absence means "never run", which is exactly what an operator
            # about to spend money needs to see stated rather than inferred.
            channel, chars = "never run", 0
        except Exception as exc:                              # noqa: BLE001
            # AND ANYTHING ELSE IS SAID OUT LOUD. A bare `except` here read a
            # constant that does not exist (`DIR_NAME` for `MARKDOWN_DIRNAME`),
            # caught its own AttributeError, and reported "never run" for every
            # paper in the corpus -- a broken reader wearing a finding. The
            # whole point of this row is to make a silent failure visible, so
            # it must not have one of its own.
            channel, chars = f"unreadable: {type(exc).__name__}", 0

        n_tab = n_cap = n_foot = 0
        try:
            from . import prepass
            for t in prepass.paper_tables(d, include_supplements=True):
                n_tab += 1
                if t.get("caption"):
                    n_cap += 1
                if t.get("footnotes"):
                    n_foot += 1
        except Exception as exc:                              # noqa: BLE001
            out.append((d.name, f"table walk failed: {type(exc).__name__}",
                        chars, None, None, None, None, None))
            continue

        degen = dup = None
        try:
            from .extraction import jats
            body = (d / markdown_out.MARKDOWN_DIRNAME / markdown_out.BODY_NAME)
            if body.is_file():
                g = jats.ingested_markdown_degeneracy(body.read_text(encoding="utf-8"))
                degen = g.get("n_degenerate_pipe_rows")
                dup = g.get("n_duplicated_rows")
        except Exception as exc:                              # noqa: BLE001
            # SAID, NOT SWALLOWED. `None` in these two columns already means
            # "no body text to score", so a failure that also produced `None`
            # would be indistinguishable from the ordinary case -- absence
            # rendered as knowledge, in the one row whose entire job is to make
            # a silent failure visible. `lint-inert` flagged the bare version.
            degen = dup = f"err:{type(exc).__name__}"

        out.append((d.name, channel, chars, n_tab, n_cap, n_foot, degen, dup))
    return out


def assert_ready(backend=None) -> None:
    """Raise :class:`PreflightError` if any fatal dependency is missing.

    Called before the spend, never after. Bypassed entirely by
    ``METASCIENCE_SKIP_PREFLIGHT=1``.
    """
    if os.environ.get("METASCIENCE_SKIP_PREFLIGHT") == "1":
        return

    failures = [(name, detail) for name, ok, detail in fatal_checks(backend=backend) if not ok]
    if not failures:
        return

    lines = "\n".join(f"  - {name}: {detail}" for name, detail in failures)
    raise PreflightError(
        "Preflight failed -- refusing to start a paid run that would produce "
        f"incomplete results without saying so:\n{lines}\n\n"
        "Fix with `pip install -e .` (and check you are using the interpreter "
        "that runs the pipeline: `metascience python`), or run `metascience preflight` "
        "for the full report. Set METASCIENCE_SKIP_PREFLIGHT=1 to override."
    )
