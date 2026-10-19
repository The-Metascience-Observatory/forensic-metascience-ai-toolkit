# Forensic review -- Au et al. 2020

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## Corrigendum: Are There Advantages to Believing in Fate? The Belief in Negotiating With Fate When Faced With Constraints
*Evelyn W. M. Au, Krishna Savani. Frontiers in Psychology. 2020. doi:10.3389/fpsyg.2019.02949*

**Design:** Corrigendum to Au & Savani (2019) Front. Psychol. 10:2354. Corrects six between-subjects randomized experiments. This document reprints Tables 1, 2 and 4 and the corrected Results paragraphs only; it is NOT the full article.

<sub>Analysed as `10.3389--fpsyg.2019.02949`</sub>

> **SUSPICIOUS** — The corrigendum states that Experiment 4's fatalism mean should read 3.53 instead of 3.54, then reprints the "corrected" paragraph with 3.54 still in it and 3.53 nowhere in it.
>
> **In plain terms:** A correction notice exists to replace wrong numbers with right ones. This one announces that a particular average was misprinted as 3.54 and should be 3.53, and then prints the supposedly corrected passage with 3.54 still in it. Whichever of the three averages in that passage belongs to the condition in question, the number the authors say should be there is not there, so a reader cannot tell which figure now stands.
>
> **Evidence:** Page 2, erratum note: "In Experiment 4, there was an error in reporting participants' mean agreement with the biased scale in the Fatalism condition. 'M_Fatalism = 3.54' was incorrectly provided instead of 'M_Fatalism = 3.53.'" Page 2, immediately below, under "A correction has been made to Experiment 4, Results section, paragraph one": "[M_Fatalism = 3.54, M_PersonalControl = 3.67, M_NegotiatingWithFate = 3.90; F(2,136) = 2.89, p = 0.06]". The three means printed in the corrected paragraph are 3.54, 3.67 and 3.90; the value 3.53 does not appear.
> **Rests on:** logical necessity (no assumption added)
> **Reproduce:** `metascience extract --pdf-path /mnt/c/Users/gregs/agent_for_forensic_metascience/eval/ground_truth/papers/10.3389--fpsyg.2019.02949/10.3389--fpsyg.2019.02949.pdf --first-page 2 --last-page 2`

**Verdict: questionable** (confidence: high)

## Provenance of the analysis

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

6 study/studies, 17 variables, 19 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| s1 | Experiment 1 (Study 1): choice/neutral/no-choice recall manipulation | rct | 121 | participant | no |
| s2 | Experiment 2 (Study 2): choice/neutral/no-choice manipulation, no-choice as regression reference group | rct | 200 | participant | no |
| s3 | Experiment 3 (Study 3): random exposure to biased fatalism / personal-control / negotiating-with-fate questionnaire; outcome rumination | rct | 217 | participant | no |
| s4 | Experiment 4 (Study 4): biased-questionnaire manipulation; outcome identifying own behavior as contributing factor | rct | 138 | participant | no |
| s5 | Experiment 5 (Study 5): biased-questionnaire manipulation; Brief-COPE style coping outcomes | rct | 194 | participant | no |
| s6 | Experiment 6 (Study 6): biased-questionnaire manipulation plus silver-lining task; outcome meaning | rct | 158 | participant | no |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Age | ratio | continuous | range not stated | years | measured | none -- not integer-valued | high |
| Gender | nominal | discrete | Men; Women | - | measured | percentage GRIM on cell counts | high |
| Educational attainment | ordinal | discrete | Did not complete high school; Completed high school; Incomplete college degree; Associate's degree; Bachelor's degree; Master's degree; Doctoral degree; Unreported | - | measured | percentage GRIM on cell counts | high |
| Religious affiliation | nominal | discrete | Non-religious; Protestant; Catholic; Christian; Other religions; Unreported | - | measured | percentage GRIM on cell counts | high |
| Personal control belief | interval | continuous | range not stated | - | mean of items (k=8): 8 items averaged (alpha = 0.79) | none -- composite granularity is 1/(items x n) | high |
| Fatalism belief | interval | continuous | range not stated | - | mean of items (k=8): 8 items averaged (alpha = 0.84) | none -- composite granularity is 1/(items x n) | high |
| Negotiating with fate belief | interval | continuous | range not stated | - | mean of items (k=10): 10 items averaged (alpha = 0.86) | none -- composite granularity is 1/(items x n) | high |
| Ease of the recall task (Experiment 1 manipulation check / covariate) | interval | unknown | range not stated | - | measured | none -- variable not typed | medium |
| Mean agreement with the biased response scale (Experiments 3-6 manipulation check / covariate) | interval | continuous | range not stated | - | mean of items | none -- composite granularity is 1/(items x n) | medium |
| Rumination (Experiment 3 outcome) | interval | continuous | range not stated | - | mean of items | none -- composite granularity is 1/(items x n) | low |
| Identifying own behavior as a contributing factor (Experiment 4 outcome) | interval | continuous | range not stated | - | mean of items | none -- composite granularity is 1/(items x n) | low |
| Positive reappraisal (Experiment 5 outcome) | interval | continuous | range not stated | - | mean of items | none -- composite granularity is 1/(items x n) | low |
| Acceptance (Experiment 5 outcome) | interval | continuous | range not stated | - | mean of items | none -- composite granularity is 1/(items x n) | low |
| Denial (Experiment 5 outcome) | interval | continuous | range not stated | - | mean of items | none -- composite granularity is 1/(items x n) | low |
| Behavioral disengagement (Experiment 5 outcome) | interval | continuous | range not stated | - | mean of items | none -- composite granularity is 1/(items x n) | low |
| Meaning derived from the event (Experiment 6 outcome) | interval | continuous | range not stated | - | mean of items | none -- composite granularity is 1/(items x n) | low |
| Perceived helpfulness of the silver-lining task (Experiment 6 covariate) | ordinal | discrete | 1-9 (integers) | - | measured | GRIM, GRIMMER, SPRITE | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Corrigendum, Experiment 1 corrected Results para 1 | one_way_anova | Ease of the recall task (Experiment 1 manipulation check / covariate) (unknown) | - | 121 | none | none reported |
| Corrigendum, Experiment 2 corrected Results para 2 | linear_regression | Fatalism belief (likert_composite) | condition: neutral vs no-choice | 200 | none | none reported |
| Corrigendum, Experiment 2 corrected Results para 2 | linear_regression | Fatalism belief (likert_composite) | condition: choice vs no-choice | 200 | none | none reported |
| Corrigendum, Experiment 2 corrected Results para 2 | linear_regression | Personal control belief (likert_composite) | condition: neutral vs no-choice | 200 | none | none reported |
| Corrigendum, Experiment 2 corrected Results para 2 | linear_regression | Personal control belief (likert_composite) | condition: choice vs no-choice | 200 | none | none reported |
| Corrigendum, Experiment 2 corrected Results para 2 | linear_regression | Negotiating with fate belief (likert_composite) | condition: neutral vs no-choice | 200 | none | none reported |
| Corrigendum, Experiment 2 corrected Results para 2 | linear_regression | Negotiating with fate belief (likert_composite) | condition: choice vs no-choice | 200 | none | none reported |
| Corrigendum, Experiment 3 corrected Results para 1 | one_way_anova | Mean agreement with the biased response scale (Experiments 3-6 manipulation check / covariate) (likert_composite) | - | 217 | none | none reported |
| Corrigendum, Experiment 4 corrected Results para 1 | one_way_anova | Mean agreement with the biased response scale (Experiments 3-6 manipulation check / covariate) (likert_composite) | - | 138 | none | none reported |
| Corrigendum, Experiment 4 corrected Results para 3 | linear_regression | Identifying own behavior as a contributing factor (Experiment 4 outcome) (likert_composite) | condition: negotiating with fate vs fatalism, agreement with biased scale (covariate) | 138 | none | none reported |
| Corrigendum, Experiment 4 corrected Results para 3 | linear_regression | Identifying own behavior as a contributing factor (Experiment 4 outcome) (likert_composite) | condition: negotiating with fate vs personal control, agreement with biased scale (covariate) | 138 | none | none reported |
| Corrigendum, Experiment 4 corrected Results para 3 | linear_regression | Identifying own behavior as a contributing factor (Experiment 4 outcome) (likert_composite) | condition: fatalism vs personal control | ? | none | none reported |
| Corrigendum, Experiment 5 corrected Results para 1 | one_way_anova | Mean agreement with the biased response scale (Experiments 3-6 manipulation check / covariate) (likert_composite) | - | 194 | none | none reported |
| Corrigendum, Experiment 5 corrected Results para 3 | linear_regression | Positive reappraisal (Experiment 5 outcome) (likert_composite) | condition: negotiating with fate vs fatalism, agreement with biased scale (covariate) | 194 | none | none reported |
| Corrigendum, Experiment 5 corrected Results para 3 | linear_regression | Positive reappraisal (Experiment 5 outcome) (likert_composite) | condition: negotiating with fate vs personal control, agreement with biased scale (covariate) | 194 | none | none reported |
| Corrigendum, Experiment 5 corrected Results para 3 | linear_regression | Acceptance (Experiment 5 outcome) (likert_composite) | condition: negotiating with fate vs fatalism, agreement with biased scale (covariate) | 194 | none | none reported |
| Corrigendum, Experiment 5 corrected Results para 3 | linear_regression | Acceptance (Experiment 5 outcome) (likert_composite) | condition: negotiating with fate vs personal control, agreement with biased scale (covariate) | 194 | none | none reported |
| Corrigendum, Experiment 6 corrected Methods para 1 | pearson_correlation | Meaning derived from the event (Experiment 6 outcome) (likert_composite) | Perceived helpfulness of the silver-lining task (Experiment 6 covariate) | 158 | none | none reported |
| Corrigendum, Experiment 6 corrected Methods para 1 | one_way_anova | Perceived helpfulness of the silver-lining task (Experiment 6 covariate) (likert_item) | - | 158 | none | none reported |

