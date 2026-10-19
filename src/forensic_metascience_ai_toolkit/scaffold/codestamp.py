"""WHICH CODE COMPUTED THIS ARTIFACT, recorded on the artifact itself.

WHY (D47, 2026-09-07). The two `account.headline.json` files on disk were
written by an older `coverage.py` than the one in the tree, and nothing said so:
ajcp read `65 / 162` on the artifact and `120 / 162` at HEAD, the supplement
`0 placed` on the artifact and `4` at HEAD. A whole round of diagnosis was spent
on residuals that the code had already stopped producing. That is
[[measured-claims-have-a-shelf-life]] and section 0b arriving through a file: a
coverage artifact is a CLAIM ABOUT THE CODE THAT WROTE IT, and it carried no way
to fail.

WHAT IS STAMPED. The commit, when the tree is a git checkout, and the sha256 of
each module that computes the thing -- because the commit alone is not enough on
a working tree with uncommitted edits, which is where every one of these numbers
is first measured. `sha256` is the one comparable token: two artifacts agree when
their `sha256` agrees, whatever the commit says.

NO SUBPROCESS, EVER. `coverage.headline` is specified as model-free and its test
makes `subprocess.run` raise; a stamp that shelled out to `git` would break that
guarantee for a fact that is sitting in a file. The commit is READ from
`.git/HEAD` and, when that is a symbolic ref, from the ref file or `packed-refs`.
A tree that is not a checkout stamps `code_commit: null`, which is a fact about
the tree and not an error.

THE STAMP IS NEVER A VERDICT. `is_current` says whether an artifact was written
by the code now on disk. It does not say the artifact is wrong -- only that
nothing here can vouch for it, which is exactly what the renderer prints instead
of a number.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

#: The modules whose source decides an account and its headline. Named rather
#: than discovered, so that adding a module to the computation is a deliberate
#: act that moves the stamp, and a module that only renders does not.
MODULES: tuple[str, ...] = (
    "scaffold/bind.py",
    "scaffold/checks.py",
    "scaffold/coverage.py",
    "scaffold/interpret.py",
    "scaffold/premises.py",
    # THE PREMISE READING FILLS THE SAME FIELDS `premises.py` DOES, from a
    # model's verdict on a candidate sentence rather than from a vocabulary, so
    # an account stamped with one is decided by this file too and the stamp has
    # to say so. Adding it MOVES the stamp, deliberately: every artifact read
    # against the old one is a claim about code that no longer decides them.
    "scaffold/premise_reading.py",
    "scaffold/reconstruct.py",
    "scaffold/schema.py",
    "scaffold/structure.py",
    "numerals.py",
    "quotes.py",
)


def _package_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _repo_root() -> Path:
    return _package_root().parent.parent


def _read_head(root: Path) -> str | None:
    """The checked-out commit, by reading files. `.git` may be a directory or,
    in a worktree, a file pointing at one."""
    dot = root / ".git"
    try:
        if dot.is_file():
            line = dot.read_text(encoding="utf-8").strip()
            if not line.startswith("gitdir:"):
                return None
            dot = Path(line.split(":", 1)[1].strip())
            if not dot.is_absolute():
                dot = (root / dot).resolve()
        head = (dot / "HEAD").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError, IndexError):
        return None
    if not head.startswith("ref:"):
        return head or None
    ref = head.split(":", 1)[1].strip()
    # A worktree's HEAD names a ref in the COMMON directory, which is what
    # `commondir` points at; without it a worktree stamps null rather than a
    # commit belonging to another checkout.
    roots = [dot]
    try:
        common = (dot / "commondir").read_text(encoding="utf-8").strip()
        roots.append((dot / common).resolve() if not Path(common).is_absolute() else Path(common))
    except OSError:
        pass
    for base in roots:
        try:
            return (base / ref).read_text(encoding="utf-8").strip() or None
        except OSError:
            pass
        try:
            for line in (base / "packed-refs").read_text(encoding="utf-8").splitlines():
                if line.endswith(" " + ref):
                    return line.split(" ", 1)[0].strip()
        except OSError:
            pass
    return None


def _sha256_of(p: Path) -> str | None:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


@lru_cache(maxsize=1)
def stamp() -> dict:
    """`{code_commit, modules, sha256}` for the code now on disk.

    Cached for the life of the process, so that two artifacts written by one run
    carry the same stamp even if a file is touched between them -- an artifact
    should record the code that RAN, and the code that ran is the code imported.
    """
    root = _package_root()
    mods = {name: _sha256_of(root / name) for name in MODULES}
    digest = hashlib.sha256(
        "\n".join(f"{k}={v}" for k, v in sorted(mods.items())).encode("utf-8")).hexdigest()[:16]
    return {"code_commit": _read_head(_repo_root()), "modules": mods, "sha256": digest}


def is_current(rec: dict | None) -> bool:
    """Was `rec` written by the code now on disk? A stamp that is absent, or of
    the wrong shape, is NOT current -- an artifact written before this module
    existed cannot be vouched for either, and that is the honest answer."""
    if not isinstance(rec, dict):
        return False
    got = rec.get("sha256")
    return bool(got) and got == stamp()["sha256"]


def describe(rec: dict | None) -> str:
    """One line naming what wrote an artifact, for a reader."""
    if not isinstance(rec, dict) or not rec.get("sha256"):
        return "no code stamp (written before the stamp existed)"
    commit = rec.get("code_commit")
    return f"code {rec['sha256']}" + (f" at commit {str(commit)[:12]}" if commit else
                                      " (the tree was not a git checkout)")


def stale_note(rec: dict | None, what: str) -> str:
    """What the renderer prints in place of a number it cannot vouch for."""
    return (f"{what} was computed by code this tree does not contain "
            f"({describe(rec)}; the code now on disk is {describe(stamp())}). "
            "The numbers are not printed: a coverage figure is a claim about the "
            "code that produced it, and this one cannot be checked against the "
            "code that would produce it now. Re-render the account to recompute it.")
