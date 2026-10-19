#!/usr/bin/env python
"""Build eval/ground_truth/manifest.csv.

Bibliographic fields come from provenance.json (Crossref/OpenAlex/Europe PMC).
The judgement fields -- how the fraud was established, which tools a case can
and cannot validate, and whether a statistical signature is even expected --
are hand-curated below with a cited source for every determination.

Curation rules (see ground_truth_corpus_protocol.md):
  * how_established records the route by which fraud was determined. A case
    can only validate tools that were NOT used to find it.
  * expected_statistical_signature is `none` whenever the misconduct leaves
    no numeric trace (image manipulation, ethics breach, provenance error).
    A "miss" on those is correct behaviour, not a false negative.
  * Anything not backed by an institutional finding, confession, conviction
    or raw-data audit is labelled `contested` and excluded from the primary
    sensitivity denominator.
"""

from __future__ import annotations

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PAPERS = os.path.join(HERE, "..", "papers")
OUT = os.path.join(HERE, "..", "manifest.csv")

ALL = "grim,grimmer,sprite,debit,statcheck,baseline_similarity,digit_preference,duplication"

# --------------------------------------------------------------------------
# Case-level curation. Keyed by DOI (lowercase).
# --------------------------------------------------------------------------
FRAUD: dict[str, dict] = {}


def case(dois, **kw):
    for d in dois:
        FRAUD[d.lower()] = dict(kw)


# --- ORI / federal findings: the strongest evidence class ------------------
case(["10.1038/nature13375"],
     case_name="Wan (ORI 2018)",
     retraction_reason="falsification: means/SDs reported at n=6-8 were computed from n=3",
     how_established="investigation",
     detecting_method_if_any="ORI investigation of primary records",
     expected_statistical_signature="sprite|grimmer",
     can_validate_tools=ALL,
     cannot_validate_tools="",
     notes="ORI finding states the declared N and the true N, so this is a rare case "
           "with a QUANTIFIED ground-truth discrepancy. Prime SPRITE positive. "
           "Falsified values sit in FIGURE PANELS, so a markdown/text-only pipeline "
           "may be structurally unable to see them -- score figure-blindness separately. "
           "Source: ORI case summary / Federal Register findings of research misconduct.")

case(["10.1016/j.cell.2016.10.023", "10.1073/pnas.1505035112"],
     case_name="Skau (ORI)",
     retraction_reason="falsification: significance claimed for a non-significant t test; "
                       "SD/SEM mislabelled; N reported larger than N collected",
     how_established="investigation",
     detecting_method_if_any="ORI investigation of primary records",
     expected_statistical_signature="statcheck|sprite|grimmer",
     can_validate_tools=ALL,
     cannot_validate_tools="",
     notes="ORI notice names the true Ns and the SD-vs-SEM mislabel explicitly, giving "
           "exact ground truth for an N-consistency and a dispersion-type check. "
           "Only case in the corpus with a documented SD/SEM mislabel.")

case(["10.1523/jneurosci.4125-10.2011", "10.1037/a0030094",
      "10.3758/s13414-012-0292-1", "10.1177/0956797612464380"],
     case_name="Anderson (ORI 2015, U. Oregon)",
     retraction_reason="falsification: outliers removed or replaced with mean values "
                       "to conform to predictions",
     how_established="investigation",
     detecting_method_if_any="ORI investigation",
     expected_statistical_signature="sprite",
     can_validate_tools=ALL,
     cannot_validate_tools="",
     notes="Mechanism matters: replacing outliers with the mean SHRINKS THE SD and leaves "
           "the mean unchanged. GRIM should NOT fire; a variance-plausibility/SPRITE check "
           "should. Treat a GRIM miss here as correct behaviour. "
           "Source: Federal Register 2015-18794, findings of research misconduct.")

case(["10.1016/j.jagp.2020.11.001", "10.1016/j.jagp.2021.01.004"],
     case_name="Rutherford (ORI)",
     retraction_reason="NOT RETRACTED -- erratum only, despite an ORI misconduct finding: "
                       "falsely reported that all subjects met inclusion/exclusion criteria",
     how_established="investigation",
     detecting_method_if_any="ORI investigation",
     expected_statistical_signature="grim|grimmer|statcheck",
     can_validate_tools=ALL,
     cannot_validate_tools="",
     notes="Highest-value item: federally adjudicated falsification in papers that are "
           "STILL LIVE in the literature (erratum only). 24-item HRSD is an integer sum "
           "so GRIM applies directly; 1-7 Likert credibility scale; APA-format test "
           "statistics are statcheck-parseable. ORI gives exact ratios of ineligible "
           "subjects (15/47, 30/108, 18/71).")

