"""Write benchmarks/grim/SOURCES.md from the labels, Crossref metadata and page titles.

Regenerate after a set or its research records change.
References come from literature_2026-10/sources/references/ (Crossref metadata
and page titles, cached 2026-10-18), so a run makes no network call.

    python benchmarks/grim/make_sources_md.py
"""
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
S = (Path(sys.argv[1]) if len(sys.argv) > 1 else
     REPO / "benchmarks/grim/literature_2026-10/sources/references")
SET = REPO / "benchmarks/grim/literature_2026-10"
labels = [json.loads(line) for line in (SET / "labels.jsonl").read_text().splitlines()
          if line.strip()]
cr = json.loads((S / "crossref_refs.json").read_text())
pages = json.loads((S / "page_titles.json").read_text())

cr["10.1177/1948550616673876"] = {
    "authors": ["Brown, N. J. L.", "Heathers, J. A. J."], "year": 2017,
    "title": "The GRIM Test: A Simple Technique Detects Numerous Anomalies in the "
             "Reporting of Results in Psychology",
    "journal": "Social Psychological and Personality Science", "volume": "8",
    "issue": "4", "page": "363-369"}


def authors(a):
    a = [x for x in a if x]
    if not a:
        return ""
    if len(a) > 6:
        return ", ".join(a[:6]) + ", et al."
    return ", ".join(a[:-1]) + (", & " if len(a) > 1 else "") + a[-1]


def ref(doi):
    m = cr.get(doi) or {}
    if not m or "error" in m:
        return None
    vol = m.get("volume") or ""
    iss = f"({m['issue']})" if m.get("issue") else ""
    pg = f", {m['page']}" if m.get("page") else ""
    jr = f" *{m['journal']}*" if m.get("journal") else ""
    vv = f", {vol}{iss}" if vol else ""
    title = html.unescape(re.sub(r"\s+", " ", m.get("title") or "")).strip().rstrip(".")
    jr = html.unescape(jr)
    who = authors(m.get("authors") or [])
    head = f"{who} ({m.get('year')}). {title}." if who else f"{title} ({m.get('year')})."
    venue = f"{jr}{vv}{pg}."
    return f"{head}{venue if jr else ''} https://doi.org/{doi}"


#: Page titles that are a bot check or a directory listing, not the page's title.
BLOCKED = ("Just a moment", "Cloudflare", "Client Challenge", "Index of", "OSF")
DOI_IN_URL = re.compile(r"(10\.\d{4,9}/[^\s?#]+)")
KNOWN_URL_DOI = {
    "https://bmcnutr.biomedcentral.com/articles/10.1186/s40795-017-0167-x":
        "10.1186/s40795-017-0167-x",
    "https://peerj.com/preprints/3025/": "10.7287/peerj.preprints.3025v1",
    "https://peerj.com/preprints/2748/": "10.7287/peerj.preprints.2748v1",
    "https://journals.sagepub.com/doi/full/10.1177/09567976211058727": "10.1177/09567976211058727",
    "https://onlinelibrary.wiley.com/doi/full/10.1111/joss.12279": "10.1111/joss.12279",
    "https://academic.oup.com/jcr/article/51/2/441/7325344": "10.1093/jcr/ucad055",
}


def source_line(e):
    url = (e.get("url") or "").split(" (read via")[0]
    who = e.get("author") or ""
    kind = e.get("kind") or ""
    doi = KNOWN_URL_DOI.get(url)
    if not doi and "doi.org/" in url:
        m = DOI_IN_URL.search(url)
        doi = m.group(1).rstrip("/") if m else None
    r = ref(doi) if doi else None
    if r:
        return f"[{kind}] {r}"
    who = who.replace("not read, OSF down", "not read at research time: OSF was down")
    who = who.replace("not read: OSF down", "not read at research time: OSF was down")
    p = pages.get(url) or {}
    title = p.get("title")
    if title:
        title = re.sub(r"^Nick Brown's blog: ", "", title)
        title = re.sub(r"\s+[–-]\s+Retraction Watch$", "", title)
    if title and not any(t in title for t in BLOCKED):
        date = f", {p['date']}" if p.get("date") else ""
        return f"[{kind}] {who + ': ' if who else ''}\"{title}\"{date}. {url}"
    return f"[{kind}] {who.rstrip('.')}. {url}" if who else f"[{kind}] {url}"


