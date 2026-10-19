# Forensic review -- RK et al. 2023

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## Suicide Ideation, Plans, and Attempts Among Individuals With Disability by Veteran Status
*Blais RK, Xie Z, Kirby AV, Marlow NM. JAMA Network Open. 2023. doi:10.1001/jamanetworkopen.2023.37679*

**Design:** Cross-sectional survey study; secondary analysis of the National Survey on Drug Use and Health (NSDUH) 2015-2020, complex multistage probability sample, analyzed with SAS PROC SURVEY procedures

<sub>Analysed as `10.1001--jamanetworkopen.2023.37679`</sub>

> **SUSPICIOUS** — The paper's central claim -- that veteran status moderates the disability-suicide association -- is never actually tested: no statistic, df or p-value for the disability x veteran interaction appears anywhere in the article, and the stratum-specific contrasts it is inferred from are null in 7 of the 9 veteran-versus-nonveteran comparisons among people with disability.
>
> **Evidence:** Methods: "Multivariable adjusted multinomial logistic regression with an interaction term for disability status x veteran status estimated adjusted odds ratios (AORs) and 95% CIs" -- yet no interaction test is printed in Table 2, Table 3 or the Results. The nine veteran-vs-nonveteran contrasts among those with disability (Table 2) are: 1 limitation 0.83 (0.59-1.18) p=.30, 0.57 (0.34-0.95) p=.03, 1.19 (0.70-2.04) p=.52; 2 limitations 1.25 (0.81-1.95) p=.32, 1.03 (0.45-2.38) p=.95, 0.46 (0.24-0.88) p=.02; >=3 limitations 0.96 (0.58-1.58) p=.87, 1.14 (0.65-2.03) p=.65, 0.68 (0.32-1.45) p=.32. Only two are significant, and four of the seven null point estimates are ABOVE 1. The >=3-limitation attempt interval [0.32, 1.45] remains compatible with a 3.12-fold effect in either direction.
> **Rests on:** a constraint the paper itself states
> **Reproduce:** `metascience absence-of-evidence --ci-low 0.32 --ci-high 1.45 --measure OR --null-value 1 --claim-of-no-effect`

**Verdict: questionable** (confidence: medium)

> **Table coverage is unmeasured.** No cell was checked through `check_table`, which is the only route this census can count, so none of the 213 checkable cells can be ticked off by id. But 130 per-cell checks did run on values taken off this paper (`absence_of_evidence`, `check_estimate_ci`, `check_summation`, `detect_duplication`, `flag_round_n`, `stalt_check`). How much of the table that covers is not known -- it is not zero, and it is not measured here.

## Provenance of the analysis

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

