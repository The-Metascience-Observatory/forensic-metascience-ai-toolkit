# Litvak planted-error benchmark -- FMA harness

Set up 2026-08-22 at Dan's request ("set up the code so it can be run easily,
but don't run yet, I'm still iterating on the agent code base").
Reviewed and corrected 2026-08-23; see "What was wrong the first time" below.

**NO PAID ANALYSIS HAS BEEN RUN.** These scripts prepare, verify and score;
they never invoke the review pipeline. `score.py` does make cheap Haiku calls
unless you pass `--no-judge`.

## Run it

```bash
# 1. build FMA paper directories from the .docx manuscripts
python benchmarks/litvak/prepare.py --which modified
python benchmarks/litvak/prepare.py --which original     # the clean control

# 2. CHECK THE TABLES SURVIVED. Not optional -- see "Conversion fidelity".
for d in ~/fmt-litvak/modified/litvak*; do metascience extract-tables "$d"; done
python benchmarks/litvak/verify_tables.py ~/fmt-litvak/modified

# 3. analyse  (THE PAID STEP -- only when Dan says the codebase has settled)
metascience batch ~/fmt-litvak/modified --backend claude

# 4. score
python benchmarks/litvak/score.py ~/fmt-litvak/modified
python benchmarks/litvak/score.py ~/fmt-litvak/original --control
```

Paths are resolved, not hardcoded: the benchmark checkout is found as a sibling
of this repo, or via `--bench` / `$LITVAK_BENCH`. Output goes to `~/fmt-litvak`
(or `$LITVAK_OUT`), outside the repo, so the corrupted manuscripts cannot be
committed.

## What it is

Paul Litvak's benchmark: **100 methodological and statistical errors planted by
hand into 10 open-access psychology papers**, 10 per paper, with
`error_insertions.csv` giving the exact before/after text of each. MIT
licensed, Copyright (c) 2026 Paul Litvak; quoting it in the grant application
is permitted with attribution.

Litvak's headline results: best single system GPT-5.5 at 71/100, union of 14
configurations 93/100, Reviewer3 worst at 30/100. All 7 errors nobody caught
are omissions.

## READ THIS BEFORE REPORTING ANY NUMBER

**The 100 errors are 10 in each of 10 categories. FMA's declared territory is
`statistical_errors` + `internal_consistency` = 20 of them.**

A flawless FMA run scores **20/100**. Against GPT-5.5's 71/100 that reads as
catastrophic failure while actually measuring scope. `score.py` never prints a
/100 headline and puts the 20-item denominator beside every rate.

Verified rather than assumed (`tests/test_litvak_bench.py`): the 20 are exactly
two per paper, one from each in-scope category, and **no** out-of-scope row
carries an in-scope *secondary* category, so nothing is hiding elsewhere.

`score.py` nonetheless scores **all 100** and prints a per-category table. The
scope claim was an assumption, and FMA's science-error analyst covers
methodology and contradictions -- which plausibly reaches
`methodological_design`, `reporting_completeness`, `analytic_flexibility` and
`attrition_missing_data`. The eight out-of-scope rows are labelled
`calibration`: they are scored to test the scope claim, not as a score.

## Two decisions that shape the result, both deliberate

**We do not use the benchmark's own converter.** `benchmark/docx_to_pdf.py`
renders a flat text PDF and says so: "This sacrifices original page layout ...
in favor of content-equality". Correct for the prose-reading LLM reviewers
Litvak scored; wrong for FMA, whose checks live in tables. Our input is
therefore NOT identical to what his systems saw -- a real difference that must
be stated wherever a number from this run appears.

**The originals are a clean control -- a REPLICATION, not a first.** An earlier
version of this file claimed "Litvak reports no false-positive measurement and
says so", and proposed ours as "the first published on this corpus". Both are
false. He ran all ten originals through every provider:
`benchmark/reports/summary.csv` carries an `*_originals` row for each, and
`benchmark/ANALYSIS_LOG.md` builds an `adjusted = modified - originals`
leaderboard from them.

### HIS RAW SCORES ARE INFLATED, AND SO WOULD OURS BE

This is the single most important thing to know before quoting any number from
this benchmark, ours included.

Nothing is planted in the ten unmodified papers. So every "detection" a system
scores there is the judge matching a finding to **nothing** -- a direct
measurement of the matching procedure's false-positive rate. Those numbers are
not small, and they scale with how much the system writes:

| system | findings | detected | on CLEAN papers |
|---|---:|---:|---:|
| GPT-5.5, no reasoning | 704 | 66 | **34** |
| GPT-5.5, high reasoning | 512 | 71 | **24** |
| Claude Sonnet, no thinking | 356 | 60 | **28** |
| Reviewer3 | 125 | 30 | **9** |