out = []
w = out.append
w("# GRIM ground truth: sources\n")
w("Every source behind the GRIM ground-truth sets: complete references with links, and "
  "the DOIs of the papers with GRIM issues. Generated 2026-10-18 from each set's "
  "`labels.jsonl`, Crossref metadata and the sources' own pages; a reference without "
  "a DOI is given as author, title, date and URL as the page shows them.\n")
w("Labels are allegations by named third parties, not findings of this toolkit, "
  "and a GRIM inconsistency is a fact about printed numbers, not about anyone's "
  "conduct. What each status and tier means: [README.md](README.md).\n")

w("## Method sources\n")
w(f"- {ref('10.1177/1948550616673876')} (the GRIM test)")
w("- Brown, N. J. L., & Heathers, J. A. J. (2016). The GRIM test: A simple technique "
  "detects numerous anomalies in the reporting of results in psychology. PeerJ "
  "Preprints 4:e2064v1. https://doi.org/10.7287/peerj.preprints.2064v1 ; OSF project "
  "with the GRIM calculator and the list of 260 examined articles: https://osf.io/3fcbr/\n")

# ---- set 1
w("## Set `literature_2026-10`\n")
w("Assembled 2026-10-17 from three literature searches; papers fetched 2026-10-18 into "
  "`agent_for_forensic_metascience_papers/grim_ground_truth/literature_2026-10/`. "
  "Details: [literature_2026-10/README.md](literature_2026-10/README.md).\n")

w("### DOIs of the papers with GRIM issues\n")
w("Papers with at least one `primary` cell (fails GRIM under both rounding conventions "
  "at a printed n, value checked in the paper) are marked **P**.\n")
w("| # | DOI | Primary | Status |")
w("|---|---|---|---|")
for i, p in enumerate(labels, 1):
    prim = sum(c.get("tier") == "primary" for c in p["cells"])
    w(f"| {i} | [{p['doi']}](https://doi.org/{p['doi']}) | "
      f"{'**P** (' + str(prim) + ')' if prim else ''} | `{p['status']}` |")
w("")

w("### Per paper: reference, outcome and sources\n")
for i, p in enumerate(labels, 1):
    tiers = Counter(c.get("tier") for c in p["cells"])
    r = ref(p["doi"]) or f"{p.get('title')}. https://doi.org/{p['doi']}"
    w(f"**{i}. {r}**\n")
    w(f"- Status: `{p['status']}`: {p['status_reason']}.")
    if p.get("outcome"):
        o = re.sub(r"\s+", " ", str(p["outcome"]))
        u = p.get("outcome_url")
        w(f"- Outcome: {o}" + (f" ({u})" if u else ""))
    if p["cells"]:
        w("- Cells: " + ", ".join(f"{n} {t}" for t, n in tiers.most_common()))
    else:
        note = re.sub(r"\s+", " ", str(p.get("cells_not_itemised") or ""))
        if len(note) > 700:
            cut = note[:700].rfind(". ")
            note = note[:cut + 1] + " [...]" if cut > 0 else note[:700] + " [...]"
        w(f"- Cells: none itemised. {note}")
    seen = set()
    lines = []
    for e in p["evidence"]:
        key = (e.get("url") or "").split(" (read via")[0]
        if key in seen:
            continue
        seen.add(key)
        lines.append(source_line(e))
    cell_urls = sorted({(c.get("source_url") or "").split(" (read via")[0]
                        for c in p["cells"]} - seen - {""})
    for u in cell_urls:
        lines.append(source_line({"url": u, "kind": "cell source"}))
    w("- Sources:")
    printed_lines = []
    for line in lines:
        if line not in printed_lines:
            printed_lines.append(line)
            w(f"  - {line}")
    w("")

# ---- set 2
w("## Set `kelly_pcit` (internal)\n")
w("- Kelly, A. J. (2021, revised 2023-03-19). A GRIM Survey of Parent-Child Interaction "
  "Therapy Research. PsyArXiv. https://doi.org/10.31234/osf.io/5m8qf ; preprint page "
  "https://osf.io/preprints/psyarxiv/5m8qf_v1/ ; OSF project https://osf.io/7dvcb/ "
  "(files: the PubMed export of 89 search results, https://osf.io/hyw54/, and the "
  "2021 manuscript, https://osf.io/5knb4/).")
