# Tool Reference

**This file is documentation for humans. It is NOT sent to any model.** It
lived in `src/metascience_agent/prompts/` until 2026-10-18, beside the prompts,
which is how it came to be mistaken for one; it moved here for that reason.

Guidance was once written here, a test asserted every sweep tool appeared here,
and the model never saw a word of it. What a model IS sent is assembled in
`metascience_agent/core/prompts/__init__.py` (see AGENTS.md, "Prompts"): each
agent's `modules/<name>/prompt.md`, the shared `core/prompts/` text, and per
tool only its MCP definition. So: **if guidance has to reach the model, it
belongs in the `description` block of the tool family's
`tool_specs/<family>/TOOL.md` (which IS the MCP tool definition), or in an
agent's `prompt.md` / `core/prompts/rulebook.md`. Writing it here reaches
nobody but a reader of this repository.**

Where this file and a tool's `TOOL.md` disagree, `TOOL.md` and the code win.
For the current list, roles and parameters, ask the registry instead of this
file -- it cannot go stale:

```bash
metascience tool list
metascience tool describe grim_check
```

Every registered tool runs from the command line as
`metascience tool run <tool> --json '<args>'`, through the same gates the agents
use, and that is the form reproductions take. Many tools also have a
hand-written verb (shown in each section) that formats its result for a person;
"MCP-only" below means only that no such verb exists.

## GRIM (means from integer data)
MCP: `grim_check` · CLI:
```bash
metascience grim <mean> <n> --scale-min <min> --scale-max <max> [--decimals 2]
```
Checks whether any integer sum S gives round(S/n) == reported mean. Only for
integer/Likert/count data. Impossible means are high-priority anomalies.

## GRIM on percentages
MCP: `grim_percentage` (MCP-only; reproduce via `metascience grim-sweep` with
one value). More powerful than GRIM on means because percentages carry more
precision.

## A value outside its logical range — this indicts US first
MCP: `check_statistic_bounds` · CLI:
```bash
metascience check-bounds 11.3 correlation
```
Call it the moment you hold a statistic that is impossible on its face: a
correlation above 1, a p-value above 1, a percentage above 100, an alpha above 1.

**It will not let you accuse the paper, and that is deliberate.** A value that
far outside its own definition is not the kind of error that survives to
publication in an honest paper OR a fabricated one — fabricators produce
plausible numbers, because that is the point of fabricating them. The likeliest
author of the error is whoever read the page, which was us.

So the verdict is `indeterminate`, `failure_mode: extraction_suspect`, and the
result names the specific slip that would explain it: 11.3 as a correlation
reads as 0.113 with the decimal point two places out.

**Then go and check the source.** Re-read the value in the paper itself — the
digits against the printed figure, and the COLUMN, since a mean or a test
statistic read out of the wrong column is the other common cause. If it is
confirmed there, call again with `extraction_verified=true` and it returns
`impossible`, which the bound then fully licenses. Verification is the price of
the accusation.

## Count against percentage — use this whenever the count is printed
MCP: `check_count_percent` · CLI:
```bash
metascience check-count-percent 142 73.0 200 --decimals 1
```
**Strictly stronger than GRIM on an `n (%)` cell.** GRIM asks whether the
percentage is attainable for SOME integer numerator; this asks whether it
matches THE numerator the paper printed.

MEASURED 2026-08-10: a cell reading `142 (73.0)` at n = 200 passes `grim_percentage` as
**consistent**, because 73.0 is reachable at k = 146 — while 100 × 142 / 200 =
71.0. That is a false clear. Run both: GRIM is still the right tool when only a
percentage is printed.

**Capped at `suspicious`, never higher, and read the `implied_denominator`
before you write anything.** A percentage over a DIFFERENT base is the
commonest convention in clinical tables — row versus column percentages,
subgroup denominators — so a mismatch is evidence about which denominator was
used at least as often as about the arithmetic. If the implied denominator is
another n printed in the same table, the cell is fine and you have simply
paired it with the wrong base; say so rather than reporting a defect.

`decimals` is required for a verdict (read it off the literal: `73.0` is 1).
A count LARGER than n returns `indeterminate`, not a flag — it proves this n is
not the base, which is a fact about the pairing, not about the paper.

## GRIM sweep (shared denominator)
MCP: `grim_sweep` · CLI:
```bash
metascience grim-sweep --values "49.1,16.2,17.4" --n-max 161 [--decimals 1]
```
Finds every n for which ALL values pass GRIM. Empty intersection ⇒ the
percentages cannot share a denominator.

## Table declarations for the harness GRIM sweep
MCP: `list_tables`, `declare_table` · CLI: `metascience tool run declare_table --json '<args>'`

`list_tables(paper_dir)` names every table the harness sweeps (`T1`, `T2`, ...)
with each column's printed n. `declare_table(paper_dir, table, ...)` records what
the table's cells are -- row variables (`rows`, `default_variable_id`,
`variables`), n's the paper states only in prose (`columns`), and whether bare
numbers are shares of the participants (`percent_of_units`) -- and runs GRIM on
every cell the declaration covers. The harness reads the same declarations back
after the run, sweeps every table, and files each table's failures as one
finding (producer `harness`, `grim_harness.finding_rows`). A failure at a
column n that a few missing answers would explain is reported as
`explained_by_nonresponse`, at a lower severity.

## 2×2 reconstruction
MCP: `reconstruct_2x2` · CLI:
```bash
metascience reconstruct-2x2 <pct_col1> <pct_col2> <n_total> [--chi2 <x>] [--chi2-tol 0.05]
```
Recovers hidden 2×2 cell counts from column-conditional percentages, total N,
and optionally a reported χ².

## GRIMMER (SDs from integer data)
MCP: `grimmer_check` · CLI:
```bash
metascience grimmer <mean> <sd> <n> [--scale-min <min>] [--scale-max <max>] [--decimals 2]
```
Enumerates GRIM-consistent sums S, then integer sums-of-squares Q (with
parity constraint Q ≡ S mod 2) whose implied SD rounds to the reported SD.

## DEBIT (binary mean/SD consistency)
MCP: `debit_check`, `debit_check_batch` (batch is MCP-only) · CLI:
```bash
metascience debit <mean> <sd> <n> [--decimals-mean 2] [--decimals-sd 2]
```
For 0/1 variables, SD is fully determined by mean and n. Catches SDs > 0.5.

## T-test recalculation
MCP: `recalc_independent_t` · CLI:
```bash
metascience ttest <mean1> <sd1> <n1> <mean2> <sd2> <n2> --reported-p <p>
```

## Within-subjects (paired) t-test correlation recovery
MCP: `recalc_within_subjects_t` (MCP-only). Recovers the implied pre/post
correlation from summary stats + reported p; |r| > 1 is impossible (Jané et
al. 2024).

