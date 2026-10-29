# Design decisions and open considerations

> Written 2026-07-28, last revised 2026-10-19. A dated record: where it disagrees with CLAUDE.md or the code, they win.

> For the cardinal rule (no false accusations) and the recurring failure
> patterns every check must guard against, see [AGENTS.md](../AGENTS.md) and
> [LESSONS.md](../LESSONS.md); the severity ladder is
> [errorlevels.md](errorlevels.md).

A log of choices that were made deliberately, choices that were deliberately
NOT made, and questions still open. Rationale for individual mechanisms lives in
the code and in commit messages; this file exists so a decision can be
*revisited* without excavating them.

Each entry says what was decided, what it rests on, and what would change it.

---

## OPEN — awaiting a decision

### Fetching what a paper links to

**Status:** not built. `--artefact` accepts a file the operator supplies;
nothing reaches the network.

**Consideration.** Auto-fetching turns "analyse this paper" into "make requests
to third parties on the authors' infrastructure" — a different act with
different consequences, and one the person running the tool should choose
rather than inherit. There is also a reproducibility cost: a fetched artefact
makes a run depend on the state of a remote repository at run time.

**What would change it:** an explicit opt-in flag, and a decision about caching
so a re-run is not a second request.

### Registry lookup (`--check-registry`)

**Status:** proposed, not built. More valuable than generic fetching.

**Consideration.** Querying ClinicalTrials.gov for a detected NCT returns the
REGISTERED primary outcome. That is what actually enables the outcome-switching
check; the current preregistration reporting can only say the comparison is
*possible*. Same for PROSPERO and ISRCTN.

This would be the first network-dependent check in the toolkit, so it needs the
offline discipline the citation work already specified: no network must return
`indeterminate`, never a negative result.

### Citation and retraction checking

**Status:** researched in detail, not built.

**Findings that should survive:**

- **Retraction is the item to build first.** It is a fact with a citable source
  rather than an inference, so there is no false-accusation risk. Crossref's
  `updated-by` field unions publisher-deposited retractions with Retraction
  Watch; the RW CSV alone caught only **8 of 14** retractions in this corpus.
- **5 papers in this repo's own corpus are themselves retracted**
  (`10.1007/s00401-008-0407-x`, `10.1007/s12035-017-0742-9`,
  `10.1007/s12035-017-0747-4`, `10.1186/1471-2202-15-90`,
  `10.1186/s12868-015-0218-7`). One free API call per paper surfaces this.
  **17 of 323 papers (5.3%) cite at least one retracted work.**
- **Do NOT build fabrication detection on "not found in Crossref".** Measured
  false-positive rate on this corpus is 10–22%: the failures are books,
  chapters, non-English work and GROBID-truncated titles. Of 18 sampled
  unresolvable DOIs, ZERO were plausibly fabricated — every one was PDF
  character corruption, e.g. `10.1001/ja-maneurol.2019.1313` where a line-break
  hyphen landed inside "jamaneurol". Two independent 2026 teams found the
  binding constraint is false-positive rate, not recall, with the best
  published cascade at FPR ≈ 0.46.
