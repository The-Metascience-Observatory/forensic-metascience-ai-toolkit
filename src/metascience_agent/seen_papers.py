"""Papers we have already fetched or analysed, kept after their folders are deleted.

The registry (`eval/corpus_records/seen_papers.tsv.gz`) is a frozen file built
on 2026-09-30 (the script that built it has since been removed): one row per
DOI with its state, the corpora that held it, the runs and detector versions,
and human review decisions.
Corpus builders consult it so a deleted corpus is never fetched and analysed
a second time (Dan, 2026-09-30, before deleting most of
`/media/dan/data/metascience_observatory_image_analysis_papers`).

**Fails closed.** A missing or unreadable registry raises rather than returning
an empty set, because an empty set would silently re-admit every paper.
`METASCIENCE_SEEN_PAPERS=off` disables the check explicitly, and
`METASCIENCE_SEEN_PAPERS=<path>` points at another registry.
"""
from __future__ import annotations

import csv
import gzip
import os
from functools import lru_cache
from collections.abc import Iterable
from pathlib import Path

DEFAULT_REGISTRY = Path(__file__).resolve().parents[2] / "eval" / "corpus_records" / "seen_papers.tsv.gz"

#: States that block a paper. `selected` (on a list, never fetched) and
#: `failed_fetch` record history only.
BLOCKING = frozenset({"analysed", "fetched", "fetch_listed"})


class SeenRegistryMissing(RuntimeError):
    pass


def normalise(doi) -> str:
    d = str(doi or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d


def registry_path() -> Path | None:
    """The registry in use, or None when the check is switched off."""
    env = os.environ.get("METASCIENCE_SEEN_PAPERS", "").strip()
    if env.lower() == "off":
        return None
    return Path(env) if env else DEFAULT_REGISTRY


@lru_cache(maxsize=4)
def _load_cached(path: str, mtime_ns: int) -> dict[str, tuple[str, frozenset[str]]]:
    rows = {}
    with gzip.open(path, "rt", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            corpora = frozenset(c for c in (row.get("corpora") or "").split(";") if c)
            rows[normalise(row["doi"])] = (row["state"], corpora)
    if not rows:
        raise SeenRegistryMissing(f"seen-papers registry {path} has no rows")
    return rows


def load() -> dict[str, tuple[str, frozenset[str]]]:
    """{doi: (state, corpora)}; {} only when explicitly switched off."""
    path = registry_path()
    if path is None:
        return {}
    try:
        return _load_cached(str(path), path.stat().st_mtime_ns)
    except FileNotFoundError as exc:
        raise SeenRegistryMissing(
            f"seen-papers registry not found at {path}; restore it from git "
            "or set METASCIENCE_SEEN_PAPERS=off") from exc


def seen_dois(*, exempt_corpus: str | Iterable[str] | None = None) -> set[str]:
    """DOIs that must not be fetched or analysed again.

    ``exempt_corpus`` (one corpus name, or several) re-admits papers whose
    ONLY homes are those corpora, so a corpus -- or a whole cohort whose
    authors share papers -- can be re-prepared from its own folders without
    blocking itself.
    """
    exempt = ({exempt_corpus} if isinstance(exempt_corpus, str)
              else set(exempt_corpus or ()))
    out = set()
    for doi, (state, corpora) in load().items():
        if state not in BLOCKING:
            continue
        if exempt and corpora and all(c.split("__")[0] in exempt for c in corpora):
            continue
        out.add(doi)
    return out


def is_seen(doi, *, exempt_corpus: str | Iterable[str] | None = None) -> bool:
    return normalise(doi) in seen_dois(exempt_corpus=exempt_corpus)
