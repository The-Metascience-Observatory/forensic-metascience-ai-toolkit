# Adversarial review: the value register (`values.py`)

> **ARCHIVED 2026-10-16.** The defects below were fixed in `values.py` (join on row_label/row/ordinal; median_iqr and numeric mapped).

Reviewed 2026-08-18 on branch `unify-2026-08-12`. Every CONFIRMED item below was
reproduced by running the code (venv `metascience-agent`); the shipped suite
`tests/test_value_register.py` passes as-is (25 passed), so none of these are
caught by it. Severity: high = wrong output a reader would act on; medium =
misleading; low = cosmetic.

## CONFIRMED defects

### 1. HIGH -- verdicts cross-attach between rows that share a row label
`attach_checks` joins on `(row_label, ordinal)` and ignores the row number,
even though every dispatch record carries it (`cell["row"]`). Two rows with the
same label -- ordinary in clinical tables ("Male" under two arms, "Age" at
baseline and endpoint) -- collide, and every verdict attaches to every group in
the collision set:

```python
cs = [{"raw": "10 (33.3)", "row": 2, "row_label": "Male", "n": 30},
      {"raw": "20 (60.0)", "row": 7, "row_label": "Male", "n": 30}]  # 20/30 = 66.7, not 60
reg = V.build_register(tables=[{"name": "t1", "parsed": parse_cells(cs), "cells": cs}],
                       bindings={"Male": "v2"}, variables=[BINARY_VAR])
out = check_table(cells=cs, variables=[BINARY_VAR], bindings={"Male": "v2"})
V.attach_checks(reg, out["results"], table="t1", consistent=out["consistent_index"])
```
Result: the row-2 group -- whose own checks all PASSED -- now carries
`('check_count_percent', 'suspicious', False)` from row 7, and vice versa the
dishonest row carries the clean verdicts. `n_checks_attached` reports 8 for 4
verdicts. This is a false accusation rendered onto an honest value, the
project's stated worst output. `dispatch.check_table`'s comment
"`(row_label, ordinal)` is unique within a table" is false, and
`attach_checks`' "the two sides mean the same thing" is false with it.
Fix: join on `(row_label, row, ordinal)` -- both sides already have `row`.

`attach_not_run` has the same defect one level coarser: it keys on `row_label`
alone, so a refusal belonging to row 7 was stamped onto row 2's group
(reproduced). `granularity: "row"` is therefore also a lie -- it is row-label.

### 2. HIGH -- `printed` fabricates literals, and `same_value` then links different numbers
`_as_printed` claims "the literal the paper printed". For `estimate_ci` cells
both bounds are reconstructed from `decimals_interval`, the COARSEST precision
of the three numbers, so `1.42 (1.08-1.9)` yields `ci_low: printed='1.1'` --
a literal the paper never printed (it printed 1.08). Add a second row
`2.0 (1.1-3.6)` and `same_value_edges` links the two ci_low values as "the
same printed number in the same role" -- 1.08 and 1.1 are different numbers.
The hover UI this feeds would show a reader a fabricated equality. Reproduced:

```python
cs = [{"raw": "1.42 (1.08-1.9)", "row": 1, "col": 1, "row_label": "OR (95% CI)"},
      {"raw": "2.0 (1.1-3.6)",  "row": 2, "col": 1, "row_label": "OR (95% CI)"}]
# -> same_value: {"val:t1:r1:c1:ci_low": ["val:t1:r1:c1:ci_low", "val:t1:r2:c1:ci_low"]}
```
Also reproduced: `1,234.5 ± 12.1` gives `printed='1234.5'` -- the thousands
separator is silently dropped, so `printed` is again not the paper's literal.
Fix: keep the matched source substring per component (celltypes has it at parse
time and discards it), or at minimum give ci_low/ci_high their own decimals.

### 3. HIGH -- "Every value the paper printed" drops six cell kinds entirely
The module header promises every printed value, and the `ROLES` comment
promises "an unnameable value is ... recorded with role `unknown` rather than
dropped". That is true for prose only. In tables, any cell whose kind is not in
`_CELL_ROLES` -- `count`, `numeric`, `median_iqr`, `median_range`, `ambiguous`,
`non_numeric` -- is silently skipped (`groups_from_cells` line ~231:
`if not roles: continue`). Reproduced: a count, a median [IQR] (three printed
numbers), and an undeclared mean/SD cell build a register with `n_groups=0,
n_values=0`. On the real cached paper 10.1007--s00702-004-0248-2, undeclared:
32 table cells -> 0 table values; `coverage()` then reports zeros across the
board, so a paper whose every table cell was dropped is spelled identically to
a paper with no tables -- the absence-as-knowledge failure this repo names.
Fix: emit `unknown`-role values (as prose already does) or count the dropped
cells in the register the way `parse_cells` counts `n_unusable`.

### 4. MEDIUM -- value ids collide across different tables
Three reproduced routes to two different printed values sharing one id:
- Slug collision: tables named `cref='#/texts/57'` and `cref-texts-57` both key
  as `cref-texts-57`; all ids coincide pairwise.
- Fallback collision: `build_register` maps every falsy table name to `"t1"`,
  colliding with each other and with a real table named `t1`. (In
  `build_from_paper`, two unlabeled tables both become `"?"` -> slug `t`.)
- Type collision: `row=1` and `row="1"` both render `r1` while the ordinal
  dict keys them separately, so two cells share `t1:r1:i0`.
Colliding ids poison `same_value`, `group_id`, and any viewer highlight.
Fix: disambiguate duplicate slugs at build time (e.g. suffix `-2`), and key
ordinals on the same string the id renders.