## ANOVA recalculation
MCP: `recalc_anova` · CLI:
```bash
metascience anova --means <m1,m2,...> --sds <s1,s2,...> --ns <n1,n2,...> [--reported-f <f>] [--reported-p <p>]
```

## F→p (any ANOVA shape)
MCP: `recalc_f_to_p` · CLI:
```bash
metascience f-to-p <F> <df1> <df2> [--reported-p <p>]
```

## Chi-squared recalculation
MCP: `recalc_chi_squared` · CLI:
```bash
metascience chi2 --observed "10,20;15,25" [--reported-chi2 <x>] [--reported-p <p>] [--yates]
```
Rows separated by `;`, cells by `,`. 2×2 tables also get Fisher's exact.

## SD range check
MCP: `check_sd_range` · CLI:
```bash
metascience sd-range <sd> <min_val> <max_val> [--n <n>]
```
Max sample SD ≈ (range/2)·√(n/(n−1)); larger is impossible.

## SD/SE confusion
MCP: `check_sd_or_se` · CLI:
```bash
metascience sd-or-se <value> <n> --as <SD|SE|unknown> [--max-sd <x>] [--range-min <a> --range-max <b>] [--decimals <d>]
```

**Pass `decimals`** -- the printed precision of the value. Under the SE reading
the rounding interval is stretched by sqrt(n), so at n = 100 a value printed to
one decimal carries +/-0.5 of implied SD. Without it the plausibility ceiling
gets a flat 1% margin, which is a guess and is the wrong size in both
directions.

## Regression coefficient consistency
MCP: `check_regression_batch` (use this for a TABLE) · `check_regression` (one
coefficient) · CLI:
```bash
metascience regression-batch coefficients.json
```
`coefficients.json` is a list of `{"b": B, "se": SE, "reported_t": t,
"reported_p": p, "df": N, "decimals_b": d, "decimals_se": d, "decimals_t": d,
"decimals_p": d, "label": "..."}`. Checks t = B/SE against what was printed.

**Pass `df` where the paper gives it.** Without df a t cannot be converted to a
p, so a row with only `reported_p` comes back `indeterminate` with nothing
checked — that is the commonest reason a coefficient goes unevaluated.

**Pass the `decimals_*` per row, read from the literals.** t is recomputed from
two ROUNDED values, so it is an interval whose width depends on the *magnitude
of SE* as well as the printed precisions: B = 2.0 with SE = 0.5 pins t to about
±0.5, while the same precisions with SE = 0.05 leave t anywhere within about
±11. That is why no constant works here. Omitted, a row falls back to the
widest plausible interval — safe, but blind: a coefficient printed `0.340` is
then checked as though it read `0.34`.

Note the window can legitimately exceed the estimate. B = 0.03 with SE = 0.01,
both at 2 dp, admits any t from 1.67 to 7.00, so `consistent` there means "this
table cannot be checked at this precision", not "this table is fine". The
returned `t_interval` is what tells you which.

**Use the batch form because it is the only form that gets the arithmetic
right**, not to save calls. Each ROW carries its own `df`, `decimals_b`,
`decimals_se`, `decimals_t`, `decimals_p` and `label` -- and as the paragraphs
above say, the t-interval a row is checked against depends on that row's own
precisions and the magnitude of its own SE. One set of precisions across a whole
coefficient table is wrong for most of it, and a row whose `df` was not carried
comes back `indeterminate` with nothing checked. `label` is what lets a finding
name the coefficient it is about.

(For scale: on one pre-batch run, 2026-07-27, 79 of 111 tool calls were
`check_regression` walking down a single regression table.)

## Summation check
MCP: `check_summation` · CLI:
```bash
metascience summation --values <v1,v2,...> --expected <sum> [--tolerance <t>]
```

**For more than one sum, use the batch form.** MCP: `check_summation_batch` · CLI:
```bash
metascience summation-batch sums.json [--tolerance <t>]
```
`sums.json` is a list of `{"values": [...], "expected_sum": N, "description": "...",
"tolerance": 0.5}`. A per-row `tolerance` overrides the default — a percentage
column rounding to 100 needs a wider window than a count column that must be
exact. The aggregate severity is the worst row, and a batch in which nothing
could be evaluated returns `indeterminate`, never `consistent`.

**Use the batch form because it is the only form that gets the arithmetic
right**, not to save calls. Each ROW carries its own `decimals`,
`decimals_total`, `tolerance` and `description`. The window a sum is allowed
depends on how many addends it has and how precisely each was printed, so one
window across a whole table is wrong for most of it -- a percentage column
rounding to 100 needs a wider window than a count column that must be exact.
Rows sent one at a time share whatever single window the last call used, and a
row with no precision comes back `indeterminate` with nothing checked. The batch
also aggregates to the worst row and returns `indeterminate` when nothing could
be evaluated; neither happens when the rows arrive separately.

(For scale: on one pre-batch run, 2026-07-27, 55 of 124 tool calls were
`check_summation` invoked once each on flow-diagram arms and column totals.)

## Ratio check (ICERs, rates, "X per Y")
MCP: `check_ratio` · CLI:
```bash
metascience check-ratio --numerator <n> --denominator <d> --reported-ratio <r> \
  --decimals-numerator <dn> --decimals-denominator <dd> --decimals-ratio <dr>
```

Nothing else here verifies a division, and a health-economics paper's entire
result is one. A cost-utility analysis printed all three columns of its central
table -- incremental cost, incremental QALYs, and the ICER -- and the sweep
filed "no tool performs ratio/division verification" under `not_checked`. Worked
by hand, the three rows implied three different incremental costs where there
can only be one, and none matched the figure stated in the paper's own methods.

All three `decimals_*` are mandatory: a quotient's slack depends on both printed
precisions AND on the denominator's magnitude (B/SE at SE=0.5 tolerates about
+/-0.5; the same precisions at SE=0.05 about +/-11), so there is no safe
default and the tool returns `indeterminate` rather than guess.

**Read `implied_denominator` out of the result, not just the verdict.** Across a
TABLE of ratios, rows implying different values for a quantity that can only
have one is the finding; a single row missing its own arithmetic is a question.
Capped at `suspicious` -- ratios are routinely computed from unrounded
intermediates a paper never shows.

## STALT (hidden p-values)
MCP: `stalt_check` · CLI:
```bash
metascience stalt <calculated_p> --reported-threshold "<0.05"
```
Flags exact p-values many orders of magnitude below their reported threshold.

## SPRITE (distribution reconstruction)
MCP: `sprite_reconstruct` · CLI:
```bash
metascience sprite <mean> <sd> <n> --scale-min <min> --scale-max <max>
```
Reconstructs possible integer datasets; note bimodal or boundary-stacked
shapes (often a sign the summary stats were invented).