1 study/studies, 14 variables, 54 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| S1 | NSDUH 2015-2020 pooled cross-sectional survey analysis of US adults aged >=18 y | cross_sectional | 231099 | individual respondent (weighted to 236 551 727 US adults) | yes |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Suicide-related outcome (4-level: none / ideation only / planning without attempt / attempt) | nominal | discrete | 4 categories, not listed | - | measured | percentage GRIM on cell counts | high |
| Number of disabling limitations (0, 1, 2, >=3) | ordinal | discrete | 0-3 (integers) | - | measured | percentage GRIM on cell counts | high |
| Veteran status (nonveteran / veteran) | nominal | discrete | 2 categories, not listed | - | measured | DEBIT; percentage GRIM | high |
| Adjusted odds ratio from multinomial logistic regression | ratio | continuous | range not stated | - | measured | none -- not integer-valued | high |
| Average marginal effect (risk-difference scale) | interval | continuous | -1 to 1 | - | measured | none -- not integer-valued | high |
| Weighted percentage of a baseline characteristic within veteran stratum | ratio | continuous | 0-100 | % | measured | percentage GRIM | high |
| Weighted number of US adults in a characteristic category | ratio | continuous | range not stated | weighted persons | measured | none -- not integer-valued | high |
| Age group (18-25, 26-34, 35-49, 50-64, >=65) | ordinal | discrete | 5 categories, not listed | - | measured | percentage GRIM on cell counts | high |
| Sex (male/female) | nominal | discrete | 2 categories, not listed | - | measured | DEBIT; percentage GRIM | high |
| Race and ethnicity (7-level) | nominal | discrete | 7 categories, not listed | - | measured | percentage GRIM on cell counts | high |
| Number of chronic conditions (0, 1, >=2) | ordinal | discrete | 3 categories, not listed | - | measured | GRIM (needs stated max) | high |
| Number of emergency department visits (0, 1, 2, >=3) | ordinal | discrete | 4 categories, not listed | - | measured | GRIM (needs stated max) | high |
| Self-rated health status (excellent/very good/good/fair-poor) | ordinal | discrete | 4 categories, not listed | - | measured | percentage GRIM on cell counts | high |
| Remaining covariates (marital status, education, employment, household income, insurance, urbanization, ever smoked, alcohol dependence, illicit drug dependence, depressive episode, survey year) | nominal | discrete | not stated | - | measured | percentage GRIM on cell counts | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Table 1, 18 baseline rows, P value column (16 rows report P<.001; suicide-related outcome P=.002; alcohol dependence P=.006). Design-based test type not stated by the authors. | chi_squared | Weighted percentage of a baseline characteristic within veteran stratum (proportion) | - | 231099 | none | none reported |
| Table 2, Veteran / 1 Limitation, Suicidal ideation only | logistic_regression | Suicide-related outcome (4-level: none / ideation only / planning without attempt / attempt) (nominal_category) | Number of disabling limitations (0, 1, 2, >=3), Veteran status (nonveteran / veteran) | 231099 | none | variance inflation factor for multicollinearity |
| Table 2, Veteran / 2 Limitations, Suicidal ideation only | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, Veteran / >=3 Limitations, Suicidal ideation only | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, Veteran / 1 Limitation, Suicide planning without attempt | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, Veteran / 2 Limitations, Suicide planning | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, Veteran / >=3 Limitations, Suicide planning | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, Veteran / 1 Limitation, Suicide attempt | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, Veteran / 2 Limitations, Suicide attempt | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, Veteran / >=3 Limitations, Suicide attempt | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, Nonveteran / 1 Limitation, Suicidal ideation only | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, Nonveteran / 2 Limitations, Suicidal ideation only | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, Nonveteran / >=3 Limitations, Suicidal ideation only | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, Nonveteran / 1 Limitation, Suicide planning | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, Nonveteran / 2 Limitations, Suicide planning | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, Nonveteran / >=3 Limitations, Suicide planning | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, Nonveteran / 1 Limitation, Suicide attempt | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, Nonveteran / 2 Limitations, Suicide attempt | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, Nonveteran / >=3 Limitations, Suicide attempt | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, No limitations / Veteran vs Nonveteran, Suicidal ideation only | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, No limitations / Veteran vs Nonveteran, Suicide planning | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, No limitations / Veteran vs Nonveteran, Suicide attempt | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, 1 Limitation / Veteran vs Nonveteran, Suicidal ideation only | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, 1 Limitation / Veteran vs Nonveteran, Suicide planning | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, 1 Limitation / Veteran vs Nonveteran, Suicide attempt | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, 2 Limitations / Veteran vs Nonveteran, Suicidal ideation only | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, 2 Limitations / Veteran vs Nonveteran, Suicide planning | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, 2 Limitations / Veteran vs Nonveteran, Suicide attempt | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, >=3 Limitations / Veteran vs Nonveteran, Suicidal ideation only | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, >=3 Limitations / Veteran vs Nonveteran, Suicide planning | logistic_regression | ? | - | 231099 | none | none reported |
| Table 2, >=3 Limitations / Veteran vs Nonveteran, Suicide attempt | logistic_regression | ? | - | 231099 | none | none reported |
| Table 3, Veteran / 1 Limitation, planning vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, Veteran / 2 Limitations, planning vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, Veteran / >=3 Limitations, planning vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, Veteran / 1 Limitation, attempt vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, Veteran / 2 Limitations, attempt vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, Veteran / >=3 Limitations, attempt vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, Nonveteran / 1 Limitation, planning vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, Nonveteran / 2 Limitations, planning vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, Nonveteran / >=3 Limitations, planning vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, Nonveteran / 1 Limitation, attempt vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, Nonveteran / 2 Limitations, attempt vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, Nonveteran / >=3 Limitations, attempt vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, No limitations / Veteran vs Nonveteran, planning vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, No limitations / Veteran vs Nonveteran, attempt vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, 1 Limitation / Veteran vs Nonveteran, planning vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, 1 Limitation / Veteran vs Nonveteran, attempt vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, 2 Limitations / Veteran vs Nonveteran, planning vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, 2 Limitations / Veteran vs Nonveteran, attempt vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, >=3 Limitations / Veteran vs Nonveteran, planning vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Table 3, >=3 Limitations / Veteran vs Nonveteran, attempt vs ideation only | logistic_regression | ? | - | ? | none | none reported |
| Tables 2 and 3, AME (95% CI) columns - 50 average marginal effects sharing the AOR p-value column. In Table 2 nearly all AMEs print as 0 or 0.01 with bounds of 0/+-0.01, i.e. rounded too coarsely to test. | other | Average marginal effect (risk-difference scale) (continuous) | - | 231099 | none | none reported |
| Methods, Statistical Analysis - disability x veteran interaction term. NO test statistic, df or p-value for the interaction itself is reported anywhere in the article, despite moderation being the paper's central claim. | logistic_regression | ? | - | 231099 | none | none reported |
| eTables 3 and 4 in Supplement 1 - multiple-imputation sensitivity analyses (N = 241 675). Supplement not provided; ~50 further estimates are cited in the Results text but could not be inspected. | logistic_regression | ? | - | 241675 | none | none reported |

