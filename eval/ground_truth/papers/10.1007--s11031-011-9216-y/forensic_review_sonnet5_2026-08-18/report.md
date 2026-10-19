# Forensic review -- Johnson et al. 2011

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## RETRACTED ARTICLE: Happiness as alchemy: Positive mood leads to self-serving responses to social comparisons
*Camille S. Johnson, Diederik A. Stapel. Motivation and Emotion. 2011. doi:10.1007/s11031-011-9216-y*

**Design:** four between-subjects lab experiments plus a pilot study; RETRACTED (journal-issued retraction header present in the article text)

<sub>Analysed as `10.1007--s11031-011-9216-y`</sub>

> **IMPOSSIBLE** — A reported significance test in Experiment 1 uses more degrees of freedom than the paper's own stated sample size can produce -- the analysis it presents could not have been run on the sample it describes.
>
> **In plain terms:** The researchers describe recruiting 47 women for this study. But one of their key statistical tests reports using more "degrees of freedom" than 47 people can supply -- roughly speaking, the test claims to have compared more people than were ever in the room. The underlying p-value is fine on its own terms, but the sample size behind it is not real.
>
> **Evidence:** "Female university (N = 47) students participated in the study for monetary compensation" and, for the contrast in question, "F(1, 46) = 6.95, p = 011" -- an error (denominator) degrees of freedom of 46. For any two-group comparison drawn from a fixed total sample, the maximum attainable error df is N-2; with the paper's own N=47 that ceiling is 45, one less than what is printed. The same experiment's other, larger 2x2 model already uses df=43 (e.g. F(1,43)=38.80), which is itself the largest df available from a 4-cell split of 47 participants -- so the single two-cell contrast cannot legitimately carry a larger df than the four-cell omnibus model.
> **Rests on:** logical necessity (no assumption added)
> **Reproduce:** `metascience f-to-p --f-value 6.95 --df1 1 --df2 46 --reported-p 0.011`

**Verdict: does_not_reconcile** (confidence: high)

> **Table coverage is unmeasured.** No cell was checked through `check_table`, which is the only route this census can count, so none of the 24 checkable cells can be ticked off by id. But 6 per-cell checks did run on values taken off this paper (`recalc_f_to_p`, `recalc_stat_to_p`). How much of the table that covers is not known -- it is not zero, and it is not measured here.

## Provenance of the analysis

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

