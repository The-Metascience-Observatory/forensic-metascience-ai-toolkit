# Forensic review -- Wells et al. 2026

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## Associations between inclusive community coalition leadership and use of evidence-based practices
*Wells, R., Ranjit, N., Brown, L. D., Chilenski, S. M., & Gaddy, Y. M. American Journal of Community Psychology, 77, 590-601. 2026. doi:10.1002/ajcp.70049*

**Design:** Two-wave lagged observational analysis nested within a cluster-randomized technical-assistance trial; 64 youth substance-misuse prevention coalitions in Pennsylvania and Missouri. Poisson, negative binomial and hierarchical linear regressions.

<sub>Analysed as `10.1002--ajcp.70049`</sub>

> **SUSPICIOUS** — The paper's strongest predictor, engaging communication, is described on two mutually incompatible scales -- the Measures section defines it as the mean of four items each scored 1-4, while the Results report it "on a 1.25-5 scale" -- so the magnitude of the paper's central finding cannot be interpreted.
>
> **Evidence:** Measures: "calculated as the mean of member responses to four items about the frequency, clarity, accuracy, and timeliness, respectively, of communication between coalition leaders and members (response options 1 = Needs a lot of work, 2 = Needs a little work, 3 = Good, 4 = Outstanding; Cronbach's alpha = 0.93)". Results: "the mean level of engaging communication was 3.83 on a 1.25-5 scale, corresponding to 'good' for such facets as frequency." Table 1: "Communication (mean, SD) 3.83 (0.42)". A mean of four items each capped at 4 cannot reach 5. The same sentence carries a second mismatch: on the paper's own anchors 3 = Good and 4 = Outstanding, so 3.83 is nearer Outstanding, not "good". This matters because the paper states it deliberately omits effect sizes: "Results in Tables 2-4 are shown as coefficients, and do not include effect sizes, as effects are multiplicative and unit increases in key independent variables are idiosyncratic and scale-dependent."
> **Rests on:** a constraint the paper itself states
> **Reproduce:** `metascience sd-range --sd 0.42 --min-val 1 --max-val 4 --n 64`

**Verdict: questionable** (confidence: high)

> **Partial table coverage:** 15 of 78 checkable cells were checked cell by cell. This counts only cells reached through `check_table`; a further 121 per-cell checks ran on values off this paper (`absence_of_evidence`, `check_regression`, `check_sd_range`, `check_summation`, `detect_duplication`, `flag_round_n`, `grim_check`, `grim_sweep`, `grimmer_check`, `stalt_check`) and report no cell ids, so the remainder is under-counted by an unknown amount.

## Provenance of the analysis

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

