"""One temp file per WRITER, not per process.

The bug this module fixes: four sites wrote tmp+rename with a fixed temp name,
so two concurrent writers opened the same `foo.json.tmp`, interleaved their
`write()` calls, and renamed a truncated file over the real one. Rename is
atomic; choosing the same tmp path is what made it useless.
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from forensic_metascience_ai_toolkit.atomicio import atomic_write_text, scratch_sibling


def test_it_writes_the_content(tmp_path):
    p = atomic_write_text(tmp_path / "a.json", '{"x": 1}')
    assert json.loads(p.read_text()) == {"x": 1}


def test_no_temp_file_is_left_behind(tmp_path):
    atomic_write_text(tmp_path / "a.json", "{}")
    assert [p.name for p in tmp_path.iterdir()] == ["a.json"]


def test_same_process_writers_get_different_temp_paths(tmp_path):
    """PID ALONE IS NOT ENOUGH, and that is why this does not simply copy the
    line docling already had. `batch --workers N` runs papers concurrently
    inside ONE process, and the two analysts of one paper run under a single
    `asyncio.gather` -- same PID, concurrent writers, and a PID discriminator
    that distinguishes nothing."""
    from forensic_metascience_ai_toolkit.atomicio import _unique_tmp
    target = tmp_path / "index.json"
    names = {_unique_tmp(target).name for _ in range(200)}
    assert len(names) == 200
    assert all(str(os.getpid()) in n for n in names)


def test_a_failed_write_leaves_no_litter(tmp_path, monkeypatch):
    """A crashed writer must not leave a `.foo.json.<pid>.<uuid>.tmp` beside
    the paper for the next reader to wonder about."""
    real_replace = Path.replace

    def boom(self, target):
        raise RuntimeError("disk full")

    monkeypatch.setattr(Path, "replace", boom)
    try:
        atomic_write_text(tmp_path / "a.json", "x")
    except RuntimeError:
        pass
    monkeypatch.setattr(Path, "replace", real_replace)
    assert list(tmp_path.iterdir()) == []


def test_concurrent_writers_never_publish_a_partial_file(tmp_path):
    """The invariant that matters: whichever write lands, lands WHOLE."""
    target = tmp_path / "big.json"
    payloads = [json.dumps({"who": i, "pad": "x" * 200_000}) for i in range(8)]

    def write(text):
        atomic_write_text(target, text)
        # Every observation of the target must parse -- never a torn file.
        return json.loads(target.read_text())

    with ThreadPoolExecutor(max_workers=8) as pool:
        seen = list(pool.map(write, payloads))

    assert all(isinstance(d, dict) and "who" in d for d in seen)
    assert json.loads(target.read_text())["pad"] == "x" * 200_000


def test_scratch_sibling_is_unique_and_beside_the_file(tmp_path):
    """The OCR pass renders a page to PNG, hands the PATH to an engine, then
    unlinks it. Two runs used to pick the same deterministic name, so one read
    the other's page image and whichever finished first deleted it."""
    supp = tmp_path / "supplement.pdf"
    a = scratch_sibling(supp, "ocr-p3", ".png")
    b = scratch_sibling(supp, "ocr-p3", ".png")
    assert a != b
    assert a.parent == b.parent == tmp_path
    assert a.suffix == ".png" and a.name.startswith(".supplement.ocr-p3.")
