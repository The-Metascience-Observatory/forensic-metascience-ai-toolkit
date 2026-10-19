# Forensic Integrity Hardening

> Written 2026-08-09 as a memo about one set of changes; status notes added 2026-10-16. Sections 1-3 and 5 are the standing principles; sections 4, 6 and 7 are dated.

*Audience: BOTH human reviewers and LLM
contributors (a future coding agent editing this repo, or the forensic agent
reasoning about its own tools). Read this before adding or changing any check
tool, the quote verifier, or an extraction consumer.*

This document explains the single rule this repository is built around, the
recurring way that rule gets broken, the design patterns that enforce it, and
the specific changes (August 2026) that apply them. It is deliberately
principle-first: the individual fixes matter less than the invariants they
protect, because the next contributor will write a new check and needs to know
the invariants, not memorise the fixes.

---

## 1. The cardinal rule

**A false accusation is the worst thing this tool can produce.** A forensic
integrity checker that flags an honest paper is not merely imperfect -- it is
actively harmful, because the output can damage a real researcher's reputation,
and because a tool that cries wolf is correctly ignored. Every design decision
here trades power for safety in that direction. Ranked, worst first:

1. **False accusation** -- we say something is wrong with the paper when it is
   not. Never acceptable. The whole severity architecture exists to prevent it.
2. **False all-clear** -- we blunt or hide a real problem (report `consistent`
   when a check actually found or could not evaluate something). Second worst,
   because it defeats the tool's purpose silently.
3. **Visible refusal / crash** -- we decline or error where we could have judged.
   Wasteful, but honest and self-announcing. Tolerable; fix when cheap.

### The severity ladder

Every check result carries a `severity` from `tools/severity.py`:

`impossible` > `highly_suspicious` > `suspicious` > `indeterminate` > `consistent`

- **`impossible`** is reserved for ARITHMETIC, bound-free contradictions: no
  dataset of any kind could produce the reported numbers (GRIM/GRIMMER
  granularity failures, an SD exceeding half the range, a 2x2 that reconstructs
  for no column split). A simulation or a likelihood argument may NEVER reach
  `impossible`; "unlikely" is not "impossible".
- **`highly_suspicious`** = technically possible but extremely unlikely under
  honest reporting, and only when the null is one the PAPER ITSELF asserts
  (it randomized; it rounded; it ran this test). See `core/prompts/rulebook.md`.
- **`suspicious`** = a discrepancy worth asking about; the likeliest cause is a
  reporting slip, so it is a question, not a verdict.
- **`indeterminate`** = a REFUSAL. A precondition could not be verified, so the
  tool declines. It is not evidence of a problem and not evidence of its
  absence. This is the honest home for "we cannot tell", and it is where a
  misapplied test, a non-finite input, or an unread paper must land.
- **`consistent`** = the check ran and found no discrepancy.

This five-rung enum is the TOOL-level verdict about a number, and it is still
what every tool returns. Since the parallel pipeline (v1.0.0) each FINDING also
carries a 1-9 severity, assigned by the adjudicator, that ranks what a journal
would have to do if the finding were confirmed. The two axes are not derivable
from each other. The ladder is defined in `severity9.py`; `docs/errorlevels.md`
is its prose and `docs/severity_ladder.json` is generated from it.

---

## 2. The recurring failure: the "house failure pattern"

Almost every real defect found in that review is one shape:

> **OUR failure, reported in the grammar of a claim about the PAPER.**

The tool fails on its own side -- a cell would not parse, a decoder broke, a
heuristic excluded a case, an extraction returned empty, an input was NaN -- and
that internal failure surfaces to the reader (or the model) as a statement about
the paper: "impossible", "not in the paper", "no figures", "clean". The reader
cannot tell our bug from the author's error, so our bug becomes an accusation.

Canonical instances that have been found and fixed (in that review and earlier):

- A corruption scanner reporting a file "clean" that it never opened.
- `_page_ink` calling OUR PDF-decoder failure "no artwork on the page".
- `paper_text` swallowing an extraction crash so downstream published a false
  all-clear.
- `check_sd_range` printing "SD of NaN exceeds the maximum" -- false as
  arithmetic (`nan > 3.0` is `False`); the sentence is reachable only down an
  else branch that never asked.
- `reconstruct_2x2` declaring a paper's table "impossible" because OUR balance
  heuristic refused to consider the (ordinary, imbalanced) split that
  reconstructs it.
- The quote verifier telling a reader a sentence "does not appear in the
  paper... searching the PDF will find nothing" about a PDF we never opened
  (only a supplement extracted).

