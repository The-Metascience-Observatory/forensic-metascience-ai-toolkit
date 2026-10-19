# Forensic review -- Romano et al. 2025

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## Momentary Mediational Associations Among Affect, Emotion Dysregulation, and Different Types of Loss of Control Eating Among Adults With Binge Eating Disorder
*Kelly A. Romano, Carol B. Peterson, Glen Forester, Joseph A. Wonderlich, Stephen A. Wonderlich, Scott E. Engel, Ross D. Crosby. The International Journal of Eating Disorders. 2025. doi:10.1002/eat.24415*

**Design:** Secondary analysis of baseline ecological momentary assessment (EMA) data from a multisite RCT; six two-level multilevel structural equation models (MSEM), 1-1-1 mediation structure

<sub>Analysed as `10.1002--eat.24415`</sub>

> **SUSPICIOUS** — Two of the paper's five significant mediation results -- including one of the four loss-of-control eating dimensions it concludes are mediated -- fail every standard correction for the 24 mediation tests it ran without applying one.
>
> **In plain terms:** The researchers ran twenty-four separate tests of whether difficulty managing emotions explains the link between mood and losing control over eating, and treated any result below the usual one-in-twenty cutoff as real. When that many tests are run at once, roughly one apparent discovery is expected by chance alone. Applying any of the standard adjustments for this, two of their five positive results drop out: one of the four eating behaviours they conclude is explained by emotion difficulties, and the single result about differences between people rather than within them. Their three strongest findings hold up comfortably under even the strictest adjustment.
>
> **Evidence:** Table 2 footnote: "Bold text is used to reflect significant effects, defined as p < 0.05". Twelve within-person indirect effects (p = .001, .070, .026, .122, .154, .233, .001, .067, .858, .859, .001, .065) and twelve between-person indirect effects (p = .052, .728, .210, .740, .060, .733, .164, .727, .380, .689, .017, .725), no correction stated anywhere. Within-person: 4 significant uncorrected, 3 survive (Bonferroni .0042, Holm .005, BH .0125, BY .0040) -- 'difficulties resisting eating' at p = .026 survives none. Between-person: 1 significant uncorrected (p = .017), 0 survive.
> **Rests on:** a constraint the paper itself states
> **Reproduce:** no runnable command -- the review's command used an option this tool does not have. The finding's own numbers are above; re-derive from those.

**Verdict: questionable** (confidence: high)

> **Table coverage:** 21 of 110 checkable cells were checked cell by cell, and 75 further table rows were checked in batch by check_regression_batch, check_summation_batch. The two counts are of different things and are not added: the batch tools report rows, not the cell identifiers this census uses, so the true combined coverage is somewhere between 75 and 96 of 110. A further 8 per-cell checks ran (`absence_of_evidence`, `check_count_percent`, `detect_duplication`) and report no cell ids at all, so the top of that range is a floor rather than a ceiling.

## Provenance of the analysis

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

