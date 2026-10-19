# GRIM recall ground truth

Published papers whose GRIM inconsistencies were documented by someone other
than this toolkit, labelled **cell by cell**, with a scorer that says, for each
labelled cell, whether a review **checked** it, **flagged** it, and **reported**
it.

- **[VERIFIED.md](VERIFIED.md): the 21 papers with verified GRIM errors**, what
  "verified" means, how each was established, and why the rest are not.
- [SOURCES.md](SOURCES.md): every source behind every set, with complete
  references, links and the DOIs of the papers with GRIM issues.

Both are generated (`make_verified_md.py`, `make_sources_md.py`) from the
labels and cached references; regenerate them rather than editing by hand.

## Sets

Each set is a subfolder with its own labels, research records and builder,
and its papers in the same-named subfolder of the working corpus,
`../agent_for_forensic_metascience_papers/grim_ground_truth/<set>/` (never this
repository). Within it, the papers with verified errors are in `verified/` (for
`literature_2026-10`, split into `verified_dev/` and `verified_holdout/`) and the
rest at the top level; `verify_labels.py` and `score.py` look one subfolder deep,
and refuse a paper found in two places. The scripts here are shared.

**Dev and holdout.** A set with a `splits.json` has a seeded random split of its
verified papers, related papers kept on one side. Develop and tune on `dev`
(`score.py --split dev`); do not inspect, score or tune against `holdout`
until the final test. `tests/test_grim_bench.py` pins that the split is disjoint,
covers every verified paper, and keeps each family together.

| Set | Papers | Primary cells | What it is |
|---|---|---|---|
| [literature_2026-10/](literature_2026-10/README.md) | 29 | 210 in 19 papers, + 1 paper verified at paper level | critiques, journal notices and PubPeer threads (Wansink's lab, Brown & Heathers, Anaya, biomedical audits), assembled 2026-10-17 |
| `kelly_pcit` (internal, not in git) | 4 | 4 in 1 paper | Kelly's PCIT GRIM survey (PsyArXiv 5m8qf): 31 itemised means, 6 positive and 25 `false_alarm` (22 explained by the authors, 3 settled by the paper's own methods). Labels live with the papers in `grim_ground_truth/kelly_grim/set/`, under an `EMBARGO.json` marker. |

A set folder holds:

- `labels.jsonl`: one paper per line, its cells under `cells`.
- `build_labels.py`: builds `labels.jsonl` from `sources/`, and holds every
  judgement made on top of them, each with its reason.
- `sources/`: the research records, each value copied from a named source
  with its URL.
- `README.md`: what is in the set, how its values were checked, and its gaps.

`tests/test_grim_bench.py` runs its label tests over every set folder holding a
`labels.jsonl`. They fail if a set's labels drift from what its builder makes,
or if a cell's stamped arithmetic or tier is stale.

## What a positive label means

**"Inconsistent with the n the paper prints", not "the mean is wrong".** In
the cases where the truth came out, the usual cause was a misreported n: the
Wansink lab's data releases and corrigenda, and the Eskine et al. dataset
(group sizes swapped in the text), make most flagged means consistent at the
true n. A tool that reads the paper can only test the printed n, so that is
the right target, and it is the claim a report should make.

This toolkit's own findings never go in a set: scoring a tool against its own
output measures nothing. (`10.1371/journal.pone.0042828`, 7 of 20 Table 2
means failing at n=6, is out for that reason.)

## Tiers

`verify_labels.py` recomputes every cell with the toolkit's GRIM arithmetic,
with no scale bounds, so only granularity is tested, and gives it a `tier`:

| Tier | What it is |
|---|---|
| `false_alarm` | `label: false_alarm`: a critic flagged it and the authors' data or answer explained it (typically a per-subject average). A tool that flags it is WRONG; the scorer counts those separately. |
| `primary` | fails GRIM under both round-half AND truncation, at an n the paper prints, on an integer premise. What the tool is built to flag. |
| `rounding_only` | fails round-half, passes truncation. The tool reports `consistent` / `rounding_convention` here **by design** (`tools/grim.py`, 2026-08-10). Most critics test round-half only, so their lists include these. |
| `inferred_n` | the critic's n is not printed: borrowed from a companion paper, an assumed equal split, derived from df, or a reading of the design |
| `doubtful_premise` | whole-number data is the critic's assumption (ages, free-text estimates, a possibly weighted index, two-coder averages) |
| `excluded` | our arithmetic does not reproduce the claim, a correction says the values are model-adjusted means, or the value is not printed in the paper |

With `--papers-root`, each value is also looked for in its paper's own text
(raw XML text including tables, and `pdftotext`), and `value_verified` is set
when it is found. A set's `build_labels.VALUE_CHECK` records the cells the
search misses and how they were settled by reading the paper.

**The headline recall is `primary` cells with `value_verified`**, reported per
cell and per paper. Cells are not independent: one paper can contribute
dozens, so a paper counts as found when at least one of its headline cells is.

## Run it

```bash
SET=benchmarks/grim/literature_2026-10
DIR=../agent_for_forensic_metascience_papers/grim_ground_truth/literature_2026-10
python $SET/build_labels.py                                                 # sources -> labels
python benchmarks/grim/verify_labels.py --labels $SET/labels.jsonl --papers-root $DIR --write
metascience batch $DIR --backend claude        # THE PAID STEP
python benchmarks/grim/score.py --labels $SET/labels.jsonl --papers-root $DIR --review 'forensic_review_*'
```

`DIR/<paper_id>/` holds each paper, `paper_id` being the DOI in lower case with
`/` → `--` (fetchpdf's folder name). `--review` is a glob for the review
directory inside each paper directory; the newest match by
`run_meta.analysed_at` is scored.

The scorer's three counts:

- **checked**: a `grim_check`, `grim_percentage` or `grimmer_check` call (direct,
  or a row of a `check_table` batch) ran on this value at this n (or n·k).
- **flagged**: a `grim_check` / `grim_percentage` call failed with failure mode
  `granularity` or `rounding_convention`. Not by severity: GRIMMER fails on SDs,
  and an `out_of_range` failure against a scale bound the model assumed is not
  a GRIM detection.
- **reported**: a non-discarded GRIM-family finding prints the value in its
  title, description or notes. Not its `quote` or `inputs`, which list passing
  values beside failing ones. Two cells of one paper with the same value and n
  cannot be told apart here.

## Adding a set

1. Make `benchmarks/grim/<set>/` with `sources/` (the research records) and a
   `build_labels.py` writing `labels.jsonl` in the shape the existing set uses.
   The label tests pick it up automatically.
2. Fetch its papers into `grim_ground_truth/<set>/`.
3. Run `verify_labels.py --papers-root`, settle every `NOT IN TEXT` cell by
   reading the paper, and record the outcome in the set's `VALUE_CHECK`.
4. Read each paper whose label rests on an unconfirmed premise (an n the paper
   does not print, an assumed whole-number premise) and record the outcome in
   the set's `MANUAL`, confirming or not, with the evidence.
5. Move the verified papers into the corpus folder's `verified/` subfolder, or
   split them into `verified_dev/` and `verified_holdout/` with a `splits.json`.
6. Add a row to the table above and write the set's README; extend
   `make_sources_md.py` / `make_verified_md.py` to read the new set, and
   regenerate both documents.
