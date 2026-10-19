"""Fetch a paper by DOI into a folder `analyze` can read.

`metascience analyze --doi <DOI> [--run-full-on-everything]` calls `fetch_for_analysis`
before anything is read or spent. It runs the installed `fetchpdf` library --
the same chain its own CLI runs -- for one DOI, into a new folder named by
`paper_ids.doi_dirname` (`10.1186/x` -> `10.1186--x/`):

  * always: the article as publisher XML or full-text HTML AND the PDF
    (`get_xml_or_html`). Which one becomes the review's text is not decided
    here: `_resolve_paper_sources` already prefers XML, then HTML that passes
    `validate_t2`, then the PDF.
  * with `everything`: the supplementary files (`{stem}_supplementary_info_N_*`
    plus a manifest) and the linked data deposits, unpacked, under
    `{stem}_data_artifacts/<deposit>/`.

WHAT WAS OBTAINED IS READ OFF THE DISK, not off fetchpdf's return value, so a
re-run over an existing folder and a fresh fetch describe the folder the same
way. Each channel gets one status:

  obtained       the file(s) are in the folder
  not_obtained   fetchpdf ran and none arrived
  none_listed    the supplementary pass found no listed material
  error          the fetch raised; nothing can be said about the paper
  not_requested  the channel was not asked for (no `--run-full-on-everything`)

`not_obtained` and `none_listed` are FETCH results, never facts about the
paper: a paywalled XML or an unlisted deposit still exists. `limitations()`
says so in those words, and `parallel.py` copies them into the review.

The outcome is written to `fetch.json` in the folder and reaches
`run_meta.fetch`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .paper_ids import doi_dirname

__all__ = [
    "FETCH_RECORD", "FetchError", "FetchResult", "fetch_for_analysis",
    "limitations_from_record", "normalize_doi", "paper_dir_for", "read_record",
]

FETCH_RECORD = "fetch.json"

#: The article channels, in the order the source resolver prefers them.
ARTICLE_CHANNELS = ("xml", "html", "pdf")

_SI_INFIX = "_supplementary_info"
_DOI_PREFIX = re.compile(
    r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)


class FetchError(RuntimeError):
    """The fetch could not be attempted (fetchpdf missing, malformed DOI)."""


def normalize_doi(raw: str) -> str:
    """`https://doi.org/10.1/X` / `doi:10.1/X` / ` 10.1/X ` -> `10.1/X`."""
    doi = _DOI_PREFIX.sub("", str(raw or "").strip()).strip()
    if not re.match(r"^10\.\d{3,}[^/\s]*/\S+$", doi):
        raise FetchError(f"not a DOI: {raw!r} (expected 10.<registrant>/<suffix>)")
    return doi


def paper_dir_for(doi: str, out_dir: str | Path = ".") -> Path:
    """`<out_dir>/<doi_dirname>`: the folder a DOI's files are written to."""
    return Path(out_dir) / doi_dirname(normalize_doi(doi))


