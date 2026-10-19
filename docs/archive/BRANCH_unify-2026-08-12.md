# Branch `unify-2026-08-12` — what is in it, and what is still broken

> **ARCHIVED 2026-10-16.** The `unify` branch merged long ago; the stage costs, open items and test counts below describe the deleted serial pipeline. Everything durable is in CHANGELOG.md and the code.

Greg Fitzgerald · 2026-08-13 · **283 commits ahead of `main`**

This is a read-first note for anyone picking the branch up. It is not a
changelog: 283 commits is unreviewable, and the useful thing is what CHANGED
ABOUT THE SYSTEM, what is MEASURED, and what is still wrong.

Nothing here has been merged to `main`. The branch is pushed so it can be read
and argued with.

---

## 1. The one-line summary

**The pipeline was reading its papers through the wrong extractor, and most of
what it could not check was invisible rather than reported.** Both are fixed and
measured; the coverage machinery still has a large hole (§5).

---

## 2. What changed, with the measurement that justified it

### Docling replaces pdfplumber for reading PDFs

Against publisher XML ground truth, on the seven papers here that ship BOTH a
JATS XML and a PDF (the XML is not an estimate of the tables — it IS them):

| extractor | table precision | table recall |
|---|---|---|
| pdfplumber (previous) | 88.3% | 60.7% |
| marker | 87.0% | 90.0% |
| **docling** | **92.0%** | **95.9%** |

Docling wins on both axes. Routing (pick the best tool per paper) was measured at
+0.4 points and dropped; the UNION of all three was +0.6 recall and WORSE
precision, because it inherits every tool's false values. One good component
beat both architectures.

**The body-text gap is larger than the table gap and was found second.**
pdfplumber renders operators as glyph references and our own debris filter then
strips them, so a printed `t(28) = -3.33` reached a checker as `t(28)3.33` —
comparator and MINUS SIGN gone. On Ophir 2009 (PNAS), statcheck finds **0**
statistics in pdfplumber's text and **26** (2 inconsistent) in Docling's.

Docling is now a hard dependency. pdfplumber stays and is not vestigial: page
counts, table detection, the scanned-paper guard and every page-range read still
go through it, and it serves the text whenever the Docling cache is cold.

### statcheck was blind to capital `P`

The vendored package hardcodes lowercase — `RGX_P = "(p\s?[<>=]\s?...)"` — so a
paper in PNAS/Nature/medical house style found zero statistics and reported *"No
NHST statistics found in APA format"*, which reads as a fact about the paper.
**MEASURED: 31 of 119 corpus papers carrying p-values (26%) use capital `P`
only** and were silently unstatcheckable. Normalised in our wrapper, not by
patching the package — a `pip upgrade` reverts a vendored edit and the defect is
invisible when it returns.

> **Consequence for anything already published:** our statcheck applicability
> figures were computed with BOTH defects live. The framing that low yield is "a
> property of the literature, not of the tool" is partly an artefact we created.
> Re-baselining is outstanding.

### Supplements are declared, not guessed

Detection keyed on seven filename substrings. Wiley names its supplement
`EAT-58-1072-s001.docx`; none of the seven appears in it; the file was skipped so
quietly it reached neither the usable nor the unusable list. Of nine real
publisher conventions the list matched four, and it missed OUR OWN FETCHER's
saved names.

Roles now come from three authorities that do not guess — the operator's
`inputs.json` (`metascience inputs`), the article's own supplementary-material
list, and the DOI stem for the article file. Anything else is `undeclared`:
listed, exit code 2, never skipped.

On the paper that exposed it, recognising the supplement took the checkable
manifest from **325 items to 924**, and six of the twelve findings in the
subsequent run cite material that had been invisible.

### Every number now says where it came from

`computation_audit` records, per finding, whether a figure was computed by a
registered tool, transcribed from the paper (located verbatim — **86.7% of the
369 figures in non-tool findings are**), or produced by the agent and therefore
needing its derivation shown. Nothing is discarded for failing this: an
unrecorded number is not a fabricated one.

`run_meta.text_provenance` records WHICH READER produced the text, per file, and
the viewer says so — because it changes what an ABSENCE means. A quiet result
from a pdfplumber read may be a quiet extractor.

### New offline instruments

| command | what it answers |
|---|---|
| `metascience inputs <dir>` | what is each file, and what is undeclared |
| `metascience extract-tables <dir>` | fill the extraction cache (explicit, cached by content hash) |
| `metascience handoff-audit <dir> [-r run]` | does every stage hand its work on, and does the next stage read it |
| `metascience agreement <dir>` | pass@K across repeated runs of one paper |

`handoff-audit` runs offline and free, and is the pre-flight before a paid run.
It has already caught two defects that would have wasted one.

It checks the DATA hand-offs and not the ADMISSIBILITY gates, and the difference
has bitten once: on Kross 2013 it printed "all 5 hand-offs carry data" and
`analyze` then exited 2, because the article's own Supporting Information
section lists Text S1–S6 and none was present. A green pre-flight means the
stages will pass work to each other, not that the run will start.

