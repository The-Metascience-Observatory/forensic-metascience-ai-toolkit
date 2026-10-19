# Forensic review -- Johnson et al. 2011

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## RETRACTED ARTICLE: Happiness as alchemy: Positive mood leads to self-serving responses to social comparisons
*Camille S. Johnson, Diederik A. Stapel. Motivation and Emotion. 2011. doi:10.1007/s11031-011-9216-y*

**Design:** Four between-subjects factorial laboratory experiments plus a pilot study; mood manipulated by autobiographical essay, social-comparison direction and similarity-cue ambiguity manipulated between subjects. NOTE: the article is published as RETRACTED (title carries the retraction marker); the second author is Diederik Stapel, whose work was retracted en masse following the 2011 Levelt/Noort/Drenth investigations. This review evaluates the printed numbers on their own terms and does not rely on the retraction for any finding.

<sub>Analysed as `10.1007--s11031-011-9216-y`</sub>

> **IMPOSSIBLE** — Experiment 4's control condition is reported as M = 4.20, SD = .21 on a single whole-number 1-7 rating, and no set of whole-number responses can produce that pair at any sample size -- yet it is the baseline every one of that experiment's eight results is measured against.
>
> **In plain terms:** Experiment 4 says its comparison group averaged 4.20 out of 7 on a single whole-number rating, with the responses spread by only 0.21 around that average -- but whole numbers cannot cluster that tightly around 4.20, because the closest they can get is a spread of about 0.41, roughly twice as wide. The baseline that all eight of that experiment's results are measured against therefore cannot be a real set of answers from real people.
>
> **Evidence:** "Higher levels of self-evaluations relative to the control condition (M = 4.20, SD = .21) were found" and, in the next section, "Compared to a control condition (M = 4.20, SD = .21)". The measure is stated as a single item: "Participants also rated their own attractiveness (How attractive are you?) on a seven-point scale (1 = not at all, 7 = extremely)" (Experiment 1), and Experiment 4 states participants "completed the same measures of mood, own attractiveness, and other attractiveness as in Experiments 1 and 2". For integer responses averaging exactly 4.20, the smallest attainable SD is approximately 0.41.
> **Rests on:** logical necessity (no assumption added)
> **Reproduce:** `metascience sprite --mean 4.2 --sd 0.21 --n 15 --scale-min 1 --scale-max 7 --decimals-mean 2 --decimals-sd 2 --data-type likert`

**Verdict: untrustworthy** (confidence: high)

> **Table coverage cannot be stated as a fraction on this run.** 28 distinct table cells were checked cell by cell, and this census surveyed 24 checkable cells in the paper's tables -- so at least 4 of the cells checked came from outside them: values read out of the prose and submitted as a table, a supplement, or a table only the PDF carries. The two counts are of different populations, so no percentage of one against the other is given, and this does NOT mean every surveyed cell was checked. Separately, 5 further table rows were checked in batch by check_summation_batch and 25 per-cell checks ran (`detect_duplication`, `grim_check`, `grimmer_check`, `r_sprite_ground_truth`, `rivets_anova`, `sprite_reconstruct`) and report no cell ids.

## Provenance of the analysis

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