#### Variable/test mismatches

A parametric test is applied to an outcome this analysis typed as non-continuous. That is not proof of an error -- the typing may be wrong, and some parametric tests are robust -- but each pair below should be checked against the paper.

- **Corrigendum, Experiment 2 corrected Results para 2**: `linear_regression` assumes a continuous, roughly normal outcome, but **Fatalism belief** is typed `likert_composite`.
- **Corrigendum, Experiment 2 corrected Results para 2**: `linear_regression` assumes a continuous, roughly normal outcome, but **Fatalism belief** is typed `likert_composite`.
- **Corrigendum, Experiment 2 corrected Results para 2**: `linear_regression` assumes a continuous, roughly normal outcome, but **Personal control belief** is typed `likert_composite`.
- **Corrigendum, Experiment 2 corrected Results para 2**: `linear_regression` assumes a continuous, roughly normal outcome, but **Personal control belief** is typed `likert_composite`.
- **Corrigendum, Experiment 2 corrected Results para 2**: `linear_regression` assumes a continuous, roughly normal outcome, but **Negotiating with fate belief** is typed `likert_composite`.
- **Corrigendum, Experiment 2 corrected Results para 2**: `linear_regression` assumes a continuous, roughly normal outcome, but **Negotiating with fate belief** is typed `likert_composite`.
- **Corrigendum, Experiment 3 corrected Results para 1**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Mean agreement with the biased response scale (Experiments 3-6 manipulation check / covariate)** is typed `likert_composite`.
- **Corrigendum, Experiment 4 corrected Results para 1**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Mean agreement with the biased response scale (Experiments 3-6 manipulation check / covariate)** is typed `likert_composite`.
- **Corrigendum, Experiment 4 corrected Results para 3**: `linear_regression` assumes a continuous, roughly normal outcome, but **Identifying own behavior as a contributing factor (Experiment 4 outcome)** is typed `likert_composite`.
- **Corrigendum, Experiment 4 corrected Results para 3**: `linear_regression` assumes a continuous, roughly normal outcome, but **Identifying own behavior as a contributing factor (Experiment 4 outcome)** is typed `likert_composite`.
- **Corrigendum, Experiment 4 corrected Results para 3**: `linear_regression` assumes a continuous, roughly normal outcome, but **Identifying own behavior as a contributing factor (Experiment 4 outcome)** is typed `likert_composite`.
- **Corrigendum, Experiment 5 corrected Results para 1**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Mean agreement with the biased response scale (Experiments 3-6 manipulation check / covariate)** is typed `likert_composite`.
- **Corrigendum, Experiment 5 corrected Results para 3**: `linear_regression` assumes a continuous, roughly normal outcome, but **Positive reappraisal (Experiment 5 outcome)** is typed `likert_composite`.
- **Corrigendum, Experiment 5 corrected Results para 3**: `linear_regression` assumes a continuous, roughly normal outcome, but **Positive reappraisal (Experiment 5 outcome)** is typed `likert_composite`.
- **Corrigendum, Experiment 5 corrected Results para 3**: `linear_regression` assumes a continuous, roughly normal outcome, but **Acceptance (Experiment 5 outcome)** is typed `likert_composite`.
- **Corrigendum, Experiment 5 corrected Results para 3**: `linear_regression` assumes a continuous, roughly normal outcome, but **Acceptance (Experiment 5 outcome)** is typed `likert_composite`.
- **Corrigendum, Experiment 6 corrected Methods para 1**: `pearson_correlation` assumes a continuous, roughly normal outcome, but **Meaning derived from the event (Experiment 6 outcome)** is typed `likert_composite`.
- **Corrigendum, Experiment 6 corrected Methods para 1**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Perceived helpfulness of the silver-lining task (Experiment 6 covariate)** is typed `likert_item`.