## CSF (baseline similarity, RCTs)
MCP: `csf_test` · CLI:
```bash
metascience csf -p "0.92,0.88,0.95,0.91,0.87" -m stouffer
```
One-sided test of excess baseline similarity. Small `similarity_p` ⇒ groups
TOO similar ⇒ red flag (see rulebook rule 1).

**Pass `design` whenever the paper states one.** Cluster-randomised, multi-site,
stepped-wedge, crossover, matched-pairs, stratified and minimised allocation
break baseline independence *by construction*; the tool refuses on them rather
than flagging. Uncorrected, it flagged a correctly-randomised cluster trial
about 71% of the time. Without a stated design the verdict is capped below
`highly_suspicious`, because stratification would explain uniformity innocently.

The null is correlation-aware (Strube 1985 for Stouffer; Brown / Kost &
McDermott for Fisher), because Table 1 rows are correlated -- weight, height,
BMI and waist measure roughly one thing. Assuming independence gave a 33.5%
false-positive rate at rho = 0.6. A `sensitivity_profile` across rho is always
returned, and `similarity_p_under_independence` is retained so the downgrade
stays auditable. Pass `correlation` only if it is genuinely estimable.

## Bayesian Table 1 dispersion (complementary to CSF, not preferred over it)
MCP: `bayesian_table1_dispersion` · CLI:
```bash
metascience table1-dispersion table1.json --design parallel_rct
```
`table1.json` is a list of rows: `{"label","means","sds","ns"}` (continuous)
or `{"label","counts": [[...],[...]]}` (categorical). τ̂ > 2 with lower CI > 2
⇒ under-dispersion; τ̂ < 0.5 ⇒ over-dispersion.

**ALWAYS pass `--design` if the paper states one.** Cluster, stepped-wedge,
crossover, matched-pairs, stratified and minimised allocation force baseline
balance BY CONSTRUCTION and are refused outright. Without a stated design the
verdict is CAPPED below `highly_suspicious`, because a design that would
explain the uniformity innocently cannot be ruled out.

Baseline rows within a trial are correlated, and correlation is what generates
false positives here (~33.5% at ρ = 0.6, ~71% on cluster trials). The CI is
correlation-aware and a sensitivity profile across ρ is always returned; pass
`--correlation` only when it is genuinely known.

## Variance dispersion (are the SDs too similar?)
MCP: `check_variance_dispersion` · CLI:
```bash
metascience variance-dispersion --sds 25.09,24.58,25.65 --ns 15,15,15 \
    --homogeneous --design parallel_rct
```
Sample variances are themselves random. Fabricators add noise to the means and
forget the dispersions need their own, leaving SDs closer together than sampling
error allows. Standardises `z² = s²/MS_w` and compares `max_z − min_z` against a
parametric bootstrap of the χ² null; one-sided, for excessive consistency.

Hartgerink, Voelkel, Wicherts & van Assen (2019) measured this as the best
fabrication detector they tested (AUROC 1.00 on raw data), against 0.38–0.51 for
terminal digits and 0.02–0.16 for Benford — which is why this toolkit has no
digit-preference check and `evaluation/corpus_run.py` records that absence as a
decision.

**Pass the SDs as PRINTED** (the CLI keeps the literals you type). Coarse
rounding collapses honest SDs onto identical values — at SD ≈ 2.0 printed to 0dp,
60% of honest samples give six identical SDs — so without the printed precision
a rounding artifact is indistinguishable from the signature. Refused above a
rounding step of 0.25 × SD.

**`--homogeneous/--heterogeneous` is required, and it gates the reassuring
verdict too.** The source paper's own preregistered analysis scored AUROC 0.264
— inverted — from getting this wrong. A violated assumption makes this test
BLIND (measured 0.0% detection), not accusatory, so an unstated assumption
cannot return `consistent` either.

Needs ≥3 groups that are comparable units on ONE instrument. Severity caps at
`suspicious` and every result sets `reference_required`: the AUROC 1.00 was
RELATIVE — every dataset in that study, genuine and fabricated alike, looked
significant against the theoretical null, and only comparison against
known-genuine data separated them. This ranks candidates; it never convicts.

## Continuous → categorical plausibility
MCP: `check_proportion_from_normal` · CLI:
```bash
metascience prop-from-normal <proportion> <mean> <sd> <n> --threshold <X> --direction <below|above>
```

## RIVETS (hand-calculation detector)
MCP: `rivets_independent_t`, `rivets_anova` · CLI:
```bash
metascience rivets-t <m1> <sd1> <n1> <m2> <sd2> <n2> -t <reported_t> -p <reported_p>
metascience rivets-anova --means ... --sds ... --ns ... -f <reported_f> -p <reported_p>
```
A reported t/F that exactly equals the value computed from the truncated
(printed) inputs, while almost no true underlying data reproduces it, is the
signature of hand-calculated statistics. Reported values OUTSIDE the analytic
interval are impossible at the stated precision.

## GRIM-U (rank-sum p-value granularity)
MCP: `grimu_check`, `grimu_coexistence` · CLI:
```bash
metascience grimu <n1> <n2> <reported_p> [--decimals 3] [--cc both|none|cc] [--method normal|exact|both]
metascience grimu-coexist <n1> <n2> --p 0.171 --p 0.172
```
Mann-Whitney U / Wilcoxon **only** (never t/F/χ²/regression p-values). Because
U is (half-)integer in [0, n1·n2], only a finite p-set is achievable.
`impossible` = below the U=0 floor (Khajuria: 6v6 floor ≈ 0.0039 ⇒ p≤0.001
impossible); `suspicious` = lands between achievable granular values (often a
software/continuity-correction artifact, so cautious); `consistent` = some
achievable U (±CC) reproduces it. `reported_p` accepts `<0.001`. See rulebook
rule 12.

## Heuristic flags
MCP: `flag_round_n`, `flag_uninformative_stat` · CLI:
```bash
metascience flag-round-n --ns "100,200,300"
metascience flag-uninformative --means ... --sds ... --ns ... -p <p>
```

## Statcheck (automated NHST verification)
MCP: `statcheck` · CLI:
```bash
metascience statcheck paper.pdf            # or paper.md, or --text "..."
```
Extracts APA-style statistics and recomputes p-values; reports errors and
decision errors.

**statcheck only sees APA-formatted PROSE.** The same statistic in a table cell,
or in a sentence its grammar does not match, is invisible to it — that is a
limit of the SCANNER, not of the arithmetic. When statcheck returns nothing,
that is usually a fact about the paper's reporting style; check the tables
yourself with the tool below.

