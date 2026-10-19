# Forensic review -- Johnson et al. 2011

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## RETRACTED ARTICLE: Happiness as alchemy: Positive mood leads to self-serving responses to social comparisons
*Camille S. Johnson, Diederik A. Stapel. Motivation and Emotion. 2011. doi:10.1007/s11031-011-9216-y*

**Design:** Four between-subjects factorial laboratory experiments plus a pilot study; the article is published under a RETRACTED ARTICLE title prefix

<sub>Analysed as `10.1007--s11031-011-9216-y`</sub>

> **HIGHLY SUSPICIOUS** — The pilot study's headline mood test, F(2, 42) = 18.44, cannot be produced by the three means and standard deviations printed in the same sentence, which imply an F between 26.0 and 27.0 under every group-size allocation tested.
>
> **In plain terms:** In the study that sets up the whole paper, the authors report a test result showing their happy/sad writing task changed people's mood. Working backwards from the average scores they print in the very same sentence, that test result should have been about 26; they print 18.44. Changing how many people were assumed to be in each group does not fix it, so one of the numbers in that sentence is not the number the analysis actually produced.
>
> **Evidence:** "A one-way Analysis of Variance (ANOVA) revealed that the mood manipulation significantly affected participant mood, F(2, 42) = 18.44, p < .001. Participants in the positive mood condition reported more positive mood (M = 7.20, SD = .93) that those in the control condition (M = 6.15, SD = .52) ... Participants in the negative mood condition reported more negative mood (M = 4.98, SD = .98)" (N = 45, three conditions, error df 42). Achievable F at 15/15/15: [26.01, 27.04]; at 12/21/12: [23.95, 24.93]; at 9/27/9: [21.16, 22.06]. Reported F = 18.44 lies below all three, and 0 of 5,000 Monte Carlo draws reproduce it.
> **Rests on:** logical necessity (no assumption added)
> **Reproduce:** no runnable command -- the review's command used an option this tool does not have. The finding's own numbers are above; re-derive from those.

**Verdict: unresolved** (confidence: high)

> **Table coverage:** 8 of 24 checkable cells were checked cell by cell, and 11 further table rows were checked in batch by check_summation_batch. The two counts are of different things and are not added: the batch tools report rows, not the cell identifiers this census uses, so the true combined coverage is somewhere between 11 and 19 of 24. A further 24 per-cell checks ran (`check_effect_plausibility`, `check_sd_or_se`, `detect_duplication`, `grim_check`, `grimmer_check`, `r_grim_ground_truth`, `r_sprite_ground_truth`, `recalc_f_to_p`, `recalc_independent_t`, `rivets_anova`) and report no cell ids at all, so the top of that range is a floor rather than a ceiling.

## Provenance of the analysis

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

5 study/studies, 11 variables, 63 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| pilot | Pilot study: mood induction without social comparison | rct | 45 | participant | no |
| exp1 | Experiment 1: positive mood x shared-birthday cue x comparison direction | rct | 47 | participant | no |
| exp2 | Experiment 2: mood (positive/negative) x direction x birthday cue, plus hanging control | rct | 141 | participant | no |
| exp3 | Experiment 3: mood (positive/neutral) x direction x ambiguity of similarity cue | rct | 96 | participant | no |
| exp4 | Experiment 4: mood (positive/neutral) x direction x cognitive load, plus hanging control | rct | 193 | participant | no |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Mood index (pilot study) | ordinal | discrete | 1-9 (integers) | - | mean of items (k=4): four nine-point bipolar mood items (negative/positive, sad/happy, unpleasant/pleasant, bad/good) | none -- composite granularity is 1/(items x n) | high |
| Self-evaluation index (pilot study) | ordinal | discrete | 1-9 (integers) | - | mean of items (k=3): three nine-point self-descriptiveness ratings: intelligent, competent, successful | none -- composite granularity is 1/(items x n) | high |
| Self-evaluation (own attractiveness rating), Experiments 1-4 | ordinal | discrete | 1-7 (integers) | - | measured | GRIM, GRIMMER, SPRITE | high |
| Target attractiveness rating (manipulation check), Experiments 1-4 | ordinal | discrete | 1-7 (integers) | - | measured | GRIM, GRIMMER, SPRITE | high |
| Single-item mood rating (Experiments 2 and 4) | ordinal | discrete | 1-7 (integers) | - | measured | GRIM, GRIMMER, SPRITE | high |
| Self-reported mood (Experiment 3) - response scale never stated | ordinal | unknown | not stated | - | measured | none -- variable not typed | low |
| Perceived similarity index (Experiment 3) | ordinal | discrete | 1-9 (integers) | - | mean of items (k=3): three nine-point similarity items: general similarity, special bond, similarity in aesthetic preferences (alpha = .87) | none -- composite granularity is 1/(items x n) | high |
| Mood induction condition | nominal | discrete | positive; negative; neutral/control | - | measured | percentage GRIM on cell counts | high |
| Direction of comparison | nominal | discrete | upward (more attractive target); downward (less attractive target) | - | measured | DEBIT; percentage GRIM | high |
| Similarity cue | nominal | discrete | shared birthday; different birthday; ambiguous aesthetic preference; unambiguous aesthetic preference | - | measured | percentage GRIM on cell counts | high |
| Cognitive load (Experiment 4) | nominal | discrete | load (8-digit number rehearsal); no load | - | measured | DEBIT; percentage GRIM | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Pilot study, Results | one_way_anova | Mood index (pilot study) (likert_composite) | Mood induction condition | 45 | none | none reported |
| Pilot study, Results | independent_t | Mood index (pilot study) (likert_composite) | - | 45 | none | none reported |
| Pilot study, Results | independent_t | Mood index (pilot study) (likert_composite) | - | 45 | none | none reported |
| Pilot study, Results | one_way_anova | Self-evaluation index (pilot study) (likert_composite) | Mood induction condition | 45 | none | none reported |
| Experiment 1, Manipulation check | one_way_anova | Target attractiveness rating (manipulation check), Experiments 1-4 (likert_item) | Direction of comparison | 47 | none | none reported |
| Experiment 1, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Similarity cue | 47 | none | none reported |
| Experiment 1, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Similarity cue, Direction of comparison | 47 | none | none reported |
| Experiment 1, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Direction of comparison | 47 | none | none reported |
| Experiment 2, Manipulation check | one_way_anova | Single-item mood rating (Experiments 2 and 4) (likert_item) | Mood induction condition | 141 | none | none reported |
| Experiment 2, Manipulation check | one_way_anova | Target attractiveness rating (manipulation check), Experiments 1-4 (likert_item) | Direction of comparison | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Mood induction condition, Direction of comparison, Similarity cue | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Similarity cue | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Direction of comparison | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Mood induction condition | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Mood induction condition, Similarity cue | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Mood induction condition, Direction of comparison | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Similarity cue, Direction of comparison | 126 | none | none reported |
| Experiment 2, Positive mood | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Direction of comparison | ? | none | none reported |
| Experiment 2, Positive mood | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Similarity cue | ? | none | none reported |
| Experiment 2, Positive mood | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Direction of comparison, Similarity cue | ? | none | none reported |
| Experiment 2, Positive mood | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | - | ? | none | none reported |
| Experiment 2, Positive mood | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | - | ? | none | none reported |
| Experiment 2, Positive mood | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | - | ? | none | none reported |
| Experiment 2, Positive mood | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | - | ? | none | none reported |
| Experiment 2, Negative mood | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Direction of comparison | ? | none | none reported |
| Experiment 3, Manipulation check | one_way_anova | Self-reported mood (Experiment 3) - response scale never stated (unknown) | Mood induction condition | 96 | none | none reported |
| Experiment 3, Manipulation check | one_way_anova | Target attractiveness rating (manipulation check), Experiments 1-4 (likert_item) | Direction of comparison | 96 | none | none reported |
| Experiment 3, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Similarity cue | 96 | none | none reported |
| Experiment 3, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Direction of comparison | 96 | none | none reported |
| Experiment 3, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Mood induction condition | 96 | none | none reported |
| Experiment 3, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Similarity cue, Mood induction condition | 96 | none | none reported |
| Experiment 3, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Similarity cue, Direction of comparison | 96 | none | none reported |
| Experiment 3, Similarity cue and mood effects on responses | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Mood induction condition | 96 | none | none reported |
| Experiment 3, Similarity cue and direction of comparison effects on responses | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Direction of comparison | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Perceived similarity index (Experiment 3) (likert_composite) | Similarity cue | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Perceived similarity index (Experiment 3) (likert_composite) | Direction of comparison | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Perceived similarity index (Experiment 3) (likert_composite) | Direction of comparison, Mood induction condition | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Perceived similarity index (Experiment 3) (likert_composite) | Similarity cue, Direction of comparison | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Perceived similarity index (Experiment 3) (likert_composite) | Similarity cue, Direction of comparison, Mood induction condition | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Perceived similarity index (Experiment 3) (likert_composite) | Direction of comparison | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Perceived similarity index (Experiment 3) (likert_composite) | Direction of comparison | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Perceived similarity index (Experiment 3) (likert_composite) | Direction of comparison | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Perceived similarity index (Experiment 3) (likert_composite) | Direction of comparison | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | pearson_correlation | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Target attractiveness rating (manipulation check), Experiments 1-4 | ? | none | none reported |
| Experiment 3, Perceptions of similarity | pearson_correlation | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Target attractiveness rating (manipulation check), Experiments 1-4 | ? | none | none reported |
| Experiment 3, Perceptions of similarity | pearson_correlation | Perceived similarity index (Experiment 3) (likert_composite) | Target attractiveness rating (manipulation check), Experiments 1-4 | ? | none | none reported |
| Experiment 4, Manipulation check | one_way_anova | Single-item mood rating (Experiments 2 and 4) (likert_item) | Mood induction condition | ? | none | none reported |
| Experiment 4, Manipulation check | one_way_anova | Target attractiveness rating (manipulation check), Experiments 1-4 (likert_item) | Direction of comparison | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Cognitive load (Experiment 4), Mood induction condition, Direction of comparison | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Cognitive load (Experiment 4) | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Mood induction condition | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Direction of comparison | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Cognitive load (Experiment 4), Mood induction condition | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Cognitive load (Experiment 4), Direction of comparison | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | Mood induction condition, Direction of comparison | ? | none | none reported |
| Experiment 4, No load conditions | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | - | ? | none | none reported |
| Experiment 4, No load conditions | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | - | ? | none | none reported |
| Experiment 4, No load conditions | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | - | ? | none | none reported |
| Experiment 4, No load conditions | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | - | ? | none | none reported |
| Experiment 4, Cognitive load conditions | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | - | ? | none | none reported |
| Experiment 4, Cognitive load conditions | independent_t | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | - | ? | none | none reported |
| Experiment 4, Cognitive load conditions | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | - | ? | none | none reported |
| Experiment 4, Cognitive load conditions | one_way_anova | Self-evaluation (own attractiveness rating), Experiments 1-4 (likert_item) | - | ? | none | none reported |

