"""Every long image verb freezes BEFORE it works, in both CLIs, and every run
record says which tree executed it (`image_forensics/frozen_code.py`)."""
from tests.source_paths import IMAGE_ROOT
import json
import os
from pathlib import Path

import pytest
from metascience_observatory_image_analysis.image_forensics import frozen_code as F
from typer.testing import CliRunner


class Sentinel(F.FrozenCodeError):
    pass


@pytest.fixture
def refused(monkeypatch):
    """Make the freeze refuse, and fail if the verb did any work first."""
    calls = []

    def ensure_frozen(verb, *, opt_out=False, **_kw):
        calls.append((verb, opt_out))
        raise Sentinel(f"sentinel refusal for {verb}")

    monkeypatch.setattr(F, "ensure_frozen", ensure_frozen)
    from metascience_observatory_image_analysis.image_forensics import (
        dataset_benchmark,
        gate,
        sweep,
    )
    boom = lambda *a, **k: pytest.fail("work started before the freeze")  # noqa: E731
    monkeypatch.setattr(sweep, "run_sweep", boom)
    monkeypatch.setattr(gate, "run", boom)
    monkeypatch.setattr(dataset_benchmark, "run_benchmark", boom)
    from metascience_observatory_image_analysis.image_forensics import complete
    monkeypatch.setattr(complete, "run_complete", boom)
    return calls


def _apps():
    from metascience_observatory_image_analysis.cli import app as standalone

    from metascience_agent.cli import app as host
    return standalone, host


@pytest.mark.parametrize("which", ["standalone", "host"])
@pytest.mark.parametrize("verb", ["sweep", "complete", "gate", "dataset-run"])
def test_each_long_verb_freezes_before_any_work(refused, tmp_path, which, verb):
    standalone, host = _apps()
    app = standalone if which == "standalone" else host
    name = verb if which == "standalone" else f"image-{verb}"
    snapshot = tmp_path / "population.json"
    snapshot.write_text("{}")
    args = {"sweep": [str(tmp_path)],
            "complete": [str(snapshot), "--acceptance", str(snapshot)],
            "gate": ["--out", str(tmp_path)],
            "dataset-run": ["--root", str(tmp_path)]}[verb]
    result = CliRunner().invoke(app, [name, *args])
    assert result.exit_code == 2, result.output
    assert "sentinel refusal" in result.output
    assert len(refused) == 1 and refused[0][1] is False
    result = CliRunner().invoke(app, [name, *args, "--no-freeze"])
    assert refused[-1][1] is True


def test_gate_bookkeeping_modes_do_not_freeze(refused, tmp_path):
    standalone, _host = _apps()
    CliRunner().invoke(standalone, ["gate", "--out", str(tmp_path), "--compare-only"])
    CliRunner().invoke(standalone, ["gate", "--out", str(tmp_path), "--accept", "abc"])
    assert refused == []


def test_the_author_launcher_freezes_first(monkeypatch, tmp_path):
    import importlib.util
    path = IMAGE_ROOT / "examples" / "run_author_image_corpora.py"
    spec = importlib.util.spec_from_file_location("author_launcher_freeze", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seen = []

    def ensure_frozen(verb, *, opt_out=False, **_kw):
        seen.append(opt_out)
        raise Sentinel("stop")

    monkeypatch.setattr(F, "ensure_frozen", ensure_frozen)
    monkeypatch.setattr(module, "validate_populations",
                        lambda *a, **k: pytest.fail("validated before freezing"))
    monkeypatch.setattr(module.sys, "argv", ["launcher", "--corpora", str(tmp_path / "a.json"),
                                            "--acceptance", str(tmp_path / "b.json")])
    with pytest.raises(Sentinel):
        module.main()
    assert seen == [False]


def test_sweep_json_records_the_frozen_identity(tmp_path, monkeypatch):
    """The field is READ: a run without it cannot say whether a concurrent
    edit reached its children."""
    from metascience_observatory_image_analysis.image_forensics import sweep as S
    corpus = tmp_path / "corpus"
    (corpus / "10.1--b").mkdir(parents=True)
    (corpus / "10.1--b" / "metadata.json").write_text("{}")
    lines = []
    summary = S.run_sweep(corpus, jobs=1, progress=False, log=lines.append,
                          sweep_id="frozen_rec", furniture_pass=False)
    on_disk = json.loads((corpus / S.SWEEPS_SUBDIR / "frozen_rec" / "sweep.json").read_text())
    for record in (summary, on_disk):
        assert record["frozen_code"]["state"] == "opted_out"  # conftest
        assert record["frozen_code"]["frozen"] is False
    assert any("NOT FROZEN (opted_out)" in line for line in lines)

    monkeypatch.delenv(F.ENV_OPT)
    snap = F.snapshot(root=tmp_path / "frozen")
    monkeypatch.setenv(F.ENV_ACTIVE, snap["path"])
    monkeypatch.setattr(F, "_running_from", lambda dest: dest == snap["path"])
    summary = S.run_sweep(corpus, jobs=1, progress=False, log=lambda s: None,
                          sweep_id="frozen_rec2", furniture_pass=False)
    rec = summary["frozen_code"]
    assert rec["frozen"] is True and rec["path"] == snap["path"]
    assert rec["tree_sha256"] == snap["tree_sha256"]
    assert rec["detector_fingerprint"] == snap["detector_fingerprint"]
    assert os.environ[F.ENV_ACTIVE] == snap["path"]