_19 of 19 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. Three significant results across two test families, no correction for multiplicity  [SUSPICIOUS | confidence: high]

**In plain terms.** In both of the experiments that carry the paper's main conclusions, the authors ran several statistical comparisons at once but judged each one on its own, as if it were the only test they had done. Run enough comparisons and some will look impressive by luck alone. Once you account for the number of comparisons actually reported, none of the three results the authors call significant clears the bar any more -- and that holds under every standard method for making the adjustment. This does not show the effects are absent; it shows the evidence presented for them is weaker than the paper states.

- **Location:** Corrected Experiment 2 Results paragraph two (six contrasts) and corrected Experiment 5 Results paragraph three (four contrasts)
- **Reported:** Experiment 2 reports six regression contrasts on the same 200 participants (p = 0.29, 0.77, 0.10, 0.11, 0.03, 0.04) and concludes "the belief in negotiating with fate was stronger in the no-choice condition than in either the neutral ... or choice ... conditions ... This result replicates the finding from Experiment 1." Experiment 5 reports four contrasts on the same 194 participants (p = 0.03, 0.10, 0.07, 0.84) and concludes "participants reported significantly greater positive reappraisal of the event after negotiating with fate was activated compared to activating fatalism." No correction is applied or mentioned in either.
- **Computed:** Experiment 2: 6 uncorrected tests, family-wise error rate up to 26.5%, Bonferroni threshold 0.0083; 2 results significant uncorrected, 0 surviving under all four of Bonferroni, Holm, Benjamini-Hochberg and Benjamini-Yekutieli; n_claims_lost_to_correction = 2. Experiment 5: 4 uncorrected tests, family-wise error rate up to 18.5%, Bonferroni threshold 0.0125; 1 significant uncorrected, 0 surviving under all four methods; n_claims_lost_to_correction = 1. The surviving interval is 0 to 0 in both families, so the result does not depend on which correction one prefers.
- **As printed in the paper:** “participants reported significantly greater positive reappraisal ... [p = 0.03] ... marginally greater positive reappraisal ... [p = 0.10] ... marginally greater acceptance ... [p = 0.07] ... No differences in acceptance were found ... [p = 0.84)” _(found in the PDF text layer, across an ellipsis)_
- **Assumptions:** That the six Experiment 2 contrasts (three belief scales x two comparisons against the same no-choice reference group, all bearing on one hypothesis) form one family, and the four Experiment 5 contrasts (two coping outcomes x two comparison conditions) form another. Family definition is a judgement the tool cannot make. Uncorrected testing is ordinary practice in this literature and this is deterministic arithmetic, not an allegation. The Experiment 5 count is a floor: Table 4 shows denial and behavioral disengagement were also measured in that study but their contrasts are not reported in this document.
- **Consequence:** 2 stated claims affected -- The stated replication of Hypothesis 1 in Experiment 2 rests on the only two significant p-values among six reported contrasts, and the adaptive-coping claim in Experiment 5 on the only significant p-value among four; none survives correction within its own family. The sentence 'the belief in negotiating with fate was stronger in the no-choice condition than in either the neutral or choice conditions ... This result replicates the finding from Experiment 1' rests on the only two significant p-values in the family, and neither survives correction for the six tests reported alongside them. Computed from 2 result(s) significant uncorrected do not survive correction (a correction the paper did not apply, over a family we chose). (computed)
- **Reproduce:** `metascience multiplicity --family-label 'Experiment 2: six regression contrasts (3 lay beliefs x 2 condition comparisons vs no-choice reference) on the same 200 participants' --tests '[{"id":"e2_fat_neutral","p_value":0.29,"correction_applied":"none"},{"id":"e2_fat_choice","p_value":0.77,"correction_applied":"none"},{"id":"e2_pc_neutral","p_value":0.10,"correction_applied":"none"},{"id":"e2_pc_choice","p_value":0.11,"correction_applied":"none"},{"id":"e2_nwf_neutral","p_value":0.03,"correction_applied":"none"},{"id":"e2_nwf_choice","p_value":0.04,"correction_applied":"none"}]'`

### 2. Experiment 4's stated correction absent from the paragraph reprinted as corrected  [SUSPICIOUS | confidence: high]

**In plain terms.** The document announces that one average was misprinted and gives the right value, then reprints the passage it says it has fixed with the wrong value still in place and the right value nowhere to be seen. The number itself is a descriptive average from a manipulation check and no conclusion turns on it, but a correction notice that does not carry out its own correction cannot be relied on to have carried out the others either.

- **Location:** Page 2: Experiment 4 erratum note and the corrected Results paragraph one printed directly beneath it
- **Reported:** Erratum: "'M_Fatalism = 3.54' was incorrectly provided instead of 'M_Fatalism = 3.53.'" Corrected paragraph: "[M_Fatalism = 3.54, M_PersonalControl = 3.67, M_NegotiatingWithFate = 3.90; F(2,136) = 2.89, p = 0.06]"
- **Computed:** The three means in the corrected paragraph are 3.54, 3.67 and 3.90. The value 3.53 appears nowhere in it. The two printed statements cannot both stand. By contrast, the structurally identical Experiment 5 correction (M_NegotiateWithFate "3.10" should be "3.09") IS applied in its corrected paragraph, which prints 3.09 -- so this is not a systematic artifact of how the document was read.
- **Assumptions:** None beyond the paper's own statements. The finding does not depend on resolving which mean carries which subscript: the erratum says the fatalism mean should read 3.53, and 3.53 is not among the three values printed, whichever position fatalism occupies. Caveat on provenance: this passage sits in a two-column region that the PDF text layer interleaves, scrambling the subscript labels; the digit strings 3.54, 3.67 and 3.90 are unambiguous, but the label-to-value mapping cannot be verified from the text layer, and the publisher XML for this article carries only the title and three tables, with no body text to reconcile against.
- **Consequence:** changes no significance decision; 1 stated claim affected -- No inferential conclusion depends on this descriptive mean, but a reader cannot determine which of 3.53 and 3.54 is now the value of record for Experiment 4's fatalism-condition manipulation check. (asserted, not computed)
- **Reproduce:** `metascience extract --pdf-path /mnt/c/Users/gregs/agent_for_forensic_metascience/eval/ground_truth/papers/10.3389--fpsyg.2019.02949/10.3389--fpsyg.2019.02949.pdf --first-page 2 --last-page 2`