## Effect size ← the F beside it
MCP: `effect_size_from_f` · CLI:
```bash
metascience effect-size-from-f 51.81 2 54 --reported 0.83
metascience effect-size-from-f 14.231 1 30 --reported 0.322
```
Partial eta-squared is `(F*df1)/(F*df1 + df2)`; Cohen's f follows from it.

**Use this instead of `check_ratio`.** The shortcut `F/(F + df2)` is only the
`df1 = 1` special case and understates the effect for every multi-level factor,
so an honest paper looks wrong. This takes `df1` and REFUSES without it.

`measure` is required, and only `partial_eta_squared` and `cohens_f` are
recoverable from F and df. `eta_squared`, `generalized_eta_squared`,
`omega_squared` and model `r_squared` need a total sum of squares the paper does
not print, and are refused BY NAME — scoring them against the partial formula
would flag every paper that honestly reports generalised eta-squared.

MEASURED 2026-08-22: `10.1007--s10803-013-1829-4` prints "F(2, 54) = 51.81,
eta_p^2 = .83" against a true .657, and the finding had to be filed under
`no_tool_exists` because nothing in the registry covered it. In the same batch
`10.1177--0956797615569889` hand-rolled four such checks through `check_ratio`,
correctly — every df1 happened to be 1, and nothing enforced that.

Both numbers are rounded, so the comparison is interval-to-interval and a flag
needs the intervals to be DISJOINT. Capped at `suspicious`: a label naming a
different effect-size family, a value carried from another model, or an F
corrected for sphericity against uncorrected df all produce a mismatch, and none
is an arithmetic violation.

## One statistic → its p-value (any format)
MCP: `recalc_stat_to_p` · CLI:
```bash
metascience stat-to-p 4.10 chi2 --df 1 --reported-p 0.04 --decimals-stat 2
metascience stat-to-p 2.10 t --df 28 --reported-p 0.045
metascience stat-to-p 0.35 r --n 40
```
Converts **t, chi2, z, r, F** — the same five distributions statcheck verifies —
from VALUES rather than from prose. Use it on every table cell that prints a
statistic beside a p-value.

MEASURED 2026-08-10: three archived papers hit this gap, and on one it downgraded the
HEADLINE finding from `impossible` to `highly_suspicious`, the review writing
"No tool in this kit converts a chi-squared statistic plus df to a p-value".

**If the paper does not print the ingredient, this refuses and NAMES it.** A
chi-squared with no degrees of freedom cannot be converted by any
implementation — report that as an incompletely reported test, a property of
the publication, NOT as a limitation of this toolkit.

Capped at `suspicious` and **directional**: only an OVER-claim is flagged (a
reported p below what the printed statistic can support). An under-claimed p is
conservative reporting or a threshold. The statistic's own rounding widens the
target — `chi2 = 4.1` asserts [4.05, 4.15) and therefore a p RANGE. `--tails` is
ignored for chi2 and F, whose p is an upper tail by construction.

## Table ingestion
MCP: `parse_table` · CLI:
```bash
metascience parse-table table.md [--format markdown] [--cross-check pdf_table.txt]
```
Turns a markdown pipe table, a pdfplumber `data` grid, or raw text into
normalized cells `[{row_label, col_label, value, sd, extras, raw}]`. Use it so
you don't hand-transcribe numbers. Pass `cross_check` (the same table from the
other extraction) to reconcile XML vs PDF (or markdown vs PDF) and flag
disagreements.

**Do NOT pass an `extract_xml` table through this tool on the main path.** It
drops every cell it cannot reduce to a scalar, which silently discards
`estimate (CI)` cells — on a real clinical Table 1 that is 57 usable cells
instead of 173. `extract_xml` already hands you `cells`; send those straight to
`parse_cells_typed`. Reconciliation via `cross_check` is what this tool is for
here.

## Duplication / copy-paste detection
MCP: `detect_duplication` · CLI:
```bash
metascience duplication-detect blocks.json
```
Compares (mean, SD) cells within and across tables/studies. Each block:
`{label, sample_id, independent, cells: [{label, value, sd}]}`. Identical pairs
across *independent* samples are a red flag (≥3 ⇒ highly_suspicious); matches
across blocks sharing a `sample_id` are expected and discounted. Also flags
identical rows/columns repeated within a table. See rulebook rule 11.

## Raw-data duplication (participant-level supplements)
MCP: `detect_raw_duplication` · CLI:
```bash
metascience raw-duplication-detect supplement.xlsx \
    --exclude-column site_id --highlight-out highlighted.xlsx
```
Takes a FILE PATH (.xlsx/.xlsm/.csv/.tsv/.docx) and loads the grid itself —
never retype cells. Finds duplicated participant rows (within AND across
sheets), repeated vertical runs (fill-down copy-paste), and improbably
specific repeated values. Matches are weighted by significant-digit
information content, with in-code discounts for derived values (fraction /
sqrt / log), sorted/ID runs, shared covariates (values many rows carry), and
a Poisson chance gate on repeat counts. Severity caps at `highly_suspicious`.
`exclude_columns` removes shared-by-design columns (IDs, coordinates,
site-level covariates); `data_context="pooled_or_meta_analysis"` caps at
`indeterminate` (pooled rows duplicate by construction). `--highlight-out`
writes a color-marked copy for human verification. See rulebook rule 11.

## PDF extraction
MCP: `extract_pdf` (args: `pdf_path`, optional `max_chars`, `first_page`,
`last_page`) · CLI: `metascience extract paper.pdf -o out.json`.
Output is capped; when TRUNCATED, request specific pages.

**An empty `tables` does not mean the paper has no tables.** A PDF table is only
returned when it resolves into a grid. Journal tables are routinely ruled
horizontally only, or not at all, and pdfplumber then finds nothing -- but the
table is still printed in `text`. Search there for `Table 1` and read the
numbers off the page.

`tables_rejected` counts candidates dropped by the tabularity gate. Inferring
columns from text alignment succeeds on ANY page, so ungated it emits about one
pseudo-table per page: on `10.1007--s00702-004-0248-2`, a 14-page prose paper,
twelve of them, the first being the title page. A candidate is kept only if it
is at least 3 rows and 2 columns, at least 10% of its filled cells are bare
numbers, and at most 15% run over 40 characters -- the last of those is what
separates a table from a reference list, which is also dense with numbers.
`pages[].tables_rejected` carries the measurements for each rejection.

## XML extraction (JATS / PMC / Elsevier)
MCP: `extract_xml` (args: `xml_path`, optional `max_chars`, `first_section`,
`last_section`) · CLI: `metascience extract-xml paper.xml -o out.json`.

