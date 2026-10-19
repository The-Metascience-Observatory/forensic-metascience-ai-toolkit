"""Write benchmarks/grim/VERIFIED.md: the papers with verified GRIM errors.

Regenerate after labels change (a rebuild, a re-verification, a manual
check). Reads the internal kelly_pcit labels from the sibling corpus folder
but writes no identity from them.
References come from literature_2026-10/sources/references/ (Crossref metadata
and page titles, cached 2026-10-18), so a run makes no network call.

    python benchmarks/grim/make_verified_md.py
"""
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GT = REPO.parent / "agent_for_forensic_metascience_papers" / "grim_ground_truth"
S = (Path(sys.argv[1]) if len(sys.argv) > 1 else
     REPO / "benchmarks/grim/literature_2026-10/sources/references")


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


lit = load(REPO / "benchmarks/grim/literature_2026-10/labels.jsonl")
kel = load(GT / "kelly_grim/set/labels.jsonl")
cr = json.loads((S / "crossref_refs.json").read_text())
splits = json.loads((REPO / "benchmarks/grim/literature_2026-10/splits.json").read_text())
SPLIT_OF = {pid: name for name in ("dev", "holdout") for pid in splits[name]}

STATUS_TEXT = {
    "confirmed_error": "confirmed by a correction, retraction notice or the authors' data",
    "journal_action": "an expression of concern or retraction cites the problems",
    "published_critique": "peer-reviewed or preprint critique only",
    "unresolved_concern": "blog post or PubPeer comment only",
}


def ref(doi):
    m = cr.get(doi) or {}
    if not m or "error" in m:
        return f"https://doi.org/{doi}"
    a = [x for x in m.get("authors") or [] if x]
    if len(a) > 6:
        who = ", ".join(a[:6]) + ", et al."
    elif len(a) > 1:
        who = ", ".join(a[:-1]) + ", & " + a[-1]
    else:
        who = a[0] if a else ""
    title = html.unescape(re.sub(r"\s+", " ", m.get("title") or "")).strip().rstrip(".")
    jr = html.unescape(m.get("journal") or "")
    vol = f", {m['volume']}" if m.get("volume") else ""
    iss = f"({m['issue']})" if m.get("issue") else ""
    pg = f", {m['page']}" if m.get("page") else ""
    return f"{who} ({m.get('year')}). {title}. *{jr}*{vol}{iss}{pg}. https://doi.org/{doi}"


def verified(p):
    return (any(c["tier"] == "primary" and c["value_verified"] for c in p["cells"])
            or bool(p.get("paper_verified")))


vlit = [p for p in lit if verified(p)]
vkel = [p for p in kel if verified(p)]
nlit = [p for p in lit if not verified(p)]
prim_cells = sum(c["tier"] == "primary" and c["value_verified"]
                 for p in vlit + vkel for c in p["cells"])
by_status = Counter(p["status"] for p in vlit + vkel)

out = []
w = out.append
w("# GRIM ground truth: verified papers\n")
w(f"**{len(vlit) + len(vkel)} papers with verified GRIM errors** ({len(vlit)} in "
  f"`literature_2026-10`, {len(vkel)} in the internal `kelly_pcit` set), holding "
  f"{prim_cells} verified failing values. In the corpus folder "
  "`agent_for_forensic_metascience_papers/grim_ground_truth/`, the literature set's 20 are "
  "split 10/10 into `literature_2026-10/verified_dev/` and `verified_holdout/` "
  "(`literature_2026-10/splits.json`), and the Kelly paper is in `kelly_grim/verified/`. "
  "Built 2026-10-17 and 2026-10-18; every claim below traces to `labels.jsonl` and the "
  "set's `build_labels.py`.\n")
w("A GRIM error here is a fact about printed numbers: the paper prints a mean or "
  "percentage that no set of whole-number observations at the paper's own n can produce. "
  "It is not a finding about anyone's conduct. Where the cause came out, it was usually a "
  "misreported n, not a wrong mean.\n")

