#!/usr/bin/env python
"""Fetch open-access full text for ground-truth corpus DOIs.

Legitimate sources only: Unpaywall best-OA-location, Europe PMC / PMC OA,
and publisher OA endpoints (PLOS). Never bypasses a paywall -- if no OA
location exists the DOI is recorded as `paywalled` and nothing is downloaded.

Usage:
    python fetch_paper.py 10.1371/journal.pone.0320595 [more DOIs...]
    python fetch_paper.py --from-manifest ../manifest.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

EMAIL = os.environ.get("UNPAYWALL_EMAIL", "greg.s.fitzgerald@gmail.com")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "papers")
UA = "metascience-ground-truth/0.1 (mailto:%s)" % EMAIL


def slug(doi: str) -> str:
    # Delegated: this function DEFINED the convention, and four other call
    # sites reimplemented it, two of them without the `.lower()`.
    from forensic_metascience_ai_toolkit.paper_ids import doi_dirname
    return doi_dirname(doi)


def _get(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return fh.read()


def _get_json(url: str) -> dict | None:
    try:
        return json.loads(_get(url).decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001 - provenance records the failure
        print("    ! %s -> %s" % (url.split("?")[0], exc), file=sys.stderr)
        return None


def crossref(doi: str) -> dict:
    """Metadata + retraction flag. `update-to` carries retraction notices."""
    j = _get_json("https://api.crossref.org/works/%s?mailto=%s" % (doi, EMAIL))
    if not j:
        return {}
    m = j.get("message", {})
    updates = [
        {"type": u.get("type"), "doi": u.get("DOI"), "label": u.get("label")}
        for u in (m.get("update-to") or [])
    ]
    return {
        "title": (m.get("title") or [""])[0],
        "journal": (m.get("container-title") or [""])[0],
        "year": (m.get("issued", {}).get("date-parts") or [[None]])[0][0],
        "first_author": " ".join(
            filter(None, [(m.get("author") or [{}])[0].get("given"),
                          (m.get("author") or [{}])[0].get("family")])
        ),
        "type": m.get("type"),
        "update_to": updates,
        "is_retracted_crossref": any(
            (u.get("type") or "").lower() in {"retraction", "withdrawal"} for u in updates
        ),
    }


def openalex(doi: str) -> dict:
    j = _get_json("https://api.openalex.org/works/doi:%s?mailto=%s" % (doi, EMAIL))
    if not j:
        return {}
    loc = j.get("best_oa_location") or {}
    return {
        "is_retracted_openalex": j.get("is_retracted"),
        "oa_status": (j.get("open_access") or {}).get("oa_status"),
        "openalex_pdf": loc.get("pdf_url"),
        "openalex_landing": loc.get("landing_page_url"),
        "cited_by_count": j.get("cited_by_count"),
    }


def unpaywall(doi: str) -> dict:
    j = _get_json("https://api.unpaywall.org/v2/%s?email=%s" % (doi, EMAIL))
    if not j:
        return {}
    b = j.get("best_oa_location") or {}
    return {
        "is_oa": j.get("is_oa"),
        "unpaywall_pdf": b.get("url_for_pdf"),
        "unpaywall_landing": b.get("url"),
        "host_type": b.get("host_type"),
        "license": b.get("license"),
    }


def europepmc(doi: str) -> dict:
    j = _get_json(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:"
        + urllib.parse.quote('"%s"' % doi)
        + "&format=json&resultType=core"
    )
    if not j:
        return {}
    hits = (j.get("resultList") or {}).get("result") or []
    if not hits:
        return {}
    r = hits[0]
    urls = [u.get("url") for u in
            ((r.get("fullTextUrlList") or {}).get("fullTextUrl") or [])
            if u.get("documentStyle") == "pdf"]
    return {
        "pmid": r.get("pmid"),
        "pmcid": r.get("pmcid"),
        "is_open_access": r.get("isOpenAccess"),
        "epmc_pdf_urls": urls,
        "epmc_pmc_pdf": (
            "https://europepmc.org/articles/%s?pdf=render" % r["pmcid"]
            if r.get("pmcid") else None
        ),
    }


def candidate_pdfs(doi: str, meta: dict) -> list[str]:
    """Ordered download candidates, most reliable first."""
    out = []
    if doi.startswith("10.1371/"):  # PLOS serves OA PDFs directly
        out.append("https://journals.plos.org/plosone/article/file"
                   "?id=%s&type=printable" % doi)
    for key in ("epmc_pmc_pdf", "unpaywall_pdf", "openalex_pdf"):
        if meta.get(key):
            out.append(meta[key])
    out.extend(meta.get("epmc_pdf_urls") or [])
    seen, uniq = set(), []
    for u in out:
        if u and u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def fetch(doi: str) -> dict:
    doi = doi.strip().lstrip("https://doi.org/").strip()
    d = os.path.join(ROOT, slug(doi))
    os.makedirs(d, exist_ok=True)
    print("[%s]" % doi)

    meta: dict = {"doi": doi, "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
    for fn in (crossref, openalex, unpaywall, europepmc):
        meta.update(fn(doi) or {})
        time.sleep(0.3)

    meta["pdf_candidates"] = candidate_pdfs(doi, meta)
    meta["pdf_path"] = None
    meta["pdf_obtainable"] = "paywalled"

    for url in meta["pdf_candidates"]:
        try:
            blob = _get(url, timeout=90)
        except Exception as exc:  # noqa: BLE001
            print("    ! download failed %s (%s)" % (url[:70], exc))
            continue
        if not blob.startswith(b"%PDF") or len(blob) < 20000:
            print("    ! not a usable PDF: %s (%d bytes)" % (url[:70], len(blob)))
            continue
        path = os.path.join(d, "%s.pdf" % slug(doi))
        with open(path, "wb") as fh:
            fh.write(blob)
        meta.update({"pdf_path": path, "pdf_source_url": url,
                     "pdf_bytes": len(blob), "pdf_obtainable": "yes"})
        print("    + PDF %.1f MB from %s" % (len(blob) / 1e6, url[:70]))
        break
    else:
        print("    - no OA PDF; marked paywalled (NOT bypassed)")

    # Full-text XML from the Europe PMC OA subset. Explicitly licensed for
    # text mining, and better than PDF here: tables arrive structured, so
    # means/SDs/Ns can be read without a PDF table parser.
    meta["xml_path"] = None
    if meta.get("pmcid"):
        try:
            blob = _get("https://www.ebi.ac.uk/europepmc/webservices/rest/"
                        "%s/fullTextXML" % meta["pmcid"], timeout=60)
            if b"<article" in blob[:4000]:
                path = os.path.join(d, "%s.xml" % slug(doi))
                with open(path, "wb") as fh:
                    fh.write(blob)
                meta["xml_path"] = path
                meta["xml_tables"] = blob.count(b"<table-wrap")
                print("    + XML %d kB (%d tables)"
                      % (len(blob) / 1000, meta["xml_tables"]))
        except Exception:
            pass  # not in the OA subset; provenance records xml_path=None

    # Free-to-read PMC author manuscripts are readable in a browser but are
    # NOT in the text-mineable OA subset, so we do not scrape them.
    if meta["pdf_obtainable"] == "paywalled" and meta.get("pmcid"):
        meta["pdf_obtainable"] = "manual_only"
        meta["manual_url"] = ("https://pmc.ncbi.nlm.nih.gov/articles/%s/"
                              % meta["pmcid"])
        print("    ~ free to read at %s but not in the OA text-mining subset;"
              " retrieve manually" % meta["manual_url"])

    with open(os.path.join(d, "provenance.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    return meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dois", nargs="*")
    ap.add_argument("--from-manifest")
    a = ap.parse_args()

    dois = list(a.dois)
    if a.from_manifest:
        with open(a.from_manifest) as fh:
            dois += [r["doi"] for r in csv.DictReader(fh)
                     if r.get("doi") and not r["doi"].startswith("#")]

    results = [fetch(d) for d in dois]
    got = sum(1 for r in results if r.get("pdf_obtainable") == "yes")
    print("\n%d/%d PDFs obtained legitimately" % (got, len(results)))


if __name__ == "__main__":
    main()