case(["10.7554/elife.59709"],
     case_name="Hwa (ORI 2023)",
     retraction_reason="falsification of sample size by duplicating four data points",
     how_established="investigation",
     detecting_method_if_any="ORI investigation",
     expected_statistical_signature="duplication",
     can_validate_tools=ALL,
     cannot_validate_tools="",
     notes="Duplication-detector target with a known count (4 duplicated points). "
           "eLife publishes source data, so the raw values are checkable.")

# --- Criminal conviction: independent of every statistical method ----------
case(["10.1097/00000542-200603000-00006"],
     case_name="Reuben (criminal conviction 2010)",
     retraction_reason="fabrication: the studies were never conducted; no patients existed",
     how_established="confession",
     detecting_method_if_any="guilty plea to health care fraud, 18 U.S.C. 1347; FDA debarment",
     expected_statistical_signature="grim|grimmer|sprite|statcheck|baseline_similarity|digit_preference",
     can_validate_tools=ALL,
     cannot_validate_tools="",
     notes="Cleanest possible positive: every number is invented and this is established "
           "by criminal conviction, wholly independent of all statistical methods. VAS/NRS "
           "pain scores on bounded integer scales with small N are textbook GRIM/SPRITE "
           "territory. Source: Scott S. Reuben Debarment Order, 76 FR 71042 (2011-11-16).")

# --- Institutional investigations -----------------------------------------
case(["10.1007/s11031-011-9216-y"],
     case_name="Stapel (confessed; Levelt/Noort/Drenth 2012)",
     retraction_reason="fabrication of data",
     how_established="confession",
     detecting_method_if_any="confession corroborated by university committee",
     expected_statistical_signature="duplication|sprite",
     can_validate_tools=ALL,
     cannot_validate_tools="",
     notes="Stapel confessed, so the determination is independent of every statistical "
           "method -- the single most valuable evidence class. CAVEAT: he fabricated whole "
           "datasets from target means, so the reported statistics are often INTERNALLY "
           "CONSISTENT and GRIM/GRIMMER/SPRITE may correctly return clean. The committee's "
           "recurring signatures were duplicated M/SD cells and implausibly clean variance, "
           "not granularity. Source: 'Flawed science', Levelt/Noort/Drenth final report, "
           "28 Nov 2012, per-paper evidence in Appendices 4-6.")

case(["10.3389/fpsyg.2016.01298"],
     case_name="Wansink (Cornell 2018; Frontiers raw-data audit)",
     retraction_reason="no empirical support for the conclusions, per an independent "
                       "expert assessment of the raw data",
     how_established="raw_data_audit",
     detecting_method_if_any="independent expert audit of raw data commissioned by Frontiers",
     expected_statistical_signature="grim|grimmer|statcheck",
     can_validate_tools=ALL,
     cannot_validate_tools="",
     notes="NON-CIRCULAR Wansink paper -- unlike the pizza papers, this one was established "
           "by a raw-data audit, not by GRIM. Usable to validate GRIM. Cornell's 2018 finding "
           "was 'misreporting of research data and problematic statistical techniques', NOT "
           "fabrication; Wansink disputed the retractions. Reports M/SD/N and F tests.")

case(["10.1016/j.curtheres.2004.06.002", "10.1016/j.curtheres.2003.08.009"],
     case_name="Fujii (Japanese Society of Anesthesiologists 2012)",
     retraction_reason="falsification/fabrication of data",
     how_established="investigation",
     detecting_method_if_any="JSA committee: records/feasibility evidence and forged "
                             "co-author signatures (NOT baseline statistics)",
     expected_statistical_signature="grim|baseline_similarity|statcheck|digit_preference",
     can_validate_tools="grim,grimmer,sprite,debit,statcheck,digit_preference,duplication",
     cannot_validate_tools="baseline_similarity",
     notes="Carlisle 2012's baseline analysis TRIGGERED the inquiry, so baseline-similarity "
           "is circular here. But the JSA committee adjudicated on unverifiable subject "
           "counts, absent ethics committees and forged signatures -- independent of GRIM/"
           "SPRITE/statcheck, which those tools can therefore be validated against. "
           "Complete-response percentages with small integer denominators suit GRIM. "
           "Source: JSA Investigation Committee report, 2012-10-19.")

