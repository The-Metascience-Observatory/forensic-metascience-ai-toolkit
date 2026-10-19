"""Image analysis: a host-side adapter over the independent image package.

With `ai_screening` on (the default) this makes the package's combined call
(`pipeline.run`: detect, then AI-screen). With it off it runs the detector
alone (`pipeline.run_detection`) and files its candidates UNSCREENED:
quarantined rows marked `ai_screening.status: not_run`, which code keeps
out of the headline (`adjudicate.apply`) and which cannot be published
(publication reads the screening ledger, where an unscreened item has no
record). See MODULE.md.
"""

from __future__ import annotations

import time
from pathlib import Path

from ..base import Module, ModuleResult

def disabled_record() -> dict:
    """The record of an image branch that is not configured
    (`image_forensics.pipeline.disabled_record`, held here so a run without
    the image package can say the same thing)."""
    return {
        "ran": False, "is_error": False, "execution_status": "disabled",
        "error_subtype": "disabled", "detail": "image pipeline disabled",
        "findings": [], "findings_rows": [], "output": None,
        "coverage": {}, "limitations": [], "n_findings_injected": 0,
        "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0,
        "wall_seconds": 0.0,
    }


def unavailable_record() -> dict:
    """The record of an image branch that was configured but could not run
    because the image analysis package is not installed. NOT a clean result:
    `ran` is false (the channel reads `refused`) and the limitation says the
    figures were not examined."""
    return {
        **disabled_record(), "execution_status": "unavailable",
        "error_subtype": "image_plugin_unavailable",
        "detail": "image analysis package not installed; figures were not examined",
        "limitations": ["Image analysis did not run: the image analysis package is "
                        "not installed, so the figures were NOT examined for "
                        "duplication or manipulation. This is not a clean result."],
    }


#: The marker an unscreened candidate carries in `inputs.ai_screening`.
NOT_SCREENED = {"status": "not_run",
                "reason": "AI image screening is off in this pipeline"}


def unscreened_rows(result: dict, paper_dir: Path) -> list[dict]:
    """The detector's groups as findings-v2 rows, unscreened. Built by the
    package's own row builder (as `screening_reconcile` builds the screened
    ones), so the two cannot describe a group differently."""
    from ...image_plugin import load
    _track = load("image_forensics.image_track")
    _find_pdfs, _findings_rows_v2 = _track._find_pdfs, _track._findings_rows_v2
    pdf = _find_pdfs(paper_dir)[0] or paper_dir / "__no_pdf__.pdf"
    rows = _findings_rows_v2(result, pdf, paper_dir)
    for row in rows:
        row["quarantined"] = True
        row.setdefault("inputs", {})["ai_screening"] = dict(NOT_SCREENED)
    return rows


async def detect_without_review(image_pipeline, paper_dir: Path, *, on_progress,
                                segment_montages: bool, reassemble_tiles: bool) -> dict:
    """`pipeline.run`'s record shape, from detection alone."""
    started = time.monotonic()
    record = image_pipeline.disabled_record()
    record.update(execution_status="failed", error_subtype="image_pipeline_failed",
                  detail="")
    try:
        record.update(await image_pipeline.run_detection(
            paper_dir, on_progress=on_progress, segment_montages=segment_montages,
            reassemble_tiles=reassemble_tiles))
        status = (record.get("output") or {}).get("status") or {}
        record["coverage"] = {"detection": status,
                              "screening": {"not_run": NOT_SCREENED["reason"]}}
        if not record.get("ran"):
            record["limitations"].append(
                "Image analysis failed or could not run: "
                + str(record.get("detail") or record.get("error_subtype")))
            return record
        result = (record.get("output") or {}).get("result")
        if not isinstance(result, dict):
            raise ValueError("image detector returned no result object")
        record["findings"] = unscreened_rows(result, paper_dir)
        record["n_findings_injected"] = len(record["findings"])
        gaps = image_pipeline.coverage_limitations(status)
        record["limitations"].extend(gaps)
        if record["findings"]:
            record["limitations"].append(
                f"AI image screening is off in this pipeline: "
                f"{len(record['findings'])} image candidate(s) are UNSCREENED -- "
                "quarantined, never the headline, and never published.")
        record["execution_status"] = "incomplete" if gaps else "completed"
        return record
    except Exception as exc:  # noqa: BLE001 -- preserve the other analysis branches
        record.update(is_error=True, error_subtype="image_pipeline_failed")
        record["limitations"].append(
            f"Image analysis {record['execution_status']}; image candidates unpublished: "
            f"{type(exc).__name__}: {exc}")
        return record
    finally:
        record["wall_seconds"] = round(time.monotonic() - started, 2)
        detail = [f"Image detection {record['execution_status']} (no AI review)",
                  record.get("detail", ""),
                  f"{record.get('n_findings_injected', 0)} unscreened candidate(s)"]
        record["detail"] = "; ".join(x for x in detail + record["limitations"] if x)


class ImageAnalysis(Module):
    async def run(self, ctx, needed) -> ModuleResult:
        from ...image_plugin import available, load
        if not available():
            return ModuleResult(self.name, record=unavailable_record())
        image_pipeline = load("image_forensics.pipeline")
        options = dict(
            segment_montages=bool(ctx.config.option(self.name, "segment_montages", False)),
            reassemble_tiles=bool(ctx.config.option(self.name, "reassemble_tiles", False)))
        if ctx.config.option(self.name, "ai_screening", True):
            record = await image_pipeline.run(
                ctx.paper_dir, on_progress=ctx.on_progress, **options)
        else:
            record = await detect_without_review(
                image_pipeline, Path(ctx.paper_dir), on_progress=ctx.on_progress,
                **options)
        return ModuleResult(self.name, record=record)


MODULE = ImageAnalysis()