w("## What \"verified\" means\n")
w("A paper is verified when at least one labelled value passes all four checks, or a "
  "paper-level proof stands (Banerjee 2012, below):\n")
w("1. **Arithmetic.** It fails GRIM under both round-half and truncation, recomputed with "
  "the toolkit's own functions (`verify_labels.classify`). A value that fails only "
  "round-half is not counted: the tool treats truncation as a legitimate convention.")
w("2. **A printed n.** The n is printed in the paper, not borrowed from another paper, "
  "assumed, or derived from degrees of freedom.")
w("3. **Whole-number data.** The paper's own description makes the observations integers "
  "(counts, single-item ratings, totals of integer items), not averages, model estimates "
  "or imputed values.")
w("4. **The value is in the paper.** Found in the paper's text (XML incl. tables, or "
  "`pdftotext`), or read by eye where the text layer is garbled; short values were "
  "also checked at their labelled row and column.\n")
w("The labels came from third parties (critiques, journal notices, PubPeer, Kelly's "
  "survey); checks 1-4 were done here. Strength of the third-party evidence:\n")
w("| Evidence | Papers |")
w("|---|---|")
for k in ("confirmed_error", "journal_action", "published_critique", "unresolved_concern"):
    w(f"| `{k}`: {STATUS_TEXT[k]} | {by_status.get(k, 0)} |")
w("")

w("## How the set was built\n")
w("1. **Search (2026-10-17).** Three literature searches: Wansink's Cornell lab "
  "(\"Statistical heartburn\", Anaya, van der Zee); Brown, Heathers and Anaya's own "
  "cases and journal notices; PubPeer threads and published audits. Each value was "
  "copied from a named source with its URL (`literature_2026-10/sources/`).")
w("2. **Arithmetic and tiers.** Every cell recomputed under both conventions and tiered "
  "(`primary`, `rounding_only`, `inferred_n`, `doubtful_premise`, `excluded`, "
  "`false_alarm`).")
w("3. **Papers fetched (2026-10-18)** with fetchpdf2; each matched its label's title. "
  "262 of 279 values found automatically in the text; 15 more read by eye where the "
  "text layer garbles them; 2 not in the paper at all (excluded).")
w("4. **Manual confirmation (2026-10-18).** Every paper whose label rested on an "
  "unconfirmed premise was read for it. Outcomes in the table at the end and in each "
  "paper's `manual_check`.")
w("5. **Kelly's PCIT survey (internal).** Kelly's 2023 revision itemises 31 flagged means "
  "for four anonymised papers; they were identified by matching (N, mean) values against "
  "Kelly's 89 search results. 25 of the 31 turned out to be false alarms. Kept outside "
  "git under an embargo marker.\n")

w("## Dev and holdout\n")
w(f"The 20 literature papers are split 10/10 at random (seed {splits['seed']}), keeping "
  "papers that share data on the same side: the four Wansink pizza papers (one dataset) "
  "and the two Strauer stem-cell trials (overlapping patients). "
  f"{splits['rule']} Score a split with `score.py --split dev`.\n")
def _cells(p):
    return sum(c["tier"] == "primary" and c["value_verified"] for c in p["cells"])


for name in ("dev", "holdout"):
    members = [p for p in vlit if SPLIT_OF[p["paper_id"]] == name]
    scorable = [p for p in members if _cells(p)]
    biggest = max(members, key=_cells)
    w(f"- **{name}**: {len(members)} papers ({len(scorable)} with scorable values), "
      f"{sum(_cells(p) for p in members)} verified values; the largest is "
      f"{biggest['doi']} with {_cells(biggest)}")
w("\nA paper verified only at paper level has no scorable value. The split was not "
  "re-drawn to even out the halves: choosing among draws would spend the holdout.\n")
