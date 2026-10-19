# Forensic review -- Johnson et al. 2011

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## RETRACTED ARTICLE: Happiness as alchemy: Positive mood leads to self-serving responses to social comparisons
*Camille S. Johnson, Diederik A. Stapel. Motivation and Emotion. 2011. doi:10.1007/s11031-011-9216-y*

**Design:** Four between-subjects factorial laboratory experiments plus a pilot study; article is marked RETRACTED on every page of the PDF

<sub>Analysed as `10.1007--s11031-011-9216-y`</sub>

> **IMPOSSIBLE** — Experiment 4's control condition is reported as mean 4.20 with a standard deviation of 0.21 on a seven-point single-item rating, a pair no sample of whole-number ratings can produce at any group size tested, and every one of that experiment's eight comparisons is measured against it.
>
> **In plain terms:** In the fourth experiment, the comparison group everything else is measured against is reported with an average of 4.20 and a spread of 0.21. Because each person gave a single whole-number rating from 1 to 7, only certain combinations of average and spread are arithmetically possible, and this one is not -- at any group size we tried, and under either of the two standard ways of calculating spread. Two separate pieces of software agree. All eight of that experiment's reported comparisons are measured against this pair of numbers.
>
> **Evidence:** "Higher levels of self-evaluations relative to the control condition (M = 4.20, SD = .21) were found, regardless of whether participants upwardly compared (M = 5.64, SD = .78; F(1,124) = 17.39, p < .001) or downwardly compared (M = 5.15, SD = .81), F(1,124) = 11.90, p = .001." The same pair is repeated in the load section: "Compared to a control condition (M = 4.20, SD = .21)". The measure is stated: participants "completed the same measures of mood, own attractiveness, and other attractiveness as in Experiments 1 and 2", and Experiment 1 prints "a seven-point scale (1 = not at all, 7 = extremely)". GRIMMER returns impossible at n = 10, 15, 20, 25 and 75, under both the sample (n-1) and population (n) SD conventions, and with the scale bounds removed entirely (feasible_ignoring_bounds: false). SPRITE returns no_solution_proven. R's rsprite2 independently refuses the parameters with "fails GRIMMER test".
> **Rests on:** logical necessity (no assumption added)
> **Reproduce:** `metascience grimmer --mean 4.20 --sd 0.21 --n 15 --scale-min 1 --scale-max 7 --decimals 2 --decimals-sd 2 --data-type likert --discreteness-source stated`

**Verdict: does_not_reconcile** (confidence: high)

> **Table coverage:** 8 of 24 checkable cells were checked cell by cell, and 6 further table rows were checked in batch by check_summation_batch. The two counts are of different things and are not added: the batch tools report rows, not the cell identifiers this census uses, so the true combined coverage is somewhere between 8 and 14 of 24. A further 37 per-cell checks ran (`check_effect_plausibility`, `detect_duplication`, `grim_check`, `grimmer_check`, `r_grim_ground_truth`, `r_sprite_ground_truth`, `recalc_anova`, `recalc_f_to_p`, `rivets_anova`, `sprite_reconstruct`) and report no cell ids at all, so the top of that range is a floor rather than a ceiling.

## Provenance of the analysis

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