_53 of 54 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. Moderation is claimed but never tested; the inference is a difference-in-significance fallacy  [SUSPICIOUS | confidence: high]

- **Location:** Methods (Statistical Analysis); Tables 2 and 3; Results, "Suicide Ideation, Planning, and Attempt by Veteran and Disability Status"; Conclusions
- **Reported:** Methods state an interaction term for disability status x veteran status was fitted. Title, Key Points, Discussion ("being a US veteran mitigated the association of disability status and risk for suicide") and Conclusions ("exploring veteran status as a moderator") all assert moderation. The Results close with "No significant differences in risks for suicide were observed by veteran status among people reporting 3 or more disabling limitations."
- **Computed:** Zero interaction test statistics, df or p-values are printed anywhere in the article; 50 stratum-specific simple-effect contrasts are reported instead. The >=3-limitation stratum, on which the "no difference" statement rests, is uninformative rather than null: attempt [0.32, 1.45] permits a 3.12-fold effect either way, planning [0.65, 2.03] a 2.03-fold effect, ideation [0.58, 1.58] a 1.72-fold effect. Each is compatible with the same magnitude of effect observed in the strata the paper calls significant, so declaring the strata different requires the interaction test that is absent.
- **As printed in the paper:** “No significant differences in risks for suicide were observed by veteran status among people reporting 3 or more disabling limitations.” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own statements. The absence-of-evidence tool declines to judge equivalence because the paper states no smallest effect size of interest; that refusal is the correct result and is what establishes the stratum is uninformative, not null.
- **Reproduce:** `metascience absence-of-evidence --ci-low 0.32 --ci-high 1.45 --measure OR --null-value 1 --claim-of-no-effect`