2 study/studies, 15 variables, 63 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| s1 | Coalition-level lagged analysis (number of EBPs, EBP reach) | secondary_analysis | 64 | coalition | yes |
| s2 | Program-level lagged analysis (EBP fidelity), programs nested in coalitions | secondary_analysis | 101 | program nested within coalition (101 programs in 35 coalitions) | yes |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Number of evidence-based programs implemented | ratio | discrete | 0-9 (integers) | programs | measured | GRIM (needs stated max) | high |
| EBP reach (unduplicated annual youth and parents served) | ratio | discrete | 0-5370 (integers) | persons | measured | GRIM (needs stated max) | high |
| EBP fidelity / adherence (mean of youth and parent items) | ordinal | continuous | 1-7 | - | measured | none -- composite granularity is 1/(items x n) | high |
| Engaging communication (coalition-level mean of member responses to 4 items) | ordinal | continuous | 1-4 | - | measured | none -- composite granularity is 1/(items x n) | high |
| Inclusive decision making (coalition-level mean of 3 items) | ordinal | continuous | 1-5 | - | measured | none -- composite granularity is 1/(items x n) | high |
| Inclusion of community residents (coalition-level mean of 2 items) | ordinal | continuous | 1-5 | - | measured | none -- composite granularity is 1/(items x n) | high |
| Number of EBPs at baseline (lagged autoregressive adjustment) | ratio | discrete | range not stated | - | measured | GRIM (needs stated max) | high |
| Follows Communities That Care model | nominal | discrete | 0-1 (integers) | - | measured | DEBIT; percentage GRIM | high |
| Received any external funding at baseline | nominal | discrete | 0-1 (integers) | - | measured | DEBIT; percentage GRIM | high |
| Level of technical assistance received | ordinal | discrete | 0-3 (integers) | - | measured | percentage GRIM on cell counts | high |
| Number of active coalition members (modelled in 10s) | ratio | discrete | range not stated | members | measured | GRIM (needs stated max) | high |
| Population of coalition service area | ratio | discrete | range not stated | persons | measured | GRIM (needs stated max) | medium |
| State (Pennsylvania vs Missouri) | nominal | discrete | 2 categories, not listed | - | measured | DEBIT; percentage GRIM | high |
| Uses at least one evidence-based program | nominal | discrete | 0-1 (integers) | - | measured | DEBIT; percentage GRIM | high |
| Assigned to full Coalition Check-Up TA (randomized) | nominal | discrete | 0-1 (integers) | - | measured | DEBIT; percentage GRIM | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Table 2, Communication, model 1 | other | Number of evidence-based programs implemented (count) | Engaging communication (coalition-level mean of member responses to 4 items), Number of EBPs at baseline (lagged autoregressive adjustment), Follows Communities That Care model, Received any external funding at baseline, Level of technical assistance received, Number of active coalition members (modelled in 10s), Assigned to full Coalition Check-Up TA (randomized) | 64 | none | none reported |
| Table 2, Inclusive decision making, model 2 | other | Number of evidence-based programs implemented (count) | Inclusive decision making (coalition-level mean of 3 items) | 64 | none | none reported |
| Table 2, Inclusion of community residents, model 3 | other | Number of evidence-based programs implemented (count) | Inclusion of community residents (coalition-level mean of 2 items) | 64 | none | none reported |
| Table 3, Communication, model 1 | other | EBP reach (unduplicated annual youth and parents served) (count) | Engaging communication (coalition-level mean of member responses to 4 items) | 64 | none | none reported |
| Table 3, Inclusive decision making, model 2 | other | EBP reach (unduplicated annual youth and parents served) (count) | Inclusive decision making (coalition-level mean of 3 items) | 64 | none | none reported |
| Table 3, Inclusion of community residents, model 3 | other | EBP reach (unduplicated annual youth and parents served) (count) | Inclusion of community residents (coalition-level mean of 2 items) | 64 | none | none reported |
| Table 4, Communication, model 1 | mixed_model | EBP fidelity / adherence (mean of youth and parent items) (likert_composite) | Engaging communication (coalition-level mean of member responses to 4 items) | 101 | none | unconditional ICC of 0.10 for fidelity at Time 2 used to justify hierarchical model |
| Table 4, Inclusive decision making, model 2 | mixed_model | EBP fidelity / adherence (mean of youth and parent items) (likert_composite) | Inclusive decision making (coalition-level mean of 3 items) | 101 | none | none reported |
| Table 4, Inclusion of community residents, model 3 | mixed_model | EBP fidelity / adherence (mean of youth and parent items) (likert_composite) | Inclusion of community residents (coalition-level mean of 2 items) | 101 | none | none reported |
| Table 2, Number of EBP at baseline, model 1 | other | ? | - | 64 | ? | none reported |
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

_62 of 63 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. Engaging communication is reported on two incompatible scales, and its verbal anchor contradicts the paper's own labels  [SUSPICIOUS | confidence: high]

