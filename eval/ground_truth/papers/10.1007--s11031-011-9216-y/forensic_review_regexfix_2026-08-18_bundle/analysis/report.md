# Forensic review -- Johnson et al. 2011

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## RETRACTED ARTICLE: Happiness as alchemy: Positive mood leads to self-serving responses to social comparisons
*Camille S. Johnson, Diederik A. Stapel. Motivation and Emotion. 2011. doi:10.1007/s11031-011-9216-y*

**Design:** Four between-subjects factorial laboratory experiments plus a pilot study; retracted article

<sub>Analysed as `10.1007--s11031-011-9216-y`</sub>

> **IMPOSSIBLE** — Three reported means in this paper cannot have come from the data the paper says it collected: two Table 2 cells whose standard deviations no set of whole-number responses can produce, and a manipulation-check mean of 7.33 on a scale the Method defines as running from 1 to 7.
>
> **In plain terms:** Ratings on these measures were whole numbers from 1 to 7, and that limits which averages and which spreads can actually occur. Two of the paper's reported spreads are not on that list -- no group of twelve people answering whole numbers could produce them. Separately, one reported average is 7.33 on a scale whose highest possible answer is 7, which cannot happen however the twelve people answered.
>
> **Evidence:** Table 2, Self-evaluation row: "6.58 (.52)" and "4.08 (.52)" at n = 12 per cell (N = 96 over eight cells, corroborated by error df = 88). Experiment 3 Manipulation check: "the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001", against Experiment 1's "on a seven-point scale (1 = not at all, 7 = extremely)", which Experiment 3 says it reused.
> **Rests on:** logical necessity (no assumption added)
> **Reproduce:** `metascience grimmer --mean 6.58 --sd 0.52 --n 12 --scale-min 1 --scale-max 7 --decimals 2 --decimals-sd 2 --data-type likert --discreteness-source stated`

**Verdict: does_not_reconcile** (confidence: high)

> **Partial table coverage:** 8 of 24 checkable cells were checked cell by cell. This counts only cells reached through `check_table`; a further 28 per-cell checks ran on values off this paper (`check_effect_plausibility`, `check_sd_or_se`, `detect_duplication`, `grim_check`, `grimmer_check`, `r_sprite_ground_truth`, `recalc_f_to_p`, `rivets_anova`, `sprite_reconstruct`) and report no cell ids, so the remainder is under-counted by an unknown amount.

## Provenance of the analysis

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

5 study/studies, 10 variables, 27 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| pilot | Pilot study: mood manipulation check and self-evaluation baseline | rct | 45 | participant | no |
| exp1 | Experiment 1: positive mood x shared birthday x comparison direction | rct | 47 | participant | no |
| exp2 | Experiment 2: mood (positive/negative) x direction x shared birthday, plus hanging control | rct | 141 | participant | no |
| exp3 | Experiment 3: mood (positive/neutral) x direction x ambiguity of similarity cue | rct | 96 | participant | no |
| exp4 | Experiment 4: mood (positive/neutral) x direction x cognitive load, plus hanging control | rct | 193 | participant | no |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Self-evaluation (self-rated attractiveness) | ordinal | discrete | 1-7 (integers) | - | measured | GRIM, GRIMMER, SPRITE | high |
| Target attractiveness rating | ordinal | discrete | 1-7 (integers) | - | measured | GRIM, GRIMMER, SPRITE | high |
| Self-reported mood (Experiments 2 and 4) | ordinal | discrete | 1-7 (integers) | - | measured | GRIM, GRIMMER, SPRITE | high |
| Mood index (pilot study) | ordinal | discrete | 1-9 (integers) | - | mean of items (k=4): four nine-point bipolar mood items, Cronbach's alpha = .91 | none -- composite granularity is 1/(items x n) | high |
| Self-evaluation index (pilot study) | ordinal | discrete | 1-9 (integers) | - | mean of items (k=3): three nine-point items: intelligent, competent, successful; Cronbach's alpha = .71 | none -- composite granularity is 1/(items x n) | high |
| Perceived similarity index (Experiment 3) | ordinal | discrete | 1-9 (integers) | - | mean of items (k=3): three nine-point similarity questions, alpha = .87 | none -- composite granularity is 1/(items x n) | high |
| Mood condition | nominal | discrete | positive; negative; neutral/control | - | measured | percentage GRIM on cell counts | high |
| Direction of comparison | nominal | discrete | upward (more attractive target); downward (less attractive target) | - | measured | DEBIT; percentage GRIM | high |
| Similarity cue | nominal | discrete | shared birthday; different birthday; ambiguous aesthetic preference; unambiguous aesthetic preference | - | measured | DEBIT; percentage GRIM | high |
| Cognitive load | nominal | discrete | load (hold 8-digit number); no load | - | measured | DEBIT; percentage GRIM | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Pilot study, Results | one_way_anova | Mood index (pilot study) (likert_composite) | Mood condition | 45 | none | none reported |
| Pilot study, Results | independent_t | Mood index (pilot study) (likert_composite) | - | 30 | none | none reported |
| Pilot study, Results | independent_t | Mood index (pilot study) (likert_composite) | - | 30 | none | none reported |
| Pilot study, Results | one_way_anova | Self-evaluation index (pilot study) (likert_composite) | Mood condition | 45 | none | none reported |
| Experiment 1, Manipulation check | one_way_anova | Target attractiveness rating (likert_item) | Direction of comparison | 47 | none | none reported |
| Experiment 1, Self-evaluations | ancova | Self-evaluation (self-rated attractiveness) (likert_item) | Similarity cue | 47 | none | none reported |
| Experiment 1, Self-evaluations | ancova | Self-evaluation (self-rated attractiveness) (likert_item) | Similarity cue, Direction of comparison | 47 | none | none reported |
| Experiment 1, Self-evaluations, unshared birthday | one_way_anova | Self-evaluation (self-rated attractiveness) (likert_item) | Direction of comparison | 24 | none | none reported |
| Experiment 2, Manipulation check | ancova | Self-reported mood (Experiments 2 and 4) (likert_item) | Mood condition | 141 | none | none reported |
| Experiment 2, Manipulation check | independent_t | Self-reported mood (Experiments 2 and 4) (likert_item) | - | ? | none | none reported |
| Experiment 2, Manipulation check | ancova | Target attractiveness rating (likert_item) | Direction of comparison | ? | none | none reported |
| Experiment 2, Self-evaluations | ancova | Self-evaluation (self-rated attractiveness) (likert_item) | Mood condition, Direction of comparison, Similarity cue | ? | none | none reported |
| Experiment 2, Positive mood | ancova | Self-evaluation (self-rated attractiveness) (likert_item) | Direction of comparison, Similarity cue | ? | none | none reported |
| Experiment 2, Negative mood | ancova | Self-evaluation (self-rated attractiveness) (likert_item) | Direction of comparison | ? | none | none reported |
| Experiment 3, Manipulation check | ancova | Self-reported mood (Experiments 2 and 4) (likert_item) | Mood condition | 96 | none | none reported |
| Experiment 3, Manipulation check | ancova | Target attractiveness rating (likert_item) | Direction of comparison | 96 | none | none reported |
| Experiment 3, Self-evaluations | ancova | Self-evaluation (self-rated attractiveness) (likert_item) | Similarity cue, Mood condition | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | ancova | Perceived similarity index (Experiment 3) (likert_composite) | Mood condition, Direction of comparison, Similarity cue | 96 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Perceived similarity index (Experiment 3) (likert_composite) | Direction of comparison | 24 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Perceived similarity index (Experiment 3) (likert_composite) | Direction of comparison | 24 | none | none reported |
| Experiment 3, Perceptions of similarity | one_way_anova | Perceived similarity index (Experiment 3) (likert_composite) | Direction of comparison | 24 | none | none reported |
| Experiment 3, Perceptions of similarity | pearson_correlation | Self-evaluation (self-rated attractiveness) (likert_item) | Target attractiveness rating | 26 | none | none reported |
| Experiment 3, Perceptions of similarity | pearson_correlation | Self-evaluation (self-rated attractiveness) (likert_item) | Target attractiveness rating | 26 | none | none reported |
| Experiment 4, Manipulation check | ancova | Self-reported mood (Experiments 2 and 4) (likert_item) | Mood condition | 193 | none | none reported |
| Experiment 4, Self-evaluations | ancova | Self-evaluation (self-rated attractiveness) (likert_item) | Cognitive load, Mood condition, Direction of comparison | 193 | none | none reported |
| Experiment 4, No load conditions | ancova | Self-evaluation (self-rated attractiveness) (likert_item) | Direction of comparison | ? | none | none reported |
| Experiment 4, Cognitive load conditions | independent_t | Self-evaluation (self-rated attractiveness) (likert_item) | Direction of comparison | ? | none | none reported |