**When you write or review a check, ask: if this branch fires because something
failed on OUR side, does the message read as a claim about the paper? If so, it
is a bug, regardless of how the arithmetic looks.**

---

## 3. The design patterns that enforce the rule

These are the reusable moves. New code should reach for them by name.

### 3.1 Convention-guard: try both conventions before accusing

When a check's verdict depends on a convention the paper did not state, try
BOTH and only flag if the value fails under BOTH. Adopt the reading that fits;
if only the "wrong" convention fails, that is not the paper's error.

- **SD**: sample (n-1) vs population (n) SD. SPRITE/GRIMMER/DEBIT try both.
- **GRIM**: round-half vs truncation. A mean that fails round-half but passes
  truncation is consistent.
- **Estimate/CI scale**: linear vs log. An odds/risk/hazard ratio has a CI
  symmetric on the LOG scale; when the caller does not name the measure,
  `check_estimate_ci` adopts log only if the estimate is the geometric (not
  arithmetic) midpoint -- so an unlabelled or unrecognised ratio (aOR, SMR) is
  not called a midpoint error.
- **2x2 reconstruction**: the column-balance ratio SORTS candidate tables; it
  never gates feasibility. Possibility is decided over EVERY split.
- **chi-squared**: accept Yates OR Pearson for a 2x2; a Yates-reported value
  must not be called impossible by a Pearson recompute.

### 3.2 Caller-classification guards, capped by provenance

Some checks are only valid for a particular kind of data, and only
accusation-grade if the paper stated the bound. The caller must classify, and
the ABSENCE of a classification caps severity:

- **`data_type`** (`integer|likert|count|proportion|binary|continuous|...`):
  GRIM/GRIMMER/DEBIT/grim_percentage REFUSE (`indeterminate`) on the wrong data
  type rather than manufacture an impossibility from an ordinary continuous
  value. `grim_percentage` is valid only for a count-proportion share.
- **`bound_source`** (`stated|logically_necessary|assumed`): a range violation
  against a bound WE assumed caps at `suspicious`; only a bound the paper stated
  (or one logically necessary, e.g. a proportion in [0,1]) licenses
  `impossible`/`highly_suspicious`. Applies to GRIM, the SD-range checks, and
  `check_sd_or_se`'s "neither reading fits" verdict.

Every guard must narrow ONLY the illegitimate case and leave genuine violations
flagged. A guard that also silences a real detection (a false all-clear) is a
regression -- verify both directions with a real counterexample.

### 3.3 Non-finite and extraction-artifact refusal

A reported statistic is never NaN, infinite, or the string "N/A": those come
from OUR failures (an empty cell, a dash, a footnote marker, a divide-by-zero).
`severity.refuse_if_nonfinite` is called at the top of the raw check functions,
and the registry gate (`ToolSpec.call`) refuses non-finite input across the MCP
surface. A batch check guards each row so one poison cell cannot crash the whole
table's coverage. The correct response to garbage is `indeterminate`, never a
verdict.

### 3.4 Quote verification: only located text may claim to be "As printed"

`quotes.py` verifies each finding's `quote` against a haystack built from the
paper, stamping `quote_verified`:

- `verbatim` / `elided` -- the text was LOCATED; only these may render as "As
  printed", the promise that a reader can go and find it.
- `stitched` -- every number is in the paper but the sentence was assembled by
  the review; it must say so, not pass as a quotation.
- `unverified` -- OUR search failed; phrased as a fact about our search, never
  about the paper.
- Numbers are matched by VALUE, not by a fragile tokenizer: APA decimals
  (`.99`), signs, and thousands groups are handled, and a number may not match
  inside a larger one (`.86` is not found in `40.86`).
- **Partial-haystack rule**: if none of the PRIMARY paper sources (body text,
  XML, PDF text layer, figure caption) loaded -- only a supplement -- negative
  verdicts are WITHHELD, because "not in the paper" would be a claim about text
  we never read.

Verdicts are set by the pipeline, never by the model; model-authored
`quote_verified` is stripped first, unconditionally.

### 3.5 A parser is not a check

`parse_table` and `parse_cells_typed` READ a grid; reading says nothing about
whether the paper is right, so their own severity is `indeterminate`. A verdict
appears only when a cross-check runs (two extractions agreeing or disagreeing),
and that reconciliation verdict is lifted to the top level. A parser that
returns `consistent` is a false all-clear -- and, via the reconcile ledger, can
publicly discredit a correct finding.

---

## 4. What changed in the August 2026 review (grouped)

Each change is a false-accusation fix, a false-all-clear fix, a coverage fix, or
the primary quote-traceability feature. All are pinned by tests.

