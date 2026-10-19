# Plan: last-digit preference on individual observations (Carlisle 2021)

Status: **proposed, not started** (2026-10-16). Supersedes `DIGITS_HANDOFF.md`
(2026-08-22), whose constraints are carried forward here and whose wiring
steps are updated to the post-refactor layout (toolkit 1.77.0).

## Where things stand

There is no trailing/terminal-digit tool, and that is a recorded decision:
`core/prompts/rulebook.md` rule 8 forbids reasoning about digit distributions,
`evaluation/corpus_run.py` `REFUSALS["digit_preference"]` says "NOT
IMPLEMENTED", and `tests/test_corpus_run.py` asserts no registry name contains
`digit`/`benford`. The decision rests on Hartgerink et al. 2019 (Study 2):
terminal digits scored AUROC 0.38–0.51 and Benford 0.02–0.16 against
fabricated data. Neither number is about the setting below.

## The case for implementing it now

1. **The input it needs now arrives in the pipeline.** When the handoff was
   written, nothing fed the toolkit individual observations. Since 1.76 the
   opt-in `raw_data` module (`modules/raw_data`, producer `raw_data_track`)
   reads every spreadsheet/CSV a paper ships, through the copy-paste
   detector's readers. Those are exactly the IPD columns Carlisle 2021
   screened. The tool would have a caller on day one instead of being "built
   and consumed by nothing".
2. **Carlisle 2021 is the evidence for that setting, and it is strong.** Of
   526 RCT submissions to *Anaesthesia*, 67/153 (44%) of trials that supplied
   IPD had false data vs 6/373 (2%) without; last-digit preference in raw
   measurements was one of the IPD screens. Hartgerink's chance-level AUROC was
   measured on data whose fabricators knew they were being tested, and on
   summary statistics for part of it — a different object from a column of
   hand-entered heights or blood pressures.
3. **It covers a gap the existing raw-data check cannot.** `detect_raw_duplication`
   finds copied rows and repeated runs. A fabricator who types fresh numbers
   leaves no duplicates, but tends to heap on 0 and 5 or avoid some digits.
   The two checks look at disjoint failure modes of the same file.
4. **It is cheap and deterministic.** A χ² on ten bins, no model call, no new
   dependency. It can run inside the `raw_data` child process at no paid cost.
