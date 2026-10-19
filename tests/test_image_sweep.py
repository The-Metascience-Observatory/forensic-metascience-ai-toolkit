"""`metascience image-sweep`: the free, resumable corpus run of the image
track, and the single writer (`image_forensics.retain`) it goes through.

Every test spawns the REAL child (`python -m ...image_track`), as
`test_image_track.py` does, because the sweep's whole claim is about what a
child run leaves on disk. Each test names the failure it exists to catch.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pytest

fitz = pytest.importorskip("fitz")
cv2 = pytest.importorskip("cv2")

from metascience_agent import corpus_stats as CS  # noqa: E402
from metascience_agent import webapp_index as W  # noqa: E402
from metascience_observatory_image_analysis.image_forensics import retain as R  # noqa: E402
from metascience_observatory_image_analysis.image_forensics import sweep as S  # noqa: E402

SRC = Path(__file__).resolve().parent.parent / "src" / "metascience_agent"


# ---------------------------------------------------------------------------
# A two-paper corpus: one paper shows the same picture as Figure 1 and
# Figure 2 (the canonical firing case), one has no PDF (a refusal).
# ---------------------------------------------------------------------------


IMAGE_SRC = __import__("pathlib").Path(__import__("metascience_observatory_image_analysis").__file__).parent
def _texture(seed: int, w: int = 256, h: int = 192) -> np.ndarray:
    rng = np.random.default_rng(seed)
    g = rng.integers(0, 256, (h, w), dtype=np.uint8)
    return cv2.GaussianBlur(g, (0, 0), 1.2)


def _png(gray: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", gray)
    assert ok
    return buf.tobytes()


def _make_pdf(path: Path, pages, caption_suffix: str = "") -> Path:
    doc = fitz.open()
    for items in pages:
        page = doc.new_page(width=612, height=792)
        for caption, png, x0, y0 in items:
            pix = fitz.Pixmap(png)
            page.insert_text((x0, y0 - 20), caption + caption_suffix, fontsize=10)
            page.insert_image(fitz.Rect(x0, y0, x0 + pix.width, y0 + pix.height),
                              stream=png)
    doc.save(path)
    doc.close()
    return path


def _write_two_fig_pdf(d: Path, suffix: str = "") -> Path:
    png = _png(_texture(1))
    return _make_pdf(d / f"{d.name}.pdf", [
        [("Figure 1. Confocal images of treated cells.", png, 72, 100)],
        [("Figure 2. Confocal images of control cells.", png, 72, 100)],
    ], caption_suffix=suffix)


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / "corpus"
    a = root / "10.1--a"
    a.mkdir(parents=True)
    _write_two_fig_pdf(a)
    (a / "metadata.json").write_text(json.dumps(
        {"doi": "10.1/a", "title": "A", "year": 2020, "journal": "J"}))
    b = root / "10.1--b"
    b.mkdir()
    (b / "metadata.json").write_text("{}")
    return root


def _sweep(root: Path, sweep_id: str = "t1", **kw):
    kw.setdefault("furniture_pass", False)
    return S.run_sweep(root, jobs=2, progress=False, log=lambda s: None,
                       sweep_id=sweep_id, **kw)


def _status(d: Path) -> dict:
    return json.loads((d / "panels" / "image_track_status.json").read_text())


# ---------------------------------------------------------------------------
# It runs, keeps the answer, and says which paper refused
# ---------------------------------------------------------------------------

def test_a_sweep_tells_the_workbench_the_corpus_is_on_this_machine(corpus, monkeypatch):
    """The workbench resolves a paper's folder only through a registered local
    root, and only the full-pipeline path registered one: a corpus swept
    from this machine synced its runs and then told its reviewer "Paper
    files unavailable on this computer; register a local folder" (Dan,
    2026-09-14, Dickendesher thesis). Whatever the database sync did, the
    directory the sweep just read exists here, and it says so."""
    from metascience_observatory_image_analysis import integration
    seen = []
    monkeypatch.setattr(integration, "notify_published",
                        lambda root: seen.append(Path(root)) or {"state": "notified"})
    monkeypatch.setenv("METASCIENCE_NO_DB_PUSH", "1")
    lines = []
    summary = S.run_sweep(corpus, jobs=2, progress=False, log=lines.append,
                          sweep_id="t_root", furniture_pass=False)
    assert seen == [corpus]
    assert summary["local_root_notice"] == {"state": "notified"}
    assert any(line.startswith("local root: notified -- ") for line in lines)
    on_disk = json.loads((corpus / ".image_track" / "sweeps" / "t_root" / "sweep.json").read_text())
    assert on_disk["local_root_notice"] == {"state": "notified"}

    # Standalone (no host hook) is a named state, never a crash.
    monkeypatch.setattr(integration, "notify_published", None)
    summary = S.run_sweep(corpus, jobs=2, progress=False, log=lambda s: None,
                          sweep_id="t_root2", furniture_pass=False, force=True)
    assert summary["local_root_notice"]["state"] == "standalone"

class TestASweepRetainsEveryAnswer:
    def test_ran_and_refused_are_both_on_disk_and_in_the_manifest(self, corpus):
        s = _sweep(corpus)
        assert s["outcomes"] == {"ran": 1, "refused": 1}
        assert s["refused_by_subtype"] == {"no_pdf": 1}
        a, b = corpus / "10.1--a", corpus / "10.1--b"
        res = json.loads((a / R.RESULT_NAME).read_text())
        assert res["n_duplicate_groups"] >= 1
        assert res["sweep"]["sweep_id"] == "t1"
        assert res["sweep"]["outcome"] == "ran"
        assert res["sweep"]["flags"]["segment_montages"] is True
        assert _status(a)["ran"] is True
        assert _status(a)["sweep"]["detector"]["fingerprint"] == R.detector_fingerprint()
        assert _status(b)["ran"] is False
        assert _status(b)["refusal_subtype"] == "no_pdf"
        assert not (b / R.RESULT_NAME).exists()
        rows = [json.loads(ln) for ln in
                Path(s["manifest"]).read_text().splitlines()]
        assert {r["paper"]: r["outcome"] for r in rows} == {
            "10.1--a": "ran", "10.1--b": "refused"}
        fr = s["fire_rate"]
        assert (fr["ran"], fr["fired"]) == (1, 1)
        assert fr["denominator"].startswith("papers where the detector ran")
        assert "excluded_by_reason" in rows[0]
        assert json.loads((Path(s["manifest"]).parent / "sweep.json").read_text())["finished_at"]

    def test_the_v2_document_validates_and_names_what_did_not_run(self, corpus):
        jsonschema = pytest.importorskip("jsonschema")
        from metascience_agent.core.prompts import findings_schema_v2
        _sweep(corpus)
        v2dir = corpus / "10.1--a" / R.V2_DIRNAME
        doc = json.loads((v2dir / R.V2_DOC).read_text())
        jsonschema.validate(doc, findings_schema_v2())
        assert doc["channels"]["image_forensics"]["state"] == "ran"
        assert doc["channels"]["tool_expert"]["state"] == "did_not_run"
        assert doc["adjudication"]["ran"] is False
        assert doc["findings"], "the firing paper produced no v2 rows"
        assert all(f["producer"] == "image_track" for f in doc["findings"])
        meta = json.loads((v2dir / R.V2_META).read_text())
        assert meta["stages"]["image_forensics"]["ran"] is True
        assert meta["total_cost_usd"] == 0.0
        assert meta["run_id"] == doc["run_id"]
        assert W.run_kind(doc) == "image_track"

    def test_the_summary_sentence_states_its_denominator(self, corpus):
        text = S.render_summary(_sweep(corpus))
        assert re.search(r"fire rate, denominator = papers where the detector ran"
                         r".*: 1 of 1 = 100\.0%", text)
        assert "refused: no_pdf 1" in text


# ---------------------------------------------------------------------------
# Resume: done is a stamp comparison, and every "not done" has a name
# ---------------------------------------------------------------------------

class TestResume:
    def test_a_second_identical_sweep_runs_nothing(self, corpus):
        _sweep(corpus)
        s = _sweep(corpus, sweep_id="t2")
        assert s["n_rows"] == 0
        assert s["selection"]["skipped_done"] == 2

    def test_changed_flags_are_named_stale(self, corpus):
        _sweep(corpus)
        s = _sweep(corpus, sweep_id="t2", max_panels=100)
        assert s["selection"]["not_done_reasons"] == {"stale:flags": 2}
        assert s["n_rows"] == 2

    def test_changed_inputs_re_run_only_that_paper(self, corpus):
        _sweep(corpus)
        _write_two_fig_pdf(corpus / "10.1--a", suffix=" (revised)")
        s = _sweep(corpus, sweep_id="t3")
        assert s["selection"]["not_done_reasons"] == {"stale:inputs": 1}
        assert [r["paper"] for r in _rows(s)] == ["10.1--a"]
        assert json.loads((corpus / "10.1--a" / R.RESULT_NAME).read_text())["sweep"]["sweep_id"] == "t3"

    def test_a_changed_furniture_set_is_stale_for_the_papers_it_touches(self, corpus):
        _sweep(corpus)
        shas = R.panel_shas(corpus / "10.1--a")
        assert shas
        furn = corpus / "furn.json"
        furn.write_text(json.dumps({"sha256": sorted(shas)}))
        s = _sweep(corpus, sweep_id="t4", furniture_from=furn)
        assert s["selection"]["not_done_reasons"] == {"stale:furniture": 1}

    def test_the_furniture_set_persists_and_only_grows(self, corpus):
        """After a furniture pass the re-run papers' indexes no longer list
        the withheld streams, so a screen of the indexes alone finds nothing
        next time; the corpus file is what remembers."""
        _sweep(corpus)
        shas = R.panel_shas(corpus / "10.1--a")
        assert shas
        S.save_corpus_furniture(corpus, shas, {"report": [
            {"sha256": x, "n_papers": 3} for x in shas], "min_papers": 3}, "seed")
        s2 = _sweep(corpus, sweep_id="t2")
        assert s2["furniture"]["f0"] == len(shas)
        assert s2["selection"]["not_done_reasons"] == {"stale:furniture": 1}
        cf = S.load_corpus_furniture(corpus)
        assert set(cf["sha256"]) >= shas and cf["history"][-1] == "seed"
        # a later sweep with a furniture pass keeps it, even though the
        # re-run paper's index now omits those streams
        s3 = _sweep(corpus, sweep_id="t3", furniture_pass=True)
        assert s3["furniture"]["f0"] == len(shas) and s3["furniture"]["f1"] >= len(shas)
        assert not (R.panel_shas(corpus / "10.1--a") & shas)

    def test_force_reruns_everything(self, corpus):
        _sweep(corpus)
        s = _sweep(corpus, sweep_id="t2", force=True)
        assert s["n_rows"] == 2


def _rows(summary: dict) -> list[dict]:
    return [json.loads(ln) for ln in Path(summary["manifest"]).read_text().splitlines()]


# ---------------------------------------------------------------------------
# A child that dies is recorded, and retried next time
# ---------------------------------------------------------------------------

class TestTrackFailures:
    def test_a_timeout_is_a_named_status_and_removes_stale_answers(self, corpus):
        _sweep(corpus)
        a = corpus / "10.1--a"
        assert (a / R.RESULT_NAME).exists()
        s = _sweep(corpus, sweep_id="t2", force=True, timeout_s=0.001)
        assert set(s["outcomes"]) == {"track_timeout"}
        assert _status(a)["refusal_subtype"] == "track_timeout"
        assert _status(a)["sweep"]["outcome"] == "track_timeout"
        assert not (a / R.RESULT_NAME).exists(), "a stale result outlived its run"
        assert not (a / R.V2_DIRNAME / R.V2_DOC).exists()
        # and the workbench reads it as a refusal with that subtype
        ch = W.scan_paper(a, corpus_root=corpus)["channels"]["image_forensics"]
        assert (ch["state"], ch["subtype"]) == ("refused", "track_timeout")

    def test_failed_papers_are_retried_by_default_and_skippable(self, corpus):
        _sweep(corpus, force=True, timeout_s=0.001)
        s = _sweep(corpus, sweep_id="t2", retry_failed=False)
        assert s["n_rows"] == 0
        s = _sweep(corpus, sweep_id="t3")
        assert s["selection"]["not_done_reasons"] == {"failed": 2}
        assert s["outcomes"] == {"ran": 1, "refused": 1}

    def test_the_failure_vocabulary_is_disjoint_from_the_childs_enum(self):
        schema = json.loads((__import__("metascience_observatory_image_analysis.prompts", fromlist=["SCHEMA_DIR"]).SCHEMA_DIR / "image_track.schema.json").read_text())
        enum = set(schema["properties"]["status"]["properties"]["refusal_subtype"]["enum"])
        assert not enum & set(R.TRACK_FAILURES)
        with pytest.raises(ValueError):
            R.retain_failure(Path("/nonexistent"), R.make_stamp("x", {
                "segment_montages": True, "include_supplements": False,
                "rendered_regions": False, "copy_move": False,
                "max_panels": 1, "emit_v2": False}), "no_pdf", "", set(), 0.0)


# ---------------------------------------------------------------------------
# What the workbench and the stats see
# ---------------------------------------------------------------------------

class TestConsumersReadItRight:
    def test_image_channel_ran_numeric_did_not_run(self, corpus):
        _sweep(corpus)
        a = W.scan_paper(corpus / "10.1--a", corpus_root=corpus)
        assert a["channels"]["image_forensics"]["state"] == "ran"
        assert a["channels"]["numeric"]["state"] == "did_not_run", (
            "an image-only review directory made the numeric pipeline read as ran")
        assert [r["kind"] for r in a["runs"]] == ["image_track"]
        b = W.scan_paper(corpus / "10.1--b", corpus_root=corpus)
        ch = b["channels"]["image_forensics"]
        assert (ch["state"], ch["subtype"]) == ("refused", "no_pdf")

    def test_no_swept_paper_is_ever_result_discarded(self, corpus):
        _sweep(corpus)
        for d in ("10.1--a", "10.1--b"):
            st = W.scan_paper(corpus / d, corpus_root=corpus)["channels"]["image_forensics"]["state"]
            assert st != "ran_result_discarded"

    def test_corpus_stats_prefers_a_full_review_over_a_newer_image_run(self, tmp_path):
        p = tmp_path / "10.1--p"
        full = p / "forensic_review"
        img = p / "forensic_review_image"
        full.mkdir(parents=True)
        img.mkdir()
        (full / "findings.v2.json").write_text(json.dumps({
            "schema_version": "2.0", "paper_id": "10.1--p", "run_id": "r_full",
            "findings": [], "channels": {"tool_expert": {"state": "ran"}}}))
        (full / "run_meta.json").write_text(json.dumps({"analysed_at": "2026-01-01T00:00:00Z"}))
        (img / "findings.v2.json").write_text(json.dumps({
            "schema_version": "2.0", "paper_id": "10.1--p", "run_id": "r_img",
            "findings": [], "channels": {"tool_expert": {"state": "did_not_run"},
                                         "image_forensics": {"state": "ran"}}}))
        (img / "run_meta.json").write_text(json.dumps({"analysed_at": "2026-09-01T00:00:00Z"}))
        assert CS._current_doc(p)["run_id"] == "r_full"
        (full / "findings.v2.json").unlink()
        assert CS._current_doc(p)["run_id"] == "r_img"

    def test_run_kind_is_one_derivation(self):
        assert W.run_kind({"channels": {"tool_expert": {"state": "ran"}}}) == "full_review"
        assert W.run_kind({"channels": {"image_forensics": {"state": "ran"}}}) == "image_track"
        assert W.run_kind({}) == "legacy"
        assert W.run_kind(None) == "legacy"


# ---------------------------------------------------------------------------
# Free by construction, and the paid path is untouched
# ---------------------------------------------------------------------------

class TestTheChildOwnsItsStdout:
    def test_a_rendered_exhibit_does_not_corrupt_the_json_contract(self, corpus):
        """MEASURED on the first real sweep: `render_review_media` printed
        "wrote <png>" to stdout ahead of the envelope, and a paper that ran
        perfectly well was filed as `track_output_invalid`."""
        import os
        import subprocess
        import sys
        from metascience_agent.agent import _image_track_command
        flags = {"segment_montages": True, "include_supplements": False,
                 "rendered_regions": False, "copy_move": False,
                 "max_panels": 200, "emit_v2": True,
                 "panel_detector": "gutter", "panel_detector_weights_sha256": "",
                 "reassemble_tiles": False, "keypoint_mode": "plain", "low_texture_keypoints": False, "hires_pixels": False, "adjacent_caption_labels": False, "stencil_art": False}
        stamp = R.make_stamp("stdout", flags)
        cmd = _image_track_command(corpus / "10.1--a",
                                   S._child_args(flags, None, stamp, True))
        # Every source root, explicitly: with only the host root the child
        # resolved the image package (and the copy-paste detector, measured
        # 2026-10-18 in a worktree: `cannot import name '_compat'`) through
        # the editable install, which may name a different checkout than the
        # one under test.
        detector = SRC.parent.parent / "copy_paste_detector" / "src"
        env = {**os.environ, "PYTHONPATH": os.pathsep.join(
            [str(SRC.parent), str(detector), str(IMAGE_SRC.parent)])}
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                              timeout=300)
        assert proc.returncode == 0, proc.stderr[-800:]
        assert proc.stdout.lstrip().startswith("{"), proc.stdout[:200]
        env_ = json.loads(proc.stdout)
        assert env_["retained"]["outcome"] == "ran"
        assert env_["result"]["n_duplicate_groups"] >= 1
        assert (corpus / "10.1--a" / R.MANIFEST_REL).exists()


class TestTheChainedAdjudication:
    """`image-sweep --adjudicate` is the whole isolated pipeline in one
    command. The sweep must still spend nothing on its own, and the paid
    pass must run only when asked."""

    def _invoke(self, corpus, extra):
        from typer.testing import CliRunner

        from metascience_agent.cli import app
        return CliRunner().invoke(
            app, ["image-sweep", str(corpus), "--sweep-id", "chain",
                  "--no-furniture-pass", "--jobs", "1"] + extra)

    def test_it_runs_only_when_asked_and_passes_the_models(self, corpus, monkeypatch):
        from metascience_observatory_image_analysis.image_forensics import adjudicate as ADJ
        seen = {}

        def fake(corpus_, **kw):
            seen.update(corpus=str(corpus_), **kw)
            return {"adjudicated": 0, "groups": 0, "groups_cleared": 0,
                    "papers_fully_cleared": 0, "papers_with_errors": 0,
                    "cost_usd": 0.0, "wall_seconds": 0.0, "out": "x",
                    "skipped": {}, "models": [], "require_all": True}

        monkeypatch.setattr(ADJ, "run_adjudication", fake)
        r = self._invoke(corpus, [])
        assert r.exit_code == 0, r.output
        assert not seen, "the sweep ran the paid pass without being asked"
        r = self._invoke(corpus, ["--force", "--adjudicate",
                                  "--adjudicate-models",
                                  "claude:sonnet,codex:gpt-5.6-luna"])
        assert r.exit_code == 0, r.output
        assert seen["models"] == [("claude", "sonnet"), ("codex", "gpt-5.6-luna")]
        assert seen["require_all"] is True
        assert seen["sweep_id"] == "chain"


class TestAPristineCopyDiesWithItsRun:
    """MEASURED 2026-09-02: a detector change re-ran 907 papers; the
    adjudicator's pristine copies from the earlier run survived, the next
    pass judged those stale groups, and wrote them BACK over the fresh
    result on 176 papers. Two guards now: the writer deletes the pristine
    on every new answer, and the adjudicator refuses a pristine or live
    file stamped by a run other than the one the status file names."""

    def test_a_resweep_deletes_the_pristine_copy(self, corpus):
        from metascience_observatory_image_analysis.image_forensics import adjudicate as ADJ
        _sweep(corpus)
        a = corpus / "10.1--a"
        assert ADJ.pristine_result(a) is not None
        assert (a / R.PRISTINE_NAME).exists()
        _sweep(corpus, sweep_id="t2", force=True)
        assert not (a / R.PRISTINE_NAME).exists()

    def test_a_stale_pristine_is_discarded_and_rebuilt(self, corpus):
        from metascience_observatory_image_analysis.image_forensics import adjudicate as ADJ
        _sweep(corpus)
        a = corpus / "10.1--a"
        pris = ADJ.pristine_result(a)
        # forge a pristine from "another run" while live + status stay current
        forged = dict(pris)
        forged["sweep"] = {**pris["sweep"], "detector": {"fingerprint": "deadbeef"}}
        forged["duplicate_groups"] = []
        (a / R.PRISTINE_NAME).write_text(json.dumps(forged))
        rebuilt = ADJ.pristine_result(a)
        assert rebuilt["duplicate_groups"], "the stale, empty pristine was reused"
        assert rebuilt["sweep"]["detector"]["fingerprint"] != "deadbeef"

    def test_a_stale_live_answer_is_refused_not_judged(self, corpus):
        from metascience_observatory_image_analysis.image_forensics import adjudicate as ADJ
        _sweep(corpus)
        a = corpus / "10.1--a"
        (a / R.PRISTINE_NAME).unlink(missing_ok=True)
        live = json.loads((a / R.RESULT_NAME).read_text())
        live["sweep"] = {**live["sweep"], "detector": {"fingerprint": "deadbeef"}}
        (a / R.RESULT_NAME).write_text(json.dumps(live))
        with pytest.raises(ADJ.StaleAnswer):
            ADJ.pristine_result(a)
        summary = ADJ.run_adjudication(corpus, models=[("codex", "x")],
                                       log=lambda s: None)
        assert summary["skipped"].get("stale_answer_needs_resweep") == 1
        assert summary["adjudicated"] == 0


class TestAdjudicationSelection:
    """`run_adjudication` must not re-judge a paper already judged by MORE
    models: with require_all, extra judges can only clear less, so a
    codex-only pass over a paper judged by {claude, codex} would replace the
    stricter verdict with a looser one and drop claude's per-group records,
    which live only in the live file. MEASURED 2026-09-02: such a pass
    selected 176 papers instead of 140."""

    def _seed(self, corpus, models):
        from metascience_observatory_image_analysis.image_forensics import adjudicate as ADJ
        d = corpus / "10.1--a"
        st = json.loads((d / R.STATUS_REL).read_text())
        st["adjudication"] = {"models": models, "require_all": True}
        (d / R.STATUS_REL).write_text(json.dumps(st))
        ADJ.pristine_result(d)          # ensure the pristine copy exists
        return d

    def _select(self, corpus, want, monkeypatch):
        from metascience_observatory_image_analysis.image_forensics import adjudicate as ADJ
        seen = []

        async def fake(paper_dir, **kw):
            seen.append(paper_dir.name)
            return {"paper": paper_dir.name, "skipped": "stubbed"}

        monkeypatch.setattr(ADJ, "adjudicate_paper", fake)
        summary = ADJ.run_adjudication(corpus, models=want, log=lambda s: None)
        return seen, summary

    def test_a_superset_of_models_counts_as_done(self, corpus, monkeypatch):
        _sweep(corpus)
        self._seed(corpus, ["claude:sonnet", "codex:gpt-5.6-luna"])
        seen, summary = self._select(
            corpus, [("codex", "gpt-5.6-luna")], monkeypatch)
        assert seen == [], seen
        assert summary["skipped"].get("already_adjudicated_by_more_models") == 1

    def test_a_different_model_set_is_still_judged(self, corpus, monkeypatch):
        _sweep(corpus)
        self._seed(corpus, ["codex:gpt-5.6-luna"])
        seen, _ = self._select(corpus, [("claude", "sonnet")], monkeypatch)
        assert seen == ["10.1--a"]


class TestItSpendsNothing:
    def test_no_llm_symbol_in_the_sweep_modules(self):
        """The paid paths, by the names code would have to import or call.
        (`adjudication` the WORD appears legitimately: the v2 document has
        a block of that name, written as `ran: False`.)"""
        for name in ("sweep.py", "retain.py"):
            src = (IMAGE_SRC / "image_forensics" / name).read_text()
            for bad in ("llm_backend", "resolve_backend",
                        "adjudicate_retained_findings", "_run_image_adjudication",
                        "copy_move_adjudicate", "openrouter", "claude -p",
                        "_run_stage"):
                assert bad not in src, f"{name} mentions {bad!r}"

    def test_the_default_child_argv_is_unchanged(self):
        # The child is the launcher (track_launcher.py), which hands these
        # exact arguments to image_track.main behind its code-change check.
        from metascience_agent.agent import _image_track_command
        cmd = _image_track_command(Path("/x"))
        assert cmd[1:] == ["-m", "metascience_observatory_image_analysis.image_forensics.track_launcher",
                           "/x", "--json"]
        assert _image_track_command(Path("/x"), ("--segment-montages",))[-1] == \
            "--segment-montages"

    def test_run_uid_matches_the_parallel_pipeline(self):
        from metascience_agent.parallel import _mint_run_uid
        assert _mint_run_uid("p", "t") == R._mint_run_uid("p", "t")