- **Location:** Results paragraph 1 vs Measures (Engaging communication); Table 1
- **Reported:** Results: "the mean level of engaging communication was 3.83 on a 1.25-5 scale, corresponding to 'good' for such facets as frequency." Measures: mean of four items, "response options 1 = Needs a lot of work, 2 = Needs a little work, 3 = Good, 4 = Outstanding". Table 1: 3.83 (0.42).
- **Computed:** A mean of four items each bounded at 4 has an attainable maximum of 4, so a reported scale maximum of 5 exceeds the instrument by 1. Separately, 3.83 sits 0.83 above the "Good" anchor and 0.17 below "Outstanding", so the gloss "corresponding to 'good'" does not follow from the stated labels under either scale reading. check_sd_range under the stated 1-4 item bound returns the reported SD of 0.42 as consistent (27.8% of the maximum possible 1.5119 for a range of 3 at n=64), so the dispersion offers no escape hatch that would require a wider scale.
- **Assumptions:** None beyond the paper's own statements. Both constraints -- the four-item 1-4 response set and the reported 1.25-5 range -- are printed in the paper; no bound was supplied by me. The direction of the error is undetermined: either the response options are misdescribed or the "5" is a typo for "4". The sd-range command reproduces only the dispersion half of the check; the contradiction itself is established by reading the two passages, and no tool in this set takes "reported observed range" and "instrument maximum" as joint inputs.
- **Reproduce:** `metascience sd-range --sd 0.42 --min-val 1 --max-val 4 --n 64`

### 2. Four cells in the p-value column of Tables 2 and 3 cannot be reconciled with the coefficients and standard errors printed beside them, and in one case the paper's own Results text contradicts its own table  [SUSPICIOUS | confidence: high]

- **Location:** Table 2 (Constant, model 1); Table 3 (Communities That Care, model 1; Number of EBP at baseline, model 2); Results paragraph 4
- **Reported:** Table 2: "Constant -4.51 (1.50) <.001". Table 3: "Communities That Care 3.16 (0.98) <.001" and "Number of EBP at baseline 0.01 (0.001) 0". Results text for the same CTC coefficient: "in the models for EBP reach, following the CTC model was significant (p<.01)".
- **Computed:** Table 2 Constant: t = -4.51/1.50 = -3.0067, calculated_p = 0.002642; at the most extreme rounding endpoint (b=-4.515, se=1.495) t = -3.0201, calculated_p = 0.002528; under a small-sample t with df=57 the same endpoint gives 0.003778. The whole attainable interval sits 2.5 to 3.8 times above the claimed threshold. Table 3 CTC: t = 3.2245, calculated_p = 0.0012624; endpoint (b=3.165, se=0.975) t = 3.2462, calculated_p = 0.0011701; under t(df=57) 0.0020905. No rounding or reference distribution reaches p<.001, and the recomputed value satisfies the p<.01 given in the paper's own text, so the table entry is the erroneous one. Table 3 EBP baseline model 2: p printed as exactly "0"; p is strictly positive for any finite statistic, and the printed values give calculated_p = 1.5633e-23. This runs against the paper's own evident convention of rounding p UP to the next tier (8.57/3.03 gives 0.004679 printed as .01; -32.89/12.17 gives 0.006860 printed as .01), under which a p of .0026 should never be labelled <.001.
- **As printed in the paper:** “Communities That Care 3.16 (0.98) <.001” _(found in the PDF text layer)_
- **Assumptions:** df=100000 was used as a numerically exact stand-in for the normal reference distribution Stata applies to Poisson and negative-binomial models; the two threshold cells were re-tested at df=57 and the conclusion is unchanged. IMPORTANT: check_regression's own p_matches flag is generous at small p and returned severity=consistent for the -4.51/1.50 and 3.16/0.98 cells. This finding rests on the tool's calculated_p output compared against the threshold the paper printed, not on the tool's match verdict.
- **Reproduce:** no runnable command -- the review did not supply a command here. The finding's own numbers are above; re-derive from those.

### 3. A null result is asserted in the Highlights, Results, Discussion and Conclusion with nothing in the paper that could bound it  [SUSPICIOUS | confidence: high]