**Primary feature -- quote traceability**
- Findings carry a pipeline-verified verbatim quote; `report.md` surfaces the
  backing verified quote, not just the model's restatement.
- The quote number-matcher matches by value (APA decimals, signs, thousands,
  no-match-inside-a-larger-number).
- Partial-haystack rule: do not say "not in the paper" when the paper was not
  read.

**False-accusation fixes**
- `se_sd` bound_source cap; `grim_percentage` data_type gate; the non-finite
  input guard across the raw check functions; `check_estimate_ci` scale
  inference for unlabelled ratios; `reconstruct_2x2` treats balance as a sort,
  not a feasibility gate; SPRITE/GRIMMER population-SD convention; GRIM
  truncation; DEBIT percent-scale guard; STALT/chi-squared judged against the
  claim; `flag_round_n` capped at `suspicious`.

**False-all-clear / coverage fixes**
- `parse_table` renders no verdict of its own and lifts the cross-check verdict;
  `check_summation_batch` survives a poison cell; the `--figures` flag is
  actually forwarded so the announced figure pass runs.

**Legibility**
- Coded verdict/severity words are defined at the point a non-expert reads them.

---

## 5. Checklist for an LLM (or human) adding or editing a check

1. On non-finite or non-numeric input, return `indeterminate`. Never a verdict.
2. If the verdict depends on a convention the paper did not state, try both and
   flag only if it fails under both (Section 3.1).
3. If the verdict depends on a caller classification (data type, bound source),
   REFUSE or CAP when the classification is absent (Section 3.2). Do not assume
   the accusing reading.
4. `impossible` is arithmetic and bound-free only. Anything resting on an
   assumed bound, a reference measure, or a distributional model caps at
   `suspicious` (and simulation/likelihood never reaches `impossible`).
5. If your branch can fire because something failed on OUR side, its message
   must say "we could not X", not "the paper lacks X" (Section 2).
6. Add a test for BOTH directions: the legitimate case is no longer accused AND
   a genuine violation is still flagged. A one-directional fix that silences a
   real detection is a regression.
7. A parser returns `indeterminate`; only a check returns a verdict.

---

## 6. Validation

- Use the interpreter the `metascience` console script points at. Run
  `metascience-test -q` (or `--stack` for the full local stack) before pushing;
  the suite has grown far past the 2,760 tests it held when this was written,
  so use `python -m pytest tests --collect-only -q` for the current count.
  Never commit red.
- `metascience preflight` must print `READY` (it catches a missing `statcheck`
  or an unreadable-supplement toolchain gap that would otherwise produce
  confidently wrong coverage).
- Tools are cross-checked against the canonical R packages (`rsprite2`,
  `scrutiny`) where an oracle exists; an rsprite2 raise is `indeterminate`,
  never `impossible`.
- Numeric consistency claims are validated against the ground-truth corpus in
  `eval/ground_truth/` (adjudicated fraud + matched controls). The gate for any
  accusation-grade detector is its FALSE-POSITIVE RATE on the clean controls.

---

## 7. Known-open and deferred (do not silently "fix")

- **`provenance_quote` laundering** -- CLOSED. As written: a model-authored
  `provenance_quote` on an anatomy variable was not verified, and
  `confidence=high` mapped to `bound_source=stated`, which could uncap severity
  to `impossible`. Now `Variable.bounds_are_stated` (`anatomy.py`) requires
  `confidence == "high"`, a `provenance_verdict` of `verbatim` or `elided`, and
  (since 2026-08-11) a quote that actually mentions the declared bounds.
  `provenance_verdict` is in `anatomy.PIPELINE_ONLY_FIELDS`, so a model-supplied
  value is stripped on every construction path, and `dispatch.py` sets it from
  the paper's own text before the checks run -- i.e. at the point the forensic
  kwargs are built, as this entry asked.
- **Simulation-based plausibility ("possible but unlikely")** -- a full design
  memo exists (see the project working notes). Verdict: GO on three narrow forms
  anchored to a paper-asserted mechanism (rounding, randomization, test
  computation); a naive `N(mean, SD)` simulator is a measured accusation
  generator (90x nominal false-positive rate on honest bimodal Likert data) and
  must NOT be built.
- **Measured negatives** (do not build): a "flagged number is not in the quote"
  check (the reported field is an evidence bundle, not the flagged number; true
  failure rate measured at 0); a structural "is this a paper" heuristic (biased
  against non-English papers).
- **Accuracy claims** -- CLOSED. The unsourced "end-to-end precision ~1%"
  figure was removed from the disclaimer and replaced with a qualitative claim
  plus a measured one (half of the clean control papers carry at least one
  statcheck inconsistency); `tests/test_disclaimer.py` asserts it stays gone.
