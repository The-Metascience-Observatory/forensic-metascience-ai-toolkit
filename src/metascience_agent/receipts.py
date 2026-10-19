"""Tool-call receipts: the TOOL side's own record of every call it answered.

Phase 3b of the modular refactor. The tool ledger (`agent._tool_call_ledger`)
is rebuilt from the MODEL's transcript, in three dialects (Claude stream-json,
Grok's `use_tool` envelope, Codex events). A receipt is written by the forensic
tool layer itself -- the MCP server, or `metascience tool run` -- at the moment
it answers, so a ledger row can be checked against something the transcript
did not produce:

  * a ledger call WITH a matching receipt is a call our tool layer really
    answered, with exactly these arguments and (when the ledger kept the full
    text) exactly this result;
  * a ledger call WITHOUT one was not answered by our layer as recorded --
    a normaliser bug, a foreign server, or a forged transcript row;
  * a receipt no ledger row claims is a call the transcript lost.

The join is reported, never acted on: it does not change `validated` or any
severity (a receipt that cannot be matched is a fact to look at, and the first
real runs decide whether it should ever gate anything).

WHERE THEY GO. The server already knows its run (`METASCIENCE_RUN_SLUG`) and
role (`METASCIENCE_MCP_STAGE`), so it derives the file itself and the MCP
config bytes do not change: `<root>/<run_slug>/<stage>.jsonl`, root
`METASCIENCE_RECEIPTS_DIR` or `~/.cache/metascience/receipts`. A server
started without a run slug (an operator's own) writes nothing. The host moves
each file into the review directory as `receipts.<label>.jsonl` and deletes the
cache copy.
"""

from __future__ import annotations

import fcntl
import hashlib
import itertools
import json
import os
import time
from pathlib import Path
from typing import Any

ROOT_ENV = "METASCIENCE_RECEIPTS_DIR"
DEFAULT_ROOT = Path.home() / ".cache" / "metascience" / "receipts"
_COUNTER = itertools.count(1)


def root() -> Path:
    override = os.environ.get(ROOT_ENV, "").strip()
    return Path(override) if override else DEFAULT_ROOT


def path_for(run_slug: str, stage: str) -> Path:
    safe = lambda s: "".join(c if c.isalnum() or c in "-_." else "_" for c in s)  # noqa: E731
    return root() / safe(run_slug) / f"{safe(stage)}.jsonl"


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _severity(result_text: str) -> str | None:
    try:
        parsed = json.loads(result_text)
    except (TypeError, ValueError):
        return None
    sev = parsed.get("severity") if isinstance(parsed, dict) else None
    return sev if isinstance(sev, str) else None


def record(tool: str, args: dict | None, result_text: str, *,
           via: str = "mcp") -> dict | None:
    """Append one receipt for the current run/role, if there is one.

    Never raises: a receipt that cannot be written must not fail the tool
    call it describes. The failure is visible as a missing receipt.
    """
    # The two names are spelled here, not imported: importing the server
    # module runs its manifest filter, which raises on a bad manifest -- and a
    # receipt must never raise.
    run_slug = os.environ.get("METASCIENCE_RUN_SLUG", "").strip()
    stage = os.environ.get("METASCIENCE_MCP_STAGE", "").strip()
    if not run_slug or not stage:
        return None
    rec = {"id": f"{os.getpid()}-{next(_COUNTER)}", "t": round(time.time(), 3),
           "tool": tool, "via": via, "stage": stage,
           "args_sha": digest(canonical(args or {})),
           "result_sha": digest(result_text or ""),
           "result_chars": len(result_text or ""),
           "severity": _severity(result_text)}
    try:
        path = path_for(run_slug, stage)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            fcntl.flock(fh, fcntl.LOCK_UN)
    except OSError:
        return None
    return rec


def load(run_slug: str, stage: str) -> list[dict]:
    path = path_for(run_slug, stage)
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def join(ledger: list[dict] | None, receipts: list[dict]) -> dict:
    """Mark each forensic ledger call with its receipt, in place; summarise.

    A call matches a receipt on (tool, canonical-argument digest); each
    receipt is used once, in order, so two identical calls need two. Every
    MCP-named call is eligible, whatever its surface (`run_python_script` is
    `agent_code` on the ledger and is still answered by our server).

    THE RESULT IS COMPARED, NOT MATCHED ON. When the ledger kept the full text
    and it differs from what the tool returned, the call still has its receipt
    and is marked `receipt_result_differs`: the transport changed the answer
    between our tool and the model. MEASURED on the first live run
    (apple_cider, Claude Sonnet, 2026-10-13): `extract_pdf` returned 93,210
    characters and the model received a 1,345-character "output too large,
    saved to a file" notice from Claude Code -- the model never saw the
    result, and nothing recorded that before receipts.
    """
    pool: dict[tuple[str, str], list[dict]] = {}
    for rec in receipts:
        pool.setdefault((rec.get("tool", ""), rec.get("args_sha", "")), []).append(rec)
    n_calls = n_matched = 0
    unmatched_calls: list = []
    differs: list = []
    for call in ledger or []:
        if not isinstance(call, dict):
            continue
        if not str(call.get("tool") or "").startswith("mcp__"):
            continue
        n_calls += 1
        key = (str(call.get("tool_short") or ""),
               digest(canonical(call.get("input") or {})))
        candidates = pool.get(key) or []
        result = call.get("result")
        full = isinstance(result, str) and not call.get("result_truncated")
        same = [i for i, r in enumerate(candidates)
                if full and r.get("result_sha") == digest(result)]
        if not candidates:
            call["receipt"] = None
            unmatched_calls.append(call.get("seq"))
            continue
        hit = candidates.pop(same[0] if same else 0)
        call["receipt"] = hit["id"]
        n_matched += 1
        if full and hit.get("result_sha") != digest(result):
            call["receipt_result_differs"] = {
                "tool_chars": hit.get("result_chars"), "model_chars": len(result)}
            differs.append(call.get("seq"))
    leftover = [rec["id"] for recs in pool.values() for rec in recs]
    return {"n_calls": n_calls, "n_receipts": len(receipts),
            "n_calls_with_receipt": n_matched,
            "calls_without_receipt": unmatched_calls,
            "receipts_without_call": leftover,
            "calls_whose_result_differs": differs}


def collect(run_slug: str, stage: str) -> str | None:
    """This run/role's receipts as text, removed from the cache; None when
    the server wrote none."""
    src = path_for(run_slug, stage)
    if not src.is_file():
        return None
    text = src.read_text(encoding="utf-8")
    try:
        src.unlink()
        src.parent.rmdir()
    except OSError:
        pass
    return text