### 3. Experiment 2 headline contrast: t of 2.02 irreconcilable with the B and SE printed beside it  [SUSPICIOUS | confidence: high]

**In plain terms.** For one of the two results the paper calls its main replication, the effect size and its margin of error, divided out, cannot produce the test statistic printed next to them -- not even allowing for rounding. The gap is small, and a single mistyped digit in any one of the three numbers would explain it. What makes it worth asking about is that this correction notice was issued partly to revise this very result's p-value from 0.03 to 0.04, and 0.03 is what the effect size and margin of error actually imply.

- **Location:** Corrected Experiment 2 Results paragraph two, negotiating-with-fate choice vs no-choice contrast
- **Reported:** "or choice [B = -0.20, SE = 0.09, t(194) = 2.02, p = 0.04, d = 0.29) conditions (see Figure 2). This result replicates the finding from Experiment 1." The corrigendum's own erratum note revised this p-value: "incorrectly reported as p = 0.05 and p = 0.03, respectively. The p-values should have been p = 0.03 and p = 0.04, respectively."
- **Computed:** t = B/SE = -0.20/0.09 = -2.222. Allowing the full rounding range of both printed values (B in [0.195, 0.205], SE in [0.085, 0.095]), the achievable magnitude interval is [2.053, 2.412]. The printed 2.02 falls below it. The p-value implied by the printed B and SE is 0.0274, which rounds to 0.03 -- the value the corrigendum changed away from. The reported p of 0.04 was NOT flagged: it sits inside its achievable interval [0.0168, 0.0415], though at the extreme upper edge.
- **As printed in the paper:** “or choice [B = -0.20, SE = 0.09, t(194) = 2.02, p = 0.04, d = 0.29) conditions (see Figure 2). This result replicates the finding from Experiment 1.” _(found in the PDF text layer)_
- **Assumptions:** That B and SE are the unstandardized coefficient and its standard error, so t = B/SE. This holds for 11 of the other 12 coefficients in the document, so it is the authors' own convention. All values read at two decimals as printed. No scale bound or external range was supplied.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The result stays significant at the 0.05 level on any reading, but this contrast is half of the sentence "the belief in negotiating with fate was stronger in the no-choice condition than in either the neutral or choice conditions ... This result replicates the finding from Experiment 1." (asserted, not computed)
- **Reproduce:** `metascience regression-batch --rows '[{"label":"Exp2 NWF choice vs no-choice","b":-0.20,"se":0.09,"reported_t":2.02,"reported_p":0.04,"df":194,"decimals_b":2,"decimals_se":2,"decimals_t":2,"decimals_p":2}]'`

### 4. Experiment 5 acceptance contrast: t of -1.81 irreconcilable with B = -0.22 and SE = 0.11  [SUSPICIOUS | confidence: high]

**In plain terms.** For the acceptance result in Experiment 5, dividing the reported effect by its reported margin of error gives exactly -2.00, but the paper prints -1.81 beside them. One of those three numbers must be a misprint. The p-value the paper reports is consistent with the -1.81, so the significance verdict is unaffected; what cannot be determined is which of the three printed figures is the correct one.

- **Location:** Corrected Experiment 5 Results paragraph three, acceptance negotiating-with-fate vs fatalism contrast
- **Reported:** "For acceptance, participants reported marginally greater acceptance of the event after negotiating with fate was activated compared to activating fatalism [B = -0.22, SE = 0.11, t(190) = -1.81, p = 0.07, d = 0.10]."
- **Computed:** t = B/SE = -0.22/0.11 = exactly -2.000. The achievable interval given two-decimal rounding of both inputs is [-2.143, -1.870]; the printed -1.81 falls outside it. Unlike five other flagged rows, the signs here agree, so this is a magnitude failure, not a sign convention. The reported p of 0.07 was NOT flagged: it lies inside its achievable interval, and t = -1.81 with df = 190 gives p = 0.072, so t and p are mutually consistent. The discrepancy is confined to the relationship between the coefficient, its standard error and the t.
- **As printed in the paper:** “For acceptance, participants reported marginally greater acceptance of the event after negotiating with fate was activated compared to activating fatalism [B = -0.22, SE = 0.11, t(190) = -1.81, p = 0.07, d = 0.10].” _(found in the PDF text layer)_
- **Assumptions:** That B and SE are the unstandardized coefficient and its standard error. All values read at two decimals as printed. Note that the neighbouring contrast in the same sentence prints SE = 0.14 with the same B = -0.22, and the adjacent acceptance row prints SE = 0.11 with B = -0.02, so a transposition between adjacent rows would account for it.
- **Consequence:** 1 stated claim affected -- The paper describes this as "marginally greater acceptance"; the effect and its standard error as printed would imply a stronger result than the reported t and p do, but which figure is the misprint cannot be determined, so whether any significance verdict changes is unknown. (asserted, not computed)
- **Reproduce:** `metascience regression-batch --rows '[{"label":"Exp5 Acceptance NWF vs fatalism","b":-0.22,"se":0.11,"reported_t":-1.81,"reported_p":0.07,"df":190,"decimals_b":2,"decimals_se":2,"decimals_t":2,"decimals_p":2}]'`

### 5. Experiment 5 erratum sentence that names an error but omits both the wrong and the corrected value  [SUSPICIOUS | confidence: high]

**In plain terms.** One of the corrections in this notice says a number was reported incorrectly but never says what the number was or what it should be, the sentence breaking off mid-clause. A reader has no way to act on it. Together with a garbled sentence elsewhere on the same page, this suggests the notice was not carefully proofread.