**Prefer this over `extract_pdf` whenever an `.xml` exists.** A PDF extraction
collapses a table row into one blob
(`'None 226150662 95.5(95.4-95.7) 96.2(95.7-96.7)'`) and markdown cannot express
a merged cell at all. This returns a dense rectangular grid with
`colspan`/`rowspan` expanded and a multi-row header flattened into composite
labels (`"Weighted % (95% CI) | Veteran"`). Measured 2026-07-31 on a real clinical Table 1:
7 usable cells per table via the PDF, 86 via the XML.

**`extract_xml` returns a table INDEX, not the grids.** Per table:
`table_num`, `label`, `caption`, `section`, `n_rows`, `width`,
`n_header_rows`, `n_footnotes`, `image_only`, `alignment_uncertain`.

## One table, in full
MCP: `get_table` (args: `xml_path`, `table_num`) · CLI:
`metascience get-table paper.xml 2`.

Returns `cells` (ready for `parse_cells_typed`), `data` (the grid, row 0 =
header), `headers`, `label`, `caption`, `section`, `footnotes`, `spans`,
`alignment_uncertain`, `image_only`, `width`.

**Why two calls rather than one.** Returning every grid at once produced a
184 kB result on a real clinical paper. The harness caps tool results, so it
spilled to a file and roughly 60% of it was never read — the model recovered
what it could by guessing line offsets into raw JSON. The tables were extracted
perfectly and delivered by luck. An index of the same document is a few kB, and
one table always arrives.

Fetch the tables you need, not all of them. The index tells you what each one
is; on most papers only one or two are worth sweeping cell by cell.

- **`cells` is the main path.** Send it straight to `parse_cells_typed` /
  `check_table`. Do not route it through `parse_table` first (see above).
- **A merged value appears ONCE**, at its anchor, with empty continuations.
  That is deliberate: one measurement is one value. "Filling in" the blanks
  would fabricate identical (mean, SD) pairs and trip `detect_duplication`.
- **`page` is always `null`** — XML has no pages. Cite `"Table 2, Age row"`.
- **`alignment_uncertain: true`** — ragged source rows, column labels may be
  shifted by one. Reconcile against the PDF with `parse_table` `cross_check`, or
  record the table as unchecked. A shifted label hands GRIM a triple the paper
  never reported.
- **`image_only: true`** — the table is a picture and has no cells. Get it from
  the PDF; if there is no PDF, record it in `unchecked`.
- **Read `footnotes` before typing cells.** They define whether a cell is
  `n (%)` or `mean (SD)`.
- `normalizations` reports every character rewrite made (true minus → ASCII,
  citation superscripts bracketed, `<break/>` → space) so nothing is silent.

## HTML extraction (fetched publisher full text, XML-not-available fallback)
MCP: `extract_html` (args: `html_path`, optional `max_chars`, `first_section`,
`last_section`) · CLI: `metascience extract-html paper.fulltext.html -o out.json`.

**Only reached when there is no `.xml`.** Same `cells`/`spans`/
`alignment_uncertain`/`image_only` contract as `extract_xml` — treat the output
identically (straight to `parse_cells_typed`/`check_table`, never through
`parse_table` first).

**Unlike XML, a fetched HTML file can BE THE WRONG PAGE** — a landing page,
cookie-consent gate, or JS-rendered app shell that never contains the article,
and it will look plausible (a real title, a real abstract, even a populated
nav/metrics table). Measured 2026-08-08 on a real corpus: at least 7 of 30 fetched
"full text" HTML files were landing pages, not articles. Because of this,
`extract_html` runs a decoy check BEFORE any parsing and returns a structured
`error` if the page fails it.

- **If `extract_html` returns an `error`, that refusal IS the result.** Do NOT
  attempt to recover text from the raw file yourself, and do NOT report the
  paper as having no full text available. Record it in `unchecked` with the
  reason, and fall back to `extract_pdf` or `Read` on `body.md` for this paper.
  A returned error must never read as "checked, zero tables found" — that is
  indistinguishable from a clean paper and is worse than refusing loudly.
- **A merged value appears ONCE**, at its anchor, with empty continuations —
  same reasoning as `extract_xml`.
- **`page` is always `null`** — HTML has no pages. Cite `"Table 2, Age row"`.
- **`alignment_uncertain: true`** — ragged source rows, column labels may be
  shifted by one. Reconcile against the PDF.
- **`image_only: true`** — the table element had no populated rows, most
  likely never rendered by the page's own JavaScript. Get it from the PDF, or
  record it in `unchecked`.
- **`footnotes` may be empty even when a table needs one.** HTML has no
  standard footnote convention the way JATS does — reconcile against the PDF
  if a cell's meaning (`n (%)` vs `mean (SD)`) is ambiguous.
- Passing the decoy check is necessary, not sufficient: a correctly-identified
  page whose real body text never rendered (a JS shell with the right title/
  DOI in its metadata but no article prose) is a known, documented gap — if a
  table's content looks like navigation, citation counts, or "related
  articles" rather than the paper's own data, treat it the same as
  `image_only` and reconcile against the PDF rather than reporting from it.

## Supplementary data files
MCP: `extract_supplement` (arg: `path`) · CLI:
`metascience extract-supplement si.docx -o out.json`.

Reads `.docx`, `.xlsx`, `.xls`, `.csv`, `.tsv` and returns the SAME shape as
`extract_xml` — a `data` grid plus ready-made `cells`. Sweep supplements exactly
as you would a main table; they are where a paper's unchecked numbers hide. Use
`extract_pdf` for a supplementary PDF.

**A large supplement comes back as an INDEX, not as its contents.** MCP:
`get_supplement_table` (args: `path`, `table`, optional `first_row`/`last_row`)
· CLI: `metascience get-supplement-table si.xlsx 2 --first-row 1 --last-row 50`.

When `extract_supplement` returns `oversized: true` you have every sheet's name,
shape, column headers and first rows — **nothing has been dropped, and it is not
the data**. Call `get_supplement_table` for the sheet you want. Exactly the
`extract_xml` → `get_table` relationship, for the same reason.

This matters more than it sounds. Every spreadsheet supplement measured in this
corpus serialises to between 0.5M and 1.9M characters, so before the index
existed the only honest answer was to refuse them — and on one paper that meant
the latent-class model-selection statistics justifying the entire analysis went
unchecked. If a supplement holds the evidence for a claim in the main text,
fetch the sheet and check it.

`table` takes the sheet NUMBER the index prints or the sheet NAME.
`first_row`/`last_row` are 1-based and inclusive over the sheet's DATA rows; the
header row always comes back. A windowed result says so in `window_note` — rows
outside the window were not returned and are evidence of nothing, so report it
as a window rather than as the sheet.

- A sheet with many data rows is flagged in its `warnings` as **participant-level
  data**. That is worth more than a summary table: it supports checks the paper's
  own tables cannot, and it is what `detect_duplication` is for.
