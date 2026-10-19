"""Where a paid table reading lives after its run directory is gone.

THE DEFECT THIS CLOSES, AND IT IS A DESIGN DEFECT RATHER THAN A BUG.
`reconstruct._cache_key` already computes exactly what a reading is a reading
OF -- the prompt version, the walker's cells, what was drawn, and the context
served -- and the reading it keys was then written ONLY inside that run's own
output directory. So the cache was co-located with the thing it exists to
protect: a wiped output directory is a wiped purchase. `/tmp/fmt-extract` has
been wiped three times (D74, D75, D81); each wipe destroyed readings that had
been paid for, and an exhaustive sweep on 2026-09-14 found ZERO papers anywhere
on the machine holding a cached table reading without its account -- there was
no second copy, because nothing ever wrote one.

WHAT THIS IS. A content-addressed store under `~/.cache/metascience/readings`,
keyed by THE SAME KEY `reconstruct` already computes. An entry holds the BYTES
of the files `passes.run_pass` wrote for that reading, so restoring one gives a
fresh run directory what it would have held had the reading been bought there.
`METASCIENCE_READING_CACHE` moves it; `off` (or an empty value) disables it
entirely, which is what the test suite does so a unit test can neither read nor
write a real purchase.

THREE PROPERTIES, EACH OF WHICH IS A RULE ABOUT WHAT THE STORE MAY NOT DO.

  1. THE RUN DIRECTORY IS AUTHORITATIVE. A reading already in the run directory
     under this key is the one used, always. The store is then offered the same
     bytes (`deposit`), and if it already holds something DIFFERENT under that
     key the run directory still wins and the disagreement is recorded rather
     than resolved. A cache that can overrule the artifact beside the account
     is a cache that can change a published number.

  2. A CORRUPT ENTRY IS A MISS, NOT A READING. Every file in an entry carries
     its own sha256 and the entry is re-hashed on every load; a truncated or
     hand-edited entry is refused with a note and the run pays again. This is
     the one failure mode worth more than the money the store saves: a reading
     served from half a file would be a reading of nothing, presented as the
     model's.

  3. THE STORE ADDS NO BITS. It restores bytes some model already produced and
     never computes, merges or repairs anything -- which is why it is not in
     `codestamp.MODULES`: no number in an account is decided by this file. What
     it decides is whether a number has to be BOUGHT AGAIN.

ONE BEHAVIOUR CHANGE, AND IT HAS TO BE SAID OUT LOUD. Before this module, a
second run of one paper into a FRESH output directory bought the table readings
again -- which is how the test-retest measurements were made (D28, D38: two
accounts of ajcp.70049, and what moved between them). It no longer does: a new
directory is answered from the store, because that is the whole point. A
deliberate re-read must therefore say so, with `METASCIENCE_READING_CACHE=off`
in the environment of that run. Otherwise the second reading is the first one,
and a retest that varies nothing will show an agreement of 1.00 and mean it
about the cache.

THE KEY IS 16 HEX CHARACTERS, i.e. 64 bits, because that is what
`reconstruct._cache_key` returns and changing it would discard every reading
already on disk -- the opposite of the point. Collisions are not a practical
concern at corpus scale (millions of entries are ~10^-8), and an entry that
somehow arrived under the wrong key still has to carry a `.meta.json` whose own
`cache_key` matches before it is served.

SIZE. About 100 KB an entry, most of it the raw CLI result, which is the
receipt for the purchase and is kept for that reason. Nothing is evicted and
nothing needs to be: the store is append-only, and deleting all of it costs
only what it was meant to save.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import passes as _passes

#: Where entries live when the environment says nothing.
DEFAULT_ROOT = Path.home() / ".cache" / "metascience" / "readings"
ENV = "METASCIENCE_READING_CACHE"
#: Values of `ENV` that switch the store off rather than move it.
OFF = frozenset({"", "off", "0", "no", "none", "false"})
STORE_VERSION = 1

#: What `passes.run_pass` writes for one pass, by suffix onto the pass name.
#: `.json` and `.meta.json` ARE the reading (`passes.load_pass` reads exactly
#: those two); the rest are the record of the purchase -- the prompt that
#: bought it, the schema it was bought under, and the untouched CLI result.
ARTIFACTS = (".json", ".meta.json", ".raw.json", ".prompt.md", ".schema.json", ".stderr.txt")
REQUIRED = (".json", ".meta.json")

_KEY = re.compile(r"[0-9a-f]{8,64}\Z")


def root() -> Path | None:
    """The store's directory, or None when it is switched off."""
    override = os.environ.get(ENV)
    if override is None:
        return DEFAULT_ROOT
    if override.strip().lower() in OFF:
        return None
    return Path(override).expanduser()