- **Location:** Highlights; Results paragraph 4; Discussion; Conclusion; Table 4
- **Reported:** "In contrast, none of the inclusive leadership practices that we examined was associated with subsequent EBP fidelity (Table 4)." / "Contrary to expectation, no facet of inclusive leadership was associated with EBP intervention fidelity." Table 4: Communication 0.53 (0.60) p=.38; Inclusive decision making -0.05 (0.98) p=.96; Inclusion of community residents -0.10 (0.72) p=.89.
- **Computed:** The three coefficients reproduce arithmetically (0.53/0.60 gives t=0.8833, calculated_p=0.37706, matching the printed .38), so the non-significance is real. But no confidence interval appears anywhere in the paper, the paper explicitly declines to report effect sizes, and no smallest effect size of interest is stated, so absence_of_evidence cannot be run on the paper's own numbers and the largest fidelity effect still compatible with these data cannot be bounded. Compounding this, every predictor in Table 4 is measured at the coalition level, so the coefficients are informed by 35 coalitions rather than 101 programs -- these are the paper's largest standard errors and its least-powered estimates, yet the claim is stated as confidently as the positive ones.
- **Assumptions:** None beyond the paper's own statements. I ran absence_of_evidence once on an interval I derived myself, purely to confirm tool behaviour; that output is deliberately NOT reported as evidence, because the interval is not the paper's. The 35-vs-101 point is a structural reading of the paper's stated nesting, not a tool output -- no tool in this set evaluates level-2 power in a two-level model.
- **Reproduce:** no runnable command -- the review did not supply a command here. The finding's own numbers are above; re-derive from those.

### 4. All three coefficient tables label their estimate columns "M (SD)" and gloss SD as "standard deviation", but the cells contain coefficients and standard errors  [SUSPICIOUS | confidence: high]

- **Location:** Tables 2, 3 and 4 -- column headers and abbreviation footnotes
- **Reported:** Header row of each table: "Coefficient | Variable M (SD) p". Footnote of each table: "Abbreviations: EBP, evidence-based programs; SD, standard deviation."
- **Computed:** Treating the parenthesised values as standard errors reproduces 59 of the 63 reported p-values across the three tables via t = b/SE; read as standard deviations they would carry no relation to the p-values printed beside them. The tables are headed "Coefficient", so the intent is clear, but the labels as printed are wrong in every table.
- **Assumptions:** None beyond the paper's own statements. The corroborating recomputation used the MCP-only check_regression. Reported because the paper supplies no effect sizes and no confidence intervals, so these mislabelled columns are the sole quantitative description of every finding in the paper.
- **Reproduce:** no runnable command -- the review did not supply a command here. The finding's own numbers are above; re-derive from those.

### 5. Nine primary tests reported with no multiplicity correction, on top of data-dependent covariate screening at p<0.10  [SUSPICIOUS | confidence: medium]

- **Location:** Analyses section (Covariates); Tables 2, 3 and 4
- **Reported:** "Variables were retained in the final models as covariates only if bivariate associations had p values under 0.10." Three leadership predictors were each tested against three outcomes in separate models. No correction is mentioned anywhere in the paper.
- **Computed:** 3 predictors x 3 outcomes = 9 primary hypothesis tests. Five reach p<.05, and four of those five sit in the .01-.03 band -- exactly where an uncorrected family of nine is most vulnerable. The covariate pre-screen was performed on the same data used for the reported models, so its effect on the reported p-values is unaccounted for; the screening results themselves (for service-area population, community poverty, coalition age and state) are never reported.
- **Assumptions:** None beyond the paper's own statements. This is a structural count of the paper's reported tests plus a reading of its stated analysis strategy; no multiplicity-correction tool exists in this toolset. Neither practice is unusual in this literature and neither makes any individual number wrong -- the point is that the nominal p-values understate family-wise false-positive risk and the paper offers no adjustment or acknowledgement.
- **Reproduce:** no runnable command -- the review did not supply a command here. The finding's own numbers are above; re-derive from those.

### 6. Two Table 3 rows print identical coefficients and standard errors but different p-values, and the printed precision is too coarse for a reader to verify either  [INDETERMINATE | confidence: high]

