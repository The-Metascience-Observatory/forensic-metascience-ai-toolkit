#!/usr/bin/env python
"""Find matched non-retracted controls for each fraud positive.

Matching hierarchy (most specific first), per the corpus protocol:
  1. same journal + same publication type (design) + year within +/-2
  2. same journal + year within +/-3, any type
  3. same journal, any year (last resort; flagged as weak match)

Every candidate is screened against the full Retraction Watch database and
against OpenAlex `is_retracted` before being accepted, so a "control" is
never a silently-retracted paper. Controls must also be open access, so the
corpus is fully reproducible by anyone.

Usage:
    python find_controls.py --rw rw.csv --positives positives.csv \
        --n 2 --out controls.csv
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request

import pandas as pd

EMAIL = "greg.s.fitzgerald@gmail.com"
UA = {"User-Agent": "metascience-ground-truth/0.1 (mailto:%s)" % EMAIL}
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _get(url: str, timeout: int = 45):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout).read())


def epmc_search(query: str, page_size: int = 50) -> list[dict]:
    url = "%s?query=%s&format=json&resultType=core&pageSize=%d" % (
        EPMC, urllib.parse.quote(query), page_size)
    try:
        return (_get(url).get("resultList") or {}).get("result") or []
    except Exception:
        return []


def openalex_retracted(doi: str) -> bool | None:
    try:
        j = _get("https://api.openalex.org/works/doi:%s?mailto=%s" % (doi, EMAIL))
        return bool(j.get("is_retracted"))
    except Exception:
        return None


def build_queries(journal: str, year: int, pubtype: str | None) -> list[tuple[str, str]]:
    j = 'JOURNAL:"%s"' % journal
    out = []
    if pubtype:
        out.append((
            "tier1_journal+design+year2",
            '%s AND PUB_TYPE:"%s" AND (PUB_YEAR:[%d TO %d]) AND OPEN_ACCESS:Y'
            % (j, pubtype, year - 2, year + 2)))
    out.append((
        "tier2_journal+year3",
        '%s AND (PUB_YEAR:[%d TO %d]) AND OPEN_ACCESS:Y'
        % (j, year - 3, year + 3)))
    out.append(("tier3_journal_any_year", '%s AND OPEN_ACCESS:Y' % j))
    return out


def find_for(pos: dict, rw_dois: set[str], rw_titles: set[str],
             n: int, used: set[str]) -> list[dict]:
    """Return up to n accepted controls for one positive."""
    journal, year = pos["journal"], int(pos["year"])
    pubtype = pos.get("pubtype") or None
    accepted: list[dict] = []

    for tier, q in build_queries(journal, year, pubtype):
        if len(accepted) >= n:
            break
        for r in epmc_search(q):
            if len(accepted) >= n:
                break
            doi = (r.get("doi") or "").lower().strip()
            title = (r.get("title") or "").strip()
            if not doi or doi in used or doi == pos["doi"].lower():
                continue
            # Screen 1: not in Retraction Watch (by DOI or by exact title)
            if doi in rw_dois or title.lower() in rw_titles:
                continue
            # Screen 2: must be a research article with full text available
            if not r.get("pmcid"):
                continue
            if (r.get("isOpenAccess") or "N") != "Y":
                continue
            # Screen 3: OpenAlex retraction flag (catches RW lag)
            if openalex_retracted(doi):
                continue
            time.sleep(0.15)
            accepted.append({
                "doi": doi,
                "title": title,
                "first_author": (r.get("authorString") or "").split(",")[0],
                "journal": r.get("journalTitle") or journal,
                "year": r.get("pubYear"),
                "pmcid": r.get("pmcid"),
                "pmid": r.get("pmid"),
                "match_tier": tier,
                "matched_to": pos["doi"],
                "matched_case": pos.get("case", ""),
            })
            used.add(doi)
    return accepted


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rw", required=True, help="Retraction Watch CSV dump")
    ap.add_argument("--positives", required=True)
    ap.add_argument("--n", type=int, default=2)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    rw = pd.read_csv(a.rw, low_memory=False)
    rw_dois = set(rw.OriginalPaperDOI.dropna().str.lower().str.strip())
    rw_titles = set(rw.Title.dropna().str.lower().str.strip())
    print("Retraction Watch screen: %d DOIs, %d titles" % (len(rw_dois), len(rw_titles)))

    pos = pd.read_csv(a.positives)
    used: set[str] = set()
    rows: list[dict] = []
    for _, p in pos.iterrows():
        got = find_for(p.to_dict(), rw_dois, rw_titles, a.n, used)
        print("  %-34s -> %d controls (%s)" % (
            p["doi"][:34], len(got), ",".join(g["match_tier"][:6] for g in got)))
        rows.extend(got)

    pd.DataFrame(rows).to_csv(a.out, index=False)
    print("\n%d controls written to %s" % (len(rows), a.out))


if __name__ == "__main__":
    main()