1 study/studies, 21 variables, 64 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| s1 | Baseline EMA sub-study of the ICAT-BED vs CBTgsh multisite RCT (NCT0204349 as printed) | secondary_analysis | 107 | Momentary EMA observation (level 1) nested within participant (level 2); 3131 completed surveys across 107 participants | yes |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Baseline age | ratio | continuous | range not stated | years | measured | none -- not integer-valued | medium |
| Baseline BMI | ratio | continuous | range not stated | kg/m2 | ratio: weight and height | none -- not integer-valued | high |
| Baseline depressive symptoms (BDI total score) | ratio | discrete | range not stated | - | sum of items: Beck's Depression Inventory items | GRIM (needs stated max) | low |
| Baseline ED-related clinical impairment (CIA total score) | ratio | discrete | range not stated | - | sum of items: Clinical Impairment Assessment items | GRIM (needs stated max) | low |
| Baseline trait emotion dysregulation (DERS total score) | ratio | discrete | range not stated | - | sum of items: Difficulties in Emotion Regulation Scale items | GRIM (needs stated max) | low |
| Baseline ED pathology (EDE global score) | interval | continuous | range not stated | - | mean of items: mean of four EDE subscale scores, each itself a mean of 0-6 items | none -- not integer-valued | medium |
| Gender identity | nominal | discrete | Men; Women; Transgender women; Transgender men; Other gender identity | - | measured | percentage GRIM on cell counts | high |
| Highest level of education | ordinal | discrete | 8th grade education or less; Some high school; Completed high school; Some college; Associate's degree; Bachelor's degree; Some graduate school; Graduate level degree; Not reported | - | measured | percentage GRIM on cell counts | high |
| Race/ethnicity | nominal | discrete | White; Hispanic; Asian; Black; American Indian or Alaska Native; Not reported | - | measured | percentage GRIM on cell counts | high |
| Momentary negative affect (latent factor) | ordinal | discrete | 1-5 (integers) | - | other: latent factor from 5 PANAS/POMS negative affect items (afraid, nervous, ashamed, sad, hostile), each 1-5; indicators lagged twice (t-2) | none -- composite granularity is 1/(items x n) | high |
| Momentary positive affect (latent factor) | ordinal | discrete | 1-5 (integers) | - | other: latent factor from 4 PANAS positive affect items (determined, attentive, inspired, active), each 1-5; indicators lagged twice (t-2) | none -- composite granularity is 1/(items x n) | high |
| Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | ordinal | discrete | 1-5 (integers) | - | other: latent factor from S-DERS Modulate subscale items, each 1-5; indicators lagged once (t-1) | none -- composite granularity is 1/(items x n) | high |
| LOC eating: general feeling of losing control while eating | ordinal | discrete | 1-5 (integers) | - | measured | GRIM, GRIMMER, SPRITE | high |
| LOC eating: difficulties resisting eating | ordinal | discrete | 1-5 (integers) | - | measured | GRIM, GRIMMER, SPRITE | high |
| LOC eating: difficulties stopping eating after starting | ordinal | discrete | 1-5 (integers) | - | measured | GRIM, GRIMMER, SPRITE | high |
| LOC eating: feeling driven or compelled to eat | ordinal | discrete | 1-5 (integers) | - | measured | GRIM, GRIMMER, SPRITE | high |
| LOC eating: not paying attention to one's eating | ordinal | discrete | 1-5 (integers) | - | measured | GRIM, GRIMMER, SPRITE | high |
| LOC eating: feeling disconnected while eating | ordinal | discrete | 1-5 (integers) | - | measured | GRIM, GRIMMER, SPRITE | high |
| Survey number of the day (statistical control) | ordinal | discrete | 1-6 (integers) | - | measured | percentage GRIM on cell counts | high |
| EMA survey compliance | ratio | discrete | 0-100 (integers) | percent | percentage: 3131 completed surveys / 4494 possible surveys | percentage GRIM | high |
| Correlation between negative urgency and emotion dysregulation | interval | continuous | -1 to 1 | - | other: Pearson correlation in the present sample | none -- not integer-valued | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Table 2, Model 1, within-person indirect effect (NA) | mixed_model | LOC eating: general feeling of losing control while eating (likert_item) | Momentary negative affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 1, between-person indirect effect (NA) | mixed_model | LOC eating: general feeling of losing control while eating (likert_item) | Momentary negative affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 1, within-person indirect effect (PA) | mixed_model | LOC eating: general feeling of losing control while eating (likert_item) | Momentary positive affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 1, between-person indirect effect (PA) | mixed_model | LOC eating: general feeling of losing control while eating (likert_item) | Momentary positive affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 2, within-person indirect effect (NA) | mixed_model | LOC eating: difficulties resisting eating (likert_item) | Momentary negative affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 2, between-person indirect effect (NA) | mixed_model | LOC eating: difficulties resisting eating (likert_item) | Momentary negative affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 2, within-person indirect effect (PA) | mixed_model | LOC eating: difficulties resisting eating (likert_item) | Momentary positive affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 2, between-person indirect effect (PA) | mixed_model | LOC eating: difficulties resisting eating (likert_item) | Momentary positive affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 3, within-person indirect effect (NA) | mixed_model | LOC eating: difficulties stopping eating after starting (likert_item) | Momentary negative affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 3, between-person indirect effect (NA) | mixed_model | LOC eating: difficulties stopping eating after starting (likert_item) | Momentary negative affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 3, within-person indirect effect (PA) | mixed_model | LOC eating: difficulties stopping eating after starting (likert_item) | Momentary positive affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 3, between-person indirect effect (PA) | mixed_model | LOC eating: difficulties stopping eating after starting (likert_item) | Momentary positive affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 4, within-person indirect effect (NA) | mixed_model | LOC eating: feeling driven or compelled to eat (likert_item) | Momentary negative affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 4, between-person indirect effect (NA) | mixed_model | LOC eating: feeling driven or compelled to eat (likert_item) | Momentary negative affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 4, within-person indirect effect (PA) | mixed_model | LOC eating: feeling driven or compelled to eat (likert_item) | Momentary positive affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 4, between-person indirect effect (PA) | mixed_model | LOC eating: feeling driven or compelled to eat (likert_item) | Momentary positive affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 5, within-person indirect effect (NA) | mixed_model | LOC eating: not paying attention to one's eating (likert_item) | Momentary negative affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 5, between-person indirect effect (NA) | mixed_model | LOC eating: not paying attention to one's eating (likert_item) | Momentary negative affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 5, within-person indirect effect (PA) | mixed_model | LOC eating: not paying attention to one's eating (likert_item) | Momentary positive affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 5, between-person indirect effect (PA) | mixed_model | LOC eating: not paying attention to one's eating (likert_item) | Momentary positive affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 6, within-person indirect effect (NA) | mixed_model | LOC eating: feeling disconnected while eating (likert_item) | Momentary negative affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 6, between-person indirect effect (NA) | mixed_model | LOC eating: feeling disconnected while eating (likert_item) | Momentary negative affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 6, within-person indirect effect (PA) | mixed_model | LOC eating: feeling disconnected while eating (likert_item) | Momentary positive affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 6, between-person indirect effect (PA) | mixed_model | LOC eating: feeling disconnected while eating (likert_item) | Momentary positive affect (latent factor), Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | 107 | none | none reported |
| Table 2, Model 1, within-person direct effect Emotion Dysregulation -> LOC eating | mixed_model | LOC eating: general feeling of losing control while eating (likert_item) | Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | ? | none | none reported |
| Table 2, Model 1, between-person direct effect Emotion Dysregulation -> LOC eating | mixed_model | LOC eating: general feeling of losing control while eating (likert_item) | Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | ? | none | none reported |
| Table 2, Model 2, within-person direct effect Emotion Dysregulation -> LOC eating | mixed_model | LOC eating: difficulties resisting eating (likert_item) | Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | ? | none | none reported |
| Table 2, Model 2, between-person direct effect Emotion Dysregulation -> LOC eating | mixed_model | LOC eating: difficulties resisting eating (likert_item) | Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | ? | none | none reported |
| Table 2, Model 3, within-person direct effect Emotion Dysregulation -> LOC eating | mixed_model | LOC eating: difficulties stopping eating after starting (likert_item) | Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | ? | none | none reported |
| Table 2, Model 3, between-person direct effect Emotion Dysregulation -> LOC eating | mixed_model | LOC eating: difficulties stopping eating after starting (likert_item) | Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | ? | none | none reported |
| Table 2, Model 4, within-person direct effect Emotion Dysregulation -> LOC eating | mixed_model | LOC eating: feeling driven or compelled to eat (likert_item) | Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | ? | none | none reported |
| Table 2, Model 4, between-person direct effect Emotion Dysregulation -> LOC eating | mixed_model | LOC eating: feeling driven or compelled to eat (likert_item) | Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | ? | none | none reported |
| Table 2, Model 5, within-person direct effect Emotion Dysregulation -> LOC eating | mixed_model | LOC eating: not paying attention to one's eating (likert_item) | Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | ? | none | none reported |
| Table 2, Model 5, between-person direct effect Emotion Dysregulation -> LOC eating | mixed_model | LOC eating: not paying attention to one's eating (likert_item) | Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | ? | none | none reported |
| Table 2, Model 6, within-person direct effect Emotion Dysregulation -> LOC eating | mixed_model | LOC eating: feeling disconnected while eating (likert_item) | Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | ? | none | none reported |
| Table 2, Model 6, between-person direct effect Emotion Dysregulation -> LOC eating | mixed_model | LOC eating: feeling disconnected while eating (likert_item) | Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) | ? | none | none reported |
| Table 2, Models 1-6, within-person direct effect Negative Affect -> Emotion Dysregulation (identical across all six models) | mixed_model | Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) (likert_composite) | Momentary negative affect (latent factor) | ? | none | none reported |
| Table 2, Models 1-6, between-person direct effect Negative Affect -> Emotion Dysregulation | mixed_model | Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) (likert_composite) | Momentary negative affect (latent factor) | ? | none | none reported |
| Table 2, Models 1-6, within-person direct effect Positive Affect -> Emotion Dysregulation | mixed_model | Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) (likert_composite) | Momentary positive affect (latent factor) | ? | none | none reported |
| Table 2, Models 1-6, between-person direct effect Positive Affect -> Emotion Dysregulation | mixed_model | Momentary emotion dysregulation (S-DERS Modulate subscale, latent factor) (likert_composite) | Momentary positive affect (latent factor) | ? | none | none reported |
| Table 2, Model 1, within-person direct NA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 1, between-person direct NA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 1, within-person direct PA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 1, between-person direct PA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 2, within-person direct NA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 2, between-person direct NA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 2, within-person direct PA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 2, between-person direct PA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 3, within-person direct NA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 3, between-person direct NA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 3, within-person direct PA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 3, between-person direct PA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 4, within-person direct NA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 4, between-person direct NA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 4, within-person direct PA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 4, between-person direct PA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 5, within-person direct NA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 5, between-person direct NA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 5, within-person direct PA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 5, between-person direct PA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 6, within-person direct NA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 6, between-person direct NA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 6, within-person direct PA -> LOC | mixed_model | ? | - | ? | none | none reported |
| Table 2, Model 6, between-person direct PA -> LOC | mixed_model | ? | - | ? | none | none reported |