- **Location:** Table 3, Number of EBP at baseline, models 1 and 3
- **Reported:** Model 1: "Number of EBP at baseline 0.01 (0.002) .01". Model 3: "Number of EBP at baseline 0.01 (0.002) <.001". Identical printed inputs, p-values differing by more than four orders of magnitude.
- **Computed:** At the printed values t = 0.01/0.002 = 5.0, calculated_p = 5.7427e-07, which matches neither .01 nor the convention used elsewhere. But the coefficient is printed to 2 decimals and the SE to 3, so the joint rounding interval spans t = 0.015/0.0015 = 10.0 (calculated_p = 1.5633e-23) down to t = 0.005/0.0025 = 2.0 (calculated_p = 0.045503). Both reported p-values fall inside that span. The row therefore cannot adjudicate its own p-value and is unverifiable as printed.
- **Assumptions:** df=100000 as a normal stand-in for Stata's negative-binomial reference distribution. I am REINTERPRETING the sweep here: Stage 1 recorded this as suspicious with a precision caveat; re-run at the printed precision, the caveat is the finding. This is an insufficient-precision problem, not demonstrable error.
- **Reproduce:** no runnable command -- the review did not supply a command here. The finding's own numbers are above; re-derive from those.

### 7. The trial's allocation is not verifiable from what is printed, and no baseline-similarity evidence exists in either direction  [INDETERMINATE | confidence: high]

- **Location:** Methods (sample description); Table 1
- **Reported:** "Half of these coalitions were randomly assigned to participate in the Coalition Check-Up technical assistance (TA)." Table 1 reports a single "All coalitions n = 64" column. No arm-wise statistics and no baseline p-values appear anywhere.
- **Computed:** csf_test and bayesian_table1_dispersion could not be run: csf_test requires a list of baseline p-values and the dispersion test requires per-arm means, SDs and ns, and the paper supplies neither. Randomisation was by coalition (a cluster), so both methods would in any case refuse or be capped, since cluster allocation breaks the independence they assume.
- **Assumptions:** None beyond the paper's own statements. Stated explicitly per rulebook rule 1 so that the ABSENCE of a baseline-uniformity flag is not misread as reassurance: this paper contains no baseline-similarity result, favourable or unfavourable, and none should be inferred. Treatment assignment is included as a covariate in all models, but its balance cannot be checked.
- **Reproduce:** no runnable command -- the review left a placeholder in its own command. The finding's own numbers are above; re-derive from those.

### 8. The Table 1 fidelity row sits under the wrong denominator, and one construct carries three different names  [INDETERMINATE | confidence: medium]

- **Location:** Table 1 (EBP adherence row); Methods; Table 4
- **Reported:** "EBP adherence 5.23 (1.13)" under the column heading "All coalitions n = 64". Table 4 title: "(n = 101 programs in 35 coalitions)". Methods: descriptives were examined "at the coalition and program level, respectively".
- **Computed:** The typed parser refused this cell as ambiguous (candidates mean_sd / n_percent / estimate_ci): alone among the Table 1 summary rows it carries no "(mean, SD)" suffix, so its meaning is not fixed by syntax or label. Fidelity/adherence is a program-level measure, yet the row is printed under n=64 coalitions. Because the denominator is unknown, no GRIM-family check can be run on it; only the SD-range check was possible and it passes. The paper additionally names what appears to be one construct three ways: "EBP adherence" (Table 1), "EBP fidelity" (Methods, Results, Table 4 title) and "Quality of EBP at baseline" (Table 4 covariate row). Table 1 also records 38 coalitions using at least one EBP against the 35 contributing fidelity data, and the paper does not reconcile the two.
- **Assumptions:** None beyond the paper's own statements. Recorded as indeterminate rather than as an error: the underlying data may be correctly computed and only the column heading and naming may be at fault.
- **Reproduce:** no runnable command -- the review left a placeholder in its own command. The finding's own numbers are above; re-derive from those.

### 9. Table 1 records 23 coalitions receiving no technical assistance in a study whose design states that all coalitions received TA  [INDETERMINATE | confidence: medium]