- **Location:** Page 2, Experiment 5 erratum note
- **Reported:** "Furthermore, the mean agreement with the biased scale across all conditions was in correctly provided as in reporting the t-test statistic when comparing the effects of activating negotiating with fate vs. personal control on positively reappraising the event [incorrectly reported as t(190) = 2.26, which should have been t(190) = -1.64]"
- **Computed:** The clause announces that a value "was in correctly provided as" and then supplies neither the erroneous value nor the corrected one, running directly into an unrelated clause about a t statistic. No corrective value is present anywhere in the surrounding text. This passage is in a clean single-column region of the page and the extraction is not in doubt. The same page also prints "we tested if there is a difference in the mean agreement with the biased scales differed across conditions".
- **Assumptions:** None beyond the paper's own text; this is a reading of printed literals and no forensic tool applies.
- **Consequence:** changes no significance decision; 1 stated claim affected -- One of the corrigendum's own stated corrections cannot be applied by a reader because the corrected value is absent from the text. (asserted, not computed)
- **Reproduce:** `metascience extract --pdf-path /mnt/c/Users/gregs/agent_for_forensic_metascience/eval/ground_truth/papers/10.3389--fpsyg.2019.02949/10.3389--fpsyg.2019.02949.pdf --first-page 2 --last-page 2`

### 6. Sample sizes for Experiments 1, 2 and 4 not reconcilable with the degrees of freedom reported for them  [SUSPICIOUS | confidence: high]

**In plain terms.** How many people took part in three of the six experiments cannot be pinned down. In Study 4 the education breakdown counts 139 people while the gender and religion breakdowns count 138, and the statistics reported for that experiment were computed on 139. Study 1's numbers imply one person fewer than the table lists, and Study 2's imply two or three fewer than the 200 stated. The other three experiments add up exactly. This matters more than a one-person discrepancy usually would, because the authors say they reprinted this very table in order to make the table and the text agree on sample size -- and for Study 4 it still does not.

- **Location:** Table 1 (all six study columns) against the corrected Results paragraphs for Experiments 1, 2 and 4
- **Reported:** Table 1 Study 4: gender 48 + 90 = 138; religion 68 + 22 + 21 + 17 + 10 + 0 = 138; education 2 + 14 + 42 + 18 + 46 + 15 + 2 + 0. Experiment 4 reports F(2,136) and t(135); Experiment 1 reports F(2,117) against a Study 1 total of 121; Experiment 2 reports t(194) against a Study 2 total of 200. The corrigendum's stated reason for reprinting Table 1 is "to ensure that the sample size reported in the text matched the table."
- **Computed:** Study 4's education column sums to 139, not the 138 given by both its gender and its religion blocks. For a three-group one-way ANOVA, df1 + df2 + 1 = N, so F(2,136) implies N = 139; with a covariate, t(135) + 4 parameters also implies N = 139. Two routes give 139 and two give 138. Experiment 1: F(2,117) implies N = 120 against Table 1's 121. Experiment 2: t(194) implies N = 197 with a three-parameter model or 198 with a covariate, against Table 1's 200. Experiments 3, 5 and 6 reconcile exactly (217, 194, 158), as does Experiment 5's regression df. Seventeen of the eighteen demographic column sums in Table 1 reconcile at zero tolerance; the Study 5 religion block that the corrigendum says it fixed now totals 194 correctly.
- **As printed in the paper:** “we found significant differences between conditions in the ease of the recall task used in the manipulation, F(2,117) = 10.19, p < 0.01” _(found in the PDF text layer)_
- **Assumptions:** That each manipulation-check F is a one-way ANOVA over three conditions (four in Experiment 6), which the reported df1 of 2 (and 3) confirms, and that the regression models contain an intercept, two condition dummies and at most one covariate -- which is what the text describes and what Experiments 4 and 5 obey exactly. The corrigendum explicitly corrects Experiment 3's df2 from 216 to 214 against N = 217, confirming N - 3 as the authors' own convention. Innocent explanations exist (listwise deletion of one case, a participant counted in demographics but dropped from one analysis) but none is stated.
- **Consequence:** changes no significance decision -- No individual significance verdict turns on one participant, but the analytic sample for Experiments 1, 2 and 4 cannot be determined from the document, and Study 4's is the table the corrigendum was issued to reconcile with the text. (asserted, not computed)
- **Reproduce:** `metascience summation-batch --rows '[{"values":[2,14,42,18,46,15,2,0],"expected_sum":138,"decimals":0,"tolerance":0,"description":"Study 4 education vs gender/religion total 138"},{"values":[2,136,1],"expected_sum":138,"decimals":0,"tolerance":0,"description":"Exp 4 F(2,136) df-implied N vs 138"},{"values":[135,4],"expected_sum":138,"decimals":0,"tolerance":0,"description":"Exp 4 t(135) + 4 params vs 138"},{"values":[2,117,1],"expected_sum":121,"decimals":0,"tolerance":0,"description":"Exp 1 F(2,117) df-implied N vs 121"},{"values":[194,4],"expected_sum":200,"decimals":0,"tolerance":0,"description":"Exp 2 t(194) + 4 params vs 200"},{"values":[2,214,1],"expected_sum":217,"decimals":0,"tolerance":0,"description":"Exp 3 reconciles"},{"values":[2,191,1],"expected_sum":194,"decimals":0,"tolerance":0,"description":"Exp 5 reconciles"},{"values":[3,154,1],"expected_sum":158,"decimals":0,"tolerance":0,"description":"Exp 6 reconciles"}]'`

### 7. Negative coefficients printed beside positive t statistics, inconsistently within single paragraphs  [SUSPICIOUS | confidence: high]

**In plain terms.** In five places the paper prints a negative effect next to a positive test statistic, which is arithmetically impossible if you take both at face value -- but the sizes match, so the authors are evidently dropping the minus sign from the test statistic. That would be an acceptable house style if it were applied consistently, and it is not: within the same paragraph some rows keep the minus sign and others drop it. Nothing about the paper's conclusions changes, because the direction of every effect is stated in words alongside.

