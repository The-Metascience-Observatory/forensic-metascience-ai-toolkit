"""Capture what the default review SENDS, for an independent parity oracle.

Run against a source tree, this drives `agent.analyze_paper` with faked stages
(no model is called) for each backend and records every CLI invocation the
pipeline builds -- argv, environment overlay, sandbox files, allowlist --
normalised so two trees on one machine compare byte for byte.

`tests/data/parity_05537458.json` was produced by running this module against
origin/main 05537458 (before pipelines existed):

    PYTHONPATH=<old tree>/src:... python tests/parity_capture.py OUT.json

`tests/test_pipeline_parity.py` runs the same capture against the current tree
and requires equality. Deliberately self-contained (no import from other test
modules), so the old tree can run it unchanged.

WHAT IT COVERS: the three LLM invocations of a default review (tool agent,
science analyst, adjudicator) on each backend -- argv, environment overlay,
sandbox files, allowlist -- the user prompt each stage receives, run_meta's
settings and provenance hashes, the history parent's recorded parameters,
channels, `is_error`, and the findings document's top-level keys. WHAT IT
DOES NOT: the image and text tracks (off here; the image track spends on AI
screening), the retry/recovery and repair paths, and written artefacts.

FROZEN INPUTS, identical in the baseline and the current capture: R
availability (it changes two prompts), uuids, and Grok's folder-trust store,
which is never written (METASCIENCE_GROK_SKIP_FOLDER_TRUST).
"""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import json
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path

BACKENDS = ("claude", "codex", "grok")
_LONG = 160


