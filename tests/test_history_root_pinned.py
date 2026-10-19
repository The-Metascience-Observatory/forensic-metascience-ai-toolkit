"""The report writers use the archive the run STARTED in, not a fresh lookup.

MEASURED 2026-10-13 (`wound_healing`, `cerebrolysin_flow` on the eval layout
`<dir>/paper` beneath an ancestor that already holds an archive): the analysis
parent run was recorded in the ancestor's archive. The image track then wrote
`.image_track/` into the paper's parent directory, `project_root(paper)` began
returning that directory, and `prepare_report_revision` looked the parent up in
a new, empty archive: `ValueError: unknown or unsealed run`, raised after the
analysis had been paid for and before any report was written. Vector-only
papers never create `.image_track`, so they never failed.
"""

from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit.analysis_runs import Archive, project_root
from forensic_metascience_ai_toolkit.history_runtime import prepare_report_revision, result_archive


def _staged(tmp_path):
    """An ancestor archive, a paper two levels below it, and a sealed parent run."""
    top = tmp_path / "top"
    paper = top / "proj" / "paper"
    paper.mkdir(parents=True)
    archive = Archive(top)
    execution = archive.execution("comprehensive", components=["comprehensive"])
    parent = archive.start(execution["id"], "comprehensive",
                           paper.relative_to(top).as_posix(), run_id="r_" + "a" * 16)
    sealed = archive.seal(parent, status="completed", completed_at="2026-10-13T00:00:00+00:00")
    assert project_root(paper.resolve()) == top.resolve()
    return top, paper, parent, sealed


def _result(paper, parent, **extra):
    return {"paper_path": str(paper),
            "run_meta": {"history": parent},
            "findings_v2": {"schema_version": "2.0", "findings": []},
            **extra}


def _image_track_appears(paper):
    (paper.parent / ".image_track").mkdir()


def test_the_hazard_is_real(tmp_path):
    """Without a pin, the second lookup lands in a different, empty archive."""
    top, paper, parent, _ = _staged(tmp_path)
    _image_track_appears(paper)
    assert project_root(paper.resolve()) == paper.parent.resolve() != top.resolve()
    with pytest.raises(ValueError, match="unknown or unsealed run"):
        prepare_report_revision(_result(paper, parent))


def test_a_pinned_root_survives_the_image_track(tmp_path):
    top, paper, parent, _ = _staged(tmp_path)
    result = _result(paper, parent, history_root=str(top))
    _image_track_appears(paper)
    assert result_archive(result).root == top.resolve()
    prepare_report_revision(result)          # must not raise
    # the revision was filed in the archive the run started in
    assert not (paper.parent / ".analysis_runs").exists()


def test_without_a_pin_the_old_lookup_still_applies(tmp_path):
    top, paper, parent, _ = _staged(tmp_path)
    assert result_archive(_result(paper, parent)).root == top.resolve()


def test_parallel_pins_the_root_where_the_parent_is_recorded():
    """The pin is set at the same place the parent is attached to the result."""
    source = (Path(__file__).resolve().parents[1] / "src" / "forensic_metascience_ai_toolkit"
              / "parallel.py").read_text()
    attach = source.index('result["run_meta"]["history"] = parent')
    pin = source.index('result["history_root"] = str(history.root)')
    assert 0 < pin - attach < 400
