"""The claim that has to hold or this must not be used: a clone is an
INDEPENDENT file, not a link. `analysis_runs` forbids hard links into mutable
paper directories precisely so a producer cannot reach through its private
staging copy and corrupt the original. If writing to a clone were visible on the
source, this helper would be that bug.

These tests pass on a filesystem with no reflink support too -- there the helper
falls back to `shutil.copy2` and the same guarantees hold for the boring reason.
That is deliberate: the test asserts the CONTRACT, not the mechanism.
"""
from __future__ import annotations

import errno
import os
import shutil
import stat
from pathlib import Path

import pytest

from metascience_agent import fsclone


def test_a_clone_is_independent_of_its_source(tmp_path):
    """THE test. Mutate the copy; the original must not move."""
    src = tmp_path / "panel.png"
    src.write_bytes(b"original bytes" * 100)
    dst = tmp_path / "staged.png"

    fsclone.clone_or_copy(src, dst)
    assert dst.read_bytes() == src.read_bytes()
    assert dst.stat().st_ino != src.stat().st_ino, "shares an inode -- this is a link"

    dst.write_bytes(b"the producer mutated its private copy")
    assert src.read_bytes() == b"original bytes" * 100
    assert dst.read_bytes() == b"the producer mutated its private copy"


def test_the_source_can_be_mutated_without_touching_the_clone(tmp_path):
    """The other direction, which matters just as much: a sweep republishing
    into the paper directory must not rewrite an archived staging copy."""
    src = tmp_path / "a.bin"
    src.write_bytes(b"v1")
    dst = tmp_path / "b.bin"
    fsclone.clone_or_copy(src, dst)
    src.write_bytes(b"v2 is longer than v1")
    assert dst.read_bytes() == b"v1"


def test_metadata_is_preserved_like_copy2(tmp_path):
    src = tmp_path / "x.bin"
    src.write_bytes(b"data")
    os.chmod(src, 0o640)
    os.utime(src, (1_600_000_000, 1_600_000_000))
    dst = tmp_path / "y.bin"
    fsclone.clone_or_copy(src, dst)
    assert stat.S_IMODE(dst.stat().st_mode) == 0o640
    assert int(dst.stat().st_mtime) == 1_600_000_000


def test_returns_the_destination_path_like_copy2(tmp_path):
    src = tmp_path / "x.bin"
    src.write_bytes(b"d")
    out = fsclone.clone_or_copy(src, tmp_path / "y.bin")
    assert Path(out) == tmp_path / "y.bin"


def test_a_directory_destination_means_into_that_directory(tmp_path):
    src = tmp_path / "paper.pdf"
    src.write_bytes(b"%PDF-1.4")
    into = tmp_path / "work"
    into.mkdir()
    out = fsclone.clone_or_copy(src, into)
    assert Path(out) == into / "paper.pdf"
    assert (into / "paper.pdf").read_bytes() == b"%PDF-1.4"


def test_overwrites_an_existing_destination_completely(tmp_path):
    """A stale longer file must not leave a tail behind the new content."""
    src = tmp_path / "s"
    src.write_bytes(b"short")
    dst = tmp_path / "d"
    dst.write_bytes(b"a much longer previous version of the file")
    fsclone.clone_or_copy(src, dst)
    assert dst.read_bytes() == b"short"


def test_works_as_copytree_copy_function(tmp_path):
    """The form `workspace()` actually needs."""
    src = tmp_path / "supplements"
    (src / "nested").mkdir(parents=True)
    (src / "one.csv").write_bytes(b"a,b\n1,2\n")
    (src / "nested" / "two.xml").write_bytes(b"<r/>")
    dst = tmp_path / "staged"
    shutil.copytree(src, dst, copy_function=fsclone.clone_or_copy)
    assert (dst / "one.csv").read_bytes() == b"a,b\n1,2\n"
    assert (dst / "nested" / "two.xml").read_bytes() == b"<r/>"


def test_a_symlink_kept_as_a_symlink_is_delegated(tmp_path):
    target = tmp_path / "real.bin"
    target.write_bytes(b"payload")
    link = tmp_path / "link.bin"
    link.symlink_to(target)
    dst = tmp_path / "copied.bin"
    fsclone.clone_or_copy(link, dst, follow_symlinks=False)
    assert dst.is_symlink()


def test_a_followed_symlink_copies_the_content(tmp_path):
    target = tmp_path / "real.bin"
    target.write_bytes(b"payload")
    link = tmp_path / "link.bin"
    link.symlink_to(target)
    dst = tmp_path / "copied.bin"
    fsclone.clone_or_copy(link, dst)
    assert not dst.is_symlink()
    assert dst.read_bytes() == b"payload"


def test_falls_back_silently_when_the_filesystem_cannot_clone(tmp_path, monkeypatch):
    """On ext4 every call takes this path, so it is the common case, not an edge."""
    def refuse(src, dst):
        raise OSError(errno.EOPNOTSUPP, "no reflink here")

    monkeypatch.setattr(fsclone, "_clone", refuse)
    src = tmp_path / "s"
    src.write_bytes(b"content")
    dst = tmp_path / "d"
    fsclone.clone_or_copy(src, dst)
    assert dst.read_bytes() == b"content"


def test_leaves_no_truncated_file_behind_when_falling_back(tmp_path, monkeypatch):
    """The clone opens the destination with O_TRUNC before the ioctl. If the
    ioctl then fails, a zero-length file must not survive into the fallback."""
    def truncate_then_refuse(src, dst):
        with open(dst, "wb"):
            pass                      # the O_TRUNC the real _clone performs
        raise OSError(errno.EXDEV, "cross-device")

    monkeypatch.setattr(fsclone, "_clone", truncate_then_refuse)
    src = tmp_path / "s"
    src.write_bytes(b"the real content")
    dst = tmp_path / "d"
    fsclone.clone_or_copy(src, dst)
    assert dst.read_bytes() == b"the real content"


def test_a_real_io_error_is_raised_not_retried_as_a_copy(tmp_path, monkeypatch):
    """A failing disk must not be laundered into a slow success."""
    def hardware_error(src, dst):
        raise OSError(errno.EIO, "the disk is unwell")

    monkeypatch.setattr(fsclone, "_clone", hardware_error)
    src = tmp_path / "s"
    src.write_bytes(b"x")
    with pytest.raises(OSError) as caught:
        fsclone.clone_or_copy(src, tmp_path / "d")
    assert caught.value.errno == errno.EIO


def test_a_missing_source_raises(tmp_path):
    with pytest.raises(OSError):
        fsclone.clone_or_copy(tmp_path / "absent", tmp_path / "d")


def test_supports_clone_answers_without_leaving_probe_files(tmp_path):
    answer = fsclone.supports_clone(tmp_path)
    assert answer in (True, False)
    assert list(tmp_path.iterdir()) == [], "probe files were not cleaned up"


def test_supports_clone_is_false_on_an_unwritable_directory(tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir(mode=0o500)
    try:
        assert fsclone.supports_clone(locked) is False
    finally:
        os.chmod(locked, 0o700)
