"""A missing report.pdf carries its reason, on both writers.

`report_render.last_pdf_error()` has held the reason for every failed render
since defect #163 (2026-08-16), and nothing called it: `_render_report_pdf`
swallowed the failure and returned None, so a run without a PDF was a run
without a sentence. Found by the 2026-09-02 audit alongside a second gap --
`analyze --pdf` defaults on and the README lists `report.pdf` among the
outputs, yet only the LEGACY writer rendered one. The parallel writer now
renders it too, best-effort, before run_meta.json is serialised.
"""
from __future__ import annotations

import json

import pytest

from forensic_metascience_ai_toolkit import agent, parallel, report_render


def _minimal_result():
    return {"run_meta": {"paper_id": "p", "version": "9.9.9"},
            "verdict": "unresolved", "confidence": "low"}


class TestTheLegacyWrapper:
    def test_a_raising_renderer_leaves_its_reason_in_run_meta(self, tmp_path, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("cairo exploded")
        monkeypatch.setattr(report_render, "render_markdown_to_pdf", boom)
        monkeypatch.setattr(report_render, "_LAST_PDF_ERROR", None)
        res = _minimal_result()
        assert agent._render_report_pdf(res, "# r", tmp_path) is None
        assert "cairo exploded" in res["run_meta"]["pdf_error"]

    def test_this_renders_exception_beats_a_stale_global(self, tmp_path, monkeypatch):
        """`_LAST_PDF_ERROR` is set by the weasyprint path and never cleared,
        so on a batch it can describe an EARLIER paper's failure. The first
        cut of `_record_pdf_error` preferred it and reported "no cairo" for a
        renderer that had raised "no engine"."""
        monkeypatch.setattr(report_render, "_LAST_PDF_ERROR",
                            "weasyprint unavailable: ImportError: no cairo")
        res = _minimal_result()
        agent._record_pdf_error(res, RuntimeError("no engine"))
        assert "no engine" in res["run_meta"]["pdf_error"]
        assert "no cairo" not in res["run_meta"]["pdf_error"]

    def test_the_renderers_own_reason_wins_when_it_recorded_one(self, tmp_path, monkeypatch):
        def quiet_fail(*a, **k):
            report_render._LAST_PDF_ERROR = "weasyprint unavailable: ImportError: no cairo"
            return None
        monkeypatch.setattr(report_render, "render_markdown_to_pdf", quiet_fail)
        res = _minimal_result()
        assert agent._render_report_pdf(res, "# r", tmp_path) is None
        assert res["run_meta"]["pdf_error"].startswith("weasyprint unavailable")

    def test_a_successful_render_records_no_error(self, tmp_path, monkeypatch):
        out = tmp_path / "report.pdf"

        def ok(*a, **k):
            out.write_bytes(b"%PDF-1.4 fake")
            return out
        monkeypatch.setattr(report_render, "render_markdown_to_pdf", ok)
        res = _minimal_result()
        assert agent._render_report_pdf(res, "# r", tmp_path) == out
        assert "pdf_error" not in res["run_meta"]


class TestTheParallelWriter:
    @pytest.fixture
    def stub_report(self, monkeypatch):
        from forensic_metascience_ai_toolkit import report_v2
        monkeypatch.setattr(report_v2, "render_report_v2", lambda *a, **k: "# report\n")

    def _result(self, tmp_path):
        paper = tmp_path / "paper"
        paper.mkdir(exist_ok=True)
        return {"findings_v2": {"schema_version": "2.0", "findings": []},
                "run_meta": {"paper_id": "p", "version": "9.9.9"},
                "limitations": [], "paper_path": str(paper)}

    def test_it_renders_the_pdf_the_readme_promises(self, tmp_path, stub_report, monkeypatch):
        def ok(result, report_md, out_dir):
            p = out_dir / "report.pdf"
            p.write_bytes(b"%PDF-1.4 fake")
            return p
        monkeypatch.setattr(agent, "_render_report_pdf", ok)
        written = parallel.write_parallel_outputs(self._result(tmp_path), tmp_path / "rv")
        assert (tmp_path / "rv" / "report.pdf").exists()
        assert "report.pdf" in written

    def test_the_reason_reaches_run_meta_json(self, tmp_path, stub_report, monkeypatch):
        def fail(result, report_md, out_dir):
            agent._record_pdf_error(result, RuntimeError("no engine"))
            return None
        monkeypatch.setattr(agent, "_render_report_pdf", fail)
        parallel.write_parallel_outputs(self._result(tmp_path), tmp_path / "rv")
        meta = json.loads((tmp_path / "rv" / "run_meta.json").read_text())
        assert "no engine" in meta["pdf_error"]
        assert not (tmp_path / "rv" / "report.pdf").exists()

    def test_no_pdf_means_no_pdf_and_no_error(self, tmp_path, stub_report, monkeypatch):
        def never(*a, **k):
            raise AssertionError("render_pdf=False must not render")
        monkeypatch.setattr(agent, "_render_report_pdf", never)
        parallel.write_parallel_outputs(self._result(tmp_path), tmp_path / "rv", render_pdf=False)
        meta = json.loads((tmp_path / "rv" / "run_meta.json").read_text())
        assert "pdf_error" not in meta