case(["10.3349/ymj.2009.50.4.474", "10.3349/ymj.2005.46.6.750",
      "10.3349/ymj.2008.49.1.119", "10.2147/tcrm.s15812", "10.2147/tcrm.s43811",
      "10.5312/wjo.v4.i4.316", "10.1136/jnnp.66.1.64", "10.1155/2013/381616"],
     case_name="Sato (Kurume finding; Bolland et al. reanalysis)",
     retraction_reason="misconduct by author; concerns about data; forged authorship",
     how_established="statistical_detection",
     detecting_method_if_any="Bolland/Avenell/Gamble/Grey baseline-distribution and "
                             "allocation-ratio analysis, Neurology 2016",
     expected_statistical_signature="baseline_similarity|grim|duplication",
     can_validate_tools="grim,grimmer,sprite,debit,statcheck,digit_preference,duplication",
     cannot_validate_tools="baseline_similarity",
     notes="CIRCULAR for baseline-similarity: that is exactly the method that found it. "
           "Anchored independently by a Kurume University misconduct finding and by "
           "forged-authorship determinations, so it remains usable for GRIM/SPRITE/statcheck. "
           "Outcome tables (fracture counts with denominators) are the non-circular surface. "
           "Source: Bolland et al., Neurology 2016;87:2391-2402.")

case(["10.1073/pnas.1209746109"],
     case_name="Shu/Gino/Ariely (Data Colada; Harvard ORI finding)",
     retraction_reason="evidence questioning the validity of the data",
     how_established="raw_data_audit",
     detecting_method_if_any="file forensics: Calibri/Cambria font split, duplicate row "
                             "twins, Excel calcChain row movement (Data Colada 98/109)",
     expected_statistical_signature="none",
     can_validate_tools=ALL,
     cannot_validate_tools="",
     notes="FALSE-NEGATIVE BENCHMARK. Every documented signature is file-level or raw-data "
           "level; none is a GRIM/GRIMMER/SPRITE/statcheck signature. A clean report here is "
           "the CORRECT result and is evidence that the summary-statistic layer needs a "
           "file-forensic layer beside it. Corroborated by Harvard's misconduct finding "
           "(Gino's tenure revoked 2024). DISPUTED: Gino is in ongoing litigation against "
           "Harvard and Data Colada; the insurance dataset was supplied by Ariely.")

case(["10.1073/pnas.0806674105", "10.1371/journal.pone.0001908"],
     case_name="Potti (Duke investigation; ORI 2015)",
     retraction_reason="results not reproducible; misconduct by author",
     how_established="raw_data_audit",
     detecting_method_if_any="Baggerly & Coombes forensic bioinformatics: off-by-one row "
                             "shift, sensitive/resistant label reversal, duplicated samples",
     expected_statistical_signature="none",
     can_validate_tools=ALL,
     cannot_validate_tools="",
     notes="NEGATIVE CONTROL / EXTRACTION-HALLUCINATION CANARY. Text-mining these papers "
           "yields 0 parseable test statistics, 0 mean+/-SD pairs and 0 GRIM-eligible means "
           "against ~16 bare p-values -- the input preconditions for GRIM/SPRITE/statcheck "
           "are UNSATISFIABLE on this document class. Any non-empty GRIM/SPRITE output here "
           "is a hallucinated extraction, not a detection. Source: Baggerly & Coombes, "
           "Ann Appl Stat 2009;3:1309-1334; IOM report doi:10.17226/13297 App. B.")

case(["10.1038/srep12770"],
     case_name="Colzato GABA RCT",
     retraction_reason="undisclosed participant exclusions",
     how_established="investigation",
     detecting_method_if_any="institutional/journal investigation",
     expected_statistical_signature="grim|grimmer|statcheck",
     can_validate_tools=ALL,
     cannot_validate_tools="",
     notes="Reported N does not match analysed N (16 undisclosed exclusions), so reported "
           "means may be inconsistent with the stated denominator -- a GRIM-shaped signature.")

case(["10.3389/fpsyg.2022.799103"],
     case_name="Swimmers RCT (author admission)",
     retraction_reason="authors admitted generating the figure data",
     how_established="confession",
     detecting_method_if_any="author admission",
     expected_statistical_signature="sprite|grimmer",
     can_validate_tools=ALL,
     cannot_validate_tools="",
     notes="Confession-backed, therefore non-circular for every tool. Fabricated values are "
           "in figures, so figure-blindness applies.")