Across his 14 systems, **r(findings emitted, false positives on clean papers) =
0.726**. The judge credits a system roughly in proportion to its output volume.

**Applying his own correction moves the field by up to five places.** GPT-5.5
high-reasoning, the headline "71/100", adjusts to 47 -- still first, but its
lead over Refine.ink shrinks from 14 to 9. Below it the order changes
substantially: GPT-5.5 no-reasoning falls 2nd to 7th (66 raw, 34 false
positives), Refine.ink rises 6th to 2nd, Opus 4.8 high-thinking 8th to 4th.
`tables.py` prints both leaderboards for that reason.

One system, `openai_gpt54_high_reasoning`, cannot be adjusted at all: its
originals run covers 4 of the 10 papers, so its false-positive count is
understated by about 60%. Litvak excludes it from his own head-to-head, and so
do we -- scoring it 56 - 6 = 50 would rank it FIRST on an incomplete
denominator. (The first version of our table did exactly that. The test that
now pins it is `test_an_incomplete_baseline_is_refused_not_scored`.)

None of this is a criticism of Litvak -- he measured it and published the
correction. It is a criticism of quoting his raw headline, which is what a
reader who has only seen the README will do.

**Our own adjusted score does not exist yet.** We have no clean-control run, so
our row reads `not computed`. Until it exists, our 49 is a raw number and can
only honestly be compared with other raw numbers -- and even that is imperfect,
since FMA emits 206 findings against GPT-5.5's 512, so the volume bias is not
equal. Running the ten originals is the highest-value paid work outstanding:
about $17.50 with grok at the measured $1.75/paper.

Caveat that travels with the control when we do run it: real papers contain
real errors, so a flag on an original is not automatically a false positive.
Report it as "flags per clean paper, N adjudicated by hand". Litvak records the
same point -- about 15% of matches on originals are unavoidable overlap with
genuine issues.

## Conversion fidelity -- MEASURED PER PAPER, never inherited

`verify_tables.py` compares each converted PDF's extracted tables against the
`.docx` read directly (which needs no layout model, so it is ground truth) and
reports whether the **column breaks** survived, not merely whether the header
text is somewhere on the page.

It exists because the LibreOffice run failed. Measured across all ten
originals, 2026-08-23:

| verdict | papers |
|---|---|
| tables damaged | 5 — litvak01, 04, 05, 07, 09 |
| not comparable (the `.docx` tables carry no header row) | 5 — litvak02, 03, 06, 08, 10 |
| intact | **0** |

Paper 1's correlation table, the clearest case:

| | `.docx` ground truth | LibreOffice PDF via docling |
|---|---|---|
| tables | 1 | 6 (5 spurious: title block, reference lists) |
| header row | `SDO / RWA / WILL` | `SDO / 'RWA WILL'` — two columns merged |
| row labels | column 0 | displaced to the end of the row |
| `α` | `α` | `\uf061`, an unmapped private-use glyph |

Damage is partial, not total: litvak09 is 12 tables intact and 5 damaged,
litvak04 is 1 intact and 2 damaged. Grid cells are NOT missing — the PDFs carry
more of them than the `.docx` does (211 vs 20 on paper 1, since docling promotes
layout blocks). **The loss is column structure, not content**, which is worse
than absence: a shifted column label hands GRIM/GRIMMER a triple the paper never
reported, whereas a missing table merely narrows coverage.

**Do not report recall from a corpus `verify_tables.py` calls damaged** — that
number is about the converter, not about FMA.

`prepare.py` picks Word over COM where `powershell.exe` is reachable and
LibreOffice otherwise, and **records which one ran** in `prepare_meta.json`. A
Word number and a LibreOffice number are not interchangeable.

If neither converter preserves the tables, the open alternative is to build the
paper directory from the `.docx` itself: `extract_supplement` reads it perfectly
(1 table, 12 cells, correct headers, no spurious blocks), and its text carries
**no** table content, so a `body.md` plus the `.docx` would duplicate nothing.
That is a change to the ingestion path and has not been made.

## Why the `.docx` is NOT copied into the paper directory

It used to be, "to keep the source beside it". But `agent._resolve_paper_inputs`
sweeps every top-level non-pdf/xml/html/md file into `si_readable`, and `.docx`
is in `_SI_READABLE` -- so each paper was fed its own manuscript **twice**, once
as extracted PDF and once as OOXML. Every table then had a byte-identical twin
in the "supplement", and `detect_duplication` escalates at three matching pairs.
That manufactures a duplication finding on all ten papers, **including the ten
clean controls whose entire purpose is measuring false positives**. Same class
as the `panels/` re-ingestion invariant in CLAUDE.md. The source path is
recorded in `prepare_meta.json` instead.