#### Variable/test mismatches

A parametric test is applied to an outcome this analysis typed as non-continuous. That is not proof of an error -- the typing may be wrong, and some parametric tests are robust -- but each pair below should be checked against the paper.

- **Pilot study, Results**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Mood index (pilot study)** is typed `likert_composite`.
- **Pilot study, Results**: `independent_t` assumes a continuous, roughly normal outcome, but **Mood index (pilot study)** is typed `likert_composite`.
- **Pilot study, Results**: `independent_t` assumes a continuous, roughly normal outcome, but **Mood index (pilot study)** is typed `likert_composite`.
- **Pilot study, Results**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation index (pilot study)** is typed `likert_composite`.
- **Experiment 1, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Target attractiveness rating (manipulation check), Experiments 1-4** is typed `likert_item`.
- **Experiment 1, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 1, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 1, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 2, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Single-item mood rating (Experiments 2 and 4)** is typed `likert_item`.
- **Experiment 2, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Target attractiveness rating (manipulation check), Experiments 1-4** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 2, Positive mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 2, Positive mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 2, Positive mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 2, Positive mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 2, Positive mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 2, Positive mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 2, Positive mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 2, Negative mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 3, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Target attractiveness rating (manipulation check), Experiments 1-4** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 3, Similarity cue and mood effects on responses**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 3, Similarity cue and direction of comparison effects on responses**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Perceived similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Perceived similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Perceived similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Perceived similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Perceived similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Perceived similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Perceived similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Perceived similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Perceived similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `pearson_correlation` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 3, Perceptions of similarity**: `pearson_correlation` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 3, Perceptions of similarity**: `pearson_correlation` assumes a continuous, roughly normal outcome, but **Perceived similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 4, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Single-item mood rating (Experiments 2 and 4)** is typed `likert_item`.
- **Experiment 4, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Target attractiveness rating (manipulation check), Experiments 1-4** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 4, No load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 4, No load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 4, No load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 4, No load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 4, Cognitive load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 4, Cognitive load conditions**: `independent_t` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 4, Cognitive load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.
- **Experiment 4, Cognitive load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (own attractiveness rating), Experiments 1-4** is typed `likert_item`.

_63 of 63 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. Pilot mood ANOVA F of 18.44 lies below every F achievable from the three means and SDs printed beside it  [HIGHLY SUSPICIOUS | confidence: high]

**In plain terms.** The pilot study reports an average mood score for each of three groups, and then a test statistic summarising how different those three averages are. The averages and the test statistic do not match: the averages imply a value around 26, and the paper prints 18.44. This holds whether the groups were equal-sized or badly unbalanced. The mismatch runs in the direction that makes the result look weaker, not stronger, so it is not the shape an exaggeration would take -- but one of the two sets of numbers is wrong.