5. **The risk is containable in code.** The ways it could accuse honest
   papers (summary tables, float-lost trailing zeros, instrument-rounded
   columns, OCR'd digits) can each be refused by a guard with a regression
   test, and the severity can be capped at `suspicious` so it never headlines
   alone.

The honest counter-case, which the plan must keep visible: many legitimate
columns have non-uniform last digits by construction — a scale read to the
nearest 0.5 kg, BP charted to the nearest 2 or 5 mmHg, ages, counts, Likert
items, derived variables (BMI, z-scores). Digit preference there is a
property of the instrument, not the authors. This is the dominant
false-positive class and the plan treats it as a first-class guard, not a
caveat.

## Scope

In: one deterministic tool, `check_digit_preference`, evaluating the last
significant printed digit of ONE column of individual observations against
Uniform{0..9}; wired into the registry (tools agent), the CLI via
`metascience tool run`, and the `raw_data` track.

Out (unchanged from the handoff): Benford/leading digits in any form; last
digits of means, SDs, p-values or coefficients; Fisher/Stouffer combination
across columns into a paper-level verdict; the other Carlisle IPD screens
(DOB clustering, IPD-vs-Table-1 reconciliation) — each would be its own tool;
any change to CSF.

## Invariants (each pinned by a test)

1. **Input class gate.** `data_kind ∈ {individual_observation,
   summary_statistic, unknown}`, default `unknown`. Only
   `individual_observation` is evaluated; the rest return `indeterminate`,
   `applicable: false`, and a sentence naming the class.
2. **Digits from literals, never floats.** API takes `values_text: list[str]`.
   `"72.0"` → 0. Sign and thousands separators stripped; scientific notation
   refused.
3. **Spreadsheet literals are reconstructed from the cell's display format.**
   An `.xlsx` stores `72.0` as the float `72`; the printed literal is the
   value under its `number_format`. Use the format's decimals when it is
   explicit; refuse the column when it is `General` with mixed precision
   (the trailing zeros are unrecoverable). CSV/TSV literals are used as read.
   This is the one place the existing readers (`_as_number`) cannot be reused
   as-is.
4. **Instrument-resolution guard.** Refuse (do not test against Uniform{0..9})
   when the column's digit support shows a fixed resolution: all last digits
   in {0,5}, all even, or a single digit on a constant number of decimals.
   Report the detected resolution instead. Also refuse integer columns whose
   range spans fewer than ~20 distinct values (counts, scores, ages in a
   narrow band) — the last digit is the value, not noise.
5. **Minimum n and valid test.** Refuse below 50 digits. Pearson χ²
   (df = 9) when every expected count ≥ 5 (n ≥ 50 guarantees this for a
   uniform null); no Monte Carlo branch unless a test shows it is needed.
6. **Severity cap, in code.** `p < 0.01 → suspicious`, else `consistent`
   (or `indeterminate` for `0.01 ≤ p < 0.05`, per the handoff — decide with
   the calibration below). `impossible` and `highly_suspicious` unreachable.
7. **No p-value on a refusal.** Guard paths carry no `chi2`/`p_value` keys.
8. **Provenance refusal.** `ocr_table`, `ocr_text`, `measured_raster` refused
   via the shared `UNVERIFIED_PROVENANCE` set.
9. **Wording.** `consistent` says a uniform distribution is not evidence of
   authenticity; nothing says "fabrication"/"fraud" (rule 9). `caveat` cites
   Hartgerink 2019's AUROC; `methodology` cites Carlisle 2021.
10. **One column, one test.** A batch form returns per-column results and a
    worst-severity summary; no combined p.

## High-level plan

### Phase 0 — measure before building (go/no-go)
Before any registry wiring, run a scratch implementation of invariants 2–5
over every structured supplement column already on disk (the corpora the
`raw_data` track has read, plus the copy-paste detector's datasets).
Record: how many columns pass the gates, the fraction flagged at p < 0.01,
and a hand-read of every flag (instrument rounding? derived variable?
real heaping?). Also measure the null: 1,000 uniform draws at n = 50/200/1000
for the false-`suspicious` rate, and 0/5-heaped draws for sensitivity.

**Stop rule:** if, after the resolution guard, flags on presumed-honest
columns are dominated by instrument/derived-variable artefacts we cannot
refuse mechanically, record that result in this file and do not ship. That
outcome is a valid answer and closes the question with a measurement instead
of a citation.

### Phase 1 — the pure function
`tools/digit_preference.py` (`check_digit_preference(values_text, data_kind,
label, provenance)`), docstring in the shape of `tools/variance_dispersion.py`,
returning the keys listed in the handoff (`n_digits`, `digit_counts`, `chi2`,
`df`, `p_value`, `heaping_0_5_count/expected`, `method`, `data_kind`,
`explanation`, `caveat`, `methodology`, plus `resolution` when refused for
it). `tests/test_digit_preference.py` with the worked-number cases
(`["72.0","73.0","74.0"]` → `[0,0,0]`; 0/5-only column → resolution refusal,
not `suspicious`; n < 50 → refusal; `summary_statistic` at n = 500 → refusal;
hand-recomputed χ² matches), and a case in
`tests/test_misapplication_guards.py`.

### Phase 2 — registry and analysts
- New family folder `tool_specs/digit_preference/` (`spec.py` + `TOOL.md`),
  listed in `tool_specs.FAMILIES` and `tool_specs.ORDER`. Stages: TOOL_AGENT
  only (the tools agent reads supplements; the science agent does not need
  it). `ALL_TOOLS`, role allowlists and the findings-v2 technique enum are
  derived — nothing to hand-edit.
- `TOOL.md` description: IPD only, pass printed literals, `data_kind`
  required, Table 1 refused, severity cap; a `<!-- guidance:NN -->` block for
  the tools agent saying when to call it (raw supplement columns).
- Add to `deterministic.reproducible_tools()` so findings replay as
  `metascience tool run check_digit_preference --json ...`. A hand-written
  CLI verb is optional.
- Regenerate `tests/data/registry_snapshot.json`; add `CASES` in
  `tests/test_registry_equivalence.py` (one evaluated, one refused).

### Phase 3 — the raw_data track
Have the `raw_data` module run the batch form over each numeric column it
already reads (using the format-aware literal reconstruction from invariant
3), emitting quarantined rows like the duplication rows: one per flagged
column, under `QUARANTINE_CAP`, never the headline. Columns refused for
resolution or n are recorded as refused, so "ran and found nothing" stays
distinguishable from "could not test".

### Phase 4 — retire the prohibitions (same commit as Phase 2)
- `rulebook.md` rule 8: summary-statistic digits remain non-evidence;
  individual-observation columns may go to `check_digit_preference`, which
  refuses anything else; Benford remains forbidden; a `suspicious` is a
  screening signal unless corroborated.
- `tool_specs/variance_dispersion/TOOL.md`, `tools/variance_dispersion.py`
  docstring, `docs/tool_reference.md`: stop saying the toolkit has no
  digit check; point at the IPD-only sibling.
- `corpus_run.REFUSALS["digit_preference"]`: change the reason to "needs IPD;
  this corpus supplies summary tables" — the 3 FIRE-EXPECTED cells stay
  unscoreable for that new reason, and are not quietly scored.
  `eval/PREREGISTRATION.md` gets a dated correction note; rewrite
  `test_digit_preference_says_the_tool_does_not_exist` to the new fact.

### Phase 5 — release and verify
MINOR bump in `version.py` + `CHANGELOG.md` (new tool ⇒ reviews across the
boundary are not comparable). Module tests, push, then `metascience-test
--stack -q`. Read the output: print a uniform and a heaped column through
`metascience tool run`, recompute χ² by hand, and run the `raw_data_only`
pipeline on one paper with a real IPD supplement and open the report.
Since a new tool reaches the tools agent's prompt, run the paid
`metascience eval --paper apple_cider` regression (on the backends in
current use) and confirm no new false positives.

## Open decisions for Dan
- Whether `0.01 ≤ p < 0.05` is `indeterminate` (handoff) or `consistent`;
  settle with the Phase 0 null measurement.
- Whether the tool should be reachable by the tools agent at all, or only via
  the deterministic `raw_data` track (the safer start: no model chooses the
  columns or the `data_kind`).