## What to expect, written down in advance

Measured from the ground truth, corrected 2026-08-23:

- **ONE is squarely deterministic** -- `p_value_inconsistent`: p .033 -> .003
  where chi-square(3)=8.74 gives .0330. statcheck's own job.
  **Not two.** `model_results_contradiction` was listed here as the second and
  is not: the modified text reports chi-square(1)=2.34, p=.126, and
  chi-square(1)=2.34 really does give p=.1261, so statcheck **passes** it. The
  catch is that the prose still calls SDO the stronger predictor after the test
  stopped saying so -- a text-vs-number contradiction, the science analyst's
  beat, not a recomputation.
- **~6 need the register plus a text-to-table cross-reference** --
  `exclusion_criterion_removed`, `coder_count_changed`,
  `analysis_count_inconsistent`, `iatrogenic_means_reversed`,
  `effect_direction_reversed`, `stopping_rule_changed`.
- **~6 need domain reasoning no check can do** -- a tool cannot know that `a*d`
  is the wrong serial-mediation formula.
- **1 is a true deletion** (`fisher_z_removed`); the other 19 are in-place
  alterations. Every error no system in Litvak's test caught was an omission,
  and we have only one.

Stating this first means the result cannot be reinterpreted afterwards.

## How scoring works

Two matchers, reported separately, and the rows where they disagree are printed.

**`judge`** is Litvak's own protocol, ported: his `JUDGE_SYSTEM` **verbatim**
(pinned by a test against his `matching.py` -- it is the comparability surface
with his fourteen configurations), one call per finding against that paper's ten
errors, first-claim-wins one-to-one assignment. Transport is
`claude -p --model haiku` rather than an API call, so **no API key is needed**;
the ten-error block goes in the system prompt so the CLI's automatic prefix
caching can cover it, and answers are cached on disk.

Two bugs in his implementation are deliberately **not** ported:
- `except Exception: result = "none"` scores a transport failure as a miss --
  our fault rendered as the system's. We record `judge_error` and count it.
- his cache key is `hash((desc[:150], quote[:150]))`, and `hash()` on a str is
  salted per process, so the cache silently misses on every restart. We use
  sha256, and include the prompt so a prompt edit invalidates it.

**`floor`** is deterministic (normalised quote or number-set overlap), free, and
a genuine lower bound. `--no-judge` runs it alone.

Only `outcome: problem` rows are eligible to match. **A `pass` is a check that
ran and CLEARED the value** -- counting one as a detection scores the benchmark
backwards, which is what the first version did.

## What was wrong the first time

All of it measured, all of it now pinned by `tests/test_litvak_bench.py`:

1. `outcome` was never filtered, so a tool that checked the planted CI and
   cleared it was credited with catching the planted error.
2. The CSV's `paper` column was never read and findings were `rglob`bed
   corpus-wide, so an error planted in paper 3 could be hit by a finding in
   paper 7. Litvak's scorer is strictly per-paper.
3. One finding could claim all twenty errors; his assignment is one-to-one.
4. `rglob` merged every `forensic_review_*` sibling, so a superseded run
   inflated the current one.
5. `fisher_z_removed` has an empty `modified_snippet` (it *is* the deletion) and
   both match paths were guarded on non-empty text -- an automatic miss still
   occupying a slot in the denominator.
6. The docstring claimed the matcher "over-counts nothing". Measured on the 20
   in-scope rows: **8** have a 60-char prefix identical to the *unmodified*
   original, so a finding about anything in that region scored as a hit; **9**
   have identical number sets before and after; **8** have no usable numbers at
   all; **4** carry curly quotes, en dashes or Greek that no PDF round trip
   preserves, against a matcher that did no normalisation.
7. The blob read `summary`/`evidence`/`explanation`, none of which exist in
   findings-v2, and skipped `reported`/`computed`/`inputs` -- the fields that
   actually carry a check's numbers.
8. Both scripts hardcoded `/mnt/c/Users/gregs/...`, which does not exist on a
   native Linux checkout; `score.py` died on the CSV before printing anything.

## Housekeeping

- **Stamp every result with the commit.** `score.py` prints it. A benchmark
  number quoted in a grant application will sit in a document for months.
- **The modified papers are deliberately corrupted and watermarked.** They must
  never enter the FMA corpus or be cited as literature.
- Re-scoring is free: the judge cache is keyed on content, not call order.