- **Location:** Methods (sample description and covariate definition) vs Table 1 and Results paragraph 3
- **Reported:** Methods: "The remaining coalitions received TA as usual, that is, access to regional training, group-based training, and TA by phone." Covariate definition: "0 = Little to no TA". Table 1: "Level of technical assistance received: None 23 (35.94%)". Results: "Forty-one (64%) of the coalitions received TA."
- **Computed:** The arithmetic is internally sound: the three TA counts sum to exactly 64 (difference 0) and the three percentages to exactly 100.00, and 64 minus the 23 coded "None" is the 41 quoted in the Results. The inconsistency is in the labelling: by design every coalition, including controls, received TA as usual, so a genuinely zero-TA category should be empty. The covariate is defined as "Little to no TA", which is compatible; Table 1 shortens this to "None" and the Results sentence then asserts that a third of coalitions received none.
- **Assumptions:** None beyond the paper's own statements. Most likely a labelling shorthand rather than a data error, which is why this is indeterminate rather than a flagged inconsistency.
- **Reproduce:** `metascience summation --values 23,21,20 --expected-sum 64 --tolerance 0.5`

## What we could NOT check

- **Confidence intervals for all 63 coefficients in Tables 2-4** — None are reported anywhere in the paper, so check_estimate_ci could not be run on a single coefficient -- normally the highest-yield check on a regression paper. Deriving intervals from the coefficients and standard errors would have required hand arithmetic and was not done.
- **Baseline balance between the randomised Coalition Check-Up arm and the TA-as-usual arm** — Table 1 pools all 64 coalitions into a single column; no arm-wise means, SDs, ns or baseline p-values are reported, so neither csf_test nor bayesian_table1_dispersion had any input. Cluster allocation would additionally cap or refuse both tests.
- **Table 1, Population of service area 84,299 (108,353)** — The typed parser misread the cell as an estimate with a confidence interval because of the thousands separators. Even read correctly there is nothing to check: the paper states no bounds for service-area population, GRIM/GRIMMER do not constrain a count of this magnitude at n=64, and an SD-range check would require a range the paper never gives. Inventing one would violate rulebook rule 4.
- **Table 1, "Use at least one evidence-based program 38 (59%)" against "Number of evidence-based programs 1.67 (2.15)"** — check_proportion_from_normal was deliberately not run. Its normality precondition is stated-false by the paper, which describes the count as "highly skewed" and models it with Poisson and negative-binomial regression. Running it would have manufactured a spurious anomaly out of an ordinary skewed count.
- **Reliability coefficients: Cronbach's alpha = 0.93 (communication), alpha = 0.88 (inclusive decision making), r = 0.80 (inclusion of community residents), r = 0.76 (fidelity youth vs parent items), ICC = 0.10 (fidelity at Time 2)** — All five lie inside their admissible ranges, so nothing is impossible. No tool in this set verifies an alpha or an ICC against item-level data, and the item-level data are not reported.
- **Survey participation rates: 60% in Year 1 (1108/1851) and 56% in Year 2 (945/1695)** — Verifying that these fractions round to the stated whole percentages requires a division no available tool performs on this input form; grim_percentage would only confirm attainability at n=1851, which is uninformative at that sample size. Recording the division by hand would breach the no-hand-arithmetic rule.
- **Supporting Information S1: Tables S1 and S2 (registry hierarchy used to classify programs as EBPs)** — The supplementary file was not provided. The EBP classification rule -- and the noted "discrepancies across registries, albeit few" -- underpins the paper's primary outcome and is not verifiable from what was supplied.
- **Sensitivity analyses omitting coalitions with no EBPs** — The paper states these "yielded very similar associations to those reported here" but reports no coefficients, standard errors or p-values from them. There is nothing numeric to check.
- **Bivariate screening of service-area population, community poverty, coalition age and state as candidate covariates** — These are named as having been screened at p<0.10 but only the final retained set is reported. The screening tests that led to their exclusion cannot be checked, which also means the multiplicity implied by that screening cannot be quantified.
- **Figures** — The paper contains no data figures; the markdown extraction shows only decorative image placeholders and extract_pdf surfaced no figure captions carrying statistics. No figure-derived values were used anywhere in this review.

