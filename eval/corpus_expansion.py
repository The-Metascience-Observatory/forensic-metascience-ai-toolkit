#!/usr/bin/env python
"""Sample candidate papers for the design families this toolkit has never seen.

WHY A SCRIPT AND NOT A HAND-PICKED LIST. `scope.NOT_TESTED` names seven families
with zero representation in the archive. Filling them by hand would reproduce
the problem #135 already names: a corpus assembled by someone who knows what
they are looking for is not a sampling frame, and every accuracy number computed
on it inherits the selection. So the frame is declared here -- one OpenAlex
query per family -- and the draw is SEEDED, so the same command produces the
same list on any machine and a reviewer can regenerate it.

WHAT IT DOES NOT DO. It does not fetch, and it does not judge. It writes CSVs of
DOIs that `fetchpdf --csv ... --make-subfolder --get-xml-or-html
--pull-supplementary` consumes directly (its directory codec is the same as
ours). Whether a sampled paper is usable -- readable PDF, real article rather
than an editorial -- is decided downstream by the extraction gates that already
exist.

TWO BUCKETS, KEPT APART ON PURPOSE (Greg, 2026-08-11).

  `primary/` -- the families this toolkit IS for and has not been tested on.
  These extend the existing evidence base.

  `separate_undertaking/` -- meta-analyses, systematic reviews, and
  meta-analyses OF meta-analyses (umbrella reviews). Auditing these is a
  different project with different tools; they are sampled here so that project
  has a frame ready, NOT so they can be run through the current pipeline. A run
  on one of these will carry `scope.classify_document`'s notice saying so.

Narrative reviews are deliberately NOT sampled. The toolkit is not designed for
them in any version of this plan, so a corpus of them has no use.

Usage:
    python eval/corpus_expansion.py --out eval/corpus_candidates --per-family 25
    python eval/corpus_expansion.py --seed 20260811 --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OPENALEX = "https://api.openalex.org/works"
MAILTO = "greg.s.fitzgerald@gmail.com"

#: The seed is a PARAMETER with a default, never `random.seed()` at import and
#: never the clock. Greg's rule, 2026-08-11: "insofar as we do simulations, we
#: must supply the initial seed for the purposes of reproducibility."
DEFAULT_SEED = 20260811

#: One entry per family in `scope.NOT_TESTED`, plus the separate bucket.
#: `filter` is an OpenAlex filter string; `search` narrows by title/abstract
#: where a topic alone is too broad to be representative of the DESIGN rather
#: than the subject.
FRAMES: tuple[dict, ...] = (
    # ---- primary research, families with zero archive representation ----
    #
    # THE FIRST DRAW OF THESE WAS BAD AND THE FIX IS IN THE FILTERS. Sampling a
    # FIELD gives you the field's subject matter, not its designs: the materials
    # frame returned "A review on polymeric hydrogel membranes" and the
    # single-case frame returned an atmospheric-river model intercomparison,
    # because OpenAlex's plain `search` is relevance over the whole record. The
    # families that are defined by a DESIGN are now anchored on
    # `title_and_abstract.search` with the phrases that design actually uses,
    # which is the paper describing itself -- the same principle as
    # `scope.classify_document`.
    {"bucket": "primary", "key": "qualitative",
     "why": "interviews, focus groups, thematic analysis -- no numbers of the kind "
            "our checks consume, which is exactly why we need to see what the "
            "pipeline does with one",
     "filter": "type:article,open_access.is_oa:true,has_doi:true,"
               "publication_year:2015-2025,"
               'title_and_abstract.search:"semi-structured interviews" AND "thematic analysis"'},
    {"bucket": "primary", "key": "bench_chemistry_materials",
     "why": "replicates vs technical repeats, yields, spectra; no clinical "
            "reporting guideline applies",
     "filter": "type:article,open_access.is_oa:true,has_doi:true,"
               "publication_year:2015-2025,primary_topic.field.id:fields/25,"
               'title_and_abstract.search:"synthesis" AND ("characterization" OR "characterisation")'},
    {"bucket": "primary", "key": "genomics_omics",
     "why": "high-throughput multiplicity is the whole design; our multiplicity "
            "family has never met an FDR over 20,000 tests",
     "filter": "type:article,open_access.is_oa:true,has_doi:true,"
               "publication_year:2015-2025,"
               'title_and_abstract.search:"differentially expressed" AND ("RNA-seq" OR "false discovery rate")'},
    {"bucket": "primary", "key": "economics_polisci",
     "why": "quantitative social science outside psychology: panel data, "
            "instrumental variables, clustered standard errors",
     "filter": "type:article,open_access.is_oa:true,has_doi:true,"
               "publication_year:2015-2025,primary_topic.field.id:fields/20,"
               'title_and_abstract.search:("difference-in-differences" OR "instrumental variable" OR "fixed effects") AND "standard errors"'},
    {"bucket": "primary", "key": "single_case_small_n",
     "why": "N-of-1 and multiple-baseline designs, where group statistics do not "
            "apply and GRIM's n is 1",
     "filter": "type:article,open_access.is_oa:true,has_doi:true,"
               "publication_year:2010-2025,"
               'title_and_abstract.search:"single-case experimental design" OR "multiple baseline design" OR "n-of-1 trial"'},
    {"bucket": "primary", "key": "simulation_modelling",
     "why": "every number is generated rather than measured, so 'impossible' "
            "means something different and the seed IS the method",
     "filter": "type:article,open_access.is_oa:true,has_doi:true,"
               "publication_year:2015-2025,"
               'title_and_abstract.search:"simulation study" AND ("Monte Carlo" OR "data-generating")'},
    # ---- the separate undertaking ----
    {"bucket": "separate_undertaking", "key": "meta_analysis",
     "why": "pooled effects, weights, heterogeneity -- own numbers, different audit",
     "filter": "open_access.is_oa:true,has_doi:true,publication_year:2015-2025,"
               'title_and_abstract.search:"meta-analysis" AND ("random-effects" OR "pooled")'},
    {"bucket": "separate_undertaking", "key": "umbrella_meta_meta",
     "why": "meta-analysis OF meta-analyses -- Greg's 'meta meta-analysis'. The "
            "unit of analysis is another synthesis, so even the meta-analysis "
            "audit does not transfer unchanged",
     "filter": "open_access.is_oa:true,has_doi:true,publication_year:2015-2025,"
               'title_and_abstract.search:"umbrella review" OR "overview of systematic reviews" OR "meta-analysis of meta-analyses"'},
)

#: Titles that announce a synthesis. Excluded from the PRIMARY buckets, where a
#: review is not merely off-target but the very document kind `scope` says this
#: toolkit is not for. Two of the first draw's materials-science picks were
#: reviews typed `article` by OpenAlex, so the type filter alone is not enough.
#:
#: WAS SILENTLY INERT ON ITS FIRST WRITING. The pattern was assembled through a
#: non-raw string and its leading word boundary became a literal BACKSPACE
#: (0x08), so the first alternative required a control character no title
#: contains: the filter matched nothing while looking like it worked, and
#: "A review on polymeric hydrogel membranes" sailed into a bucket of primary
#: research. One raw literal now, pinned by a test carrying that exact title.
_REVIEW_TITLE = re.compile(
    r"\breview\b|\bsurvey\s+(?:of|on)\b|\bmeta[-\s]?anal|\boverview\s+of\b",
    re.I)


def _get(url: str, tries: int = 3) -> dict:
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"fmt-corpus ({MAILTO})"})
            with urllib.request.urlopen(req, timeout=60) as fh:
                return json.loads(fh.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001, PERF203
            last = exc
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"OpenAlex request failed after {tries} tries: {last}")


def sample_frame(frame: dict, n: int, rng: random.Random, pool: int = 200) -> list[dict]:
    """Draw `n` works from a frame, by taking a POOL and sampling it.

    Not `per_page=n`: OpenAlex's default ordering is by relevance/citation, so
    the first n are the famous ones, and a corpus of famous papers is not a
    corpus of ordinary ones. Taking a larger pool and sampling it with the
    supplied seed gives an ordinary draw that is still reproducible.
    """
    params = {"filter": frame["filter"], "per_page": str(min(pool, 200)),
              "mailto": MAILTO, "select": "doi,title,publication_year,type,"
                                          "primary_topic,open_access,language"}
    if frame.get("search"):
        params["search"] = frame["search"]
    data = _get(f"{OPENALEX}?{urllib.parse.urlencode(params)}")
    rows = [r for r in (data.get("results") or []) if r.get("doi")]
    # English only: every extraction gate and every prompt in this repo assumes
    # it, and a non-English paper would be scored as an extraction failure that
    # says more about us than about the paper.
    rows = [r for r in rows if (r.get("language") or "en") == "en"]
    # A review in a PRIMARY bucket is not merely off-target -- it is the exact
    # document kind `scope.OUT_OF_SCOPE` says this toolkit is not for. OpenAlex
    # typed two of the first draw's picks `article` while their titles began
    # "A review on ...", so the type filter alone does not do it.
    if frame["bucket"] == "primary":
        rows = [r for r in rows if not _REVIEW_TITLE.search(r.get("title") or "")]
    total = (data.get("meta") or {}).get("count", 0)
    picked = rows if len(rows) <= n else rng.sample(rows, n)
    out = []
    for r in picked:
        topic = r.get("primary_topic") or {}
        out.append({
            "DOI": str(r["doi"]).replace("https://doi.org/", ""),
            "title": (r.get("title") or "")[:180],
            "year": r.get("publication_year"),
            "openalex_type": r.get("type"),
            "field": ((topic.get("field") or {}).get("display_name") or ""),
            "subfield": ((topic.get("subfield") or {}).get("display_name") or ""),
            "family": frame["key"],
            "bucket": frame["bucket"],
        })
    return out, total, len(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="eval/corpus_candidates",
                    help="directory for the per-bucket CSVs")
    ap.add_argument("--per-family", type=int, default=25)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED,
                    help="draw seed; the same seed reproduces the same list")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the frames and counts, write nothing")
    a = ap.parse_args(argv)

    rng = random.Random(a.seed)
    out_dir = Path(a.out)
    by_bucket: dict[str, list[dict]] = {}
    print(f"seed = {a.seed}   per-family = {a.per_family}\n")
    for frame in FRAMES:
        try:
            rows, total, pool = sample_frame(frame, a.per_family, rng)
        except Exception as exc:  # noqa: BLE001
            print(f"  {frame['key']:<26} FAILED: {exc}")
            continue
        print(f"  {frame['key']:<26} {len(rows):>3} drawn from a pool of {pool:>3} "
              f"(frame holds {total:,})")
        by_bucket.setdefault(frame["bucket"], []).extend(rows)

    if a.dry_run:
        print("\n(dry run -- nothing written)")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    cols = ["DOI", "title", "year", "openalex_type", "field", "subfield",
            "family", "bucket"]
    for bucket, rows in sorted(by_bucket.items()):
        p = out_dir / f"{bucket}.csv"
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {len(rows):>3} rows -> {p}")
    (out_dir / "PROVENANCE.json").write_text(json.dumps({
        "seed": a.seed, "per_family": a.per_family,
        "frames": [{k: f.get(k) for k in ("bucket", "key", "filter", "search", "why")}
                   for f in FRAMES],
        "note": "Regenerate with the same --seed to reproduce this exact draw.",
    }, indent=2), encoding="utf-8")
    print(f"wrote the sampling frame -> {out_dir/'PROVENANCE.json'}")
    print("\nNext: fetchpdf --csv <bucket>.csv -o <dir> --make-subfolder "
          "--get-xml-or-html --pull-supplementary --tracksource --provenance -w 4")
    return 0


if __name__ == "__main__":
    sys.exit(main())