- Merged cells follow the same rule as everywhere else — value at the anchor,
  empty continuations. Do not fill them in.
- An unreadable format (legacy `.doc`, or a figure supplied as `.jpg`/`.bmp` —
  there is no OCR) returns an `error` naming the format. **That refusal is the
  result.** Record it in `unchecked`. Do NOT report the supplement as absent:
  "present but unreadable" and "not provided" are different facts about a paper.

## Typed table-cell parsing (run this FIRST)
MCP: `parse_cells_typed` · CLI:
```bash
metascience parse-cells cells.json
```
Input: `[{raw, row_label, col_label}, ...]`. Returns a `kind` per cell
(`mean_sd`, `n_percent`, `median_iqr`, `median_range`, `estimate_ci`, `mean_se`,
`numeric`, `count`, `ambiguous`, `non_numeric`) plus `coverage` -- the honest
answer to how much of the table was actually understood.

**This is upstream of every other technique.** The untyped parser read every
`X (Y)` cell as `mean=X, sd=Y`, so a clinical `142 (71.0)` -- a count and a
PERCENTAGE, the modal Table 1 cell -- arrived at GRIMMER and SPRITE as
`sd=71.0` and manufactured impossibilities out of an ordinary table. It also
silently dropped `median [IQR]`, `OR (95% CI)` and `median [range]` entirely,
starving the tools while reporting success.

A cell returned as `ambiguous` carries its candidate readings and **must not be
fed to any forensic tool**. Run nothing on a value whose meaning is unknown.

Every result also carries **`unparsed`**: the cells nothing could read, grouped
by shared shape, split into `numeric_shaped` (values the paper printed and we
failed to parse -- **our** defect) and prose (row labels, for which
`non_numeric` is the correct answer). Read it. A table where every cell fails is
not a table with nothing in it, and 153 silent per-cell failures is the form
both of this module's worst historical bugs took.

## Declaring a cell format the parser does not know
MCP: `parse_cells_as_declared` · CLI:
```bash
metascience parse-cells-as cells.json --declared mean_sd:brace
metascience parse-cells-as cells.json --declared list     # print the vocabulary
```
For a table typeset in a convention `parse_cells_typed` does not recognise --
`5.38 {1.17}`, `5.38 <1.17>`, `5.38 / 1.17`. A format name is
`<pairing>:<delimiter>`, both from a closed list:

| | |
|---|---|
| **pairings** (what the numbers mean) | `mean_sd` `mean_se` `n_percent` `median_iqr` `median_range` `estimate_ci` |
| **delimiters** (how the second is wrapped) | `paren` `bracket` `brace` `angle` `plusminus` `comma` `semicolon` `slash` |

**You name the format; you never write the pattern.** Every character of the
matching is code in `tools/cellformat.py`. A generated regex is a generated
statistic: whatever it captured would become the mean GRIM is then run against,
and no later layer can tell an invented number from a read one.

**Choose the pairing by READING the table** -- its header, caption and
footnotes -- not by which numbers happen to fit. `142 (71.0)` is equally a valid
mean (SD) and a valid n (%); only the table says which. `unparsed.clusters`
lists the formats that would parse a block, but the numbers cannot choose
between them and neither should you.

Your declaration is then **tested, not obeyed**: each cell is checked against
the same coherence guards the label path uses (an n (%) needs an integer count
and a percentage in [0, 100]; an estimate must lie inside its own CI and near
its midpoint), and the declaration is **refused wholesale** if it fits under 80%
of the cells -- `misfits` then shows what did not. `n_overrides_automatic`
counts the cells where your declaration contradicted the paper's own row/column
labels; a declaration that fights the headers is likelier wrong than they are.

If `candidate_formats` is empty, no format in the vocabulary expresses that
cell. Report it as a coverage limit and check nothing from it.

## Estimate vs its own confidence interval
MCP: `check_estimate_ci` · CLI:
```bash
metascience check-ci 1.42 1.08 1.87 --measure HR --reported-p 0.012
```
Checks that the interval is ordered and contains the estimate, that the estimate
sits at the CI-implied midpoint **on the correct scale**, and that the p
recovered from the CI matches the reported p.

**Always pass `measure`.** OR/RR/HR/IRR intervals are symmetric in LOG space; a
linear-symmetry check misfires on EVERY hazard ratio at SE_log = 0.4
(measured 2000/2000; the scale inference is what keeps the unlabelled path
clean, and it cannot help once you mislabel the measure). A "wrong" p is tested against alternative confidence levels before
anything is flagged, since a 90% CI reported as 95% is a labelling error, not a
fabrication.

**Pass `decimals`** -- the printed precision of the **coarsest** of the three
numbers, since a comparison among them is only known to that precision. Without
it the tolerance is re-derived from the parsed floats, and the float has already
lost the literal: `str(1.40)` is `"1.4"` and `str(5.0)` is `"5.0"`. So a bound
printed `1.40` reads as one decimal, one too COARSE, and the tolerance comes out
ten times too LOOSE -- a real mismatch is waved through. That direction is still
live and is the reason to pass `decimals`.

The opposite direction is FIXED and this paragraph used to describe it as
current: an integral `5` was read as one decimal (`str(5.0)` is `"5.0"`), giving
a tolerance ten times too TIGHT, so `OR 4 (1-9)` -- the correct 0 dp rounding of
3.6 (1.4-9.4) -- came back `suspicious` for missing its own geometric midpoint.
Integral values now infer 0 decimals, which is what they assert.

## Absence of evidence
MCP: `absence_of_evidence` · CLI:
```bash
metascience absence-of-evidence 0.72 1.95 --measure OR --sesoi 1.25
```
Tests whether a stated "no effect" conclusion survives its own interval.
"Not significant" is not "no effect": this reports the largest effect the data
still cannot rule out.

Without a smallest effect size of interest (`sesoi`) it describes the interval
and **explicitly declines to judge** -- equivalence cannot be claimed against an
unstated threshold. That refusal is the correct output, not a gap.

## Multiple comparisons (family-wise arithmetic)
MCP: `multiplicity_report` · CLI:
```bash
metascience multiplicity -p "0.01,0.03,0.07,0.03,0.01,0.03,0.38,0.96,0.89" \
  --family-label "nine outcomes, 3x3 design"
```
Family-wise error rate, four correction thresholds, and the number that actually
matters: `n_claims_lost_to_correction` -- how many results significant
uncorrected fail to survive correction. Use whenever a paper reports several
tests with no stated correction, and use it INSTEAD of doing the arithmetic
yourself; a hand-computed multiplicity finding cannot be reproduced or checked.