5 study/studies, 10 variables, 62 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| pilot | Pilot study: mood induction validation | rct | 45 | participant | no |
| exp1 | Experiment 1: positive mood, shared vs different birthday, upward vs downward target | rct | 47 | participant | no |
| exp2 | Experiment 2: 2 mood x 2 direction x 2 birthday cue, plus hanging control | rct | 141 | participant | no |
| exp3 | Experiment 3: 2 mood x 2 direction x 2 ambiguity of similarity cue | rct | 96 | participant | no |
| exp4 | Experiment 4: 2 mood x 2 direction x 2 cognitive load, plus hanging control | rct | 193 | participant | no |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Self-evaluation (own attractiveness) | ordinal | discrete | 1-7 (integers) | scale points | measured | GRIM, GRIMMER, SPRITE | high |
| Rated attractiveness of the comparison target | ordinal | discrete | 1-7 (integers) | scale points | measured | GRIM, GRIMMER, SPRITE | high |
| Self-reported mood (Experiments 2 and 4) | ordinal | discrete | 1-7 (integers) | scale points | measured | GRIM, GRIMMER, SPRITE | high |
| Mood index (pilot study) | ordinal | discrete | 1-9 (integers) | scale points | mean of items (k=4): four nine-point bipolar mood items, averaged (Cronbach's alpha = .91) | none -- composite granularity is 1/(items x n) | high |
| Self-evaluation index (pilot study) | ordinal | discrete | 1-9 (integers) | scale points | mean of items (k=3): intelligent, competent, successful, each on a nine-point Likert scale, averaged (alpha = .71) | none -- composite granularity is 1/(items x n) | high |
| Similarity index (Experiment 3) | ordinal | discrete | 1-9 (integers) | scale points | mean of items (k=3): three nine-point similarity questions, averaged (alpha = .87) | none -- composite granularity is 1/(items x n) | high |
| Mood induction condition | nominal | discrete | positive; negative; neutral/control | - | measured | percentage GRIM on cell counts | high |
| Direction of comparison | nominal | discrete | upward (more attractive target); downward (less attractive target) | - | measured | DEBIT; percentage GRIM | high |
| Similarity cue | nominal | discrete | shared birthday; different birthday; ambiguous aesthetic preference; unambiguous aesthetic preference | - | measured | DEBIT; percentage GRIM | high |
| Cognitive load (Experiment 4) | nominal | discrete | load (8-digit number rehearsal); no load | - | measured | DEBIT; percentage GRIM | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Pilot study, first results paragraph | one_way_anova | Mood index (pilot study) (likert_composite) | Mood induction condition | 45 | none | none reported |
| Pilot study, first results paragraph | independent_t | Mood index (pilot study) (likert_composite) | Mood induction condition | 45 | none | none reported |
| Pilot study, first results paragraph | independent_t | Mood index (pilot study) (likert_composite) | Mood induction condition | 45 | none | none reported |
| Pilot study, second results paragraph | one_way_anova | Self-evaluation index (pilot study) (likert_composite) | Mood induction condition | 45 | none | none reported |
| Experiment 1, Manipulation check | one_way_anova | Rated attractiveness of the comparison target (likert_item) | Direction of comparison | 47 | none | none reported |
| Experiment 1, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Similarity cue | 47 | none | none reported |
| Experiment 1, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Similarity cue, Direction of comparison | 47 | none | none reported |
| Experiment 1, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Direction of comparison | 47 | none | none reported |
| Experiment 2, Manipulation check | one_way_anova | Self-reported mood (Experiments 2 and 4) (likert_item) | Mood induction condition | 141 | none | none reported |
| Experiment 2, Manipulation check | one_way_anova | Rated attractiveness of the comparison target (likert_item) | Direction of comparison | 141 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Mood induction condition, Direction of comparison, Similarity cue | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Similarity cue | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Direction of comparison | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Mood induction condition, Similarity cue | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Mood induction condition, Direction of comparison | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Similarity cue, Direction of comparison | 126 | none | none reported |
| Experiment 2, Positive mood | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Direction of comparison | ? | none | none reported |
| Experiment 2, Positive mood | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Similarity cue | ? | none | none reported |
| Experiment 2, Positive mood | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Similarity cue, Direction of comparison | ? | none | none reported |
| Experiment 2, Positive mood contrasts vs control | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | - | ? | none | none reported |
| Experiment 2, Positive mood contrasts vs control | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | - | ? | none | none reported |
| Experiment 2, Positive mood contrasts vs control | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | - | ? | none | none reported |
| Experiment 2, Positive mood contrasts vs control | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | - | ? | none | none reported |
| Experiment 2, Negative mood | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Direction of comparison | ? | none | none reported |
| Experiment 3, Manipulation check | one_way_anova | Self-reported mood (Experiments 2 and 4) (likert_item) | Mood induction condition | 96 | none | none reported |
| Experiment 3, Manipulation check | one_way_anova | Rated attractiveness of the comparison target (likert_item) | Direction of comparison | 96 | none | none reported |
| Experiment 3, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Similarity cue | 96 | none | none reported |
| Experiment 3, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Direction of comparison | 96 | none | none reported |
| Experiment 3, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Mood induction condition | 96 | none | none reported |
| Experiment 3, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Similarity cue, Mood induction condition | 96 | none | none reported |
| Experiment 3, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Similarity cue, Direction of comparison | 96 | none | none reported |
| Experiment 3, Similarity cue and mood effects on responses | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Mood induction condition | ? | none | none reported |
| Experiment 3, Similarity cue and direction of comparison effects on responses | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Direction of comparison | ? | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Similarity index (Experiment 3) (likert_composite) | Similarity cue | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Similarity index (Experiment 3) (likert_composite) | Direction of comparison | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Similarity index (Experiment 3) (likert_composite) | Direction of comparison, Mood induction condition | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Similarity index (Experiment 3) (likert_composite) | Similarity cue, Direction of comparison | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Similarity index (Experiment 3) (likert_composite) | Similarity cue, Direction of comparison, Mood induction condition | 96 | none | none reported |
| Experiment 3, Perceptions of similarity, planned comparison | one_way_anova | Similarity index (Experiment 3) (likert_composite) | Direction of comparison | ? | none | none reported |
| Experiment 3, Perceptions of similarity, planned comparison | one_way_anova | Similarity index (Experiment 3) (likert_composite) | Direction of comparison | ? | none | none reported |
| Experiment 3, Perceptions of similarity, planned comparison | one_way_anova | Similarity index (Experiment 3) (likert_composite) | Direction of comparison | ? | none | none reported |
| Experiment 3, Perceptions of similarity, planned comparison | one_way_anova | Similarity index (Experiment 3) (likert_composite) | Direction of comparison | ? | none | none reported |
| Experiment 3, Perceptions of similarity, correlations | pearson_correlation | Self-evaluation (own attractiveness) (likert_item) | Rated attractiveness of the comparison target | ? | none | none reported |
| Experiment 3, Perceptions of similarity, correlations | pearson_correlation | Self-evaluation (own attractiveness) (likert_item) | Rated attractiveness of the comparison target | ? | none | none reported |
| Experiment 3, Perceptions of similarity, correlations | pearson_correlation | Similarity index (Experiment 3) (likert_composite) | Rated attractiveness of the comparison target | ? | none | none reported |
| Experiment 4, Manipulation check | one_way_anova | Self-reported mood (Experiments 2 and 4) (likert_item) | Mood induction condition | ? | none | none reported |
| Experiment 4, Manipulation check | one_way_anova | Rated attractiveness of the comparison target (likert_item) | Direction of comparison | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Cognitive load (Experiment 4), Mood induction condition, Direction of comparison | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Cognitive load (Experiment 4) | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Mood induction condition | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Direction of comparison | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Cognitive load (Experiment 4), Mood induction condition | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Cognitive load (Experiment 4), Direction of comparison | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | Mood induction condition, Direction of comparison | ? | none | none reported |
| Experiment 4, No load conditions | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | - | ? | none | none reported |
| Experiment 4, No load conditions | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | - | ? | none | none reported |
| Experiment 4, No load conditions | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | - | ? | none | none reported |
| Experiment 4, No load conditions | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | - | ? | none | none reported |
| Experiment 4, Cognitive load conditions | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | - | ? | none | none reported |
| Experiment 4, Cognitive load conditions | independent_t | Self-evaluation (own attractiveness) (likert_item) | - | ? | none | none reported |
| Experiment 4, Cognitive load conditions | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | - | ? | none | none reported |
| Experiment 4, Cognitive load conditions | one_way_anova | Self-evaluation (own attractiveness) (likert_item) | - | ? | none | none reported |

#### Variable/test mismatches

A parametric test is applied to an outcome this analysis typed as non-continuous. That is not proof of an error -- the typing may be wrong, and some parametric tests are robust -- but each pair below should be checked against the paper.

- **Pilot study, first results paragraph**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Mood index (pilot study)** is typed `likert_composite`.
- **Pilot study, first results paragraph**: `independent_t` assumes a continuous, roughly normal outcome, but **Mood index (pilot study)** is typed `likert_composite`.
- **Pilot study, first results paragraph**: `independent_t` assumes a continuous, roughly normal outcome, but **Mood index (pilot study)** is typed `likert_composite`.
- **Pilot study, second results paragraph**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation index (pilot study)** is typed `likert_composite`.
- **Experiment 1, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Rated attractiveness of the comparison target** is typed `likert_item`.
- **Experiment 1, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 1, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 1, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 2, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-reported mood (Experiments 2 and 4)** is typed `likert_item`.
- **Experiment 2, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Rated attractiveness of the comparison target** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 2, Positive mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 2, Positive mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 2, Positive mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 2, Positive mood contrasts vs control**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 2, Positive mood contrasts vs control**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 2, Positive mood contrasts vs control**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 2, Positive mood contrasts vs control**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 2, Negative mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 3, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-reported mood (Experiments 2 and 4)** is typed `likert_item`.
- **Experiment 3, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Rated attractiveness of the comparison target** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 3, Similarity cue and mood effects on responses**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 3, Similarity cue and direction of comparison effects on responses**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity, planned comparison**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity, planned comparison**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity, planned comparison**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity, planned comparison**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity, correlations**: `pearson_correlation` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 3, Perceptions of similarity, correlations**: `pearson_correlation` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 3, Perceptions of similarity, correlations**: `pearson_correlation` assumes a continuous, roughly normal outcome, but **Similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 4, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-reported mood (Experiments 2 and 4)** is typed `likert_item`.
- **Experiment 4, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Rated attractiveness of the comparison target** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 4, No load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 4, No load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 4, No load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 4, No load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 4, Cognitive load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 4, Cognitive load conditions**: `independent_t` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 4, Cognitive load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.
- **Experiment 4, Cognitive load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness)** is typed `likert_item`.

_62 of 62 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. Experiment 4's control mean and SD (4.20, 0.21) cannot arise from whole-number ratings at any group size tested  [IMPOSSIBLE | confidence: high]

**In plain terms.** The fourth experiment compares eight groups against one no-treatment comparison group, reported as averaging 4.20 with a spread of 0.21. Each participant gave a single whole-number score from 1 to 7, and that restricts which average-and-spread combinations can exist. This one cannot exist -- we tested group sizes from 10 to 75, both standard formulas for spread, and with the 1-to-7 limits removed; it failed every time, and a second, independent piece of statistical software reached the same conclusion. The paper does not say how many people were in this group, so we could not test the one true size, but no size we tried works. Every conclusion the fourth experiment draws is measured against these two numbers.

