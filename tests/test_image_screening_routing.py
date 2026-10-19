"""Exercise the public route without making model calls."""
import asyncio
import json

from typer.testing import CliRunner

from metascience_observatory_image_analysis.image_forensics import screening, screening_eval
from metascience_observatory_image_analysis.image_forensics.screening_config import DEFAULT_SCREEN, DEFAULT_CONFIRM
from tests.test_image_review import _paper, _group


def test_cli_defaults_use_luna_then_grok(tmp_path, monkeypatch):
    from forensic_metascience_ai_toolkit.cli import app
    called = []
    async def run(root, screen, confirm, *args, **kwargs):
        called.append((screen, confirm))
    monkeypatch.setattr(screening, "run", run)
    result = CliRunner().invoke(app, ["image-screen", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert called == [(('codex', 'gpt-5.6-luna'), ('grok', 'grok-4.6'))]


def test_per_paper_escalates_to_grok(tmp_path, monkeypatch):
    monkeypatch.delenv("METASCIENCE_IMAGE_SCREEN", raising=False)
    monkeypatch.delenv("METASCIENCE_IMAGE_CONFIRM", raising=False)
    (tmp_path / ".image_track").mkdir()
    paper = _paper(tmp_path, "paper", [_group()])
    calls = []
    async def judge(packet, backend, model, **kwargs):
        calls.append((backend, model))
        if len(calls) == 1:
            return {"decision": "unresolved", "confidence": "low", "validated": False}
        return {"decision": "innocuous", "confidence": "high", "validated": True}
    monkeypatch.setattr(screening, "judge", judge)
    result = json.loads((paper / "image_duplication_findings.json").read_text())
    asyncio.run(screening.screen_paper_result(paper, result))
    assert calls == [DEFAULT_SCREEN, DEFAULT_CONFIRM]
    record = next(iter(screening.read_ledger(tmp_path)["items"].values()))
    assert record["routing"] == {"screen": list(DEFAULT_SCREEN), "confirm": list(DEFAULT_CONFIRM)}


def test_deterministic_clear_never_reaches_paid_screening(tmp_path, monkeypatch):
    (tmp_path / ".image_track").mkdir()
    group = _group()
    group["duplication_evidence"] = False
    paper = _paper(tmp_path, "paper", [group])
    calls = []
    async def judge(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("cleared item reached the model")
    monkeypatch.setattr(screening, "judge", judge)
    result = json.loads((paper / "image_duplication_findings.json").read_text())
    coverage = {}
    asyncio.run(screening.screen_paper_result(paper, result, coverage=coverage))
    assert calls == []
    assert coverage == {"n_candidates": 0, "n_unresolved": 0}


def test_deterministic_clear_remains_available_to_audit_without_a_ledger(tmp_path):
    item = {
        "id": "within:paper:IMGDUP-1",
        "cleared": True,
        "source_identity": {"revision": 2, "verified": True},
    }

    assert screening.published_items(tmp_path, [item]) == [item]


def test_mistaken_source_alias_can_be_reconsidered_and_then_cached(tmp_path, monkeypatch):
    (tmp_path / ".image_track").mkdir()
    paper = _paper(tmp_path, "paper", [_group()])
    calls = []
    async def judge(packet, backend, model, **kwargs):
        calls.append((backend, model))
        if backend == DEFAULT_CONFIRM[0]:
            return {"decision": "innocuous", "confidence": "high", "validated": True,
                    "category": "caption_explained"}
        return {"decision": "unresolved", "confidence": "low", "validated": False,
                "category": "source_alias", "validation_errors": [
                    "source-alias clearance requires verified identity of candidates A and B, not each candidate and its own full figure"]}
    monkeypatch.setattr(screening, "judge", judge)
    result = json.loads((paper / "image_duplication_findings.json").read_text())
    asyncio.run(screening.screen_paper_result(paper, result))
    asyncio.run(screening.screen_paper_result(paper, result))
    assert calls == [DEFAULT_SCREEN, DEFAULT_CONFIRM]
    record = next(iter(screening.read_ledger(tmp_path)["items"].values()))
    assert "terminal_evidence_block" not in record
    assert record["decision"] == "innocuous"


def test_evaluation_uses_same_route_and_does_not_reuse_old_escalation(tmp_path, monkeypatch):
    item = {"id": "test", "decision": {"decision": "true_issue"}}
    monkeypatch.setattr(screening_eval, "build_items", lambda *a, **kw: {"items": [item]})
    monkeypatch.setattr(screening_eval, "evidence", lambda *a: {"id": "test"})
    calls = []
    async def judge(packet, backend, model, **kwargs):
        calls.append((backend, model))
        return {"decision": "unresolved" if model == DEFAULT_SCREEN[1] else "issue",
                "confidence": "high", "validated": True}
    monkeypatch.setattr(screening_eval, "judge", judge)
    out = tmp_path / 'eval'; out.mkdir()
    (out / 'references.json').write_text(json.dumps({'test': 'issue'}))
    old = {'id': 'test', 'model': DEFAULT_SCREEN[1], 'repeat': 0,
           'fingerprint': screening.fingerprint({'id': 'test'}),
           'configuration': {'screen': list(DEFAULT_SCREEN), 'confirm': ['claude', 'sonnet']}}
    (out / 'results.jsonl').write_text(json.dumps(old)+'\n')
    asyncio.run(screening_eval.evaluate(tmp_path, out))
    assert calls == [DEFAULT_SCREEN, DEFAULT_CONFIRM]
    summary = json.loads((out / 'summary.json').read_text())
    assert summary['models'][DEFAULT_SCREEN[1]]['calls'] == 1
    assert summary['models'][DEFAULT_SCREEN[1]]['retained_positives'] == 1
    calls.clear()
    asyncio.run(screening_eval.evaluate(tmp_path, out))
    assert calls == []