This is deterministic arithmetic, not an accusation. Uncorrected testing is
ordinary in most literatures, and the output is a statement about what the
numbers imply.

**How many results survive is a BOUND, not one number.** Which correction
applies depends on what the family needs, so all four are reported and
`n_surviving_floor` / `n_surviving_ceiling` span them:

- `n_significant_bonferroni` -- family-wise, alpha/m.
- `n_significant_holm` -- family-wise, step-down. Same guarantee and same
  assumptions as Bonferroni and **never rejects fewer**, so quote Holm rather
  than Bonferroni whenever you want the family-wise number.
- `n_significant_bh` -- false discovery rate. The most permissive of the four.
- `n_significant_by` -- Benjamini-Yekutieli: FDR under **arbitrary dependence**.
  This is the honest one when several outcomes are measured on the same
  subjects, which is the normal case. It can be **stricter than Bonferroni**
  when only one p-value is small, so do not describe it as sitting "in
  between" -- read the reported floor instead.

Report the interval and say which method you are quoting.
`n_claims_lost_to_correction` is read off Benjamini-Hochberg, the most permissive
of the four, so it is the *smallest* loss these corrections support; the
strict-end loss is `n_significant_uncorrected - n_surviving_floor`.

**What counts as a family is your call and the tool cannot make it.**
`family_label` is **mandatory and has no default** -- omit it and the tool
refuses rather than pooling the whole paper. Run it once per family. See the
family rubric in `tool_specs/multiplicity/TOOL.md` for what does and does not
constitute one.
Tests the authors already corrected are excluded automatically. Tests whose p is
reported as a threshold ("p < .05") are dropped rather than coerced, and counted
in the output -- treating a bound as a point would change which results are
counted as surviving.

FWER assumes independence and is therefore an **upper** bound; correlated
outcomes inflate it. Undisclosed analytic flexibility means the true comparison
count can exceed the reported one, so the whole report is a **floor** on the
multiplicity problem.

## Power analysis verification
MCP: `verify_power_analysis`, `required_n` · CLI:
```bash
metascience power-check two_sample_t -e 0.5 -a 0.05 --power 0.80 -n 128
metascience required-n two_sample_t 0.5            # -> 64/group, 128 total
```
Exact noncentral distributions (noncentral t/F/chi-square, Fisher z), verified
to exact agreement with R `pwr`. `test_type` is one of `two_sample_t`,
`one_sample_t`, `paired_t`, `anova_oneway`, `correlation`, `chi_square`,
`two_proportions`.

Returns `indeterminate` unless every input needed to reproduce the calculation
was actually stated. Most published power statements cannot be checked at all
(Bakker et al. 2020: ~80% are uncheckable; of those that can be checked, 97%
reproduce, but ~38% powered a different hypothesis than the one tested). An
uncheckable power statement is a REPORTING finding, not a tool failure -- say so
rather than guessing the missing inputs.

## R ground truth (cross-check before you report)
MCP: `r_grim_ground_truth`, `r_sprite_ground_truth` (MCP-only; require R with
`scrutiny` and `rsprite2` installed).

```
r_grim_ground_truth(mean, n, items=1, decimals=2)
r_sprite_ground_truth(mean, sd, n, scale_min, scale_max, ...)
```

Run the canonical R implementation of a check whose Python result you are about
to report as an anomaly. **Disagreement between engines means our tooling is
wrong, not the paper.** Use these before any `impossible` verdict leaves the
sweep -- a false accusation is not recoverable, and a thirty-second cross-check
is the cheapest insurance available.

Two caveats worth knowing:

- `rsprite2` infers decimal precision from the LITERAL, so `mean=4.0` reads as
  ZERO decimals. Pin `m_prec` / `sd_prec` explicitly or the two engines will
  appear to disagree when they do not. This is the single most common source of
  spurious cross-implementation disagreement in this field.
- Agreement is not universal and is not supposed to be. Our DEBIT deliberately
  evaluates the rounding interval implied by the printed mean, where `scrutiny`
  compares at exact `k/n`; ours is correct there (0 false accusations over
  28,720 enumerated cells, against 91.4% agreement with exact truth for
  `scrutiny`). Where the engines differ, say so in the finding rather than
  silently preferring one.

## Paired-design d, when the correlation is unreported
MCP: `paired_d_interval` · CLI:
```bash
metascience paired-d-interval --dz 0.89
metascience paired-d-interval --t 6.3 --n 50
metascience paired-d-interval --dz 0.89 --r 0.6
```
A paired design reports `d_z` -- the difference over the SD OF THE DIFFERENCES
-- and a reader comparing it against a between-subjects literature wants a
raw-SD effect size. The closed form is:

    d_rm = d_z * sqrt(2 * (1 - r))     [Lakens 2013 eq. 8]

and papers reporting `d_z` almost never report `r`.

**Try `recalc_within_subjects_t` first.** When both the pre and post SDs are
printed it RECOVERS `r`, which beats assuming it. This tool is for when they are
not, and then the honest output is an interval: for `d_z = 0.89` the attainable
range across r in [0.1, 0.95] is [0.28, 1.19], a factor of 4.2.

**It returns d_rm, not d_av.** They coincide only at equal pre/post SDs;
measured 2026-08-27, the error against true d_av is 0.2% at equal SDs, 29.3%
at sd2/sd1 = 2 and 44.5% at 3. `d_av` also needs the SD ratio, which this tool
does not take. The keys are `d_rm_low` / `d_rm_high`. Quote the
interval. Picking r = 0.5 silently is an unstated assumption doing the work of a
measurement -- the same shape as the "within 15 per cent" tolerance that once
appeared in this project's own reasoning with no author and no trace.

**The direction inverts easily and a published R package has it backwards.**
`d_rm` SHRINKS as `r` rises: a high correlation makes the paired test efficient,
so `d_z` is large while the raw-SD effect is not. At r = 0.95 the factor is
sqrt(0.1) = 0.316. `effectcheck` 0.7.7's `dav_from_dz` divides where it should
multiply and reports 2.82 where the truth is 0.28 -- verified against a
200,000-pair simulation with known r.

DESCRIPTIVE: it reports a property of what was printed and can never accuse. A
wide interval is a fact about the reporting, not about the work.

## Effect-size plausibility
MCP: `check_effect_plausibility` · CLI:
```bash
metascience effect-size --d 3.5 --field psychotherapy
metascience effect-size --mean1 12 --sd1 2 --n1 20 --mean2 5 --sd2 2 --n2 20 --field psychotherapy
```
Computes Cohen's d / Hedges' g and places it against EMPIRICAL, CITED benchmarks
for a named field. **Pass `field`** -- without it the tool reports the value and
declines to judge, because "large" is meaningless without a comparison class.