### 2. Conclusions describe as "uniform" a pattern that is mostly null in the paper's own tables, and rest on one result the authors' own sensitivity analysis did not replicate  [SUSPICIOUS | confidence: high]

- **Location:** Key Points; Discussion paragraph 1; Results, "Suicide Ideation, Planning, and Attempt by Veteran and Disability Status"; Table 2
- **Reported:** Key Points: "service in the military was associated with higher suicide risk among those without disability. However, among those with disability, military service was associated with lower suicide risk." Discussion: "results were not uniform across all levels of risk for suicide and disability status, but were uniform among veteran status."
- **Computed:** Among those WITHOUT disability, only 1 of 3 outcomes is significant (planning AOR 1.71 [1.17-2.49], p=.006, recovered p=.0054); ideation 1.12 [0.88-1.42] permits at most a 1.42-fold effect and attempt 0.98 [0.60-1.59] at most 1.67-fold -- both uninformative. The Results themselves state the 1.71 result "was not significant in sensitivity analyses (eTable 3 in Supplement 1)." Among those WITH disability, 7 of 9 contrasts are null and four of those seven point ABOVE 1 (1.19, 1.25, 1.03, 1.14), i.e. toward higher risk in veterans. "Uniform" is not a defensible description of this pattern.
- **As printed in the paper:** “No significant differences in risks for suicide were observed by veteran status among people reporting 3 or more disabling limitations.” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own statements. Counting significant versus null contrasts is an enumeration of Table 2, not a tool computation; the interval widths cited were computed by absence_of_evidence and check_estimate_ci.
- **Reproduce:** `metascience absence-of-evidence --ci-low 0.88 --ci-high 1.42 --measure OR --null-value 1 --claim-of-no-effect`

### 3. A Table 3 average marginal effect is arithmetically inconsistent with its own confidence interval  [SUSPICIOUS | confidence: high]

- **Location:** Table 3, Nonveteran / >=3 Limitations, Suicide attempt (vs suicidal ideation only), AME column
- **Reported:** "1.36 (0.98 to 1.89) | .07 | 0.04 (-0.01 to 0.05)"
- **Computed:** The printed AME of 0.04 is not the arithmetic midpoint of [-0.01, 0.05], whose centre is 0.02, and the interval implies p = .0090 against a printed p = .07. All 19 other AME cells in Table 3 sit correctly at the midpoint of their own intervals, and the companion planning cell on the same table line reads 0.04 (-0.01 to 0.10), symmetric about 0.045. The isolation of the anomaly makes a mis-set upper bound (0.09 or 0.10 printed as 0.05) the most economical explanation.
- **Assumptions:** AMEs are on a linear risk-difference scale, so arithmetic (not geometric) symmetry is the correct test; this follows from the measure and is not an assumed bound. Warrants a published correction; it is not evidence of anything beyond a printing error, and it does not affect any conclusion.
- **Reproduce:** `metascience check-ci --estimate 0.04 --ci-low -0.01 --ci-high 0.05 --null-value 0 --reported-p 0.07`

### 4. Fifty odds-ratio contrasts tested at alpha = .05 with no multiplicity adjustment, and every headline result sits near the threshold  [SUSPICIOUS | confidence: high]

- **Location:** Methods, Statistical Analysis; Tables 2 and 3
- **Reported:** "Test-specific significance levels were assessed at alpha <= .05." No correction is mentioned anywhere.
- **Computed:** Tables 2 and 3 contain 50 non-reference AOR contrasts, plus 18 baseline comparisons in Table 1 and roughly 50 more cited from the sensitivity eTables. At alpha = .05 across the 50 primary contrasts alone, about 2.5 false positives are expected. Both results supporting the "protection among those with disability" claim recover p just under threshold (0.57 [0.34-0.95] recovers p = .0320; 0.46 [0.24-0.88] recovers p = .0191), as do several others the Results emphasise (1.50 [1.01-2.23] recovers p = .0448, with a lower bound of 1.01; 1.61 [1.03-2.49] recovers p = .0344; 0.49 [0.24-0.97] recovers p = .0453). None would survive even a modest correction.
- **Assumptions:** The count of the test family is an enumeration of the paper's contents, not a tool output; the recovered p-values were computed by check_estimate_ci on the log scale. No individual number is wrong -- this bears on how many of the 50 should be believed.
- **Reproduce:** `metascience check-ci --estimate 1.50 --ci-low 1.01 --ci-high 2.23 --measure OR --reported-p 0.04`