- **Location:** Experiment 4, No load conditions and Cognitive load conditions
- **Reported:** "Higher levels of self-evaluations relative to the control condition (M = 4.20, SD = .21) were found"; repeated verbatim in the load section as "Compared to a control condition (M = 4.20, SD = .21)". Experiment 4's Procedure states participants "completed the same measures of mood, own attractiveness, and other attractiveness as in Experiments 1 and 2"; Experiment 1's Dependent measures prints "a seven-point scale (1 = not at all, 7 = extremely)".
- **Computed:** GRIMMER returns `impossible` at n = 10, 15, 20, 25 and 75. At n = 15 the only mean-consistent integer total is 63, and no integer sum-of-squares of the required parity falls in the window [265.19, 265.25] that SD = 0.21 implies. Every run reports feasible_ignoring_bounds: false, population_feasible_ignoring_bounds: false -- so the verdict does not depend on the 1-7 range at all, nor on which SD convention is used. sprite_reconstruct returns outcome `no_solution_proven`: "No integer sample can produce this mean/SD pair." R's rsprite2 independently refuses the same parameters with "The standard deviation is not consistent with this mean and number of observations (fails GRIMMER test)". Two engines, agreeing.
- **As printed in the paper:** **Experiment 4, No load conditions, control condition** -- “Higher levels of self-evaluations relative to the control condition (M = 4.20, SD = .21) were found” _(found in the paper's text)_
- **Assumptions:** That each participant contributed one whole-number rating, which the paper establishes by stating Experiment 4 used the same single-item attractiveness measure as Experiments 1 and 2, whose numerals are printed. The control group's size is NOT printed and the experiment's own degrees of freedom disagree about it (see the sample-size finding), which is why five candidate values spanning 10 to 75 were tested; all five fail. Scale bounds are not load-bearing. The two commonest innocent explanations are closed by the sweep's own tallies: across the paper's 13 granularity checks, none is rescued by truncation rather than round-half rounding, and none by the population rather than the sample SD.
- **Consequence:** 8 stated claims affected -- This control condition is the baseline for all eight of Experiment 4's reported contrasts, including the four that carry its central claim that cognitive load abolishes self-serving responding. (asserted, not computed)
- **Reproduce:** no runnable command -- the review could not produce one that runs. The finding's own numbers are above; re-derive from those.

### 2. Two Table 2 cells report a standard deviation of .52 that no set of twelve whole-number ratings can produce  [IMPOSSIBLE | confidence: high]

**In plain terms.** Two cells of the third experiment's results table report a spread of .52 among twelve people's whole-number ratings. No set of twelve whole numbers gives that spread alongside the averages printed beside it -- the closest achievable value is .51, in both cells. A second, independent piece of software agrees. This holds whether the rating scale ran 1 to 7 or 1 to 9. The one thing we had to work out for ourselves is that each cell held twelve people, which follows from the stated total of 96 split across eight groups and is supported by all eight averages in that row being achievable at twelve. These two cells are the ones behind one of the experiment's headline comparisons.

- **Location:** Table 2, Self-evaluation row, Positive/Unambiguous Upward and Positive/Unambiguous Downward
- **Reported:** Table 2 prints "6.58 (.52)" and "4.08 (.52)" for the two Positive/Unambiguous self-evaluation cells. Experiment 3's Procedure states participants "rated their own attractiveness (on the seam measures used in Experiments 1 and 2)"; both of those experiments print a single seven-point item.
- **Computed:** GRIMMER returns `impossible` for both cells at n = 12. For 6.58 the only mean-consistent total is 79 and no integer sum-of-squares of matching parity falls in the implied window; for 4.08 the only total is 49, same result. Both runs report feasible_ignoring_bounds: false, and re-running both cells with the range set to 1-9 instead of 1-7 returns `impossible` unchanged -- the scale is not load-bearing. R's rsprite2 refuses both cells with "fails GRIMMER test". Both are near misses: the sweep records .51 as the only attainable SD where .52 is printed, in both cells.
- **As printed in the paper:** **Table 2, Self-evaluation row, Positive/Unambiguous/Upward cell** -- “Participants also rated their own attractiveness (How attractive are you?) on a seven-point scale (1 = not at all, 7 = extremely).” _(found in the paper's text)_
- **Assumptions:** The cell size of 12 is DERIVED, not printed: Experiment 3 states "University students (N = 96)" in a fully crossed 2 x 2 x 2 design, and its ANOVA error df of 88 plus 8 cells returns 96. The derivation is corroborated -- all eight Table 2 self-evaluation means pass GRIM at n = 12, which a wrong denominator would not generally produce, and the planned comparisons carry df of 94. If the cells were in fact unequal this finding does not stand, and that is the single assumption a reader must accept. That both cells miss by one hundredth invites a rounding convention we have not reproduced, but the sweep's tally records no cell in this paper rescued by truncation, and it would have to be the same unreproduced convention twice.
- **Consequence:** 1 stated claim affected -- These are the two cells of the Positive/Unambiguous contrast reported as F(1, 94) = 92.47, p < .001, the result establishing that unambiguous similarity information produces symmetric assimilation. (asserted, not computed)
- **Reproduce:** no runnable command -- the review could not produce one that runs. The finding's own numbers are above; re-derive from those.

### 3. Experiment 3 reports a mean rating of 7.33 on an instrument it states was the seven-point scale of Experiments 1 and 2  [HIGHLY SUSPICIOUS | confidence: medium]

**In plain terms.** The third experiment says it measured attractiveness using the same seven-point scale as the earlier experiments, then reports an average rating of 7.33 -- higher than the scale's maximum. One of those two statements must be wrong. It may simply be that this experiment actually used a nine-point scale and the methods section describes it incorrectly, which is plausible because the same experiment's other questions are on nine-point scales and the sentence in question contains a spelling error. We cannot tell which, so we report the contradiction rather than calling the number impossible.

- **Location:** Experiment 3, Procedure and Manipulation check
- **Reported:** Procedure: "Participants reported their major, gender, age, and then rated their own attractiveness (on the seam measures used in Experiments 1 and 2). Then, participants rated the target on her attractiveness." Manipulation check: "the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001." Experiment 1 prints "a seven-point scale (1 = not at all, 7 = extremely)" and "the same 7-point scale"; Experiment 2 prints "seven-point scales (1 = not at all attractive and 7 = extremely attractive)".
- **Computed:** grim_check returns `impossible` with failure_mode `out_of_range`: at n = 48 the mean implies a total of 352 against a maximum attainable total of 336 on a 1-7 scale. The mean is above the ceiling irrespective of n. R's scrutiny returns `consistent`, and the two engines do not conflict -- scrutiny tests granularity only, which our own run also passes; the impossibility is the range violation, which scrutiny does not test. recalc_anova separately confirms the printed F is exactly what these two means and SDs imply (calculated F = 169.24, achievable interval [166.76, 171.75] against a reported 170.34), so the arithmetic is internally coherent and the conflict is with the instrument.
- **As printed in the paper:** **Experiment 3, Manipulation check, target attractiveness** -- “the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001.” _(found in the paper's text)_
- **Assumptions:** The seven-point range is imported into Experiment 3 by the paper's own cross-reference rather than printed in Experiment 3 itself, and the sentence carrying that cross-reference contains a typo ("seam" for "same"). The innocent explanation is live and the paper does not close it: Experiment 3 may have run on nine-point instruments -- its own similarity items are printed as nine-point, as are the pilot's -- in which case the value is fine and the Procedure misdescribes the measure. Experiment 3's mood mean in the same paragraph is also 7.33, on a mood measure whose range the paper never states at all. Severity is set below `impossible` for exactly this reason: the contradiction between the two passages is certain, but which of them is wrong is not.
- **Consequence:** changes no significance decision; 1 stated claim affected -- Experiment 3's direction-of-comparison manipulation check rests on a mean that the instrument the paper names cannot produce; either that check is wrong or the Methods misdescribe the measure. (asserted, not computed)
- **Reproduce:** no runnable command -- the review could not produce one that runs. The finding's own numbers are above; re-derive from those.

### 4. Experiment 4 states 193 participants but its degrees of freedom account for roughly 133, with no exclusions reported  [SUSPICIOUS | confidence: high]

**In plain terms.** The fourth experiment says 193 people took part, but the statistics reported for it are calculated as though about 133 people were analysed -- roughly 60 short. No exclusions are described anywhere, and the one obvious reason for excluding people is explicitly ruled out: the paper says every participant successfully recalled the memory-load number. The same arithmetic, applied to the paper's other four studies, matches their stated totals exactly, so this is not a quirk of how we counted. A typing error in the printed total would explain it entirely.

- **Location:** Experiment 4, Participants and design vs Results and discussion
- **Reported:** "University (N = 193, 103 female) students participated in the study for monetary compensation." The contrasts throughout are reported on F(1, 124) over nine groups; the factorial is reported on F(1, 110) over eight cells.
- **Computed:** check_summation_batch, applying the paper's own reconciliation rule (error df plus number of groups equals analysed N) to all five studies: the pilot (42 + 3 = 45), Experiment 1 (43 + 4 = 47), Experiment 2 (132 + 9 = 141) and Experiment 3 (88 + 8 = 96) all land exactly on their stated totals. Experiment 4 gives 124 + 9 = 133 against a stated 193, a shortfall of 60. Its internal figures are mutually coherent -- 110 + 8 = 118 in the factorial, plus a control of 15, is 133 -- so the stated N is the sole outlier.
- **As printed in the paper:** **Participants sections and Results of Pilot and Experiments 1-4** -- “University (N = 193, 103 female) students participated in the study for monetary compensation.” _(found in the paper's text)_
- **Assumptions:** That the error df of a single-degree-of-freedom contrast over nine groups is N minus 9. This is not an assumption imposed from outside: it is validated on four other studies in the same paper, where it reproduces each stated total exactly. A typo in the printed N (193 for 133) would account for the whole gap and is the least dramatic reading.
- **Consequence:** 12 stated claims affected -- Every test reported in Experiment 4 runs on degrees of freedom implying about 133 analysed participants, so on the stated recruitment roughly 60 people are silently absent from every analysis. (asserted, not computed)
- **Reproduce:** `metascience summation-batch --rows '[{"values":[124,9],"expected_sum":193,"decimals":[0,0],"tolerance":0,"description":"Exp 4 contrast error df plus 9 groups vs stated N"},{"values":[132,9],"expected_sum":141,"decimals":[0,0],"tolerance":0,"description":"Exp 2 same arithmetic"},{"values":[88,8],"expected_sum":96,"decimals":[0,0],"tolerance":0,"description":"Exp 3 same arithmetic"}]'`

### 5. The two means in Experiment 4's central conclusion run opposite to the labels attached to them  [SUSPICIOUS | confidence: high]

**In plain terms.** The sentence carrying the fourth experiment's main conclusion describes one group as having rated themselves more positively than the comparison group and another as less positively -- but the numbers printed alongside those words say the reverse. The most likely explanation is that the two figures were swapped when the sentence was written, which is a proofreading failure rather than a data problem. As printed, though, the sentence does not support the claim it makes.

- **Location:** Experiment 4, Cognitive load conditions, final sentence
- **Reported:** "This pattern was identical to the neutral mood condition, in which upward comparison led to more positive self-ratings (M = 3.33, SD = 1.05), F(1,124) = 18.83, p < .001, and downward comparison led to less positive self-ratings (M = 5.53, SD = .87), F(1,124) = 7.84, p = .006, relative to the control condition." The control mean given two sentences earlier is 4.20.
- **Computed:** Ordering each printed mean against the control mean printed in the same passage: the mean labelled "more positive" (3.33) is below the control (4.20) and the mean labelled "less positive" (5.53) is above it. The other three pairs in the same two paragraphs run the correct way -- positive mood under load gives 5.71 above and 3.09 below; no-load neutral gives 5.47 above and 3.24 below. Verified verbatim in the XML full text.
- **As printed in the paper:** “This pattern was identical to the neutral mood condition, in which upward comparison led to more positive self-ratings (M = 3.33, SD = 1.05), F(1,124) = 18.83, p < .001, and downward comparison led to less positive self-ratings (M = 5.53, SD = .87), F(1,124) = 7.84, p = .006, relative to the control condition.” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own printed values. The F statistics do not disambiguate which mean belongs to which condition. Figure 3 plots these means and would settle whether this is a writing error or a data error; the figure was not read.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The sentence asserts that positive mood under load becomes indistinguishable from neutral mood, which is Experiment 4's central claim, but as printed the neutral-mood means it cites run the opposite way to the description. (asserted, not computed)
- **Reproduce:** `No command applies: this is a reading of the paper's prose against its own printed means, not a calculation.`

### 6. Experiment 3's headline contrasts imply standardised effects near five standard deviations on single-item rating scales  [SUSPICIOUS | confidence: medium]

**In plain terms.** The differences between groups in the third experiment are enormous by the standards of this kind of research: the two groups barely overlap at all. Effects that large from twelve people per group are the pattern you see when results have been selected or when something has gone wrong upstream, though they are not impossible on their own. One caveat cuts the other way: neither table explains what the numbers in brackets are, and if they are a different measure of variability than we assumed, these effects would be considerably smaller. This is a judgement we are supplying, not a standard the paper set for itself.

- **Location:** Table 2, Self-evaluation and Similarity rows, positive mood columns
- **Reported:** Table 2 gives Positive/Unambiguous self-evaluations of 6.58 (.52) upward versus 4.08 (.52) downward, and Positive/Ambiguous similarity of 7.06 (.53) upward versus 4.14 (.59) downward, at twelve per cell. The paper prints no effect size of its own.
- **Computed:** check_effect_plausibility gives Hedges' g = 4.64, 95% CI [3.23, 6.39] for the self-evaluation contrast and g = 5.03, 95% CI [3.53, 6.88] for the similarity contrast. The tool reports the magnitude and declines to judge it: "|d| = 4.64 is remarkable in any field." Separately, required_n shows a two-group comparison would need 26 per group to detect d = 0.8 at 80% power, against the 12 per group available here.
- **As printed in the paper:** **Table 2, Self-evaluation row, Positive/Unambiguous columns** -- “However, when the cue was unambiguous, participants assimilated to the comparison targets, as expected, F(1, 94) = 92.47, p < .001.” _(found in the paper's text)_
- **Our check returned a different severity.** The `check_effect_plausibility` check returned `consistent` for the sweep finding `e3_effect_sizes_extreme`, which this review recorded as `suspicious`. This entry asserts more than the check established, so read it as this review's judgement and not as a computed result. The finding states a reason.
- **Assumptions:** This escalation above the tool's own `consistent` verdict is a reviewer-supplied judgement under rulebook rule 6, not a determination by the tool; the comparison class -- that standardised effects near g = 5 are far outside what social-psychological rating measures ordinarily yield -- is mine, and the paper never accepted it. Of the three ordinary causes, a units mismatch is ruled out (both rows are the paper's own rating scales) and a waitlist comparator does not apply (these are randomised between-subjects cells), but dispersion reported as standard error rather than standard deviation cannot be fully ruled out: neither table carries a footnote defining the parenthetical value, and the reading as SD comes from the prose, which writes "M = x, SD = y" for the same quantities. If those parentheses were standard errors, these effect sizes are inflated.
- **Consequence:** changes no significance decision; 2 stated claims affected -- The two contrasts the paper leans on in Experiment 3 imply differences of roughly five standard deviations, which is the combination -- very large observed effects from twelve people per cell -- in which estimates are most inflated. (asserted, not computed)
- **Reproduce:** no runnable command -- the review could not produce one that runs. The finding's own numbers are above; re-derive from those.

### 7. The pilot's self-evaluation ANOVA is reported with one numerator degree of freedom for a three-group comparison  [SUSPICIOUS | confidence: high]

**In plain terms.** In the pilot study, a comparison across three groups is reported using a figure that only fits a two-group comparison, while the sentence just above it reports the correct figure for three groups. The conclusion is unaffected -- the groups did not differ either way -- but the notation is wrong.

- **Location:** Pilot study, second results paragraph
- **Reported:** "Those in the negative mood (M = 6.98, SD = .53), positive mood (M = 6.98, SD = .80), and the control condition (M = 6.82, SD = .67), did not differ F(1, 42) = .27, p = .76."
- **Computed:** The same paragraph reports the mood ANOVA over the same three groups as F(2, 42), so the numerator degrees of freedom for a three-group one-way comparison is 2 and the printed 1 is a misprint. recalc_f_to_p run at both readings settles which number is wrong: the printed p of .76 falls inside the achievable interval [0.761, 0.768] at df1 = 2, and does not reconcile at df1 = 1, which implies p = .606.
- **As printed in the paper:** “Those in the negative mood (M = 6.98, SD = .53), positive mood (M = 6.98, SD = .80), and the control condition (M = 6.82, SD = .67), did not differ F(1, 42) = .27, p = .76.” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own printed text. The finding rests on the contradiction between two sentences in the same paragraph, with the two recomputations as supporting evidence; recalc_f_to_p itself returns `consistent` on the printed pairing because it is directional and treats an over-large p as conservative reporting.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The claim is a null one -- that mood alone did not move self-evaluations -- and it holds under either reading, so the error is in the notation rather than the conclusion. (asserted, not computed)
- **Reproduce:** `metascience f-to-p --f-value 0.27 --df1 2 --df2 42 --reported-p 0.76 --decimals-f 2 --decimals-p 2`

### 8. The pilot's mood ANOVA reports F = 18.44 where its own printed means and SDs imply about 26.5  [SUSPICIOUS | confidence: medium]

**In plain terms.** In the pilot study, the test statistic reported for the mood manipulation is smaller than the group averages printed beside it can produce -- about 18 where roughly 26 is implied. This works against the authors rather than for them, since the larger value would be a stronger result. The comparison depends on our assuming the 45 participants split evenly into three groups of 15, which the paper does not state, so it is a question rather than a determination.

- **Location:** Pilot study, mood manipulation check
- **Reported:** "A one-way Analysis of Variance (ANOVA) revealed that the mood manipulation significantly affected participant mood, F(2, 42) = 18.44, p < .001," alongside group means of 7.20 (SD .93), 6.15 (SD .52) and 4.98 (SD .98).
- **Computed:** rivets_anova, run at three equal groups of 15, gives an achievable F interval of [26.01, 27.04] across the rounding box of the printed inputs, with a point value of 26.48. The reported 18.44 lies outside that interval. The tool returned `highly_suspicious`; it is recorded a rung lower here.
- **As printed in the paper:** **Pilot study, mood manipulation check** -- “Participants in the positive mood condition reported more positive mood (M = 7.20, SD = .93) that those in the control condition (M = 6.15, SD = .52), t(42) = 3.43, p = .001. Participants in the negative mood condition reported more negative mood (M = 4.98, SD = .98) than those in the control condition, t(42) = -3.80, p < .001.” _(found in the paper's text)_
- **Assumptions:** The group sizes are OUR inference, not the paper's. The pilot states only "N = 45" across three conditions and never prints cell sizes; the equal split of 15/15/15 follows from 45 dividing by three and from the error df of 42 confirming three groups totalling 45, but unequal cells would change the achievable interval and could reconcile the reported value. Rulebook rule 4 caps an assumption-dependent finding at `suspicious`, which is why the tool's own verdict is not carried through, and why this cannot be the paper's headline problem.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The reported statistic is smaller than the printed means and SDs support, so the mood manipulation check is if anything understated and the manipulation is significant on either value. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command used an option this tool does not have. The finding's own numbers are above; re-derive from those.

### 9. Table 1's caption names three dependent measures; the table reports one and Experiment 2 analyses only that one  [SUSPICIOUS | confidence: high]

**In plain terms.** The heading above the second experiment's results table promises three sets of measurements; the table contains one, and the experiment's text never analyses the other two. The methods section for that experiment also never describes collecting them. Most likely the heading was copied from the other table in the paper, which does contain one of the missing measures. The less comfortable possibility is that measurements were taken and not reported.

- **Location:** Table 1 caption vs Table 1 body and Experiment 2, Dependent measures
- **Reported:** Caption: "Effects of upward (more attractive) versus downward (less attractive) comparisons on self-evaluations, ratings of target similarity, and use of information to benefit the self as a function of mood and shared birthday information." The table body carries a single row, labelled Self-evaluation.
- **Computed:** Both the XML grid and the PDF grid return exactly one body row for Table 1, so this is not an extraction failure. Experiment 2's Dependent measures section describes only attractiveness ratings of self and target plus a single mood item -- no similarity index and no 'use of information' measure -- and the Results section analyses neither of the two additional measures the caption names.
- **As printed in the paper:** “Effects of upward (more attractive) versus downward (less attractive) comparisons on self-evaluations, ratings of target similarity, and use of information to benefit the self as a function of mood and shared birthday information” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own text. The likeliest explanation is that the caption was copied from Table 2, which does carry a Similarity row, or from a template. The alternative and more consequential reading is that measures were collected and not reported.
- **Consequence:** changes no significance decision; 2 stated claims affected -- Two dependent measures the caption says the table reports appear nowhere in it, and Experiment 2's Results analyse neither, so two measures named as reported are absent. (asserted, not computed)
- **Reproduce:** `metascience get-table --xml-path <home>/agent_for_forensic_metascience/eval/ground_truth/papers/10.1007--s11031-011-9216-y/10.1007--s11031-011-9216-y.xml --table-num 1`

### 10. Malformed test statistics in results-carrying sentences: two p-values printed with no decimal point and a degrees-of-freedom value matching no group structure  [SUSPICIOUS | confidence: high]

**In plain terms.** Two of the paper's significance values are printed without their decimal points, so as they stand they are not percentages or probabilities at all; one of them belongs to the fourth experiment's main result. In the first experiment, a comparison is also reported using a sample-size figure that does not match any grouping the experiment describes. These are almost certainly typesetting or typing errors rather than data problems, but they mean the reader cannot check those two results as published.

- **Location:** Experiment 1, Self-evaluations; Experiment 4, Self-evaluations and Manipulation check
- **Reported:** Experiment 1: "Exposure to the upward comparison target led to lowered self-evaluations (M = 3.33, SD = .65) compared to the downward comparison target (M = 4.64, SD = 1.50), F(1, 46) = 6.95, p = 011." Experiment 4: "Analysis revealed the expected three-way interaction effect of load, mood, and direction of comparison on attractiveness, F(1, 110) = 11.23, p = 001." Experiment 4 manipulation check: "the attractive comparison target was rated more attractive than the (M = 5.58, SD = .78) than the unattractive target (M = 2.99, SD = .89)".
- **Computed:** As printed, "p = 011" and "p = 001" are not p-values; no recomputation against them is possible, so both statistics are unverifiable as published. The error df of 46 in Experiment 1 corresponds to no group structure the experiment describes: the 2 x 2 ANOVA reported two sentences earlier uses F(1, 43), where 43 is 47 minus 4 cells, and a two-group comparison of 47 participants would give 45. All three passages are present identically in the XML full text.
- **As printed in the paper:** **Whole article, Results sections of Pilot and Experiments 1-4** -- “A one-way Analysis of Variance (ANOVA) revealed that the mood manipulation significantly affected participant mood, F(2, 42) = 18.44, p < .001.” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own printed text. "p = 011" is almost certainly ".011", which is what F(1, 43) = 6.95 would give, and "p = 001" almost certainly ".001"; on those readings only the notation is wrong. Grouped as one finding because all three sit in results-carrying sentences and evidence the same thing -- that the Results were not closely proofread.
- **Consequence:** changes no significance decision -- Two of the paper's reported effects -- Experiment 1's symmetric-contrast simple effect and Experiment 4's three-way interaction, which is that experiment's primary result -- are reported with p-values that are not p-values as printed. Zero decision errors: no reported p crosses .05 in the wrong direction, so no significance claim in the paper changes on recomputation. Computed from 0 statistic(s) whose recomputed p crosses the paper's alpha. (computed)
- **Reproduce:** `metascience f-to-p --f-value 6.95 --df1 1 --df2 43 --reported-p 0.011 --decimals-f 2 --decimals-p 3`

### 11. A reported p of .83 where the printed F statistic implies .22  [SUSPICIOUS | confidence: high]

**In plain terms.** One reported result gives a significance value of .83 where the test statistic printed beside it implies about .22. The conclusion drawn from it -- that there was no difference -- is the same either way, so nothing in the paper's argument turns on it, but one of the two numbers is wrong.

- **Location:** Experiment 3, Perceptions of similarity, final sentence
- **Reported:** "Identical effects emerged when the information was unambiguous, F(1, 94) = 1.50, p = .83."
- **Computed:** recalc_f_to_p gives p = 0.2237 for F(1, 94) = 1.50, with an achievable interval of [0.2230, 0.2245] given the printed precision -- far outside any rounding window around .83. statcheck flags the same pair as an inconsistency. The two tools formally disagree: recalc_f_to_p returns `consistent` because it is deliberately directional and flags only p-values SMALLER than the statistic supports, treating a larger one as conservative reporting. The severity here rests on statcheck's flag together with the size of the gap, not on overriding the directional tool.
- **As printed in the paper:** **Whole article, Results sections of Pilot and Experiments 1-4** -- “A one-way Analysis of Variance (ANOVA) revealed that the mood manipulation significantly affected participant mood, F(2, 42) = 18.44, p < .001.” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's printed values. An adjustment for multiple comparisons would raise a p-value, but the paper reports no correction for Experiment 3; a typo in the printed .83 is the likelier explanation. The sentence describes this effect as "identical" to the F(1, 94) = .31, p = .58 result immediately preceding it, which recomputes exactly.
- **Consequence:** changes no significance decision -- Both the reported and the recomputed value are far above the .05 threshold, so the 'no difference' conclusion the sentence draws is unaffected and only the printed number is wrong. Zero decision errors: no reported p crosses .05 in the wrong direction, so no significance claim in the paper changes on recomputation. Computed from 0 statistic(s) whose recomputed p crosses the paper's alpha. (computed)
- **Reproduce:** `metascience f-to-p --f-value 1.50 --df1 1 --df2 94 --reported-p 0.83 --decimals-f 2 --decimals-p 2`

### 12. The paper's only route to its underlying data is a footnote directing readers to one author  [INDETERMINATE | confidence: high]

**In plain terms.** The paper says its data can be obtained by writing to the first author. That was normal practice for a psychology paper in 2011 and is not a criticism. It matters only because the arithmetic problems described above could be settled immediately by the raw ratings, and no copy of those ratings was deposited anywhere.

- **Location:** Experiment 3, footnote 4
- **Reported:** "Complete data and results available from the first author."
- **Computed:** The paper deposits nothing: no repository, no accession number, no supplementary file, and none accompanies the article. This is the paper's sole data provision.
- **As printed in the paper:** “4 Complete data and results available from the first author.” _(found in the PDF text layer)_
- **Assumptions:** A 'data available on request' footnote was entirely conventional for a 2011 psychology article and is not, in that era, a departure from any standard the paper or its field then imposed; it is graded `indeterminate` for that reason and should not be read as a criticism of the authors' practice at the time. It is recorded because it is the only route by which the arithmetic anomalies above could be settled, and because the article has since been retracted, which makes that route uncertain.
- **Consequence:** changes no significance decision -- None of the granularity anomalies in this report can be resolved without the underlying data, and the paper provides no route to it independent of an author's cooperation. (asserted, not computed)
- **Reproduce:** `No command applies: this is a reading of the paper's reporting practice, not a calculation.`

## What we could NOT check

- **Table 1 (Experiment 2), all 8 self-evaluation cells** — No cell size is printed and none can be derived: the factorial holds 126 participants (error df 118 plus 8 cells) across 8 cells, and 126 does not divide by 8, so the cells are provably unequal. check_table refused all 24 candidate checks for want of a denominator. Guessing one here is the standard route to a false accusation, so Experiment 2's entire results table is outside the reach of this analysis and nothing in this report clears it.
- **Table 2 (Experiment 3), all 8 Similarity cells** — The similarity index is the mean of three nine-point items, so its granularity is one thirty-sixth rather than one twelfth. Our GRIM, GRIMMER and SPRITE implementations take no items parameter, so checking these at the wrong step size would manufacture impossibilities; the dispatcher correctly refused all 8. An implementation taking an items argument, such as R's scrutiny, could check them.
- **Pilot study, mood index and self-evaluation index means** — Both are means of multiple nine-point items (four and three respectively), so the same items-granularity limit applies. Cell sizes are also unstated.
- **Experiment 3, Manipulation check, self-reported mood (M = 7.33, SD = .86; M = 5.44, SD = .97)** — Experiment 3 never states the range of its mood measure. Experiment 2 used a 1-7 mood item and the pilot a 1-9 index; neither is stated to apply here. Without stated bounds no range check may run, and inventing one would invert the check rather than weaken it. Note that this mean is the same value, 7.33, as the checkable and out-of-range target-attractiveness mean in the same paragraph.
- **Experiment 2 and Experiment 4, all cell means reported in prose** — No cell sizes are printed for either experiment, and in Experiment 4 the stated N contradicts the degrees of freedom, so no denominator can be trusted even approximately. Granularity checks were not attempted on these.
- **Figures 1, 2 and 3** — Values plotted in the figures were not read; this agent reads text and does not see figures. No caption defines what any error bar represents, so no dispersion could be recovered even if the marks were measured. Figures 2 and 3 appear to plot means also printed in Table 2 and Experiment 4's prose, so this is not believed to be a coverage hole, but Figure 3 is the one artefact that would settle whether Experiment 4's transposed means are a writing error or a data error.
- **Table 1 footnote giving Experiment 2's control condition (M = 4.20, SD = .86)** — This value is absent from the XML, which returns zero footnotes for Table 1, and the sweep recovered it from the PDF only. It was NOT re-verified at source in this pass, so nothing in this report rests on it; it is noted only because Experiment 2's control mean of 4.20 coincides with Experiment 4's, whose SD is the impossible one.
- **Reported Cronbach's alpha values (.91, .71, .87)** — Reliability coefficients cannot be verified without the item-level covariance matrix, which the paper does not print. No registered tool applies.
- **Results reported as 'Fs < 1', 'p > .05', 'ps > .84' and 'p > .9'** — These are bounds with no statistic attached. statcheck cannot parse them and no recomputation is possible; they are counted in neither statcheck's denominator of 22 nor any multiplicity family, so both understate the number of comparisons actually made.
- **Experiment 2 and Experiment 4 Tukey HSD re-analyses (footnotes 2 and 5)** — The footnotes report only which single contrast changed status and at what value (.07 and .13 respectively), with no test statistics or group sizes. Nothing can be recomputed, though their existence is why no multiplicity finding was raised against those two experiments.
- **Supplementary materials** — The paper directory contains no supplementary files and the article provides none; its only data provision is a footnote directing readers to the first author. Recorded as not provided, rather than present-but-unreadable.
- **table rows Similarity, Similarity, Similarity, Similarity, Similarity, Similarity and 2 more** — grim_check, grimmer_check, sprite_reconstruct not run: multi-item composite whose scoring is undeclared. If the score is a MEAN of items its granularity is 1/(items*n) and grim_test has no `items` parameter, so checking at 1/n would manufacture an impossibility; if it is a SUM the granularity is 1/n and the check is valid. Declare `derivation` as 'mean_of_items' or 'sum_of_items' to resolve this -- the field is already in the schema and the prompt asks for it.
- **table rows Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation and 2 more** — grim_check not run: grim_check needs n and this cell carries none; supply n for this row (the participants paragraph or the table footnote usually states it)
- **table rows Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation and 2 more** — grimmer_check not run: grimmer_check needs n and this cell carries none; supply n for this row (the participants paragraph or the table footnote usually states it)
- **table rows Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation, Self-evaluation and 2 more** — sprite_reconstruct not run: sprite_reconstruct needs n and this cell carries none; supply n for this row (the participants paragraph or the table footnote usually states it)

## Questions for the authors

_Each of these is answerable from what the authors already have. None presupposes an error on their part: an inconsistency is far more often a reporting slip, or a mistake by this tool in reading the number off the page, than anything else._

1. Experiment 4's no-mood, no-comparison control condition is reported twice as M = 4.20, SD = .21. Could you supply the number of participants in that condition and their individual self-evaluation ratings? We could not find a set of whole-number ratings on the 1-7 scale that produces this mean and standard deviation together at any group size we tested (10, 15, 20, 25 and 75), under either the n-1 or the n formula for the standard deviation.
   <sub>Would resolve: Settles the headline finding directly; the raw ratings would either reproduce the pair or identify a transcription error.</sub>
2. Experiment 4 reports N = 193, but the contrasts throughout are reported on F(1, 124) across nine groups and the factorial on F(1, 110) across eight cells, which together account for about 133 participants. The same arithmetic reproduces the stated totals exactly for the pilot and for Experiments 1, 2 and 3. Could you tell us how many participants entered the analyses, and whether any were excluded?
   <sub>Would resolve: Resolves whether roughly 60 participants were excluded without report, or whether the printed N is a typographical error.</sub>
3. Experiment 3's Procedure states that own and target attractiveness were rated 'on the seam measures used in Experiments 1 and 2', which are printed as seven-point scales, but the manipulation check reports a mean target rating of M = 7.33, SD = 1.19. Could you confirm which scale range Experiment 3 actually used for the attractiveness items and for its mood item?
   <sub>Would resolve: Determines whether the reported mean is off-scale or whether the Methods sentence misdescribes the instrument; also decides how Table 2's self-evaluation cells should be read.</sub>
4. Table 2's Positive/Unambiguous self-evaluation cells read 6.58 (.52) and 4.08 (.52). Could you confirm the number of participants in each of the eight cells of Experiment 3, and state whether the values in parentheses in Tables 1 and 2 are standard deviations or standard errors? Neither table carries a footnote defining them.
   <sub>Would resolve: The cell size of 12 is our derivation from N = 96, and the SD-versus-SE reading is taken from the prose; both are load-bearing for findings in this report.</sub>
5. In Experiment 4's cognitive load section, the neutral mood condition is described as showing 'upward comparison led to more positive self-ratings (M = 3.33, SD = 1.05)' and 'downward comparison led to less positive self-ratings (M = 5.53, SD = .87)' relative to a control of M = 4.20. Could you confirm which mean belongs to which condition?
   <sub>Would resolve: As printed the two means run opposite to their labels; this sentence carries Experiment 4's central claim, and Figure 3 would resolve it but was not read here.</sub>

## Limitations

- This agent reads text and does not see figures. No figure pass was run on this paper: Figures 1, 2 and 3 were not extracted or read, and no value was taken from any plot. Figure 3 is the one artefact that would settle whether Experiment 4's transposed means are a writing error or a data error, and it remains unread.
- The `second_look` worklist flagged all 15 of the sweep's accusations with `quote_not_located`. That marker fired on 15 of 15 -- a fact about the instrument, not about the findings. On re-reading the full XML text in this pass, every quoted span carried into this report was located verbatim, with one exception recorded in `not_checked`: the Table 1 footnote giving Experiment 2's control condition, which is absent from the XML and which nothing in this report rests on. The marker class is settled globally and no finding was dropped on account of it.
- The two `impossible` findings were both cross-checked in R. R's rsprite2 refuses all three flagged mean/SD pairs with the message 'fails GRIMMER test', which is agreement between the two GRIMMER implementations; our wrapper records that refusal as `indeterminate` for SPRITE purposes because an exception raised is not a proof, so the severity rests on our own GRIMMER with R as corroboration. For the Experiment 3 off-scale mean, R's scrutiny returns `consistent` -- this is NOT a disagreement, because scrutiny tests granularity only, which our own run also passes; the impossibility there is a range violation scrutiny does not test.
- Experiment 4's control group size is never printed, so the headline finding was tested at five candidate values (10, 15, 20, 25, 75) rather than at the true one. All five fail, under both SD conventions and with the scale bounds removed, but no run tested the actual denominator because the paper does not supply it.
- The Table 2 finding depends on a cell size of 12 that we derived from the stated total of 96 and a fully crossed eight-cell design. It is corroborated -- all eight means in that row are attainable at twelve -- but it is a derivation, and if the cells were unequal the finding does not stand.
- Neither table carries a footnote defining what the parenthetical value is. The reading as a standard deviation comes from the paper's prose, which writes 'M = x, SD = y' for the same quantities. If those parentheses were standard errors, the effect-size finding would be materially weaker; the granularity findings would be unaffected, since they are stated in the prose as SDs.
- This system reads one paper and reaches no network. Two questions a reader needs in order to weigh these findings are outside its reach entirely: whether similar anomalies appear in other papers by the same authors, and how the reported effect sizes compare with calculated values from other studies in this literature. The interpretation here is therefore partly ours and partly the reader's.
- The article is marked RETRACTED on every page of the record. This analysis is an arithmetic check of the document as published and takes no position on the retraction, its grounds, or the responsibility of either author.
- No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.

## Coverage

- **Statistics found:** 46; **checked:** 42
- **Tools run:** extract_xml, get_table, extract_pdf, parse_cells_typed, check_table, statcheck, grim_check, grimmer_check, sprite_reconstruct, r_sprite_ground_truth, r_grim_ground_truth, recalc_f_to_p, recalc_anova, rivets_anova, check_summation_batch, detect_duplication, multiplicity_report, check_effect_plausibility, required_n
- **Tables checked:** Table 1 (Experiment 2) - XML grid and PDF grid; all 8 cells refused for want of a derivable n, Table 2 (Experiment 3) - XML grid and PDF grid; 24 checks run over the 8 self-evaluation cells, 20 consistent, 4 flagged; 8 similarity cells refused as a multi-item composite
- **Checkable table cells:** 24 of 24 surveyed; **checked:** 8
    - 24 could not be checked without knowing what kind of quantity the row reports
- **Every checkable item:** 157 registered; 24 refused with a stated reason; **133 outstanding**
    - how many were CHECKED is not measured -- no persisted item identity joins a tool call back to a manifest row, so how many items were CHECKED cannot be counted. This is not a count of zero. This is not a count of zero.
- **Stage-1 findings:** 22 raised; 17 carried into this report; 5 not carried
- **Where a check and this review disagreed:** 4 sweep findings recorded a severity the validated check behind them did not return (1 upgraded, 3 downgraded). 1 is marked on the entry above that cites it. 1 is an explained downgrade on an entry above, counted here and not marked there: the check said more, this review said less and said why, which is what stage 2 is for. 2 sit on sweep findings no entry in this report cites, so this line is the only place they appear.
- **Traceable to the page:** 43 of 43 checks recorded the passage their numbers were read from; 43 of those were located in the paper's own text.

## What each check does

One entry per check that ran on this paper. The **assumptions** are the conditions under which its verdict holds; where one is unmet the verdict is capped, not merely caveated.

### `check_effect_plausibility` — probabilistic

Places an effect size against cited field benchmarks; flags unusual, never impossible.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- Benchmarks carry a provenance label. Only social_psychology's percentiles trace to a published table (Lovakov & Agadullina 2021, Table 1); the rest are uncited estimates and say so in the result. psychology_general was WITHDRAWN 2026-08-16 -- its median came from an OSC 2015 correlation (r = .40) used as a Cohen's d, which is d ~ 0.87, so it flagged ordinary effects as large; naming it now returns a diagnosis rather than a comparison.
- Field benchmarks are distributions of PUBLISHED effects, themselves inflated by publication bias.
- Dispersion inputs must be SDs; an SEM read as an SD inflates d by sqrt(n).
- d from group statistics assumes independent groups and pooled-SD standardisation.
- An effect can be improbable but never impossible, so this caps at `suspicious`.

### `check_summation_batch` — probabilistic

Runs every summation check in one call; the worst row sets the verdict.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- Same premises as check_summation per row.
- Give `decimals` per row; a row with no printed precision is refused rather than guessed.
- An all-unevaluated batch is indeterminate, never `consistent`.

### `check_table` — absolute

Runs every applicable check on a typed table in one call; the worst row wins.

**What its verdict means.** Absolute (possible vs impossible). Exact arithmetic over the printed values and their rounding intervals. Subject to the preconditions below, a flagged result cannot be produced by any dataset.

**Strongest verdict it may reach:** `impossible`

**It assumes:**
- A ROUTER, so the `absolute` class above describes only its CEILING, not every row it returns. `impossible` can still only come from a bound-free arithmetic check; but a `highly_suspicious` or `suspicious` row may have come from a probabilistic one (a Wald-CI judgement, a dispersion plausibility). Read the per-row `tool` and look up ITS card -- the routed check's evidence class governs, not this one.
- Variables must be truthfully declared -- data_type, bounds and bound_source gate every downstream check.
- Declare provenance for figure-read values; the exact-arithmetic checks then refuse them rather than judge them.

### `detect_duplication` — probabilistic

Finds identical (mean, SD) pairs recurring across supposedly independent samples.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- Blocks are assumed to describe INDEPENDENT samples unless they share a sample_id; confirm editorially before accusing.
- The chance model is Poisson over all comparisons, with spans inferred from the observed values.
- Round values collide by chance far more often and are discounted.
- Capped at `highly_suspicious`: duplication is improbable, never impossible.

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

### `grim_check` — absolute

Tests whether a mean of integer data is reachable at all for its n and printed precision.

**What its verdict means.** Absolute (possible vs impossible). Exact arithmetic over the printed values and their rounding intervals. Subject to the preconditions below, a flagged result cannot be produced by any dataset.

**Strongest verdict it may reach:** `impossible`

**It assumes:**
- Observations must be integer-valued; continuous data is refused rather than judged.
- `decimals` must be the precision AS PRINTED -- '5.9' is 1, not 2; a wrong value accuses, so a missing one is refused.
- Both the round-half and truncation reporting conventions are tried; a truncation-only pass caps at `suspicious`.
- Range failures on ASSUMED bounds cap at `suspicious`; only stated bounds license `impossible`.
- GRANULARITY failures cap at `suspicious` unless `discreteness_source` is `stated` or `logically_necessary`: the arithmetic is airtight only if each subject contributed a whole number, and `data_type` merely asserts that.
- The mean and n must be printed values; figure-read inputs are refused.

### `grimmer_check` — absolute

Tests whether an SD is reachable for integer data with the reported mean and n.

**What its verdict means.** Absolute (possible vs impossible). Exact arithmetic over the printed values and their rounding intervals. Subject to the preconditions below, a flagged result cannot be produced by any dataset.

**Strongest verdict it may reach:** `impossible`

**It assumes:**
- Both GRANULARITY modes (mean and SD) cap at `suspicious` unless `discreteness_source` is stated or logically necessary -- they are bound-free, not premise-free.
- Observations must be integer-valued; ordinary continuous values otherwise read as `impossible`.
- Printed precision must be supplied or inferred correctly -- a wrong assumed precision accuses.
- Only integer and parity failures license `impossible`; range-dependent failures on assumed bounds cap at `suspicious`.
- Both the sample and population SD conventions are tried; a population-only match caps at `suspicious`.

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

### `r_grim_ground_truth` — descriptive

Cross-checks our GRIM against R's canonical scrutiny package.

**What its verdict means.** Descriptive. Extracts, parses or computes a quantity; it does not itself render a verdict about the paper.

**Strongest verdict it may reach:** `indeterminate`

**It assumes:**
- Reports R's verdict. A disagreement between engines means OUR tooling is wrong; it is never evidence about the paper.

### `r_sprite_ground_truth` — descriptive

Cross-checks our SPRITE against R's canonical rsprite2 package.

**What its verdict means.** Descriptive. Extracts, parses or computes a quantity; it does not itself render a verdict about the paper.

**Strongest verdict it may reach:** `indeterminate`

**It assumes:**
- Reports rsprite2's result. A disagreement is a bug in our tooling and the finding must not be reported.

### `recalc_anova` — probabilistic

Recomputes a one-way ANOVA F and p from group summaries and compares them to the report.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The reported F and p are assumed to come from a classical fixed-effects one-way ANOVA, not Welch's.
- Homogeneity of variance across groups: MS_within pools the group SDs.
- Independent observations within and between groups.
- Normality of the sampling distribution of the group means.
- Rounding propagates multiplicatively into F, so the reported value is matched against an achievable interval.

### `recalc_f_to_p` — probabilistic

Verifies a reported p against the range its rounded F and df imply.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The reported p is assumed to be the upper-tail F probability at the printed df.
- The printed F is rounded, so it asserts a p RANGE; only a p below that range is flagged.
- The F must come from the test its df describe, whose assumptions are inherited.

### `required_n` — descriptive

Computes the sample size a design needs for a target power; a pure calculator.

**What its verdict means.** Descriptive. Extracts, parses or computes a quantity; it does not itself render a verdict about the paper.

**Strongest verdict it may reach:** `indeterminate`

**It assumes:**
- Uses the standard model for the named test; it renders no verdict about any paper.

### `rivets_anova` — probabilistic

Maps the F and p reachable from rounded inputs, and flags hand-calculation signatures.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The reported F and p are assumed computed from these summaries by a classical one-way ANOVA.
- Monte Carlo draws uniformly over each printed value's truncation interval.
- Printed decimals must be supplied; the defaults assume more precision than most papers report.
- A point match plus a rare hit rate is read as a hand-calculation signature -- the RIVETS premise itself.
- Pass a bound p as the STRING, never the float, or it reads as an unreachable exact value.

### `sprite_reconstruct` — absolute

Searches for integer samples matching a reported mean and SD, and proves when none exists.

**What its verdict means.** Absolute (possible vs impossible). Exact arithmetic over the printed values and their rounding intervals. Subject to the preconditions below, a flagged result cannot be produced by any dataset.

**Strongest verdict it may reach:** `impossible`

**It assumes:**
- `grim_fail` and `no_solution_proven` are bound-free but rest on the observations being integers, so they cap at `suspicious` unless `discreteness_source` is stated or logically necessary.
- Observations must be integers on a bounded scale; continuous measures are refused.
- Printed precision drives which totals are admissible, so a wrong value accuses.
- Only a proven no-solution is evidence; an exhausted search is a failed search, never an anomaly.
- Range-dependent infeasibility rests on the scale bounds and caps at `suspicious` on assumed ones.
- The population-SD convention is tried before accusing.

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

This article reports a pilot study and four between-subjects experiments arguing that positive mood lets people reinterpret ambiguous similarity information in self-serving ways: assimilating to superior comparison targets, contrasting away from inferior ones, and losing the ability to do either under cognitive load. It is marked RETRACTED on every page of the record. This analysis is an arithmetic check of the document as published and takes no position on the retraction or on the responsibility of either author.

Forty-two checks ran. Twenty-four passed, twenty of those collapsed inside a single table dispatch and therefore invisible in the findings list: all eight of Table 2's self-evaluation means are attainable at twelve per cell, six of those eight also survive both dispersion checks, Experiment 3's manipulation-check F recomputes almost exactly from its own printed means, and statcheck's own count of decision errors -- results whose significance verdict changes on recomputation -- is zero across the twenty-two statistics it could parse. That last number deserves saying plainly, because the raw statcheck count of twenty flagged rows badly overstates the problem: eighteen of them are rounding, .008 against a computed .007877 and the like. Multiplicity is also not a problem here. Experiment 3's planned comparisons lose nothing to any of the four standard corrections, and footnotes 2 and 5 record that Experiments 2 and 4 were re-run with Tukey's HSD with the changed contrast named -- more discipline than most papers of this vintage show.

What does not hold together is concentrated, and it is concentrated in Experiment 4. Its control condition is reported twice as 4.20 with a spread of 0.21, and no sample of whole-number ratings produces that pair -- not at any of the five group sizes tested, not under either formula for the standard deviation, and not with the scale limits removed, which is the strongest form this check takes because it means the verdict does not rest on any range at all. Its stated recruitment of 193 exceeds what its own degrees of freedom account for by about sixty people, with no exclusion reported and the obvious exclusion route explicitly closed by the paper's statement that every participant recalled the load number. Its primary three-way interaction is printed "p = 001". And the sentence carrying its central conclusion -- that positive mood under load becomes indistinguishable from neutral mood -- attaches "more positive" to a mean below the control and "less positive" to one above it. Any one of those is an ordinary publishing accident. Together, in one experiment, they mean nothing that experiment reports can be verified as printed.

The Table 2 anomaly is narrower and cleaner. Two cells share the printed dispersion .52 where the only value twelve whole-number ratings can produce is .51, and they are the two cells behind the contrast the paper reports as F(1, 94) = 92.47. Both engines agree, and the result is unchanged whether the scale ran to 7 or to 9. The single thing a reader must accept is that the cells held twelve people each, which we derived rather than read; the corroboration is that all eight means in that row are attainable at twelve, which a wrong denominator does not generally deliver.

Three things cut the other way and belong in the same breath. First, the Experiment 3 off-scale mean of 7.33 is a contradiction between two passages, not a demonstrated impossibility: the paper never prints Experiment 3's own scale, importing it by a cross-reference in a sentence that contains a typo, and the alternative -- that the experiment ran on nine-point instruments throughout, as its similarity items demonstrably do -- would leave the number fine and the Methods wrong. Second, the pilot's out-of-range F rests on our assuming its 45 participants split evenly in three, which the paper does not state. Third, the very large effect sizes in Experiment 3, near five standard deviations, are a comparison we are supplying and would shrink substantially if the values in parentheses turned out to be standard errors -- neither table says which they are.

The coverage limits matter as much as the findings. Experiment 2's entire results table could not be checked at all: 126 participants do not divide into eight cells, no cell sizes are printed, and guessing a denominator is the standard route to a false accusation. Table 2's eight similarity cells are three-item composites our implementations cannot check at the right step size. Every cell mean in Experiments 2 and 4 reported in prose is likewise beyond reach. None of that clears those numbers; it means they were not examined.

Two independently impossible mean-and-standard-deviation pairs, each sitting under a result the paper depends on, are not reconcilable with the rest of what the paper reports. I have no confidence in the accuracy of Experiment 4 as published, and the Table 2 cells warrant the same reservation; the paper's own numbers do not reconcile.

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