An effect far outside the usual range is among the most informative things you
can report, and it is NOT evidence of misconduct. Severity is capped at
`suspicious`: an effect size can be improbable, never arithmetically impossible.
Rule out the three ordinary causes first -- dispersion reported as SEM and read
as SD (inflates d by sqrt(n)), a waitlist rather than active comparator, and a
units mismatch.

**This is the check that works on figure-derived data.** Gross implausibility
survives digitization error: across the full +/-37% dispersion error range the
verdict does not move (g swings 2.50-5.47 and stays `suspicious`). So a paper
reporting its outcome only as a bar chart becomes checkable here, even though
GRIM, GRIMMER, SPRITE and DEBIT refuse those values outright.

## Figure extraction
MCP: `extract_figures` · CLI:
```bash
metascience extract-figures paper.pdf --dpi 150
```
Locates every figure, crops it, and pairs it with its caption. Runs LOCALLY via
PyMuPDF -- no network, no API, no token cost.

Uses CAPTION-ANCHORED cropping, not embedded-image extraction: most journal
charts are VECTOR linework that `get_images()` does not see at all (measured on
this corpus: 144 embedded rasters but 56 pages of heavy vector drawing across 25
PDFs). The caption is found as a text BLOCK and the crop is the artwork nearest
that block -- above it or below it, whichever is closer. Both directions occur
in the same paper: in `10.1002--hbm.26595`, Figures 1, 3 and 4 are captioned
below their artwork and Figures 2 and 5 above it.

### Read `crop_confidence` before reading the image
| value | what it means | what to do |
|---|---|---|
| `high` | artwork located and cropped to | read it |
| `low` | cropped, but too little ink to be a chart | read the page image named in the figure's `warnings` |
| `none` | no artwork found near the caption; `image_path` IS THE WHOLE PAGE | locate the figure by eye, or accept that it is unavailable |

`none` is common on papers that collect their figure legends onto a separate
page, and on captions whose artwork sits on the ADJACENT page -- a known
limitation, not something the tool can currently solve. **Reporting a value read
off a `low` or `none` image without saying so is a fabricated measurement.**

Returns `error_bar_meaning` read out of the caption (SD | SEM | CI | IQR |
range, or null). **A null there is a real result** -- SD, SEM and a 95% CI
half-width differ by sqrt(n) and ~1.96*sqrt(n), so a figure whose error bars are
unlabelled cannot yield an effect size, and the tool says so instead of assuming
SEM.

### Provenance: as-printed vs measured
A numeral PRINTED in a figure -- a data label, "n = 32", an axis annotation --
is a number the authors asserted. It licenses the full severity ladder like any
other printed value. Only a value MEASURED off the marks is different in kind,
and it is barred from every exact-arithmetic check. The split is not
text-vs-figure; it is as-printed vs measured.

## Whole-table dispatch (use this for any table)
MCP: `check_table` · CLI:
```bash
metascience check-table table.json
```
One call runs every applicable check on a whole table. A real run made 58 tool
calls on one paper, 51 of them the same check repeated per cell -- each call is
a turn, and turns are what cost.

Pass the `cells`, the `variables` you declared in Pass 0, and `bindings` mapping
row labels to variable ids. **Which checks apply is determined by cell kind x
variable family; you do not choose them.**

A declared variable also RESOLVES cells that syntax alone must refuse:
`48.90 (14.46)` under a bare label is ambiguous, but declaring the variable
continuous fixes the reading. That is what makes declaring variables pay.

Returns non-consistent results in full, a count of the consistent ones, and a
`not_run` list giving the REASON each check was refused -- so coverage does not
depend on you remembering. **Always report the denominator:** 3 suspicious out
of 140 checks and 3 out of 4 are different papers.

## Techniques from the founding text that we deliberately do NOT implement

The name of this toolkit and most of what it does come from James Heathers,
*An Introduction to Forensic Metascience* (Linnaeus University, 14 Feb 2025,
doi:10.5281/zenodo.14871843). A full read of the book against this registry
found we implement or exceed nearly every numerical technique in it. Four we
have decided against, and a decision recorded is worth more than a gap someone
rediscovers every six months.

**Median/IQR to mean/SD conversion.** The book raises it and then argues
against relying on it: "any such conversion is imprecise and produces an
approximation", and "Many methods here are conclusive proof of a data anomaly,
this one is not." A check whose output is an approximation cannot support an
accusation, and our severity ladder has no band for "probably off". We parse
`median (IQR)` cells (`celltypes.py`) so they are visible and counted; we do
not convert them and then test the conversion. If this is ever wanted, the
book's own condition applies: characterise the distribution first, compare
several conversion methods, and use the result only to justify requesting the
raw data.

**CORVIDS.** Enumerates every dataset consistent with a mean/SD/n, where SPRITE
samples them. The forensic claim we make -- "no sample can produce these
numbers" -- is already covered by `sprite_reconstruct`'s `no_solution_proven`,
cross-checked against R `rsprite2`. CORVIDS would add exhaustiveness we do not
report and a runtime the book itself flags as prohibitive at larger n.

**MVRNORM correlation-table reconstruction.** The book's own verdict: "it
remains promising but very open-ended, and should be designated only for
exploratory investigation." A technique with no verdict is a technique with no
place in a pipeline whose every output carries a severity.

**Image forensics, in this package.** When this section was written the
toolkit did no image forensics. It now has a deterministic panel-duplication
track (`analyze_paper_images`, below), but the detector, its gate and the AI
screening are a separate, privately distributed package
(`metascience_observatory_image_analysis`). Without it the image channel reads
`refused` and every report says the figures were NOT examined -- coverage is
never inferred from figures having been opened.

## Tools without a section above

Added 2026-09-02, when four registered tools had no entry. Their full
definitions are the `description` blocks in their `tool_specs/<family>/TOOL.md`,
which IS what the model is sent.

- **`check_flow_arithmetic`** (`metascience flow-check`; scientific proofreading
  agent and adjudicator) -- reconciles a CONSORT / participant-flow cascade by exact
  integer arithmetic: each stage minus its stated exclusions must equal the
  next, arms must sum to their stage total.
- **`run_python_script`** (no CLI verb; scientific proofreading agent only) -- runs a
  short script in a network-off sandbox and returns captured stdout/stderr;
  every script is persisted under the run's `analysis_code/`.
- **`analyze_paper_images`** (`metascience image-analysis`; CLI-only) -- the
  deterministic panel-duplication detector. Not callable by any agent: it runs
  as a child subprocess concurrent with the analysts and its findings reach
  the adjudicator by injection, quarantined.
- **`detect_tortured_phrases`** (`metascience tortured-phrases`; CLI-only) --
  the fingerprint-dictionary text screen, same arrangement as the image track.