5 study/studies, 6 variables, 17 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| pilot | Pilot study | unknown | 45 | ? | no |
| exp1 | Experiment 1 | unknown | 47 | ? | no |
| exp2 | Experiment 2 | unknown | 141 | ? | no |
| exp3 | Experiment 3 | unknown | 96 | ? | no |
| exp4 | Experiment 4 | unknown | 193 | ? | no |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Mood index (pilot) | interval | continuous | 1-9 | - | mean of items (k=4): four nine-point bipolar mood items, averaged (Cronbach's alpha = .91) | none -- composite granularity is 1/(items x n) | high |
| Self-evaluation index (pilot) | interval | continuous | 1-9 | - | mean of items (k=3): three nine-point Likert self-ratings (intelligent, competent, successful), averaged (Cronbach's alpha = .71) | none -- composite granularity is 1/(items x n) | high |
| Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1 | interval | discrete | 1-7 (integers) | - | measured | GRIM, GRIMMER, SPRITE | high |
| Target attractiveness rating (manipulation check) | interval | discrete | 1-7 (integers) | - | measured | GRIM, GRIMMER, SPRITE | high |
| Momentary mood rating (Experiments 2/3/4 manipulation check) | interval | discrete | 1-7 (integers) | - | measured | GRIM, GRIMMER, SPRITE | high |
| Similarity index (Experiment 3, Table 2) | interval | continuous | 1-9 | - | mean of items (k=3): three nine-point similarity items, averaged (alpha = .87) | none -- composite granularity is 1/(items x n) | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Pilot study | one_way_anova | Mood index (pilot) (likert_composite) | mood condition | 45 | ? | none reported |
| Pilot study | one_way_anova | Self-evaluation index (pilot) (likert_composite) | mood condition | 45 | ? | none reported |
| Experiment 1, Manipulation check | one_way_anova | Target attractiveness rating (manipulation check) (likert_item) | direction of comparison | 47 | ? | none reported |
| Experiment 1, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1 (likert_item) | similarity cue, direction | 47 | ? | none reported |
| Experiment 1, Self-evaluations (unshared birthday) | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1 (likert_item) | direction | 47 | ? | none reported |
| Experiment 2, Manipulation check | one_way_anova | Momentary mood rating (Experiments 2/3/4 manipulation check) (likert_item) | mood condition | 141 | ? | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1 (likert_item) | mood, direction, similarity cue | 141 | ? | none reported |
| Experiment 2, Positive mood | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1 (likert_item) | direction, similarity cue | 141 | ? | none reported |
| Experiment 2, Negative mood | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1 (likert_item) | direction | 141 | ? | none reported |
| Experiment 3, Manipulation check | one_way_anova | Momentary mood rating (Experiments 2/3/4 manipulation check) (likert_item) | mood condition | 96 | ? | none reported |
| Experiment 3, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1 (likert_item) | similarity cue, mood | 96 | ? | none reported |
| Experiment 3, Similarity cue and mood effects | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1 (likert_item) | mood | 96 | ? | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Similarity index (Experiment 3, Table 2) (likert_composite) | direction | 96 | ? | none reported |
| Experiment 3, Perceptions of similarity | pearson_correlation | Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1 (likert_item) | Target attractiveness rating (manipulation check) | 26 | ? | none reported |
| Experiment 4, Manipulation check | one_way_anova | Momentary mood rating (Experiments 2/3/4 manipulation check) (likert_item) | mood condition | 193 | ? | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1 (likert_item) | load, mood, direction | 193 | ? | none reported |
| Experiment 4, Cognitive load conditions | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1 (likert_item) | direction (vs control) | 193 | ? | none reported |

#### Variable/test mismatches

A parametric test is applied to an outcome this analysis typed as non-continuous. That is not proof of an error -- the typing may be wrong, and some parametric tests are robust -- but each pair below should be checked against the paper.

- **Pilot study**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Mood index (pilot)** is typed `likert_composite`.
- **Pilot study**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation index (pilot)** is typed `likert_composite`.
- **Experiment 1, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Target attractiveness rating (manipulation check)** is typed `likert_item`.
- **Experiment 1, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1** is typed `likert_item`.
- **Experiment 1, Self-evaluations (unshared birthday)**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1** is typed `likert_item`.
- **Experiment 2, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Momentary mood rating (Experiments 2/3/4 manipulation check)** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1** is typed `likert_item`.
- **Experiment 2, Positive mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1** is typed `likert_item`.
- **Experiment 2, Negative mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1** is typed `likert_item`.
- **Experiment 3, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Momentary mood rating (Experiments 2/3/4 manipulation check)** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1** is typed `likert_item`.
- **Experiment 3, Similarity cue and mood effects**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1** is typed `likert_item`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index (Experiment 3, Table 2)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `pearson_correlation` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1** is typed `likert_item`.
- **Experiment 4, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Momentary mood rating (Experiments 2/3/4 manipulation check)** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1** is typed `likert_item`.
- **Experiment 4, Cognitive load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1/2/4 and Table 1** is typed `likert_item`.

_17 of 17 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. Denominator degrees of freedom (df=46) exceeds the paper's own stated sample size (N=47)  [IMPOSSIBLE | confidence: high]

**In plain terms.** One of the paper's central results -- that participants who did not share a birthday with a comparison target responded symmetrically, the finding used to argue that ambiguous similarity information is necessary for the self-serving effect -- reports a statistical test drawn from more people than the study says it recruited. This is not a rounding slip; it is a number that cannot come from the sample as described, which means a reader cannot verify what test was actually run or trust the result attached to it.

- **Location:** Experiment 1, Self-evaluations (unshared-birthday conditions)
- **Reported:** "F(1, 46) = 6.95, p = 011" for the contrast between upward and downward comparison targets, in the unshared-birthday subset of a study explicitly described as "Female university (N = 47) students."
- **Computed:** For any independent two-group split of a fixed total sample, maximum attainable error df = N-2. With the paper's own stated N=47, that ceiling is 45 -- one less than the printed df=46, and less than the 46 minimum participants (df+2) the printed value would require. The same experiment's own 4-cell 2x2 omnibus model (the largest model the design supports) uses df=43 throughout (F(1,43)=38.80; F(1,43)=7.77; F(1,43)=5.99) -- consistent with N=47 minus 4 cells -- so this single two-group contrast, drawn from at most half the sample, cannot legitimately exceed even that larger model's df, let alone the absolute N-2 ceiling. Re-running the F-to-p conversion (F=6.95, df1=1, df2=46) confirms the printed p=.011 is internally consistent with the printed F and df -- the arithmetic of the p-value is not the problem; the problem is that df=46 cannot have come from this sample.
- **As printed in the paper:** **Experiment 1, Self-evaluations (unshared birthday conditions)** -- “Exposure to the upward comparison target led to lowered self-evaluations (M = 3.33, SD = .65) compared to the downward comparison target (M = 4.64, SD = 1.50), F(1, 46) = 6.95, p = 011.” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own stated N=47 for Experiment 1 and the logically necessary bound df<=N-2 for any two-group comparison drawn from a fixed sample; no invented range or scale is used.
- **Consequence:** 1 stated claim affected -- This is the specific contrast supporting the paper's claim that self-serving responding requires ambiguous similarity information (Hypothesis 1, stated as a primary result). The printed p-value cannot be traced to a real sample, so this piece of evidence for the paper's central claim cannot be verified. (asserted, not computed)
- **Reproduce:** `metascience f-to-p --f-value 6.95 --df1 1 --df2 46 --reported-p 0.011`

### 2. Identical denominator df (124) recurs across four unrelated subgroup breakdowns in two different experiments with different total sample sizes  [HIGHLY SUSPICIOUS | confidence: medium]

**In plain terms.** The number of participants behind a statistical test is supposed to change when you change the group being tested. Here, the exact same denominator (124) appears for a breakdown of positive-mood participants and, separately, for a breakdown of negative-mood participants in the same experiment -- and then again for entirely different breakdowns in an unrelated experiment with a different total number of participants. Under the sample sizes the paper itself reports elsewhere, this value cannot arise honestly from either subgroup. This bears directly on the tests that support three of the paper's four central hypotheses.

- **Location:** Experiment 2 (Positive mood and Negative mood sections, N=141) and Experiment 4 (No load and Cognitive load sections, N=193)
- **Reported:** Experiment 2: "in the positive mood conditions, direction of comparison, F(1, 124) = 14.79"; "presence of similarity cue... F(1, 124) = 18.61"; "interaction effect of direction of comparison and similarity information, F(1, 124) = 9.39"; and separately, "Among the negative mood conditions, only the main effect of direction was significant, F(1, 124) = 56.97." Experiment 4: "F(1,124) = 17.39"; "F(1,124) = 11.90"; "F(1,124) = 17.89"; "F(1,124) = 10.37"; "F(1,124) = 23.14"; "t(124) = -3.30"; "F(1,124) = 18.83"; "F(1,124) = 7.84."
- **Computed:** Experiment 2's own internally consistent models establish a factorial-only sample of N=126 (the paper's df=118 omnibus model on the full 8-cell design implies N_factorial-8=118, i.e. N=126, leaving a control n of 15 against the total N=141 and its df=132 nine-condition model). The positive-mood-only and negative-mood-only subgroup tests, each drawn from a subset of that same 126-person factorial pool, both report the identical residual df=124 -- which, on a 2(direction)x2(cue) model (4 parameters), implies a subgroup n of 128 for EACH mood group. Two subgroups of 128 people cannot both be drawn from a shared pool of 126: even a single subgroup of 128 already exceeds the entire factorial sample. The identical value 124 is then reused, unexplained, for eight further tests across a wholly different experiment (Experiment 4, total N=193, its own factorial-only omnibus using df=110).
- **As printed in the paper:** “As can be seen in Table 1, in the positive mood conditions, direction of comparison, F(1, 124) = 14.79, p < .001... Among the negative mood conditions, only the main effect of direction was significant, F(1, 124) = 56.97, p < .001.” _(found in the paper's text, across an ellipsis)_
- **Assumptions:** Assumes the positive-mood-only and negative-mood-only tests use a standard multi-parameter ANOVA model (direction x cue) rather than an undocumented pooled-error contrast scheme; the paper does state it used single-df pooled contrasts (citing Jaccard 1998) for its explicit control-condition comparisons (the F(1,132)/F(1,132) tests), so an unreported variant of that same pooling scheme applied instead to these mood-subset breakdowns cannot be entirely ruled out, which is why this stops short of impossible.
- **Reproduce:** no runnable command -- the review's command used an option this tool does not have. The finding's own numbers are above; re-derive from those.

### 3. Two significant p-values print without their leading decimal point  [SUSPICIOUS | confidence: high]

**In plain terms.** Two of the paper's reported p-values are missing their decimal point (printed as "011" instead of ".011"). Read the intended way, the numbers are fine. On its own this is an ordinary proofreading slip -- but one of the two sentences it appears in is also the sentence carrying the impossible degrees-of-freedom problem above, which is worth noting even though it proves nothing by itself.

- **Location:** Experiment 1, Self-evaluations; Experiment 4, Self-evaluations
- **Reported:** "F(1, 46) = 6.95, p = 011" and "F(1, 110) = 11.23, p = 001" (both missing the leading decimal that would read p = .011 and p = .001).
- **Computed:** Recalculating F(1,46)=6.95 gives p=.0114, consistent with the intended .011 reading; the second instance sits alongside a df already found to be irreconcilable with the paper's stated N (see rank 1). Both are typesetting defects rather than arithmetic errors on their own.
- **As printed in the paper:** “F(1, 46) = 6.95, p = 011.” _(found in the paper's text)_
- **Assumptions:** None beyond ordinary APA decimal notation; treated as a proofreading slip, not a computational one.
- **Reproduce:** `metascience f-to-p --f-value 6.95 --df1 1 --df2 46 --reported-p 0.011`

### 4. No table or experiment reports per-cell sample sizes, blocking GRIM/GRIMMER verification of every mean and SD  [INDETERMINATE | confidence: high]

**In plain terms.** The paper's two summary tables report averages and spreads for each experimental group, but never say how many people were in each group -- only the total for the whole experiment. That gap means the paper's most checkable numbers (the individual cell means) cannot be verified at all, in either direction. This is a reporting gap, not evidence of a problem with the numbers themselves.

- **Location:** Table 1 (Experiment 2, 8 cells) and Table 2 (Experiment 3, 16 cells); all four experiments generally
- **Reported:** Both tables print mean (SD) on stated, printable scales (a single seven-point self-evaluation item; a three-item nine-point similarity composite), but neither the tables nor the surrounding text state a per-cell or per-condition n anywhere in the paper -- only total experiment N and various ANOVA error degrees of freedom.
- **Computed:** check_table was run against both tables' 24 mean/SD cells; grim_check, grimmer_check and sprite_reconstruct all refused for want of a per-cell n, which error df alone cannot supply without assuming perfectly balanced cells (an assumption the instructions direct against making).
- **As printed in the paper:** “5.25 (.93)” _(found in a table)_
- **Assumptions:** None -- this is a refusal to check, not a finding about the numbers themselves.
- **Reproduce:** no runnable command -- the review's command did not match the tool's arguments. The finding's own numbers are above; re-derive from those.

## What we could NOT check

- **Table 1 (Experiment 2), all 8 mean/SD cells** — No per-cell or per-condition sample size is reported anywhere in the paper, so GRIM/GRIMMER/SPRITE cannot be run on these stated-scale (1-7) single-item means without assuming an unstated per-cell n.
- **Table 2 (Experiment 3), all 16 mean/SD cells** — Same missing-per-cell-n limitation as Table 1. The Similarity row is additionally a 3-item composite mean, which this toolkit's GRIM/GRIMMER cannot correctly evaluate even with n known.
- **Pilot study mood and self-evaluation composite indices** — Both are multi-item composite means (4 items; 3 items); this toolkit's granularity checks model single-item integer data, not k-item composites, and per-group n is not reported either.
- **All experiments, per-cell/per-condition sample sizes** — No experiment reports the number of participants in each factorial cell; only total N and various ANOVA error degrees of freedom are given, which do not determine individual cell sizes without assuming balance.
- **Pairwise p-values reported only as thresholds (e.g. 'p < .001', 'ps > .84')** — A large share of the paper's p-values are reported only as bounds without an exact value or accompanying test statistic sufficient for further recomputation.
- **table rows Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation and 10 more** — grim_check not run: grim_check needs n and this cell carries none; supply n for this row (the participants paragraph or the table footnote usually states it)
- **table rows Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation and 10 more** — grimmer_check not run: grimmer_check needs n and this cell carries none; supply n for this row (the participants paragraph or the table footnote usually states it)
- **table rows Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation and 10 more** — sprite_reconstruct not run: sprite_reconstruct needs n and this cell carries none; supply n for this row (the participants paragraph or the table footnote usually states it)
- **table rows Similarity, Similarity, Similarity, Similarity, Similarity, Similarity and 2 more** — grim_check, grimmer_check, sprite_reconstruct not run: multi-item composite whose scoring is undeclared. If the score is a MEAN of items its granularity is 1/(items*n) and grim_test has no `items` parameter, so checking at 1/n would manufacture an impossibility; if it is a SUM the granularity is 1/n and the check is valid. Declare `derivation` as 'mean_of_items' or 'sum_of_items' to resolve this -- the field is already in the schema and the prompt asks for it.

## Questions for the authors

_Each of these is answerable from what the authors already have. None presupposes an error on their part: an inconsistency is far more often a reporting slip, or a mistake by this tool in reading the number off the page, than anything else._

1. Could you supply the exact analytic model (including the number of participants) used for the F(1, 46) = 6.95 contrast in Experiment 1's unshared-birthday self-evaluations, and separately for the F(1, 124) tests reported in Experiment 2's positive-mood and negative-mood sections and in Experiment 4's no-load and cognitive-load sections?
   <sub>Would resolve: These denominator degrees of freedom cannot be reconciled with the paper's own stated total sample sizes under a standard ANOVA model; the authors' underlying dataset or analysis code, if available, would settle whether an unreported pooled-error or contrast specification explains the values.</sub>

## Limitations

- Figures were not read in this stage; Stage 1 examined all three figures with extract_figures and found none carries a numeric value not already printed in the text or tables, and that finding is carried forward here without independent re-verification of the images.
- Three findings in the Stage-1 sweep were initially flagged by the automated second-look worklist as 'quote not located.' On re-reading the source XML directly (rather than relying on a possibly non-contiguous composited quote), all three underlying passages were located verbatim in the paper; the marker fired because the sweep's quotes joined non-adjacent sentences with ellipses rather than because the values were misread. This is recorded once here rather than three times.
- No per-cell or per-condition sample sizes are reported anywhere in this paper, which blocks GRIM/GRIMMER/SPRITE verification of every individual mean and SD in Tables 1 and 2 -- the paper's most granular, and otherwise most checkable, numbers.
- This paper carries a journal-issued retraction header and is one of the works covered by the Levelt Committee's finding of fabricated data by co-author Diederik Stapel; that background is noted for context but is not itself evidence for any specific finding above, each of which rests on the paper's own printed numbers.
- R cross-checks were not applicable here: no GRIM/GRIMMER/SPRITE finding was produced by the sweep (the paper's stated scales support these checks in principle, but the missing per-cell n blocks them, per the indeterminate finding above), so the r_grim_ground_truth / r_sprite_ground_truth cross-check requirement did not apply to any finding in this report.
- No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.

## Coverage

- **Statistics found:** 63; **checked:** 68
- **Tools run:** extract_xml, get_table, parse_cells_typed, check_table, statcheck, recalc_f_to_p, recalc_stat_to_p, multiplicity_report, extract_pdf, extract_figures
- **Tables checked:** Table 1 (Experiment 2), Table 2 (Experiment 3)
- **Checkable table cells:** 24 of 24 surveyed; **checked:** 0
    - 24 could not be checked without knowing what kind of quantity the row reports
- **Every checkable item:** 157 registered; 24 refused with a stated reason; **133 outstanding**
    - how many were CHECKED is not measured -- no persisted item identity joins a tool call back to a manifest row, so how many items were CHECKED cannot be counted. This is not a count of zero. This is not a count of zero.
- **Stage-1 findings:** 13 raised; 5 carried into this report; 8 not carried
- **Traceable to the page:** 10 of 11 checks recorded the passage their numbers were read from; 9 of those were located in the paper's own text.
- **1 check cited numbers with no quoted source.** Those values cannot be traced to a passage from this document; re-read them at source before relying on them.
- **1 quoted passage is ours, not the paper's.** Every number in it was found in the paper, but the sentence around those numbers was assembled by this review and does not appear as written -- so do not search the PDF for it. The CHECK is sourced; only the quotation marks over-promise.

## What each check does

One entry per check that ran on this paper. The **assumptions** are the conditions under which its verdict holds; where one is unmet the verdict is capped, not merely caveated.

### `check_table` — absolute

Runs every applicable check on a typed table in one call; the worst row wins.

**What its verdict means.** Absolute (possible vs impossible). Exact arithmetic over the printed values and their rounding intervals. Subject to the preconditions below, a flagged result cannot be produced by any dataset.

**Strongest verdict it may reach:** `impossible`

**It assumes:**
- A ROUTER, so the `absolute` class above describes only its CEILING, not every row it returns. `impossible` can still only come from a bound-free arithmetic check; but a `highly_suspicious` or `suspicious` row may have come from a probabilistic one (a Wald-CI judgement, a dispersion plausibility). Read the per-row `tool` and look up ITS card -- the routed check's evidence class governs, not this one.
- Variables must be truthfully declared -- data_type, bounds and bound_source gate every downstream check.
- Declare provenance for figure-read values; the exact-arithmetic checks then refuse them rather than judge them.

### `extract_figures` — descriptive

Locates, crops and captions the figures in a PDF; renders no verdict.

**What its verdict means.** Descriptive. Extracts, parses or computes a quantity; it does not itself render a verdict about the paper.

**Strongest verdict it may reach:** `indeterminate`

**It assumes:**
- Values later read off the cropped artwork carry measured provenance and are barred from exact-arithmetic checks.

### `extract_pdf` — descriptive

Extracts text and resolvable tables from a PDF; renders no verdict.

**What its verdict means.** Descriptive. Extracts, parses or computes a quantity; it does not itself render a verdict about the paper.

**Strongest verdict it may reach:** `indeterminate`

**It assumes:**
- An empty `tables` list does not mean the paper has no tables -- unresolvable grids remain in `text`.

### `extract_xml` — descriptive

Indexes body text and tables from publisher XML; renders no verdict.

**What its verdict means.** Descriptive. Extracts, parses or computes a quantity; it does not itself render a verdict about the paper.

**Strongest verdict it may reach:** `indeterminate`

**It assumes:**
- Tables flagged alignment_uncertain or image_only must be reconciled against the PDF before use.

### `get_table` — descriptive

Fetches one XML table in full with its label, caption and footnotes; renders no verdict.

**What its verdict means.** Descriptive. Extracts, parses or computes a quantity; it does not itself render a verdict about the paper.

**Strongest verdict it may reach:** `indeterminate`

**It assumes:**
- Footnotes define cell semantics -- 'n (%)' versus 'mean (SD)' -- so read them before typing cells.

### `multiplicity_report` — descriptive

Reports the family-wise error rate and four correction thresholds for a declared family.

**What its verdict means.** Descriptive. Extracts, parses or computes a quantity; it does not itself render a verdict about the paper.

**Strongest verdict it may reach:** `indeterminate`

**It assumes:**
- Everything is conditional on the DECLARED family; the same p-values give different answers under different families.
- FWER-if-independent is an upper bound when outcomes are correlated; survivor counts are a bound across four methods.
- Undisclosed analytic flexibility means the true comparison count can exceed the reported one, so this is a floor.

### `parse_cells_typed` — descriptive

Classifies table cells by kind before any check runs; renders no verdict.

**What its verdict means.** Descriptive. Extracts, parses or computes a quantity; it does not itself render a verdict about the paper.

**Strongest verdict it may reach:** `indeterminate`

**It assumes:**
- Cells returned `ambiguous` carry candidate readings and must not be fed to any forensic tool.

### `recalc_f_to_p` — probabilistic

Verifies a reported p against the range its rounded F and df imply.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The reported p is assumed to be the upper-tail F probability at the printed df.
- The printed F is rounded, so it asserts a p RANGE; only a p below that range is flagged.
- The F must come from the test its df describe, whose assumptions are inherited.

### `recalc_stat_to_p` — probabilistic

Recomputes a p-value from one printed test statistic and compares it to the reported p.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The named distribution and degrees of freedom are assumed to be the test the paper actually ran.
- The statistic is rounded, so it implies a p INTERVAL; the reported p is judged against that, never against the point value.
- Directional: only an OVER-claim is flagged. An under-claimed p is conservative reporting or a threshold.
- Ceiling `suspicious`: a one-tailed test, a different df convention or an unshown correction would each explain a disagreement.
- A missing df or n is reported as an incompletely reported test -- a property of the paper, since no implementation can recover it.

### `statcheck` — probabilistic

Extracts APA-style results and recomputes their p-values for internal consistency.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- Each p is recomputed assuming a two-tailed, unadjusted test.
- Only APA-formatted results are extracted; everything else is invisible to it.
- A p correct at its own printed precision is not an error.
- Inconsistencies are near-universal in honest work and must never support a misconduct verdict alone.

## Narrative

This paper reports a pilot study and four between-subjects lab experiments (total participants across studies: 45, 47, 141, 96, 193) arguing that positive mood leads people to interpret ambiguous social-comparison information in self-serving ways -- assimilating toward better-off comparison targets and contrasting away from worse-off ones -- while negative mood and unambiguous information do not produce this pattern. The paper was later retracted; it is one of the works covered by the Levelt Committee's finding that co-author Diederik Stapel fabricated data across a large body of his published work. That history is background, not evidence, and every finding below rests on the paper's own printed numbers rather than on that history.

Sixty-three NHST statistics were recovered from the text and run through statcheck; none showed a decision-changing gap between a printed test statistic and its printed p-value. Several individual F-to-p recalculations (the pilot's F(1,42)=.27/p=.76, Experiment 3's F(1,94)=1.50/p=.83, and others) turned up sizeable but non-decision-changing gaps -- each an under-claim, where the true p implied by the statistic is smaller and more significant than what was printed, the conservative direction rather than the inflating one. Two families of planned control contrasts (four tests in Experiment 2, eight in Experiment 4) were checked for multiplicity and none loses significance under any of four standard corrections. As far as this class of check goes, the paper's arithmetic is largely unremarkable.

The problem is elsewhere, in the bookkeeping behind the degrees of freedom themselves. Experiment 1 states plainly that 47 women took part, and its main 2x2 model consistently uses an error df of 43 -- exactly what a four-cell split of 47 participants supports. But the one contrast that anchors the paper's headline claim about Experiment 1 (that responses are symmetric, not self-serving, when similarity information is absent) reports F(1, 46) = 6.95: an error df of 46, one more than even the full sample's own two-group ceiling of 45, and three more than the four-cell model's own df of 43. The p-value that goes with it is internally correct for the printed F and df -- this is not a p-value error -- but the degrees of freedom cannot have come from this sample under any partition of it.

That is bad enough to be the headline on its own. It is not the only instance of the pattern. The identical value 124 recurs as the denominator df for four different subgroup breakdowns split across two experiments with different total sample sizes -- positive-mood-only and negative-mood-only tests in Experiment 2 (N=141), and no-load and cognitive-load tests in Experiment 4 (N=193). Experiment 2's own internally consistent numbers pin its factorial-only sample at 126 participants; a positive-mood-only 2x2 test with df=124 implies a subgroup of 128 people, which alone exceeds the entire 126-person factorial pool, before even asking where the negative-mood participants (needed for the parallel df=124 test reported two paragraphs later) would come from. I have stopped short of calling this impossible outright, because the paper does describe using an unreported pooled single-degree-of-freedom contrast method (citing Jaccard 1998) for some of its comparisons, and I cannot fully rule out an undocumented variant of that scheme producing this number by a route I have not reconstructed. But every ordinary reading of the reported model fails, and the same failure recurring identically across two unrelated experiments is not the kind of thing honest rounding or typesetting produces.

A minor, lower-stakes observation: two of the paper's p-values print without their decimal point ("p = 011" and "p = 001" rather than ".011" and ".001"). Read the intended way the arithmetic checks out, so this is recorded as an ordinary proofreading slip -- worth noting only because one of the two sentences carrying it is the same sentence carrying the impossible-df problem above.

Finally, neither of the paper's two data tables, nor any of its four experiments, reports how many participants sat in each experimental cell -- only the total N per experiment and various omnibus error degrees of freedom. That gap makes it impossible to run GRIM, GRIMMER, or SPRITE on any of the paper's individual cell means, which are otherwise exactly the kind of stated-scale, small-Likert data those checks are built for. This is recorded as a reporting gap rather than a finding about the numbers themselves, but it means the paper's most granular claims are simply not checkable from what it printed.

I do not have confidence that the reported statistics in Experiment 1 and the positive/negative-mood breakdowns of Experiment 2 and Experiment 4 come from the samples the paper describes.

## How to read this

**What this document is.** An automated check of a paper against itself: whether
the numbers it reports are mutually consistent, whether any dataset could have
produced them, whether its statistics follow from the values printed beside
them, and whether its own record -- tables, references, supplementary material
-- holds together. Where it says a value is "impossible", it means the reported
figures contradict one another arithmetically.

**What this document is not.** It is not a finding of fraud, misconduct, error,
or bad faith, and it is not adequate for definitive detection of any of those.
An inconsistency has many ordinary causes, and the innocent ones are far more
common than the guilty ones: typographical error, rounding or transcription
slips, a mislabelled sample size, values copied from a superseded analysis, or
-- most often -- a mistake by this tool in reading the number off the page.

**The base rates that matter here.** In our own ground-truth corpus, half of the
clean control papers contain at least one statcheck inconsistency. Reporting
errors are near-universal in honest work. Separately, nearly all of this
pipeline's failure lives in getting numbers off a PDF, not in the arithmetic:
the arithmetic is exact and the extraction is not. Any individual flag in this
report is therefore much more likely to be our extraction error than the
authors' misconduct.

**Anything marked `indeterminate` is a refusal, not a negative result.** It means
a precondition could not be verified and the tool declined to judge. It is not
evidence of a problem, and it is not evidence of the absence of one.

**What it has been tested on.** at least 37 runs over 19 papers, almost all of them
primary biomedical or psychology research and most of them human randomised
trials. No qualitative, bench-science, -omics, or non-biomedical paper has ever
been through it, and no claim here about its accuracy transfers to one. It is
**not designed for narrative reviews** -- their numbers belong to the papers
they cite, so a flag would land on the wrong authors -- and auditing a
**meta-analysis or systematic review** is a separate undertaking with different
tools, which this is not. The full breakdown is in "What this has been tested
on", below.

**Before treating anything here as a problem:** verify the number by hand against
the published paper, since the most likely explanation is that this tool misread
it. If it holds up, the appropriate next step is to contact the corresponding
author and ask -- most discrepancies are resolved by a correction or an
explanation. Requesting the raw data is the only thing that can actually settle
the question. Public allegations are not an appropriate use of this output.

## What this has been tested on

The checks in this report were built and calibrated against a small corpus. Naming it is not modesty -- it is the denominator you need in order to know how much of it to believe for YOUR paper.

The archive holds **35 runs over 19 papers** (three of them blinded). Of those, 28 runs on 16 identifiable papers have been classified by design, by reading the reports:

- Human randomised trials and their follow-ups -- 12 runs (the bulk of it -- 3-arm rTMS trial, stroke RCTs, a pooled 2-RCT analysis, a home-visiting follow-up, blinded-control and antibiotics trials)
- Rodent / preclinical neuroscience -- 2 runs (nanoparticle toxicity, ischaemia models)
- Observational multilevel community psychology -- 3 runs (coalition study)
- Complex-survey cross-sectional epidemiology -- 2 runs (veterans / suicidality)
- Social-psychology laboratory experiments -- 2 runs (one of them retracted)
- Cost-effectiveness analysis -- 1 run (a Markov cost-utility model)
- Retrospective records with latent-class analysis -- 1 run (inpatient comorbidities)
- Ecological momentary assessment / intensive longitudinal -- 4 runs (mediation model; three of the four are 2026-08-11 re-runs of the same paper -- the warrant-schema run and the clamped re-run are the repeat-run pair)
- A correction notice -- 1 run (not a study at all; the run correctly said so and audited the notice)

**Designs with no representation at all.** Nothing resembling these has ever been through this pipeline, so no claim here about its accuracy transfers to them:

- qualitative and mixed-methods research
- bench chemistry, materials science and physics
- genomics and other high-throughput -omics
- economics, political science and other quantitative social science outside psychology
- any field outside biomedicine and psychology (one environmental-journal paper is itself a clinical rehabilitation study)
- single-case and small-N designs
- simulation and modelling studies

**Document kinds this is not the instrument for:**

- **A narrative review** -- not designed for. Nearly every number in a narrative review is quoted from somebody else's paper. Checking those numbers tests the papers being reviewed, not the review, so a flag lands on authors who did not produce the value. Do not use this output to judge a narrative review.
- **A systematic review** -- a separate undertaking. Auditing a systematic review means auditing its search strategy, its inclusion criteria and how they were applied, its extraction procedure and its risk-of-bias assessment. None of that is what the checks here test. Treat any consistency result below as narrow bookkeeping about the numbers printed, not as an assessment of the review.
- **A meta-analysis** -- a separate undertaking. A meta-analysis's own numbers are pooled estimates, weights and heterogeneity statistics. What makes one sound -- search completeness, correct effect-size conversion, publication-bias analysis, the independence of the included samples -- is a different audit with different tools, and this toolkit does not perform it. Granularity checks in particular say nothing useful about a pooled standardised mean difference.