#### Variable/test mismatches

A parametric test is applied to an outcome this analysis typed as non-continuous. That is not proof of an error -- the typing may be wrong, and some parametric tests are robust -- but each pair below should be checked against the paper.

- **Pilot study, Results**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Mood index (pilot study)** is typed `likert_composite`.
- **Pilot study, Results**: `independent_t` assumes a continuous, roughly normal outcome, but **Mood index (pilot study)** is typed `likert_composite`.
- **Pilot study, Results**: `independent_t` assumes a continuous, roughly normal outcome, but **Mood index (pilot study)** is typed `likert_composite`.
- **Pilot study, Results**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation index (pilot study)** is typed `likert_composite`.
- **Experiment 1, Manipulation check**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Target attractiveness rating** is typed `likert_item`.
- **Experiment 1, Self-evaluations**: `ancova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness)** is typed `likert_item`.
- **Experiment 1, Self-evaluations**: `ancova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness)** is typed `likert_item`.
- **Experiment 1, Self-evaluations, unshared birthday**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness)** is typed `likert_item`.
- **Experiment 2, Manipulation check**: `ancova` assumes a continuous, roughly normal outcome, but **Self-reported mood (Experiments 2 and 4)** is typed `likert_item`.
- **Experiment 2, Manipulation check**: `independent_t` assumes a continuous, roughly normal outcome, but **Self-reported mood (Experiments 2 and 4)** is typed `likert_item`.
- **Experiment 2, Manipulation check**: `ancova` assumes a continuous, roughly normal outcome, but **Target attractiveness rating** is typed `likert_item`.
- **Experiment 2, Self-evaluations**: `ancova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness)** is typed `likert_item`.
- **Experiment 2, Positive mood**: `ancova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness)** is typed `likert_item`.
- **Experiment 2, Negative mood**: `ancova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness)** is typed `likert_item`.
- **Experiment 3, Manipulation check**: `ancova` assumes a continuous, roughly normal outcome, but **Self-reported mood (Experiments 2 and 4)** is typed `likert_item`.
- **Experiment 3, Manipulation check**: `ancova` assumes a continuous, roughly normal outcome, but **Target attractiveness rating** is typed `likert_item`.
- **Experiment 3, Self-evaluations**: `ancova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness)** is typed `likert_item`.
- **Experiment 3, Perceptions of similarity**: `ancova` assumes a continuous, roughly normal outcome, but **Perceived similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Perceived similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Perceived similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Perceived similarity index (Experiment 3)** is typed `likert_composite`.
- **Experiment 3, Perceptions of similarity**: `pearson_correlation` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness)** is typed `likert_item`.
- **Experiment 3, Perceptions of similarity**: `pearson_correlation` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness)** is typed `likert_item`.
- **Experiment 4, Manipulation check**: `ancova` assumes a continuous, roughly normal outcome, but **Self-reported mood (Experiments 2 and 4)** is typed `likert_item`.
- **Experiment 4, Self-evaluations**: `ancova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness)** is typed `likert_item`.
- **Experiment 4, No load conditions**: `ancova` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness)** is typed `likert_item`.
- **Experiment 4, Cognitive load conditions**: `independent_t` assumes a continuous, roughly normal outcome, but **Self-evaluation (self-rated attractiveness)** is typed `likert_item`.

_27 of 27 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. Two Table 2 standard deviations cannot arise from whole-number responses, and they are the two halves of one reported contrast  [IMPOSSIBLE | confidence: high]

**In plain terms.** Each person in these two groups gave a single whole-number rating from 1 to 7, so only certain combinations of average and spread are arithmetically possible. For both of these groups the reported spread is not one of them: there is no way twelve people giving whole-number answers could produce that average alongside that spread. The two affected numbers are the two sides of the single comparison this experiment was designed to make, so the comparison cannot be checked and, as printed, cannot be right.

- **Location:** Table 2 (Experiment 3), Self-evaluation row, Positive mood / Unambiguous cue, Upward and Downward columns
- **Reported:** "6.58 (.52)" and "4.08 (.52)". The measure is a single item: "Participants also rated their own attractiveness (How attractive are you?) on a seven-point scale (1 = not at all, 7 = extremely)", which Experiment 3's Procedure says it reused.
- **Computed:** grimmer_check, re-run at this stage on both cells: at n = 12 exactly one integer total is compatible with each mean (79 and 49 respectively), and for neither is there an integer sum-of-squares of the required parity that reproduces an SD rounding to 0.52 at two decimals. Both cells return failure_mode sd_granularity with feasible_ignoring_bounds = false and population_feasible_ignoring_bounds = false, meaning the failure survives under both the sample (n-1) and population (n) SD conventions and does not depend on the scale endpoints at all. Stage 1's SPRITE run returned no_solution_proven on the same two triples.
- **As printed in the paper:** **Table 2, Self-evaluation row, Positive/Unambiguous/Upward** -- “rated their own attractiveness and the target’s attractiveness on seven-point scales (1 = not at all attractive and 7 = extremely attractive)” _(found in the paper's text)_
- **Assumptions:** Two, both named. (1) n = 12 per cell is not printed; it follows from N = 96 over eight cells, is corroborated by the reported error df of 88 (= 96 - 8), and is further corroborated by all eight Self-evaluation cells being GRIM-consistent at exactly n = 12. (2) The value in parentheses is an SD, as Table 2's own caption convention and the rest of the paper indicate. R cross-check caveat, stated plainly: rsprite2 rejected both triples through its own GRIMMER screen with the message "The standard deviation is not consistent with this mean and number of observations", which agrees with our result in substance -- but it did so by raising an exception rather than returning a clean infeasible flag, and our wrapper measures a 16.2% false-raise rate for that path, so the R confirmation is substantive rather than formally clean. The finding therefore rests on our own analytic enumeration, which is a closed-form parity argument rather than a search that could have given up. Extraction was verified: the independently extracted PDF grid reproduces all 16 Table 2 cells identically, and the XML table was flagged neither alignment_uncertain nor image_only.
- **Consequence:** 1 stated claim affected -- The 6.58-versus-4.08 contrast is the paper's evidence that positive-mood participants assimilate to comparison targets when the similarity cue is unambiguous -- the boundary condition Experiment 3 exists to establish -- and both halves of it are individually unreconstructable. (asserted, not computed)
- **Reproduce:** no runnable command -- the review could not produce one that runs. The finding's own numbers are above; re-derive from those.

### 2. Experiment 3 manipulation-check mean of 7.33 exceeds the seven-point ceiling the Method assigns to that measure  [IMPOSSIBLE | confidence: medium]

**In plain terms.** The paper says people rated attractiveness on a scale where 7 is the highest possible answer, and Experiment 3 says it used that same scale. It then reports an average of 7.33, which is higher than the highest answer anyone could have given. Either the number is wrong or the paper has misdescribed which scale it used -- and the sentence that would settle which is itself garbled, printing "seam" where it means "same".

- **Location:** Experiment 3, Manipulation check; scale defined in Experiment 1 and Experiment 2 Dependent measures
- **Reported:** "the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001". Experiment 1: "Participants also rated their own attractiveness (How attractive are you?) on a seven-point scale (1 = not at all, 7 = extremely). Then, participants rated the target's attractiveness on the same 7-point scale." Experiment 2: "rated their own attractiveness and the target's attractiveness on seven-point scales (1 = not at all attractive and 7 = extremely attractive)". Experiment 3 Procedure: "rated their own attractiveness (on the seam measures used in Experiments 1 and 2)".
- **Computed:** grim_check, re-run at this stage: failure_mode out_of_range, sum_in_range = false. The nearest admissible integer total is 352, giving 352/48 = 7.3333, but the maximum attainable total on a 1-7 scale at n = 48 is 336. The violation is independent of n -- no sample size rescues a mean above the scale maximum. The same paragraph reports a mood mean of 7.33, on a measure Experiment 2 defines as "(1 = negative mood and 7 = positive mood)".
- **As printed in the paper:** **Experiment 3, Manipulation check** -- “the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001” _(found in the paper's text)_
- **Assumptions:** The scale bound is stated -- Experiments 1 and 2 both print the numerals -- but reaching Experiment 3 requires one inference step through the sentence "on the seam measures used in Experiments 1 and 2", and that sentence contains a typographical error in the word "same". The innocent explanation is that Experiment 3 silently switched to a nine-point instrument, as its similarity items demonstrably are ("1 = not at all, 9 = extremely similar") and as the pilot's self-ratings were. What decides it against that reading: the Method sentence states the opposite, and all eight Experiment 3 self-evaluation cells in Table 2 -- measured on that same referenced instrument -- fall within 1 to 7, as does the downward attractiveness mean of 4.17. I record this at medium confidence for the inference step, and note that no GRIM-family R cross-check applies to a range violation, which is arithmetic on the stated ceiling rather than a granularity question. Either way the paper contradicts itself: either the mean exceeds its scale, or the Method misdescribes the instrument used for the paper's primary outcome.
- **Consequence:** changes no significance decision; 1 stated claim affected -- This is the manipulation check establishing that upward targets were seen as more attractive, which is the precondition every Experiment 3 comparison depends on; the direction of the effect is unaffected, but the reported value cannot be what the stated instrument produced. (asserted, not computed)
- **Reproduce:** no runnable command -- the review could not produce one that runs. The finding's own numbers are above; re-derive from those.

### 3. Experiment 4 control-group mean of 4.20 with SD .21 has no whole-number solution at any plausible group size  [HIGHLY SUSPICIOUS | confidence: medium]

**In plain terms.** The comparison group that every result in Experiment 4 is measured against is reported with an average of 4.20 and a spread of 0.21. For whole-number ratings, a spread that small cannot occur alongside that average -- the tightest possible arrangement of whole numbers would still be about twice as spread out. The most likely ordinary cause is that the authors printed a different measure of precision and labelled it a standard deviation, which is a common slip; but as printed the number does not work, and it is the anchor for eight reported comparisons.

- **Location:** Experiment 4, No load conditions and Cognitive load conditions, control-condition reference mean
- **Reported:** "Higher levels of self-evaluations relative to the control condition (M = 4.20, SD = .21) were found". The control group's size is never printed.
- **Computed:** grimmer_check, re-run at this stage at n = 15: the only compatible integer total is 63, and no integer sum-of-squares of matching parity yields an SD rounding to 0.21, with feasible_ignoring_bounds = false under both SD conventions. Stage 1 obtained the same result at n = 10 and n = 20 and SPRITE returned no_solution_proven at n = 15. The problem is that .21 is too small, not too large: the tightest whole-number configuration consistent with a mean of 4.20 -- a mixture of 4s and 5s -- forces an SD near 0.41.
- **As printed in the paper:** **Experiment 4, No load conditions, control condition** -- “Higher levels of self-evaluations relative to the control condition (M = 4.20, SD = .21) were found” _(found in the paper's text)_
- **Assumptions:** The control group's n is never reported anywhere in the paper, and only n in {10, 15, 20} was tested, so this is not exhaustive; that is why it sits one rung below the tools' own `impossible`. The likeliest innocent explanation is a standard error mislabelled as a standard deviation -- a class of error found in roughly 40% of studies reporting an "SD" (Olsen 2002) -- and check_sd_or_se shows that reading implies an SD near 0.81 at n = 15, entirely ordinary for this scale and in line with every other dispersion in the paper. A simple typographical error is equally available. The paper contains nothing that decides between them.
- **Consequence:** 8 stated claims affected -- This single control mean is the reference point against which all eight of Experiment 4's No load and Cognitive load contrasts are computed, so every one of those F tests is measured against a value that cannot be reconstructed from whole-number data. (asserted, not computed)
- **Reproduce:** no runnable command -- the review could not produce one that runs. The finding's own numbers are above; re-derive from those.

### 4. Error degrees of freedom irreconcilable with the stated sample size in three of the four experiments  [SUSPICIOUS | confidence: high]

**In plain terms.** Every statistical test carries a number that records how many people contributed to it. In three of the four experiments those numbers do not match the number of participants the paper says took part -- in Experiment 4 about 75 people are unaccounted for, and in Experiment 1 one test claims more participants than the whole study had. The paper never reports how many people were in each condition and never mentions anyone being dropped, so a reader cannot tell how many people any given result rests on. Experiment 3 is the exception: its numbers add up exactly.

- **Location:** Experiment 1 Self-evaluations; Experiment 2 Manipulation check and Self-evaluations; Experiment 4 Participants and design versus Results
- **Reported:** Experiment 1: "Female university (N = 47) students participated", with the factorial correctly at F(1, 43) but the simple effect at "F(1, 46) = 6.95, p = 011." Experiment 2: "University (N = 141, 75 women) students participated", with error df of 118, 124, 132 and 138 used across one experiment. Experiment 4: "University (N = 193, 103 female) students participated", with the three-way interaction at F(1, 110) and contrasts at F(1, 124).
- **Computed:** Cross-reference reading of the printed df against the stated N and design. Experiment 1: a simple effect within the two unshared-birthday cells has roughly 22 error df, and even a two-group comparison using all 47 participants has only 45; the printed 46 exceeds every reading. Experiment 2: error df 118 over eight cells implies 126 participants, while t(138) implies 140, against a stated 141. Experiment 4: error df 110 over eight cells implies 118 participants in the factorial, leaving roughly 75 of the stated 193 unaccounted for by the single hanging control condition the paper describes. No exclusions or missing data are reported anywhere, and cell sizes are given for no experiment.
- **As printed in the paper:** “University (N = 193, 103 female) students participated in the study for monetary compensation.” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own statements. Part of the Experiment 2 spread is legitimately explained by the hanging control being included in the contrasts and excluded from the factorial, and I have not counted that portion against the paper. Ordinary listwise deletion would explain the rest but is nowhere stated. Experiment 3 is the counter-example that makes this readable rather than an artefact of my method: its df reconcile exactly (88 = 96 - 8 and 94 = 96 - 2), which is also what licenses n = 12 per cell for the Table 2 checks above.
- **Consequence:** 22 stated claims affected -- Every test in Experiments 1, 2 and 4 -- including all three of the paper's headline interaction effects -- is reported on degrees of freedom that cannot be reconciled with the sample the same section states. (asserted, not computed)
- **Reproduce:** `metascience get-table --xml-path <home>/agent_for_forensic_metascience/eval/ground_truth/papers/10.1007--s11031-011-9216-y/10.1007--s11031-011-9216-y.xml --table-num 2`

### 5. Two reported F statistics fall below the range their own group means and standard deviations permit  [SUSPICIOUS | confidence: medium]

**In plain terms.** A test statistic can be recalculated from the group averages and spreads printed beside it. For two results, the recalculated value does not match what the paper printed -- and in both cases the printed value is weaker than the underlying numbers support, not stronger. Since the paper never says how many people were in each condition, part of the gap could be my assumption about group sizes; a third result checked the same way came out exactly right, which suggests the assumption is not the problem.

- **Location:** Pilot study mood ANOVA; Experiment 1 Self-evaluations, unshared-birthday simple effect
- **Reported:** Pilot: "the mood manipulation significantly affected participant mood, F(2, 42) = 18.44, p < .001" with group means 7.20 (.93), 6.15 (.52) and 4.98 (.98). Experiment 1: "Exposure to the upward comparison target led to lowered self-evaluations (M = 3.33, SD = .65) compared to the downward comparison target (M = 4.64, SD = 1.50), F(1, 46) = 6.95, p = 011."
- **Computed:** rivets_anova over the interval the printed precision permits. Pilot at 15/15/15: achievable F is [26.01, 27.04], against a reported 18.44; at 10/25/10 it is [22.20, 23.13]; at 8/29/8, an allocation implausible for three randomly assigned conditions, it is [19.99, 20.86]. The reported value sits below all three. Experiment 1 at 12 per cell: achievable F is [7.55, 7.89] against a reported 6.95, with zero of the Monte Carlo draws matching.
- **As printed in the paper:** **Experiment 1, Self-evaluations, unshared birthday simple effect** -- “Exposure to the upward comparison target led to lowered self-evaluations (M = 3.33, SD = .65) compared to the downward comparison target (M = 4.64, SD = 1.50), F(1, 46) = 6.95, p = 011.” _(found in the paper's text)_
- **Assumptions:** Per-condition sample sizes are reported nowhere in the paper, so the allocations are my inference -- which is why this is capped at `suspicious` rather than carried at the tool's own higher grade, and why I tested three allocations for the pilot rather than one. For Experiment 1, 47 participants do not divide evenly into four cells, so an 11/12 split would lower the achievable interval somewhat. The control that makes these interpretable: the same tool run on Experiment 1's manipulation check, with group sizes inferred the same way, returned `consistent` with the reported F of 38.80 sitting inside [38.39, 39.68]. Note the direction -- both reported F values are SMALLER than their own group statistics support, which is the opposite of what inflation would produce.
- **Consequence:** changes no significance decision; 2 stated claims affected -- The pilot's claim that the mood induction worked and Experiment 1's symmetric-contrast result; because both reported F values understate rather than overstate the effect their own statistics imply, neither conclusion changes direction. (asserted, not computed)
- **Reproduce:** no runnable command -- the review could not produce one that runs. The finding's own numbers are above; re-derive from those.

### 6. Effect sizes of Hedges' g = 5.03 on a substantive outcome from twelve participants per cell  [SUSPICIOUS | confidence: medium]

**In plain terms.** The size of the difference between two groups can be expressed on a standard scale where 0.8 already counts as large. One of this paper's central results comes out at about 5 -- the two groups barely overlap at all -- from twelve people per group. That is not impossible, and I checked the usual innocent explanations (a mislabelled measure of spread, a do-nothing comparison group, mismatched units) and none applies. But a study this small has less than half the participants needed to reliably detect even a large effect, and effects this extreme from samples this small are exactly the pattern that publication pressure produces. This is my judgement as a reviewer, not a standard the paper agreed to.

- **Location:** Table 2, Similarity row, Positive/Ambiguous cells; Experiment 2 Manipulation check
- **Reported:** "in the presence of ambiguous information, participants in a positive mood rated upward comparison targets as more similar to the self than downward comparison targets, F(1, 94) = 53.17, p < .001", from Table 2 cells 7.06 (.53) and 4.14 (.59). Also "Participants in the positive mood condition were more positive (M = 5.72, SD = .82) than the control condition (M = 4.40, SD = .83)", against a negative-mood mean of 2.98 (.83).
- **Computed:** check_effect_plausibility: the Experiment 3 similarity contrast gives Hedges' g = 5.03, 95% CI [3.53, 6.88], pooled SD 0.561. The Experiment 2 mood manipulation gives g = 3.29, 95% CI [2.68, 3.96]. Separately, required_n: detecting even a large effect (d = 0.8) at 80% power needs 26 per group, against the 12 per cell this design provides -- a ratio of 0.46.
- **As printed in the paper:** **Experiment 2, Manipulation check** -- “Participants in the positive mood condition were more positive (M = 5.72, SD = .82) than the control condition (M = 4.40, SD = .83), t(138) = 5.61, p < .001. The negative mood condition (M = 2.98, SD = .83), was more negative than the control condition, t(138) = -5.97, p < .001.” _(found in the paper's text)_
- **Our check returned a different severity.** The `check_effect_plausibility` check returned `consistent` for the sweep finding `effect_sizes_extraordinary`, which this review recorded as `suspicious`. This entry asserts more than the check established, so read it as this review's judgement and not as a computed result. The finding states a reason.
- **Assumptions:** This is a reported magnitude, not a verdict, and an effect size can be improbable but never arithmetically impossible, so it is capped accordingly. The three ordinary causes were ruled out: dispersion is labelled SD throughout and its magnitudes (.53 to 1.19 on 7- and 9-point scales) are the size one expects of SDs rather than standard errors, which would imply near-zero variance; there is no waitlist comparator, these being randomly assigned laboratory conditions; and units match on both sides of each contrast. The n values are inferred, not printed. The Experiment 2 figure is a manipulation check, where very large effects are normal and unremarkable -- it is the Experiment 3 similarity effect, a substantive dependent variable, that is the outlier. No study in the paper reports an a-priori power analysis, so there is nothing to reproduce; the sensitivity calculation is asked of the paper's own cell sizes instead. That an underpowered design should return effects several times the conventional large threshold at very small p is the frame in which the rest of this review should be read.
- **Consequence:** changes no significance decision; 1 stated claim affected -- Bears on how the paper's effects are weighed as a set rather than on whether any individual test is correctly computed; the similarity result itself remains significant on its own arithmetic. (asserted, not computed)
- **Reproduce:** no runnable command -- the review could not produce one that runs. The finding's own numbers are above; re-derive from those.

### 7. Experiment 1 asserts two significant main effects, prints a statistic for one, then denies the other one sentence later  [SUSPICIOUS | confidence: high]

**In plain terms.** The paper says two effects were statistically significant, gives the supporting numbers for only one of them, and then in the very next sentence says no other effects were significant -- which contradicts what it just said about the second one. In a design of this shape there are only two such effects, so there is no third reading that makes both sentences true, and the missing numbers appear nowhere.

- **Location:** Experiment 1, Self-evaluations, opening paragraph
- **Reported:** "A 2(similarity cue: shared birthday vs. different birthday) x 2(direction: upward vs. downward) ANOVA revealed significant main effects of cue and direction of comparison such that those sharing a birthday reported higher self-evaluations (M = 4.92, SD = 1.14) than those not sharing a birthday (M = 3.96, SD = 1.3), F(1, 43) = 7.77, p = .008. No other main effects were significant."
- **Computed:** Reading of two adjacent sentences. The design is 2x2, so it has exactly two main effects. The passage claims both are significant, prints an F for the cue effect only, and then states that no other main effects were significant -- which can only refer to direction, the effect just claimed as significant. No statistic for the direction main effect appears anywhere in Experiment 1, so the contradiction cannot be resolved from the text.
- **As printed in the paper:** “A 2(similarity cue: shared birthday vs. different birthday) × 2(direction: upward vs. downward) ANOVA revealed significant main effects of cue and direction of comparison such that those sharing a birthday reported higher self-evaluations (M = 4.92, SD = 1.14) than those not sharing a birthday (M = 3.96, SD = 1.3), F(1, 43) = 7.77, p = .008. No other main effects were significant.” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own statements.
- **Consequence:** 1 stated claim affected -- The status of the direction-of-comparison main effect in Experiment 1 is asserted and then implicitly denied, with no statistic printed either way. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command crashed when run. The finding's own numbers are above; re-derive from those.

### 8. Three of sixty-five reported test statistics disagree with their own p-values, one substantively  [SUSPICIOUS | confidence: high]

**In plain terms.** A test statistic and its p-value have to agree with each other, and a program can check all of them at once. Three of sixty-five disagree here. That rate is normal and would not by itself be a criticism -- most honest papers contain one. One of the three turns out to be a simple typing slip that corrects cleanly. The one that matters reports a p-value of .83 where the statistic gives .22, in a sentence that also calls the result identical to a different result it does not match. None of the three changes whether any finding counts as significant.

- **Location:** Results sections, Pilot study through Experiment 4
- **Reported:** "Identical effects emerged when the information was unambiguous, F(1, 94) = 1.50, p = .83." Also "did not differ F(1, 42) = .27, p = .76" and "neutral mood, r(24) = .53, p = .008".
- **Computed:** statcheck over 65 extracted NHST results: 3 inconsistencies after a rounding allowance, and zero decision errors -- no reported p falls on the wrong side of the threshold it is judged against. F(1, 94) = 1.50 gives p = .224, not .83. r(24) = .53 gives p = .0054, not .008. The third, F(1, 42) = .27 with p = .76, reconciles exactly once the numerator df is corrected: recalc_f_to_p at df1 = 2 -- which is what a one-way ANOVA over three mood conditions requires, and what the companion mood ANOVA two paragraphs earlier correctly prints as F(2, 42) -- gives an achievable p interval of [.7609, .7685], containing the reported .76. That one is a typographical error in the df, not a wrong p.
- **As printed in the paper:** **Results sections, Pilot study through Experiment 4** -- “Identical effects emerged when the information was unambiguous, F(1, 94) = 1.50, p = .83.” _(found in the paper's text)_
- **Our check returned a different severity.** The `recalc_f_to_p` check returned `consistent` for the sweep finding `pilot_selfeval_df_typo`, which this review recorded as `suspicious`. This entry asserts more than the check established, so read it as this review's judgement and not as a computed result. The finding states a reason.
- **Assumptions:** None beyond the paper's own statements. The base rate matters and cuts in the paper's favour here: statcheck inconsistencies at roughly this rate are near-universal in honest work, half of the clean control papers in this project's own corpus contain at least one, and a rate of 3 in 65 with zero decision errors would not on its own support any adverse reading. Only the F(1, 94) = 1.50 case is substantive, and it is compounded by the sentence describing that result as "Identical" to a preceding F of .31, which it is not.
- **Consequence:** changes no significance decision -- Zero decision errors: no reported p falls on the wrong side of its own significance threshold, so none of the three inconsistencies changes a conclusion the paper draws. Zero decision errors: no reported p falls on the wrong side of its own significance threshold, so none of the three inconsistencies changes a conclusion the paper draws. Computed from 0 statistic(s) whose recomputed p crosses the paper's alpha. (computed)
- **Reproduce:** `metascience f-to-p --f-value 1.50 --df1 1 --df2 94 --reported-p 0.83 --decimals-f 2 --decimals-p 2`

### 9. Data offered on request rather than deposited, in a paper whose open questions only the raw data can settle  [INDETERMINATE | confidence: high]

**In plain terms.** The paper says the full data can be had by writing to the first author rather than posting it anywhere. That was completely normal for a psychology paper in 2011 and is not a criticism of the authors. It is worth noting only because every unresolved question in this review is one the raw data would answer immediately.

- **Location:** Experiment 3, footnote 4
- **Reported:** "Complete data and results available from the first author."
- **Computed:** No computation applies. This is the paper's only data-availability statement.
- **As printed in the paper:** “Complete data and results available from the first author.” _(found in the PDF text layer)_
- **Assumptions:** Era context is decisive and is why this is graded `indeterminate` rather than as a defect: availability on request was entirely standard practice for a 2011 psychology paper, deposit was not expected, and this is recorded as an observation rather than a criticism. It is worth stating only because the specific questions this review leaves open -- cell sizes in all four experiments, the degrees-of-freedom discrepancies, the two unreconstructable Table 2 cells -- are precisely the ones access to the data would settle in minutes.
- **Consequence:** changes no significance decision -- Changes no reported result; it determines only whether the discrepancies above could be resolved by a reader. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command crashed when run. The finding's own numbers are above; re-derive from those.

## What we could NOT check

- **Table 1 (Experiment 2), all 8 self-evaluation cells** — Cell sizes are never reported and the factorial N implied by the error df (126) does not divide evenly into 8 cells, so no denominator can be assigned. GRIM, GRIMMER and SPRITE all require one, and running them at a guessed n is the commonest route to a false accusation. Experiment 2 is therefore the least verifiable of the four studies, and its three-way interaction is one of the paper's headline results.
- **Table 2 (Experiment 3), all 8 Similarity-row cells** — The similarity index is a MEAN of three nine-point items, so its granularity is 1/(3n) rather than 1/n, and our GRIM-family implementation has no items parameter. All 8 cells were refused rather than checked at the wrong granularity. This is a gap in our toolkit, not a property of the paper; R's `scrutiny` GRIM does take an items argument and could check these.
- **Pilot study, mood index and self-evaluation index means (6 mean/SD pairs)** — Both are multi-item composite means (4 items and 3 items) on 1-9 scales, and per-condition sample sizes are not reported. Neither the items granularity nor the denominator is available.
- **All prose mean (SD) pairs in Experiments 1, 2 and 4 (roughly 25 pairs)** — The paper reports no cell sizes in any of the four experiments. Where a group n could be defensibly inferred from the design the check was run; where it could not, no guess was substituted.
- **Experiment 3, mood and attractiveness manipulation-check means (7.33, 5.44, 7.33, 4.17)** — GRIMMER and SPRITE need a settled scale, and which scale Experiment 3 used is precisely what is in dispute. Only the range check, which is scale-agnostic in direction, could be run.
- **Figures 1, 2 and 3** — Figure 1 is a conceptual schematic with no data. Figures 2 and 3 plot means that are also printed in Table 2 and in the Experiment 4 Results text respectively, so no unique value is lost. No figure-pixel measurement was attempted and none was needed.
- **Supplementary materials** — None accompany this paper. Footnote 4 states that complete data and results are available from the first author rather than deposited, so there is no supplement to read.
- **Multiplicity across the Experiment 2 and Experiment 4 contrast families** — Deliberately not run. The authors report their own Tukey HSD correction for both families in footnotes 2 and 5 and disclose which contrast fails it -- one drops from p < .05 to p = .13. Running a correction over tests the authors already corrected would double-count it.
- **Formally clean R cross-check of the two Table 2 cells graded impossible** — rsprite2 rejected both triples through its own GRIMMER screen, agreeing with our result in substance, but did so by raising an exception rather than returning a clean infeasible flag. Our wrapper measures a 16.2% false-raise rate on that path, so the confirmation is substantive rather than formally clean and the finding rests on our own analytic enumeration.
- **table rows Similarity, Similarity, Similarity, Similarity, Similarity, Similarity and 2 more** — grim_check, grimmer_check, sprite_reconstruct not run: multi-item composite whose scoring is undeclared. If the score is a MEAN of items its granularity is 1/(items*n) and grim_test has no `items` parameter, so checking at 1/n would manufacture an impossibility; if it is a SUM the granularity is 1/n and the check is valid. Declare `derivation` as 'mean_of_items' or 'sum_of_items' to resolve this -- the field is already in the schema and the prompt asks for it.
- **table rows Similarity, Similarity, Similarity, Similarity, Similarity, Similarity and 2 more** — grim_check, grimmer_check, sprite_reconstruct not run: composite scored as a MEAN of items: granularity is 1/(items*n), not 1/n, and grim_test has no `items` parameter. Checking at 1/n would manufacture an impossibility. Refused until `items` is plumbed through.

## Questions for the authors

_Each of these is answerable from what the authors already have. None presupposes an error on their part: an inconsistency is far more often a reporting slip, or a mistake by this tool in reading the number off the page, than anything else._

1. Could you supply the per-condition sample sizes for the pilot study and for Experiments 1, 2 and 4? None of the four experiments prints them, and several reported degrees of freedom cannot be reconciled with the stated totals -- Experiment 4 states N = 193 while its three-way interaction is reported as F(1, 110), which over eight cells implies 118 participants in the factorial.
   <sub>Would resolve: Cell sizes are the single missing input blocking roughly 25 prose mean/SD pairs and all eight Table 1 cells from any granularity check, and they would settle the degrees-of-freedom finding directly.</sub>
2. Could you send the cell-level values behind the two Table 2 Self-evaluation entries reported as 6.58 (.52) and 4.08 (.52)? At twelve participants per cell on the single seven-point item, we can find no set of whole-number responses that produces either mean alongside a standard deviation of .52, under either the n-1 or the n convention.
   <sub>Would resolve: These two cells are the two halves of the unambiguous-cue contrast Experiment 3 rests on, and both are individually unreconstructable from integer data.</sub>
3. Which response scale was used for the attractiveness ratings in Experiment 3? The Procedure refers to the measures used in Experiments 1 and 2, which are printed as seven-point (1 = not at all, 7 = extremely), but the manipulation check reports an upward-target mean of 7.33, and the mood mean in the preceding sentence is also 7.33 on a measure Experiment 2 defines as running from 1 to 7.
   <sub>Would resolve: Resolves whether the reported means exceed their scale or the Method sentence misdescribes the instrument; the sentence that would decide it contains a typographical error ('seam' for 'same').</sub>
4. For the Experiment 4 control condition reported as M = 4.20, SD = .21, was .21 a standard deviation or a standard error? For whole-number ratings with a mean of 4.20 the smallest attainable standard deviation is near 0.41, whereas reading .21 as a standard error at a group size of around 15 implies an SD near 0.81, which matches the dispersions reported elsewhere in the paper.
   <sub>Would resolve: This control mean is the reference point for all eight Experiment 4 contrasts, and the SE reading would resolve the discrepancy entirely.</sub>
5. Could you provide the statistic for the main effect of direction of comparison in Experiment 1? The Self-evaluations paragraph reports 'significant main effects of cue and direction of comparison', prints F(1, 43) = 7.77 for cue only, and then states 'No other main effects were significant.'
   <sub>Would resolve: In a 2x2 design there are exactly two main effects, so the two sentences cannot both be true as printed, and no statistic for the direction effect appears anywhere in Experiment 1.</sub>

## Limitations

- This agent reads text and tables and does not see figures. Figure extraction was NOT run on this paper. That costs nothing here on the sweep's own reading: Figure 1 is a conceptual schematic carrying no data, and Figures 2 and 3 plot means that are also printed in Table 2 and in the Experiment 4 Results text. No value was checked that came from a figure, and none was needed.
- The two Table 2 cells graded `impossible` rest on n = 12 per cell, which the paper never prints. The inference is strong -- N = 96 over eight cells, corroborated by the reported error df of 88 and by all eight cells being GRIM-consistent at exactly n = 12 -- but it is an inference, and a reader who rejects it should treat those two findings as unverified rather than as refuted.
- The R cross-check on those two cells agreed in content but not in form: rsprite2's GRIMMER screen rejected both triples by raising rather than returning a clean infeasible flag, and our wrapper measures a 16.2% false-raise rate on that path. The findings therefore stand on our own closed-form parity enumeration, corroborated but not formally confirmed by a second engine.
- The Stage-1 worklist flagged all 16 accusations with `quote_not_located`. That is a fact about the instrument, not about the findings: on re-reading the XML full text at this stage, every span checked -- the pilot ANOVA sentence, the Experiment 1 main-effects passage, 'F(1, 46) = 6.95, p = 011.', the Experiment 3 manipulation check, 'on the seam measures used in Experiments 1 and 2', the Experiment 2 participants sentence and the F(1, 94) = 1.50 sentence -- was located verbatim. The class is resolved globally and no individual finding was discarded on it.
- This system reads one paper and reaches no network. Two questions a reader would want answered about a pattern like this -- whether comparable anomalies appear in other papers by the same authors, and how these effect sizes compare with the wider social-comparison literature -- are outside its reach entirely, and the interpretation is therefore partly ours and partly the reader's.
- The article carries a retraction notice in its own title. That is recorded as context only. Nothing in this review uses the retraction as evidence; every finding above was derived from the paper's printed numbers and would stand or fall identically had the article never been retracted.
- Cell sizes are reported for none of the four experiments, which is the single largest constraint on coverage here: roughly 25 prose mean/SD pairs and all eight Table 1 cells could not be checked at all for want of a denominator.
- No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.

## Coverage

- **Statistics found:** 80; **checked:** 43
- **Tools run:** extract_xml, get_table, extract_pdf, parse_cells_typed, check_table, grim_check, grimmer_check, sprite_reconstruct, r_sprite_ground_truth, statcheck, recalc_f_to_p, rivets_anova, detect_duplication, check_sd_or_se, check_effect_plausibility, required_n
- **Tables checked:** Table 1 (Experiment 2) -- typed, denominators unavailable, 0 of 8 cells checkable, Table 2 (Experiment 3) -- typed and swept, 24 checks run, 8 refused, 2 of 8 checkable cells failing, Table 2 cross-checked against the independently extracted PDF grid, 16 of 16 cells identical
- **Checkable table cells:** 24 of 24 surveyed; **checked:** 8
    - 24 could not be checked without knowing what kind of quantity the row reports
- **Every checkable item:** 157 registered; 24 refused with a stated reason; **133 outstanding**
    - how many were CHECKED is not measured -- no persisted item identity joins a tool call back to a manifest row, so how many items were CHECKED cannot be counted. This is not a count of zero. This is not a count of zero.
- **Stage-1 findings:** 23 raised; 17 carried into this report; 6 not carried
- **Where a check and this review disagreed:** 7 sweep findings recorded a severity the validated check behind them did not return (2 upgraded, 5 downgraded). 2 are marked on the entry above that cites them. 4 are explained downgrades on an entry above, counted here and not marked there: the check said more, this review said less and said why, which is what stage 2 is for. 1 sits on a sweep finding no entry in this report cites, so this line is the only place it appears.
- **Traceable to the page:** 32 of 32 checks recorded the passage their numbers were read from; 32 of those were located in the paper's own text.

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

This paper reports a pilot study and four between-subjects laboratory experiments arguing that positive mood lets people reinterpret ambiguous information about a comparison target in self-serving ways -- assimilating to people who outshine them and contrasting away from people who do not. The design is consistent across studies: a mood induction, a comparison target, an ambiguous or unambiguous similarity cue, and a single seven-point self-rating of attractiveness as the outcome. The article carries a retraction notice in its own title; I note that as context and use none of it as evidence. Everything below comes from the printed numbers and would read identically had the paper never been retracted.

**What reconciled.** Twenty-six of the forty-three checks run came back consistent, twenty of them collapsed inside a single table sweep rather than reported individually, and several are worth naming because they are what make the failures interpretable rather than an artefact of method. Experiment 3's degrees of freedom reconcile exactly with its stated sample under both the factorial and the two-group planned comparisons (88 = 96 - 8, 94 = 96 - 2), which is the counter-example that gives the degrees-of-freedom finding in the other three experiments its force -- and which is also what licenses n = 12 per cell for the granularity checks. Experiment 1's manipulation check, with group sizes inferred exactly the same way as the two failing ones, returns a reported F of 38.80 sitting comfortably inside its achievable interval of [38.39, 39.68]. Table 2's sixteen cells were extracted independently from the XML and from the PDF and agree on every one. And across 128 cross-source comparisons, no duplicated mean/SD pair appears anywhere between Tables 1 and 2 -- these two tables are not copies of one another, and that is a clean negative result that deserves saying.

**Where the coverage stopped, and why it matters.** The paper reports cell sizes for none of its four experiments. That single omission is what blocks the largest part of this review: roughly twenty-five prose mean/SD pairs and all eight of Table 1's cells could not be checked at all, because GRIM, GRIMMER and SPRITE each need a denominator and substituting a guess is the fastest available route to a false accusation. Experiment 2 -- whose three-way interaction is one of the paper's headline results -- is consequently the least verifiable of the four studies. A further eight cells, the Similarity row of Table 2, were refused because that index is a mean of three items and our implementation cannot express the 1/(3n) granularity that requires; that is a gap in our toolkit and not a property of the paper.

**How the failures cluster.** What survives triage is not a scatter of small discrepancies. Three reported values cannot have come from the data described, and they are not in obscure corners: one is the boundary-condition contrast Experiment 3 exists to demonstrate, one is the manipulation check that licenses every Experiment 3 comparison, and one is the control mean against which all eight of Experiment 4's contrasts are measured. Around them sit degrees of freedom that cannot be reconciled with the stated samples in three experiments out of four, two F statistics falling below the range their own means and standard deviations permit, and a paragraph that asserts an effect and denies it one sentence later.

Two things pull the other way and should be weighed. The statcheck rate of three inconsistencies in sixty-five results, with zero decision errors, is unremarkable -- half the clean control papers in this project's own corpus contain at least one, and one of these three resolves cleanly as a typo in the degrees of freedom. And the authors correct their own multiplicity in footnotes 2 and 5, disclosing which contrast drops to p = .13 under Tukey HSD; that is straightforwardly good practice and it is not common.

Two of the three impossible values rest on a per-cell sample size of twelve that the paper never prints, though the inference is corroborated three independent ways. The third rests on a scale the Method prints in numerals but reaches Experiment 3 through a sentence containing a typographical error in the crucial word. Neither caveat dissolves the arithmetic; both are stated so a reader can weigh them.

The reported statistics do not reconcile with one another, and the failures reach the results the paper depends on.

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
