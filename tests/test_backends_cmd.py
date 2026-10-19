"""`metascience backends`: availability + live model listings per backend."""

import json

from typer.testing import CliRunner

from metascience_agent import llm_backend
from metascience_agent.cli import app
from metascience_agent.llm_backend import (
    parse_codex_models,
    parse_grok_models,
)


def test_grok_models_listing_is_parsed():
    text = ("You are logged in with grok.com.\n\nDefault model: grok-4.7\n\n"
            "Available models:\n  * grok-4.7 (default)\n  - grok-4.6\n")
    assert parse_grok_models(text) == [("grok-4.7", "default"), ("grok-4.6", "")]


def test_codex_catalog_skips_hidden_and_orders_by_priority():
    text = json.dumps({"models": [
        {"slug": "b", "display_name": "B", "visibility": "list", "priority": 9,
         "supported_reasoning_levels": [{"effort": "low"}, {"effort": "high"}]},
        {"slug": "hidden", "visibility": "hide", "priority": 1},
        {"slug": "a", "display_name": "A", "visibility": "list", "priority": 4},
    ]})
    assert parse_codex_models(text) == [("a", "A"), ("b", "B (effort: low, high)")]


def test_missing_binary_is_unavailable_not_an_empty_list(monkeypatch):
    monkeypatch.setattr(llm_backend.shutil, "which", lambda _b: None)
    result = CliRunner().invoke(app, ["backends", "--backend", "grok", "--json"])
    assert result.exit_code == 0, result.output
    entry = json.loads(result.output)["grok"]
    assert entry["usable"] is False
    assert "models" not in entry  # never asked, so never reported as empty


def test_default_absent_from_live_list_is_flagged(monkeypatch):
    monkeypatch.setattr(llm_backend.shutil, "which", lambda b: f"/bin/{b}")
    monkeypatch.setattr(llm_backend, "backend_binary_version", lambda _be: "x")
    monkeypatch.setattr(llm_backend, "list_backend_models",
                        lambda _n, timeout=60.0: ([("gpt-6-luna", "")], "live"))
    result = CliRunner().invoke(app, ["backends", "--backend", "codex", "--json"])
    assert json.loads(result.output)["codex"]["default_listed"] is False


def test_effort_suffixed_slug_counts_as_the_default(monkeypatch):
    monkeypatch.setattr(llm_backend.shutil, "which", lambda b: f"/bin/{b}")
    monkeypatch.setattr(llm_backend, "backend_binary_version", lambda _be: "x")
    monkeypatch.setattr(
        llm_backend, "list_backend_models",
        lambda _n, timeout=60.0: ([("gemini-4-argon-high", "")], "live"))
    result = CliRunner().invoke(app, ["backends", "--backend", "agy", "--json"])
    assert json.loads(result.output)["antigravity"]["default_listed"] is True