### 5. Outcome substitution: self-reported 12-month ideation and attempt are presented as evidence that military service is protective against suicide  [SUSPICIOUS | confidence: medium]  ⚠ not backed by a sweep finding

- **Location:** Key Points ("Meaning"); Introduction paragraph 2; Conclusions; Measures, "Risk for Suicide"
- **Reported:** Measured outcome: three dichotomous self-report items about the past 12 months. Key Points "Meaning": "military service could be a protective factor against suicide among a subpopulation of US adults." Conclusions: "prior military service may be protective against suicide when considering disability status."
- **Computed:** The paper's own Introduction states the opposite for the outcome the conclusion invokes: "In 2020, 6146 veterans died by suicide with an unadjusted rate of 31.7 per 100 000 people. This is over twice the general US population suicide rate, with elevated risk among veterans consistently observed over a 19-year period." A protective association for self-reported 12-month ideation and attempt does not license a claim about suicide, and the substitution is not flagged in the Limitations, which raise self-report only as a measurement-accuracy concern.
- **Assumptions:** No metascience tool adjudicates a conclusion-versus-outcome mismatch; this is a reading of the paper's stated measure against its stated conclusion, using the paper's own cited mortality figures. No assumed bounds are involved.
- **Reproduce:** no runnable command -- the review did not supply a command here. The finding's own numbers are above; re-derive from those.

### 6. One "<.001" threshold is not supported by its own confidence interval  [SUSPICIOUS | confidence: low]

- **Location:** Table 2, Veteran / >=3 Limitations, Suicidal ideation only
- **Reported:** "2.27 (1.34 to 3.86) <.001"
- **Computed:** The interval recovers p = .0024, roughly 2.4 times the printed threshold. The estimate and interval are mutually consistent with each other (the tool grades the pair "consistent"; it is the threshold LABEL that does not follow). Three neighbouring cells labelled <.001 recover p-values that genuinely clear it -- 2.60 (1.59-4.24) recovers p = 1.3e-4, 2.02 (1.80-2.27) recovers p < 1e-16, and 3.68 (2.69-5.05) recovers p = 4.4e-16 -- which isolates this cell rather than implicating the column.
- **As printed in the paper:** “2.27 (1.34 to 3.86)c <.001” _(found in the PDF text layer)_
- **Assumptions:** p is recovered by a normal approximation on the log-OR scale. A design-based t reference distribution would shrink the recovered p somewhat, and NSDUH's design degrees of freedom are not stated in the article, so I could not test how far. Ranked last and given low confidence for that reason; substantively harmless, since the result is significant on either reading. Note that Stage 1 graded this cell 'suspicious'; the tool's own verdict on the estimate-CI pair is 'consistent', and only the threshold label is at issue.
- **Reproduce:** `metascience check-ci --estimate 2.27 --ci-low 1.34 --ci-high 3.86 --measure OR`

### 7. The headline association is produced entirely by covariate adjustment across groups with very little demographic overlap  [INDETERMINATE | confidence: medium]  ⚠ not backed by a sweep finding

