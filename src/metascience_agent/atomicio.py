"""Publish a file so no concurrent writer can rename a half-written one.

WHY THIS EXISTS. `extraction/docling_tables.py` already carried the comment
that explains it -- "two processes extracting the same paper at once left a
half-written cache that the other one read back as corrupt" -- and fixed it
there with a PID-suffixed temp file. Four other sites in this package wrote
tmp+rename with a FIXED temp name, which fixes nothing: two writers open the
same `foo.json.tmp`, their `write()` calls interleave, and one of them renames
a truncated file over the real one. Rename is atomic; choosing the same tmp
path is what makes it useless.

The sites, and what a torn write costs at each:

    paper_metadata.py       metadata.json      the identity every downstream
                                               consumer reads (db_push,
                                               corpus_stats, webapp_index)
    webapp_index.py         index.json         corpus-wide; a torn one makes
                                               EVERY later refresh give up
                                               with "unreadable index"
    review_io.py            review.json        a human's verdicts
    docling_tables.py       the table cache    re-extraction, the cheap case

PID IS NOT ENOUGH, which is why this does not simply copy the docling line.
`metascience batch --workers N` runs N papers concurrently INSIDE ONE PROCESS
(one asyncio task per paper), and `parallel.analyze_paper_parallel` runs its
two analysts under one `asyncio.gather`. Same PID, concurrent writers, same
temp path -- exactly the case a PID discriminator cannot see. The uuid is what
makes the name unique per CALL rather than per process.

Atomic replacement alone does not serialize a read-modify-write. Callers
that merge shared records must also hold file_lock across the read and
publish, as review_io and webapp_index now do.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path


def _unique_tmp(path: Path) -> Path:
    """A sibling temp path no concurrent caller can also choose.

    Hidden (leading dot) so a directory listing, and anything that globs the
    paper directory for real artefacts, does not show a transient.
    """
    return path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")


def atomic_write_text(path, text: str, encoding: str = "utf-8") -> Path:
    """Write `text` to `path` via a unique temp file and one atomic rename.

    The temp file is removed if anything fails, so a crashed writer leaves no
    litter beside the paper for the next reader to wonder about.
    """
    path = Path(path)
    tmp = _unique_tmp(path)
    try:
        tmp.write_text(text, encoding=encoding)
        tmp.replace(path)
    except BaseException:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return path


def scratch_sibling(path, tag: str, suffix: str) -> Path:
    """A unique scratch path beside `path`, for a file that is written, read by
    another process, then deleted.

    Distinct from `atomic_write_text` because there is nothing to publish: the
    OCR pass renders a page to PNG, hands the PATH to an OCR engine, and unlinks
    it. Two runs OCR-ing the same supplement used to pick the same deterministic
    name, so one read the other's page image and whichever finished first
    deleted it out from under the other.
    """
    path = Path(path)
    return path.parent / (
        f".{path.stem}.{tag}.{os.getpid()}.{uuid.uuid4().hex[:8]}{suffix}"
    )


from contextlib import contextmanager


@contextmanager
def file_lock(path: Path):
    """Cross-process transaction lock; acquire before reading, release after publish.

    Lock files are stable siblings, never unlinked (unlinking splits waiters
    between different inodes). Callers do not nest the same lock.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            if handle.seek(0, 2) == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)
