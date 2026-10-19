"""The MCP server's stdout carries JSON-RPC and nothing else.

MEASURED 2026-10-18 (apple_cider, --backend antigravity): the statcheck
package prints "Extracting statistics from text" to stdout on every call.
Claude's MCP client skips such a line; agy's treats it as a protocol error
(`invalid character 'E' looking for beginning of value`), marks the server
failed, and refuses every later forensic call in the stage -- csf_test, the
baseline-uniformity check, among them.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_a_printing_tool_does_not_reach_the_protocol_stream():
    calls = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "t", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "statcheck",
            "arguments": {"text": "t(28) = 2.20, p = .04."}}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}},
    ]
    env = {**os.environ, "METASCIENCE_MCP_STAGE": "tool_agent",
           "PYTHONPATH": os.pathsep.join(
               [str(ROOT / "src"), str(ROOT / "copy_paste_detector" / "src"),
                os.environ.get("PYTHONPATH", "")])}
    proc = subprocess.run(
        [sys.executable, "-m", "metascience_agent.mcp_server"],
        input="".join(json.dumps(c) + "\n" for c in calls),
        capture_output=True, text=True, timeout=180, env=env)
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    for ln in lines:
        json.loads(ln)                       # every stdout line is JSON-RPC
    ids = [json.loads(ln).get("id") for ln in lines]
    assert ids == [1, 2, 3]
    # The chatter still exists; it is on stderr, where a client ignores it.
    assert "Extracting statistics" in proc.stderr