- **Location:** Table 1; Table 2, No limitations / Veteran vs Nonveteran; Discussion paragraph 2
- **Reported:** Table 1 crude weighted percentages -- veterans vs nonveterans: suicidal ideation only 2.8% vs 3.1%, planning 0.8% vs 0.8%, attempt 0.3% vs 0.6%. Composition: veterans 91.0% male and 48.8% aged >=65; nonveterans 44.0% male and 17.8% aged >=65.
- **Computed:** Crude figures show veterans reporting equal or LOWER suicidality on all three outcomes, yet the adjusted model yields AOR 1.71 (1.17-2.49) for planning among those with no disability. The "higher risk without disability" claim is therefore a product of the adjustment, over exposure groups that differ by 47 percentage points on sex and 31 points on age >=65. The Discussion attributes the protective finding to Department of Veterans Affairs services while conceding "the veteran group was not limited to those using VA health services, nor was assessment for receipt of DRC among veterans included in the NSDUH."
- **Assumptions:** Table 1 is not stratified by disability status, so the crude-versus-adjusted contrast is suggestive rather than dispositive -- adjustment for age and sex can legitimately reverse a marginal association. Recorded as indeterminate for that reason. No forensic tool quantifies residual confounding or covariate overlap; no assumed bounds are involved.
- **Reproduce:** no runnable command -- the review did not supply a command here. The finding's own numbers are above; re-derive from those.

## What we could NOT check

- **eTables 1 and 2 in Supplement 1 (bivariate associations of all covariates with suicide-related outcomes and with disability status)** — Supplement 1 was not provided. The Results assert "All evaluated covariates had significant bivariate associations" -- roughly 36 further comparisons -- and this claim drove covariate selection for every adjusted model in the paper.
- **eTable 3 in Supplement 1 (multiple-imputation sensitivity analysis, N = 241 675)** — Supplement not provided. About 30 further AORs are cited in the Results. Its N of 241 675 implies the outcome and the exposure were themselves imputed for the 3315 respondents missing suicide, disability or veteran information -- a substantive analytic choice that could not be examined.
- **eTable 4 in Supplement 1 (multiple-imputation sensitivity analysis among those with suicidal ideation)** — Supplement not provided. The Results rely on it for three claims significant ONLY in the sensitivity analysis (nonveterans with >=3 limitations for planning; nonveterans with >=3 disabilities for attempt; veterans with 1 limitation for planning), and for one headline claim that LOSES significance there (the 1.71 planning result). None could be verified.
- **Supplement 2 (Data Sharing Statement)** — Not provided with the paper. The body states the NSDUH data set is publicly available -- which is true of the NSDUH public-use files -- but the specific sharing commitments and any analytic-code availability could not be inspected.
- **Table 1, P value column (18 baseline comparisons)** — The authors do not state which test produced these p-values (design-based Rao-Scott chi-squared and Wald F are both plausible under PROC SURVEYFREQ), and 16 of 18 rows print only a threshold. Without the test type, cell counts or exact p-values, no recalculation is possible.
- **Table 2, AME (95% CI) column, all 30 cells** — Printed to 2 decimals on values of magnitude <= 0.03, with twelve cells reading exactly "0 (0 to 0)" or similar. The rounding destroys the resolution that midpoint and p-recovery checks require; running them would generate spurious flags rather than information.
- **Results text percentages 20.03% and 4.39%** — No validated tool performs a ratio recomputation from a weighted numerator and denominator, and grim_percentage is inapplicable to weighted survey estimates. Both numerators and the denominator were independently confirmed by check_summation; only the final division is unverified.
- **One AME cell in Table 2 (1 Limitation / Veteran vs Nonveteran, ideation)** — The cell breaks across a line in both the rotated PDF and the markdown extraction, probably losing a leading minus sign. parse_cells_typed classified it non_numeric, so it was not fed to any tool, per the rule against checking a value of unknown meaning.
- **Headline effect size versus external field benchmarks** — check_effect_plausibility requires a Cohen's d or group means/SDs/ns. This paper reports only odds ratios from a multinomial model with no group-level summary statistics, so no d can be formed and no benchmark comparison is possible without inventing inputs.
- **GRIM / GRIMMER / SPRITE / DEBIT on all Table 1 percentages** — Deliberately not run. Every percentage in Table 1 is a design-weighted estimate whose numerator is a sum of person-level survey weights, not an integer count, so the granularity argument does not hold. Supplying the unweighted n as a denominator would test a quantity the paper never computed.
- **Carlisle-Stouffer-Fisher and Table-1 dispersion tests** — Deliberately not run, and correctly so. Both presuppose random allocation. This is an observational comparison of veterans with nonveterans, so the null they assume does not exist; running them would have inverted the logic of rulebook rule 1.
- **A-priori power or minimum-detectable-effect analysis** — The paper states none, so verify_power_analysis would have required inventing the effect size, alpha and target power. For a secondary analysis of a fixed existing survey this is defensible, but it means the small veteran strata carry no stated minimum detectable effect.