_64 of 64 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. One of four claimed mediated eating dimensions does not survive correction for its own test family  [SUSPICIOUS | confidence: high]

**In plain terms.** Testing many things at once makes lucky results likelier, so researchers usually tighten the bar. These authors tested twelve versions of their main idea and used the ordinary bar for each. Three of their four positive results are strong enough that no reasonable tightening would remove them. The fourth -- difficulty resisting eating -- is not, yet it is listed alongside the others in the results and again in the discussion as something they showed. That one claim is weaker than the paper presents it as being; the other three are as strong as claimed.

- **Location:** Table 2, within-person Indirect effects rows, Models 1-6; Results 'Indirect Effects' paragraph; Discussion 'Variations Across LOC Eating Dimensions'
- **Reported:** The Results state: "There were also significant indirect effects at the within-person -- but not between-person -- level among the negative affect, emotion dysregulation, and (separately) general sense of LOC while eating, difficulties resisting eating, and feeling driven/compelled to eat factors (beta = 0.02-0.03)." Table 2 footnote defines significance as p < 0.05. No correction for multiple comparisons is stated anywhere in the paper.
- **Computed:** Twelve within-person indirect-effect tests on the same 107 participants. Family-wise error rate up to 46.0%; about 0.6 false positives expected by chance. Four significant uncorrected; three survive under all four methods (Bonferroni .00417, Holm .005, Benjamini-Hochberg .0125, Benjamini-Yekutieli .00403). 'Difficulties resisting eating' at p = .026 exceeds every threshold. n_claims_lost_to_correction = 1; surviving interval 3 to 3.
- **As printed in the paper:** “Note: Bold text is used to reflect significant effects, defined as p < 0.05” _(found in a table)_
- **Assumptions:** Family defined as the twelve within-person indirect effects (6 outcomes x 2 affect predictors) estimated on one sample -- a judgement, not a fact of the paper. FWER assumes independence and is an upper bound; the six LOC outcomes are measured on the same subjects and are correlated, which is why Benjamini-Yekutieli is the appropriate FDR method here, and it also keeps only three. The exploratory reverse-pathway models described in the Results add at least twelve further indirect-effect tests whose numbers appear only in Data S1, so this family count is a floor.
- **Consequence:** 1 stated claim affected -- 'Difficulties resisting eating' is named in the Results and repeated in the Discussion as one of the four dimensions emotion dysregulation was found to mediate, and at p = .026 it crosses the paper's own alpha only without correction. The mediation effect for 'difficulties resisting eating' (p = .026) does not survive any of the four corrections, yet it is named in the abstract and conclusions as one of the dimensions emotion dysregulation was found to mediate. Computed from 1 result(s) significant uncorrected do not survive correction (a correction the paper did not apply, over a family we chose). (computed)
- **Reproduce:** no runnable command -- the review's command used an option this tool does not have. The finding's own numbers are above; re-derive from those.

### 2. Sole between-person mediation claim survives none of four corrections for its twelve-test family  [SUSPICIOUS | confidence: high]

**In plain terms.** Alongside the moment-to-moment analyses, the authors ran twelve tests comparing people to each other rather than comparing moments within a person. Exactly one came out positive, which is roughly what you would expect from chance alone with twelve tests. The paper reports that one result as a finding without noting it stood alone among twelve. It should be treated as a lead worth following, not as something demonstrated.

- **Location:** Table 2, between-person Indirect effects rows, Models 1-6; Results 'Indirect Effects' paragraph
- **Reported:** Results: "Also, participants who generally reported greater negative affect than other participants generally reported greater emotion dysregulation and, in turn, feeling more disconnected while eating throughout the study." This rests on Table 2 Model 6 between-person indirect effect b = 0.95 (0.40), p = .017, beta = 0.69. No correction is stated.
- **Computed:** Exactly one of twelve between-person indirect-effect tests reached p < .05, against about 0.6 false positives expected by chance across a family of that size. Zero claims survive Bonferroni, Holm, Benjamini-Hochberg or Benjamini-Yekutieli. n_claims_lost_to_correction = 1; surviving interval 0 to 0.
- **As printed in the paper:** “Note: Bold text is used to reflect significant effects, defined as p < 0.05” _(found in a table)_
- **Assumptions:** Family defined as the twelve between-person indirect effects (6 outcomes x 2 affect predictors) on one sample. FWER assumes independence and is an upper bound under the correlation these outcomes plainly have. Uncorrected testing is ordinary practice in this literature; this is arithmetic about what the reported p-values imply, not an allegation.
- **Consequence:** 1 stated claim affected -- The paper's only between-person mediation conclusion -- that people with generally higher negative mood report more emotion dysregulation and in turn feel more disconnected while eating -- is one significant test among twelve and is repeated in the Results without that context. The sole between-person mediation claim - that participants with generally greater negative affect reported greater emotion dysregulation and in turn felt more disconnected while eating - rests on p = .017 among 12 tests and survives none of the four corrections. Computed from 1 result(s) significant uncorrected do not survive correction (a correction the paper did not apply, over a family we chose). (computed)
- **Reproduce:** no runnable command -- the review's command used an option this tool does not have. The finding's own numbers are above; re-derive from those.

### 3. Dimension-to-dimension contrast asserted without any test of the difference between dimensions  [SUSPICIOUS | confidence: high]

