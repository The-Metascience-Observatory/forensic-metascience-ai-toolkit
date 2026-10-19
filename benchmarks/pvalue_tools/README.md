# Deterministic p-tool benchmark

This benchmark scores the p-value tools directly against human-labelled
statistics: no model, no cost, about 7 seconds. It exists so a change to the
p arithmetic can be judged before any paid batch run. It is pinned as a
regression gate in `tests/test_pvalue_tools_bench.py`.

## Data

`build_cases.py` turns the label datasets in the statcheck_pvalue_errors
corpus (`_sources/label_datasets/`) into `cases.jsonl`. Each case is one
printed statistic with its reported p, labelled `error` or `correct` by a
human coder.

| source | errors | correct | what it is |
|---|---|---|---|
| `wicherts2011` | 49 | 1,071 | Wicherts, Bakker & Molenaar (2011): every statistic in 49 JPSP/JEP 2004 papers, coded by hand. |
| `garcia2004` | 23 | 203 | García-Berthou & Alcaraz (2004): BMJ and Nature 2001. The r² rows are skipped (the tools take r). |
| `nuijten2017` | 0 | 96 | Nuijten et al. (2017), Study 2. These are statcheck flags that a human found explained by the multiplicity or sphericity correction the paper declares. They are negatives, provided the tool is told the correction. |
| `corpus` | 14 | 0 | Documented errors from the corpus's **working set** that parse as APA statistics. |

**The evaluation set is excluded** from `corpus`, because it is held out for
the paid A/B. Some evaluation papers' statistics are in `wicherts2011` and
`garcia2004` anyway, since those studies are where the papers came from.
Changes calibrated here should be general rules, never fitted to particular
cases.

**Strata** include:
- `bound` vs `exact`, depending on whether the printed p is "p < x" or "p = x";
- `sphericity_corrected` (the Wicherts coders' Huynh-Feldt rows);
- `undeclared_one_tailed`;
- `correction_explained` (the Nuijten rows), split by `adjust_*`;
- the journal and statistic kind.

## Scoring

`score.py` runs two tools on every case:
- `recalc_stat_to_p` is flagged when it returns an accusing severity.
- The statcheck wrapper (`python_statcheck_text`) runs on the case rendered as
  APA. It is flagged when statcheck reports an `error` that the wrapper does
  not cancel as correct at printed precision.

The scorecard lists caught errors and false flags **by case id** for every
group: all, each source, and each stratum.

```bash
python benchmarks/pvalue_tools/build_cases.py <corpus dir>   # regenerate cases.jsonl
python benchmarks/pvalue_tools/score.py                      # writes scorecard.json
```

## Gate

The test rescoring fails in two situations:
- a pinned catch is lost in any group;
- any group gains false flags.

An improvement is recorded by committing the new `scorecard.json`. The file
`scorecard_baseline_1.89.0.json` keeps the starting point.

## Baseline (1.89.0)

| | `recalc_stat_to_p` | statcheck |
|---|---|---|
| Wicherts errors caught | 15 of 49 | 18 of 49 |
| Errors on a printed bound caught | 20 of 55 | 23 of 55 |
| Wicherts false flags | 12 of 1,071, all Huynh-Feldt | 19 of 1,071 |
| Correction-explained statistics flagged | 95 of 96 | 96 of 96 |
| Corpus documented errors caught | 13 of 14 | 13 of 14 |

The bound misses come from rounding slack that a printed bound should not get.
The correction false flags come from the under-claim rule, which knows
nothing about corrections. Release 1.90.0 addresses both.

## After 1.93.0 (2026-10-18), `recalc_stat_to_p`

| | 1.89.0 | 1.90.0 | 1.93.0 |
|---|---|---|---|
| Wicherts errors caught | 15 of 49 | 27 of 49 | 48 of 49 |
| Errors on a printed bound caught | 20 of 55 | 32 of 55 | 54 of 55 |
| False flags, all labelled-correct | 109 of 1,370 | 4 of 1,370 | 4 of 1,370 |
| Corpus documented errors caught | 13 of 14 | 13 of 14 | 14 of 14 |

1.90.0 removed the bound slack and taught the under-claim rule about declared
corrections. 1.93.0 stopped assuming an unstated one-tailed test (statcheck's
`OneTailedTxt` rule). The unstated rescue had decided 23 cases, all of them
labelled errors. `scorecard.json` holds the current per-case record.