- **Location:** Corrected Results paragraphs for Experiments 2, 4 and 5
- **Reported:** Five coefficients print a negative B with a positive t: Experiment 2 negotiating-with-fate neutral contrast (B = -0.24, t = 2.18); Experiment 4 identify-own-behavior vs fatalism (B = -0.45, t = 1.91) and vs personal control (B = -0.52, t = 2.26); Experiment 4 fatalism vs personal control (B = -0.05, t = 0.24); Experiment 5 positive reappraisal vs fatalism (B = -0.31, t = 2.26).
- **Computed:** In all five rows the magnitude |t| falls inside the interval implied by |B|/SE at the printed precision, so only the sign is discordant. The convention is not applied consistently: within Experiment 2's single paragraph, the personal-control rows print B and t both negative while the negotiating-with-fate rows print B negative and t positive, and within Experiment 5's paragraph the positive-reappraisal-vs-fatalism row prints t positive while the acceptance-vs-fatalism row prints t negative for a coefficient of the same sign.
- **As printed in the paper:** “the belief in negotiating with fate was stronger in the no-choice condition than in either the neutral [B = -0.24, SE = 0.11, t(194) = 2.18, p = 0.03, d = 0.29]” _(found in the PDF text layer)_
- **Assumptions:** That reporting |t| rather than signed t is the intended convention. The surrounding prose states the direction of each effect unambiguously in words, so no reader is misled about direction.
- **Consequence:** changes no significance decision -- No conclusion changes; the direction of every affected effect is stated in words in the adjacent text. (asserted, not computed)
- **Reproduce:** `metascience regression-batch --rows '[{"label":"Exp2 NWF neutral","b":-0.24,"se":0.11,"reported_t":2.18,"reported_p":0.03,"df":194,"decimals_b":2,"decimals_se":2,"decimals_t":2,"decimals_p":2},{"label":"Exp4 idb vs fatalism","b":-0.45,"se":0.23,"reported_t":1.91,"reported_p":0.06,"df":135,"decimals_b":2,"decimals_se":2,"decimals_t":2,"decimals_p":2},{"label":"Exp4 idb vs personal control","b":-0.52,"se":0.23,"reported_t":2.26,"reported_p":0.03,"df":135,"decimals_b":2,"decimals_se":2,"decimals_t":2,"decimals_p":2},{"label":"Exp4 fatalism vs personal control","b":-0.05,"se":0.22,"reported_t":0.24,"reported_p":0.81,"df":90,"decimals_b":2,"decimals_se":2,"decimals_t":2,"decimals_p":2},{"label":"Exp5 posreap vs fatalism","b":-0.31,"se":0.14,"reported_t":2.26,"reported_p":0.03,"df":190,"decimals_b":2,"decimals_se":2,"decimals_t":2,"decimals_p":2}]'`

## What we could NOT check

- **Table 3 (correlations between fate beliefs by condition), cited in the corrected Experiment 1 Results paragraph** — Referenced by the corrigendum but not reprinted in it. The XML index lists only Tables 1, 2 and 4, and all four PDF pages contain only those three. The table exists in the original article (Front. Psychol. 10:2354), which is outside this document. No correlation matrix could be checked for values outside [-1, 1], positive-definiteness, or internal consistency.
- **Figures 2 and 4, cited in the corrected Experiment 2 and Experiment 4 Results paragraphs** — Cited in the corrected text ("see Figure 2", "see Figure 4") but this corrigendum contains no figures at all; all four pages are text and tables. The figures live in the original article. Any statistic appearing only there is outside this review.
- **Tables 2 and 4: 30 of the 39 estimate/confidence-interval triples** — Both tables place the mean, the SD and the two CI bounds in four separate columns, so every cell arrives as a bare scalar and the batch table checker correctly refused all of them; reassembled into estimate(CI) form it typed them all but reported no check defined for that cell kind on Likert data. check_estimate_ci has no batch form. Nine triples were checked individually -- the three values the corrigendum claims to have corrected plus their row-mates as comparators -- and all nine passed. The other thirty are unchecked.
- **Manipulation-check ANOVAs for Experiments 3, 4 and 5: F(2,214) = 1.45, F(2,136) = 2.89, F(2,191) = 6.10** — Recomputing an F from group statistics requires per-group means, SDs and ns. The corrigendum prints the three group means for each but no SDs and no per-cell sample sizes. These F values were verified only as F-to-p conversions, which does not test whether the F is consistent with the means it is printed beside.
- **Five explicit no-difference claims: Experiment 2 fatalism (p = 0.29, p = 0.77) and personal control (p = 0.10, p = 0.11); Experiment 5 acceptance vs personal control (p = 0.84)** — Testing whether a null result survives its own interval requires a confidence interval, and the corrigendum prints B and SE for these coefficients but no CIs. Constructing them by hand would be arithmetic outside the validated tool surface. The largest effect these intervals still permit is therefore unknown, and "did not differ" should not be read as "no effect". No smallest effect size of interest is stated anywhere, so equivalence could not have been claimed even with intervals.
- **Experiment 6 correlation r = 0.33, p < 0.001, n = 158** — No tool in the validated set converts a Pearson correlation and its sample size to a p-value, so the thresholded p could not be recovered and checked for concealed extremity the way F(2,117) = 10.19 could.
- **Per-arm sample sizes for all six experiments** — The corrigendum reports only total N per study, via Table 1, and never states how many participants fell in each condition. Without per-arm ns, no granularity test could be applied to any cell of Table 2 or Table 4. The per-group n of 65 used in the two effect-size recomputations is an even split of Experiment 5's N = 194 and is an assumption; Cohen's d is essentially insensitive to it.
- **GRIM / GRIMMER / SPRITE / DEBIT on Tables 2 and 4** — Deliberately not run. Every mean in these tables averages 8, 10 or more Likert items, so the granularity of a group mean is far finer than 1/n and the tests have no power; and the response-scale bounds are never stated in the corrigendum, so any range would have been invented. Age in Table 1 is a continuous measure in years and is outside GRIM's applicability. Running these would have manufactured impossibilities out of ordinary numbers.
- **A-priori power analysis** — No power calculation, target effect size or sample-size justification appears anywhere in this corrigendum, so there were no inputs to reproduce. Whether the original article states one could not be determined from this document.
- **Baseline-similarity tests on Table 1** — Not applicable rather than skipped. Table 1 reports demographics for six separate samples side by side, not baseline characteristics of randomised arms within one trial, and no baseline p-values are reported anywhere. There is no allocation to test for excess similarity, so the uniformity checks that apply to trial baseline tables do not bite here.
- **The original article, Au & Savani (2019), Front. Psychol. 10:2354** — Only the corrigendum was supplied. Everything this document does not reprint -- the methods, the response scales and their bounds, the model specifications, Table 3, all figures, and any data availability statement -- is outside this review. The corrigendum states "the original article has been updated", so the version of record now differs from both documents.

## Questions for the authors

_Each of these is answerable from what the authors already have. None presupposes an error on their part: an inconsistency is far more often a reporting slip, or a mistake by this tool in reading the number off the page, than anything else._

