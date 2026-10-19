# Handoff: the paper-summarization track on `best-source-acquisition-2026-09-05`

> **ARCHIVED 2026-10-16.** The paper-account work it hands off landed as `scaffold/` (studies, variables, values, checks, premises); the branch named below no longer exists. `scaffold/` is not wired into the analysis pipeline.

Written 2026-09-08, at the point where the work stopped because the account's weekly model
quota ran out. Everything described here is committed on this branch. Nothing is pushed to
`main` and no PR is open for it.

Audience: Dan, and whichever agent picks this up next. The companion planning documents live
in Greg's Drive folder `academic/metascience_observatory/` and are named inline below; this
file is the part that has to travel with the code.

## 1. What this branch is for

One account per paper: every study, group, variable with its levels, test, and every reported
value, each placed and traceable back to a quote or a table cell. Human-readable and
machine-tractable. The success criterion Greg set is **verifiability, not accuracy**: a good
account is one where a person or an agent can follow any number back to the paper and judge
whether its inputs were valid.

This is the extraction/summarization half of the toolkit. It does not change the forensic
checks, and it deliberately does not read values off figures.

## 2. The one architectural result everything else follows from

**Decompose once.** Measured 2026-09-07 on `10.1002/ajcp.70049`, pre-registered before the run:

| | two full runs | one frozen structure, downstream re-run |
|---|---|---|
| table values with the same variable id | 0.76 | 1.00 (204/204) |
| prose values with the same variable id | 0.67 | 0.94 |
| comparisons (Jaccard) | 0.00 | 1.00 |
| statistic kinds, coefficient tables | 34/55 | 55/55 |

Given the same vocabulary the model selects the same id essentially every time. All the
run-to-run instability lives in passes 1 and 2. The corollary is the cost side: a **wrong**
structural decision is propagated just as faithfully (one column was read `se` in one
decomposition and `sd` in another, consistently each time), so the single decomposition is
the thing that must be adjudicated.

Consequence, now implemented: `scaffold/structure.json` is a versioned artifact with a
`draft -> adjudicated -> frozen` lifecycle. When it exists, passes 1 and 2 do not run, the
downstream vocabulary is closed (an id the structure does not declare is nulled and counted
as `unbound_foreign_id`, never accepted), artifacts from different structure versions cannot
be bound together, and a changed served document is reported as `stale_document` rather than
silently re-decomposed.

## 3. What landed, in order

| commits | what |
|---|---|
| `a4f1f5d` | Headline coverage: `scaffold/coverage.py`, account section 0, numeral floor demoted to "Inventory" |
| `a4f1f5d..da685a4` (9) | The frozen structure: `structure.py`, versions, closed vocabulary, `stale_document`, `--freeze-draft` / `--freeze` / `--redecompose` / `--adjudicate-structure` |
| `da685a4..e21c599` (8) | Code stamps on derived artifacts; verifier stub rule; `non_statistical` table tier; `printed_as` on variables; coordinate completion by caption join; prose denominator keyed on the floor's own classes; `values.csv` export |
| `e21c599..f81a601` (12) | The eleven input-layer defects found by preparing six new papers (below) |

Suite: 9,802 passed at `e21c599`, and **9,870 passed / 0 failed at `f81a601`**, the branch
head (section 7).

### The three headline measures (`scaffold/coverage.py`)
The numeral floor is an inventory, not the headline denominator. The headline is: **table
cells placed**, **statistic-bearing sentences covered**, **declared variables with a value**,
each partitioned into tiers that must sum to the denominator, each split by source
(article/supplement, prose/table). `placed` is strict: it requires the name-join to
corroborate the model's id, and a sub-tier separates corroborated from model-only.

Measured on ajcp run C, recomputed at the shipping commit:

| | before wave 2 | after |
|---|---|---|
| statistic-bearing sentences fully covered | 25 of 49 | 34 of 38 |
| uncorroborated ids on table entries | 78 | 7 |
| corroborated cells placed (article tables) | 65 of 143 | 116 of 143 |
| values with study+group coordinate | 12 | 254 |
| numeral floor `n_total` | 1,051 | 1,051 (unmoved) |

The denominator shrank by **classification**, never suppression: citation years, our own
inlined placeholders, ordinals after "(Table", and phase labels are now classed as what they
are, and p-thresholds already held as comparisons are credited. A test pins `n_total`.

## 4. The eleven input-layer defects (last twelve commits)

Found by preparing six papers of new designs and looking at what the pipeline would actually
have been served. Each was reproduced by a failing test on the real paper before being fixed:

1. Figure captions: the XML rung writes `[Figure 1.: ...]`, the reader anchored on `Figure N`,
   so **zero** captions were found on every figure-bearing paper; figures existed only because
   the PMC image fetch had run.
2. Supplement prose was silently truncated at 50,000 characters (299,183 lost on one paper,
   including every eTable legend) with a marker left inside the served text.
3. A PDF supplement table was rendered as its whole page, so a page holding two tables handed
   the reader a table it was not asked to read.
4. `render_png` clipped at a 5,000 px window with no error (a 237-row table lost its last ~60
   rows silently).
5. A table too large for one call had no reading path; now read in row blocks and verified as
   one.
6. Tables were numbered by position, so a publisher that orders Table 5 before Table 4 got
   both captions joined to the wrong table.
7. The reference list stayed in the served body on the XML rung (49k of 92k characters on one
   paper).
8. Empty walker tables were rendered and queued for reading.
9. Figures and tables embedded as images inside a Word supplement were invisible.
10. A supplement had no role, so a 195,000-character trial protocol was served as results
    prose.
11. A supplement PDF with no extraction cache served zero characters marked UNKNOWN; it is now
    a named refusal, and the numerals of a withheld supplement are counted beside the total.

