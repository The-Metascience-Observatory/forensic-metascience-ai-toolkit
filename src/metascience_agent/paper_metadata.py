"""Bibliographic identity for a paper directory.

The workbench needs title, first author, journal, volume, issue, year.
Those are not forensic findings: they are who-what-where, and they come
from (in order):

  1. `metadata.json` beside the paper — a previous fetch, Dropbox-synced
  2. The DOI cascade in `fetch_metadata_from_doi` (copied from the
     observatory website ingestor)
  3. Publisher XML already on disk (`jats.article_metadata`) — free, local
  4. The directory name, which is a DOI with `/` written as `--`

A missing file is not empty metadata. A failed fetch writes `error` so
the next scan can say "we asked and the APIs did not answer" instead of
pretending the paper has no title.

The index scanner NEVER calls the network. It only reads `metadata.json`.
`ensure_metadata` is the fetch path (CLI, workbench background refill).
A row that already has a title and an author is left alone — missing
volume/issue/pages is a small gap, not a refetch. A recorded failure is
retried only after a day, so a downed API is not asked on every page open.

Schema 1.1 (2026-08-21, findings_v2.md §11) adds `journal_normalized`
(passthrough for unknown journals — never null when the journal is known),
`authors_list` (`[{given, family, full}]`, structured sources preserved
instead of re-guessing surnames from a joined string), and `metadata_status`
(`ok|partial|failed|offline` — "offline" means we never asked the network,
a different fact from "the APIs failed"). `needs_enrichment` gates the
backfill. A 1.0 file upgrades in place on the next fetch: the 1.1 fields
derive locally at zero network cost; the one network-costing step —
refetching initials-only author names — runs once at upgrade time, keeps
the answer only when more complete, and its failure never blocks the
upgrade.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .extraction.jats import article_metadata, find_xml
from .extraction.xml_html import doi_url
from .fetch_metadata_from_doi import (
    _authors_have_abbreviations,
    _is_initial_token,
    _new_authors_are_better,
    fetch_metadata_from_doi,
)
from .journal_names import normalize as normalize_journal_name

FILENAME = "metadata.json"
SCHEMA_VERSION = "1.1"
# A failed DOI lookup is not retried on every paper open. A day is long
# enough that a flaky Crossref outage is not a per-click cost, and short
# enough that a paper we asked too early still gets a second chance.
_RETRY_AFTER = timedelta(hours=24)

FIELDS = ("title", "authors", "journal", "volume", "issue", "pages", "year", "url")

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s]+", re.I)


def doi_from_slug(slug: str) -> str | None:
    """`10.1234--foo.bar (Case Conflict)` → `10.1234/foo.bar`.

    EVERY `--` is a `/`, because `paper_ids.doi_dirname` (the producer)
    replaces every `/`. Replacing only the first one turned
    `10.1210--clinem--dgag124` into `10.1210/clinem--dgag124` — a DOI
    that resolves nowhere — and 59 directories in the papers root carry
    two separators (Oxford's `10.1093/<journal>/<id>` pattern, Research
    Square's `/v1` suffix). The other 58 were only spared because their XML
    or provenance file named the DOI before the slug was consulted.
    """
    if not slug:
        return None
    text = slug.replace("--", "/")
    m = _DOI_RE.search(text)
    if not m:
        return None
    return m.group(0).rstrip(").,;]")


def first_author(authors: str | None) -> str | None:
    """The first name in an author list, or None.

    Lists from the DOI cascade are `; `-separated (`Nina Mazar; Dan Ariely`).
    XML and some APIs join with commas (`Stefan Strilciuc, Constantin Radu`).
    A single `Last, First` name is left intact.
    """
    if not authors or not str(authors).strip():
        return None
    s = str(authors).strip()
    if ";" in s:
        first = s.split(";")[0].strip()
        return first or None
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) >= 3:
        return parts[0]
    if len(parts) == 2 and len(parts[1].split()) >= 2:
        return parts[0]
    return s


def given_is_initials(given: Any) -> bool:
    """True when a given name is initials-ONLY: 'J.', 'J. R.', 'J', 'A.C.'.

    Uses `_is_initial_token` from the fetch cascade, which is what keeps
    'Ji-Woo', 'Jo' and all-caps short names ('JAN', 'KIM') out: an undotted
    token counts as an initial only when it is a single uppercase letter.
    'J. Robert' is not initials-only — one full word clears the name.
    """
    if not isinstance(given, str) or not given.strip():
        return False
    tokens = given.replace(",", " ").split()
    return bool(tokens) and all(_is_initial_token(t) for t in tokens)


def authors_list_from_crossref(payload: Any) -> list[dict]:
    """`[{given, family, full}]` from a Crossref `message` dict.

    Keeps the structured given/family split Crossref already provides, so
    nothing downstream has to re-guess which token is the surname. Values
    are preserved verbatim — no initial-dotting, no case folding.
    """
    authors = payload.get("author") if isinstance(payload, dict) else None
    out: list[dict] = []
    for a in authors or []:
        if not isinstance(a, dict):
            continue
        given = str(a.get("given") or "").strip() or None
        family = str(a.get("family") or "").strip() or None
        full = " ".join(p for p in (given, family) if p)
        if not full:
            full = str(a.get("name") or "").strip()
        if not full:
            continue
        out.append({"given": given, "family": family, "full": full})
    return out


def _split_author_names(s: Any) -> list[str]:
    """One string of authors → one string per author (first_author's rules)."""
    if not s or not str(s).strip():
        return []
    s = str(s).strip()
    if ";" in s:
        return [n.strip() for n in s.split(";") if n.strip()]
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) >= 3:
        return parts
    if len(parts) == 2 and len(parts[1].split()) >= 2:
        return parts
    return [s]


def _name_parts(name: str) -> dict:
    """{given, family, full} from one name string, best effort.

    `full` is the source of truth; given/family are a split of convenience.
    'Last, First' splits on the comma; 'First Last' takes the final token as
    the family name, which mis-files multi-word surnames ('van der Berg') —
    that is why structured sources are preserved instead of round-tripped.
    """
    name = name.strip()
    if "," in name:
        family, _, given = name.partition(",")
        family, given = family.strip(), given.strip()
        full = f"{given} {family}".strip() if given else family
        return {"given": given or None, "family": family or None, "full": full}
    tokens = name.split()
    if len(tokens) == 1:
        return {"given": None, "family": tokens[0], "full": name}
    return {"given": " ".join(tokens[:-1]), "family": tokens[-1], "full": name}


def build_authors_list(meta: dict | None) -> list[dict]:
    """`[{given, family, full}]` for a metadata record.

    Precedence: an already-structured `authors_list` (a 1.1 file, or a
    caller that kept Crossref structure) is preserved; a raw Crossref
    `author` array is converted; only then is the joined `authors` string
    parsed. Structure, once had, is never destroyed by a round-trip.
    """
    if not isinstance(meta, dict):
        return []
    existing = meta.get("authors_list")
    if isinstance(existing, list) and existing and all(
            isinstance(e, dict) and e.get("full") for e in existing):
        return [{"given": e.get("given") or None,
                 "family": e.get("family") or None,
                 "full": str(e["full"])} for e in existing]
    if isinstance(meta.get("author"), list):
        structured = authors_list_from_crossref(meta)
        if structured:
            return structured
    authors = meta.get("authors")
    return [_name_parts(n) for n in _split_author_names(
        authors if isinstance(authors, str) else None)]


def authors_have_initials(meta: dict | None) -> bool:
    """Does any author's given name look initials-only?

    Reads the structured list when one exists; otherwise falls back to the
    fetch cascade's string heuristic. Single-token names (no given name at
    all) are not "initials" — they are absence, a different fact.
    """
    if not isinstance(meta, dict):
        return False
    alist = meta.get("authors_list")
    if isinstance(alist, list) and alist:
        return any(isinstance(e, dict) and given_is_initials(e.get("given"))
                   for e in alist)
    authors = meta.get("authors")
    return _authors_have_abbreviations(
        authors if isinstance(authors, str) else None)


def _normalize_to_first_last(authors_str: str) -> str:
    """'Mazar, Nina; Ariely, Dan' → 'Nina Mazar; Dan Ariely'.

    Ported from expand_author_names.py: some APIs (Dimensions) answer in
    'Last, First' and the cache stores 'First Last', so a fetched list is
    folded before it is compared or kept.
    """
    names = str(authors_str).split(";")
    normalized = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        if "," in name:
            last, _, first = name.partition(",")
            last, first = last.strip(), first.strip()
            normalized.append(f"{first} {last}" if first and last else name)
        else:
            normalized.append(name)
    return "; ".join(normalized)


def citation_bits(meta: dict | None) -> str:
    """`Journal 12(3) (2021)` — empty pieces are omitted, not shown as None."""
    if not isinstance(meta, dict):
        return ""
    journal = str(meta.get("journal") or "").strip()
    volume = str(meta.get("volume") or "").strip()
    issue = str(meta.get("issue") or "").strip()
    year = meta.get("year")
    year_s = str(year).strip() if year not in (None, "") else ""
    loc = volume
    if issue:
        loc = f"{volume}({issue})" if volume else f"({issue})"
    parts = [p for p in (journal, loc, f"({year_s})" if year_s else "") if p]
    return " ".join(parts)


def load_cached(paper_dir: Path) -> dict | None:
    """`metadata.json` if it is readable JSON, else None.

    None means we have not asked, or the file is unreadable. A file that
    records `error` is a result, not an absence.
    """
    path = Path(paper_dir) / FILENAME
    if not path.is_file():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def doi_of(paper_dir: Path) -> str | None:
    paper_dir = Path(paper_dir)
    cached = load_cached(paper_dir)
    if isinstance(cached, dict) and cached.get("doi"):
        return str(cached["doi"])
    for cand in (paper_dir / f"{paper_dir.name}.provenance.json",
                 paper_dir / "provenance.json"):
        obj = _read_json(cand)
        if not isinstance(obj, dict):
            continue
        ident = obj.get("identifier") or obj.get("doi")
        if ident:
            d = doi_from_slug(str(ident))
            if d:
                return d
        resolved = obj.get("identifiers_resolved")
        if isinstance(resolved, dict) and resolved.get("doi"):
            return str(resolved["doi"])
        meta = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else obj
        if isinstance(meta, dict) and meta.get("doi"):
            return str(meta["doi"])
    xml_meta = xml_seed(paper_dir)
    if xml_meta.get("doi"):
        return str(xml_meta["doi"])
    return doi_from_slug(paper_dir.name)


def xml_seed(paper_dir: Path) -> dict:
    """What the publisher XML already says, with no network.

    Empty strings from `article_metadata` become None so they do not
    look like a title of length zero.
    """
    xml = find_xml(paper_dir)
    if xml is None:
        return {}
    try:
        import xml.etree.ElementTree as ET
        raw = article_metadata(ET.parse(xml).getroot())
    except Exception:
        return {}
    out: dict[str, Any] = {}
    for key in FIELDS + ("doi",):
        val = raw.get(key)
        if val in (None, ""):
            continue
        out[key] = val
    if out.get("authors") and isinstance(raw.get("author_list"), list):
        # Prefer the already-joined authors string.
        pass
    return out


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _blank(val: Any) -> bool:
    return val in (None, "", "NaN")


def _merge(base: dict, incoming: dict) -> dict:
    out = dict(base)
    for key, val in incoming.items():
        if _blank(val):
            continue
        if _blank(out.get(key)):
            out[key] = val
        elif key == "authors" and _new_authors_are_better(out.get(key), val):
            out[key] = val
    return out


def _normalise(meta: dict, *, doi: str | None, source: str,
               error: str | None = None) -> dict:
    authors = meta.get("authors")
    year = meta.get("year")
    if isinstance(year, str) and year.isdigit():
        year = int(year)
    journal = meta.get("journal") or None
    rec = {
        "schema_version": SCHEMA_VERSION,
        "doi": doi,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "title": meta.get("title") or None,
        "authors": authors or None,
        "first_author": first_author(authors if isinstance(authors, str) else None),
        "journal": journal,
        # Passthrough for unknown journals: a known journal NEVER maps to null.
        "journal_normalized": normalize_journal_name(journal) if journal else None,
        "authors_list": build_authors_list(meta),
        "volume": meta.get("volume") or None,
        "issue": meta.get("issue") or None,
        "pages": meta.get("pages") or None,
        "year": year,
        "url": meta.get("url") or doi_url(doi),
        "error": error,
    }
    rec["metadata_status"] = derive_status(rec)
    return rec


def _write(paper_dir: Path, rec: dict) -> dict:
    # Via `atomicio`, not a fixed `metadata.json.tmp`: two runs on one paper
    # directory (a cross-backend comparison, or `batch --workers N`) both
    # opened that one temp path and renamed each other's half-written bytes
    # over the identity file every downstream consumer reads.
    # The file is a cache: a failed write (a full disk, a read-only mirror)
    # must not discard a record the APIs already answered. Measured
    # 2026-09-26: a full data disk made every summary-figure reference blank.
    from .atomicio import atomic_write_text
    try:
        atomic_write_text(Path(paper_dir) / FILENAME,
                          json.dumps(rec, indent=2) + "\n")
    except OSError as exc:
        import sys
        print(f"metadata.json not cached for {paper_dir}: {exc}", file=sys.stderr)
    return rec


def has_displayable(meta: dict | None) -> bool:
    """Enough to put a title (or a first author + year) on a row."""
    if not isinstance(meta, dict) or meta.get("error"):
        return False
    return bool(meta.get("title") or meta.get("first_author") or meta.get("authors"))


def has_core_identity(meta: dict | None) -> bool:
    """Title and an author. Volume, issue and pages may be absent."""
    if not isinstance(meta, dict):
        return False
    title = str(meta.get("title") or "").strip()
    author = str(meta.get("authors") or meta.get("first_author") or "").strip()
    return bool(title and author)


def _fetched_recently(fetched_at: Any) -> bool:
    if not fetched_at:
        return False
    try:
        raw = str(fetched_at).replace("Z", "+00:00")
        ts = datetime.fromisoformat(raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - ts < _RETRY_AFTER
    except ValueError:
        return False


def needs_network(meta: dict | None) -> bool:
    """Should we ask the DOI cascade again?

    Small bibliographic gaps (no volume, no issue) are not a refetch.
    A recorded failure is not asked again until `_RETRY_AFTER` has passed.
    A paper with no DOI will not grow a DOI by asking, so we do not retry.
    """
    if has_core_identity(meta):
        return False
    if not isinstance(meta, dict):
        return True
    err = str(meta.get("error") or "")
    if "no DOI" in err:
        return False
    if err and _fetched_recently(meta.get("fetched_at")):
        return False
    return True


def derive_status(meta: dict | None) -> str:
    """`ok | partial | failed | offline` for a metadata record.

    - `failed`: an error was recorded and nothing usable came back.
    - `partial`: some fields, but not the core identity (or usable fields
      rescued alongside a recorded error).
    - `offline`: this record was never network-fetched (`source` is `xml`
      or `none`). On the network path those sources always carry an error
      — `ensure_metadata` sets one whenever the APIs contributed nothing —
      so this branch cannot mislabel a fetched record. "We did not ask" is
      a different fact from "we asked and it failed" (LESSONS #1).
    - `ok`: title and an author, no error.
    """
    if not isinstance(meta, dict):
        return "failed"
    if meta.get("error"):
        salvageable = dict(meta, error=None)
        return "partial" if has_displayable(salvageable) else "failed"
    if meta.get("source") in ("xml", "none", None):
        return "offline"
    return "ok" if has_core_identity(meta) else "partial"


# The 1.1 fields. Key PRESENCE is the test, not truthiness: a paper with no
# journal legitimately carries `journal_normalized: None`.
_V11_FIELDS = ("journal_normalized", "authors_list", "metadata_status")


def needs_enrichment(meta: dict | None) -> bool:
    """The backfill gate: does this record predate schema 1.1?

    Three answers from three states: a missing/unreadable record → True
    (we know nothing; the backfill should visit); a 1.0 record → True
    (any 1.1 field absent); a full 1.1 record → False.
    """
    if not isinstance(meta, dict):
        return True
    return any(key not in meta for key in _V11_FIELDS)


def upgrade_record(meta: dict) -> dict:
    """A 1.0 record with the 1.1 fields derived from what it already holds.

    Zero network cost — journal normalization, the structured author list
    and the status are all computable from the cached fields. The caller
    decides whether to write it back (`ensure_metadata` writes only on the
    fetch path; the scanner's offline path returns it unwritten).
    """
    out = dict(meta)
    out["schema_version"] = SCHEMA_VERSION
    journal = out.get("journal") or None
    if not out.get("journal_normalized"):
        out["journal_normalized"] = (
            normalize_journal_name(journal) if journal else None)
    if not isinstance(out.get("authors_list"), list):
        out["authors_list"] = build_authors_list(out)
    out["metadata_status"] = derive_status(out)
    return out


def _fetch_by_title(title: str) -> dict | None:
    """Title-search cascade, imported lazily: the vendored module is large
    and most calls never need it (papers here almost always have a DOI)."""
    from .fetch_metadata_from_title import fetch_metadata_from_title
    return fetch_metadata_from_title(title)


def _expand_abbreviated_authors(rec: dict) -> dict:
    """Refetch fuller author names when the given names are initials-only.

    Ported from expand_author_names.py: by DOI when there is one, by the
    title-search fallback otherwise, and the answer is kept ONLY when
    `_new_authors_are_better` says it is more complete — a wrong-paper
    match that lost authors, or a same-quality list, changes nothing.
    Any failure returns the record unchanged: a name upgrade must never
    break a fetch or block the schema upgrade.
    """
    if not authors_have_initials(rec):
        return rec
    got = None
    try:
        if rec.get("doi"):
            got = fetch_metadata_from_doi(rec["doi"])
        elif rec.get("title"):
            got = _fetch_by_title(rec["title"])
    except Exception:  # noqa: BLE001 — never fail a review page on a refetch
        return rec
    new_authors = got.get("authors") if isinstance(got, dict) else None
    if not new_authors or not isinstance(new_authors, str):
        return rec
    new_authors = _normalize_to_first_last(new_authors)
    if not _new_authors_are_better(rec.get("authors"), new_authors):
        return rec
    out = dict(rec)
    out["authors"] = new_authors
    out["first_author"] = first_author(new_authors)
    out["authors_list"] = build_authors_list({"authors": new_authors})
    return out


def _with_first_author(meta: dict) -> dict:
    if not meta.get("first_author"):
        meta["first_author"] = first_author(
            meta.get("authors") if isinstance(meta.get("authors"), str)
            else None)
    return meta


def ensure_metadata(paper_dir: Path, *, force: bool = False,
                    network: bool = True) -> dict:
    """Return bibliographic metadata, fetching and caching if needed.

    `network=False` only reads the cache and XML — used by the scanner.
    A failed network fetch is recorded, not silently turned into "no title".
    """
    paper_dir = Path(paper_dir)
    cached = load_cached(paper_dir)
    if cached and not force:
        if not network or not needs_network(cached):
            rec = _with_first_author(dict(cached))
            if not needs_enrichment(rec):
                return rec
            # A 1.0 file upgrades in place on the next fetch. Deriving the
            # 1.1 fields costs no network; the abbreviated-author refetch
            # does, so it runs only on the network path — and exactly once,
            # because the written file is 1.1 and takes the early return
            # above from then on. Offline callers (the scanner) get the
            # upgraded record unwritten: the scanner only reads.
            rec = upgrade_record(rec)
            if network:
                rec = _expand_abbreviated_authors(rec)
                return _write(paper_dir, rec)
            return rec

    doi = doi_of(paper_dir)
    seed = xml_seed(paper_dir)
    if not network:
        if seed:
            rec = _normalise(seed, doi=doi or seed.get("doi"), source="xml")
            return rec
        return cached or _normalise({}, doi=doi, source="none")

    if not doi:
        # The website's fallback: no DOI to ask by, but a title to search
        # for. Kept only when it returns something displayable — the
        # similarity gate lives inside fetch_metadata_from_title.
        no_doi_error = "no DOI on this paper, so the APIs were not asked"
        title = seed.get("title")
        if title:
            try:
                got = _fetch_by_title(str(title))
            except Exception:  # noqa: BLE001 — the fallback must not break the page
                got = None
            if isinstance(got, dict):
                merged = _merge(seed, {k: got.get(k) for k in FIELDS})
                rec = _normalise(merged, doi=got.get("doi") or seed.get("doi"),
                                 source="title_api+xml")
                if has_displayable(rec):
                    return _write(paper_dir, rec)
            no_doi_error = "no DOI on this paper; the title search found nothing"
        rec = _normalise(seed, doi=None, source="xml" if seed else "none",
                         error=no_doi_error)
        return _write(paper_dir, rec)

    error = None
    api: dict = {}
    try:
        got = fetch_metadata_from_doi(doi)
        if isinstance(got, dict):
            api = {k: got.get(k) for k in FIELDS}
        else:
            error = "DOI APIs returned nothing"
    except Exception as exc:  # noqa: BLE001 — never fail a review page on Crossref
        error = f"{type(exc).__name__}: {exc}"

    merged = _merge(seed, api) if seed else dict(api)
    source = "doi_api" if api else ("xml" if seed else "failed")
    if seed and api:
        source = "doi_api+xml"
    if not has_displayable(_normalise(merged, doi=doi, source=source)) and error is None:
        error = "DOI APIs returned no title or authors"
    rec = _normalise(merged, doi=doi, source=source, error=error)
    return _write(paper_dir, rec)


def record_for_run(paper_dir: Path) -> dict:
    """Fetch-and-cache during `analyze_paper`. Never raises.

    A missing title must not cost a paid sweep. Failures are written as
    `error` on `metadata.json` when we got as far as asking, and returned
    either way so a caller can log them.

    Under pytest the network is off: the suite uses fake DOIs
    (`10.1234--x`) and a Crossref round-trip would make every
    `analyze_paper` test pay for a 404.
    """
    try:
        import os
        network = not os.environ.get("PYTEST_CURRENT_TEST")
        return ensure_metadata(Path(paper_dir), network=network)
    except Exception as exc:  # noqa: BLE001
        return {
            "schema_version": SCHEMA_VERSION,
            "error": f"{type(exc).__name__}: {exc}",
            "source": "failed",
            "metadata_status": "failed",
        }


def identity_from_metadata(meta: dict | None) -> dict:
    """The fields `_paper_identity` overlays onto a paper row."""
    if not isinstance(meta, dict):
        return {}
    return {
        "title": meta.get("title"),
        "authors": meta.get("authors"),
        "first_author": meta.get("first_author") or first_author(meta.get("authors")),
        "journal": meta.get("journal"),
        "volume": meta.get("volume"),
        "issue": meta.get("issue"),
        "pages": meta.get("pages"),
        "year": meta.get("year"),
        "doi": meta.get("doi"),
        "url": meta.get("url"),
    }
