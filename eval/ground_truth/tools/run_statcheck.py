#!/usr/bin/env python
"""Preliminary sensitivity/specificity run: statcheck over the whole corpus.

statcheck is the only tool in the kit that runs end-to-end with no human
extraction step -- it reads APA-format test statistics straight out of the
text -- so it is the one tool whose sensitivity can be measured on this
corpus today. GRIM/GRIMMER/SPRITE/DEBIT all need mean/SD/N triples with a
known scale and granularity, which requires the extraction layer to be
validated first; running them now would measure the extractor, not the test.

Text source: full-text XML where available (clean, no PDF layout noise),
otherwise the PDF via pdfplumber.

Usage: python run_statcheck.py [--out results_statcheck.csv]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile

import pandas as pd
from metascience_agent.paper_ids import doi_dirname

HERE = os.path.dirname(os.path.abspath(__file__))
PAPERS = os.path.join(HERE, "..", "papers")
MANIFEST = os.path.join(HERE, "..", "manifest.csv")

R_SCRIPT = r"""
suppressMessages(library(statcheck))
args <- commandArgs(trailingOnly = TRUE)
txt <- readChar(args[1], file.info(args[1])$size, useBytes = TRUE)
txt <- iconv(txt, to = "UTF-8", sub = "")
res <- tryCatch(statcheck(txt, messages = FALSE), error = function(e) NULL)
if (is.null(res) || nrow(res) == 0) {
  cat("0,0,0\n")
} else {
  cat(sprintf("%d,%d,%d\n", nrow(res), sum(res$error, na.rm = TRUE),
              sum(res$decision_error, na.rm = TRUE)))
}
"""


# JATS wraps test statistics as <italic>F</italic>(1, 350) = 6.02. Replacing
# those inline tags with a space yields "F (1, 350)", which statcheck's regex
# does not match -- so inline formatting tags must be deleted, not spaced.
_INLINE = r"italic|bold|sup|sub|sc|underline|monospace|styled-content|xref|named-content"


def xml_to_text(path: str) -> str:
    raw = open(path, "rb").read().decode("utf-8", "replace")
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S)
    raw = re.sub(r"</?(%s)(\s[^>]*)?>" % _INLINE, "", raw)   # delete, no space
    raw = re.sub(r"<[^>]+>", " ", raw)                        # block tags -> space
    raw = raw.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    raw = raw.replace(" ", "").replace(" ", " ").replace("−", "-")
    return re.sub(r"[ \t]+", " ", raw)


def pdf_to_text(path: str) -> str:
    try:
        import pdfplumber
    except ImportError:
        return ""
    out = []
    try:
        with pdfplumber.open(path) as doc:
            for p in doc.pages:
                out.append(p.extract_text() or "")
    except Exception:
        return ""
    return re.sub(r"\s+", " ", " ".join(out))


def get_text(slug: str) -> tuple[str, str]:
    d = os.path.join(PAPERS, slug)
    pj = os.path.join(d, "provenance.json")
    if not os.path.exists(pj):
        return "", "none"
    m = json.load(open(pj))
    for key, kind, fn in (("xml_path", "xml", xml_to_text),
                          ("pdf_path", "pdf", pdf_to_text)):
        p = m.get(key)
        if p:
            p = p if os.path.isabs(p) else os.path.join(d, os.path.basename(p))
            if not os.path.exists(p):
                p = os.path.join(d, "%s.%s" % (slug, kind))
            if os.path.exists(p):
                t = fn(p)
                if len(t) > 500:
                    return t, kind
    return "", "none"


def run_statcheck(text: str) -> tuple[int, int, int]:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(text)
        tpath = fh.name
    with tempfile.NamedTemporaryFile("w", suffix=".R", delete=False) as fh:
        fh.write(R_SCRIPT)
        rpath = fh.name
    try:
        out = subprocess.run(["Rscript", rpath, tpath], capture_output=True,
                             text=True, timeout=300).stdout.strip().splitlines()
        for line in reversed(out):
            if re.fullmatch(r"\d+,\d+,\d+", line.strip()):
                return tuple(int(x) for x in line.strip().split(","))  # type: ignore
    except Exception:
        pass
    finally:
        for p in (tpath, rpath):
            try:
                os.unlink(p)
            except OSError:
                pass
    return 0, 0, 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "..", "results_statcheck.csv"))
    a = ap.parse_args()

    man = pd.read_csv(MANIFEST)
    rows = []
    for _, r in man.iterrows():
        slug = doi_dirname(r["doi"])
        text, kind = get_text(slug)
        n, err, derr = run_statcheck(text) if text else (0, 0, 0)
        rows.append({
            "doi": r["doi"], "label": r["label"],
            "expected_statistical_signature": r["expected_statistical_signature"],
            "text_source": kind, "text_chars": len(text),
            "n_stats_extracted": n, "n_inconsistent": err,
            "n_decision_errors": derr,
            "flagged": int(err > 0),
            "testable": int(n > 0),
        })
        print("  %-38s %-8s %-4s stats=%-4d err=%-3d dec=%d"
              % (r["doi"][:38], r["label"], kind, n, err, derr))

    df = pd.DataFrame(rows)
    df.to_csv(a.out, index=False)

    print("\n" + "=" * 68)
    print("PRELIMINARY statcheck RESULTS -- see protocol for caveats")
    print("=" * 68)
    f, c = df[df.label == "fraud"], df[df.label == "control"]
    print("Corpus: %d fraud, %d control" % (len(f), len(c)))
    print("Papers yielding >=1 parseable APA statistic: fraud %d/%d, control %d/%d"
          % (f.testable.sum(), len(f), c.testable.sum(), len(c)))

    ft, ct = f[f.testable == 1], c[c.testable == 1]
    if len(ft):
        print("\nSensitivity  (all fraud, testable):      %d/%d = %.0f%%"
              % (ft.flagged.sum(), len(ft), 100 * ft.flagged.mean()))
    exp = f[f.expected_statistical_signature.str.contains("statcheck", na=False)]
    expt = exp[exp.testable == 1]
    if len(expt):
        print("Sensitivity  (statcheck signature EXPECTED): %d/%d = %.0f%%"
              % (expt.flagged.sum(), len(expt), 100 * expt.flagged.mean()))
    if len(ct):
        print("Specificity  (controls, testable):       %d/%d = %.0f%%"
              % ((1 - ct.flagged).sum(), len(ct), 100 * (1 - ct.flagged.mean())))
    print("\nNOTE: a statcheck 'inconsistency' is a reporting error, NOT evidence of "
          "fraud.\nBase rates of ~50%% of papers containing >=1 inconsistency are normal in "
          "the\nliterature, which is why the control arm is mandatory for interpretation.")


if __name__ == "__main__":
    main()