case(["10.1371/journal.pone.0128753"],
     case_name="MD Anderson genotype duplication",
     retraction_reason="117 controls and 4 cases carried identical genotypes",
     how_established="raw_data_audit",
     detecting_method_if_any="data audit",
     expected_statistical_signature="duplication",
     can_validate_tools=ALL,
     cannot_validate_tools="",
     notes="Duplication-detector positive with a known count. 7 tables in the XML.")

case(["10.1371/journal.pone.0320595"],
     case_name="Sugira Muryango spillover (CONTESTED)",
     retraction_reason="data published without the data owner's permission; plus reported "
                       "N=247 against an outcome measured on 57 and analysed on 44; "
                       "imputation unverifiable; clustering not adjusted",
     how_established="raw_data_audit",
     detecting_method_if_any="co-author comparison against the primary research records",
     expected_statistical_signature="grim|grimmer",
     can_validate_tools=ALL,
     cannot_validate_tools="",
     notes="CONTESTED and NOT established fabrication. The retraction is driven primarily by "
           "unauthorised data use (an authorship/permission dispute); the corresponding "
           "author concedes a sample-size error but maintains the conclusions hold. Label it "
           "'misreporting', never 'fraud'. Still a genuine positive control for an "
           "N-consistency check: means reported against N=247 were computed on n=44. "
           "Source: retraction notice 10.1371/journal.pone.0327838.")


def main() -> None:
    rows = []
    for d in sorted(os.listdir(PAPERS)):
        pj = os.path.join(PAPERS, d, "provenance.json")
        if not os.path.exists(pj):
            continue
        m = json.load(open(pj))
        doi = (m.get("doi") or "").lower()
        f = FRAUD.get(doi)
        retracted = bool(m.get("is_retracted_crossref") or m.get("is_retracted_openalex"))

        if f:
            row = dict(
                label="fraud",
                retraction_status=("retracted" if retracted
                                   else "not_retracted_but_misconduct_finding"),
                retraction_reason=f["retraction_reason"],
                how_established=f["how_established"],
                detecting_method_if_any=f["detecting_method_if_any"],
                expected_statistical_signature=f["expected_statistical_signature"],
                can_validate_tools=f["can_validate_tools"],
                cannot_validate_tools=f["cannot_validate_tools"],
                notes="[%s] %s" % (f["case_name"], f["notes"]),
            )
        else:
            row = dict(
                label="control",
                retraction_status="not_retracted",
                retraction_reason="",
                how_established="",
                detecting_method_if_any="",
                expected_statistical_signature="none",
                can_validate_tools=ALL,
                cannot_validate_tools="",
                notes="Matched control: same journal, nearest available year and design, "
                      "screened against the full Retraction Watch database (71,315 records) "
                      "and against the OpenAlex is_retracted flag. Used for specificity.",
            )
            if retracted:  # safety net; should never fire
                row["label"] = "EXCLUDE_retracted_control"
                row["retraction_status"] = "retracted"

        src = (m.get("pdf_source_url") or m.get("manual_url")
               or m.get("unpaywall_landing") or "https://doi.org/%s" % m.get("doi", ""))
        rows.append({
            "doi": m.get("doi"),
            "title": (m.get("title") or "").replace("\n", " ").strip(),
            "first_author": m.get("first_author") or "",
            "journal": m.get("journal") or "",
            "year": m.get("year") or "",
            "pdf_obtainable": m.get("pdf_obtainable") or "no",
            "has_fulltext_xml": "yes" if m.get("xml_path") else "no",
            "xml_tables": m.get("xml_tables", 0),
            "pmcid": m.get("pmcid") or "",
            "source_url": src,
            **row,
        })

    cols = ["doi", "title", "first_author", "journal", "year", "label",
            "retraction_status", "retraction_reason", "how_established",
            "detecting_method_if_any", "expected_statistical_signature",
            "can_validate_tools", "cannot_validate_tools", "pdf_obtainable",
            "has_fulltext_xml", "xml_tables", "pmcid", "source_url", "notes"]
    rows.sort(key=lambda r: (r["label"] != "fraud", r["journal"], str(r["year"])))
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    n_f = sum(1 for r in rows if r["label"] == "fraud")
    print("manifest.csv: %d rows (%d fraud, %d control)" % (len(rows), n_f, len(rows) - n_f))
    unmatched = set(FRAUD) - {r["doi"].lower() for r in rows}
    if unmatched:
        print("WARNING curated but not on disk:", unmatched)


if __name__ == "__main__":
    main()