## Limitations

- This agent reads text and tables only and does not see figures. No figure was interpreted, and no value was read off a chart. (In this paper that costs nothing: it contains no data figures.)
- check_regression's p_matches flag is generous at small p and returned severity=consistent for the two "<.001" cells reported in finding 2. Those findings rest on the tool's calculated_p output compared against the threshold the paper printed, not on the tool's own match verdict. A reader should check the calculated_p values quoted rather than the tool's severity label.
- No `metascience` CLI verb was available for check_regression in this toolset, so findings 2, 4 and 6 carry exact MCP tool inputs in place of a runnable command rather than an invented one.
- df=100000 was used throughout as a numerically exact stand-in for the normal reference distribution Stata applies to Poisson and negative-binomial models. The two threshold findings were re-tested at df=57 and the conclusion is unchanged; no other cell was tested for reference-distribution sensitivity.
- absence_of_evidence was run once on a confidence interval I derived myself, solely to confirm tool behaviour. Those bounds are NOT the paper's and are deliberately excluded from finding 3, which rests only on the paper's own reporting choices.
- No tool in this set evaluates multiplicity correction or level-2 power in a two-level model, so findings 5 and the power element of finding 3 are structural readings of the paper rather than tool outputs.
- The required_n figures (85 observations for r=.30, 37 for r=.45, both at 80% power, two-tailed) are approximate context for the coalition-level sample size only. They do not correspond to the paper's actual Poisson, negative-binomial or hierarchical models and must not be read as a power calculation for them.
- The direction of the headline scale contradiction cannot be resolved from the paper: it is not determinable whether the response options are misdescribed or the "5" is a typo for "4".
- No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.

## Coverage

- **Statistics found:** 94; **checked:** 84
- **Tools run:** extract_pdf, statcheck, parse_table, parse_cells_typed, check_table, grim_sweep, grim_check, grimmer_check, sprite_reconstruct, grim_percentage, check_sd_or_se, check_summation, check_sd_range, check_regression, detect_duplication, flag_round_n, stalt_check, required_n, absence_of_evidence
- **Tables checked:** Table 1 (coalition characteristics, n=64), Table 2 (number of EBPs, Poisson, n=64), Table 3 (EBP reach, negative binomial, n=64), Table 4 (EBP fidelity, HLM, 101 programs in 35 coalitions)
- **Checkable table cells:** 78 of 143 surveyed; **checked:** 15
    - 70 could not be checked without knowing what kind of quantity the row reports
    - 8 were missing an input: n (8)

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

### `check_regression` — probabilistic

Checks a regression coefficient's t = B/SE and its p within printed rounding.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- Assumes the reported t is B/SE and the reported p its t-distribution tail at the given df.
- t is judged against the interval reachable from the PRINTED precision of B and SE, never a point.
- Both sign conventions (signed t and |t|) and both tail conventions are accepted before anything is flagged.
- Without df only the p check is skipped; the t = B/SE comparison still runs and can flag on its own.

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

### `required_n` — descriptive

Computes the sample size a design needs for a target power; a pure calculator.

**What its verdict means.** Descriptive. Extracts, parses or computes a quantity; it does not itself render a verdict about the paper.

**Strongest verdict it may reach:** `indeterminate`

**It assumes:**
- Uses the standard model for the named test; it renders no verdict about any paper.

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

This is a two-wave lagged observational analysis nested inside a cluster-randomised technical-assistance trial. Sixty-four youth substance-misuse prevention coalitions in Pennsylvania and Missouri were surveyed at baseline and again a year later. Three coalition-level measures of inclusive leadership -- engaging communication, inclusive decision making, and inclusion of community residents -- are each regressed on three later outcomes: number of EBPs (Poisson), EBP reach (negative binomial), and program fidelity (hierarchical linear model over 101 programs in 35 coalitions), adjusting for the baseline outcome and five covariates. The authors report that communication and inclusive decision making predict more EBPs and greater reach, that inclusion of residents is marginal, and that nothing predicts fidelity.