def entry_path(key: str) -> Path | None:
    """Where `key`'s entry is, or None when the store is off or the key is not
    a key. The shape test is not paranoia about hashes: a key is pasted into a
    path, and a key containing a separator would write outside the store."""
    r = root()
    if r is None or not _KEY.match(str(key or "")):
        return None
    return r / key[:2] / f"{key}.json"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_atomic(path: Path, text: str) -> str | None:
    """`text` at `path`, or why not. Written beside the target and renamed, so
    a reader never sees half a file and a crash leaves the old one intact."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=path.suffix)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except (OSError, ValueError) as exc:
        return f"could not write {path.name}: {type(exc).__name__}: {exc}"
    return None


def _read_files(name: str, out_dir: Path) -> tuple[dict[str, str], str | None]:
    """The artifacts `run_pass` wrote for `name`, by suffix. A file that is
    absent is absent; a file that is present and unreadable is a failure, and
    the caller is told which -- an entry missing half a purchase is not one."""
    got: dict[str, str] = {}
    for suffix in ARTIFACTS:
        p = Path(out_dir) / f"{name}{suffix}"
        if not p.is_file():
            continue
        try:
            got[suffix] = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return got, f"{p.name} is on disk and could not be read ({type(exc).__name__}: {exc})"
    missing = [s for s in REQUIRED if s not in got]
    if missing:
        return got, f"{name} is missing {', '.join(missing)}; nothing deposited"
    return got, None


def _entry(key: str, name: str, out_dir: Path, files: dict[str, str]) -> dict[str, Any]:
    return {
        "store_version": STORE_VERSION,
        "cache_key": key,
        "bought_as": name,
        "origin": str(Path(out_dir).resolve()),
        "deposited_at": _now(),
        "files": {s: {"sha256": _sha(t), "text": t} for s, t in files.items()},
    }


def load(key: str) -> tuple[dict[str, Any] | None, str | None]:
    """`(entry, why not)` for `key`. `(None, None)` is a plain miss -- the
    ordinary state of a key nobody has bought yet, and not worth a word.
    `(None, why)` means an entry IS there and is refused, which is worth one.

    Refused means one of: unparseable; written by a store version this code
    does not know; filed under a key it does not claim; missing the reading
    itself; a file whose bytes no longer hash to what the entry recorded; or a
    `.meta.json` that does not carry this key, which is the check that makes a
    restored directory behave exactly like the one that bought the reading.
    """
    path = entry_path(key)
    if path is None or not path.is_file():
        return None, None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, (f"cached reading {key} is unreadable and was not used "
                      f"({type(exc).__name__}: {exc})")
    if not isinstance(entry, dict):
        return None, f"cached reading {key} is not an object and was not used"
    if entry.get("store_version") != STORE_VERSION:
        return None, (f"cached reading {key} was written by store version "
                      f"{entry.get('store_version')!r}, not {STORE_VERSION}; not used")
    if entry.get("cache_key") != key:
        return None, (f"cached reading {key} is filed under that key and claims to be "
                      f"{entry.get('cache_key')!r}; not used")
    files = entry.get("files")
    if not isinstance(files, dict):
        return None, f"cached reading {key} carries no files; not used"
    for suffix in REQUIRED:
        if not isinstance(files.get(suffix), dict):
            return None, f"cached reading {key} is missing {suffix}; not used"
    for suffix, rec in files.items():
        if not isinstance(rec, dict) or not isinstance(rec.get("text"), str):
            return None, f"cached reading {key} has a malformed {suffix}; not used"
        if _sha(rec["text"]) != rec.get("sha256"):
            return None, (f"cached reading {key} failed its own checksum on {suffix} "
                          f"(the entry is truncated or was edited); not used")
    try:
        meta = json.loads(files[".meta.json"]["text"])
    except json.JSONDecodeError as exc:
        return None, f"cached reading {key} has unparseable meta ({exc}); not used"
    if not isinstance(meta, dict) or meta.get("cache_key") != key:
        return None, (f"cached reading {key} holds a reading whose own meta says "
                      f"{(meta or {}).get('cache_key')!r}; not used")
    return entry, None


def deposit(name: str, out_dir: str | Path, key: str) -> dict[str, Any]:
    """Put the reading `run_pass` wrote (or found) for `name` into the store.

    FIRST PURCHASE WINS. A valid entry already under this key is kept even when
    the bytes differ: two readings of one table can differ legitimately, the
    store's job is to be stable rather than current, and the run directory is
    authoritative for this run either way. The difference is REPORTED, because
    two different readings under one key is a fact about the model's stability
    that nobody would otherwise see. An INVALID entry is replaced -- it cannot
    be served, so keeping it protects nothing.
    """
    path = entry_path(key)
    if path is None:
        return {"status": "off" if root() is None else "not_a_key", "note": None}
    files, why = _read_files(name, Path(out_dir))
    if why:
        return {"status": "incomplete", "note": f"reading store: {why}", "path": str(path)}
    held, refused = load(key)
    if held is not None:
        same = all((held["files"].get(s) or {}).get("sha256") == _sha(t)
                   for s, t in files.items() if s in REQUIRED)
        if same:
            return {"status": "already_held", "note": None, "path": str(path)}
        return {"status": "differs", "path": str(path),
                "note": (f"reading store: the entry for {key} is a DIFFERENT reading from the one "
                         f"in this run directory ({held.get('bought_as')} bought "
                         f"{held.get('deposited_at')} in {held.get('origin')}). The run "
                         f"directory's reading is the one used; the store was left alone.")}
    err = _write_atomic(path, json.dumps(_entry(key, name, Path(out_dir), files),
                                         indent=1, ensure_ascii=False))
    if err:
        return {"status": "failed", "note": f"reading store: {err}", "path": str(path)}
    return {"status": "replaced" if refused else "deposited", "path": str(path),
            "note": (f"reading store: replaced an unusable entry for {key} ({refused})"
                     if refused else None)}


def backfill(out_dir: str | Path) -> dict[str, Any]:
    """Deposit every reading in `out_dir` that says which key it answers.

    WHY THIS IS NOT THE SAME AS DEPOSITING WHAT THIS RUN USED. A reading is
    keyed on the walker's cells and on what was drawn, so the key can only be
    computed AFTER the table renders -- and a table that no longer renders
    never reaches the lookup at all. MEASURED on the ajcp run directory
    2026-09-14: tables 5 and 6 came back `not_attempted` for exactly that
    reason, and $0.59 of readings already paid for would have been left
    unprotected by a store that only ever kept what the current run consumed.
    The money is on the disk; whether this run can use it is a separate
    question from whether it survives the disk being wiped.

    Every reading carries its own key in its meta, so this needs no rendering,
    no model and no XML -- only the directory.
    """
    out = Path(out_dir)
    counts: dict[str, int] = {}
    notes: list[str] = []
    if root() is None or not out.is_dir():
        return {"counts": counts, "notes": notes}
    for meta_p in sorted(out.glob("*.meta.json")):
        try:
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            notes.append(f"reading store: {meta_p.name} is on disk and unreadable "
                         f"({type(exc).__name__}); the reading beside it was not deposited")
            continue
        key = (meta or {}).get("cache_key") if isinstance(meta, dict) else None
        if not key:
            continue  # a pass that is not content-addressed; nothing to file it under
        res = deposit(meta_p.name[: -len(".meta.json")], out, str(key))
        counts[res["status"]] = counts.get(res["status"], 0) + 1
        if res.get("note"):
            notes.append(res["note"])
    return {"counts": counts, "notes": notes}


def restore(key: str, name: str, out_dir: str | Path) -> tuple[dict[str, Any] | None, str | None]:
    """Write `key`'s stored reading into `out_dir` under `name` and return it
    exactly as `passes.load_pass` would. `(None, None)` on a plain miss.

    `.json` IS WRITTEN LAST, deliberately: `load_pass` keys on its existence,
    so an interrupted restore leaves a directory that reads as having no
    reading rather than as having one with no meta.

    A `<name>.restored.json` is written beside it. A restored reading is
    otherwise indistinguishable from one bought here -- same bytes, same names
    -- and a reader of this directory is entitled to know that the prompt in it
    was addressed to a PNG at another path, in another run, on another day.
    """
    entry, why = load(key)
    if entry is None:
        # `load`'s reasons are reasons, and `deposit` composes them into its
        # own; a reason that reaches an account's problem list is named.
        return None, (f"reading store: {why}" if why else None)
    files: dict[str, dict] = entry["files"]
    order = [s for s in ARTIFACTS if s in files and s != ".json"] + [".json"]
    for suffix in order:
        err = _write_atomic(Path(out_dir) / f"{name}{suffix}", files[suffix]["text"])
        if err:
            return None, f"reading store: {key} could not be restored: {err}"
    marker = {
        "restored_from_store": str(entry_path(key)),
        "cache_key": key,
        "bought_as": entry.get("bought_as"),
        "bought_in": entry.get("origin"),
        "deposited_at": entry.get("deposited_at"),
        "restored_at": _now(),
        "restored_as": name,
        "sha256": {s: r.get("sha256") for s, r in files.items()},
        "note": ("These files were not produced by this run. They are the bytes of the reading "
                 "this cache key was bought with, restored from the content-addressed store; "
                 "the prompt and raw result name the run that paid for them."),
    }
    _write_atomic(Path(out_dir) / f"{name}.restored.json",
                  json.dumps(marker, indent=1, ensure_ascii=False))
    got = _passes.load_pass(name, out_dir)
    if got is None or (got.get("meta") or {}).get("cache_key") != key:
        return None, (f"reading store: {key} was restored into {out_dir} and did not read back "
                      f"as a reading of that key; not used")
    return got, None


def bought_here(name: str, out_dir: str | Path) -> None:
    """Drop any marker saying `name` was restored rather than bought.

    A reading restored under one key and then RE-BOUGHT under another -- the
    cells moved, or the prompt version did -- overwrites its own files while
    the marker beside them goes on claiming they came from the store, in
    another directory, on another day. A provenance note that outlives the
    thing it describes is worse than none, because it is read as true.
    """
    try:
        (Path(out_dir) / f"{name}.restored.json").unlink(missing_ok=True)
    except OSError:  # the marker stays and says something false; nothing else breaks
        pass


def reuse(name: str, out_dir: str | Path, key: str) -> tuple[dict[str, Any] | None, list[str]]:
    """A reading already paid for under `key`, with any notes for the account.

    The run directory first, the store second, and nothing else: a miss returns
    None and the caller pays, exactly as before this module existed.

    A run directory holding a reading of a DIFFERENT key under this name is
    stale -- the cells, the context or the prompt version have moved since --
    and restoring over it is what a paid call would have done anyway. It is
    said out loud rather than done quietly, because the file that disappears
    was somebody's evidence.
    """
    notes: list[str] = []
    out = Path(out_dir)
    saved = _passes.load_pass(name, out)
    if saved and (saved.get("meta") or {}).get("cache_key") == key:
        note = deposit(name, out, key).get("note")
        if note:
            notes.append(note)
        return {**saved, "reused_from": "run_dir"}, notes
    displaced = (saved.get("meta") or {}).get("cache_key") if saved else None
    got, why = restore(key, name, out)
    if got is not None and displaced:
        notes.append(f"reading store: {name} in this run directory was a reading of "
                     f"{displaced}, not of {key}; the reading for {key} was restored from the "
                     f"store over it, as a paid call would have done")
    if why:
        notes.append(why)
    if got is None:
        return None, notes
    return {**got, "reused_from": "store"}, notes
