"""Build the deterministic p-tool benchmark cases from human-labelled statistics.

Every case is ONE printed test statistic with its reported p, as a human coder
judged it: `label` is "error" (the printed p does not follow from the printed
statistic) or "correct". The cases drive the p tools directly, with no model in
the loop, so a change to the arithmetic can be scored for free (see score.py).

Sources (all under the corpus `_sources/label_datasets/`):

  wicherts2011   ManuallyCodedComparisonSample.txt -- Wicherts, Bakker &
                 Molenaar (2011), every statistic in 49 JPSP/JEP papers coded by
                 hand (1,120 rows, 49 errors). For t, `plos.df1` holds the TAILS
                 and `df2` the df; for chi the df sits in whichever column is
                 not NA. Coder comments name one-tailed tests and Huynh-Feldt
                 corrected p's, kept as strata.
  garcia2004     1471-2288-4-13-S1/S2.doc -- Garcia-Berthou & Alcaraz (2004),
                 BMJ (63) and Nature (181) 2001 statistics, 28 errors. Decimals
                 are given; the p carries no relation, so it is exact.
  nuijten2017    CodedCorrections.csv -- Nuijten et al. (2017) validity study,
                 Study 2. ONLY rows coded Correction = 1 are used: statcheck
                 flagged them and a human found the inconsistency explained by
                 the multiplicity/sphericity correction the paper declares. They
                 are NEGATIVES when the tool is told the correction.
  corpus         manifest.csv (tier A/B, WORKING SET only) -- the
                 statcheck_pvalue_errors corpus's documented errors whose printed
                 statistic parses. POSITIVES. The evaluation set is excluded: it
                 is held out for the paid A/B.

    python benchmarks/pvalue_tools/build_cases.py CORPUS_DIR [--out cases.jsonl]
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def decimals(text: str) -> int | None:
    text = str(text).strip()
    if not re.fullmatch(r"-?\d*\.?\d+", text):
        return None
    return len(text.split(".")[1]) if "." in text else 0


def parse_p(text: str):
    """'<.05' -> ('<', 0.05, 2); '0.04' -> ('=', 0.04, 2); '0' -> ('<', .001, 3)."""
    t = str(text).strip().replace(" ", "")
    m = re.fullmatch(r"([<>=]?)(\d*\.?\d+)", t)
    if not m:
        return None
    rel, num = m.group(1) or "=", m.group(2)
    if float(num) == 0:  # "=.000" printed: the coders read it as p < .001
        return "<", 0.001, 3
    return rel, float(num), decimals(num)


def _case(**kw) -> dict:
    return {k: v for k, v in kw.items() if v is not None}


# ---------------------------------------------------------------- wicherts2011
def wicherts(path: Path) -> list[dict]:
    out = []
    rows = list(csv.DictReader(path.open(encoding="ascii", errors="replace", newline=""),
                               delimiter="\t"))
    for i, r in enumerate(rows):
        stat = r["plos.Statistic"].strip().lower()
        comment = (r["plos.comment"] or "").strip()
        low = comment.lower()
        p = parse_p(r["plos.Reported.P.Value"])
        if p is None:
            continue
        rel, rp, dp = p
        value = r["Value"].strip()
        df1, df2 = r["plos.df1"].strip(), r["df2"].strip()
        tails = 2
        if stat == "t":
            kind, df, d2 = "t", float(df2), None
            # `plos.df1` codes the TAILS for t: 1 = a one-tailed test the coders
            # accepted. A "one-tailed, but not presented as such" row is an error
            # precisely because the paper did not declare it, so it is scored as
            # the two-tailed claim the paper printed.
            if df1 == "1" and "not presented as such" not in low:
                tails = 1
        elif stat == "f":
            kind, df, d2 = "f", float(df1), float(df2)
        else:
            kind, d2 = "chi2", None
            df = float(df2) if df2 not in ("NA", "") else float(df1)
        strata = ["bound" if rel in "<>" else "exact"]
        if "not presented as such" in low:
            strata.append("undeclared_one_tailed")
        if "huyn" in low or "feldt" in low or "greenhouse" in low:
            strata.append("sphericity_corrected")
        out.append(_case(
            id=f"wicherts2011:{i}", source="wicherts2011", kind=kind,
            statistic=float(value), decimals_stat=decimals(value), df=df, df2=d2,
            reported_p=rp, p_relation=rel, decimals_p=dp, tails=tails,
            p_adjustment="sphericity" if "sphericity_corrected" in strata else None,
            label="error" if r["plos.Error"].strip().upper() == "TRUE" else "correct",
            decision_error=r["plos.DecisionError"].strip().upper() == "TRUE",
            strata=strata, note=comment or None, raw_p=r["plos.Reported.P.Value"]))
    return out


# ------------------------------------------------------------------ garcia2004
_G_KINDS = {"X2": "chi2", "F": "f", "t": "t", "r": "r", "r2": "r2", "G": "chi2"}


def garcia(folder: Path) -> list[dict]:
    out = []
    for part, journal in (("S1", "bmj2001"), ("S2", "nature2001")):
        text = subprocess.run(["catdoc", "-w", str(folder / f"1471-2288-4-13-{part}.doc")],
                              capture_output=True, text=True).stdout
        text = re.sub(r'HYPERLINK "[^"]*"(\s*\\l "[^"]*")?', " ", text)
        # Records end with the error flag (yes/no), optionally followed by a
        # last-digit column; hyperlinked cells broke them across lines.
        records, buf = [], []
        for line in text.splitlines():
            buf.append(line)
            joined = "\t".join(buf)
            toks = [t.strip() for t in re.split(r"\t", joined) if t.strip()]
            if toks and (toks[-1] in ("yes", "no") or (len(toks) > 1 and toks[-2] in ("yes", "no")
                                                       and re.fullmatch(r"\d", toks[-1]))):
                records.append(toks)
                buf = []
        n = 0
        for toks in records:
            k = next((j for j, t in enumerate(toks) if t in _G_KINDS), None)
            if k is None or len(toks) < k + 9:
                continue
            test, df1, df2, value, dstat, rp, dp, _congruent, err = toks[k:k + 9]
            kind = _G_KINDS[test]
            try:
                stat = float(value)
                df2f = float(df2)
                rpf = float(rp)
            except ValueError:
                continue
            case = dict(id=f"garcia2004:{journal}:{n}", source="garcia2004",
                        reported_p=rpf, p_relation="=",
                        decimals_p=int(dp) if dp.isdigit() else decimals(rp),
                        decimals_stat=int(dstat) if dstat.isdigit() else decimals(value),
                        label="error" if err == "yes" else "correct",
                        strata=["exact", journal, f"kind_{test}"])
            n += 1
            if kind in ("chi2", "t"):
                case.update(kind=kind, statistic=stat, df=df2f, tails=2)
            elif kind == "f":
                case.update(kind="f", statistic=stat, df=float(df1), df2=df2f)
            elif kind == "r":  # residual df: n = df + 2
                case.update(kind="r", statistic=stat, n=int(round(df2f)) + 2, tails=2)
            else:
                # r2 is SKIPPED: the tools take r, and sqrt of a printed r2 has no
                # printed precision to hand them, so a correctly rounded r2 scores
                # as an error (8 of 13 correct r2 rows did on the first build).
                continue
            out.append(_case(**case))
    return out


# ----------------------------------------------------------------- nuijten2017
_APA = re.compile(
    r"^(?P<k>[tFrz])\s*\(\s*(?P<d1>\d+(?:\.\d+)?)\s*(?:,\s*(?P<d2>\d+(?:\.\d+)?))?\s*\)\s*=\s*"
    r"(?P<v>-?\d*\.?\d+)\s*,\s*p\s*(?P<rel>[<>=])\s*(?P<p>\d*\.\d+)\s*$", re.I)
_ADJ = {"bonferroni": "multiplicity", "tukey": "multiplicity", "scheffe": "multiplicity",
        "greenhouse-geisser": "sphericity", "huynh-feldt": "sphericity"}


def nuijten(path: Path) -> list[dict]:
    out = []
    text = path.read_bytes().decode("mac_roman")
    for i, r in enumerate(csv.DictReader(io.StringIO(text), delimiter=";")):
        if (r.get("Correction") or "").strip() != "1":
            continue
        m = _APA.match((r.get("Raw") or "").strip())
        if not m:
            continue
        k = m.group("k").lower()
        if k == "f" and not m.group("d2"):
            continue
        adj = _ADJ.get((r.get("DetectedCorrection") or "").strip().lower(), "unknown")
        case = dict(id=f"nuijten2017:{i}", source="nuijten2017",
                    statistic=float(m.group("v")), decimals_stat=decimals(m.group("v")),
                    reported_p=float(m.group("p")), p_relation=m.group("rel"),
                    decimals_p=decimals(m.group("p")), p_adjustment=adj, label="correct",
                    strata=["correction_explained", f"adjust_{adj}",
                            "bound" if m.group("rel") in "<>" else "exact"],
                    note=(r.get("Remarks") or "").strip() or None, raw=r["Raw"].strip())
        if k == "f":
            case.update(kind="f", df=float(m.group("d1")), df2=float(m.group("d2")))
        elif k == "r":
            case.update(kind="r", n=int(float(m.group("d1"))) + 2, tails=2)
        else:
            case.update(kind=k, df=float(m.group("d1")), tails=2)
        out.append(_case(**case))
    return out


# --------------------------------------------------------------------- corpus
_STAT = re.compile(
    r"(?P<k>\bt|\bF|\br|χ2|chi2)\s*(?:\(\s*(?P<d1>\d+(?:\.\d+)?)\s*(?:,\s*(?P<d2>\d+(?:\.\d+)?))?\s*\)"
    r"|(?P<sd1>\d+),(?P<sd2>\d+))?\s*=\s*(?P<v>[-−–]?\s*\d*\.?\d+)\s*[,;]?\s*[pP]\s*(?P<rel>[<>=])\s*"
    r"(?P<p>\d*\.\d+)")


def corpus(manifest: Path) -> list[dict]:
    out = []
    for r in csv.DictReader(manifest.open(encoding="utf-8")):
        if r["tier"] not in ("A", "B") or "test_statistic_to_p" not in r["check_type"]:
            continue
        # WORKING SET ONLY. The evaluation set is held out for the paid A/B; a
        # gate that pins catches on its documented statistics would tune the
        # tools to it. (Wicherts and Garcia-Berthou overlap some evaluation
        # papers unavoidably -- that is where those papers came from.)
        if r.get("split") != "working_set":
            continue
        text = r["erroneous"].replace("−", "-").replace("–", "-").replace("χ2", "chi2")
        for j, m in enumerate(_STAT.finditer(text)):
            k = {"t": "t", "f": "f", "r": "r", "chi2": "chi2"}[m.group("k").lower()]
            d1 = m.group("d1") or m.group("sd1")
            d2 = m.group("d2") or m.group("sd2")
            if d1 is None or (k == "f" and d2 is None):
                continue  # a df-free statistic is a different question (stratum below)
            v = m.group("v").replace(" ", "")
            case = dict(id=f"corpus:{r['doi']}:{j}", source="corpus", doi=r["doi"],
                        tier=r["tier"], split=r.get("split"), statistic=float(v),
                        decimals_stat=decimals(v.lstrip("-")), reported_p=float(m.group("p")),
                        p_relation=m.group("rel"), decimals_p=decimals(m.group("p")),
                        label="error", strata=["documented_error",
                                               "bound" if m.group("rel") in "<>" else "exact"],
                        raw=m.group(0))
            if k == "f":
                case.update(kind="f", df=float(d1), df2=float(d2))
            elif k == "r":
                case.update(kind="r", n=int(float(d1)) + 2, tails=2)
            else:
                case.update(kind=k, df=float(d1), tails=2)
            out.append(_case(**case))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("corpus", type=Path, help="the statcheck_pvalue_errors corpus directory")
    ap.add_argument("--out", type=Path, default=HERE / "cases.jsonl")
    a = ap.parse_args(argv)
    lab = a.corpus / "_sources" / "label_datasets"
    cases = (wicherts(lab / "ManuallyCodedComparisonSample.txt")
             + garcia(lab / "garcia_berthou_2004_supp")
             + nuijten(lab / "CodedCorrections.csv")
             + corpus(a.corpus / "manifest.csv"))
    a.out.write_text("".join(json.dumps(c, sort_keys=True) + "\n" for c in cases))
    by = {}
    for c in cases:
        by.setdefault(c["source"], [0, 0])[c["label"] == "error"] += 1
    for s, (neg, pos) in by.items():
        print(f"{s:14} {pos:5} errors {neg:6} correct")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