## Limitations

- This agent reads text and tables only and does not see figures. The article's sole figure is a cohort-selection flow diagram whose 11 counts were extracted as text and fully reconciled; there are no data figures (no plotted means, error bars or effect estimates), so no figure-derived quantities were required.
- Supplement 1 (eTables 1-4) and Supplement 2 were not available. Roughly 80 further estimates are cited in the Results, including three claims that are significant only in the sensitivity analyses and one headline claim that loses significance there. My assessment of the paper's evidentiary base is therefore incomplete in a direction that matters.
- All p-values recovered from confidence intervals use a normal approximation on the log-odds scale. The analysis used design-based SAS PROC SURVEY procedures with a t reference distribution, and NSDUH's design degrees of freedom are not stated in the article, so small discrepancies between recovered and printed p-values cannot be fully adjudicated.
- Table 2 is typeset rotated in the PDF and extracts character-reversed; both the PDF and markdown renderings were decoded and reconciled cell by cell before any check was run, and they agree completely, but a systematic decoding error would not have been visible to either source.
- Two findings (outcome substitution; residual confounding and covariate overlap) rest on reading the paper's text against its own tables rather than on a tool computation, and are marked as such. No validated tool in the available subset adjudicates either question.
- The multiplicity count is an enumeration of the paper's contents, not a tool output. No tool in the suite performs a family-wise error calculation.
- No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.

## Coverage

- **Statistics found:** 406; **checked:** 158
- **Tools run:** extract_pdf, statcheck, parse_table, parse_cells_typed, check_summation, check_estimate_ci, stalt_check, detect_duplication, absence_of_evidence, flag_round_n
- **Tables checked:** Figure (cohort selection flow diagram, 11 counts), Table 1 page 5 (sociodemographic and clinical characteristics by veteran status), Table 1 page 6 (continued), Table 2 (adjusted multinomial logistic regression, 30 AORs + 30 AMEs, decoded from the rotated PDF and cross-checked against body.md), Table 3 (adjusted multinomial logistic regression among those with suicidal ideation, 20 AORs + 20 AMEs)
- **Checkable table cells:** 213 of 429 surveyed; **checked:** 0
    - 213 could have run as they stand and were never submitted to a check

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

### `check_summation` — probabilistic

Checks that printed values sum to their stated total within accumulated rounding.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The values are assumed exhaustive, non-overlapping addends of the stated total; overlap or an omitted row mimics a mismatch.
- The window derives from the printed decimals of every addend and of the total; with neither decimals nor tolerance it refuses.
- Count columns that must hold exactly take tolerance = 0; percentage columns legitimately misbalance by rounding.

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

This study pools six years of the National Survey on Drug Use and Health (2015-2020) and asks whether prior US military service changes the well-established association between disability and suicide risk. From 231 099 adult respondents, weighted to 236 551 727 US adults, the authors fit an adjusted multinomial logistic regression with a disability x veteran interaction and report that veterans without disability are at higher suicide risk, while among people with disability military service appears protective. The Key Points conclude that "military service could be a protective factor against suicide among a subpopulation of US adults."