5 study/studies, 11 variables, 65 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| pilot | Pilot study: mood manipulation check and effect of mood alone on self-evaluations | rct | 45 | participant | no |
| exp1 | Experiment 1: 2(comparison direction) x 2(shared birthday cue), all in positive mood | rct | 47 | participant | no |
| exp2 | Experiment 2: 2(mood: positive/negative) x 2(direction) x 2(birthday cue) plus a no-mood no-comparison hanging control | rct | 141 | participant | no |
| exp3 | Experiment 3: 2(mood: positive/neutral) x 2(direction) x 2(similarity cue: ambiguous/unambiguous) | rct | 96 | participant | no |
| exp4 | Experiment 4: 2(mood: positive/neutral) x 2(direction) x 2(cognitive load) plus a no-mood no-comparison no-load hanging control | rct | 193 | participant | no |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Self-evaluation (self-rated attractiveness, single item) | ordinal | discrete | 1-7 (integers) | scale points | measured | GRIM, GRIMMER, SPRITE | high |
| Target attractiveness (single item; the direction-of-comparison manipulation check) | ordinal | discrete | 1-7 (integers) | scale points | measured | GRIM, GRIMMER, SPRITE | high |
| Self-reported mood, Experiments 2 and 4 (single item) | ordinal | discrete | 1-7 (integers) | scale points | measured | GRIM, GRIMMER, SPRITE | high |
| Mood index, pilot study (mean of four 9-point bipolar items) | ordinal | continuous | 1-9 | scale points | mean of items (k=4): four nine-point bipolar items (negative/positive mood; sad/happy; unpleasant/pleasant; bad/good), averaged, Cronbach's alpha = .91 | none -- composite granularity is 1/(items x n) | high |
| Self-evaluation index, pilot study (mean of three 9-point items) | ordinal | continuous | 1-9 | scale points | mean of items (k=3): self-ratings of intelligent, competent, successful on nine-point Likert scales, averaged, Cronbach's alpha = .71 | none -- composite granularity is 1/(items x n) | high |
| Self-reported mood, Experiment 3 | ordinal | unknown | not stated | scale points | measured | none -- variable not typed | low |
| Similarity index, Experiment 3 (mean of three 9-point items) | ordinal | continuous | 1-9 | scale points | mean of items (k=3): similarity in general; special bond; similarity in aesthetic preferences, each 1-9, averaged (alpha = .87) | none -- composite granularity is 1/(items x n) | high |
| Mood condition | nominal | discrete | positive; negative; neutral/control | - | measured | percentage GRIM on cell counts | high |
| Direction of comparison | nominal | discrete | upward (more attractive target); downward (less attractive target) | - | measured | DEBIT; percentage GRIM | high |
| Similarity cue | nominal | discrete | shared birthday / ambiguous; different birthday / unambiguous | - | measured | DEBIT; percentage GRIM | high |
| Cognitive load | nominal | discrete | load (rehearse 8-digit number); no load | - | measured | DEBIT; percentage GRIM | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Pilot study, para 2 | one_way_anova | Mood index, pilot study (mean of four 9-point bipolar items) (likert_composite) | Mood condition | 45 | none | none reported |
| Pilot study, para 2 | independent_t | Mood index, pilot study (mean of four 9-point bipolar items) (likert_composite) | - | 45 | none | none reported |
| Pilot study, para 2 | independent_t | Mood index, pilot study (mean of four 9-point bipolar items) (likert_composite) | - | 45 | none | none reported |
| Pilot study, para 3 | one_way_anova | Self-evaluation index, pilot study (mean of three 9-point items) (likert_composite) | Mood condition | 45 | none | none reported |
| Experiment 1, Manipulation check | one_way_anova | Target attractiveness (single item; the direction-of-comparison manipulation check) (likert_item) | Direction of comparison | 47 | none | none reported |
| Experiment 1, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | Similarity cue | 47 | none | none reported |
| Experiment 1, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | Similarity cue, Direction of comparison | 47 | none | none reported |
| Experiment 1, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | Direction of comparison | 47 | none | none reported |
| Experiment 2, Manipulation check | one_way_anova | Self-reported mood, Experiments 2 and 4 (single item) (likert_item) | Mood condition | 141 | none | none reported |
| Experiment 2, Manipulation check | independent_t | Self-reported mood, Experiments 2 and 4 (single item) (likert_item) | - | 141 | none | none reported |
| Experiment 2, Manipulation check | independent_t | Self-reported mood, Experiments 2 and 4 (single item) (likert_item) | - | 141 | none | none reported |
| Experiment 2, Manipulation check | one_way_anova | Target attractiveness (single item; the direction-of-comparison manipulation check) (likert_item) | Direction of comparison | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | Mood condition, Direction of comparison, Similarity cue | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | 126 | none | none reported |
| Experiment 2, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | 126 | none | none reported |
| Experiment 2, Positive mood | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 2, Positive mood | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 2, Positive mood | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 2, Positive mood (contrast vs control) | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 2, Positive mood (contrast vs control) | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 2, Positive mood (contrast vs control) | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 2, Positive mood (contrast vs control) | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 2, Negative mood | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 3, Manipulation check | one_way_anova | Self-reported mood, Experiment 3 (unknown) | Mood condition | 96 | none | none reported |
| Experiment 3, Manipulation check | one_way_anova | Target attractiveness (single item; the direction-of-comparison manipulation check) (likert_item) | Direction of comparison | 96 | none | none reported |
| Experiment 3, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | 96 | none | none reported |
| Experiment 3, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | 96 | none | none reported |
| Experiment 3, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | 96 | none | none reported |
| Experiment 3, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | 96 | none | none reported |
| Experiment 3, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | 96 | none | none reported |
| Experiment 3, Similarity cue and mood effects on responses | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 3, Similarity cue and direction of comparison effects | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Similarity index, Experiment 3 (mean of three 9-point items) (likert_composite) | - | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Similarity index, Experiment 3 (mean of three 9-point items) (likert_composite) | - | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Similarity index, Experiment 3 (mean of three 9-point items) (likert_composite) | - | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Similarity index, Experiment 3 (mean of three 9-point items) (likert_composite) | - | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Similarity index, Experiment 3 (mean of three 9-point items) (likert_composite) | - | 96 | none | none reported |
| Experiment 3, Perceptions of similarity (planned comparison) | one_way_anova | Similarity index, Experiment 3 (mean of three 9-point items) (likert_composite) | - | ? | none | none reported |
| Experiment 3, Perceptions of similarity (planned comparison) | one_way_anova | Similarity index, Experiment 3 (mean of three 9-point items) (likert_composite) | - | ? | none | none reported |
| Experiment 3, Perceptions of similarity (planned comparison) | one_way_anova | Similarity index, Experiment 3 (mean of three 9-point items) (likert_composite) | - | ? | none | none reported |
| Experiment 3, Perceptions of similarity (planned comparison) | one_way_anova | Similarity index, Experiment 3 (mean of three 9-point items) (likert_composite) | - | ? | none | none reported |
| Experiment 3, Perceptions of similarity | pearson_correlation | Self-evaluation (self-rated attractiveness, single item) (likert_item) | Target attractiveness (single item; the direction-of-comparison manipulation check) | ? | none | none reported |
| Experiment 3, Perceptions of similarity | pearson_correlation | Self-evaluation (self-rated attractiveness, single item) (likert_item) | Target attractiveness (single item; the direction-of-comparison manipulation check) | ? | none | none reported |
| Experiment 3, Perceptions of similarity | pearson_correlation | Similarity index, Experiment 3 (mean of three 9-point items) (likert_composite) | Target attractiveness (single item; the direction-of-comparison manipulation check) | ? | none | none reported |
| Experiment 4, Manipulation check | one_way_anova | Self-reported mood, Experiments 2 and 4 (single item) (likert_item) | Mood condition | ? | none | none reported |
| Experiment 4, Manipulation check | one_way_anova | Target attractiveness (single item; the direction-of-comparison manipulation check) (likert_item) | Direction of comparison | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | Cognitive load, Mood condition, Direction of comparison | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 4, Self-evaluations | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 4, No load conditions | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 4, No load conditions | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 4, No load conditions | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 4, No load conditions | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 4, Cognitive load conditions | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 4, Cognitive load conditions | independent_t | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 4, Cognitive load conditions | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |
| Experiment 4, Cognitive load conditions | one_way_anova | Self-evaluation (self-rated attractiveness, single item) (likert_item) | - | ? | none | none reported |

#### Variable/test mismatches

A parametric test is applied to an outcome this analysis typed as non-continuous. That is not proof of an error -- the typing may be wrong, and some parametric tests are robust -- but each pair below should be checked against the paper.

- **Pilot study, para 2**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Mood index, pilot study (mean of four 9-point bipolar items)** is typed `likert_composite`.
- **Pilot study, para 2**: `independent_t` assumes a continuous, roughly normal outcome, but **Mood index, pilot study (mean of four 9-point bipolar items)** is typed `likert_composite`.
- **Pilot study, para 2**: `independent_t` assumes a continuous, roughly normal outcome, but **Mood index, pilot study (mean of four 9-point bipolar items)** is typed `likert_composite`.
- **Pilot study, para 3**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation index, pilot study (mean of three 9-point items)** is typed `likert_composite`.
- **Experiment 1, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Target attractiveness (single item; the direction-of-comparison manipulation check)** is typed `likert_item`.
- **Experiment 1, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 1, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 1, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 2, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-reported mood, Experiments 2 and 4 (single item)** is typed `likert_item`.
- **Experiment 2, Manipulation check**: `independent_t` assumes a continuous, roughly normal outcome, but **Self-reported mood, Experiments 2 and 4 (single item)** is typed `likert_item`.
- **Experiment 2, Manipulation check**: `independent_t` assumes a continuous, roughly normal outcome, but **Self-reported mood, Experiments 2 and 4 (single item)** is typed `likert_item`.
- **Experiment 2, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Target attractiveness (single item; the direction-of-comparison manipulation check)** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 2, Positive mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 2, Positive mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 2, Positive mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 2, Positive mood (contrast vs control)**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 2, Positive mood (contrast vs control)**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 2, Positive mood (contrast vs control)**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 2, Positive mood (contrast vs control)**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 2, Negative mood**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 3, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Target attractiveness (single item; the direction-of-comparison manipulation check)** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 3, Similarity cue and mood effects on responses**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 3, Similarity cue and direction of comparison effects**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index, Experiment 3 (mean of three 9-point items)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index, Experiment 3 (mean of three 9-point items)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index, Experiment 3 (mean of three 9-point items)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index, Experiment 3 (mean of three 9-point items)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index, Experiment 3 (mean of three 9-point items)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity (planned comparison)**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index, Experiment 3 (mean of three 9-point items)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity (planned comparison)**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index, Experiment 3 (mean of three 9-point items)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity (planned comparison)**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index, Experiment 3 (mean of three 9-point items)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity (planned comparison)**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Similarity index, Experiment 3 (mean of three 9-point items)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `pearson_correlation` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 3, Perceptions of similarity**: `pearson_correlation` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 3, Perceptions of similarity**: `pearson_correlation` assumes a continuous, roughly normal outcome, but **Similarity index, Experiment 3 (mean of three 9-point items)** is typed `likert_composite`.
- **Experiment 4, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-reported mood, Experiments 2 and 4 (single item)** is typed `likert_item`.
- **Experiment 4, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Target attractiveness (single item; the direction-of-comparison manipulation check)** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 4, No load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 4, No load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 4, No load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 4, No load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 4, Cognitive load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 4, Cognitive load conditions**: `independent_t` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 4, Cognitive load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.
- **Experiment 4, Cognitive load conditions**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness, single item)** is typed `likert_item`.

