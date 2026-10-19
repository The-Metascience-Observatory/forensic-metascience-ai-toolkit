# Forensic review -- Wells et al. 2026

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## Associations between inclusive community coalition leadership and use of evidence-based practices
*Rebecca Wells, Nalini Ranjit, Louis D. Brown, Sarah M. Chilenski, Yvonne Mary Gaddy. American Journal of Community Psychology, 77, 590-601. 2026. doi:10.1002/ajcp.70049*

**Design:** Longitudinal observational (1-year lagged) regression analysis of 64 youth substance misuse prevention coalitions, nested within a randomized technical-assistance trial. Poisson (number of EBPs), negative binomial (EBP reach), and hierarchical linear (program-level fidelity) models. Stata 17.0.

<sub>Analysed as `10.1002--ajcp.70049`</sub>

> **SUSPICIOUS** — The paper's primary predictor is described on two mutually incompatible scales in the same article, so the "one-unit increase" that every headline coefficient is expressed per has no defined meaning.
>
> **Evidence:** Measures (p. 594): engaging communication is "the mean of member responses to four items ... (response options 1 = Needs a lot of work, 2 = Needs a little work, 3 = Good, 4 = Outstanding; Cronbach's alpha = 0.93)" -- a four-item mean on 1-4 cannot exceed 4. Results (p. 595): "the mean level of engaging communication was 3.83 on a 1.25-5 scale, corresponding to 'good' for such facets as frequency." Table 1 gives Communication 3.83 (0.42), n = 64. Table 2 reports the effect of this measure as b = 1.01 (0.38), p = .01, and Table 3 as b = 3.91 (1.78), p = .03, both per one-unit increase.
> **Rests on:** a constraint the paper itself states
> **Reproduce:** `metascience extract --pdf-path /mnt/c/Users/gregs/agent_for_forensic_metascience/high_value_pdfs_to_run_on/10.1002--ajcp.70049/10.1002--ajcp.70049.pdf --first-page 5 --last-page 8`

**Verdict: questionable** (confidence: medium)

> **Table coverage is unmeasured.** No cell was checked through `check_table`, which is the only route this census can count, so none of the 78 checkable cells can be ticked off by id. But 108 per-cell checks did run on values taken off this paper (`check_regression`, `check_sd_range`, `check_summation`, `detect_duplication`, `flag_round_n`, `grim_check`, `grim_percentage`, `grim_sweep`, `grimmer_check`, `r_sprite_ground_truth`, `sprite_reconstruct`, `stalt_check`). How much of the table that covers is not known -- it is not zero, and it is not measured here.

## Provenance of the analysis

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