w("- 24 eligible PCIT papers, 17 with at least one inconsistency. The source names no "
  "paper. Tables 2-4 of the 2023 revision itemise 31 means (N, M, outcome) for the four "
  "papers whose authors replied. Of these, 22 were explained by the authors (per-subject "
  "averaging) and 3 more are settled by one paper's own methods (pooled multiple-imputation "
  "values), leaving 6 positives; 4 of them are primary, all in one paper.")
w("- The papers were identified by matching those values against the 89 search results. "
  "Their DOIs are deliberately NOT listed here: Kelly anonymised them, and the set is "
  "internal. They are in "
  "`agent_for_forensic_metascience_papers/grim_ground_truth/kelly_grim/set/`, which "
  "carries an `EMBARGO.json` marker.\n")

# ---- leads
w("## Sources found but not yet mined\n")
w("All OSF items below were public when checked on 2026-10-18; none needs a login.\n")
leads = [
    "Brown & Heathers (2016-2017), GRIM survey files: \"GRIM list of examined articles.xls\" "
    "and the GRIM calculator, https://osf.io/3fcbr/ . The 71 testable articles are "
    "anonymised in the paper; whether the list identifies the inconsistent ones is unchecked.",
    "Brown, N. J. L., & Heathers, J. A. J. (2019). Analysis of articles by Nicolas Guéguen "
    "(\"20190425 NB-JH analysis of Gueguen articles.pdf\") and related documents, "
    "https://osf.io/98nzj/",
    "Yeager, D. S. Re-analysis of descriptive statistics from Mueller & Dweck (1998), "
    "https://osf.io/ngwn8/ (cell list for 10.1037/0022-3514.75.1.33)",
    "Brown, N. J. L. (2019). Reanalysis of Rushton (1992), https://osf.io/4zjba/",
    "Williams, M. N. (2025). EMDR didn't do that: Inconsistent numeric findings in Gauhar "
    "(2016). PsyArXiv. https://doi.org/10.31234/osf.io/6awdf_v1",
    "Impossible Values in Canonical Cognitive Dissonance Studies and their Early "
    "Replications (2026). SocArXiv. https://doi.org/10.31235/osf.io/r8xn9_v1",
    "Vigotsky, A. D., Nuckols, G., Heathers, J., et al. (2020). Improbable data patterns "
    "in the work of Barbalho et al. SportRxiv. https://doi.org/10.31236/osf.io/sg3wm",
    "De Cassai, A., et al. (2024). GRIM audit of erector spinae plane block RCTs. "
    "*Canadian Journal of Anesthesia*, 71, 1323-1324. "
    "https://doi.org/10.1007/s12630-024-02772-8 (266 RCTs, 55 with inconsistent means; "
    "papers and cells only in the eAppendix spreadsheet)",
    "De Cassai, A., et al. (2024). The GRIM Test could be useful in detecting fabricated "
    "data. *Minerva Anestesiologica*, 90, 1160-1161. "
    "https://doi.org/10.23736/S0375-9393.24.18328-9 (articles not named)",
    "Sinomenine rheumatoid-arthritis rodent meta-analysis (2026). *Frontiers in "
    "Pharmacology*. https://doi.org/10.3389/fphar.2026.1800265 (7 of 11 studies flagged; "
    "values in Supplementary Table S4)",
    "Nowbar, A. N., et al. (2014). DAMASCENE. *BMJ*. https://doi.org/10.1136/bmj.g2688 "
    "and Cole, G. D., et al. (2015). *BMJ*. https://doi.org/10.1136/bmj.h4708 "
    "(impossible percentages per trial, in supplementary appendices)",
    "Abouelmagd, M. (2026). Assumptions, Borderline Cases, and Misapplications of the GRIM "
    "Test in Forensic Metascience. Preprints.org. "
    "https://doi.org/10.20944/preprints202607.1945.v1 (misapplication examples; useful "
    "for false-alarm labels)",
    "Gino, F., Schweitzer, M. E., Mead, N. L., & Ariely, D. (2011). *OBHDP*, 115, "
    "191-203. https://doi.org/10.1016/j.obhdp.2011.03.001 , Study 3 (a pilot reports one "
    "GRIM inconsistency, cell unstated; data at https://osf.io/hu3ae/)",
]
for lead in leads:
    w(f"- {lead}")
w("")
(REPO / "benchmarks/grim/SOURCES.md").write_text("\n".join(out) + "\n")
print(len(out), "lines")