1. The Experiment 4 erratum states that "M_Fatalism = 3.54" was incorrectly provided instead of "M_Fatalism = 3.53", but the corrected Results paragraph printed immediately below it reads "[M_Fatalism = 3.54, M_PersonalControl = 3.67, M_NegotiatingWithFate = 3.90; F(2,136) = 2.89, p = 0.06]". Which value now stands for the fatalism condition, 3.53 or 3.54?
   <sub>Would resolve: Settles the headline contradiction and tells a reader whether the notice's other corrections were applied to the reprinted text.</sub>
2. In the Experiment 5 erratum the sentence beginning "Furthermore, the mean agreement with the biased scale across all conditions was in correctly provided as ..." does not give either the erroneous value or the corrected one. What value was affected, and what should it read?
   <sub>Would resolve: One stated correction is currently unusable; only the authors can supply the missing figures.</sub>
3. Two reported coefficients cannot be reconciled with the t statistics printed beside them: Experiment 2's negotiating-with-fate choice contrast (B = -0.20, SE = 0.09, t(194) = 2.02, where B/SE = 2.22) and Experiment 5's acceptance vs fatalism contrast (B = -0.22, SE = 0.11, t(190) = -1.81, where B/SE = -2.00). For each, which of B, SE and t is the correct figure? We note the corrigendum revised the first of these p-values from 0.03 to 0.04, and that B = -0.20 with SE = 0.09 implies p = 0.027.
   <sub>Would resolve: Resolves the two genuine arithmetic inconsistencies among the thirteen reported coefficients, one of which sits on the paper's stated replication claim.</sub>
4. For Study 4, Table 1's education block sums to 139 while its gender block (48 + 90) and religion block (68 + 22 + 21 + 17 + 10 + 0) each sum to 138, and Experiment 4 reports F(2,136) and t(135), both of which imply N = 139. What was the analytic sample size for Experiment 4, and were any participants excluded? Relatedly, Experiment 1 reports F(2,117) against a Study 1 total of 121, and Experiment 2 reports t(194) against a Study 2 total of 200 -- could you confirm the sample sizes and, for Experiment 2, the covariates entered in the regression model?
   <sub>Would resolve: Three of the six experiments have degrees of freedom that do not reconcile with Table 1; the other three reconcile exactly, so this is not a general reporting convention.</sub>
5. Experiment 2 reports six regression contrasts on the same 200 participants and Experiment 5 reports four on the same 194, with no correction for multiple comparisons mentioned. Were these families pre-specified, and would the conclusions be stated the same way under a correction for the number of contrasts reported? For reference, the two significant Experiment 2 results (p = 0.03, p = 0.04) and the one significant Experiment 5 result (p = 0.03) do not survive Bonferroni, Holm, Benjamini-Hochberg or Benjamini-Yekutieli within their own families.
   <sub>Would resolve: The corrigendum asserts that its corrections "do not change the scientific conclusions of the article in any way"; this establishes how much of the original conclusion the reported p-values support in the first place.</sub>

## Limitations

- This agent reads text and tables only. It does not see figures. This document contains no figures at all, but it cites Figures 2 and 4 in the original article, and nothing shown only there could be examined.
- The publisher XML for this article carries only the title and the three tables -- no body text. Every statistic in the corrected Results and Methods paragraphs therefore rests on a single extraction, the PDF text layer, with no second source to reconcile against. The three tables were cross-checked between XML and PDF and agree exactly, cell for cell.
- One passage, Experiment 4's corrected mean-agreement sentence, sits in a two-column region that the PDF text layer interleaves badly, scrambling the subscript labels around the three means. The digit strings 3.54, 3.67 and 3.90 are unambiguous, but which subscript attaches to which value cannot be verified. The headline finding was constructed so as not to depend on that mapping.
- This is a four-page correction notice, not the article it corrects. Judgements about model specification, measurement scales and analytic decisions are made from what this document prints, which is partial by design. Several findings would likely be resolved by the original article's methods section.
- No raw data are referenced anywhere in this document, so none of the irreconcilable statistics can be settled from what is published here. This is normal for a corrigendum and is not itself a criticism.
- Whether the six Experiment 2 contrasts and the four Experiment 5 contrasts each constitute one family for multiplicity purposes is a judgement, not a computation. A reader who regards each belief scale or each coping outcome as a separate pre-specified family would reach a different conclusion about how many results survive.
- No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.

## Coverage

- **Statistics found:** 340; **checked:** 124
- **Tools run:** extract_xml, get_table, extract_pdf, check_summation_batch, check_regression_batch, statcheck, stalt_check, check_table, detect_duplication, check_estimate_ci, multiplicity_report, check_effect_plausibility, flag_round_n
- **Tables checked:** Table 1 (Demographic information for all six samples) -- 114 data cells; all 18 demographic column sums checked at zero tolerance; cross-verified XML against PDF, Table 2 (Means, SDs and 95% CIs for the three lay beliefs, Experiments 1-2) -- 72 numbers, 18 estimate/CI triples typed, 3 checked directly; cross-verified XML against PDF, Table 4 (Means, SDs and 95% CIs for Experiments 3-6) -- 84 numbers, 21 estimate/CI triples typed, 6 checked directly; cross-verified XML against PDF
- **Where a check and this review disagreed:** 1 sweep finding recorded a severity the validated check behind it did not return (0 upgraded, 1 downgraded). 1 sits on a sweep finding no entry in this report cites, so this line is the only place it appears.

## What each check does

One entry per check that ran on this paper. The **assumptions** are the conditions under which its verdict holds; where one is unmet the verdict is capped, not merely caveated.

### `check_effect_plausibility` — probabilistic

Places an effect size against cited field benchmarks; flags unusual, never impossible.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- Benchmarks carry a provenance label. Only social_psychology's percentiles trace to a published table (Lovakov & Agadullina 2021, Table 1); the rest are uncited estimates and say so in the result. psychology_general is worse than uncited -- it cites an OSC 2015 correlation (r = .40) and uses the number as a Cohen's d median, which converts to d = 0.87, so it over-flags.
- Field benchmarks are distributions of PUBLISHED effects, themselves inflated by publication bias.
- Dispersion inputs must be SDs; an SEM read as an SD inflates d by sqrt(n).
- d from group statistics assumes independent groups and pooled-SD standardisation.
- An effect can be improbable but never impossible, so this caps at `suspicious`.

### `check_estimate_ci` — probabilistic

