"""Copy-on-write file clones where the filesystem offers them.

WHY THIS EXISTS. `analysis_runs.workspace()` stages an isolated copy of a paper
directory per (run x paper) so a producer can mutate its inputs freely without
touching the original. MEASURED 2026-09-13 across three corpora, those staging
trees held **157.6 GB**, of which **19.9 GB was duplicated source PDFs** (4,043
files, byte-identical to the paper directory, different inodes). On
`image_discovery_2026-09_batch2` the staging area was nearly twice the size of
the corpus it staged.

A reflink removes the cost without removing the isolation. `FICLONE` asks the
filesystem to give a NEW inode that shares the source's extents; the first write
to either side allocates fresh blocks. The two files are independent in every
way a caller can observe -- separate inode, separate mode and times, separate
length -- they merely share storage until one of them changes.

THAT DISTINCTION IS WHY THIS IS ALLOWED WHERE A HARD LINK IS NOT, and both
rules it has to satisfy are about the same hazard. `analysis_runs`' module
docstring: "Objects are COPIES, never hard links into mutable paper
directories." `history_runtime`, publishing output back to a paper dir: "Copy,
no links." Both exist so that a producer writing to its private staging path can
never reach through and corrupt a shared original. A hard link is the same inode
and would do exactly that. A reflink cannot: writing through it is copy-on-write
by construction. So the isolation those comments protect is preserved exactly,
and only the redundant bytes go away.

WHERE IT WORKS. btrfs, and XFS mounted with reflink=1. Everything else -- ext4,
tmpfs, any cross-device copy, a kernel without the ioctl -- falls back to
`shutil.copy2` and costs exactly what it cost before. There is nothing to
configure and nothing to tune: the ioctl either works or it does not, and the
caller cannot tell the difference apart from `df`.

MEASURED on the corpus disk 2026-09-13 (`/media/dan/data`, XFS), 256 MB of
incompressible data:

    reflink clone via this helper   0.0 MB of filesystem space
    the same via shutil.copy2    256.9 MB
    `filefrag -v` on the clone   reports its extents as `shared`

**Measure this with `df`/`statvfs`, never with `du`.** `du` accounts blocks
per-file and knows nothing about sharing, so it bills a reflink to BOTH files
and reports a clone as full price -- which is how a first pass here read "64 MB
extra cost" off a clone that had in fact cost nothing. The giveaway that
sharing was real: overwriting 32 MB inside the 64 MB clone made `du` RISE by
32 MB, where overwriting part of a private file allocates nothing. That is
copy-on-write breaking the share, and it is visible only if you know which
instrument answers which question.

NOT A CACHE AND NOT DEDUPLICATION. This shares extents at the moment of copy
only. It never scans for identical files, never rewrites existing ones, and
holds no state.
"""
from __future__ import annotations

import errno
import os
import shutil

#: `linux/fs.h`: `#define FICLONE _IOW(0x94, 9, int)`. Not a tunable -- it is
#: the kernel's number for "share this file's extents with that one".
FICLONE = 0x40049409

#: Errnos that mean "this filesystem/kernel/pair cannot clone", as opposed to
#: "the copy failed". Each of these is a routine, expected answer and must fall
#: back silently; anything NOT in this set is a real I/O error and is raised,
#: because a staging copy that half-happened must never look like a success.
_UNSUPPORTED = frozenset({
    errno.EOPNOTSUPP,   # filesystem has no reflink (ext4, tmpfs)
    errno.ENOTTY,       # ioctl not understood at all
    errno.EXDEV,        # different filesystems
    errno.EINVAL,       # not a regular file, or an unsupported range
    errno.ENOSYS,       # kernel without FICLONE
    errno.EPERM,        # e.g. immutable/append-only source
    errno.ETXTBSY,      # source is a running executable
})


def _clone(src: str, dst: str) -> None:
    """Share `src`'s extents into a fresh `dst`, or raise OSError."""
    import fcntl

    src_fd = os.open(src, os.O_RDONLY)
    try:
        # 0o600 then copystat: the clone must not briefly expose the source's
        # permissions to a wider mode than the caller asked for.
        dst_fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            fcntl.ioctl(dst_fd, FICLONE, src_fd)
        finally:
            os.close(dst_fd)
    finally:
        os.close(src_fd)


def clone_or_copy(src, dst, *, follow_symlinks=True):
    """`shutil.copy2`-compatible copy that shares extents when the fs allows.

    Signature and return value match `shutil.copy2` so this can be handed to
    `shutil.copytree(..., copy_function=clone_or_copy)`.

    Falls back to a real copy for anything a clone cannot express: symlinks kept
    as symlinks, non-regular files, and every `_UNSUPPORTED` errno. A genuine
    I/O failure propagates rather than being retried as a copy -- a silent
    fallback on a real error would turn a failing disk into a slow one.
    """
    src_path = os.fspath(src)
    dst_path = os.fspath(dst)
    # copy2 semantics: a directory destination means "into that directory".
    if os.path.isdir(dst_path):
        dst_path = os.path.join(dst_path, os.path.basename(src_path))

    is_link = os.path.islink(src_path)
    if (is_link and not follow_symlinks) or not os.path.isfile(src_path):
        # Symlink-preserving copies and anything that is not a regular file are
        # copy2's business; FICLONE has nothing to say about them.
        return shutil.copy2(src, dst, follow_symlinks=follow_symlinks)

    try:
        _clone(src_path, dst_path)
    except OSError as exc:
        if exc.errno not in _UNSUPPORTED:
            raise
        # Leave nothing half-written behind for the fallback to inherit.
        try:
            os.unlink(dst_path)
        except OSError:
            pass
        return shutil.copy2(src, dst, follow_symlinks=follow_symlinks)
    shutil.copystat(src_path, dst_path, follow_symlinks=follow_symlinks)
    return dst_path


def supports_clone(directory) -> bool:
    """Whether `directory`'s filesystem can clone -- a DIAGNOSTIC, not a gate.

    Nothing branches on this: `clone_or_copy` always tries and always falls
    back, so a wrong answer here cannot change what a caller gets. It exists so
    a maintenance command can tell an operator whether reclaiming space will
    actually help on their disk.
    """
    probe = os.path.join(os.fspath(directory), f".fsclone-probe-{os.getpid()}")
    source, target = probe + ".src", probe + ".dst"
    try:
        with open(source, "wb") as handle:
            handle.write(b"\0" * 4096)
        try:
            _clone(source, target)
            return True
        except OSError:
            return False
    except OSError:
        return False
    finally:
        for path in (source, target):
            try:
                os.unlink(path)
            except OSError:
                pass