**In plain terms.** The paper's second main claim is that emotion difficulties explain some kinds of loss-of-control eating but not others. It reaches this by noting which results passed the significance bar and which did not, rather than by directly comparing the kinds to each other. For one of the two behaviours placed on the 'not explained' side -- difficulty stopping once you start -- the data are still compatible with an effect as large as the ones called real elsewhere, so it has not actually been shown to differ. For the other -- not paying attention while eating -- the data are tight enough that the contrast does hold. Half of this claim stands and half does not.

- **Location:** Conclusions; Discussion section 'Variations Across LOC Eating Dimensions'; Table 2 Models 1-6 within-person indirect effects
- **Reported:** Conclusions: "However, notable variations in this pattern of results emerged based on the different LOC eating components." Discussion: participants "subsequently reported more severe levels of certain LOC eating outcomes (general sense of LOC while eating, difficulties resisting eating, feeling driven or compelled to eat, feeling disconnected while eating), but not others (difficulties stopping eating after starting, not paying attention to one's eating)." Table 2 gives Model 3 within-person indirect b = 0.04 (0.03), p = .154 and Model 5 b = -0.004 (0.02), p = .858, against b = 0.10, 0.09 and 0.09 (all p = .001) for the dimensions called mediated.
- **Computed:** The interval derived from Model 3's own printed b and SE runs to 0.099 -- LARGER than the b = 0.09 and b = 0.10 effects the paper calls significant for other dimensions. The data therefore do not separate 'difficulties stopping eating after starting' from the mediated dimensions. Model 5 is the opposite case and supports the paper: its interval [-0.043, 0.035] excludes those effects, so that dimension genuinely does differ. No interaction or moderation test of dimension is reported, and no smallest effect size of interest is stated, so equivalence cannot be assessed for either null.
- **As printed in the paper:** **Table 2, Model 3 (Difficulties Stopping Eating After Starting), within-person indirect effect** -- “Negative Affect → Emotion Dysregulation → LOC Eating 0.04 (0.03) .154 0.01 0.85 (0.45) .060 0.61” _(found in the PDF text layer)_
- **Assumptions:** Intervals are DERIVED from the printed b and SE (b +/- 1.96 x SE on the normal, matching the paper's stated maximum likelihood estimation); the paper prints no confidence intervals anywhere, and the derived bounds inherit the 2-decimal rounding of b and SE. The norm invoked -- that a difference between a significant and a non-significant result is not itself a demonstrated difference -- is Gelman and Stern (2006, The American Statistician 60:328-331), an external standard I supply; the paper never claims to have tested dimensions against each other.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The paper's second headline claim -- that mediation varies meaningfully across LOC eating dimensions, stated in the Conclusions and given its own Discussion section -- holds for one of the two contrasting dimensions and is not established for the other. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command did not match the tool's arguments. The finding's own numbers are above; re-derive from those.

### 4. Table 2 in the publisher XML mislabels six rows, contradicting the paper's own positive-affect conclusion  [SUSPICIOUS | confidence: high]

**In plain terms.** In the online version of the article, six rows of the main results table carry the wrong description. As printed there, the table appears to show a strong result for positive mood that the paper's own conclusions say does not exist. The actual numbers are correct and identical to those in the manuscript version; only the row descriptions are wrong, and the mistake looks like it happened when the article was converted for online publication rather than being anything the authors did. It matters because most readers, and any automated system harvesting the results, will see the online version.

- **Location:** Table 2, third row under 'Direct effects' in each of Models 1-6, as rendered in the publisher XML (version of record)
- **Reported:** In the XML each model block carries a row labelled "Positive affect -> Emotion dysregulation -> LOC eating" under the heading 'Direct effects', with Model 1 values 0.28 (0.07), p < 0.001, beta = 0.13, 0.82 (0.41), p = 0.048, beta = 0.68 -- and a second, differently-valued row bearing the identical label under 'Indirect effects' below it. The Conclusions state: "Also, all momentary mediational pathways involving positive affect as a predictor were not significant."
- **Computed:** Six affected rows, zero numeric cells affected -- every number is identical between the XML and the PDF. Two facts establish the defect from the XML alone, with no cross-source comparison: a two-mediator path cannot appear under a 'Direct effects' heading, and two rows in the same model block cannot carry the same label with different coefficients. The PDF and the paper's own prose independently identify the correct label as 'Emotion dysregulation -> LOC eating': the Results describe beta = 0.13-0.14 within-person and 0.68-0.77 between-person for that direct effect, matching Models 1 and 6 exactly.
- **As printed in the paper:** **Table 1, Participant characteristics** -- “Note: N = 107; additional participant characteristics are reported in Peterson et al. ([2020]).” _(found in a table)_
- **Assumptions:** The diagnosis of which label is correct rests on the PDF (a PMC author manuscript, which I did not open myself -- it was read by the numeric sweep) and on the paper's prose, which I did verify against the grid. The defect itself rests only on the XML. This is a typesetting or markup fault in the version of record, not an authorial or arithmetic one, and no accusation against the authors is implied.
- **Consequence:** changes no significance decision; 1 stated claim affected -- Read at face value, the published XML and the HTML generated from it show a positive-affect mediation path significant at p < .001 in Models 1, 4 and 6, flatly contradicting the paper's Conclusions that no positive-affect pathway was significant. (asserted, not computed)
- **Reproduce:** `metascience get-table --xml-path /mnt/c/Users/gregs/agent_for_forensic_metascience/high_value_pdfs_to_run_on/10.1002--eat.24415/10.1002--eat.24415.xml --table-num 2`

### 5. Trial registration number has seven digits and cannot be looked up as printed  [SUSPICIOUS | confidence: high]

**In plain terms.** The paper gives a registration number for the parent clinical trial so readers can look up what that trial planned to do. The number as printed is one digit short of a valid registration number and leads nowhere. This is almost certainly a typing slip, but it blocks the one check a reader would want to make: whether this analysis matches what the original trial said it would measure.

- **Location:** Participants and Procedures, second paragraph
- **Reported:** "The present study used baseline EMA data from a multisite randomized controlled trial (NCT0204349) testing the efficacy of Integrative Cognitive-Affective Therapy (ICAT-BED) versus guided self-help Cognitive Behavioral Therapy for Eating Disorders (CBTgsh)."
- **Computed:** ClinicalTrials.gov identifiers are 'NCT' followed by exactly eight digits. The printed string has seven and resolves to no registration. The same string appears in both the XML and the PDF, so it is the paper's own text rather than an extraction artefact. No claim is made about which digit is missing.
- **As printed in the paper:** “randomized controlled trial (NCT0204349)” _(found in the paper's text)_
- **Assumptions:** The eight-digit NCT format is a fact about the registry, external to the paper, which the paper never states it follows. Verifying the intended registration would require a registry lookup, which this analysis cannot perform -- it reads one paper and reaches no network.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The registration is a reader's only route to the parent trial's registered design and outcomes, against which this secondary analysis would be checked; as printed it cannot be followed. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command crashed when run. The finding's own numbers are above; re-derive from those.

### 6. Survey compliance printed as 70.00% when the paper's own counts give 69.67%  [SUSPICIOUS | confidence: high]

**In plain terms.** The paper says participants answered 3,131 of 4,494 possible surveys, which is 69.67 per cent, but prints the figure as 70.00 per cent. The two counts themselves are right and check out against the study design. This is a presentation slip of a third of a percentage point and changes nothing about the study's findings.

- **Location:** Results, first paragraph
- **Reported:** "Participants responded to 3131 out of 4494 possible surveys, reflecting good compliance (70.00%)."
- **Computed:** 3131/4494 = 69.67%, outside the rounding interval [69.995, 70.01] that '70.00' asserts. The printed percentage implies a denominator of about 4,472.9 rather than 4,494. Both counts are independently sound: 6 surveys per day x 7 days x 107 participants = 4,494. The likeliest explanation is a value rounded to a whole number and then formatted to two decimals for consistency, asserting precision it does not carry. The same pattern is visible, though not checkable, in Table 1's BDI row, '15.00 (10.00)' -- the only row where both statistics are whole numbers, and one for which no more primitive figures are printed.
- **As printed in the paper:** “Participants responded to 3131 out of 4494 possible surveys, reflecting good compliance (70.00%).” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own statements; count, denominator and percentage are all printed in the same sentence. The remark about the BDI row is an observation offered as context for the diagnosis, not a second finding: that cell is granularity-consistent at n = 107 and nothing about it can be checked.
- **Consequence:** changes no significance decision; 1 stated claim affected -- Overstates compliance by 0.33 percentage points and affects only the descriptive characterisation of compliance as 'good'; no inferential result depends on it. (asserted, not computed)
- **Reproduce:** `metascience check-count-percent --count 3131 --n 4494 --percentage 70.00 --decimals 2`

### 7. Fixed slopes omit a variance component known to bias 1-1-1 multilevel indirect effects  [SUSPICIOUS | confidence: medium]  ⚠ not backed by a sweep finding

**In plain terms.** The statistical model assumes the strength of the mood-to-emotion-difficulty link, and of the emotion-difficulty-to-eating link, is identical for every participant. The authors say they wanted to let these vary between people but the model would not run that way. When they are forced to be identical, a known extra ingredient of the mediation effect is left out, and the reported effects can be too large or too small as a result. Nothing in the published numbers lets anyone tell which, or by how much. The authors mention the technical problem but not this consequence.

- **Location:** Statistical Analyses, final paragraph; all within-person indirect effects in Table 2
- **Reported:** "Fixed slopes and random intercepts were modeled at both levels due to convergence difficulties when random slopes were added (because of the data structure's complexity)." The paper discloses the constraint but does not discuss its consequence for the indirect effects, and the Strengths and Limitations section does not mention it.
- **Computed:** No recomputation is possible from the printed values. In a 1-1-1 multilevel mediation the population within-person indirect effect is E(a)E(b) + cov(a,b); constraining both slopes to be fixed estimates only the first term and drops the covariance between the person-specific a and b paths. The direction and magnitude of the resulting bias cannot be determined from what the paper prints, because the slope covariance is exactly the quantity the model could not estimate.
- **Assumptions:** The result invoked is Kenny, Korchmaros and Bolger (2003, Psychological Methods 8:115-128) and Bauer, Preacher and Gil (2006, Psychological Methods 11:142-163), an external methodological standard I supply. The authors state the random-slope model would not converge, so the constraint was forced rather than chosen; the finding concerns the undiscussed consequence, not the decision.
- **Reproduce:** no runnable command -- the review's command crashed when run. The finding's own numbers are above; re-derive from those.

### 8. Blanket positive-affect null rests on three results just above the significance threshold  [INDETERMINATE | confidence: high]

**In plain terms.** The paper concludes flatly that positive mood played no part in any of the pathways it tested. Three of the six relevant results were only just short of the cutoff the authors used, and two were nowhere near it. Nothing here is calculated wrongly and every individual judgement is correct by the paper's own rule -- but 'no effect' is a stronger summary than results sitting just outside the line support, and the article prints no ranges that would let a reader notice.

- **Location:** Conclusions and Discussion 'Positive Affect'; Table 2, within-person positive-affect Indirect effects rows, Models 1-6
- **Reported:** Conclusions: "Also, all momentary mediational pathways involving positive affect as a predictor were not significant." Discussion: "It is noteworthy that all momentary pathways, including positive affect as a predictor of emotion dysregulation and, in turn, LOC eating dimensions, were not significant in the present study." Table 2 gives the six within-person positive-affect indirect p-values as .070, .122, .233, .067, .859, .065.
- **Computed:** Three of the six sit at p = .065-.070, immediately above the paper's stated alpha of .05; only two (.859, .233) are clearly null. No confidence intervals are printed anywhere in the paper for any of the 84 coefficients, so a reader cannot see this from the table as presented. NOTE: an interval derived from Model 6's printed b = -0.02 and SE = 0.01 appears to exclude zero, but this is an artefact of two-decimal rounding, not a contradiction -- the coefficient row is consistent, with a reachable p-interval of [6e-07, 0.317] at that printed precision, and no inconsistency should be read into it.
- **As printed in the paper:** **Table 2, Model 6 (Felt Disconnected While Eating), within-person indirect effect for positive affect** -- “Positive Affect → Emotion Dysregulation → LOC Eating −0.02 (0.01) .065 −0.01 −0.02 (0.06) .725 −0.02” _(found in the PDF text layer)_
- **Our check returned a different severity.** The `absence_of_evidence` check returned `consistent` for the sweep finding `absence_of_evidence_positive_affect_null`, which this review recorded as `indeterminate`. This entry asserts more than the check established, so read it as this review's judgement and not as a computed result. The finding states a reason.
- **Assumptions:** Intervals are derived from printed b and SE, not reported by the paper. The judgement that a flat 'not significant' understates results at p = .065-.070 is a reporting-emphasis observation; the paper's arithmetic is correct throughout and its individual significance decisions are all right at its own threshold.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The Conclusions' unqualified statement that no positive-affect pathway was significant is carried in half its instances by marginal rather than clearly null results, which the paper does not signal. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command did not match the tool's arguments. The finding's own numbers are above; re-derive from those.

### 9. Mediator correlates at .948 with the mediator used in a prior paper on the same sample  [INDETERMINATE | confidence: medium]

**In plain terms.** The psychological quality this paper treats as the explanatory mechanism is almost perfectly correlated -- .948 out of a possible 1.0 -- with the quality an earlier paper by the same group used as the mechanism, in the very same participants. The paper reports this correlation openly and lists the earlier work. It does mean the two sets of findings are closer to one result than two, which is worth knowing when reading them alongside each other. Nothing here is miscalculated.

- **Location:** Study Purpose, final paragraph
- **Reported:** "a prior analysis of the present sample examined whether the momentary negative affect-binge eating association was mediated by negative urgency (i.e., a self-regulatory process that overlaps with emotion dysregulation [r = 0.948 in the present study] and is defined as behaving impulsively while experiencing negative affect; Wonderlich et al. [2024])."
- **Computed:** r = .948 is well within bounds and no arithmetic check flags it. The paper cites it as evidence of 'overlap'; at that magnitude the two constructs are close to interchangeable in this sample. The prior publication tested negative urgency as the mediator of the negative-affect-to-binge-eating path in these same 107 participants; the present paper tests emotion dysregulation.
- **As printed in the paper:** “overlaps with emotion dysregulation (r = .948 in the present study)” _(found in the PDF text layer)_
- **Assumptions:** Whether two analyses on one sample with mediators correlated at .948 should be read as independent contributions is an editorial judgement I am supplying, not a standard the paper accepted. The paper is transparent about the overlap and about the shared dataset, listing four prior publications from it. No shared-variance figure is computed here.
- **Consequence:** changes no significance decision; 1 stated claim affected -- Bears on how independently this paper's negative-affect mediation result should be read relative to the same team's prior result on the same participants, not on whether either result is correctly computed. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command crashed when run. The finding's own numbers are above; re-derive from those.

### 10. No observation count reported for the six outcome variables' descriptive statistics  [INDETERMINATE | confidence: high]

**In plain terms.** The six eating-behaviour questions were only shown to a participant who had reported eating recently, so they were answered far fewer times than the total number of surveys. The paper never says how many times. Without that number the averages it reports for those six behaviours cannot be independently checked, even though they are exactly the kind of figure that is usually checkable. Nothing about them looks wrong -- there is simply no way to confirm them.

- **Location:** Results, first paragraph (LOC eating severity descriptives)
- **Reported:** "participants generally reported LOC eating at a moderate level of severity across the assessed dimensions, yet with high variability (all ranges = 1-5): (1) general feeling of losing control while eating (M = 2.26, SD = 1.32); (2) difficulties resisting eating (M = 2.79, SD = 1.42)" and four further dimensions. Methods: "Participants were presented with the LOC eating items if they endorsed that they ate since their last survey."
- **Computed:** Nothing could be computed. These six means are otherwise ideal targets for granularity checking -- single items on a stated 1-5 integer scale -- and all three applicable checks are blocked for one reason: the number of eating-episode observations underlying them is an unstated subset of the 3,131 completed surveys. Substituting the survey total would invent the denominator and could manufacture a false impossibility, so nothing was run. All six standard deviations (1.18-1.42) sit well below the ceiling a 1-5 scale permits, so nothing looks wrong; it simply cannot be verified.
- **As printed in the paper:** “(1) general feeling of losing control while eating (M = 2.26, SD = 1.32); (2) difficulties resisting eating (M = 2.79, SD = 1.42)” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own statements. The 1-5 range is stated by the paper, as is the conditional administration of the items.
- **Consequence:** changes no significance decision -- No conclusion depends on these descriptive figures, but they are the paper's only distributional summary of its six outcome variables and none of them can be independently verified. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command crashed when run. The finding's own numbers are above; re-derive from those.

## What we could NOT check

- **Data S1 (Supporting Information): multilevel confirmatory factor analyses, all model fit statistics, missing-data analyses, the exploratory reverse-pathway models, and the comparison of the 5 excluded against the 107 analysed participants** — OUR GAP, not an omission by the authors: no supplementary file was among the inputs to this analysis (only the .xml and .pdf were supplied), so its contents could not be read. This is the largest coverage hole here. Table 2's footnote states "model fit statistics were good and are reported in Data S1", and the Results describe the entire exploratory analysis set as significant for four of six dimensions without printing a single coefficient in the main text. None of that could be verified from what we hold.
- **Results, the six LOC eating means and SDs (M = 2.26 / 2.79 / 2.54 / 2.88 / 3.45 / 2.19)** — All three granularity checks require an observation-level denominator and none is reported; the items were shown only after a reported eating episode, so the relevant count is an unstated subset of the 3,131 completed surveys. Substituting the survey total would invent the denominator.
- **Table 1, BDI / CIA / DERS total-score standard deviations (10.00, 9.87, 26.61)** — The exact-arithmetic checks refused these rows because the paper states no scoring range for any of the three instruments. Falling back on a default Likert maximum would manufacture an impossibility out of an ordinary unbounded total score. The refusal is correct; a stated instrument range would make them checkable.
- **Table 1, baseline age (39.87) and BMI (35.10)** — Declared continuous, so the exact-arithmetic family correctly does not apply. Age could in principle be whole years, but the paper does not say so, and asserting it would rest on an assumption we supplied.
- **Table 2, the 16 coefficient rows whose p is printed as '< .001'** — A thresholded p is a bound, not a value, and was excluded from the 68-row coefficient check rather than being read as an exact 0.001. Those coefficients are large relative to their standard errors (0.35/0.06, 0.96/0.10), so the threshold itself is not in doubt, but no exact verification was performed.
- **Degrees of freedom for every coefficient in Table 2** — The paper reports none. The coefficient check was run against the normal reference implied by the stated maximum likelihood estimation, which is what such models report; a different reference would shift the recovered p-values slightly.
- **A-priori power or sample-size justification** — The paper reports none, so there was nothing to reproduce. This is expected for a secondary analysis where N is fixed by the parent trial, and is recorded as context rather than as a defect.
- **Exploratory reverse-pathway models (emotion dysregulation -> affect -> LOC eating)** — Described in the Results as significant for four of six dimensions, with all numbers in Data S1, which we do not hold. These add at least twelve further indirect-effect tests, so the two multiplicity findings above understate the true comparison count.
- **Baseline-similarity tests on Table 1** — Deliberately not run. Both such tests compare randomised arms; this paper reports a single pooled sample with no arm-wise breakdown and performs no baseline comparison, so there are no baseline p-values to combine. Running either would require inventing a grouping the paper does not report.
- **Effect-size plausibility benchmarking of the headline mediation effects** — Not run, and unavailable for this paper. The benchmark table covers standardised mean differences; these are within-person standardised mediation path coefficients (beta = 0.02-0.03), which are not on that scale and have no corresponding benchmark. Passing them would compare incommensurable quantities.
- **Rank-sum granularity checks** — Not applicable: every p-value in this paper comes from Wald tests of multilevel structural equation model coefficients, not from rank-sum tests.
- **The article abstract** — The abstract was not present in the XML full text available to this stage. Claims are therefore cited to the Results, Discussion and Conclusions sections, whose text was verified directly, rather than to the abstract.
- **table rows Baseline depressive symptoms (BDI total score), Baseline eating disorder-related clinical impairment (CIA total score), Baseline emotion dysregulation (DERS total score)** — grimmer_check, sprite_reconstruct not run: this check needs a STATED scale maximum and the paper does not give one. It would otherwise fall back to a default 1-7 Likert scale, which for an unbounded variable manufactures an impossibility out of an ordinary value (measured: a mean of 35.78 members at n=64 reported `impossible` against an invented maximum of 7).

## Questions for the authors

_Each of these is answerable from what the authors already have. None presupposes an error on their part: an inconsistency is far more often a reporting slip, or a mistake by this tool in reading the number off the page, than anything else._

1. How many eating-episode observations underlie the six loss-of-control eating descriptive statistics reported in the Results (M = 2.26, SD = 1.32 for the general feeling of losing control, and the five others)? Since the items were shown only when a participant had reported eating since the last survey, the relevant count is a subset of the 3,131 completed surveys, and it does not appear in the article. Could you also supply the number of level-1 observations that entered each of the six models?
   <sub>Would resolve: Without an observation-level denominator none of the six outcome descriptives can be granularity-checked, and the level-1 N is needed to gauge the precision of the within-person indirect effects. Resolves finding 9.</sub>
2. Was any adjustment for multiple comparisons applied across the twenty-four indirect effects in Table 2, or across the further exploratory reverse-pathway models? If not, would you regard the within-person mediation of difficulties resisting eating (b = 0.06, SE 0.03, p = .026) and the between-person mediation of feeling disconnected while eating (b = 0.95, SE 0.40, p = .017) as robust, given that neither clears a Bonferroni, Holm, Benjamini-Hochberg or Benjamini-Yekutieli threshold for a twelve-test family?
   <sub>Would resolve: These are the two results that cross the paper's stated alpha of .05 only without correction, and both are stated as findings. Resolves findings 1 and 3.</sub>
3. Was any formal test of the difference between loss-of-control eating dimensions run -- for example a joint model with dimension as a moderator? The within-person indirect effect for difficulties stopping eating after starting is b = 0.04 (SE 0.03), which is compatible with effects as large as the b = 0.09 to 0.10 reported as significant for the other dimensions, so the contrast between them does not appear to have been tested directly.
   <sub>Would resolve: The paper's second headline conclusion is that mediation varies across dimensions; for this dimension the printed estimates do not separate it from the mediated ones. Resolves finding 2.</sub>
4. Could you confirm the ClinicalTrials.gov identifier for the parent trial? The article prints 'NCT0204349', which has seven digits where the registry format has eight, and does not resolve as written.
   <sub>Would resolve: The registration is the only route to the parent trial's registered design and outcomes. Resolves finding 6.</sub>
5. In the publisher's online version of Table 2, the third row under 'Direct effects' in each of the six models is labelled 'Positive affect -> Emotion dysregulation -> LOC eating' -- the same label as the indirect-effects row below it -- carrying values of 0.28 (0.07), p < 0.001 in Model 1. The manuscript PDF labels that row 'Emotion Dysregulation -> LOC Eating', which matches the beta values of 0.13 to 0.14 described in your Results. Could you confirm which label is correct, so the discrepancy can be raised with the publisher?
   <sub>Would resolve: As rendered online the table appears to report a significant positive-affect mediation path, contradicting the paper's own conclusion that no positive-affect pathway was significant. Resolves finding 5.</sub>

## Limitations

- FIGURES WERE NOT READ. This agent reads text and tables and does not see figures. The paper contains one figure, a conceptual path diagram whose caption states it depicts the model structure and lagging scheme; on the caption alone it carries no estimated values, so no numeric check was lost. That judgement rests on the caption, not on the artwork.
- The supplementary file Data S1 was not among the inputs supplied to this analysis. It holds every model fit statistic the paper claims, the factor analyses, the missing-data analyses and the whole exploratory analysis set. Its absence is our limitation, not a reporting failure by the authors, and it means the paper's fit claims and one entire analysis set are unverified here rather than verified or refuted.
- I read the publisher XML directly and re-fetched both tables at source before writing. I did not open the PDF myself; the diagnosis of which Table 2 row label is correct rests on the numeric sweep's reading of the PDF, corroborated independently by the paper's own prose, which I did verify against the table grid.
- Two of the four questions a multiplicity or overlap finding should be read against are outside this system's reach entirely: whether similar patterns appear in other papers by these authors, and what the equivalent values look like in comparable studies in this literature. This analysis reads one paper and reaches no network, so that part of the interpretation is the reader's to supply.
- The multiplicity arithmetic depends on how the family of tests is defined, which is my judgement and not a fact of the paper. I grouped the twelve within-person and the twelve between-person indirect effects as two families. A reader who considers each of the six models a separate confirmatory question would reach a more permissive conclusion; one who pools all twenty-four tests, or adds the exploratory models, would reach a stricter one.
- Confidence intervals are derived from the printed coefficients and standard errors, which are given to two decimal places; the paper prints no intervals of its own. For the smallest coefficients this rounding makes the derived bounds coarse, and one apparent interval-versus-p-value contradiction in the positive-affect rows was traced to exactly that rounding and is reported as no anomaly.
- The 'questionable' verdict is not a default. The specific unresolved matters are: two named claims that cross the paper's own significance threshold only without correction, a dimension-to-dimension contrast that holds for one of the two contrasting outcomes and not the other, a bias from the forced fixed-slope specification whose direction and size cannot be recovered from the published numbers, and the unread supplement.
- No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.

## Coverage

- **Statistics found:** 136; **checked:** 94
- **Tools run:** extract_xml, get_table, check_count_percent, multiplicity_report, absence_of_evidence, parse_cells_typed, check_table, check_summation_batch, grim_check, check_regression_batch, detect_duplication, statcheck, extract_pdf
- **Tables checked:** Table 1 (Participant characteristics, 29 rows x 3 cols, 26 cells, 100% typed, 0 ambiguous), Table 2 (Multilevel SEM results, 60 rows x 7 cols, 84 coefficients, 68 with an exact p checked)
- **Checkable table cells:** 110 of 314 surveyed; **checked:** 21
    - 6 could not be checked without knowing what kind of quantity the row reports
    - 104 were missing an input: n (104)
- **Where a check and this review disagreed:** 2 sweep findings recorded a severity the validated check behind them did not return (1 upgraded, 1 downgraded). 1 is marked on the entry above that cites it. 1 sits on a sweep finding no entry in this report cites, so this line is the only place it appears.
- **Traceable to the page:** 16 of 16 checks recorded the passage their numbers were read from; 10 of those were located in the paper's own text.
- **6 quoted passages are ours, not the paper's.** Every number in them was found in the paper, but the sentence around those numbers was assembled by this review and does not appear as written -- so do not search the PDF for it. The CHECK is sourced; only the quotation marks over-promise.

## What each check does

One entry per check that ran on this paper. The **assumptions** are the conditions under which its verdict holds; where one is unmet the verdict is capped, not merely caveated.

### `absence_of_evidence` — probabilistic

Tests whether a stated 'no effect' conclusion survives its own confidence interval.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The null must be locatable: 1 for ratio measures, 0 for differences; without `measure` it declines.
- The CI is taken at face value; the verdict targets the CLAIM made about it, not the data.
- Equivalence is judged only against a supplied SESOI; with none it describes the interval and declines.

### `check_count_percent` — probabilistic

Checks the printed count over the printed denominator against the printed percentage.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The percentage is assumed to be over THIS n -- the assumption most likely to be wrong, since row, column and subgroup bases coexist in one table.
- Ceiling `suspicious`, tighter than its class allows: a different percentage base is an ordinary reporting convention and no arithmetic disagreement rules it out.
- The printed percentage asserts a rounding interval, and its decimals must be supplied rather than assumed.
- A count exceeding its denominator is reported as a wrong pairing, not as a defect in the paper.

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

This is a secondary analysis of baseline ecological momentary assessment data from a multisite randomised trial of two psychotherapies for binge eating disorder. In 107 adults who answered 3,131 of 4,494 prompted surveys over seven days, the authors fit six two-level multilevel structural equation models, each asking whether momentary emotion dysregulation carries the effect of momentary affect onto one of six distinct loss-of-control (LOC) eating dimensions. They conclude that emotion dysregulation mediated negative-affect pathways to four of the six dimensions, that the pattern varied meaningfully across dimensions, and that no positive-affect pathway was significant at any level.

## The arithmetic is in good order

This is a carefully prepared paper at the level of its numbers, and that deserves stating before anything else. All 68 coefficient rows in Table 2 that carry an exact p-value reproduce that p from the coefficient and standard error printed beside them -- 68 of 68, with no inconsistency and none indeterminate. All 15 count-and-percentage pairs in Table 1 reconcile exactly against N = 107. All three categorical blocks sum exactly to 107, the sample flow reconciles at 107 + 5 = 112, and the three integer-scored baseline totals are granularity-consistent. Every standardised coefficient quoted in the Results narrative traces to the corresponding Table 2 cell, including the ranges (beta = 0.13-0.14, 0.68-0.77, 0.08-0.14, 0.02-0.03), and the prose is scrupulous at the significance boundary, describing Model 1's between-person direct effect at p = .048 as significant while calling its indirect effect at p = .052 not. A duplication scan over 960 comparisons found no improbable repetition; the small patternless variation across model blocks -- a between-person coefficient of 0.96 in Models 1-3 and 0.95 in Models 4-6, a p-value moving .038/.039/.040/.040/.042/.038 -- is the signature of six genuinely separate re-estimations rather than a copied block.

## Where the problem lies

The difficulties in this paper are not in its arithmetic but in the inferences drawn from it, and they are really one problem seen twice. The paper asks a single question -- does emotion dysregulation mediate the affect-to-LOC-eating path -- of twenty-four correlated outcomes in the same 107 people, and then reads the resulting pattern of significant and non-significant results as a substantive map of which eating behaviours are mechanistically explained and which are not. Both halves of that reading are weaker than the paper presents them. The pattern of significance is partly a function of having run twenty-four tests at the ordinary threshold, and the contrast between a mediated and an unmediated dimension is asserted rather than tested -- for one of the two dimensions placed on the null side, the estimate is compatible with an effect larger than the ones called significant elsewhere.

Two counterweights belong in the same breath. First, uncorrected testing is ordinary practice in this literature and is not a mark against these authors; the arithmetic here is about what the reported p-values imply, not about anyone's conduct. Second, three of the four within-person mediation claims survive even Bonferroni, which is a demanding test, and the second null dimension -- not paying attention to one's eating -- genuinely does differ from the mediated ones. The paper's core finding, that momentary emotion dysregulation carries negative affect onto several forms of loss-of-control eating, is not what is in doubt. What is in doubt is the finer-grained dimensional story built on top of it.

## Two things I considered and did not report

The paper's data availability statement offers data, materials and code "from the corresponding author upon reasonable request". For identifiable momentary data from an ongoing clinical trial this is the standard and defensible formulation, and treating it as evasive would hold the paper to a standard its design never owed. I do not report it.

A citation year differs between the two versions of the article -- Stefano et al. is dated 2014 in the manuscript PDF and 2016 throughout the publisher XML. The PDF is a PMC author manuscript and the XML the version of record, so an ordinary copy-editing correction between them fully explains it, no numeric claim depends on it, and I have dropped it rather than padding the review.

I also declined to escalate one cell in Table 1. The BDI row reads 15.00 (10.00), the only row in that table where both statistics are whole numbers. It is granularity-consistent at n = 107, nothing more primitive is printed against which it could be checked, and rounding for presentation explains it as readily as anything else. It appears in this review only as context for the compliance figure, which is the same formatting pattern in a case where the underlying counts are printed and the discrepancy can be demonstrated.

## Reading the version of record

One defect belongs to the publisher rather than the authors, and it is the one most likely to mislead a reader who never opens the manuscript PDF. In the published XML -- and so in the HTML generated from it -- six rows of Table 2 carry the label of the row beneath them, with the effect that the article as published online appears to report a positive-affect mediation path significant at p < .001 in three models, in direct contradiction of its own conclusions. The numbers are all correct and identical across both versions. Only the labels are wrong, and the paper's own prose identifies which label belongs there.

The core result of this paper appears sound and its reported statistics verify; the dimension-by-dimension conclusions built on top of that result are less secure than the article states, and warrant clarification from the authors rather than distrust.

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