### 5. MEDIUM -- ids do not survive reordering, in the dominant real case
`value_id` claims ids are "derived from WHERE IT IS PRINTED, not from its
position in a list, so it survives re-extraction and re-ordering". For
columnless cells -- which is ALL cells from `prepass.paper_tables` (verified:
0 of 20 carry `col` on the cached paper) -- the id contains the within-row
ordinal, i.e. list position. Reproduced: swapping two same-row cells moves the
Treatment mean from `val:t1:r2:i0:mean` to `val:t1:r2:i1:mean`. The claim is
true only in the `col`-bearing case that real extractions never produce.

### 6. MEDIUM -- unlabeled rows never join; the clean verdict is lost
For a cell with no `row_label`, dispatch stamps `row_label: ""` (`... or ""`)
while the register stores `None`. Reproduced with an unlabeled `estimate_ci`
row: the check RAN and came back consistent, but the join key `('', 0)` misses
`(None, 0)`; the verdict lands in `unjoined_check_cells` (good), the group
reads silent, and `coverage()`'s note then claims "a check neither ran nor said
why" -- false: it ran, reported, and the join dropped it.

### 7. MEDIUM -- `coverage()`'s four states are not "KEPT APART"
`n_no_applicable_tool` is counted regardless of `checks`/`not_run`, so one
group can occupy two states. Reproduced: an undeclared `mean_sd` cell
(applicable_tools `()`, dispatch refusal attached) counts in BOTH
`n_refused_with_a_reason` and `n_no_applicable_tool`; the four states sum to 2
for 1 group. Any consumer computing rates over these buckets double-counts.

### 8. MEDIUM -- `applicable_tools` is not "the answer the pipeline would actually give"
Two reproduced gaps between the docstring and the code:
- "An empty tuple is meaningful and distinct from an unknown kind" -- false:
  `applicable_tools("garbage", "unknown")` and the deliberately-declined
  `("mean_sd", "unknown")` both return `()`, indistinguishably (`DISPATCH.get`
  with a `()` default).
- It reads `DISPATCH` only, skipping `check_table`'s composite gate and
  `_drop_unbounded`. Reproduced: a `mean_sd` group bound to a
  `likert_composite` variable reports
  `['grim_check', 'grimmer_check', 'sprite_reconstruct']` while `check_table`
  on the same cell runs nothing and refuses all three. The shipped test
  (`test_applicable_tools_come_from_the_dispatcher_not_a_restatement`, BDI-II
  = likert_composite) asserts the wrong answer.

### 9. LOW -- `_CELL_ROLES` "cannot disagree" with `forensic_kwargs`, but already does
The comment says the mapping is "read off `celltypes.ParsedCell.forensic_kwargs`,
so the two cannot disagree". `forensic_kwargs()` returns `{}` for `mean_se`;
`_CELL_ROLES` maps it. Harmless today, but the stated invariant is false.

## SUSPECTED (reasoned, not run)

- `applicable_tools`' `except: return ()` renders "dispatch failed to import"
  as "considered and declined" -- a guard converting an absence into a
  negative, the repo's named failure mode. Same shape in `_data_type`.
- `check_table` line ~859 `if spec is None: continue`: a DISPATCH tool missing
  from the registry runs nothing AND records no `not_run`, producing a
  legitimate `n_silent > 0` with no bug in the register itself.
- Defect 1 chains into `dedupe_checks`: its key `(tool, severity, passed)`
  ignores `check_id`, so two REAL identical-severity verdicts cross-attached
  from two rows would be collapsed as one "duplicate".
- Body groups: two `_body_items` with the same `offset` cannot occur today
  (overlap set), but any caller-supplied items lacking `offset` all collide on
  `grp:body:None`.

## Docstring claims audited

- "0 of 20 cells had a col" on 10.1007--s00702-004-0248-2: TRUE (ran
  `prepass.paper_tables`; 20 cells, 0 with `col`).
- "10 of 20 shared a (row, col) key": TRUE under the excess-cells reading --
  10 distinct `(row, None)` keys each held by 2 cells (so also readable as
  20 of 20; the number is defensible, the phrasing loose).
- `attach_not_run`'s "column header reads `Placebo (n ¼ 68)`": TRUE -- the
  glyph-corrupted string is in the cached body.md (3 occurrences of `¼`).
- "all 24 checkable table groups" on that paper: CONSISTENT but not
  reproducible as stated -- the two tables hold exactly 24 `ambiguous` cells
  (12+12), which presumably became the 24 groups under declarations; run
  undeclared, the paper yields 0 table groups (defect 3).
- `build_from_paper` "ONE walker": TRUE -- single `paper_tables` call, and
  `.problems` is really carried (`_walked` list subclass).
- Dedup "37 of 745 (5.0%)" and completeness "94 of 757 (12.4%)": arithmetic
  checks out; the archive measurements themselves are unverifiable here.

## Attacked and could NOT break

- `zip(typed["cells"], cells)` truncation in dispatch: unreachable --
  `parse_cells` provably emits exactly one output per input, in order, and
  both zip arms derive from the same list. Same for `parse_cells`
  dropping/reordering relative to its input: it does neither.
- Ordinal computation values-vs-dispatch on IDENTICAL input: agrees, including
  empty raw cells and unparsed cells (both count every cell, same row key).
- `same_value` role separation (count 30 vs denominator 30): holds.
- `71` vs `71.0` precision separation: holds where decimals are honest
  (defect 2 is the exception, not this mechanism).
- Prose offsets colliding via overlapping `BODY_PATTERNS` matches: prevented
  by `_body_items`' seen-offset set.
- `attach_checks` called twice accumulating duplicates: real, but
  `dedupe_checks` exists for exactly this and works on the same-group case.
- The floor guarantee: nothing in `values.py` writes into `completeness`'
  denominator; the not-a-denominator claim holds in code.