**What the arithmetic shows.** This is a clean paper at the level of numbers, and that deserves saying plainly before the criticism. The cohort flow reconciles exactly at both steps (315 661 = 241 675 + 73 986; 241 675 = 231 099 + 7261 + 130 + 1141 + 2044). Fifteen of eighteen weighted-N blocks in Table 1 sum to the stated weighted total with a difference of exactly zero, and the remaining three miss by exactly one person out of 236.5 million -- ordinary display rounding, not an anomaly. Every multi-category percentage column sums to 100 within the 0.1 that one-decimal rounding permits. Seven independent reconciliations between the Results text and Table 1 are exact, and all ten narrative percentage restatements ("71% more likely", "43% lower odds") match their table odds ratios precisely. Across 600 cross-table comparisons there are no duplicated estimate pairs. Of 50 odds ratios in Tables 2 and 3, 49 sit at the geometric centre of their own interval on the log scale; the small p-value drifts Stage 1 flagged in Table 3 are all under 0.012, change no significance call, and reduce to the coarse standard errors implied by printing two-decimal values near 1. I found no signature of data fabrication anywhere.

**A note on Table 1's p-values, since this is where reviews of survey papers usually go wrong.** Sixteen of the eighteen baseline rows print P<.001. In a randomised trial that pattern would be unremarkable and the *opposite* pattern -- uniformly high p-values -- would be the red flag. Neither logic applies here. There is no randomisation; this is a comparison of two naturally occurring populations that differ on essentially everything, at n = 231 099. The Carlisle-Stouffer-Fisher test and Table-1 dispersion analysis were correctly not run, and I confirm that refusal: running them would have inverted their own logic and manufactured a finding out of an expected result.

**Where the paper goes wrong is inferential, not arithmetic.** The problem is that the conclusion is about a comparison the article never reports. The Methods say an interaction term was fitted; no interaction statistic, degrees of freedom or p-value appears in Table 2, Table 3 or the Results. What the tables contain are simple effects within strata, and moderation is being read off the pattern of which ones cleared .05. That is the difference-in-significance fallacy, and here it is doing real work: the >=3-limitation stratum -- the most severely disabled group, where "protection" would matter most -- is not null but uninformative, its intervals compatible with veterans having roughly a third the odds of attempt or triple the odds. The interaction p-value is precisely the quantity that would settle whether the strata differ, and it is the one quantity not printed.

The gap between the tables and the prose compounds this. The Discussion calls the veteran-status result "uniform"; seven of nine contrasts among people with disability are null, and four of those seven point *above* 1. The claim of higher risk among veterans without disability rests on one outcome out of three -- and the Results themselves note that this result "was not significant in sensitivity analyses." Readers of the Key Points are told something considerably firmer than Table 2 supports.

**Two interpretive concerns the numbers cannot settle.** First, the outcome is self-reported 12-month ideation, planning and attempt, but the Conclusions speak of protection "against suicide" -- while the paper's own Introduction documents that veterans die by suicide at over twice the general population rate. Second, the veteran and nonveteran groups differ by 47 percentage points on sex and 31 on age >=65; crude Table 1 percentages show veterans reporting *equal or lower* suicidality on all three outcomes, so the headline association is entirely a product of the adjustment model, over groups with limited covariate overlap. The Discussion attributes the effect to Department of Veterans Affairs services while conceding that VA use was never measured.

Credit where due: the NSDUH public-use files genuinely are downloadable, so this is not a state-but-withhold data-availability pattern. The four supplementary eTables were unavailable to me, however, and several Results claims depend entirely on them.

The underlying data appear sound and the reported statistics largely verify; it is the conclusion that outruns them. The moderation claim, as published, is not supported by any test the paper reports and should not be relied upon without the interaction estimate.

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