Reconciles a point estimate with its own CI and reported p on the correct scale.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- CIs are assumed Wald-type: symmetric on the linear scale, or on the LOG scale for OR/RR/HR/IRR -- pass `measure`.
- Exact, profile and bootstrap CIs are legitimately asymmetric and can fail the midpoint check innocently.
- Alternative confidence levels are tried before a 'wrong p' is reported; p is recovered by normal approximation.
- A p that cannot be placed against alpha at its own printed precision is not classified.
- A threshold p ('P < .001', passed with `reported_p_operator`) is an interval claim: flagged only when the bound is unreachable at the stated level AND at the one common level that could still rescue it.

### `check_regression_batch` — probabilistic

Runs the t = B/SE coefficient check over every row of a regression table in one call.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- Same premises as check_regression per row.
- Pass per-row decimals; omitted, each row falls back to the widest plausible interval -- safe but blind.
- A row with neither reported_t nor df is indeterminate; the aggregate is the worst row, and an all-unevaluated batch is never `consistent`.

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

### `flag_round_n` — probabilistic

Triage flag for several distinct sample sizes that are all suspiciously round.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- A base-rate heuristic: fabricated papers over-represent round Ns, but so do honest recruitment targets.
- Needs at least three reported sizes with at least two distinct before it says anything.
- Ceiling `suspicious`: a weak signal that escalates only alongside stronger findings.

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

### `stalt_check` — probabilistic

Checks a recomputed p against the threshold the paper printed for it.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The recomputed p must be of the SAME test the printed threshold describes.
- The threshold is read as an upper-bound claim: any p at or below it is consistent.
- A factor-of-two overshoot is tolerated as a one- versus two-tailed artefact.
- Escalation scales with the size of the overshoot.

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

## What this document is

Au and Savani (2020) is a four-page correction notice to a six-experiment social-psychology paper (Front. Psychol. 10:2354) arguing that a lay belief in "negotiating with fate" strengthens under constraint and promotes adaptive responses to uncontrollable negative events. The corrigendum is not the article. It reprints Tables 1, 2 and 4 in corrected form, reprints seven Results and Methods paragraphs, lists about a dozen individual values it says were wrong, and closes: "The authors apologize for these errors and state that these corrections do not change the scientific conclusions of the article in any way."

That closing sentence sets the standard against which this document should be read, and it is the right standard. A correction notice is judged on whether it corrects.

## What verifies

A good deal, and it should be said plainly before the problems. Both extractions of Tables 1, 2 and 4 -- the publisher XML and the PDF -- agree cell for cell, so nothing below turns on a disputed reading of a table. Seventeen of the eighteen demographic column sums in Table 1 reconcile exactly at zero tolerance, including the Study 5 religion block whose missing "Unreported = 1" row was the stated reason for reprinting the table. All three of the corrigendum's table corrections were applied and each reconciles with its own confidence interval: Table 2's Study 1 negotiating-with-fate mean now reads 4.41, Table 4's Study 4 personal-control mean 3.33, and Table 4's Study 5 positive-reappraisal upper bound 2.98. Across 594 cross-sample comparisons of 39 mean/SD pairs from six independent samples there is not one identical pair -- no sign of recycled summary statistics. Sample sizes are unround. The largest effect anywhere in the paper is d = 0.47, and the headline d = 0.29 sits just below the social-psychology median of 0.36 (Lovakov & Agadullina 2021, 12,170 effects), so there is no implausibly large effect to explain. Of eighteen reported NHST results, none is a decision error, and every p-value the corrigendum says it corrected recomputes correctly -- F(2,214) = 1.45 gives 0.237, F(2,136) = 2.89 gives 0.059, F(2,191) = 6.10 gives 0.0027, F(3,154) = 0.944 gives 0.421. Eleven of thirteen regression coefficients reconcile with their test statistics, including both t values the corrigendum itself revised.

## Where the sweep was moved

Three of the numeric sweep's flags do not survive scrutiny and are not carried forward.

The residual statcheck hit -- t(190) = 2.26 printed with p = 0.03 where the exact value is 0.024956 -- sits 0.000044 below the rounding boundary, on a t that is itself rounded to two decimals. The identical t(135) = 2.26 elsewhere in the paper gives 0.025423 and rounds correctly. That is a boundary artifact, not evidence.

The sweep raised the apparent incoherence of the reported Cohen's d values, in particular Experiment 5 assigning d = 0.28 to a contrast with |t| = 1.64 and d = 0.10 to one with |t| = 1.81 at the same degrees of freedom. Recomputing from Table 4's raw group statistics resolves it: acceptance differs by 3.30 versus 3.22, giving Hedges' g = 0.12 against the reported 0.10, while positive reappraisal differs by 2.80 versus 2.57, giving g = 0.30 against the reported 0.39. The d values track the raw group means; the t statistics track the covariate-adjusted coefficients. Those need not move together, and the pattern is explained.

The sweep also asked a human to look at Table 4's Study 4 personal-control cell, where the interval-implied centre is 3.355 against a printed 3.33 while both row-mates are exactly symmetric. Re-run individually, all three cells pass. It is not reportable.

One sweep claim is narrowed rather than dropped. On the Experiment 5 acceptance contrast the sweep held that both the t and the p lie outside their achievable intervals; the p does not, and only the t discrepancy is carried forward.

## What the balance leaves

The findings that survive divide into two kinds. One is a set of ordinary reporting inconsistencies -- two coefficients irreconcilable with their own t statistics, three experiments whose degrees of freedom do not match Table 1, a sign convention applied unevenly. Individually each has an innocent explanation, and a single mistyped digit accounts for most of them. What gives them weight here is where they sit: in a document whose sole purpose was to catch exactly this class of error, and which reprints the affected paragraphs as authoritative.

The other is the multiplicity arithmetic, which is a statement about the original analysis rather than about the corrections. It is the finding with the largest bearing on what the paper claims, and it is deterministic: the three results the paper calls significant in Experiments 2 and 5 are the only significant results among ten reported contrasts, and none survives correction within its own family under any of the four standard methods. Uncorrected testing is normal practice in this literature, and this is not an accusation. It does mean that the sentence "This result replicates the finding from Experiment 1" is carrying more weight than the reported p-values of 0.03 and 0.04 can bear once the five and three companion tests reported beside them are counted.

None of this is arithmetically impossible, and nothing here suggests fabrication. The tables are clean, the effect sizes are unremarkable, and there is no duplication. What is in doubt is whether the corrected record can be relied on: the notice does not apply one of its own corrections, leaves another with the value missing, and moves a headline p-value away from what the coefficient and standard error printed beside it imply. Several of the discrepancies would be settled in a sentence by the authors, and the questions below are framed so they can be.

The reported statistics mostly verify, but this correction notice does not reliably correct, and I would not treat its numbers as settled without the authors' clarification.

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