2 study/studies, 14 variables, 64 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| s1 | Coalition-level lagged analysis (number of EBPs, EBP reach) | cohort | 64 | coalition | no |
| s2 | Program-level lagged analysis (EBP fidelity), programs nested in coalitions | cohort | 101 | program nested within coalition (random intercept for coalition) | yes |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Number of evidence-based programs implemented by the coalition | ratio | discrete | 0-9 (integers) | programs | measured (count of coalition-leader-reported programs the research team coded as EBPs against registries) | GRIM (needs stated max) | high |
| EBP reach | ratio | discrete | 0-5370 (integers) | persons (youth and parents) per year | sum of items: total unduplicated annual number of youth and parents reported by the coordinator for each program at each site, summed over all EBPs supported by a coalition | GRIM (needs stated max) | high |
| EBP fidelity / adherence | ordinal | continuous | 1-7 | - | mean of items (k=2): mean of one item asked separately for youth and for parents: 'how much of the outlined program content was actually delivered' (inter-item correlation = 0.76) | none -- composite granularity is 1/(items x n) | high |
| Uses at least one evidence-based program | nominal | discrete | uses at least one EBP; uses none | - | recoded: dichotomization of the number of EBPs | DEBIT; percentage GRIM | high |
| Engaging communication | ordinal | continuous | 1-4 | - | mean of items (k=4): mean of member responses to four items on frequency, clarity, accuracy and timeliness of leader-member communication, then averaged to coalition level (Cronbach's alpha = 0.93) | none -- composite granularity is 1/(items x n) | medium |
| Inclusive decision making | ordinal | continuous | 1-5 | - | mean of items (k=3): mean of member responses to three items on fair say, mutually beneficial solutions and shared support for decisions, averaged to coalition level (Cronbach's alpha = 0.88) | none -- composite granularity is 1/(items x n) | high |
| Inclusion of community residents | ordinal | continuous | 1-5 | - | mean of items (k=2): mean of two items on facilitating participation of, and including views of, individuals affected by the coalition's decisions (inter-item correlation = 0.80) | none -- composite granularity is 1/(items x n) | high |
| Population of coalition service area | ratio | continuous | range not stated | persons | measured | none -- not integer-valued | high |
| Coalition size (number of active members) | ratio | discrete | range not stated | members | measured (count of active members reported by coalition leaders; entered in models in units of 10) | GRIM (needs stated max) | high |
| State | nominal | discrete | Pennsylvania; Missouri | - | measured | DEBIT; percentage GRIM | high |
| Follows the Communities That Care model | nominal | discrete | follows CTC; any other model or none | - | measured | DEBIT; percentage GRIM | high |
| Receives external funding at baseline | nominal | discrete | received any external funding; did not | - | measured | DEBIT; percentage GRIM | high |
| Level of technical assistance received | ordinal | discrete | 0 = Little to no TA; 1 = Regular noncustomized assistance in groups; 2 = Regular (monthly) one-on-one monitoring; 3 = Regular (monthly) one-on-one capacity building assistance | - | measured | percentage GRIM on cell counts | high |
| Assigned to full Coalition Check-Up technical assistance | nominal | discrete | assigned to Coalition Check-Up; TA as usual | - | measured (random assignment of half of the original 68 coalitions) | DEBIT; percentage GRIM | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Table 2, Communication row, model 1 | other | Number of evidence-based programs implemented by the coalition (count) | Engaging communication, Number of evidence-based programs implemented by the coalition, Follows the Communities That Care model, Receives external funding at baseline, Level of technical assistance received, Coalition size (number of active members), Assigned to full Coalition Check-Up technical assistance | 64 | none | none reported |
| Table 2, Inclusive decision making row, model 2 | other | Number of evidence-based programs implemented by the coalition (count) | Inclusive decision making, Number of evidence-based programs implemented by the coalition, Follows the Communities That Care model, Receives external funding at baseline, Level of technical assistance received, Coalition size (number of active members), Assigned to full Coalition Check-Up technical assistance | 64 | none | none reported |
| Table 2, Inclusion of community residents row, model 3 | other | Number of evidence-based programs implemented by the coalition (count) | Inclusion of community residents, Number of evidence-based programs implemented by the coalition, Follows the Communities That Care model, Receives external funding at baseline, Level of technical assistance received, Coalition size (number of active members), Assigned to full Coalition Check-Up technical assistance | 64 | none | none reported |
| Table 3, Communication row, model 1 | other | EBP reach (count) | Engaging communication, Follows the Communities That Care model, Receives external funding at baseline, Level of technical assistance received, Coalition size (number of active members), Assigned to full Coalition Check-Up technical assistance | 64 | none | none reported |
| Table 3, Inclusive decision making row, model 2 | other | EBP reach (count) | Inclusive decision making, Follows the Communities That Care model, Receives external funding at baseline, Level of technical assistance received, Coalition size (number of active members), Assigned to full Coalition Check-Up technical assistance | 64 | none | none reported |
| Table 3, Inclusion of community residents row, model 3 | other | EBP reach (count) | Inclusion of community residents, Follows the Communities That Care model, Receives external funding at baseline, Level of technical assistance received, Coalition size (number of active members), Assigned to full Coalition Check-Up technical assistance | 64 | none | none reported |
| Table 4, Communication row, model 1 | mixed_model | EBP fidelity / adherence (likert_composite) | Engaging communication, EBP fidelity / adherence, Follows the Communities That Care model, Receives external funding at baseline, Level of technical assistance received, Coalition size (number of active members), Assigned to full Coalition Check-Up technical assistance | 101 | none | unconditional intraclass correlation coefficient of 0.10 for fidelity at Time 2 used to justify hierarchical models |
| Table 4, Inclusive decision making row, model 2 | mixed_model | EBP fidelity / adherence (likert_composite) | Inclusive decision making, EBP fidelity / adherence, Follows the Communities That Care model, Receives external funding at baseline, Level of technical assistance received, Coalition size (number of active members), Assigned to full Coalition Check-Up technical assistance | 101 | none | none reported |
| Table 4, Inclusion of community residents row, model 3 | mixed_model | EBP fidelity / adherence (likert_composite) | Inclusion of community residents, EBP fidelity / adherence, Follows the Communities That Care model, Receives external funding at baseline, Level of technical assistance received, Coalition size (number of active members), Assigned to full Coalition Check-Up technical assistance | 101 | none | none reported |
| Table 2, Number of EBP at baseline, model 1 | other | Number of evidence-based programs implemented by the coalition (count) | - | 64 | ? | none reported |
| Table 2, Number of EBP at baseline, model 2 | other | ? | - | 64 | ? | none reported |
| Table 2, Number of EBP at baseline, model 3 | other | ? | - | 64 | ? | none reported |
| Table 2, Communities That Care, model 1 | other | ? | - | 64 | ? | none reported |
| Table 2, Communities That Care, model 2 | other | ? | - | 64 | ? | none reported |
| Table 2, Communities That Care, model 3 | other | ? | - | 64 | ? | none reported |
| Table 2, Externally funded, model 1 | other | ? | - | 64 | ? | none reported |
| Table 2, Externally funded, model 2 | other | ? | - | 64 | ? | none reported |
| Table 2, Externally funded, model 3 | other | ? | - | 64 | ? | none reported |
| Table 2, Level of technical assistance, model 1 | other | ? | - | 64 | ? | none reported |
| Table 2, Level of technical assistance, model 2 | other | ? | - | 64 | ? | none reported |
| Table 2, Level of technical assistance, model 3 | other | ? | - | 64 | ? | none reported |
| Table 2, Number of members, model 1 | other | ? | - | 64 | ? | none reported |
| Table 2, Number of members, model 2 | other | ? | - | 64 | ? | none reported |
| Table 2, Number of members, model 3 | other | ? | - | 64 | ? | none reported |
| Table 2, Constant, model 1 | other | ? | - | 64 | ? | none reported |
| Table 2, Constant, model 2 | other | ? | - | 64 | ? | none reported |
| Table 2, Constant, model 3 | other | ? | - | 64 | ? | none reported |
| Table 3, Number of EBP at baseline, model 1 | other | ? | - | 64 | ? | none reported |
| Table 3, Number of EBP at baseline, model 2 | other | ? | - | 64 | ? | none reported |
| Table 3, Number of EBP at baseline, model 3 | other | ? | - | 64 | ? | none reported |
| Table 3, Communities That Care, model 1 | other | ? | - | 64 | ? | none reported |
| Table 3, Communities That Care, model 2 | other | ? | - | 64 | ? | none reported |
| Table 3, Communities That Care, model 3 | other | ? | - | 64 | ? | none reported |
| Table 3, Externally funded, model 1 | other | ? | - | 64 | ? | none reported |
| Table 3, Externally funded, model 2 | other | ? | - | 64 | ? | none reported |
| Table 3, Externally funded, model 3 | other | ? | - | 64 | ? | none reported |
| Table 3, Level of technical assistance, model 1 | other | ? | - | 64 | ? | none reported |
| Table 3, Level of technical assistance, model 2 | other | ? | - | 64 | ? | none reported |
| Table 3, Level of technical assistance, model 3 | other | ? | - | 64 | ? | none reported |
| Table 3, Number of members, model 1 | other | ? | - | 64 | ? | none reported |
| Table 3, Number of members, model 2 | other | ? | - | 64 | ? | none reported |
| Table 3, Number of members, model 3 | other | ? | - | 64 | ? | none reported |
| Table 3, Constant, model 1 | other | ? | - | 64 | ? | none reported |
| Table 3, Constant, model 2 | other | ? | - | 64 | ? | none reported |
| Table 3, Constant, model 3 | other | ? | - | 64 | ? | none reported |
| Table 4, Quality of EBP at baseline, model 1 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Quality of EBP at baseline, model 2 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Quality of EBP at baseline, model 3 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Communities That Care, model 1 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Communities That Care, model 2 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Communities That Care, model 3 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Externally funded, model 1 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Externally funded, model 2 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Externally funded, model 3 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Level of technical assistance, model 1 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Level of technical assistance, model 2 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Level of technical assistance, model 3 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Number of members, model 1 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Number of members, model 2 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Number of members, model 3 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Constant, model 1 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Constant, model 2 | mixed_model | ? | - | 101 | ? | none reported |
| Table 4, Constant, model 3 | mixed_model | ? | - | 101 | ? | none reported |
| Methods, Covariates paragraph | other | ? | Population of coalition service area, State, Coalition size (number of active members), Follows the Communities That Care model, Receives external funding at baseline, Level of technical assistance received, community poverty, coalition age | 64 | none | none reported |

_63 of 64 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. Engaging communication is given two incompatible scales (1-4 in Measures, 1.25-5 in Results), leaving the headline coefficients' unit undefined  [SUSPICIOUS | confidence: high]

- **Location:** Measures, 'Engaging communication' (p. 594) vs Results paragraph 1 (p. 595); Table 1 Communication row; Table 2 and Table 3 Communication rows
- **Reported:** Measures: mean of four items scored 1 = Needs a lot of work to 4 = Outstanding. Results: "the mean level of engaging communication was 3.83 on a 1.25-5 scale, corresponding to 'good'". Table 1: Communication 3.83 (0.42). Effects reported per one-unit increase: b = 1.01 (0.38), p = .01 (number of EBPs); b = 3.91 (1.78), p = .03 (reach).
- **Computed:** The two stated bounds cannot both hold: a mean of four integer items scored 1-4 has a maximum of 4, so a '1.25-5 scale' is not attainable. Dispersion cannot adjudicate between the readings -- check_sd_range returns consistent under both: SD 0.42 is 27.8% of the maximum possible (1.5119) for a 1-4 range at n = 64, and 22.2% of the maximum possible (1.8898) for a 1.25-5 range. Note that 1.25 = 5/4 is exactly attainable as the mean of four 1-4 items, which supports reading '1.25-5' as an observed range with a typo in the upper value. The interpretive gloss is also off: on the 1-4 anchors 3.83 sits close to 'Outstanding' (4), not 'good' (3).
- **As printed in the paper:** “Communication (mean, SD) | 3.83 (0.42) ... response options 1 = Needs a lot of work ... 4 = Outstanding” _(found in a table, across an ellipsis)_
- **Assumptions:** None beyond the paper's own statements -- both bounds are stated by the paper (rulebook rule 4: stated constraint, not assumed). Stage 1 confirmed both strings verbatim against the source PDF, so this is not a markdown-extraction artifact. The sd-range corroboration assumes the reported SD refers to the coalition-level composite in Table 1.
- **Reproduce:** `metascience sd-range --sd 0.42 --min-val 1 --max-val 4 --n 64 && metascience sd-range --sd 0.42 --min-val 1.25 --max-val 5 --n 64 && metascience extract --pdf-path /mnt/c/Users/gregs/agent_for_forensic_metascience/high_value_pdfs_to_run_on/10.1002--ajcp.70049/10.1002--ajcp.70049.pdf --first-page 5 --last-page 8`

### 2. All three regression tables label coefficient/standard-error columns as 'M (SD)' and gloss SD as 'standard deviation'  [SUSPICIOUS | confidence: high]

- **Location:** Tables 2, 3 and 4, column sub-headers and footnotes (pp. 596-598); 63 estimate cells
- **Reported:** Each table prints a group header 'Coefficient' over a sub-header row reading '| Variable | M (SD) | p | M (SD) | p | M (SD) | p |', with the footnote 'Abbreviations: EBP, evidence-based programs; SD, standard deviation.'
- **Computed:** The parenthetical values are standard errors, not standard deviations: check_regression reproduces the printed p from b/SE in 59 of 63 cells (e.g. 1.01/0.38 gives p = 0.0079 against a printed .01; 0.85/0.47 gives p = 0.0705 against a printed .07; 8.57/3.03 gives p = 0.0047). A mean/SD reading is not compatible with the printed p-values. Three tables and 63 cells are affected, and Table 1 uses the same '(mean, SD)' notation for a genuinely different quantity.
- **Assumptions:** Assumes Stata's normal reference for Poisson, negative binomial and mixed-model output (emulated with df = 1000000). Confirmed verbatim in the source PDF by Stage 1, so this is the published text rather than an extraction artifact.
- **Reproduce:** `metascience extract --pdf-path /mnt/c/Users/gregs/agent_for_forensic_metascience/high_value_pdfs_to_run_on/10.1002--ajcp.70049/10.1002--ajcp.70049.pdf --first-page 7 --last-page 8`

### 3. Nine correlated primary tests with no multiplicity correction, on models whose covariates were selected by screening against the same outcomes  [SUSPICIOUS | confidence: high]

- **Location:** Methods, Covariates paragraph (p. 595); Tables 2-4; Results paragraph 3
- **Reported:** "Variables were retained in the final models as covariates only if bivariate associations had p values under 0.10." Nine primary tests (3 leadership facets x 3 EBP outcomes) with p = .01, .03, .07, .03, .01, .03, .38, .96, .89. No correction is described anywhere. Eight candidate covariates are named; four appear in the final models.
- **Computed:** Five of nine primary tests reach p < .05 and none is stronger than p = .01. The three predictors are facets of one construct from the same member survey and the three outcomes are functions of the same coalitions' EBP portfolios, so the tests are far from independent. Four named candidates (community poverty, state, coalition age, service-area population) were dropped and their bivariate statistics appear nowhere, so the number of tests actually performed is not recoverable. State was dropped despite an 85.94%/14.06% Pennsylvania-Missouri split, and service-area population despite being motivated in the text as needed 'to contextualize EBP reach'.
- **Assumptions:** No forensic tool adjudicates multiplicity or data-dependent model selection; this is a structural reading of the enumerated test inventory and the stated Methods procedure. The reproduction command surfaces the text and tables, not a verdict.
- **Reproduce:** `metascience extract --pdf-path /mnt/c/Users/gregs/agent_for_forensic_metascience/high_value_pdfs_to_run_on/10.1002--ajcp.70049/10.1002--ajcp.70049.pdf --first-page 5 --last-page 8`

### 4. Internally inconsistent p-value rendering: a p printed as exactly '0', and two '<.001' cells that recompute above .001  [SUSPICIOUS | confidence: medium]

- **Location:** Table 2 Constant model 1; Table 3 Communities That Care model 1; Table 3 Number of EBP at baseline model 2; Table 3 Inclusive decision making model 2
- **Reported:** 'Constant | -4.51 (1.50) | <.001'; 'Communities That Care | 3.16 (0.98) | <.001'; 'Number of EBP at baseline | 0.01 (0.001) | 0'; 'Inclusive decision making | 8.57 (3.03) | .01'
- **Computed:** check_regression on the printed b and SE gives p = 0.00264 for the constant (z = -3.007) and p = 0.00126 for Communities That Care (z = 3.224); both exceed the printed bound of .001, and Stage 1 found the discrepancy survives the most extreme corner of the rounding intervals (0.0025 and 0.0012 respectively). A p-value printed as exactly '0' is not an attainable value for a probability, and the adjacent model in the same row uses '<.001' for the same quantity. The Inclusive decision making cell recomputes to p = 0.0047, which at the table's two-decimal precision would print as .00 rather than .01.
- **As printed in the paper:** “Communities That Care | 3.16 (0.98) | <.001” _(found in a table)_
- **Assumptions:** Assumes a normal reference (df = 1000000), matching Stata's reporting for Poisson and negative binomial; Stage 1 checked t(57) as a sensitivity and the constant still gives 0.0039, above .001. Note that check_regression's own p_matches flag returned true and severity 'consistent' for the two '<.001' cells because its tolerance is lenient -- the judgment rests on the computed p exceeding the printed bound, not on the flag. All four cells are intercepts, covariates or conservative roundings, so none changes an inferential conclusion. check_regression is exposed only through the MCP server; there is no metascience CLI verb, so the reproduction command below retrieves the printed values rather than recomputing them.
- **Reproduce:** `metascience extract --pdf-path /mnt/c/Users/gregs/agent_for_forensic_metascience/high_value_pdfs_to_run_on/10.1002--ajcp.70049/10.1002--ajcp.70049.pdf --first-page 7 --last-page 7`

### 5. The fidelity null is stated as an absence of association, with no confidence intervals and no equivalence threshold to support it  [INDETERMINATE | confidence: medium]

- **Location:** Abstract, Results paragraph 3, Discussion and Conclusion; Table 4 (n = 101 programs in 35 coalitions)
- **Reported:** "none of the inclusive leadership practices that we examined was associated with subsequent EBP fidelity" and "Contrary to expectation, no facet of inclusive leadership was associated with EBP intervention fidelity." Table 4: Communication 0.53 (0.60), p = .38; Inclusive decision making -0.05 (0.98), p = .96; Inclusion of community residents -0.10 (0.72), p = .89.
- **Computed:** Not computable from the published numbers. absence_of_evidence requires ci_low and ci_high and the paper reports no confidence interval for any coefficient in any table; no smallest effect size of interest is stated, so the tool would decline to judge equivalence even with an interval. What is visible on the face of Table 4 is that the standard errors (0.60, 0.98, 0.72) are large relative to a 1-7 fidelity outcome, and that this analysis rests on 35 of the 64 coalitions.
- **As printed in the paper:** “In contrast, none of the inclusive leadership practices that we examined was associated with subsequent EBP fidelity (Table 4). ... Contrary to expectation, no facet of inclusive leadership was associated with EBP intervention fidelity.” _(found in the paper's text, across an ellipsis)_
- **Assumptions:** Deriving an interval from b and SE would be unvalidated hand arithmetic and was not done. Recorded as indeterminate rather than as a pass: 'not significant' has been reported as 'not associated', and the paper supplies nothing that lets a reader distinguish the two. The paper's own Highlights are more careful -- 'It is not yet clear how inclusive leadership improves evidence-based practice fidelity.'
- **Reproduce:** `metascience extract --pdf-path /mnt/c/Users/gregs/agent_for_forensic_metascience/high_value_pdfs_to_run_on/10.1002--ajcp.70049/10.1002--ajcp.70049.pdf --first-page 8 --last-page 8`

### 6. An embedded randomized trial whose allocation balance is never shown  [INDETERMINATE | confidence: medium]  ⚠ not backed by a sweep finding

- **Location:** Methods, sample paragraph (p. 593); Table 1
- **Reported:** "The sample began with 68 Pennsylvania and Missouri youth substance misuse prevention coalitions. Half of these coalitions were randomly assigned to participate in the Coalition Check-Up technical assistance (TA)." All models include a binary Coalition Check-Up assignment indicator. Table 1 reports a single pooled column headed 'All coalitions n = 64'.
- **Computed:** Not testable. csf_test and bayesian_table1_dispersion require baseline characteristics reported separately by arm with per-arm ns; no by-arm baseline summaries or p-values exist in the paper, so neither baseline uniformity nor baseline imbalance can be assessed in either direction. No claim about randomization quality is made here.
- **Assumptions:** This is a secondary observational analysis rather than a report of the trial itself, so a by-arm Table 1 is not strictly required by reporting convention; it is nonetheless a gap given that treatment assignment is a covariate in all nine models and that TA level -- which the paper says 'varied between coalitions assigned to the Coalition Check-Up process and those that were not' -- is a second covariate on the same causal pathway. No stage-1 tool backs this entry; it is a design observation.
- **Reproduce:** `metascience extract --pdf-path /mnt/c/Users/gregs/agent_for_forensic_metascience/high_value_pdfs_to_run_on/10.1002--ajcp.70049/10.1002--ajcp.70049.pdf --first-page 3 --last-page 6`

## What we could NOT check

- **Table 4 null results (fidelity) -- equivalence / precision assessment** — absence_of_evidence requires ci_low and ci_high, and the paper reports no confidence intervals for any coefficient in any table. Deriving an interval from b and SE would be unvalidated hand arithmetic. No smallest effect size of interest is stated either, so the tool would decline to judge equivalence even with an interval.
- **Methods -- statistical power** — The paper states no a-priori power analysis: no target power, no assumed effect size, no alpha. verify_power_analysis returns indeterminate unless every input was actually stated, so it was not run rather than run on invented inputs. This is itself a reporting gap for a study with 64 clusters and nine primary tests.
- **Baseline comparability between the randomized Coalition Check-Up arm and the TA-as-usual arm** — csf_test and bayesian_table1_dispersion require baseline characteristics reported separately by arm with per-arm ns. Table 1 pools all 64 coalitions into a single column, so no by-arm baseline p-values or summaries exist to test. Randomization balance cannot be assessed in either direction.
- **Table 1 -- Population of service area, mean 84,299 (SD 108,353)** — Continuous, unbounded measure with no stated range. GRIM/GRIMMER/SPRITE are inapplicable to continuous data, and check_sd_range needs bounds the paper does not give. Inventing a plausible population range would violate rulebook rule 4. An SD exceeding the mean is unremarkable for a right-skewed population count.
- **Table 1 -- Number of coalition members, mean 35.78 (SD 33.74)** — A count with no stated upper bound. check_table refused GRIMMER and SPRITE here because the default 1-7 Likert fallback would manufacture an impossibility for an unbounded variable. No stated or logically necessary maximum exists, so no granularity check is admissible.
- **Table 1 -- 'EBP adherence 5.23 (1.13)': denominator and cell type** — The row is printed in a column headed 'All coalitions n = 64' but fidelity is a program-level measure (Table 4 reports 101 programs). The paper does not state the n for this row, it is the only continuous row carrying no '(mean, SD)' annotation, and it types as ambiguous on syntax alone. The SD-range check was run and is insensitive to the choice of n, but no n-dependent check could be applied.
- **Table 1 -- 'Use at least one EBP' (38, 59%) reconciled against 'Number of EBPs' (1.67, 2.15)** — 38 of 64 implies exactly 26 coalitions with a count of zero. The Python SPRITE sampler produced 36-38 zeros in all 300 reconstructions, but the rsprite2 cross-check returned valid distributions with markedly fewer zeros. Engine disagreement is an instrumentation problem, not evidence about the paper, so no anomaly is claimed. A reader with the raw data could settle it.
- **Supporting Information S1: Tables S1 and S2 (registry hierarchy used to classify programs as EBPs)** — Cited in Methods as the source of the predetermined ordering of EBP registries but not provided with the paper files supplied for this analysis. The EBP classification drives both primary outcomes, so this is a material dependency that could not be inspected.
- **Bivariate covariate-screening tests (Methods, Covariates paragraph)** — The paper states that candidate covariates were screened at bivariate p < 0.10 but reports none of the resulting statistics. With no coefficients, test statistics or p-values printed, there is nothing to recalculate and the number of tests performed is not recoverable.
- **Reported reliability statistics (Cronbach's alpha 0.93 and 0.88; inter-item correlations 0.80 and 0.76) and the unconditional ICC of 0.10** — No tool in this toolkit verifies internal-consistency coefficients or an ICC against item-level data, and the item-level data are not reported. All values are within ordinary ranges and none is out of bounds on its face.
- **Figures** — The article contains no data figures; the image placeholders in the extraction are journal furniture (logos, rules, section ornaments). No figure-derived quantities were used anywhere in this review.

## Limitations

- This agent reads text and tables only and does not see figures. In this paper that costs nothing, because the article contains no data figures -- every reported statistic lives in the text or in Tables 1-4.
- Nothing in this paper is mathematically impossible. Every finding above is a reporting, interpretation or design concern, not an arithmetic contradiction, and none of them rules out the paper's conclusions.
- The regression recomputations assume Stata reports Poisson, negative binomial and mixed-model coefficients against a normal reference (emulated with df = 1000000). A t reference with 57 degrees of freedom was checked as a sensitivity on the flagged cells and did not change any verdict.
- check_regression, the tool that carries most of the verification here, is reachable only through the MCP server; there is no metascience CLI verb for it, so the reproduction strings on those findings retrieve the printed values rather than recomputing them.
- Multiplicity, data-dependent covariate selection and the missing by-arm baseline table are structural readings of the Methods and the reported test inventory. No forensic tool adjudicates them, and they are reported as judgments rather than as tool outputs.
- The zero-count reconciliation between Table 1's '38 (59%) use at least one EBP' and its 'Number of EBPs 1.67 (2.15)' could not be settled: the Python SPRITE engine and rsprite2 disagreed about which zero-counts are attainable, and engine disagreement is treated as an instrumentation problem, not evidence about the paper.
- All numbers quoted here were cross-checked against the source PDF by the numeric sweep, which found zero discrepancies against the markdown extraction. That reduces but does not eliminate the risk that an anomaly reported here originates in extraction rather than in the paper.
- No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.

## Coverage

- **Statistics found:** 91; **checked:** 79
- **Tools run:** parse_table, parse_cells_typed, check_table, statcheck, extract_pdf, grim_sweep, grim_check, grim_percentage, grimmer_check, sprite_reconstruct, r_sprite_ground_truth, check_sd_range, check_summation, check_regression, stalt_check, flag_round_n, detect_duplication
- **Tables checked:** Table 1 (coalition EBPs, inclusive leadership and other attributes, n=64), Table 2 (number of EBPs, Poisson, n=64), Table 3 (EBP reach, negative binomial, n=64), Table 4 (EBP fidelity, HLM, n=101 programs in 35 coalitions)
- **Checkable table cells:** 78 of 143 surveyed; **checked:** 0
    - 70 could not be checked without knowing what kind of quantity the row reports
    - 8 were missing an input: n (8)

## What each check does

One entry per check that ran on this paper. The **assumptions** are the conditions under which its verdict holds; where one is unmet the verdict is capped, not merely caveated.

### `check_regression` — probabilistic

Checks a regression coefficient's t = B/SE and its p within printed rounding.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- Assumes the reported t is B/SE and the reported p its t-distribution tail at the given df.
- t is judged against the interval reachable from the PRINTED precision of B and SE, never a point.
- Both sign conventions (signed t and |t|) and both tail conventions are accepted before anything is flagged.
- Without df only the p check is skipped; the t = B/SE comparison still runs and can flag on its own.

### `check_sd_range` — absolute

Checks a reported SD against the hard ceiling implied by the variable's range.

**What its verdict means.** Absolute (possible vs impossible). Exact arithmetic over the printed values and their rounding intervals. Subject to the preconditions below, a flagged result cannot be produced by any dataset.

**Strongest verdict it may reach:** `impossible`

**It assumes:**
- min_val and max_val must be the variable's TRUE attainable bounds: this tool has no bound_source guard, so supply STATED bounds only -- on an assumed range it can still reach `impossible`.
- Pass decimals_sd; without it the precision is inferred from the literal, which errs wide but is a guess.
- With n unknown the ceiling is the weakest over all n (range/sqrt(2), attained at n = 2); supplying n tightens it.
- A negative SD is bound-free and impossible whatever else is unknown.

### `check_summation` — probabilistic

Checks that printed values sum to their stated total within accumulated rounding.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The values are assumed exhaustive, non-overlapping addends of the stated total; overlap or an omitted row mimics a mismatch.
- The window derives from the printed decimals of every addend and of the total; with neither decimals nor tolerance it refuses.
- Count columns that must hold exactly take tolerance = 0; percentage columns legitimately misbalance by rounding.

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

### `flag_round_n` — probabilistic

Triage flag for several distinct sample sizes that are all suspiciously round.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- A base-rate heuristic: fabricated papers over-represent round Ns, but so do honest recruitment targets.
- Needs at least three reported sizes with at least two distinct before it says anything.
- Ceiling `suspicious`: a weak signal that escalates only alongside stronger findings.

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

### `grim_percentage` — absolute

Tests whether a percentage can be an integer count's share of the sample.

**What its verdict means.** Absolute (possible vs impossible). Exact arithmetic over the printed values and their rounding intervals. Subject to the preconditions below, a flagged result cannot be produced by any dataset.

**Strongest verdict it may reach:** `impossible`

**It assumes:**
- The percentage must be a SHARE of the sample, 100*k/n for integer k.
- Mean changes, concentrations and ratios are refused: they are not constrained to multiples of 100/n.
- n must be the true denominator OF THIS percentage, and `decimals` must match the printed precision.
- Both the round-half and truncation reporting conventions are tried; a truncation-only pass caps at `suspicious`. SPSS and several journal styles truncate percentages, and 9/93 = 9.6774 printed as 9.6% is a truncating reporter, not an impossibility.

### `grim_sweep` — absolute

Finds every sample size at which several percentages could share one denominator.

**What its verdict means.** Absolute (possible vs impossible). Exact arithmetic over the printed values and their rounding intervals. Subject to the preconditions below, a flagged result cannot be produced by any dataset.

**Strongest verdict it may reach:** `impossible`

**It assumes:**
- Every value must be a share of the SAME sample -- a shared denominator is exactly what is being tested.
- An empty intersection reaches `impossible` only when n_max_source='stated' (n_max is the paper's own total N) and n_min covers the floor; otherwise the sweep refuses with `indeterminate` -- emptiness inside a range WE chose is a fact about the search, not the paper.
- No data_type guard here: the caller must verify the values are count shares, not continuous percentages.

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

### `parse_table` — probabilistic

Parses a summary table into normalised cells, and can reconcile two renderings of it.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- Parsing alone renders no verdict; a severity appears only when `cross_check` supplies a second rendering.
- A cross-check disagreement is evidence about OUR EXTRACTION, not about the paper: the likeliest cause by far is that one of the two parsers mis-read the table, so confirm against the source before citing it.
- Both renderings must be of the SAME table; comparing different tables produces a meaningless disagreement.
- Drops cells it cannot reduce to a scalar, such as estimate-plus-CI; use the XML cells route for those.

### `r_sprite_ground_truth` — descriptive

Cross-checks our SPRITE against R's canonical rsprite2 package.

**What its verdict means.** Descriptive. Extracts, parses or computes a quantity; it does not itself render a verdict about the paper.

**Strongest verdict it may reach:** `indeterminate`

**It assumes:**
- Reports rsprite2's result. A disagreement is a bug in our tooling and the finding must not be reported.

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

## What the paper claims

Wells and colleagues report a one-year lagged observational analysis of 64 youth substance-misuse prevention coalitions in Pennsylvania and Missouri, drawn from an ongoing randomized technical-assistance trial. Three facets of "inclusive leadership" measured at baseline from member surveys -- engaging communication, inclusive decision making, and inclusion of community residents -- are used to predict three evidence-based-practice outcomes a year later: the number of EBPs a coalition runs (Poisson), the number of youth and parents those EBPs reach (negative binomial), and implementation fidelity (a hierarchical linear model over 101 programs in 35 coalitions). The abstract concludes that inclusive leadership was positively associated with the first two outcomes but not the third.

## The arithmetic mostly holds

This deserves saying plainly before anything else. Fifty-nine of the 63 coefficient/SE/p triples in Tables 2-4 reproduce their printed p-value from b/SE, and critically **all nine** headline inclusive-leadership tests -- the ones carrying every claim in the abstract and conclusion -- recompute correctly. Table 1 is fully self-consistent: all seven two-decimal percentages simultaneously admit n = 64 and the counts GRIM recovers at that denominator (55, 9, 26, 41, 23, 21, 20) are exactly the counts printed beside them; the technical-assistance categories sum to 64 and to 100%; GRIM, GRIMMER and SPRITE all pass on the one Table 1 mean to which they legitimately apply. There is no duplication across tables, no round-N pattern, and the survey participation rates (1108/1851 and 945/1695) reconcile with their printed percentages. Feasibility checks out too -- NIDA R01 funding, $40 incentives, a documented IRB approval, and 4 of 68 coalitions lost over a year, which is ordinary rather than implausibly low attrition.

## What I set aside from the numeric sweep

Four sweep signals do not survive scrutiny and I have dropped or downgraded them.

The STALT check recovered p-values around 1e-15 to 1e-23 behind the "<.001" printed for *number of EBPs at baseline*, and the tool returned `highly_suspicious`. That verdict does not transfer: these are autoregressive stability coefficients, where a strongly autocorrelated measure predicting itself a year later should produce exactly this. Rulebook rule 2 targets a *headline* effect hidden behind a threshold; this is neither headline nor implausible.

The apparent contradiction of two Table 2 cells printing identical estimates (-0.01, 0.17) with different p-values (.97, .98) dissolves once precision is accounted for -- these are different models whose estimates merely round alike, and the rounding intervals admit p from 0.953 to 0.977.

The Table 3 baseline coefficient 0.01 (0.002) is too coarsely printed to check at all: its rounding intervals admit p anywhere from 0.046 to 1e-23. That is uninformative, not inconsistent, and treating it as a hit would be a false accusation.

Finally, a promising-looking clash between Table 1's "38 (59%) use at least one EBP" and its EBP count distribution could not be settled because the two SPRITE engines disagreed about which zero-counts are attainable. Engine disagreement is our problem, not the authors'.

## What actually limits confidence

The residual problems are interpretive rather than arithmetic, and they compound. The paper's own methodological note is revealing: "Results in Tables 2-4 are shown as coefficients, and do not include effect sizes, as effects are multiplicative and unit increases in key independent variables are idiosyncratic and scale-dependent." That is an accurate description of a real problem, but declining to report effect sizes does not solve it. The three predictors have observed SDs of 0.42, 0.29 and 0.32 (Table 1), so the "one-unit increase" in which every coefficient is expressed spans several times the entire spread of the observed data -- and under the Measures-stated 1-4 scale, with a mean of 3.83, there is less than one scale point of headroom above the average coalition at all. A reader cannot size these associations, and the contradictory scale statement makes it worse rather than better.

Layered on that: nine correlated tests, uncorrected, none of the five positive results stronger than p = .01, in models whose covariates were retained by screening bivariate associations against the same outcomes at p < 0.10 -- with the screening statistics never reported, so the number of tests performed is unrecoverable. The paper's Highlights and Discussion hedge appropriately ("may improve", "may promote"); the abstract and Conclusion do not.

The data availability statement -- "available from Drs. Brown and Chilenski upon reasonable request" -- is standard journal boilerplate rather than a state-but-withhold claim, but combined with the missing Supporting Information tables that define the EBP registry hierarchy, the two quantities that drive both primary outcomes cannot be independently reconstructed.

## Verdict

Nothing here is impossible and the authors' computations largely check out; what I cannot verify is the interpretation built on top of them, and the tables that carry it are mislabelled and internally inconsistent in ways that should have been caught. The findings are plausible but the reporting needs correction before they can be relied on.

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
