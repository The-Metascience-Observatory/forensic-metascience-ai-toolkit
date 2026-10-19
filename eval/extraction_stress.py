"""Extraction stress harness: run every FREE extraction path over a wide,
stratified PDF sample and classify how each one FAILS.

WHY THIS EXISTS
---------------
The corpora this repo tests against are narrow. `high_value_pdfs_to_run_on` is
97 recent biomedical and psychology papers, almost all with publisher XML;
`cerebrolysin_papers` is one drug literature; `eval/ground_truth` is 78 curated
cases. All of them are PDFs produced this century by publishers with modern
typesetting pipelines.

Real inputs are not like that. An adversarial audit on 2026-08-07 found a
cluster of extraction defects whose common shape was a DEGRADED RESULT THAT
DOES NOT ANNOUNCE ITSELF -- `extract_figures` returning `success: true,
n_figures: 0, warnings: []` on an unreadable document; a corrupt PDF becoming a
zero-page document with `truncated: False`; a supplement gate passing because
the text it reads was empty. Every one of those is invisible on a clean modern
PDF and obvious on an old scanned one.

This harness measures the thing those defects live in: the failure DISTRIBUTION
across publishers and decades. It costs nothing -- no model calls, no network --
so it can run over thousands of documents.

WHAT IT CLASSIFIES
------------------
Each extraction path returns one of:

  ok              content came back
  honest_refusal  nothing came back AND the result says so (an error, a warning,
                  or an explicit zero with an explanation). This is a PASS.
  silent_empty    nothing came back and NOTHING SAYS SO. This is the defect
                  class the audit named; it is indistinguishable to a caller
                  from a document that genuinely has no tables or figures.
  crash           the call raised

`silent_empty` is the number this harness exists to drive to zero. It is not
the same as `honest_refusal`, and conflating them is how the defects survived.

USAGE
-----
    python -m eval.extraction_stress --n 400 --out stress.json
    python -m eval.extraction_stress --n 40 --decade 1990   # one stratum
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import random
import re
import shutil
import sqlite3
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any

ZOTERO_SQLITE = Path("/mnt/c/Users/gregs/Zotero/zotero.sqlite")
ZOTERO_STORAGE = Path("/mnt/c/Users/gregs/Zotero/storage")

OK, REFUSAL, SILENT, CRASH = "ok", "honest_refusal", "silent_empty", "crash"
TIMEOUT = "timeout"

#: Per-path wall-clock budget. A 400-page scanned thesis can hold pdfplumber
#: for minutes, and an extraction path that cannot bound its own runtime is a
#: defect in its own right when the caller is a paid agent on a per-stage
#: timeout -- so a timeout is RECORDED as an outcome rather than being avoided
#: by sampling only small files.
PATH_TIMEOUT_SEC = 45

#: Docling's OWN budget, which is minutes rather than seconds.
#:
#: Extraction is an explicit STAGE of this harness (see `probe`). Letting it
#: share `PATH_TIMEOUT_SEC` would time out essentially every document and record
#: the timeout as a property of the paper -- the house defect, reproduced inside
#: the instrument built to find it.
#:
#: IT DOES NOT ACTUALLY BOUND ANYTHING, AND THE COMMENT SAYING OTHERWISE WAS
#: WRONG. MEASURED 2026-08-18 over 41 documents: one took 2,199 s against this
#: 900 s budget and was never interrupted. `_budget` raises from a SIGALRM
#: handler, and a Python signal handler only runs between BYTECODE
#: instructions -- docling spends its time inside torch/onnx C extensions, where
#: the interpreter never gets a chance to deliver it. The alarm fires, the
#: handler is queued, and nothing happens until the C call returns of its own
#: accord.
#:
#: So this is a best-effort ceiling on the Python-visible parts and nothing
#: more. A real wall-clock bound on extraction needs a subprocess that can be
#: killed from outside. Left as-is deliberately: the harness is a measurement
#: tool and a 37-minute outlier is DATA (it is the scanned document that falls
#: through to OCR), but the number must not be quoted as an enforced limit.
EXTRACT_TIMEOUT_SEC = 900

#: Where a sampled PDF is copied so extraction has somewhere to put its cache.
#:
#: NOT the Zotero storage tree. `docling_tables._cache_path` writes
#: `.extraction_cache/` BESIDE the PDF, and that tree is synced by the desktop
#: client; a measurement run must not leave artefacts in the user's library.
#: Also ext4 rather than `/mnt/c`, which had 16 GB free against 909 GB here and
#: pays 9p translation on every read of a job that is entirely file-bound.
#:
#: The directory is STABLE and keyed by Zotero attachment key, so an interrupted
#: run resumes against the caches it already paid for.
WORKROOT = Path.home() / "fmt-zotero-stress"


class _Timeout(Exception):
    pass


def _budget(seconds: int):
    """Context manager raising `_Timeout` after `seconds` of wall clock."""
    import signal
    from contextlib import contextmanager

    @contextmanager
    def guard():
        def fire(_sig, _frm):
            raise _Timeout(f"exceeded {seconds}s")
        old = signal.signal(signal.SIGALRM, fire)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)

    return guard()


# --------------------------------------------------------------------------
# Sampling
# --------------------------------------------------------------------------

def zotero_pdfs() -> list[dict]:
    """Every PDF attachment with the year and journal of its parent item.

    The live database is COPIED before reading. Zotero holds it open and the
    skill notes for this machine are explicit that writing to it risks
    corruption; a read against the live file can also hit a lock mid-sync.
    """
    if not ZOTERO_SQLITE.exists():
        return []
    tmp = tempfile.mktemp(suffix=".sqlite")
    shutil.copy(ZOTERO_SQLITE, tmp)
    try:
        con = sqlite3.connect(tmp)
        rows = con.execute("""
            SELECT i.key, ia.path,
              (SELECT value FROM itemData d JOIN itemDataValues v ON d.valueID=v.valueID
               WHERE d.itemID=p.itemID AND d.fieldID=
                 (SELECT fieldID FROM fields WHERE fieldName='date')) AS date,
              (SELECT value FROM itemData d JOIN itemDataValues v ON d.valueID=v.valueID
               WHERE d.itemID=p.itemID AND d.fieldID=
                 (SELECT fieldID FROM fields WHERE fieldName='publicationTitle')) AS journal
            FROM itemAttachments ia
            JOIN items i ON i.itemID = ia.itemID
            LEFT JOIN items p ON p.itemID = ia.parentItemID
            WHERE ia.contentType = 'application/pdf'
        """).fetchall()
        con.close()
    finally:
        os.unlink(tmp)

    out = []
    for key, path, date, journal in rows:
        if not path:
            continue
        name = path.split(":", 1)[1] if ":" in path else path
        f = ZOTERO_STORAGE / key / name
        if not f.exists():
            continue
        year = (date or "")[:4]
        out.append({
            "key": key,
            "path": str(f),
            "year": int(year) if year.isdigit() else None,
            "journal": (journal or "").strip(),
            "size": f.stat().st_size,
        })
    return out


#: Journal-name substrings that place a venue in a FORMAT family. Matched
#: lowercase, first hit wins, so order is meaningful: `nature reviews` and
#: `nature communications` are ordinary journals rather than the short-article
#: house style `Nature` itself has, and must be caught before the bare `nature`.
_VENUE_FAMILIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("mega_journal", ("plos one", "scientific reports", "peerj", "f1000",
                      "heliyon", "plos ")),
    ("bench_biology", ("journal of biological chemistry", "neuron",
                       "journal of neuroscience", "cell ", "molecular cell",
                       "biochemistry", "journal of cell biology", "embo",
                       "brain research", "neuroscience")),
    ("clinical", ("neurology", "alzheimer", "lancet", "new england journal",
                  "jama", "bmj", "clinical", "medicine", "psychiatry",
                  "diabetes", "cancer")),
    ("flagship_multidisciplinary", ("nature reviews", "nature communications",
                                    "nature ")),
    ("flagship_multidisciplinary_exact", ("nature", "science", "pnas",
                                          "proceedings of the national")),
)


def venue_family(journal: str) -> str:
    """Which FORMAT family a journal belongs to, or `other`.

    The families are the ones task #168 names, and they are about DOCUMENT SHAPE
    rather than subject: a flagship multidisciplinary paper is four pages with
    the data in a 60-page supplement, a mega-journal paper has no house style at
    all, bench biology carries its data in figures, and clinical papers are
    table-dense. Those are four different ways for extraction to fail.
    """
    j = (journal or "").strip().lower()
    if not j:
        return "unknown"
    for family, needles in _VENUE_FAMILIES:
        exact = family.endswith("_exact")
        for needle in needles:
            if (j == needle if exact else needle in j):
                return family[:-6] if exact else family
    return "other"


def era(year: int | None) -> str:
    """Pre-2010 / 2010s / post-2020, per #168.

    Coarser than a decade because the thing being sampled for is FONT-ENCODING
    ERA, not publication date: the corruption that `glyphs` detects clusters in
    pre-2010 typesetting pipelines, and splitting 1990 from 2000 buys nothing
    when both are the same technology.
    """
    if not year:
        return "unknown"
    if year < 2010:
        return "pre2010"
    return "2010s" if year < 2020 else "post2020"


def stratify(items: list[dict], n: int, seed: int = 11) -> list[dict]:
    """A sample crossed over VENUE FAMILY and ERA, both deliberately flat.

    Decade alone was not enough, and the reason is the whole point of #168: this
    library is a neuroscience library, so a draw stratified only by year returns
    150 near-identical neuro papers from different decades. The format families
    are what make the sample adversarial -- they are four different ways for a
    document to be shaped, and our 119-paper corpus contains essentially one.

    Both margins are FLAT rather than proportional. A proportional sample would
    be 55% 2010s and mostly bench biology, which is the stratum every existing
    corpus already covers; the failures live in the thin cells.
    """
    rng = random.Random(seed)
    buckets: dict[str, list[dict]] = collections.defaultdict(list)
    for it in items:
        it["family"] = venue_family(it.get("journal", ""))
        it["era"] = era(it["year"])
        buckets[f"{it['family']}|{it['era']}"].append(it)

    # Equal share per stratum, capped by what the stratum holds. The remainder
    # goes to the biggest strata so the total lands on n.
    keys = sorted(buckets)
    share = max(1, n // max(1, len(keys)))
    picked: list[dict] = []
    for k in keys:
        picked += rng.sample(buckets[k], min(share, len(buckets[k])))
    if len(picked) < n:
        rest = [x for x in items if x not in picked]
        picked += rng.sample(rest, min(n - len(picked), len(rest)))
    # SHUFFLE BEFORE TRUNCATING. `picked` is built by walking the cells in
    # sorted order, so `picked[:n]` cut it in ALPHABETICAL order by cell name:
    # a 3-document smoke run returned bench_biology three times and looked like
    # a sampling result rather than the truncation artefact it was. Harmless at
    # n=200 where every cell gets a full share, silently wrong at every size
    # below that -- which is exactly the size a person uses to check the thing
    # works before trusting it.
    rng.shuffle(picked)
    return picked[:n]


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------

#: Keys whose presence means the result EXPLAINED an empty return.
#:
#: `methodology` was here and had to go: `extract_figures` attaches one to
#: EVERY success return, so its presence says nothing about whether this
#: particular empty result was explained, and including it made
#: `figures: silent_empty` unreachable. Re-scoring the 84 figure refusals from
#: the first 300-document run without it: 70 were genuine and 14 came back with
#: `warnings == []` and no error. A key belongs here only if it is absent on a
#: silent return -- an unconditional key is not evidence of anything.
#:
#: `tables_note` added 2026-08-17: it is set ONLY when the document was read and
#: no table structure was found, so it satisfies the rule above -- it is absent
#: on a return that failed to look. Its arrival does mean the `tables` path can
#: no longer report `silent_empty`, and that is correct rather than convenient:
#: with extraction measured as its own stage, "did anything look at this file?"
#: is answered by `extract`, and the question left for the tables path is the
#: harder one below -- whether the paper CLAIMS tables we did not find.
_EXPLANATION_KEYS = ("warnings", "warning", "note", "tables_rejected_note",
                     "how_to_get_more", "unreadable", "tables_note")


def _said_something(result: Any) -> bool:
    """Did the result ADMIT that it came back empty?

    An error key, any warning, or an explicit note counts. A bare empty list
    with no explanation does not -- that is the whole point of the exercise.
    """
    if not isinstance(result, dict):
        return False
    if result.get("error"):
        return True
    for key in _EXPLANATION_KEYS:
        v = result.get(key)
        if isinstance(v, (list, tuple)) and v:
            return True
        if isinstance(v, str) and v.strip():
            return True
        if v is True:
            return True
    return False


def body_chars(result: Any) -> int:
    """Characters that came from the DOCUMENT, not from the envelope.

    `extract_text_with_tables` joins a `--- Page N ---` header for every page
    unconditionally, so `len(result["text"])` is non-zero on any document with
    at least one page and `text: silent_empty` was UNREACHABLE BY
    CONSTRUCTION. That is a stronger failure than scoring leniently, and it is
    why the first run reported `text SILENT=0`.

    Five documents in that run returned exactly zero extracted characters and
    were scored `ok`. It is provable to the byte, because `text_chars` equals
    the page-marker skeleton exactly: emdr-article, 6 pages, 100 chars =
    6*15 + 5*2. Those same five are the ENTIRE `raw_text` SILENT set -- so the
    harness recorded the same zero bytes as SILENT on one path and `ok` on
    another, in the same record, and had no check that would notice.

    IT MUST BE THE LIBRARY'S MEASURE, NOT A SECOND ONE. This summed the page
    texts itself, which excludes the page markers but NOT the publisher
    furniture -- so a two-page scan carrying only "(c) 1968 Nature Publishing
    Group" scored 66 characters here and 0 in
    `extraction.pdf.readable_body_chars`, and the harness recorded `text: ok`
    on a document the library had already flagged `unreadable: True`.

    The run's own contradiction check is what surfaced it: the same three
    documents came back SILENT on `raw_text` and OK on `text`, and both paths
    read the same bytes. A harness that reimplements the predicate it is
    testing will drift from it, and drift silently. Importing is the fix.
    """
    if not isinstance(result, dict):
        return 0
    from metascience_agent.extraction.pdf import readable_body_chars

    pages = result.get("pages")
    if isinstance(pages, list) and pages:
        return readable_body_chars(
            [(p.get("text") or "") for p in pages if isinstance(p, dict)])
    return len((result.get("text") or "").strip())


def classify(result: Any, content: bool) -> str:
    if content:
        return OK
    return REFUSAL if _said_something(result) else SILENT


def _timeout_or_crash(exc: BaseException) -> str:
    """A budget expiry is a TIMEOUT even when it arrives wearing a crash.

    The SIGALRM fires inside pdfminer, which catches it and re-raises it as
    `PdfminerException: exceeded 45s`. So the exception that reaches us is
    indistinguishable by type from a genuine parse failure, and 9 of the first
    run's recorded crashes were really this. That mattered: "your library
    cannot parse this file" and "we did not give it long enough" call for
    completely different fixes.
    """
    if f"exceeded {PATH_TIMEOUT_SEC}s" in str(exc):
        return TIMEOUT
    return CRASH


def workdir(item: dict) -> Path:
    """A stable directory holding a copy of one sampled PDF.

    Extraction writes its cache beside the file it read, so the file has to live
    somewhere we are willing to write. Keyed by Zotero attachment key and reused
    across runs, which makes a 12-hour job resumable rather than restartable.
    """
    d = WORKROOT / item["key"]
    d.mkdir(parents=True, exist_ok=True)
    dest = d / "paper.pdf"
    if not dest.exists() or dest.stat().st_size != item["size"]:
        shutil.copy(item["path"], dest)
    return d


def probe(pdf: Path) -> dict:
    """Every free extraction path against one document.

    EXTRACTION RUNS FIRST, AND IS ITSELF A MEASURED PATH. Until 2026-08-17 this
    function called the readers directly, which was correct while they would
    extract on demand. Both went CACHE-ONLY in #173, so on any document outside
    the 23-entry corpus cache -- which is every document this harness samples --
    each reader returned an empty result that EXPLAINED ITSELF, and `classify`
    scored the explanation as `honest_refusal`, a pass. `silent_empty`, the one
    number this file exists to drive to zero, was therefore 0 by construction.
    The harness reported perfect health because it had stopped working.

    Keeping extraction as a separate recorded stage also separates two failures
    that a single number would merge: docling could not read this document, and
    docling read it but the reader saw nothing.
    """
    from metascience_agent.extraction import docling_tables as _dl
    from metascience_agent.tool_specs.readers.spec import extract_figures  # refuses by name without the image package
    from metascience_agent.extraction.pdf import (
        extract_text,
        extract_text_with_tables,
    )

    out: dict[str, Any] = {}

    # --- extraction, the stage everything below depends on
    started = time.time()
    try:
        with _budget(EXTRACT_TIMEOUT_SEC):
            r = _dl.extract_pdf_tables(pdf, allow_extract=True)
        out["extract"] = REFUSAL if r.get("error") else OK
        out["extract_cached"] = bool(r.get("cached"))
        if r.get("error"):
            out["extract_error"] = str(r["error"])[:300]
    except _Timeout:
        out["extract"] = TIMEOUT
    except Exception as exc:
        out["extract"] = CRASH
        out["extract_error"] = f"{type(exc).__name__}: {exc}"[:300]
    out["extract_seconds"] = round(time.time() - started, 1)

    # --- text + tables
    try:
        with _budget(PATH_TIMEOUT_SEC):
            r = extract_text_with_tables(pdf, max_chars=20000)
        out["text"] = classify(r, bool(body_chars(r)))
        out["tables"] = classify(r, bool(r.get("tables")))
        out["n_pages"] = r.get("num_pages")
        out["n_tables"] = len(r.get("tables") or [])
        out["text_chars"] = len((r.get("text") or ""))
        out["body_chars"] = body_chars(r)

        # THE PAPER'S OWN PROSE AS AN INDEPENDENT WITNESS.
        #
        # A zero-table result is ambiguous on its own and a second opinion is
        # free: a paper that writes "as shown in Table 2" is asserting that a
        # table exists. Claims > 0 with extracted == 0 is a RECALL FAILURE and
        # is worth opening by hand; claims == 0 with extracted == 0 is an
        # ordinary figure-borne paper and is worth nothing. Merging those two
        # into one "no tables" count is what would make the overnight numbers
        # uninterpretable.
        #
        # Deliberately counts only "Table" + digit, so "in tabular form" and a
        # bare "Table" heading do not inflate it. It is a screen, not a census.
        #
        # SUPPLEMENT REFERENCES ARE EXCLUDED, and leaving them in made the
        # screen useless. MEASURED 2026-08-18 by opening all five flagged
        # papers: FOUR were false positives whose every "Table N" was a
        # "Supplementary Table N" -- Finan et al. 2015 in Nat Med referred to
        # eight, has no main-text table at all, and zero extracted was correct.
        # A supplementary table lives in a separate file this run never saw, so
        # citing one says nothing about the article's own tables. The screen
        # went from 5 hits to 1 real one.
        body = " ".join((r.get("text") or "").split())
        _supp = re.compile(
            r"(?:supplementary|supplemental|supporting|extended\s+data|online)\s+$",
            re.I)
        out["table_claims"] = sum(
            1 for m in re.finditer(r"\bTables?\s+\d", body)
            if not _supp.search(body[max(0, m.start() - 30):m.start()]))
        out["table_recall_suspect"] = bool(
            out["table_claims"] and not out["n_tables"])
    except _Timeout:
        out["text"] = out["tables"] = TIMEOUT
    except Exception as exc:
        kind = _timeout_or_crash(exc)
        out["text"] = out["tables"] = kind
        out["text_error"] = f"{type(exc).__name__}: {exc}"[:200]

    # --- raw text, the simplest path of all
    try:
        with _budget(PATH_TIMEOUT_SEC):
            t = extract_text(pdf)
        out["raw_text"] = OK if t.strip() else SILENT
        out["raw_text_chars"] = len(t)
    except _Timeout:
        out["raw_text"] = TIMEOUT
    except Exception as exc:
        out["raw_text"] = _timeout_or_crash(exc)
        out["raw_text_error"] = f"{type(exc).__name__}: {exc}"[:200]

    # --- figures
    with tempfile.TemporaryDirectory() as td:
        try:
            with _budget(PATH_TIMEOUT_SEC):
                r = extract_figures(pdf, out_dir=td, render_pages=False)
            out["figures"] = classify(r, bool(r.get("figures")))
            out["n_figures"] = r.get("n_figures")
            out["fig_success"] = r.get("success")
        except _Timeout:
            out["figures"] = TIMEOUT
        except Exception as exc:
            out["figures"] = CRASH
            out["figures_error"] = f"{type(exc).__name__}: {exc}"[:200]

    # --- character corruption (#168 Phase 1 item 2)
    #
    # `scan_paper` takes a DIRECTORY and fails closed on unreadable text, which
    # is why it is called rather than `scan`: an empty string scans clean, and a
    # corruption detector reporting clean on a file it could not read is the
    # exact defect this harness classifies as `silent_empty` elsewhere.
    try:
        from metascience_agent.glyphs import scan_paper
        with _budget(PATH_TIMEOUT_SEC):
            g = scan_paper(pdf.parent)
        out["glyph_text_available"] = bool(g.get("text_available"))
        out["glyph_clean"] = bool(g.get("clean"))
        out["glyph_occurrences"] = g.get("total_occurrences") or 0
        # The key is `pattern`, NOT `name`. Read wrongly for the first 41
        # documents of the 2026-08-18 sweep, which recorded `[None]` for every
        # hit -- corruption counts with no way to say WHICH corruption, which is
        # most of the value. Recomputable from the caches, so nothing is lost.
        out["glyph_patterns"] = [
            pat.get("pattern") for pat in (g.get("patterns") or [])
            if isinstance(pat, dict)][:8]
        # THE FIELD THAT DECIDES WHETHER CORRUPTION MATTERS. A mangled ligature
        # in prose is cosmetic; a mangled DIGIT reaches a forensic check and can
        # manufacture a finding about a number the paper never printed. Counting
        # both under one "corrupt" flag would report the harmless case at the
        # same weight as the dangerous one.
        out["glyph_corrupts_digits"] = any(
            pat.get("corrupts_digits") for pat in (g.get("patterns") or [])
            if isinstance(pat, dict))
        out["glyph_quarantine"] = bool(g.get("quarantine"))
    except _Timeout:
        out["glyph_scan"] = TIMEOUT
    except Exception as exc:
        out["glyph_scan"] = CRASH
        out["glyph_error"] = f"{type(exc).__name__}: {exc}"[:200]
    return out


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def run(n: int, decade: str | None, seed: int, out_path: Path | None) -> dict:
    items = zotero_pdfs()
    if not items:
        raise SystemExit("no Zotero PDFs found")
    if decade:
        items = [i for i in items
                 if i["year"] and f"{(i['year'] // 10) * 10}s" == decade]
    sample = stratify(items, n, seed)
    print(f"{len(items)} candidates -> {len(sample)} sampled")

    # A per-document line, flushed as it is produced. Extraction is minutes per
    # paper now, so a 150-document run is hours and WILL be interrupted at some
    # point; a report written only at the end is a report that does not survive
    # a closed laptop.
    stream = (out_path.with_suffix(".jsonl") if out_path
              else Path("extraction_stress.jsonl"))
    done: set[str] = set()
    if stream.exists():
        for line in stream.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["path"])
            except Exception:
                continue
        print(f"resuming: {len(done)} already recorded in {stream}")

    records = []
    t0 = time.time()
    with stream.open("a", encoding="utf-8") as fh:
        for i, it in enumerate(sample, 1):
            if it["path"] in done:
                continue
            rec = {k: it[k] for k in
                   ("key", "path", "year", "journal", "size", "family", "era")}
            started = time.time()
            try:
                rec.update(probe(workdir(it) / "paper.pdf"))
            except Exception:
                rec["fatal"] = traceback.format_exc(limit=2)[:400]
            rec["seconds"] = round(time.time() - started, 2)
            records.append(rec)
            fh.write(json.dumps(rec, default=str) + "\n")
            fh.flush()
            print(f"  {i}/{len(sample)} {rec['family']}/{rec['era']} "
                  f"{rec.get('extract')} {rec['seconds']}s "
                  f"({time.time() - t0:.0f}s elapsed)", flush=True)

    report = summarise(records)
    if out_path:
        out_path.write_text(json.dumps(
            {"summary": report, "records": records}, indent=2, default=str))
        print(f"\nwrote {out_path}")
    return report


def summarise(records: list[dict]) -> dict:
    paths = ["raw_text", "text", "tables", "figures"]
    BAD = (SILENT, CRASH, TIMEOUT)
    by_path = {p: collections.Counter(r.get(p) for r in records) for p in paths}
    by_decade: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter)
    for r in records:
        y = r.get("year")
        d = "unknown" if not y else f"{(y // 10) * 10}s"
        for p in paths:
            v = r.get(p)
            if v in BAD:
                by_decade[d][f"{p}:{v}"] += 1
        by_decade[d]["n"] += 1

    print("\n=== OUTCOME BY EXTRACTION PATH ===")
    for p in paths:
        c = by_path[p]
        tot = sum(c.values()) or 1
        print(f"  {p:10s} ok={c[OK]:4d} refusal={c[REFUSAL]:4d} "
              f"SILENT={c[SILENT]:4d} crash={c[CRASH]:4d} timeout={c[TIMEOUT]:4d}  "
              f"(silent+crash = {100 * (c[SILENT] + c[CRASH]) / tot:.1f}%)")

    print("\n=== SILENT FAILURES AND CRASHES BY DECADE ===")
    for d in sorted(by_decade):
        c = by_decade[d]
        bad = {k: v for k, v in c.items() if k != "n"}
        print(f"  {d:9s} n={c['n']:4d}  {dict(bad) if bad else 'clean'}")

    # The harness checks itself, because the first run needed it to.
    #
    # `raw_text` and `text` read the same document with the same library. If
    # one says it got nothing and the other says it succeeded, at least one of
    # them is wrong -- and in the first run that contradiction sat in FIVE
    # records, unremarked, because nothing compared the two columns. A tool
    # built to catch results that do not announce their own failure has no
    # business failing to announce its own.
    contradictions = [
        r for r in records
        if r.get("raw_text") == SILENT and r.get("text") == OK
    ]
    if contradictions:
        print(f"\n!!! {len(contradictions)} record(s) where raw_text came back "
              f"SILENT and text came back OK on the SAME document. Both paths "
              f"read the same bytes, so one of these classifications is wrong:")
        for r in contradictions[:8]:
            print(f"      pages={r.get('n_pages')} text_chars={r.get('text_chars')} "
                  f"body_chars={r.get('body_chars')}  {r['path'].split('/')[-1][:56]}")

    return {
        "n": len(records),
        "by_path": {p: dict(by_path[p]) for p in paths},
        "by_decade": {d: dict(c) for d, c in by_decade.items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--decade", help="restrict to one decade, e.g. 1990s")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    run(a.n, a.decade, a.seed, a.out)


if __name__ == "__main__":
    main()