w("## The verified papers\n")
for i, p in enumerate(vlit, 1):
    prim = [c for c in p["cells"] if c["tier"] == "primary" and c["value_verified"]]
    w(f"### {i}. {ref(p['doi'])}\n")
    w(f"- Split: **{SPLIT_OF[p['paper_id']]}**")
    w(f"- Evidence: `{p['status']}`: {p['status_reason']}.")
    if p.get("outcome"):
        outcome = re.sub(r"\s+", " ", str(p["outcome"]))
        w(f"- Outcome: {outcome}")
    if p.get("paper_verified"):
        w(f"- **Verified at paper level:** {p['paper_verified']}")
    if prim:
        tables = Counter(re.split(r",", c["location"] or "")[0].strip() for c in prim)
        how = Counter(c.get("value_verified_by") or "text" for c in prim)
        w(f"- Verified values: {len(prim)} ("
          + ", ".join(f"{n} in {t}" for t, n in tables.most_common(4))
          + ("; ..." if len(tables) > 4 else "") + "); value check: "
          + ", ".join(f"{n} by {k}" for k, n in how.items()) + ".")
        show = prim if len(prim) <= 8 else prim[:6]
        for c in show:
            w(f"  - {c['value']}{'%' if c['kind'] == 'percentage' else ''} at n = {c['n']}"
              f"{' x ' + str(c['items_k']) + ' items' if c.get('items_k', 1) > 1 else ''}"
              f" ({c['location']})")
        if len(prim) > len(show):
            w(f"  - ... and {len(prim) - len(show)} more in `labels.jsonl`")
    if p.get("manual_check"):
        w(f"- Manual check: {p['manual_check']}")
    w("")
for p in vkel:
    prim = [c for c in p["cells"] if c["tier"] == "primary" and c["value_verified"]]
    w(f"### {len(vlit) + 1}. Internal: Kelly's Paper {p['kelly_paper']} (`kelly_pcit`)\n")
    w("- Identity withheld: Kelly anonymised the papers, and the set is internal. See "
      "`grim_ground_truth/kelly_grim/set/README.md`.")
    w(f"- Evidence: `{p['status']}`: {p['status_reason']}.")
    w(f"- Verified values: {len(prim)}, totals of integer items at n printed per column "
      "in the paper's Table 1.\n")

w("## Not verified, and why\n")
w("| Paper | Why not |")
w("|---|---|")
for p in nlit:
    why = p.get("manual_check")
    if not why:
        tiers = Counter(c["tier"] for c in p["cells"])
        if not p["cells"]:
            why = "no failing values itemised in any source we could read"
        else:
            why = "cells are " + ", ".join(f"{n} {t}" for t, n in tiers.most_common())
    w(f"| [{p['doi']}](https://doi.org/{p['doi']}) | {why} |")
for p in kel:
    if verified(p):
        continue
    kelly_why = {
        "1": "its one positive, 29.35 at N = 90, fails only round-half, and the paper's other "
             "raw-score means cannot show whether the authors rounded or truncated; its other "
             "flag (5.65) is a false alarm",
        "3": "all 11 flags are false alarms: the authors confirmed per-subject subscale averaging",
        "4": "all 13 flags are false alarms: 10 explained by the authors (averaging), 3 settled "
             "by the paper's own methods (pooled multiple-imputation values)",
    }
    w(f"| Kelly Paper {p['kelly_paper']} (internal) | {kelly_why[p['kelly_paper']]} |")
w("")
w("## False alarms\n")
fa = sum(c["tier"] == "false_alarm" for p in kel for c in p["cells"])
w(f"`kelly_pcit` holds {fa} `false_alarm` cells: means a critic flagged that are not "
  "errors. 22 were explained by the authors as per-subject averages of a subscale; 3 more "
  "are pooled multiple-imputation values, as the paper itself says. A tool that flags "
  "them is wrong; the scorer counts those flags separately.\n")
(REPO / "benchmarks/grim/VERIFIED.md").write_text("\n".join(out) + "\n")
print(len(vlit) + len(vkel), "verified;", prim_cells, "cells;", len(out), "lines")