- **Location:** Pilot study, Results (mood manipulation ANOVA)
- **Reported:** "A one-way Analysis of Variance (ANOVA) revealed that the mood manipulation significantly affected participant mood, F(2, 42) = 18.44, p < .001." Group means/SDs in the same passage: 7.20 (.93), 6.15 (.52), 4.98 (.98); N = 45, three conditions.
- **Computed:** rivets_anova, re-run at this stage: achievable F interval [26.01, 27.04] at n = 15/15/15, with 0 of 5,000 Monte Carlo draws over the rounding box reaching 18.44. Re-run at 12/21/12 gives [23.95, 24.93] and at 9/27/9 gives [21.16, 22.06]; the reported value sits below all three. The reported p (< .001) is not refuted -- every achievable F is MORE significant than the one printed, so the direction of the discrepancy is conservative.
- **As printed in the paper:** “A one-way Analysis of Variance (ANOVA) revealed that the mood manipulation significantly affected participant mood, F(2, 42) = 18.44, p < .001. Participants in the positive mood condition reported more positive mood (M = 7.20, SD = .93) that those in the control condition (M = 6.15, SD = .52), t(42) = 3.43, p = .001. Participants in the negative mood condition reported more negative mood (M = 4.98, SD = .98) than those in the control condition, t(42) = -3.80, p < .001.” _(found in the paper's text)_
- **Assumptions:** Cell ns are not printed. n = 15 per group follows from N = 45 across three conditions with error df 42 (= 45 - 3), and the finding was deliberately re-tested at two progressively more unequal allocations to check that the assumption is not doing the work; it is not. The two t-tests reported in the same passage, t(42) = 3.43 and t(42) = -3.80, carry df 42, i.e. they are contrasts on the ANOVA's pooled error term rather than two-sample tests -- a two-sample recomputation of them therefore does not apply and is not offered here as evidence.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The pilot's claim that the mood induction worked rests on a statistic that does not follow from the data printed beside it; the significance decision itself is unaffected, since every achievable F is more extreme than the reported one. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command used an option this tool does not have. The finding's own numbers are above; re-derive from those.

### 2. Sixty of Experiment 4's 193 stated participants appear in no reported analysis, with no exclusions or attrition disclosed  [SUSPICIOUS | confidence: high]

**In plain terms.** Experiment 4 says it recruited 193 students. The technical details attached to every one of its statistical tests imply that only about 133 people were actually in those analyses. The paper never mentions anyone dropping out, being excluded, or having missing data. The same check reconciles perfectly for the paper's other three experiments, so this is not a quirk of how the tests were counted -- roughly a third of Experiment 4's participants are simply unaccounted for.

- **Location:** Experiment 4, Participants and design versus Results and discussion
- **Reported:** "University (N = 193, 103 female) students participated in the study for monetary compensation. This experiment used a 2(mood: positive, neutral) x 2 (direction of comparison: upward vs. downward) x 2(load: load vs. no load) factorial design, with an additional no mood induction, no comparison, no load control condition." Every factorial test is reported at error df 110; every contrast against the control at df 124.
- **Computed:** check_summation_batch, re-run at this stage over all four experiments. Experiment 4: error df 110 + 8 cells = 118 in the factorial, contrast df 124 + 9 groups = 133 in total, against a stated N of 193 -- a shortfall of 60, 31% of the sample. The same arithmetic reconciles EXACTLY in the other three: Experiment 1 (43 + 4 = 47), Experiment 2 (126 + 15 = 141), Experiment 3 (88 + 8 = 96). 1 of 4 rows inconsistent.
- **As printed in the paper:** **Experiments 1-4, Participants and design sections vs reported degrees of freedom** -- “University (N = 193, 103 female) students participated in the study for monetary compensation. This experiment used a 2(mood: positive, neutral) × 2 (direction of comparison: upward vs. downward) × 2(load: load vs. no load) factorial design, with an additional no mood induction, no comparison, no load control condition.” _(found in the paper's text)_
- **Assumptions:** The derivation assumes the two df values come from the models the Methods describe -- a 2x2x2 factorial and single-df contrasts against a hanging control -- which is what the paper states, and is the reading under which the other three experiments reconcile to the digit. Innocent explanations that would resolve it entirely and are stated nowhere in the paper: undisclosed exclusions, listwise deletion, or a typo in the reported N.
- **Consequence:** changes no significance decision; 8 stated claims affected -- Every Experiment 4 test runs on a subset roughly two-thirds the size of the sample the paper says it recruited, and the paper reports no exclusions, attrition or missing data anywhere in that experiment. (asserted, not computed)
- **Reproduce:** no runnable command -- the review could not produce one that runs. The finding's own numbers are above; re-derive from those.

### 3. Two Table 2 self-evaluation cells report a standard deviation no whole-number responses can produce  [SUSPICIOUS | confidence: high]

**In plain terms.** If twelve people each pick a whole number from 1 to 7, only certain combinations of average and spread are arithmetically possible. Two cells of the paper's Table 2 report a spread that no such set of twelve answers can produce. Two independent pieces of software agree. The averages themselves are all fine, so this is a narrow problem with two numbers rather than a table-wide one -- but those two cells are the evidence for one of Experiment 3's conclusions.

- **Location:** Table 2, Self-evaluation row, Positive/Unambiguous columns (Experiment 3)
- **Reported:** "6.58 (.52)" and "4.08 (.52)" -- the Positive/Unambiguous upward and downward cells, on a self-rated attractiveness item the paper describes as a single seven-point scale.
- **Computed:** grimmer_check, re-run at this stage on both cells at n = 12: the single GRIM-consistent total (79 for 6.58, 49 for 4.08) admits no integer sum-of-squares of the required parity that rounds to SD = 0.52, under either the sample (n-1) or population (n) convention, with or without the scale bounds. R rsprite2 independently rejects both cells with 'The standard deviation is not consistent with this mean and number of observations (fails GRIMMER test)'. The two engines agree. Denominator: 4 of 24 checks across the 16 Table 2 cells were flagged; all 16 cell means pass GRIM.
- **As printed in the paper:** “6.58 (.52)” _(found in a table)_
- **Assumptions:** The cell n of 12 is derived, not printed: N = 96 in a 2x2x2 design with error df 88 (= 96 - 8) forces 12 per cell. Severity is capped at `suspicious` rather than `impossible` because the tool's discreteness premise was left at 'assumed' -- if each participant really contributed one whole-number rating on a seven-point item, as the paper's cross-reference implies, the arithmetic would license a stronger verdict, but that premise reaches Experiment 3 by cross-reference rather than by a scale printed in that section. R's refusal is likewise capped at `indeterminate` by our wrapper, because a raised exception is not a proof of infeasibility (measured false-raise rate 16.2%); it corroborates without licensing escalation.
- **Consequence:** 1 stated claim affected -- These two cells are the Positive/Unambiguous pair whose contrast, F(1, 94) = 92.47, is the evidence for the claim that positive-mood participants assimilate normally when the similarity cue is unambiguous. (asserted, not computed)
- **Reproduce:** no runnable command -- the review could not produce one that runs. The finding's own numbers are above; re-derive from those.

### 4. Experiment 4's cognitive-load means run in the opposite direction to the sentence citing them  [SUSPICIOUS | confidence: high]

**In plain terms.** In Experiment 4 the authors write that one group rated themselves more positively than a comparison group and another rated themselves less positively. The actual numbers printed in that sentence say the reverse: the supposedly higher score is 3.33 against a benchmark of 4.20, and the supposedly lower score is 5.53. Swapping the two would fix the sentence, and that is probably what happened -- but as published, the sentence Experiment 4's conclusion rests on is contradicted by the numbers inside it.

- **Location:** Experiment 4, Cognitive load conditions
- **Reported:** "This pattern was identical to the neutral mood condition, in which upward comparison led to more positive self-ratings (M = 3.33, SD = 1.05), F(1,124) = 18.83, p < .001, and downward comparison led to less positive self-ratings (M = 5.53, SD = .87), F(1,124) = 7.84, p = .006, relative to the control condition." The control mean is given twice in the same section as M = 4.20, SD = .21.
- **Computed:** No arithmetic performed. The passage describes 3.33 as more positive than a control of 4.20 and 5.53 as less positive than it, which reverses the printed ordering of both values against the control mean stated in the same paragraph. Values confirmed identical in the XML full text and the PDF.
- **As printed in the paper:** “This pattern was identical to the neutral mood condition, in which upward comparison led to more positive self-ratings (M = 3.33, SD = 1.05), F(1,124) = 18.83, p < .001, and downward comparison led to less positive self-ratings (M = 5.53, SD = .87), F(1,124) = 7.84, p = .006, relative to the control condition.” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own statements. The likeliest explanation by a wide margin is a transposition: swapping the two means makes the sentence internally consistent, matches the direction of all six other Experiment 4 cells, and matches the claimed parallel with the positive/load cells (5.71 upward, 3.09 downward). Nothing printed decides which of the two readings is the real one.
- **Consequence:** 1 stated claim affected -- Experiment 4 concludes that under cognitive load positive-mood participants behave identically to neutral-mood participants; as printed, the neutral/load means run opposite to every other cell in the experiment and so do not support the claim they are cited for. (asserted, not computed)
- **Reproduce:** `No command applies: this is a cross-reference contradiction between the prose and the means printed beside it, not a calculation.`

### 5. Experiment 3 reports two manipulation-check means of 7.33 on measures whose response scales it never states  [SUSPICIOUS | confidence: medium]

**In plain terms.** Experiment 3 reports two average scores of exactly 7.33: one for how attractive people rated a photo, one for their own mood. If those were measured on the 1-to-7 scale the paper points back to, a 7.33 average is off the top of the scale and impossible. But Experiment 3 never actually states what scale it used for either measure, and it does use a 1-to-9 scale elsewhere, on which 7.33 is unremarkable. So this is either an impossible number or an unreported change of instrument -- and the paper gives the reader no way to tell which.

- **Location:** Experiment 3, Manipulation check and Procedure
- **Reported:** "the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001" and, in the same section, "Participants in the positive mood condition were more positive (M = 7.33, SD = .86) than the neutral condition (M = 5.44, SD = .97)." The Procedure says only "participants rated their own attractiveness (on the seam measures used in Experiments 1 and 2). Then, participants rated the target on her attractiveness."
- **Computed:** grim_check: on the seven-point scale of Experiments 1 and 2 ("rated their own attractiveness and the target's attractiveness on seven-point scales (1 = not at all attractive and 7 = extremely attractive)"), the maximum attainable total at n = 48 is 336, while a mean of 7.33 requires 352 -- out of range. Cross-checked with R scrutiny, which returns GRIM-consistent: scrutiny tests granularity only and does not test scale bounds, so the two engines are answering different questions and this is not a disagreement about the arithmetic.
- **As printed in the paper:** **Experiment 3, Manipulation check** -- “the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001” _(found in the paper's text)_
- **Assumptions:** The seven-point ceiling reaches Experiment 3 only through the paper's own cross-reference, and that cross-reference sentence is attached to the SELF rating -- the target rating follows in a separate sentence carrying no scale at all. Experiment 3 demonstrably uses nine-point items for its similarity index, so a silent switch to nine-point attractiveness and mood items is a live innocent reading, and it is supported by the fact that Experiment 3's two means straddle 5.75 while the corresponding pairs in Experiments 1, 2 and 4 straddle 4. The paper is SILENT on which is true, so no out-of-range verdict is asserted here; what is asserted is that the reader cannot tell. Note also that the sentence establishing the scale contains a typo ("seam" for "same"), one of four garbled constructions in load-bearing passages, along with "rated more attractive than the (M = 5.58, SD = .78) than the unattractive target", "under cognitive loaded", and "Fours studies examine".
- **Consequence:** 2 stated claims affected -- Experiment 3's two manipulation checks -- that the mood induction worked and that the attractive target was seen as more attractive -- cannot be evaluated at all, because the paper does not state the scales those means are on. (asserted, not computed)
- **Reproduce:** no runnable command -- the review could not produce one that runs. The finding's own numbers are above; re-derive from those.

### 6. Two p-values printed with the decimal point missing, on tests the paper's conclusions rely on  [SUSPICIOUS | confidence: high]

**In plain terms.** Two probability values are printed as '011' and '001', with the decimal point dropped. Read literally they are impossible values. What the authors meant is obvious, but both sit in the sentences reporting key results, and the missing dot means automated checking software skips those two tests entirely.

- **Location:** Experiment 1, Self-evaluations; Experiment 4, Self-evaluations
- **Reported:** "Exposure to the upward comparison target led to lowered self-evaluations (M = 3.33, SD = .65) compared to the downward comparison target (M = 4.64, SD = 1.50), F(1, 46) = 6.95, p = 011." and "Analysis revealed the expected three-way interaction effect of load, mood, and direction of comparison on attractiveness, F(1, 110) = 11.23, p = 001."
- **Computed:** No arithmetic performed. As written each value asserts a probability of one or greater, outside the range a p-value can take. The intended values are plainly .011 and .001. Confirmed identical in the XML full text and the PDF.
- **As printed in the paper:** “Analysis revealed the expected three-way interaction effect of load, mood, and direction of comparison on attractiveness, F(1, 110) = 11.23, p = 001.” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own statements. This is typographic and not a claim about the data; it is recorded because of where the two errors sit, and because each removes a test from the reach of automated verification -- both were invisible to statcheck.
- **Consequence:** changes no significance decision; 2 stated claims affected -- Both sit on load-bearing sentences -- Experiment 1's simple effect and Experiment 4's headline three-way interaction -- so neither of those two tests can be checked by any automated p-value checker. (asserted, not computed)
- **Reproduce:** `No command applies: this is a notation defect in the printed text, not a calculation.`

### 7. Two contrasts presented as significant in the main text fail the authors' own Tukey correction, disclosed only in footnotes  [SUSPICIOUS | confidence: medium]

**In plain terms.** The authors ran a stricter version of their statistics to check whether their results survived testing many comparisons at once. Two of them did not: they moved from 'significant' to not. The authors say so honestly, but only in footnotes, while the main text presents both as significant with no caveat. A reader who did not read the footnotes would take away two conclusions the authors' own check does not support.

- **Location:** Experiment 2 footnote 2 and Experiment 4 footnote 5 (recovered from the PDF; absent from the XML full text)
- **Reported:** "with the only difference being that in the negative mood, shared birthday, upward comparison condition differs from the control at the p = .07 level" and "with the only difference being that the high load, neutral mood induction, downward comparison condition differed from the control at the p = .13 level". Both corresponding main-text sentences assert the contrast as significant with no qualifier.
- **Computed:** No arithmetic performed: this is the paper's own disclosure read against its own Results text. Separately, multiplicity_report over Experiment 4's eight cell-versus-control contrasts returned `consistent` with 0 claims lost to correction, but could evaluate only the 4 whose p was printed exactly -- and the authors' Tukey HSD is stricter than any method that check applies.
- **As printed in the paper:** **Experiment 4, No load and Cognitive load conditions** -- “followed by single degree of freedom contrasts to test specific hypotheses (Jaccard [1998]).” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own statements. Running and reporting the correction at all is to the authors' credit, and many papers of this period did neither; what is recorded is the placement, not the analysis.
- **Reproduce:** no runnable command -- the review's command used an option this tool does not have. The finding's own numbers are above; re-derive from those.

### 8. Table 1's caption names three dependent measures; the table reports one and the text reports none of the other two  [SUSPICIOUS | confidence: high]

**In plain terms.** The title above Experiment 2's table promises results for three different things that were measured. The table contains only one of them, and the other two are never reported anywhere in the paper. They are also not listed among the things Experiment 2 says it measured, so the likeliest explanation is that the caption was copied from the other table rather than that results were withheld.

- **Location:** Table 1 caption versus Table 1 body (Experiment 2)
- **Reported:** "Effects of upward (more attractive) versus downward (less attractive) comparisons on self-evaluations, ratings of target similarity, and use of information to benefit the self as a function of mood and shared birthday information". The table body contains a single data row, Self-evaluation.
- **Computed:** No arithmetic performed. Confirmed in both sources: the XML grid has one data row and the PDF's Table 1 (page 9) likewise. Experiment 2's Dependent measures section describes only attractiveness and mood ratings, so neither 'ratings of target similarity' nor 'use of information to benefit the self' is described as collected either.
- **As printed in the paper:** “Effects of upward (more attractive) versus downward (less attractive) comparisons on self-evaluations, ratings of target similarity, and use of information to benefit the self as a function of mood and shared birthday information” _(found in the paper's text)_
- **Assumptions:** Because the two extra measures are absent from the Methods as well as from the table, a caption copied from another table is at least as likely as suppressed outcomes -- and Table 2 does report a Similarity row, which is where such a caption would have come from. Recorded at `suspicious` for that reason rather than as selective outcome reporting.
- **Reproduce:** `No command applies: this is a cross-reference contradiction between a caption and its own table.`

### 9. The only data-availability statement routes all verification through a personal request, in a paper since retracted  [SUSPICIOUS | confidence: medium]

**In plain terms.** The paper offers its data only on request to one of the authors, in a single footnote, with no file or repository anyone can go to. That was normal practice for psychology in 2011 and is not a criticism of the authors by the standards of the time. It matters here only because this article has since been retracted, so that offer turned out not to be a route anyone could use.

- **Location:** Experiment 3, footnote 4 (recovered from the PDF; absent from the XML full text)
- **Reported:** "Complete data and results available from the first author." No repository, accession number or supplementary file is named anywhere in the article.
- **Computed:** No arithmetic performed. No supplementary files accompany this paper, so no participant-level data could be swept for duplication, and none of the paper's reported values can be checked against the data behind them.
- **As printed in the paper:** “Complete data and results available from the first author.” _(found in the PDF text layer)_
- **Assumptions:** This is the state-but-withhold pattern named in the shared rulebook, which is a standard this analysis supplies rather than one the paper accepted -- and 'available from the first author' was the ordinary convention in 2011 social psychology, so on its own it carries little weight and is not a criticism of the authors' practice at the time. It is recorded because the article is published under a RETRACTED ARTICLE title prefix, so the offer was in the event not the route to verification it appears to be.
- **Reproduce:** `No command applies: this is a reporting-practice observation.`

### 10. Three reported p-values disagree with their own test statistics, one with no available explanation  [SUSPICIOUS | confidence: high]

**In plain terms.** Three of the sixty-three test results in the paper have a probability value that does not match the statistic printed next to it. One is explained by a mistyped detail and one is a small discrepancy in the cautious direction. The third, where the paper reports a probability of .83 for a statistic that implies .22, has no explanation I could find. None of the three changes whether a result counts as significant.

- **Location:** Pilot study Results; Experiment 3, Perceptions of similarity
- **Reported:** "F(1, 42) = .27, p = .76"; "Identical effects emerged when the information was unambiguous, F(1, 94) = 1.50, p = .83."; "r(24) = .53, p = .008".
- **Computed:** statcheck extracted 63 statistics and flagged 3 after rounding rescue, with 0 decision errors -- an inconsistency rate of 4.8%. Re-run at this stage: recalc_f_to_p confirms F(1, 42) = .27 gives p = .606 as printed but p = .765 at df1 = 2 (achievable interval [.761, .768]), so the printed df1 = 1 is a typo -- the paper describes a one-way ANOVA over three conditions, which has df1 = 2, and rivets_anova independently returns `consistent` on those three groups. recalc_f_to_p on F(1, 94) = 1.50 gives p = .224 (achievable interval [.2230, .2245]) against the printed .83; the tool records this as `consistent` because it flags only over-claims, and .83 is conservative.
- **As printed in the paper:** **Results sections, Pilot study through Experiment 4** -- “Analysis revealed the expected three-way interaction effect of load, mood, and direction of comparison on attractiveness, F(1, 110) = 11.23, p = 001.” _(found in the paper's text)_
- **Our check returned a different severity.** The `recalc_f_to_p` check returned `consistent` for the sweep finding `pilot_selfeval_df_typo`, which this review recorded as `suspicious`. This entry asserts more than the check established, so read it as this review's judgement and not as a computed result. The finding states a reason.
- **Assumptions:** None beyond the paper's own statements. A 4.8% statcheck rate is unremarkable in isolation -- roughly half of clean control papers contain at least one such inconsistency -- and this must not carry weight on its own. The middle case is the one with no innocent reading I could find: .83 is not the p of F(1, 94) = 1.50 under any tail convention, and the neighbouring sentence reports F(1, 94) = .31, p = .58, whose p is correct, so .83 is not a house convention.
- **Consequence:** changes no significance decision -- None of the three crosses the alpha the paper used -- statcheck reports zero decision errors -- so no reported conclusion changes on any of them. (asserted, not computed)
- **Reproduce:** `metascience f-to-p --f-value 1.50 --df1 1 --df2 94 --reported-p 0.83 --decimals-p 2 --decimals-f 2`

### 11. Degrees of freedom on isolated tests in Experiments 1, 2 and 3 do not reconcile with the stated sample sizes  [SUSPICIOUS | confidence: medium]

**In plain terms.** Every statistical test carries a number that encodes how many people were in it. In each of three experiments, most of those numbers add up correctly against the stated sample size and a few do not -- for example, four correlations in Experiment 3 imply 26 participants where every group in that study is a multiple of twelve. Individually these are the kind of slip that happens in any paper; together they are the same signature as the much larger sample discrepancy in Experiment 4.

- **Location:** Experiment 1 Self-evaluations; Experiment 2 Positive and Negative mood; Experiment 3 Perceptions of similarity
- **Reported:** Experiment 1 reports F(1, 46) among tests otherwise at F(1, 43); Experiment 2 reports F(1, 124) among tests at F(1, 118) and F(1, 132); Experiment 3 reports all four of its correlations as r(24).
- **Computed:** check_summation_batch: Experiment 1's df 46 + 2 groups = 48 against a stated N of 47; Experiment 2's df 124 + 9 groups = 133 against a stated N of 141; Experiment 3's r(24) requires n = 26, while every derivable subgroup in that experiment is a multiple of 12. In each experiment the majority of df reconcile exactly with the stated N and design, and only isolated tests do not. 3 of 3 rows inconsistent.
- **As printed in the paper:** **Experiments 1-3, reported degrees of freedom** -- “Exposure to the upward comparison target led to lowered self-evaluations (M = 3.33, SD = .65) compared to the downward comparison target (M = 4.64, SD = 1.50), F(1, 46) = 6.95, p = 011.” _(found in the paper's text)_
- **Assumptions:** These are individually weak and should be read as a pattern, not as three charges. Ordinary explanations cover each in isolation: a df printed for a model other than the one described, a contrast on a pooled error term the text does not name, or plain typos. No conclusion turns on any of them, since a df off by one or two changes no p-value materially.
- **Consequence:** changes no significance decision -- Each anomalous value sits under a test cited in support of a hypothesis, but a discrepancy of one or two in the degrees of freedom changes no p-value materially, so no individual conclusion turns on these. (asserted, not computed)
- **Reproduce:** no runnable command -- the review could not produce one that runs. The finding's own numbers are above; re-derive from those.

### 12. Every reported comparison yields an effect size near the largest the measures can express, in cells of twelve  [INDETERMINATE | confidence: medium]

**In plain terms.** The paper never reports how big its effects were, so I calculated them. Its substantive results are as large as its manipulation check -- the deliberately obvious comparison between an attractive and an unattractive photograph -- meaning the two groups' scores barely overlap at all. That is very unusual for measures of how people rate themselves, and it comes out of groups of twelve people, which is under half the size needed to reliably detect even a large effect. This is not an error, and it is not evidence of one; it is a reason to treat the sizes of these effects with caution.

- **Location:** Experiment 2 Manipulation check; Table 2, Self-evaluation and Similarity rows (Experiment 3)
- **Reported:** The paper reports no effect size for any of its 63 tests, and no a-priori power analysis for any of its four experiments.
- **Computed:** check_effect_plausibility, from the group statistics the paper prints: Experiment 2's attractiveness manipulation check gives Hedges' g = 4.89 [4.22, 5.62]; Experiment 3's Positive/Ambiguous similarity contrast g = 5.03 [3.53, 6.88]; Experiment 3's Positive/Unambiguous self-evaluation contrast g = 4.64 [3.23, 6.39]. Separately, required_n: a 12-versus-12 cell pair has 46% of the sample needed to detect even a conventionally large effect (d = 0.8) at 80% power.
- **As printed in the paper:** **Experiment 2, Manipulation check** -- “The upward comparison target was rated more attractive (M = 5.98, SD = .69) than the downward target (M = 2.46, SD = .74), F(1,118) = 716.92, p < .001.” _(found in the paper's text)_
- **Assumptions:** This is context I am supplying, not a defect the paper owed anyone. All three dispersions are labelled SD rather than SEM, all three comparisons are between-subjects as described, and no units mismatch is in play, so the three ordinary deflationary explanations are ruled out. The right yardstick is the manipulation check itself: g = 4.89 for 'is this photograph of an attractive person more attractive than this photograph of an unattractive person' is exactly where such a value is expected. The two substantive outcomes sit in the same range, which is the part worth a reader's attention. Small-sample designs of this era routinely produced inflated published estimates, and that is a property of the literature, not an accusation about this paper.
- **Reproduce:** no runnable command -- the review could not produce one that runs. The finding's own numbers are above; re-derive from those.

## What we could NOT check

- **Table 1 (Experiment 2), all eight Self-evaluation cells** — GRIM, GRIMMER and SPRITE all need a cell n and none is printed. Unlike Experiment 3 the n cannot be derived: the 126 factorial participants implied by the error df of 118 do not divide evenly into eight cells (15.75 each), so cell sizes were unequal by an unknown amount. Running a granularity check on a guessed n is the commonest route to a false accusation. All eight means do lie within the stated 1-7 scale bounds.
- **Experiment 1, all four cell means (M = 5.08, 4.75, 3.33, 4.64)** — N = 47 does not divide into four cells and no cell ns are printed, so no granularity check can be run.
- **Experiment 4, all eight cell means and the control mean** — No cell ns are printed, and the stated N = 193 does not reconcile with the degrees of freedom, so no denominator can be trusted for a granularity check.
- **Table 2, Similarity row (all eight cells)** — All eight refused: the similarity index is the mean of three nine-point items, so its granularity is 1/(3n) rather than 1/n, and grim_test has no items parameter. Checking these at 1/n would manufacture impossibilities. This is a gap in our toolkit, not a fact about the paper.
- **Experiment 3, self-reported mood (M = 7.33, SD = .86 positive; M = 5.44, SD = .97 neutral)** — The response scale for the Experiment 3 mood item is never stated. The pilot used nine-point mood items and Experiments 2 and 4 a single seven-point item; Experiment 3 says neither. Without a stated bound no range check can be run, and inventing one would invert the check.
- **Experiment 1 and Experiment 4 manipulation-check F statistics (F(1,43) = 38.80; F(1,110) = 259.08)** — These are main effects from factorial ANOVAs whose error term is pooled across all cells, but only marginal means and SDs are printed. The marginal SDs absorb variance from the other factors, so a recomputation would use a systematically different denominator than the paper's model and could not distinguish a real discrepancy from that mismatch.
- **Figures 2 and 3** — Figure extraction was not run. Both plot means also printed in Table 2 and in the Experiment 4 prose respectively, and neither caption states what any error bars represent, so nothing checkable is believed to be unique to them.
- **Table 1 footnote** — The XML extraction reported zero footnotes for Table 1, but the PDF shows one carrying Experiment 2's control statistics (M = 4.20, SD = .86) and a blanket claim that all self-evaluations differed from the control at p < .05. It was recovered from the PDF and used; an XML-only sweep would have missed the only place Experiment 2's control condition is quantified.
- **Supplementary materials** — None accompany this paper in our corpus. The article's only data-availability statement is a footnote offering the data on request, so there is no participant-level file to check for duplication.
- **Retraction notice** — The article is published under the title prefix 'RETRACTED ARTICLE' but neither the XML nor the PDF contains a retraction notice, date, or statement of grounds. The reason for retraction could not be read from the paper itself and is not assumed anywhere in this report; every finding rests only on the article's own printed values.
- **table rows Similarity, Similarity, Similarity, Similarity, Similarity, Similarity and 2 more** — grim_check, grimmer_check, sprite_reconstruct not run: multi-item composite whose scoring is undeclared. If the score is a MEAN of items its granularity is 1/(items*n) and grim_test has no `items` parameter, so checking at 1/n would manufacture an impossibility; if it is a SUM the granularity is 1/n and the check is valid. Declare `derivation` as 'mean_of_items' or 'sum_of_items' to resolve this -- the field is already in the schema and the prompt asks for it.

## Questions for the authors

_Each of these is answerable from what the authors already have. None presupposes an error on their part: an inconsistency is far more often a reporting slip, or a mistake by this tool in reading the number off the page, than anything else._

1. The pilot study reports F(2, 42) = 18.44 for the mood manipulation alongside group means of 7.20 (SD .93), 6.15 (SD .52) and 4.98 (SD .98). Recalculating from those three means and standard deviations gives an F between 26.0 and 27.0 at equal group sizes, and it stays above 21 even at strongly unequal allocations such as 9/27/9. Could you send the per-group sample sizes and the ANOVA table for that analysis?
   <sub>Would resolve: Would settle whether the F, one of the three SDs, or the group sizes is the value that does not belong.</sub>
2. Experiment 4 states N = 193, while the factorial tests are reported at error df 110 and the contrasts against the control at df 124, which together imply about 133 participants entered the analyses. The same arithmetic reconciles exactly for Experiments 1, 2 and 3. Could you provide the per-cell sample sizes for Experiment 4 and a note of any exclusions or missing data?
   <sub>Would resolve: Would resolve the 60-participant shortfall and establish whether the reported N or the analysed N is the one to read.</sub>
3. Experiment 3 reports mean target attractiveness of 7.33 (SD 1.19) and mean self-reported mood of 7.33 (SD .86). The Procedure refers to the measures used in Experiments 1 and 2, which are described there as seven-point scales, on which 7.33 is not attainable. Could you confirm the response scales used for the attractiveness and mood items in Experiment 3?
   <sub>Would resolve: Would decide between an out-of-range value and an unreported change of instrument -- the paper as printed does not permit either reading to be ruled out.</sub>
4. Table 2's Positive/Unambiguous self-evaluation cells read 6.58 (.52) and 4.08 (.52). At twelve participants per cell on a seven-point single-item measure, no set of whole-number ratings produces a standard deviation of .52 with either of those means. Could you send the cell-level descriptive output for that row?
   <sub>Would resolve: Would establish whether the cell n is twelve, whether the measure is a single integer-valued item, and whether the printed SDs are as computed.</sub>
5. In the Experiment 4 cognitive load section, the neutral mood condition is described as showing upward comparison leading to more positive self-ratings (M = 3.33) and downward comparison to less positive self-ratings (M = 5.53), relative to a control mean of 4.20. As printed those two means run opposite to the description. Could you confirm which mean belongs to which condition?
   <sub>Would resolve: A transposition would explain it entirely; as printed, the sentence Experiment 4's conclusion rests on is contradicted by its own values.</sub>

## Limitations

- This agent reads text and tables and does NOT see figures. Figure extraction was not run on this paper: Figures 2 and 3 plot means that are also printed in Table 2 and in the Experiment 4 prose, and neither caption states what its error bars represent, so no value was believed to be unique to them. Anything visible only in those charts is outside this review.
- Per-cell sample sizes are printed nowhere in this paper. Cell ns were derivable only for Experiment 3 (N = 96, eight cells, error df 88 forces 12 each). For Experiments 1, 2 and 4 they are not derivable at all, which is why the granularity checks that would test Table 1 and the Experiment 4 means could not be run. That is the single largest gap in coverage here and it is a property of the paper's reporting, not of the toolkit.
- The `quote_not_located` marker fired on 13 of 13 accusations from the numeric sweep. On re-reading the XML full text at this stage, every one of those spans was found verbatim, including the malformed 'p = 011' and 'p = 001', the 'seam measures' typo, and the Experiment 4 load-condition means. This is an instrument artefact affecting the whole worklist, not evidence about any individual finding.
- Two of the passages this review relies on -- Table 1's footnote and the Tukey footnotes in Experiments 2 and 4 -- exist only in the PDF; the XML extraction dropped them. Their content was read from the PDF but was not re-verified against a second independent extraction.
- One spot-recheck was discarded as a misapplication rather than reported: recalculating the pilot's t(42) = 3.43 as a two-sample t returns 3.82 and flags `suspicious`, but the paper's df of 42 shows those are contrasts on the ANOVA's pooled error term, not two-group tests, so the recomputation does not apply.
- This system reads one paper and reaches no network. Two questions a reader needs in order to weigh the findings here are outside its reach: whether similar anomalies appear in other papers by the same authors, and how these effect sizes compare with others in this literature. The second is especially live given that the article is retracted and that the retraction's grounds could not be read from the article itself.
- GRIMMER severities in this report are capped at `suspicious` because the discreteness premise -- that each participant contributed one whole-number rating -- reaches Experiment 3 by the paper's own cross-reference rather than by a scale printed in that section. Confirming the instrument directly would license a stronger verdict on the two flagged Table 2 cells.
- No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.

## Coverage

- **Statistics found:** 63; **checked:** 41
- **Tools run:** extract_xml, get_table, rivets_anova, recalc_independent_t, grimmer_check, r_grim_ground_truth, r_sprite_ground_truth, check_summation_batch, recalc_f_to_p, statcheck, grim_check, sprite_reconstruct, check_table, check_sd_or_se, check_effect_plausibility, detect_duplication, multiplicity_report, required_n, parse_cells_typed, extract_pdf
- **Tables checked:** Table 1 (Experiment 2), Table 2 (Experiment 3)
- **Checkable table cells:** 24 of 24 surveyed; **checked:** 8
    - 24 could not be checked without knowing what kind of quantity the row reports
- **Every checkable item:** 157 registered; 24 refused with a stated reason; **133 outstanding**
    - how many were CHECKED is not measured -- no persisted item identity joins a tool call back to a manifest row, so how many items were CHECKED cannot be counted. This is not a count of zero. This is not a count of zero.
- **Stage-1 findings:** 21 raised; 16 carried into this report; 5 not carried
- **Where a check and this review disagreed:** 2 sweep findings recorded a severity the validated check behind them did not return (1 upgraded, 1 downgraded). 1 is marked on the entry above that cites it. 1 is an explained downgrade on an entry above, counted here and not marked there: the check said more, this review said less and said why, which is what stage 2 is for.
- **Traceable to the page:** 31 of 31 checks recorded the passage their numbers were read from; 31 of those were located in the paper's own text.

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

### `check_sd_or_se` — probabilistic

Adjudicates whether a reported dispersion value is an SD or a mislabelled SE.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- SD and SE are linked by SE = SD/sqrt(n); n must be the cell's true denominator.
- A 'neither reading fits' verdict rests ENTIRELY on the plausibility ceiling implied by the variable's range.
- A ceiling from an ASSUMED bound caps at `suspicious`; only a stated bound licenses `highly_suspicious`.
- Under the SE reading the rounding interval stretches by sqrt(n).
- BASE RATE: mislabelling SE as SD is the norm, not an outlier. Olsen (2002) found 35 of 88 studies (40%) reporting the SEM where they said SD. Heathers (2025): 'usually an honest mistake of statistical ignorance, not anything that implies a problem with research integrity.' Report it as a reporting defect; it moves what the numbers MEAN, not what the authors did.

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

### `recalc_f_to_p` — probabilistic

Verifies a reported p against the range its rounded F and df imply.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The reported p is assumed to be the upper-tail F probability at the printed df.
- The printed F is rounded, so it asserts a p RANGE; only a p below that range is flagged.
- The F must come from the test its df describe, whose assumptions are inherited.

### `recalc_independent_t` — probabilistic

Recomputes an independent-samples t-test, under both Welch and Student readings.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- Independent groups, and normality of the sampling distribution of the mean difference.
- Welch's and Student's pooled t are BOTH accepted unless the paper states which it ran.
- Homogeneity of variance is assumed only under the Student reading.
- One- and two-tailed p conventions are both accepted unless stated.
- Input rounding propagates into an achievable interval; only over-claimed significance is flagged, unless you pass p_is_threshold=False to say the paper printed the p exactly.

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

This paper reports a pilot study and four between-subjects laboratory experiments arguing that people in a positive mood reinterpret ambiguous information about a comparison target in whatever way flatters them: assimilating to someone more attractive, contrasting away from someone less attractive. It is published under a RETRACTED ARTICLE title prefix, but neither the XML nor the PDF carries a retraction notice or statement of grounds, so the reason for retraction could not be read from the article. Nothing below assumes it. Every finding rests on values printed in the paper itself.

## What actually verified

Of 41 checks that ran, 28 passed, 20 of them collapsed inside a single table check and therefore invisible in the findings list. All eight Table 2 self-evaluation means are attainable as integer totals over twelve responses on a 1-7 scale and all lie within the scale bounds. No (mean, SD) pair recurs across the two tables of summary statistics drawn from different participants, which is exactly the configuration a duplication check exists for and it came back clean. Experiment 4's control-condition SD of .21 sits comfortably inside the plausible bound for a seven-point scale under both the SD and SE readings. The pilot's self-evaluation ANOVA reconciles cleanly on the same three groups and the same assumed group sizes as the mood ANOVA that does not -- which is what shows the method, not the assumption, is producing that flag. Nothing could be refused for want of a precondition; the refusal count for this paper is zero.

## Why the pilot ANOVA leads

The mood test that opens the paper, F(2, 42) = 18.44, cannot come from the three means and SDs in the same sentence. The achievable range is [26.01, 27.04] at equal group sizes, and I re-ran it at 12/21/12 and again at 9/27/9 specifically to check whether the equal-n assumption was doing the work. It is not: the reported value sits below all three intervals, and none of 5,000 Monte Carlo draws over the rounding box reaches it. The direction is worth stating plainly, because it cuts against the obvious suspicion -- the printed statistic is *less* significant than the data imply, which is the opposite of what a self-serving error looks like. A single mistyped SD would explain it, and so would an F carried over from another analysis.

## The pattern the individual findings share

Taken one at a time, most of what follows is ordinary. A 4.8% statcheck rate is unremarkable; roughly half of clean control papers contain at least one such inconsistency. Two dropped decimal points are typographic. A caption naming measures the table does not carry is most likely copied from the other table. Degrees of freedom off by one or two change no conclusion.

What makes the set worth a reader's attention is that in each experiment the *majority* of degrees of freedom reconcile exactly with the stated N and design, and only isolated tests do not -- and in Experiment 4 that same arithmetic fails by 60 people, 31% of the sample, with no exclusions, attrition or missing data reported anywhere. The check that produces that number reconciles to the digit in Experiments 1, 2 and 3. This is the finding with the widest reach in the paper: every Experiment 4 test runs on a subset roughly two-thirds the size of the sample the paper claims.

## Two things the paper does not let a reader settle

Experiment 3 reports two manipulation-check means of exactly 7.33, one for target attractiveness and one for mood. On the seven-point scale the Procedure cross-references, 7.33 is off the top of the scale and unattainable. But that cross-reference is attached to the self-rating; the target rating follows in a separate sentence with no scale at all, Experiment 3 uses nine-point items for its similarity index, and its two attractiveness means straddle 5.75 where the corresponding pairs in the other three experiments straddle 4. I dropped this a rung from the sweep's grading for that reason. The defect that survives is not an impossible number -- it is that Experiment 3 does not state its own response scales, so neither of its manipulation checks can be evaluated at all.

The second is Experiment 4's cognitive-load paragraph, which describes 3.33 as more positive than a control of 4.20 and 5.53 as less positive than it. A transposition explains it completely, matches the direction of all six other cells in that experiment, and matches the parallel the sentence claims. Nothing printed decides it, and as published the sentence carrying Experiment 4's conclusion is contradicted by the numbers inside it.

## On effect sizes, and on the footnotes

The paper reports no effect size for any of its 63 tests and no power analysis for any of its four experiments, so I computed three. The two substantive outcomes come out at Hedges' g of 4.6 and 5.0, matched against g = 4.89 for the manipulation check -- which is to say, distinguishing self-ratings between conditions worked about as decisively as distinguishing a photograph of an attractive person from an unattractive one, out of cells of twelve. That is context, not a defect, and small-sample designs of this era routinely produced inflated published estimates.

Finally, credit where it is due: the authors ran a Tukey correction as a sensitivity analysis and reported honestly that two contrasts do not survive it, moving to p = .07 and p = .13. Many papers of this period did neither. What is recorded here is only the placement -- both reversals appear in footnotes while the main text asserts both contrasts as significant without qualification.

The arithmetic in this paper does not settle either way. Several of its numbers contradict each other, one substantially, and the paper withholds the per-cell sample sizes that would let a reader decide which of each contradictory pair to believe.

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