## The arithmetic is, on the whole, sound

It is worth saying plainly what checked out, because the denominator matters. Sixty-three coefficient/p pairs across the three regression tables were recomputed from their own coefficients and standard errors; 59 reproduce within the rounding envelope of the printed inputs. All nine of the paper's primary hypothesis tests are among those that reproduce. Table 1 is internally airtight: its seven two-decimal percentages jointly admit n = 64, and every count GRIM recovers at that n (55, 9, 26, 41, 23, 21, 20) matches the count printed alongside it exactly; both category sets sum to 64 and to 100.00 with no drift. The count outcomes pass GRIM, GRIMMER and SPRITE against bounds the paper itself states. Cross-table duplication detection found zero identical coefficient/SE pairs across 833 comparisons, and the sample sizes (68, 64, 101, 35, 1851, 1695) show natural non-round variation.

There is no data-integrity signal in this paper. The problems are reporting and inference problems -- and they concentrate in exactly the places where the paper asks the reader to take its word.

## Why the reporting problems bite harder here than usual

The paper states: "Results in Tables 2-4 are shown as coefficients, and do not include effect sizes, as effects are multiplicative and unit increases in key independent variables are idiosyncratic and scale-dependent." No confidence interval appears anywhere. So the entire evidentiary content of this paper is a coefficient, a standard error, and a significance label. The significance labels are the part that demonstrably contains errors; the columns holding the estimates are mislabelled "M (SD)" in all three tables; and the scale that would make the strongest coefficient interpretable is stated two incompatible ways. The authors correctly identify that interpretation is scale-dependent, then misstate the scale of their own headline predictor.

## Findings I discarded or downgraded from the numeric sweep

STALT flagged the baseline-EBP coefficient (0.31, SE 0.04) at p = 9.3e-15 behind "<.001" -- eleven orders of magnitude below the threshold -- and returned `highly_suspicious`. I am not reporting it. That coefficient is the lagged autoregressive adjustment term, where a very large t is what a stable count measured twice twelve months apart should produce; rule 2's concern is a surprisingly strong *substantive* effect concealed behind a threshold, and measure stability is not that.

The sweep's whole-table run produced three non-consistent verdicts for "Number of coalition members 35.78 (33.74)". Those were artefacts of a default 1-7 Likert bound applied to a headcount; correctly bounded, the row passes. Discarded.

Three p-values are rounded *up* to the next tier (8.57/3.03 gives .0047, printed .01; -32.89/12.17 gives .0069, printed .01). That errs against the authors' interest and is not a finding -- but it sharpens the two "<.001" cells, because against a convention of rounding up, a p of .0026 should never be labelled "<.001".

The one flag I materially reinterpreted is the pair of Table 3 baseline rows: re-run at the printed precision, the coefficient's two-decimal interval against the standard error's three-decimal interval spans t = 2.0 to t = 10.0, so both printed p-values are attainable. That is an unverifiability problem, not an error, and is reported as such.

## Design and feasibility

The clustering is handled correctly: programs nested within coalitions with a coalition random intercept, explicitly justified by a reported ICC of 0.10. But every predictor in Table 4 is measured at the coalition level, so those coefficients are informed by 35 coalitions, not 101 programs -- which is why they carry the largest standard errors in the paper, and why the null fidelity claim is the least-supported result while being stated in the Highlights as confidently as the positive ones.

Nothing else raises feasibility concerns. The work is NIH-funded (R01DA045815), IRB approval is stated, four of 68 coalitions were lost between waves, and participation rates of 60% and 56% are unremarkable rather than implausibly clean. The data statement is a plain on-request statement, not the state-but-withhold pattern.

## Verdict

The primary findings reproduce from the numbers given, but this paper cannot be checked where it matters most: I would want confidence intervals, a corrected scale description for engaging communication, and a corrected p-value column before relying on any magnitude reported here.

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
