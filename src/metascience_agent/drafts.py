"""On-demand PubPeer-comment and letter-to-editor drafts from stored findings.

Contract: docs/specs/webapp_db.md section 11. The ANALYSIS agents never
draft these; a human clicks a button, the draft is generated from the
already-adjudicated findings, edited by the human, and pasted by the human.
This module NEVER posts anywhere -- it imports nothing network-facing, and
the transport is one `claude -p` subprocess with an injectable runner,
failing to a structured refusal rather than an exception.

Register rules baked into the prompts: courteous and numbers-first, verbatim
quotes, reproduction commands included, inconsistency never intent, severity
language capped by the errorlevels rung, invites author response.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DRAFTS_DIRNAME = "drafts"
_TIMEOUT_S = 240
_MODEL = "sonnet"

_PUBPEER_SYSTEM = """You draft PubPeer comments for a forensic-metascience
reviewer. Write in the PubPeer register: courteous, numbers-first, specific.
Rules, non-negotiable:
- Describe inconsistencies, never intent: "the reported percentages are not
  attainable for the stated n" -- words like fabricated/fraud/manipulated
  are banned.
- Quote the paper verbatim (short spans) for every number you discuss, and
  include each finding's reproduction command so readers can check.
- Keep the strength of language within each finding's stated severity level;
  findings marked provisional are presented as provisional.