def read_record(paper_dir: str | Path) -> dict | None:
    """The folder's `fetch.json`, or None when absent or unreadable."""
    try:
        rec = json.loads((Path(paper_dir) / FETCH_RECORD).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


@dataclass
class FetchResult:
    doi: str
    paper_dir: Path
    reused: bool
    channels: dict[str, dict]
    record: dict = field(default_factory=dict)

    @property
    def has_article(self) -> bool:
        return any(self.channels[c]["status"] == "obtained"
                   for c in ARTICLE_CHANNELS)

    def limitations(self) -> list[str]:
        return limitations_from_record(self.record)


def _load_fetchpdf():
    """The fetchpdf module. A seam: tests replace it."""
    try:
        import fetchpdf
    except ImportError as exc:
        raise FetchError(
            "fetchpdf is not importable in this interpreter, so a DOI cannot "
            "be fetched. It is a base dependency: reinstall the toolkit "
            "(`pip install -e .` in this checkout) or fetch the paper "
            "yourself and pass its folder to `metascience analyze`. "
            f"({exc})") from exc
    return fetchpdf


class _Collector:
    """fetchpdf's `json_out`: it calls `.write(record)` once per DOI."""

    def __init__(self):
        self.records: list[dict] = []

    def write(self, record: dict) -> None:
        self.records.append(record)


def _rel(paper_dir: Path, paths) -> list[str]:
    return [str(Path(p).relative_to(paper_dir)) for p in paths]


def _supplement_files(paper_dir: Path) -> list[Path]:
    return sorted(p for p in paper_dir.iterdir()
                  if p.is_file() and _SI_INFIX in p.name
                  and not p.name.endswith(_SI_INFIX + ".json"))


def _channels(paper_dir: Path, *, everything: bool, raised: str | None,
              si_json: dict | None) -> dict[str, dict]:
    """Each channel's status, read off the folder (module docstring)."""
    from .extraction.html import find_html
    from .extraction.jats import find_pdf, find_xml
    from .supplements import data_artifact_files

    missed = "error" if raised else "not_obtained"
    out: dict[str, dict] = {}
    for name, found in (("xml", find_xml(paper_dir)),
                        ("html", find_html(paper_dir)),
                        ("pdf", find_pdf(paper_dir))):
        out[name] = ({"status": "obtained", "paths": _rel(paper_dir, [found])}
                     if found else {"status": missed, "paths": []})
    landing = sorted(paper_dir.glob("*.landing.html"))
    if out["html"]["status"] != "obtained" and landing:
        out["html"]["detail"] = ("only a publisher landing page was obtained: "
                                 + ", ".join(_rel(paper_dir, landing)))
    if raised:
        for name in ARTICLE_CHANNELS:
            if out[name]["status"] == "error":
                out[name]["detail"] = raised

    si = _supplement_files(paper_dir)
    si_status = (si_json or {}).get("status")
    if si:
        entry = {"status": "obtained", "paths": _rel(paper_dir, si)}
        if si_status in ("partial", "incomplete"):
            entry["fetch_status"] = si_status
            entry["missing_declared"] = list(
                (si_json or {}).get("missing_declared") or [])
    elif not everything:
        entry = {"status": "not_requested", "paths": []}
    elif raised or si_status == "error":
        entry = {"status": "error", "paths": [],
                 **({"detail": raised} if raised else {})}
    elif si_status == "none_found":
        entry = {"status": "none_listed", "paths": []}
    else:
        entry = {"status": "not_obtained", "paths": [],
                 **({"fetch_status": si_status} if si_status else {})}
    out["supplements"] = entry

    data, left_out = data_artifact_files(paper_dir)
    n_all = sum(1 for folder in paper_dir.glob("*_data_artifacts")
                if folder.is_dir() for p in folder.rglob("*") if p.is_file())
    if data or n_all:
        out["datasets"] = {"status": "obtained", "paths": _rel(paper_dir, data),
                           "n_files_downloaded": n_all,
                           "n_left_out_by_cap": left_out}
    else:
        out["datasets"] = {"status": ("not_requested" if not everything
                                      else "error" if raised
                                      else "not_obtained"), "paths": []}
    return out


def _article_on_disk(paper_dir: Path) -> bool:
    from .extraction.html import find_html
    from .extraction.jats import find_pdf, find_xml

    return any(f(paper_dir) for f in (find_xml, find_html, find_pdf))


def fetch_for_analysis(doi: str, out_dir: str | Path = ".", *,
                       everything: bool = False, refetch: bool = False,
                       email: str | None = None,
                       max_supplementary_mb: float | None = None,
                       max_data_mb: float | None = None,
                       verbose: bool = False) -> FetchResult:
    """Fetch `doi` into `paper_dir_for(doi, out_dir)` and describe the result.

    REUSE: a folder that already holds the article -- and, when `everything`
    is asked for, a supplementary manifest or an earlier `everything` fetch --
    is described without touching the network. `refetch` runs fetchpdf again
    anyway; fetchpdf keeps files already on disk and re-checks supplements.
    Never raises for a network failure: that is the `error` status.
    """
    doi = normalize_doi(doi)
    paper_dir = paper_dir_for(doi, out_dir)
    paper_dir.mkdir(parents=True, exist_ok=True)
    prior = read_record(paper_dir) or {}

    si_covered = bool(prior.get("everything")) or any(
        paper_dir.glob(f"*{_SI_INFIX}.json"))
    reused = (not refetch and _article_on_disk(paper_dir)
              and (not everything or si_covered))

    raised = None
    fp_record: dict | None = None
    fp_version = prior.get("fetcher", {}).get("version")
    if reused:
        fp_record = prior.get("fetchpdf_record")
        si_json = (fp_record or {}).get("supplementary")
    else:
        fp = _load_fetchpdf()
        fp_version = getattr(fp, "__version__", None)
        sink = _Collector()
        mb = lambda v: int(v * 1024 * 1024) if v else None  # noqa: E731
        try:
            fp.batch_fetch_pdfs(
                [doi], str(paper_dir), email=email, verbose=verbose,
                workers=1, create_missing_report=False,
                get_xml_or_html=True, want_provenance=True,
                upgrade_existing=refetch,
                pull_supplementary=everything,
                refresh_supplementary=everything and refetch,
                max_supplementary_bytes=mb(max_supplementary_mb),
                download_data_artifacts=everything,
                max_data_artifact_bytes=mb(max_data_mb),
                unpack_data_artifacts=everything,
                json_out=sink)
        except Exception as exc:  # noqa: BLE001 -- recorded, never fatal here
            raised = f"fetchpdf raised {type(exc).__name__}: {exc}"
        fp_record = sink.records[0] if sink.records else None
        si_json = (fp_record or {}).get("supplementary")

    channels = _channels(paper_dir, everything=everything or si_covered,
                         raised=raised, si_json=si_json)
    record = {
        "doi": doi,
        "paper_dir": paper_dir.name,
        "fetched_at": (prior.get("fetched_at") if reused
                       else datetime.now(timezone.utc).isoformat(timespec="seconds")),
        "fetcher": {"name": "fetchpdf", "version": fp_version},
        "everything": bool(everything or (reused and prior.get("everything"))),
        "reused": reused,
        "channels": channels,
        **({"fetchpdf_record": fp_record} if fp_record else {}),
        **({"error": raised} if raised else {}),
    }
    if reused:
        record["described_at"] = datetime.now(timezone.utc).isoformat(
            timespec="seconds")
    (paper_dir / FETCH_RECORD).write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return FetchResult(doi, paper_dir, reused, channels, record)


def limitations_from_record(record: dict | None) -> list[str]:
    """Sentences for the review's Limitations, one per channel that did not
    deliver. Worded as what the FETCH got, never as what the paper lacks."""
    if not record:
        return []
    ch = record.get("channels") or {}
    st = lambda name: (ch.get(name) or {}).get("status")  # noqa: E731
    out: list[str] = []
    if st("xml") != "obtained" and st("html") != "obtained":
        if st("pdf") == "obtained":
            out.append("No publisher XML or full-text HTML was obtained for "
                       "this DOI; the text was read from the PDF, so table "
                       "cells come from PDF extraction rather than markup.")
        else:
            out.append("fetchpdf obtained no copy of the article for this DOI.")
    si = ch.get("supplements") or {}
    if si.get("status") == "none_listed":
        out.append("fetchpdf found no supplementary material listed for this "
                   "DOI. That is a fetch result, not proof the paper has none.")
    elif si.get("status") in ("not_obtained", "error"):
        out.append("Supplementary material was requested but none was "
                   f"obtained ({si.get('status')}); any supplement this paper "
                   "has was not examined.")
    elif si.get("fetch_status") in ("partial", "incomplete"):
        names = ", ".join(si.get("missing_declared") or []) or "unnamed files"
        out.append("Some supplementary files listed for this paper could not "
                   f"be fetched ({si['fetch_status']}): {names}. They were not "
                   "examined.")
    ds = ch.get("datasets") or {}
    if ds.get("status") == "error":
        out.append("The linked-dataset fetch failed; any deposited data were "
                   "not examined.")
    elif ds.get("status") == "not_obtained":
        out.append("No linked data deposit was downloaded for this DOI. That "
                   "is a fetch result, not proof the authors deposited none.")
    if ds.get("n_left_out_by_cap"):
        out.append(f"{ds['n_left_out_by_cap']} file(s) in the linked data "
                   "deposits were beyond the per-review cap and were not "
                   "examined.")
    return out