_65 of 65 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. Control-condition mean and SD in Experiment 4 unreconstructable from any whole-number sample  [IMPOSSIBLE | confidence: high]

**In plain terms.** The comparison group in the fourth experiment is described as averaging 4.20 out of 7 with the individual answers falling within about 0.21 of that. Since people could only pick whole numbers, their answers cannot bunch that tightly around 4.20; the tightest possible is roughly double. Two separate pieces of software, one of them the standard published tool for this check, agree that no group of people answering that question could have produced these two numbers. Every result in that experiment is stated as a comparison against this group.

- **Location:** Experiment 4, 'No load conditions' and 'Cognitive load conditions' (the same control statistics printed twice)
- **Reported:** M = 4.20, SD = .21 for the no-mood, no-comparison, no-load hanging control, on the single-item seven-point self-attractiveness rating carried over from Experiments 1 and 2.
- **Computed:** SPRITE returns no_solution_proven at n = 15 and n = 30; the sweep additionally proved infeasibility at n = 20 and n = 60. R's rsprite2 independently returns infeasible=true, and does so even when the scale is widened to 1-9, so the result does not depend on the scale bound at all. At n = 15 the only whole-number total consistent with a mean of 4.20 is 63, and no integer sum-of-squares of the required parity falls in the window [265.19, 265.25] implied by SD = 0.21. The smallest SD attainable for an integer mean of exactly 4.20 is approximately 0.41.
- **As printed in the paper:** “Higher levels of self-evaluations relative to the control condition (M = 4.20, SD = .21) were found” _(found in the paper's text)_
- **Assumptions:** That the self-evaluation measure is the single whole-number item the paper describes ('How attractive are you?'), which Experiment 4 states by explicit cross-reference to Experiments 1 and 2. The control group's size is not printed; the finding does not depend on it, having been tested at four values. No scale bound is required.
- **Consequence:** 8 stated claims affected -- All eight of Experiment 4's self-evaluation contrasts are tested against this control mean, so the paper's mechanistic conclusion -- that cognitive load abolishes self-serving reinterpretation -- is computed against a baseline that cannot exist. (asserted, not computed)
- **Reproduce:** `metascience sprite --mean 4.2 --sd 0.21 --n 15 --scale-min 1 --scale-max 7 --decimals-mean 2 --decimals-sd 2 --data-type likert`

### 2. Two Table 2 self-evaluation cells impossible at the cell size the paper's own design fixes  [IMPOSSIBLE | confidence: high]

**In plain terms.** Two of the eight groups in the third experiment report averages and spreads that no twelve people answering a whole-number question could have produced. Unlike most such checks, the group size here is not a guess -- the paper's stated total of 96 people split evenly across eight groups fixes it at twelve. These two groups are the comparison condition for that experiment's central claim, that the effect only appears when the information is ambiguous.

- **Location:** Table 2, Self-evaluation row, Positive/Unambiguous/Upward and Positive/Unambiguous/Downward columns (Experiment 3)
- **Reported:** 6.58 (.52) and 4.08 (.52), among eight cells of twelve participants each.
- **Computed:** GRIMMER returns impossible for both cells at n = 12. Both means pass the granularity check (candidate integer totals 79 and 49 respectively), so the failure is in the SD: no integer sum-of-squares of the required parity yields an SD rounding to 0.52. Re-run at scale 1-9 as well as 1-7, both cells remain impossible, so the finding survives the alternative scale reading Experiment 3 raises elsewhere. The sweep independently confirmed both with R's rsprite2. Denominator: 24 checks over the eight self-evaluation cells produced 4 impossible results and 20 consistent ones.
- **As printed in the paper:** “Self-evaluation ... 6.58 (.52) 4.08 (.52)” _(found in the paper's text, across an ellipsis)_
- **Assumptions:** That the cell size is 12. This is fixed rather than inferred: the paper states N = 96, states a balanced 2x2x2 design, and reports df_error = 88, which is 96 minus 8 cells. That the self-evaluation item is a single whole-number rating, which the paper states by cross-reference. No scale bound is needed -- the result holds at both 1-7 and 1-9.
- **Consequence:** 2 stated claims affected -- Both cells sit in the unambiguous-cue condition that Experiment 3 uses as its comparison baseline for the claim that self-serving responding requires ambiguity. (asserted, not computed)
- **Reproduce:** `metascience grimmer --mean 6.58 --sd 0.52 --n 12 --scale-min 1 --scale-max 7 --decimals 2 --decimals-sd 2 --data-type likert`

### 3. Experiment 3 target-attractiveness mean of 7.33 above the seven-point maximum the paper cross-references  [HIGHLY SUSPICIOUS | confidence: medium]

**In plain terms.** Experiment 3 reports an average rating of 7.33 on what it describes as a scale running from 1 to 7 -- an average cannot exceed the top of its own scale. The most likely innocent explanation is that this experiment actually used a nine-point scale and the methods section describes it wrongly, which would also explain the identical value 7.33 reported two sentences earlier for a different measure. Either way, one of the two statements is incorrect, and the paper does not say which.

- **Location:** Experiment 3, Manipulation check
- **Reported:** "the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001"
- **Computed:** GRIM with bound_source=stated returns failure_mode 'out_of_range': the granularity is fine (352/48 = 7.3333 rounds back to 7.33) but the implied total of 352 exceeds the maximum possible total of 336 for 48 whole-number responses on a 1-7 scale. No sample size rescues it. Separately, rivets_anova confirms the reported F of 170.34 is internally consistent with the two printed means and SDs -- so the F reconciles with a number that cannot be a mean of the stated scale.
- **As printed in the paper:** “the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001” _(found in the paper's text)_
- **Assumptions:** Downgraded from the sweep's 'impossible' deliberately. The seven-point bound reaches Experiment 3 only by cross-reference -- 'rated their own attractiveness (on the seam [same] measures used in Experiments 1 and 2)', where both those experiments define a seven-point target-attractiveness scale. Two things weaken a hard call: the target-rating sentence that follows does not restate the scale, and the immediately preceding paragraph reports the mood check as M = 7.33 as well, so a nine-point reading would reconcile both values at once. Either the mean is wrong or the description of the scale is wrong; the arithmetic cannot say which.
- **Consequence:** changes no significance decision; 1 stated claim affected -- Affects Experiment 3's direction-of-comparison manipulation check, which licenses reading the whole experiment as an upward-versus-downward comparison; the check is significant under either reading of the scale. (asserted, not computed)
- **Reproduce:** `metascience grim --mean 7.33 --n 48 --scale-min 1 --scale-max 7 --decimals 2 --data-type likert --bound-source stated`

### 4. Six Experiment 4 cell means unreconstructable at both candidate cell sizes  [HIGHLY SUSPICIOUS | confidence: medium]

**In plain terms.** Six of the eight group averages in the fourth experiment cannot be produced by any set of whole-number answers, at either of the two group sizes the paper's own statistics imply. This check is less certain than the others because the paper never prints how many people were in each group -- the sizes had to be worked back from the analysis, and those workings conflict with the total the paper states. If the groups were substantially larger than they appear, some of these averages could be genuine.

- **Location:** Experiment 4, 'No load conditions' and 'Cognitive load conditions' (prose cell statistics)
- **Reported:** 5.64 (.78), 5.15 (.81), 5.47 (.51), 3.24 (1.09), 3.09 (.94) and 5.53 (.87), among eight factorial cells.
- **Computed:** GRIMMER over the eight cells returns 19 impossible of 24 checks at n = 15 and 20 of 24 at n = 14; six cells fail at both candidate sizes. Two further cells, 5.71 (.83) and 3.33 (1.05), pass at one size only.
- **As printed in the paper:** “upwardly compared (M = 5.64, SD = .78; F(1,124) = 17.39, p < .001) or downwardly compared (M = 5.15, SD = .81)” _(found in the paper's text)_
- **Assumptions:** Cell size is derived, not printed. It rests on a factorial N of 118 implied by df_error = 110 across eight cells, giving 14 or 15 per cell. That derived N is itself contradicted by the paper's stated N = 193 (see the sample-size finding), and the two cannot both be right. If the true cells held roughly 22-23 participants, this check would have far less power and these values might be reconstructable. The finding is therefore conditional on the reported degrees of freedom being correct.
- **Consequence:** 6 stated claims affected -- These six cells carry the whole of Experiment 4's cognitive-load moderation claim, the paper's mechanistic conclusion. (asserted, not computed)
- **Reproduce:** `metascience grimmer --mean 5.15 --sd 0.81 --n 15 --scale-min 1 --scale-max 7 --decimals 2 --decimals-sd 2 --data-type likert`

### 5. Four further single-item cell means unreconstructable at both candidate cell sizes in Experiments 1 and 2  [HIGHLY SUSPICIOUS | confidence: medium]

**In plain terms.** Four more group averages, in the first two experiments, cannot have come from whole-number answers at either group size the paper's statistics allow. One of them is the single result on which the first experiment's main conclusion rests. As with the fourth experiment, the group sizes had to be reconstructed because the paper never prints them, so these are strong signals rather than certainties.

- **Location:** Table 1, Self-evaluation row (Experiment 2), three cells; and Experiment 1, Self-evaluations, shared-birthday/upward cell
- **Reported:** Table 1: 3.17 (.98), 3.07 (.62) and 5.35 (.70). Experiment 1: "asymmetric assimilation towards the upward comparison target (M = 5.08, SD = .52)".
- **Computed:** For Table 1, GRIMMER over the eight cells returns 18 impossible of 24 checks at n = 16 and 13 of 24 at n = 15; three cells fail at both. For Experiment 1, SPRITE returns no_solution_proven at n = 12 and GRIM failure at n = 11, so the pair is unreconstructable at both; R's rsprite2 independently returns infeasible=true at n = 12.
- **As printed in the paper:** “Self-evaluation 5.25 (.93) 5.53 (.52) 3.17 (.98) 5.13 (.72) 3.33 (.90) 5.20 (.68) 3.07 (.62) 5.35 (.70)” _(found in the PDF text layer)_
- **Assumptions:** Neither experiment prints cell sizes. Experiment 2's factorial N of 126 is implied by df_error = 118 across eight cells and reconciles exactly with the stated N = 141 once the df-implied control of 15 is added, giving cells of 15 or 16. Experiment 1's N = 47 across four cells (df_error = 43 confirms four) gives 11 or 12. Only cells failing under both candidates are reported. A markedly unbalanced allocation, which the paper does not report, would weaken these results.
- **Consequence:** 4 stated claims affected -- The Experiment 1 cell is the one carrying that experiment's headline claim of assimilation to an upward target under a shared-birthday cue, and two of the three Table 1 cells carry Experiment 2's claim that negative mood produces symmetric contrast. (asserted, not computed)
- **Reproduce:** `metascience grimmer --mean 3.17 --sd 0.98 --n 15 --scale-min 1 --scale-max 7 --decimals 2 --decimals-sd 2 --data-type likert`

### 6. Experiment 4's claim of an identical response pattern contradicted by the means printed in the same sentence  [SUSPICIOUS | confidence: high]

**In plain terms.** The fourth experiment's key conclusion is that when people are mentally taxed, those in a good mood stop responding self-servingly and start behaving like everyone else. The sentence stating this describes two groups as showing an identical pattern -- but the numbers printed inside that same sentence show the opposite patterns, each one described backwards relative to the comparison group's score of 4.20. Two numbers appear to have been swapped. Until the authors say which is correct, the experiment's conclusion is not supported by the numbers offered for it.

- **Location:** Experiment 4, Cognitive load conditions
- **Reported:** "upward comparison led to more positive self-ratings (M = 5.71, SD = .83) ... and downward comparison led to less positive self-ratings (M = 3.09, SD = .94) ... This pattern was identical to the neutral mood condition, in which upward comparison led to more positive self-ratings (M = 3.33, SD = 1.05) ... and downward comparison led to less positive self-ratings (M = 5.53, SD = .87), relative to the control condition." The control mean is 4.20.
- **Computed:** No forensic tool covers a contradiction between prose and the numbers beside it; this is a direct reading of four printed means against the printed control mean of 4.20. The value called 'more positive' than the 4.20 control is 3.33, which is lower; the value called 'less positive' is 5.53, which is higher. The two conditions the paper calls identical are exactly inverted: positive-mood-under-load runs 5.71 up / 3.09 down, neutral-mood-under-load runs 3.33 up / 5.53 down. The three parallel comparisons elsewhere in Experiment 4 (positive no-load 5.64/5.15, neutral no-load 5.47/3.24, positive load 5.71/3.09) all describe their means correctly, so this is not a labelling convention.
- **As printed in the paper:** “This pattern was identical to the neutral mood condition, in which upward comparison led to more positive self-ratings (M = 3.33, SD = 1.05), F(1,124) = 18.83, p < .001, and downward comparison led to less positive self-ratings (M = 5.53, SD = .87), F(1,124) = 7.84, p = .006, relative to the control condition.” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own statements. The sweep confirmed the sentence reads identically in the XML and in the PDF version of record, so it is not an extraction artefact.
- **Consequence:** 1 stated claim affected -- Experiment 4's mechanistic conclusion is that cognitive load makes positive-mood participants behave like neutral-mood participants; the printed means make those two conditions opposite rather than identical. (asserted, not computed)
- **Reproduce:** no runnable command -- the review did not supply a command here. The finding's own numbers are above; re-derive from those.

### 7. Pilot mood ANOVA F below every value its own group statistics permit  [SUSPICIOUS | confidence: medium]

**In plain terms.** The pilot study's test statistic is smaller than the group averages and spreads printed beside it can produce, under equal group sizes and two unequal ones. The effect it reports would have been larger, not smaller, so this does not change the conclusion that the mood manipulation worked -- but the number does not follow from the numbers given for it.

- **Location:** Pilot study, paragraph 2
- **Reported:** "the mood manipulation significantly affected participant mood, F(2, 42) = 18.44, p < .001", with group means 7.20, 6.15 and 4.98 and SDs .93, .52 and .98.
- **Computed:** RIVETS one-way ANOVA over the rounding intervals of the printed means and SDs gives an achievable F range of [26.01, 26.98] at equal allocation, with the reported 18.44 outside it and zero Monte Carlo hits in 5000 samples. The sweep tested two lopsided allocations as well, 10/25/10 and 19/7/19, giving ranges [22.20, 23.07] and [28.03, 29.05]; the reported F is below all three.
- **As printed in the paper:** “A one-way Analysis of Variance (ANOVA) revealed that the mood manipulation significantly affected participant mood, F(2, 42) = 18.44, p < .001.” _(found in the paper's text)_
- **Assumptions:** Group sizes are not stated. This is a genuine one-way ANOVA on three groups -- df(2, 42) matches N = 45 exactly -- so unlike Experiment 2's manipulation check there is no factorial-residual explanation available. Graded suspicious rather than higher because some extreme unequal allocation not tested might reconcile it, and because the significance decision is unaffected. The tool itself returned highly_suspicious; the downgrade is mine.
- **Consequence:** changes no significance decision; 1 stated claim affected -- Affects the pilot's demonstration that the mood induction worked; the reported F is smaller than the group statistics imply, so the conclusion of a significant effect stands. (asserted, not computed)
- **Reproduce:** `metascience rivets-anova --means '[7.2,6.15,4.98]' --sds '[0.93,0.52,0.98]' --ns '[15,15,15]' --reported-f 18.44 --decimals-mean 2 --decimals-sd 2 --decimals-f 2`

### 8. Two dependent measures named in Table 1's caption reported nowhere in Experiment 2  [SUSPICIOUS | confidence: high]

**In plain terms.** The title above Table 1 says it shows results for three different measures. The table shows one. The other two -- how similar participants rated the comparison person, and whether they used the information to their own benefit -- appear nowhere in that experiment. Either they were measured and not reported, or the table's title was left over from an earlier version.

- **Location:** Table 1 caption versus Table 1 body and Experiment 2 text
- **Reported:** The caption promises "effects ... on self-evaluations, ratings of target similarity, and use of information to benefit the self". The table contains exactly one data row, Self-evaluation.
- **Computed:** Table 1 returns one data row of eight cells in both the XML grid and, per the sweep, the PDF. Neither 'ratings of target similarity' nor 'use of information to benefit the self' appears anywhere in Experiment 2's text or table, and Experiment 2's Dependent measures section never describes a similarity measure, although Experiment 3 does.
- **As printed in the paper:** “Effects of upward (more attractive) versus downward (less attractive) comparisons on self-evaluations, ratings of target similarity, and use of information to benefit the self as a function of mood and shared birthday information” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own statements. This may be a caption inherited from a fuller table that was cut, rather than measures collected and suppressed; the paper gives no way to tell.
- **Consequence:** 2 stated claims affected -- Two dependent measures named in the table's own caption are never reported in Experiment 2, so their results cannot be evaluated at all. (asserted, not computed)
- **Reproduce:** `metascience get-table --xml-path /mnt/c/Users/gregs/agent_for_forensic_metascience/eval/ground_truth/papers/10.1007--s11031-011-9216-y/10.1007--s11031-011-9216-y.xml --table-num 1`

### 9. Two degrees-of-freedom values inconsistent with the designs they are attributed to  [SUSPICIOUS | confidence: medium]

**In plain terms.** Two places in the paper report a technical number that describes how many people went into a test, and in both cases it does not match the design described. Neither changes whether the result is statistically significant, but both suggest the analyses were not all run on the samples the paper describes.

- **Location:** Experiment 1, Self-evaluations; and Experiment 3, Perceptions of similarity
- **Reported:** Experiment 1: "F(1, 46) = 6.95, p = 011" for a simple effect, where every other test in that experiment uses df_error = 43. Experiment 3: three correlations reported as r(24), e.g. "r(24) = .87, p < .001".
- **Computed:** For Experiment 1, N = 47 in a 2x2 design gives df_error = 43; the printed 46 equals N - 1 and corresponds to no error term in the stated design. The p-value is unaffected: F(1,46) = 6.95 gives p = .0114 and F(1,43) = 6.95 gives p = .0116, both printing as .011. For Experiment 3, each correlation is computed within one mood-by-ambiguity combination spanning two cells of twelve, so 24 participants and df = 22; the printed df = 24 implies n = 26.
- **As printed in the paper:** “Exposure to the upward comparison target led to lowered self-evaluations (M = 3.33, SD = .65) compared to the downward comparison target (M = 4.64, SD = 1.50), F(1, 46) = 6.95, p = 011.” _(found in the paper's text)_
- **Assumptions:** That the correlations were computed within a single mood-by-ambiguity combination, which is how the text describes them. The Experiment 3 discrepancy could be a convention slip of reporting n rather than n - 2.
- **Consequence:** changes no significance decision; 4 stated claims affected -- Affects Experiment 1's symmetric-contrast simple effect and the three Experiment 3 correlations used to argue similarity ratings mediate the effect; no significance decision changes. (asserted, not computed)
- **Reproduce:** no runnable command -- the review did not supply a command here. The finding's own numbers are above; re-derive from those.

### 10. Sixty of Experiment 4's stated 193 participants absent from every analysis it reports  [SUSPICIOUS | confidence: high]

**In plain terms.** Experiment 4 says 193 people took part, but the statistics it reports only account for about 133 of them. No dropouts, exclusions or missing data are mentioned anywhere. The other four studies in the paper add up exactly, which is what makes this one stand out rather than looking like a house style. It also means nobody can check that experiment's group averages, because the group sizes depend on which of the two totals is right.

- **Location:** Experiment 4, Participants and design, versus Results and discussion
- **Reported:** "University (N = 193, 103 female) students participated in the study for monetary compensation." The factorial ANOVA reports df_error = 110 and the contrasts against the control report df_error = 124.
- **Computed:** check_summation with tolerance 0: df_error = 110 across eight factorial cells implies 118 participants; df_error = 124 across nine groups implies 133 in total, leaving a control of 15. 118 + 15 = 133, against a stated 193 -- a shortfall of 60. The paper reports no exclusions, attrition or missing data. The same arithmetic reconciles exactly for the other four studies: pilot 42+3 = 45, Experiment 1 43+4 = 47, Experiment 2 126+15 = 141, Experiment 3 eight cells of 12 = 96.
- **As printed in the paper:** “University (N = 193, 103 female) students participated in the study for monetary compensation.” _(found in the paper's text)_
- **Assumptions:** That the reported degrees of freedom correspond to the models the paper describes, which they do in all four other studies. None beyond the paper's own statements.
- **Reproduce:** `metascience summation-batch --rows '[{"values":[118,15],"expected_sum":193,"decimals":0,"decimals_total":0,"tolerance":0,"description":"Experiment 4 df-implied N vs stated N"}]'`

### 11. Data-availability offer with no data deposited  [SUSPICIOUS | confidence: high]

**In plain terms.** A footnote in the third experiment says complete data are available from the first author, but no data accompany the article. Every one of the arithmetic problems in this review could be resolved -- in either direction -- by seeing the actual responses.

- **Location:** Experiment 3, footnote 4
- **Reported:** "Complete data and results available from the first author."
- **Computed:** No supplementary files accompany the record; nothing could be read. Two dependent measures named in Table 1's caption are also never reported.
- **As printed in the paper:** “Complete data and results available from the first author.” _(found in the PDF text layer)_
- **Assumptions:** This records the presence of an availability claim and the absence of deposited data. It is not evidence about the authors' willingness to supply data on request, which was not tested.
- **Reproduce:** no runnable command -- the review did not supply a command here. The finding's own numbers are above; re-derive from those.

### 12. Three of sixty-five reported test statistics inconsistent with their own p-values  [SUSPICIOUS | confidence: high]

**In plain terms.** Three of the paper's sixty-five statistical results do not match the probability values printed beside them. This is an ordinary rate of typographical slippage -- about half of error-free papers have at least one -- and none of the three changes whether a result counts as significant. It is recorded so the reader knows it was checked, not as a criticism.

- **Location:** Whole body text (Pilot and Experiments 1-4)
- **Reported:** "F(1, 94) = 1.50, p = .83" (Experiment 3), "F(1, 42) = .27, p = .76" (Pilot), and "r(24) = .53, p = .008" (Experiment 3).
- **Computed:** statcheck over all 65 NHST results recomputes p = .2237, .6061 and .0054 respectively; zero decision errors. Two have benign explanations: rivets_anova independently confirms the pilot F of .27 reconciles with its group statistics and yields p = .757 once the numerator df is read as 2 rather than 1, which the three-group design requires; and .83 for F = 1.50 may be a transposition of .23. The paper also prints two malformed p-values, 'p = 011' and 'p = 001', normalised to .011 and .001 for the run.
- **As printed in the paper:** “Identical effects emerged when the information was unambiguous, F(1, 94) = 1.50, p = .83.” _(found in the paper's text)_
- **Assumptions:** Three out of sixty-five is a low rate and unremarkable on its own -- roughly half of clean control papers contain at least one such mismatch. Reported for completeness rather than as a substantive charge.
- **Consequence:** changes no significance decision -- None of the three inconsistencies crosses the paper's significance threshold, so no reported conclusion changes. None of the three inconsistencies crosses alpha, so no reported conclusion changes; all three affected results are non-significant or already significant either way. Computed from 0 statistic(s) whose recomputed p crosses the paper's alpha. (computed)
- **Reproduce:** `metascience statcheck --pdf-path /mnt/c/Users/gregs/agent_for_forensic_metascience/eval/ground_truth/papers/10.1007--s11031-011-9216-y/10.1007--s11031-011-9216-y.pdf`

### 13. Repeated summary values across independent samples, below the threshold at which duplication checking flags them  [INDETERMINATE | confidence: low]

**In plain terms.** Several numbers recur across studies that used different people and different questionnaires -- most noticeably, the three spread values from the pilot study reappear in the same order in the first three columns of Experiment 2's table. The automated check for copied statistics found nothing, because it looks for averages and spreads matching together and here only the spreads match. This is an observation, not a finding: repeated values happen by chance, and I could not measure how likely this particular coincidence is.

- **Location:** Pilot study versus Table 1 (Experiment 2); Experiment 3 Manipulation check; Table 2 Similarity row
- **Reported:** The pilot's three mood-condition SDs are .93, .52 and .98; Table 1's first three self-evaluation SDs are .93, .52 and .98, in the same order. Separately: two attractiveness SDs identical at 1.19 in one sentence; two Table 2 similarity means identical at 6.81; two pilot self-evaluation means identical at 6.98; the value 7.33 reported for two different Experiment 3 measures; and the control mean of exactly 4.20 in both Experiment 2 and Experiment 4.
- **Computed:** detect_duplication over 1407 cross-source comparisons of 58 (mean, SD) cells found zero identical pairs between independent samples; three flagged items were digit transpositions between 5.35 and 5.53, which is weak. Re-run in stage 2 on the pilot and Table 1 blocks specifically, it again returned consistent with zero identical pairs, because it matches mean-and-SD together and only the SDs coincide. The SD-sequence observation therefore has NO tool backing and is recorded as a reading.
- **Assumptions:** Repeated values are ordinary in small samples and prove nothing on their own (rulebook rule 8). The pilot and Experiment 2 involve different participants and different measures on different scales -- a four-item nine-point composite versus a single seven-point item -- which is what makes three SDs coinciding in sequence worth noting, but I could not quantify how improbable it is with any validated tool.
- **Consequence:** changes no significance decision -- No claim depends on this; it is recorded as a weak corroborating pattern and as a record of what duplication checking ruled out. (asserted, not computed)
- **Reproduce:** `metascience duplication-detect --blocks '[{"label":"Pilot mood by condition","sample_id":"pilot","independent":true,"cells":[{"label":"positive","value":7.2,"sd":0.93},{"label":"control","value":6.15,"sd":0.52},{"label":"negative","value":4.98,"sd":0.98}]},{"label":"Exp 2 Table 1 first three cells","sample_id":"exp2","independent":true,"cells":[{"label":"pos/same/up","value":5.25,"sd":0.93},{"label":"pos/same/down","value":5.53,"sd":0.52},{"label":"pos/diff/up","value":3.17,"sd":0.98}]}]' --decimals-mean 2 --decimals-sd 2`

## What we could NOT check

- **Table 2, Similarity row (8 cells)** — The similarity index is a mean of three nine-point items, so it moves in steps of 1/(3n) rather than 1/n, and the granularity tools have no items parameter. Running them with 1/n would manufacture impossibilities, and hand-checking the 1/36 granularity would be unvalidated arithmetic.
- **Pilot study mood and self-evaluation means (six values)** — Both are means of multi-item composites (four nine-point items and three nine-point items), so the granularity tools do not apply for the same reason. The ANOVAs computed from them were checked with rivets_anova instead.
- **Figures 1, 2 and 3** — Neither data figure carries values absent from the text: Figure 2 replots Table 2's self-evaluation row and Figure 3 replots Experiment 4's prose cell means, all checked directly. No error-bar meaning is stated in either caption, so no dispersion could have been read off them in any case.
- **Experiment 2 contrast tests reported with df_error = 124 (four tests)** — The error df of 124 corresponds to neither the factorial model (118) nor the contrast model (132) used elsewhere in the same experiment. Without knowing which sub-model produced it, the group sizes could not be reconstructed, so these F values were left unverified rather than checked against a guessed model.
- **Per-group sample sizes throughout** — The paper prints no cell sizes anywhere. Every n used here except Experiment 3's was derived from reported degrees of freedom and the stated design; where two candidates were possible, checks were run at both and only results failing under both are reported.
- **Supplementary materials** — None were provided with the paper. Footnote 4 states 'Complete data and results available from the first author', but no data file accompanies the record. This is 'not provided', distinct from 'present but unreadable'.
- **Effect-size plausibility benchmarking** — check_effect_plausibility was not run. The paper reports no effect sizes, several key contrasts lack dispersion, and the group statistics that do exist are themselves the object of the impossibility findings; benchmarking an effect computed from values that no integer sample can produce would not be informative.
- **Table 1 footnote giving Experiment 2's control statistics** — The XML extraction reported zero footnotes for Table 1; the sweep recovered the footnote (M = 4.20, SD = .86) from the PDF. All 24 table cell values agreed exactly between the two sources, but a reader working from the XML alone would have missed these control statistics entirely. Recorded against the extraction tooling, not the authors.

## Questions for the authors

_Each of these is answerable from what the authors already have. None presupposes an error on their part: an inconsistency is far more often a reporting slip, or a mistake by this tool in reading the number off the page, than anything else._

1. Experiment 4 reports the hanging control condition twice as M = 4.20, SD = .21 on the single seven-point self-attractiveness item. For whole-number responses averaging exactly 4.20, the smallest attainable standard deviation is about 0.41 at any sample size. Could you confirm the control group's size and the standard deviation as computed, or supply the individual responses?
   <sub>Would resolve: This is the paper's strongest arithmetic contradiction and it is the baseline for all eight of Experiment 4's contrasts. Only the raw responses or a corrected value can settle it.</sub>
2. Experiment 4 states N = 193, but df_error = 110 for the factorial ANOVA implies 118 participants across the eight cells and df_error = 124 for the contrasts implies 133 in total. Were participants excluded, and if so how many and on what grounds? The pilot and Experiments 1-3 all reconcile exactly against their stated Ns.
   <sub>Would resolve: Sixty participants, roughly a third of the stated sample, are unaccounted for, and the ambiguity blocks any verification of Experiment 4's cell statistics.</sub>
3. In the cognitive-load section of Experiment 4, the neutral-mood upward condition is described as 'more positive' with M = 3.33 and the downward condition as 'less positive' with M = 5.53, against a control of M = 4.20; the pattern is then called identical to the positive-mood condition, which runs 5.71 upward and 3.09 downward. Have these two means been transposed?
   <sub>Would resolve: As printed, the two conditions the paper calls identical are exactly inverted, which is the comparison Experiment 4's mechanistic conclusion depends on.</sub>
4. Table 2 reports the Positive/Unambiguous/Upward and Positive/Unambiguous/Downward self-evaluation cells as 6.58 (.52) and 4.08 (.52). With twelve participants per cell -- as N = 96 across a balanced 2x2x2 design and df_error = 88 imply -- neither mean and standard deviation can arise from whole-number responses, on either a seven-point or a nine-point scale. Could you confirm the cell sizes and these two standard deviations?
   <sub>Would resolve: This is the only impossibility in the paper whose group size is fixed by stated values rather than derived, and both cells sit in Experiment 3's baseline condition.</sub>
5. Experiment 3 reports an upward-target attractiveness mean of 7.33 and describes the measure as 'the seam [same] measures used in Experiments 1 and 2', both of which specify a seven-point scale; the mood check in the preceding paragraph also reports 7.33. Which scale range was used for attractiveness and for mood in Experiment 3?
   <sub>Would resolve: A mean of 7.33 cannot arise on a 1-7 scale, but a nine-point scale would reconcile both values at once; only the authors can say which statement is the erroneous one.</sub>
6. Table 1's caption describes effects on 'self-evaluations, ratings of target similarity, and use of information to benefit the self', but the table contains only a Self-evaluation row and neither of the other two measures appears anywhere in Experiment 2. Were target similarity and use of information collected in Experiment 2, and if so are those results available?
   <sub>Would resolve: Distinguishes a caption left over from an earlier draft from measures collected but not reported.</sub>

## Limitations

- This agent reads text and tables only. It does not see figures: Figures 1, 2 and 3 were not read, and any value appearing only in their artwork was not checked.
- No cell sizes are printed anywhere in the paper. Except in Experiment 3, where N = 96 and a stated balanced 2x2x2 design fix the cells at 12, every group size used here was derived from reported degrees of freedom. Findings resting on a derived n are graded highly_suspicious rather than impossible for that reason, and each names its candidate sizes.
- Experiment 4's cell-level findings are conditional in a way the others are not: they rest on a factorial N of 118 implied by df_error = 110, and that derived N is contradicted by the paper's own stated N = 193. Both cannot be right, and the paper offers no basis for choosing.
- The seven-point scale bound for Experiment 3 reaches that experiment only through a cross-reference to Experiments 1 and 2. The out-of-range finding for the mean of 7.33 is graded accordingly and is not the headline.
- The observation that the pilot's three SDs recur in order in Table 1 has no validated tool behind it. The duplication check, run twice, returned no identical mean-and-SD pairs; it is recorded as a reading, not a result.
- The article is published as retracted, and the second author's corpus was retracted following the 2011 Levelt investigations. No finding in this review rests on that fact; every one was derived from the printed numbers alone.
- No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.

## Coverage

- **Statistics found:** 65; **checked:** 65
- **Tools run:** extract_xml, get_table, parse_cells_typed, check_table, statcheck, grim_check, grimmer_check, sprite_reconstruct, r_sprite_ground_truth, rivets_anova, detect_duplication, check_summation_batch, multiplicity_report, extract_figures, extract_pdf
- **Tables checked:** Table 1 (Experiment 2, self-evaluation, 8 cells), Table 2 (Experiment 3, self-evaluation and similarity, 16 cells), Experiment 1 prose cell means (4 cells, treated as a table), Experiment 4 prose cell means (8 cells, treated as a table)
- **Checkable table cells:** 24 of 24 surveyed; **checked:** 28
    - at least 4 of the cells checked came from outside the tables this census walked -- values read from the prose, a supplement, or a table only the PDF carries. These are two different populations, so no share of one in the other is stated, and this does NOT mean every surveyed cell was checked
    - 24 could not be checked without knowing what kind of quantity the row reports
- **Where a check and this review disagreed:** 4 sweep findings recorded a severity the validated check behind them did not return (0 upgraded, 4 downgraded). 4 are explained downgrades on an entry above, counted here and not marked there: the check said more, this review said less and said why, which is what stage 2 is for.

## What each check does

One entry per check that ran on this paper. The **assumptions** are the conditions under which its verdict holds; where one is unmet the verdict is capped, not merely caveated.

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

### `r_sprite_ground_truth` — descriptive

Cross-checks our SPRITE against R's canonical rsprite2 package.

**What its verdict means.** Descriptive. Extracts, parses or computes a quantity; it does not itself render a verdict about the paper.

**Strongest verdict it may reach:** `indeterminate`

**It assumes:**
- Reports rsprite2's result. A disagreement is a bug in our tooling and the finding must not be reported.

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

## What the paper claims

A pilot study and four between-subjects experiments argue that positive mood lets people reinterpret ambiguous similarity information in whatever direction flatters them: assimilating towards more attractive comparison targets and contrasting away from less attractive ones. Experiment 1 establishes the asymmetry using a shared-birthday cue; Experiment 2 rules out a mood-congruency explanation by showing negative mood does not produce it; Experiment 3 shows the effect requires the similarity cue to be ambiguous; Experiment 4 shows it is abolished by cognitive load, which is the mechanistic conclusion the paper builds towards. Self-evaluation is throughout a single whole-number rating, "How attractive are you?", on a seven-point scale.

## A note on the record, and why it changes nothing here

The article is published as retracted, and the second author's corpus was retracted following the 2011 Levelt, Noort and Drenth investigations. No finding in this review rests on that. Every result below was derived from the printed numbers, and each names whether it depends on a sample size the paper states or one that had to be worked backwards from reported degrees of freedom. The arithmetic was checkable without knowing how the story ended.

## Why the impossibility findings carry the weight they do

Because self-evaluation is a single whole-number item, the printed means and standard deviations are heavily constrained: only certain combinations can arise from any set of responses at all. Two of the paper's combinations cannot arise from any set.

The stronger of the two is Experiment 4's control condition, printed twice as M = 4.20, SD = .21. Whole numbers averaging exactly 4.20 must sit at least as far apart as a mix of 4s and 5s allows, which forces a standard deviation of roughly 0.41 or more. This holds at every sample size, and it does not depend on the scale at all -- I re-ran it at 1-9 as well as 1-7, and against R's `rsprite2`, which is the published reference implementation. Both engines agree no such sample exists. The immediate contrast is Experiment 2's control condition, M = 4.20, SD = .86, which reconstructs cleanly at n = 15. That is the control on the method: the same check, the same scale, the same nominal mean, and one passes.

The second is Table 2. Two cells in the unambiguous-cue condition of Experiment 3, 6.58 (.52) and 4.08 (.52), admit no whole-number sample at twelve per cell -- and twelve is not a guess here. The paper states N = 96, states a balanced 2x2x2 design, and reports df_error = 88, which is 96 minus 8. I re-ran both cells at 1-9 as well as 1-7 in case Experiment 3 used a wider scale than the methods describe, and they fail either way.

Ten further cells across Experiments 1, 2 and 4 fail the same checks, but only at cell sizes reconstructed from degrees of freedom rather than stated. Those are reported one grade lower for that reason, and Experiment 4's are lower again in confidence, because the degrees of freedom they rest on contradict that experiment's own stated N.

## What I dropped or softened from the numeric sweep

Four sweep findings I did not carry forward as defects. The sweep had already downgraded Experiment 2's manipulation-check F of 716.92 to indeterminate, correctly: the tool recomputes a one-way ANOVA while the paper's df_error of 118 comes from the full factorial residual, which accounts for nearly all of the apparent gap. The XML-versus-PDF reconciliation is a gap in our extraction tooling -- the XML dropped Table 1's footnote -- and belongs in limitations, not against the authors. The duplication sweep and the multiplicity check are negative results and are recorded as such: across 1407 comparisons there is not one identical mean-and-SD pair between independent samples, and no Experiment 4 claim is lost to correction for multiple testing. Whatever is wrong here, wholesale copy-paste and undisclosed multiplicity are not it.

Two I softened. The Experiment 3 mean of 7.33 on a stated seven-point scale is graded highly_suspicious rather than impossible: the seven-point bound reaches Experiment 3 only by cross-reference, and the same paragraph reports the mood check at 7.33 too, so a nine-point scale would reconcile both at once. Either the mean or the methods description is wrong; the arithmetic cannot say which, and a finding this contingent should not lead a review. The pilot ANOVA I kept at suspicious rather than the tool's own highly_suspicious, because group sizes are unstated and some extreme allocation I did not test might reconcile it.

One I have handled more carefully than the sweep did. The pilot's three mood SDs -- .93, .52, .98 -- reappear in that exact order as the first three SDs of Table 1, in a different experiment, on different participants, measuring something else on a different scale. The duplication tool does not flag this, because it matches means and SDs together and here only the SDs coincide. I ran it again specifically on those two blocks and it returned nothing. So this is a reading with no tool behind it, and it is recorded at indeterminate. It is not evidence; it is a thing worth asking about.

## The reasoning the sweep could not do

Experiment 4 contradicts itself in the sentence carrying its conclusion. The paper's mechanistic claim is that load makes positive-mood participants behave like neutral-mood ones. The printed means make those two conditions opposite: positive-under-load runs 5.71 upward and 3.09 downward against a control of 4.20, while neutral-under-load runs 3.33 upward and 5.53 downward -- each described backwards relative to the control, in a paragraph that then calls the patterns identical. The three parallel comparisons elsewhere in the same experiment get the arithmetic right, so this is not a labelling convention. Two numbers look transposed. Until that is confirmed, the experiment's conclusion is unsupported by the numbers offered for it -- and it sits on top of a control condition that cannot exist and a sample sixty participants short of the one stated.

Around this: a footnote offers complete data that are not deposited, and Table 1's caption names two dependent measures that appear nowhere in Experiment 2. Both are recoverable by the authors in an afternoon.

Verification coverage was broad -- all 65 reported test statistics, all 24 table cells, and both reported sample-flow reconciliations -- and most of it passed.

## Trust verdict

The two experiments carrying the paper's central mechanistic claims each report at least one summary statistic that no dataset could have produced, and Experiment 4 additionally contradicts its own conclusion and cannot account for a third of its stated sample. I have no confidence in the accuracy of the reported statistics, and the results should not be relied upon without the raw data.

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
errors are near-universal in honest work. Separately, this pipeline's end-to-end
precision on real papers is at or below 1%: the arithmetic is exact, but getting
numbers off a PDF is not, and that is where nearly all of the failure lives. Any
individual flag in this report is therefore much more likely to be our
extraction error than the authors' misconduct.

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