- Claim-support verification ("does this reference support what it is cited
  for") is **unsolved**, not merely hard. Do not build it.

### Table serialization — belongs in `pdf2mdjson`, not here

**Status:** diagnosed, fix is in Dan's repo. **Needs re-measurement (2026-10-16).**
The measurements below were taken on the pdf2mdjson Markdown pipeline. PDF table
cells now come from docling's own grid: `extraction/docling_tables.py` reads
`TableCell.text` from `data.grid` and falls back to the DataFrame export and
only then to Markdown. That should avoid the `tabulate()` reparse, but the
13.4% / 2,121-cell figure and the en-dash count have not been re-measured on the
current extractor, so this is not recorded as resolved.

**Consideration.** `docling_core`'s markdown serializer calls `tabulate()`
without `disable_numparse=True`, so an all-numeric column is re-parsed and
reprinted: **`71.0` becomes `71`**. Reproduced end-to-end, and in the shipped
corpus (`8.0` → `8` where Docling's own `TableCell.text` holds `8.0`). 13.4% of
papers, 2,121 cells. Every one gives a granularity check a rounding interval
computed from the wrong number of decimals.

Docling's **JSON, HTML and DataFrame exports are all lossless**. Only Markdown
is lossy, and the pipeline chose Markdown. The fix is a serialization change,
not a re-extraction — about 45 minutes of CPU for the corpus.

Separately, every en-dash inside a table cell becomes an ASCII hyphen (zero
survive across 305 papers), so a minus sign is indistinguishable from a range
separator.

### `check_regression` batching

**Status:** done. `check_regression_batch` (`tools/regression.py`, registered in
`tool_specs/regression/`; run it with `metascience tool run
check_regression_batch --json ...`) checks every coefficient
in one call, reports the worst row, and re-runs across probe dfs when the df is
not reported. The motivating measurement: 79 of 111 stage-1 calls on one paper
(serial pipeline, deleted in v1.27.0) were `check_regression`, one per
coefficient. Third instance of the pattern, after `check_table` and
`check_summation_batch`.

### Image-result reset: paid screening ledger and furniture set

Moved 2026-10-16 to the image analysis package, which now owns `disk_plan`:
see `docs/workbench_image_review.md` there, under "Image-result reset decision
(moved from DESIGN_DECISIONS)". Still open.

---

### Composite granularity — refuse, or plumb `items` through?

**Status:** PARTLY RESOLVED (checked 2026-10-16). `dispatch._is_composite` now
decides on `derivation` before family: a composite declared `sum_of_items` is
dispatched to GRIM at 1/n, which is the correct granularity for an integer
total. It still refuses a composite declared `mean_of_items` (whatever its
family) and a `likert_composite` whose scoring is undeclared, because
`grim_test` still has no `items` parameter. The open part is plumbing `items`
through for the mean-scored case.

**Consideration.** A mean of k items moves in steps of 1/(k·n), not 1/n, and
`grim_test` has no `items` parameter — so dispatching a composite uses the
wrong denominator and returns `impossible` on ordinary values. Refusing is
correct today. Now that `derivation` and `n_items` are captured per variable,
running the check with the RIGHT denominator is available and would recover
real coverage.

---

## DECIDED — and why

### 2026-10-18: the harness GRIM sweep files its failures as findings

**Decided (Dan, 2026-10-18):** GRIM failures found by the harness sweep
(`grim_harness`, wired in `prepass.run_exhaustive`) are written into the
review as findings, one per table, producer `harness`. This reverses, for this
one sweep, the rule in `prepass.py` that harness sweeps record coverage and
never append findings.

**Why.** On the dev half of the GRIM ground truth the tools agent checked 38 of
135 known-bad values and flagged every one it checked: the misses were values
nobody tested. A sweep that tests every cell but files nothing would leave the
same 97 values out of the report. The rule existed so a machine would not
write accusations from premises nobody established; here the premises are the
tools agent's own `declare_table` declarations (row variables, shares, n's),
read back from the run, and a cell whose premise is not declared is counted
and never checked.

**Bounds.** Severity is provisional and at most `highly_suspicious` (4), never
`impossible`; a failure that a slightly smaller n (within 5%, the non-response
window `dispatch` already uses) explains is filed at `suspicious` (3) and says
so; a sparse row under columns of different n is refused (docling places a
spanning value under the wrong subcolumn); a paper declaring a complex survey
is refused whole. The duplication and sd_range sweeps are unchanged.

### SUPERSEDED 2026-10-18: a missing supplement warns and runs

**Decided (Dan, 2026-10-18):** a paper that cites supplementary material we do
not hold is analysed, with a printed warning and a limitation in its report
naming the missing items. Blocking threw away every check the main text
supports -- the GRIM ground-truth batch skipped a paper whose GRIM failures are
all in the article. An unreadable article (no text at all) still refuses, in
`analyze` and `batch` alike. `--ok-if-supplementary-missing` is a no-op kept
for old scripts. The record below is the decision this replaces.

### (Superseded) The supplement gate BLOCKS; the missing-repo case does not

**Decided:** `analyze` refuses (exit 2) when a paper cites supplementary
material that is not present, unless `--ok-if-supplementary-missing` is passed. A
missing code repository is reported but never blocks.

**Why the asymmetry.** A missing supplement *manufactures findings*: this tool
reasons about what a paper does and does not report, so an absent eTable is
indistinguishable from a statistic the authors never reported, and the run
produces "no sensitivity analysis reported" as a charge against them for the
operator's omission. A missing repository degrades nothing — no check in the
sweep reasons about code — so blocking on it would be ceremony rather than
protection.

Measured: 76% of the high-value corpus cites a supplement and essentially none
is on disk, so the gate excludes 69 of 95 papers. That number is stark and
correct.

### No run-spec / configuration layer

**Decided:** not building it. **Evidence:** measured guard supply on a live
Opus run was **92.9%** (65/70 slots) — the model passed `measure` on 59 of 64
`check_estimate_ci` calls and 6 of 6 `absence_of_evidence` calls, and did so
*before* `measure` was even marked as a guard.

**Caveat on the evidence:** only two guarded tools were exercised on that paper,
both on `measure`. It is strong evidence for one guard type, not for
`data_type`, `design` or `bound_source`. Revisit if a run shows those defaulting.

**Scope (2026-10-16):** pipeline YAML (`pipelines/*.yaml`, `--pipeline`) now
configures which modules a run uses and the tools agent's toolset; this entry is
about per-call guard parameters, which are still supplied by the model, not by a
run-level spec.

### Do NOT migrate to a VLM extractor

**Decided.** The corpus is **100% born-digital** — zero scanned PDFs, 97.7%
with healthy text layers. Every VLM (olmOCR, MinerU's VLM path, Nougat,
MonkeyOCR) *generates* numbers token-by-token rather than copying them, which
converts a solved problem into a hallucination risk. olmOCR-2 has documented
digit corruption (`84-89`→`84.89`, `61.6`→`74.6`) — verdict-flipping errors.
MinerU silently falls back to generative OCR on private-use-area text, i.e. on
subsetted maths fonts.

**Clarification (2026-10-16).** This decision is about the default reader and
stands: docling reads every PDF. But the corpus claim did not survive in one
respect. 7.2% of the 305-paper cerebrolysin corpus carries font-encoding
corruption touching a number (undeclared glyph mappings that every text-layer
extractor inherits), and on those papers a pixel reading recovers what the text
layer lost. So `extraction/mistral_tables.py` reads a cached Mistral OCR
extraction of the page images, and `prepass._text_layer_lies` prefers it for a
file's tables only when `glyphs.scan` finds corruption in that file's docling
text. The choice is per file and fails closed to the text layer; the Mistral
extraction is produced out of band (the module makes no API call) and every
table it supplies is stamped `extractor: "mistral"`. The generative-number risk
described above is accepted only where the text layer is known to be wrong.

**Correction on record:** MonkeyOCR was recommended earlier in the session on
the strength of beating Docling on Table-arXiv (0.78 vs 0.69 F1-TEDS). That
recommendation was withdrawn once the born-digital finding landed: the
benchmark advantage is real but measures a task this corpus does not pose.

### Precision over coverage in the glyph quarantine

**Decided.** Two candidate pattern sets flagged 49.6% and 60.3% of the corpus
and were discarded; the shipped set flags 9.9%, with 5.0% quarantine-grade.

**Why.** `157 (60.2)` is an ordinary n(%) cell, `231 099` is a narrow-space
thousands separator, `1991. 19 We enrolled` is a superscript citation and
`10.1186/s13293-020-00299-3 . 49` is a DOI. A "space around the decimal point"
rule cannot separate real corruption (`1.517 (0. 613-3.753)`) from any of them,
so it was dropped rather than shipped noisy. **A quarantine that fires on half
the corpus tells the reader nothing.**

### `role` removed from the variable schema

**Decided.** A variable is the outcome of one model and a covariate in the next,
so role is a property of the (variable, test) PAIR. It was also redundant —
tests already carry `outcome_var` and `predictor_vars`.

### Preregistration: silence is weak evidence, never absence

**Decided.** Three states, with `not_mentioned` distinct from
`explicitly_not_preregistered`. Registration statements sit in funding and
data-availability sections that extraction routinely drops, so reporting
silence as "not registered" would be an accusation drawn from our own gaps.

A registered study is never reported as cleared: comparing the registered
primary outcome to the reported one is the check this *enables*, and it is not
automated.

### Tool merges: three were real, four were guard-parity bugs

**Decided.** Of seven candidate merges, only `parse_table`→typed cells,
`debit_check_batch`→`debit_check` and `recalc_*`→`rivets_*` were genuine. The
other four (`grimu` pair, `csf`/`dispersion`, `check_estimate_ci`/
`absence_of_evidence`, the GRIM family) answer *different questions* — merging
them would have destroyed capability. What looked like redundancy was missing
guards, now fixed.

### `check_table` relocates discretion, it does not remove it

**Recorded as a known limitation.** The model still authors `raw`, `row_label`,
`variables` and `provenance`. Relabelling a cell flips the verdict to
`impossible`; declaring a 9-item composite as `likert_item` bypasses the
refusal built to prevent exactly that. This is *worse* for auditability than
per-tool calls in one respect: a wrong tool choice is visible in the call log,
a wrong `row_label` is indistinguishable from what the paper printed.

Mitigation would be recording model-authored labels in the audit trail. Not
built.

---

## PUBLICATION AND EXPOSURE

### `benchmarks/paper_reviews/papers/` is not publishable

Three hand-written reviews naming live, non-retracted papers by URL with strong
conclusions; third-party authored; alongside publishers' copyrighted PDFs. The
repository is private, which is the only thing containing this. **Making it
public would publish them retroactively via git history** — removal at that
point requires rewriting history, not deleting files. See that directory's
README.

### Licence

The PolyForm Noncommercial License 1.0.0 plus three additional terms (see
`LICENSE`): no commercial use, written permission before analyzing more than
500 papers, and attribution: published work that uses the toolkit or its
output must cite it (`CITATION.cff` gives the form), and derived works must
say they are based on it. PolyForm's `Required Notice:` line covers copies.
**It does not cover the
publishers' PDFs** stored in the corpora — the code licence cannot license
third-party articles.

### A publishable gap: no benchmark measures printed-form exactness

**TEDS uses normalised Levenshtein per cell**, so `"71.0"` vs `"71"` costs half
a node divided across the whole table — a table 100% wrong for GRIM routinely
scores TEDS > 0.95. TEDS-Struct ignores content entirely. olmOCR-Bench
explicitly maps em-dash to hyphen. And no published study measures
GRIM/GRIMMER/SPRITE false-positive rates attributable to extraction error;
every canonical application used manual transcription.

A **printed-form exactness** metric where `71.0 ≠ 71` and `−0.34 ≠ -0.34`,
reported as verdict-flip rate by extractor on a labelled set, is a real
contribution nobody has made — and is directly the §3b "prove it small before
scaling" deliverable.

---

## CORRECTED CLAIMS

Numbers previously published in this repo that were wrong:

| Claim | Was | Is |
|---|---|---|
| Table recovery from PDF | 15% | **82.8%** (786 tables, 400 papers) |
| statcheck applicability | "a property of the literature, not of the tool" | partly OUR artefact — unescaping HTML entities recovers **+45% statistics, +20 papers** |

The more useful correction to the first: structural recovery was never the
problem. **PAIRING is** — on one JAMA table, 26% of `estimate (95% CI)` pairs
were destroyed while ZERO of 85 numeric tokens went missing. Any validation
asking "did this number appear anywhere" reports ~98% recall on a pipeline that
cannot support GRIM.