---

## 3. The extraction cache is portable

Verified, not assumed: the cache key is a **SHA-256 of the file's content**, the
payload holds **no absolute paths**, and a machine with Docling's import BLOCKED
still read it and returned the full text. So extraction can be done on a fast
machine and the `.extraction_cache/` directories copied across. A mismatched
transfer misses the hash and degrades to pdfplumber rather than serving the
wrong paper's text.

> The sentence above used to end "the Docling version is stamped in each entry",
> and when I opened the entries it was stamped in ONE of eleven. Three cache
> generations had shipped side by side, and the oldest held **tables only, no
> text** — so `extract_text` fell back to pdfplumber for four of the five
> table-rich medical papers queued for review, while this note said otherwise.
> All were re-extracted; every entry now carries text and `extractor_version`.
> **If you copy caches between machines, check `n_text_chars` and
> `extractor_version` are present** — a tables-only entry is not an error, it is
> an older format, and `cached_text` returns a reason saying so.

---

## 4. What a run costs

Romano, 2026-08-13, with its supplement: **$12.30, 30 minutes** — sweep $8.96 /
1401 s, editorial $3.35 / 413 s. There is **no resume**: a run that dies loses
the sweep as well as the editorial pass. Building stage-2 resume would also make
prompt iteration affordable ($3.35 rather than $12.30 per experiment).

---

## 5. What is still broken — read this before trusting a coverage figure

1. ~~**The completeness manifest is effectively a TABLE manifest.**~~ **FIXED
   2026-08-15, and the diagnosis was wrong.** It was not a weak prose enumerator:
   `_read_body` read publisher XML or `body.md` and nothing else, so a PDF-ONLY
   paper — most of them — was handed no prose at all. Wired to the docling cache,
   Ophir 2009 goes from a manifest of **0 items to 30**, Kross from **0 to 27**;
   papers that ship XML are unchanged because they always had a source. The
   enumerator was never the problem. What REMAINS open is that the enumerator's
   RECALL has never been measured — Romano yields 11 prose items from 56,519
   characters against JAMA's 45 from 23,015, and nobody has established whether
   that gap is the papers or the regex.
2. **The verdict rename is display-only.** Every renderer now maps through
   `verdicts.canonical` — the report body did not until 2026-08-13, so the
   shipped Romano page carried BOTH vocabularies, a chip reading `unresolved`
   above a line reading `Verdict: questionable`. But the schema and the stage-2
   prompt still say `trustworthy / questionable / untrustworthy`, so the model
   is still asked to judge a PAPER's trustworthiness and the label is changed
   afterwards. Renaming the answer is not the same as changing the question.
3. **Run-to-run agreement is 34–64%** (pass@1, Romano, three runs). The interval
   is that wide because matching findings across runs by string is unreliable in
   both directions; an adjudicator is specified but not built.
4. **`n_runnable` is routinely 0** while `n_checked` is not, and both are
   rendered. On Romano: 913 cells extracted, 209 consumable, 0 runnable, 18
   checked. The census and the checker disagree about what "runnable" means.
5. **No tripwire.** Everything above is RECORDED; nothing stops a run when
   information known to exist fails to arrive.

---

## 6. Where the reasoning lives

- `LESSONS.md` — the nine errors this repository keeps making, each with the
  real instance. Read before measuring anything.
- `docs/ACQUISITION_STAGE_SPEC.md` — the proposed pre-pipeline acquisition
  stage, and why the denominator (what we could NOT reach) is its deliverable.
- Module docstrings carry the measurement that justified the code, dated.
  `tests/test_prompt_claims_are_dated.py` enforces the dating and records the
  standing question: *what would the model do differently if this number were
  40%?* If nothing, it does not belong in a prompt.

## 7. Verifying it yourself

```
pip install -e '.[statcheck]'      # docling is now a hard dependency
metascience preflight              # must print READY
pytest -q                          # 5,036 passing, 82 skipped
metascience lint-inert --certain-only   # 28; a ratchet, tested
```

**Run it in parallel and run it in a clean checkout.** Both are load-bearing,
and each caught a defect the other could not.

*Parallel* — the suite defaults to `-n 10 --dist loadfile` and takes ~4m30s.
Two of the defects fixed here appear ONLY under concurrent workers; the most
recent, a provenance record that lost both of its git fields when the first of
two `git` calls timed out, surfaced as one flaky failure that passed in
isolation.

*Clean checkout* — and ideally on a case-sensitive filesystem. Development
happens on `/mnt/c`, which is a Windows filesystem and folds case. Checking the
same commit out on ext4 failed two tests that pass on `/mnt/c`: two
ground-truth DOIs are printed uppercase in the manifest, every directory is
lowercase, and Windows had been quietly resolving the difference. On Linux the
corpus evaluation had been running on 76 of 78 papers and filing the other two
as missing. If you develop on Windows or macOS, a Linux checkout is not a
formality.