def _h(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _norm(text: str, subs: list[tuple[str, str]]) -> str:
    for old, new in subs:
        if old:
            text = text.replace(old, new)
    text = re.sub(r"\b(r|e|x|run|exec)_[0-9a-f]{12,32}\b", r"\1_<ID>", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?", "<TIME>", text)
    return text


def _value(v, subs):
    if isinstance(v, str):
        v = _norm(v, subs)
        return _h(v) if len(v) > _LONG else v
    if isinstance(v, dict):
        return {str(k): _value(x, subs) for k, x in sorted(v.items())}
    if isinstance(v, (list, tuple)):
        return [_value(x, subs) for x in v]
    return v


def _stage(doc):
    return {"structured_output": doc, "result": None, "text": "",
            "prompt": "P", "messages": [], "cost_usd": 0.1,
            "input_tokens": 1, "output_tokens": 1,
            "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
            "return_code": 0, "is_error": False, "error_subtype": None,
            "wall_seconds": 1.0, "tool_calls": 0, "stop_reason": None,
            "num_turns": 1, "allowed_tools": []}


def _doc(slug, technique):
    return {"schema_version": "1.0", "paper_id": "p",
            "coverage": {"stats_found": 1, "tools_run": ["grim_check"]},
            "anatomy": {"studies": [], "variables": [], "tests": []},
            "findings": [{"slug": slug, "technique": technique,
                          "title": "a plain-language headline here",
                          "description": "a plain-english description of what "
                                         "is wrong, with the numbers inline",
                          "location": "Table 2", "outcome": "problem",
                          "provisional_severity": 4,
                          "quote": "81.3% of participants reported full compliance"}]}


def capture_backend(backend: str, root: Path) -> list[dict]:
    from forensic_metascience_ai_toolkit import agent, paper_metadata

    paper = root / "paper"
    paper.mkdir()
    (paper / "body.md").write_text("The compliance rate was 81.3% of participants "
                                   "reported full compliance.")
    for env, sub in (("METASCIENCE_GROK_SANDBOX_ROOT", "grok"),
                     ("METASCIENCE_CODEX_SANDBOX_ROOT", "codex")):
        (root / sub).mkdir()
        os.environ[env] = str(root / sub)
    counter = itertools.count()
    uuid.uuid4 = lambda: uuid.UUID(int=next(counter))  # deterministic ids
    src_root = str(Path(agent.__file__).resolve().parents[1])
    subs = [(str(paper), "<PAPER>"), (str(root), "<TMP>"),
            (src_root, "<SRC>"), (str(Path(src_root).parent), "<REPO>"),
            (sys.executable, "<PYTHON>")]
    # Since 1.85.1 a child's PYTHONPATH is this tree's two roots, then the
    # CALLER's own entries (`llm_backend.forensic_pythonpath`). Those extras
    # are the machine's, not the tree's (an image checkout, say), so they are
    # dropped before anything else is normalised. A no-op on older trees,
    # which never sent them.
    ours = {Path(src_root).resolve(),
            (Path(src_root).parent / "copy_paste_detector" / "src").resolve()}
    extras: list[str] = []
    for entry in os.environ.get("PYTHONPATH", "").split(os.pathsep):
        if entry and Path(entry).resolve() not in ours and entry not in extras:
            extras.append(entry)
    if extras:
        subs.insert(0, (os.pathsep + os.pathsep.join(extras), ""))

    seen: list[dict] = []
    prompts_seen: dict[str, str] = {}
    real_build = agent._build_claude_cmd

    def spy(*a, **k):
        inv = real_build(*a, **k)
        files = {}
        if getattr(inv, "workdir", None) and Path(inv.workdir).is_dir():
            for f in sorted(Path(inv.workdir).rglob("*")):
                if f.is_file():
                    files[_norm(str(f.relative_to(inv.workdir)), subs)] = _value(
                        f.read_text(errors="replace"), subs)
        seen.append({"stage": k.get("mcp_stage"),
                     "argv": _value(list(inv.argv), subs),
                     "env_overlay": _value(dict(inv.env_overlay or {}), subs),
                     "allowed_tools": list(inv.allowed_tools or ()),
                     "prompt_delivery": inv.prompt_delivery,
                     "files": files})
        return inv

    async def fake_requiring(*, build_cmd, prompt, stage_label, **kw):
        prompts_seen[stage_label] = _h(_norm(prompt, subs))
        build_cmd()
        res = _stage(_doc("t1", "grim_check"))
        # One on-list forensic call: a tools agent with an empty ledger is
        # refused as a plumbing failure (`AnalystModule.run`), and every real
        # run reads the paper first.
        res["messages"] = [
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "read1",
                 "name": agent._mcp("extract_pdf"), "input": {}}]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "read1",
                 "content": [{"type": "text", "text": "{}"}]}]}}]
        agent.record_spend(stage_label, res)
        return res

    async def fake_run_stage(cmd, prompt, *a, **kw):
        label = kw.get("stage_label")
        prompts_seen[label] = _h(_norm(prompt, subs))
        if label == "science_agent":
            return _stage(_doc("s1", "factual_claim"))
        if label == "adjudicator":
            fids = re.findall(r'"finding_id": "(f_[0-9a-f]{16}(?:-\d+)?)"', prompt)
            return _stage({
                "verdicts": [{"finding_id": f, "action": "kept", "severity": 5,
                              "category": "none", "rationale": "kept after reading"}
                             for f in dict.fromkeys(fids)],
                "paper": {"verdict": "does_not_reconcile", "paper_severity": 5,
                          "confidence": "medium", "summary": "s" * 200,
                          "headline_finding_id": fids[0] if fids else "f_x"}})
        raise AssertionError(label)

    agent._build_claude_cmd = spy
    agent._run_stage_requiring_forensic_tools = fake_requiring
    agent._run_stage = fake_run_stage
    agent.ensure_paper_extracted = lambda *a, **k: None
    paper_metadata.record_for_run = lambda d: None
    try:
        result = asyncio.run(agent.analyze_paper(
            str(paper), mode="parallel", image_forensics=False,
            text_forensics=False, backend=backend))
    finally:
        agent._build_claude_cmd = real_build
    meta = result["run_meta"]
    history = (meta.get("history") or {}).get("provenance") or {}
    return {"invocations": seen,
            "user_prompts": prompts_seen,
            "prompt_sha256": meta.get("prompt_sha256"),
            "registry_sha256": meta.get("registry_sha256"),
            "settings": {k: meta.get(k) for k in (
                "mode", "schema_version", "llm_backend", "model", "effort")},
            "history_parameters": _value(history.get("parameters") or {}, subs),
            "stages": sorted(meta.get("stages") or {}),
            "channels": _value(result["findings_v2"].get("channels"), subs),
            "document_keys": sorted(result["findings_v2"]),
            "is_error": result["is_error"]}


def capture_all() -> dict:
    from forensic_metascience_ai_toolkit import preflight
    preflight._r_crosscheck_status = lambda: (True, "frozen for the parity capture")
    out = {}
    for backend in BACKENDS:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["METASCIENCE_SKIP_PREFLIGHT"] = "1"
            os.environ["METASCIENCE_FREEZE"] = "0"
            os.environ["METASCIENCE_GROK_SKIP_FOLDER_TRUST"] = "1"
            os.environ["METASCIENCE_ANALYSIS_ROOT"] = tmp
            out[backend] = capture_backend(backend, Path(tmp))
    return out


if __name__ == "__main__":
    Path(sys.argv[1]).write_text(json.dumps(capture_all(), indent=1, sort_keys=True))