- Close by inviting the authors to clarify.
- Output ONLY the comment markdown -- no preamble, no meta-commentary."""

_LETTER_SYSTEM = """You draft a letter to a journal editor for a
forensic-metascience reviewer, following COPE-style practice: factual,
courteous, specific, requesting editorial assessment rather than asserting
misconduct. The same non-negotiables as a PubPeer comment apply: verbatim
quotes, reproduction commands, inconsistency never intent, severity language
capped by each finding's level, provisional findings presented as
provisional. Address the editor, reference the article by title and DOI,
and close with an offer to provide the full structured findings. Output
ONLY the letter markdown."""


def _refuse(reason: str) -> dict:
    return {"ok": False, "error": reason}


def _is_partial(doc: dict) -> bool:
    pipeline = doc.get("pipeline")
    return isinstance(pipeline, dict) and pipeline.get("complete_review") is False


def _findings_payload(paper_dir: Path, finding_ids: list[str] | None) -> dict | None:
    docs = sorted(paper_dir.glob("forensic_review*/findings.v2.json")) \
        + list(paper_dir.glob("findings.v2.json"))
    if not docs:
        return None
    loaded = []
    for p in docs:
        # One unreadable historical document must not block drafting from a
        # valid review beside it.
        try:
            d = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(d, dict):
            loaded.append(d)
    if not loaded:
        return None
    # A COMPLETE REVIEW BY DEFAULT. A partial pipeline (one tool, no
    # adjudicator) is drafted from only when the caller names its findings,
    # and then its scope travels in the payload so the draft can say it.
    complete = [d for d in loaded if not _is_partial(d)]
    if complete:
        doc = complete[-1]
    elif finding_ids:
        doc = loaded[-1]
    else:
        return {"paper_id": None, "findings": [], "partial_only": True}
    if finding_ids and not any(
            f.get("finding_id") in finding_ids or f.get("slug") in finding_ids
            for f in doc.get("findings") or [] if isinstance(f, dict)):
        # Named findings may live in a partial experiment.
        doc = next((d for d in reversed(loaded) if any(
            f.get("finding_id") in finding_ids or f.get("slug") in finding_ids
            for f in d.get("findings") or [] if isinstance(f, dict))), doc)
    rows = [f for f in doc.get("findings") or [] if isinstance(f, dict)]
    if finding_ids:
        wanted = {i.strip() for i in finding_ids if i.strip()}
        rows = [f for f in rows
                if f.get("finding_id") in wanted or f.get("slug") in wanted]
    else:
        rows = [f for f in rows
                if f.get("outcome") == "problem"
                and (f.get("adjudication") or {}).get("action") != "discarded"]
    keep = ("finding_id", "slug", "title", "description", "location",
            "severity", "severity_is_provisional", "impossible", "quote",
            "reproduction", "technique", "producer")
    return {"paper_id": doc.get("paper_id"),
            "paper_metadata": doc.get("paper_metadata") or {},
            "adjudication_summary": (doc.get("adjudication") or {}).get("summary"),
            **({"pipeline_scope": (
                f"PARTIAL PIPELINE {doc['pipeline'].get('name')!r}: not a "
                "complete review; modules run: "
                + ", ".join(str(m.get("use")) for m in doc["pipeline"].get(
                    "modules") or [] if isinstance(m, dict))
                + ". Say so in the draft.")} if _is_partial(doc) else {}),
            "findings": [{k: f.get(k) for k in keep if f.get(k) is not None}
                         for f in rows]}


def _run_claude(system: str, prompt: str, model: str,
                run_cli=None) -> tuple[str | None, str | None]:
    argv = ["claude", "-p", "--model", model,
            "--tools", "",
            "--append-system-prompt", system,
            "--permission-mode", "bypassPermissions",
            "--output-format", "json"]
    runner = run_cli or (lambda a, text: subprocess.run(
        a, input=text, capture_output=True, text=True, timeout=_TIMEOUT_S))
    try:
        proc = runner(argv, prompt)
    except FileNotFoundError:
        return None, "the claude CLI is not on PATH"
    except subprocess.TimeoutExpired:
        return None, f"draft generation timed out ({_TIMEOUT_S}s)"
    if proc.returncode != 0:
        return None, f"claude exited {proc.returncode}: {proc.stderr[:300]}"
    try:
        body = json.loads(proc.stdout)
        text = body.get("result") if isinstance(body, dict) else None
    except Exception:  # noqa: BLE001
        text = proc.stdout
    if not (text or "").strip():
        return None, "the model returned an empty draft"
    return str(text), None


def generate(paper_dir: str | Path, kind: str = "pubpeer",
             finding_ids: list[str] | None = None, model: str = _MODEL,
             run_cli=None) -> dict:
    """Generate one draft and persist it. Returns {ok, path, body} or a
    structured refusal -- never raises, never posts."""
    paper_dir = Path(paper_dir)
    if kind not in ("pubpeer", "letter"):
        return _refuse(f"unknown draft kind {kind!r}")
    payload = _findings_payload(paper_dir, finding_ids)
    if payload is None:
        return _refuse("no findings.v2.json under this paper -- run the "
                       "pipeline or migrate-v2 first")
    if payload.get("partial_only"):
        return _refuse("this paper has only partial-pipeline runs; name the "
                       "findings to draft from (finding_ids) to use one")
    if not payload["findings"]:
        return _refuse("no matching findings to draft from")
    system = _PUBPEER_SYSTEM if kind == "pubpeer" else _LETTER_SYSTEM
    prompt = ("Draft from these structured findings (JSON):\n\n"
              + json.dumps(payload, indent=2, default=str))
    text, err = _run_claude(system, prompt, model, run_cli=run_cli)
    if err:
        return _refuse(err)
    drafts = paper_dir / DRAFTS_DIRNAME
    drafts.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = drafts / f"{kind}-{stamp}.md"
    front = {"kind": kind, "model": model,
             "finding_ids": [f["finding_id"] for f in payload["findings"]],
             "generated_at": stamp, "edited": False}
    path.write_text("---\n" + json.dumps(front, indent=2) + "\n---\n\n"
                    + text.strip() + "\n", encoding="utf-8")
    return {"ok": True, "path": str(path), "body": text.strip(),
            "n_findings": len(payload["findings"])}


def list_drafts(paper_dir: str | Path) -> list[dict]:
    out = []
    for p in sorted(Path(paper_dir).glob(f"{DRAFTS_DIRNAME}/*.md")):
        m = re.match(r"(pubpeer|letter)-(\d{8}-\d{6})\.md", p.name)
        out.append({"name": p.name,
                    "kind": m.group(1) if m else "unknown",
                    "generated_at": m.group(2) if m else None,
                    "path": str(p)})
    return out