## 5. The finding to act on first

**On a converted PDF supplement, the walker is not a valid conservation witness.** Reading
`10.1001/jamanetworkopen.2023.37679`'s eight supplement tables produced 1 verified and 7
refused. The refusals are the checker's fault, not the reader's: the walker's text-layer parse
fuses rows, so it holds digit runs like `18915385128668870103079078421099`, while the model
reading the rendered page returned clean cells (`95.3 (93.8-96.8)`). Digit conservation
against a garbage grid can only refuse.

The fix is structural, not another rule: where the source is a converted PDF, conservation
must be against the page's own text layer over the cropped region, or against a second
independent reading of the same image, and the walker's grid must be demoted to a hint. The
same "two independent readings as the conservation rule" appears in the figure-inventory spec
for the same reason (no walker exists there either). This is the fifth time a verifier
refusal turned out to be about the verifier; treat a refusal as evidence about the checker
first.

## 6. How to run it

```
# disk-only re-assembly, no model call, no cost
python -m metascience_agent.scaffold <paper_dir> --no-llm --no-recon --skip-residual

# full run, structure written once and frozen at creation
python -m metascience_agent.scaffold <paper_dir> --freeze-draft --recon-model sonnet --review

# re-run downstream against an existing structure (passes 1 and 2 do NOT run)
python -m metascience_agent.scaffold <paper_dir> --resume --recon-model sonnet

# a new decomposition, keeping the old version on disk
python -m metascience_agent.scaffold <paper_dir> --redecompose
```

Set `METASCIENCE_NO_DB_PUSH=1` when driving the writers: `write_parallel_outputs` pushes to a
live database.

Outputs per paper, under `scaffold/`: `structure.json` (+ `structure.versions/<n>.json`),
`account.json`, `account.md`, `account.headline.json`, `values.csv`, `tables/` (one PNG,
prompt, reading and meta per table), `document.json`, and the pass artifacts.

## 7. State at the moment work stopped

- **Test suite: GREEN at `f81a601`** -- 9,870 passed, 143 skipped, 1 xfailed, 0 failed, in
  12m24s, run 2026-09-08 after the last commit. Reproduce with:
  `rsync -a --delete --exclude test_pdfs <repo>/ /tmp/fmt-suite/ && cd /tmp/fmt-suite && pytest -q -n 4 tests/ --ignore=tests/test_litvak_bench.py`
  (`tests/test_litvak_bench.py` does not collect on Python 3.10; that is unrelated and
  pre-existing.)
- **Two paid runs were cut off by the quota**, and their artifacts are therefore partial:
  the NHANES cohort paper (`10.1093/jncics/pkaf034`) has a frozen structure v1 (14 studies,
  63 variables) and 3 of 14 tables read, the rest carrying `failed: You've hit your weekly
  limit`; the 37679 supplement run completed but with the refusals in section 5.
  **Do not read either as a measurement of the pipeline.**
- **Uncommitted in the tree**: 154 modified binaries under `test_pdfs/`, pre-existing and not
  from this work.
- **`values.csv`, rendered accounts and the readiness table** are staged in the Drive folder
  under `step2_ajcp70049_tidy_2026-09-06/`.

## 8. What is specified but not built

Each has a spec in the Drive folder with tests and gates named:

- `MO-wave3_spec_2026-09-07.md`: the residual pass driven by the coverage measure (serve only
  the uncovered statistic-bearing sentences, ~$1/paper), design templates, and **`summary.md`**
  -- the one-page-per-study human deliverable rendered from the account only, where every
  number is a value id with a trace and an unfilled slot is shown empty.
- `MO-wave4_protocol_2026-09-07.md`: pre-registered protocol for the structural adjudication
  (second reader over a docket the pipeline itself recorded), with five expectations and a
  rule that suspects the gate before the reader.
- `MO-wave5_spec_figures_2026-09-07.md`: a figure **inventory** -- axis labels, legend n's,
  panel structure, statistics printed on the figure -- as transcription, with a schema that
  has no field for a plotted value. It does not reopen reading values off charts.
- `MO-wave6_spec_structure-validation_2026-09-07.md`: score the frozen structure against the
  MO benchmark's registry ground truth. The zero-cost half is **built and self-tested** at
  `/tmp/jats1/tier_t_pilot/` (30-item pilot drawn by the pre-registered hash rule, 30/30
  documents built, scorer with 34 passing self-tests, ~$113 of decompositions to run).

## 9. Gotchas that will cost an agent a day

- **The table-reading prompt's text is part of the reading cache key.** Any wording or schema
  change discards every paid reading. Carry new information in the structure instead.
- **Derived artifacts carry a code stamp** and a render refuses a stale one. A number read out
  of an artifact written by older code is not a measurement of the current code; this bit us
  twice in one afternoon.
- **Never argue from a run older than two weeks** (`metascience runs <paper>` partitions
  them). Archived runs were produced by code that no longer exists.
- **A coverage win must never become a false binding.** An ambiguous join binds nothing; a
  derived boundary may narrow a premise, never supply one; classify a numeral, never suppress
  it.
- **One agent edits the tree at a time**, and a paid run must import from a quiescent
  checkout (use a detached worktree at a known commit).
- The machine has 10 GB of RAM; the xdist suite beside a paid run will tip it over.

## 10. Separate deliverable

`fetch-pdf-from-doi` (now `delton137/fetchpdf-grey`) has an open PR from this work:
**PR #5**, branch `pmc-page-figures-blocked` -- the PMC article page as an HTML source, a
`--pull-figures` retrieval goal (mirror first for original bytes, CDN render second), and
`blocked` recorded distinctly from `none_found`. 694 tests pass there.
