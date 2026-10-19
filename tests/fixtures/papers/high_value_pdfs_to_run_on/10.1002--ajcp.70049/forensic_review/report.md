# Forensic review -- Wells et al. 2026

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## Associations between inclusive community coalition leadership and use of evidence-based practices
*Wells, R., Ranjit, N., Brown, L. D., Chilenski, S. M., & Gaddy, Y. M. American Journal of Community Psychology, 77, 590-601. 2026. doi:10.1002/ajcp.70049*

**Design:** Lagged observational analysis (1-year lag) of 64 youth substance misuse prevention coalitions in Pennsylvania and Missouri, nested within a randomized technical-assistance trial; Poisson, negative binomial and hierarchical linear regressions. Funded by NIDA R01DA045815.

<sub>Analysed as `10.1002--ajcp.70049`</sub>

> **SUSPICIOUS** — The paper states two mutually exclusive response scales for its lead predictor -- Measures defines engaging communication on a four-point scale topping out at 4 = 'Outstanding', while Results reports its mean 'on a 1.25-5 scale' -- so the magnitude of the paper's central effect cannot be interpreted.
>
> **Evidence:** Measures: "response options 1 = Needs a lot of work, 2 = Needs a little work, 3 = Good, 4 = Outstanding; Cronbach's alpha = 0.93". Results: "the mean level of engaging communication was 3.83 on a 1.25-5 scale, corresponding to 'good' for such facets as frequency." Table 1: "Communication (mean, SD) | 3.83 (0.42)". Under the Measures reading no coalition can exceed 4, so the proportion above 4 is necessarily 0/64; under a normal model with mean 3.83 and SD 0.42 the expected proportion above 4 is 0.3428 (binomial p = 3.03e-12). The narrative gloss compounds it: on the stated 1-4 scale, 3.83 sits nearer 'Outstanding' than 'Good'.
> **Rests on:** a constraint the paper itself states
> **Reproduce:** `metascience prop-from-normal --reported-proportion 0 --mean 3.83 --sd 0.42 --n 64 --threshold 4 --direction above`

**Verdict: questionable** (confidence: medium)

> **Partial table coverage:** 11 of 78 checkable cells were checked cell by cell. This counts only cells reached through `check_table`; a further 47 per-cell checks ran on values off this paper (`check_proportion_from_normal`, `check_regression`, `check_sd_range`, `check_summation`, `detect_duplication`, `flag_round_n`, `grim_check`, `grim_sweep`, `grimmer_check`, `stalt_check`) and report no cell ids, so the remainder is under-counted by an unknown amount.

## Provenance of the analysis

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

1 study/studies, 14 variables, 63 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| s1 | Coalition Check-Up lagged cohort: 64 PA/MO youth substance misuse prevention coalitions, Wave 1 (2020-2021) to Wave 2 (2021-2022) | cohort | 64 | Coalition for Tables 1-3 (n=64); program nested within coalition for Table 4 (101 programs in 35 coalitions, coalition as random intercept) | yes |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Number of evidence-based programs implemented (Wave 2 outcome; Wave 1 covariate) | ratio | discrete | 0-9 (integers) | programs | measured | GRIM (needs stated max) | high |
| EBP reach (total unduplicated annual youth and parents served) | ratio | discrete | 0-5370 (integers) | persons | measured | GRIM (needs stated max) | high |
| EBP fidelity / adherence (mean of 2 items, youth and parent versions) | ordinal | continuous | 1-7 | - | measured | none -- composite granularity is 1/(items x n) | high |
| Engaging communication (coalition-level mean of member responses to 4 items). NOTE: scale bounds are internally contested - Measures states 1-4, Results states a 1.25-5 scale. | interval | continuous | 1-4 | - | measured | none -- composite granularity is 1/(items x n) | medium |
| Inclusive decision making (coalition-level mean of member responses to 3 items) | interval | continuous | 1-5 | - | measured | none -- composite granularity is 1/(items x n) | high |
| Inclusion of community residents (coalition-level mean of member responses to 2 items) | interval | continuous | 1-5 | - | measured | none -- composite granularity is 1/(items x n) | high |
| Use at least one evidence-based program | nominal | discrete | 0-1 (integers) | - | measured | DEBIT; percentage GRIM | high |
| Follows the Communities That Care model | nominal | discrete | 0-1 (integers) | - | measured | DEBIT; percentage GRIM | high |
| Received any external funding at baseline | nominal | discrete | 0-1 (integers) | - | measured | DEBIT; percentage GRIM | high |
| Level of technical assistance received | ordinal | discrete | 0-3 (integers) | - | measured | percentage GRIM on cell counts | high |
| Number of active coalition members (entered in 10s in models) | ratio | discrete | range not stated | members | measured | GRIM (needs stated max) | high |
| State (Pennsylvania vs Missouri) | nominal | discrete | 0-1 (integers) | - | measured | DEBIT; percentage GRIM | high |
| Population of coalition service area | ratio | discrete | range not stated | persons | measured | GRIM (needs stated max) | medium |
| Assigned to full Coalition Check-Up TA (randomized binary). Stated as included in every model but never reported in any table. | nominal | discrete | 0-1 (integers) | - | measured | DEBIT; percentage GRIM | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Table 2, Communication row, column 1 (Poisson regression) | other | Number of evidence-based programs implemented (Wave 2 outcome; Wave 1 covariate) (count) | Engaging communication (coalition-level mean of member responses to 4 items). NOTE: scale bounds are internally contested - Measures states 1-4, Results states a 1.25-5 scale., Number of evidence-based programs implemented (Wave 2 outcome; Wave 1 covariate), Follows the Communities That Care model, Received any external funding at baseline, Level of technical assistance received, Number of active coalition members (entered in 10s in models), Assigned to full Coalition Check-Up TA (randomized binary). Stated as included in every model but never reported in any table. | 64 | none | none reported |
| Table 2, Inclusive decision making row, column 2 (Poisson regression) | other | Number of evidence-based programs implemented (Wave 2 outcome; Wave 1 covariate) (count) | Inclusive decision making (coalition-level mean of member responses to 3 items), Number of evidence-based programs implemented (Wave 2 outcome; Wave 1 covariate), Follows the Communities That Care model, Received any external funding at baseline, Level of technical assistance received, Number of active coalition members (entered in 10s in models), Assigned to full Coalition Check-Up TA (randomized binary). Stated as included in every model but never reported in any table. | 64 | none | none reported |
| Table 2, Inclusion of community residents row, column 3 (Poisson regression) | other | Number of evidence-based programs implemented (Wave 2 outcome; Wave 1 covariate) (count) | Inclusion of community residents (coalition-level mean of member responses to 2 items), Number of evidence-based programs implemented (Wave 2 outcome; Wave 1 covariate), Follows the Communities That Care model, Received any external funding at baseline, Level of technical assistance received, Number of active coalition members (entered in 10s in models), Assigned to full Coalition Check-Up TA (randomized binary). Stated as included in every model but never reported in any table. | 64 | none | none reported |
| Table 3, Communication row, column 1 (negative binomial regression) | other | EBP reach (total unduplicated annual youth and parents served) (count) | Engaging communication (coalition-level mean of member responses to 4 items). NOTE: scale bounds are internally contested - Measures states 1-4, Results states a 1.25-5 scale., Number of evidence-based programs implemented (Wave 2 outcome; Wave 1 covariate), Follows the Communities That Care model, Received any external funding at baseline, Level of technical assistance received, Number of active coalition members (entered in 10s in models), Assigned to full Coalition Check-Up TA (randomized binary). Stated as included in every model but never reported in any table. | 64 | none | none reported |
| Table 3, Inclusive decision making row, column 2 (negative binomial regression) | other | EBP reach (total unduplicated annual youth and parents served) (count) | Inclusive decision making (coalition-level mean of member responses to 3 items), Number of evidence-based programs implemented (Wave 2 outcome; Wave 1 covariate), Follows the Communities That Care model, Received any external funding at baseline, Level of technical assistance received, Number of active coalition members (entered in 10s in models), Assigned to full Coalition Check-Up TA (randomized binary). Stated as included in every model but never reported in any table. | 64 | none | none reported |
| Table 3, Inclusion of community residents row, column 3 (negative binomial regression) | other | EBP reach (total unduplicated annual youth and parents served) (count) | Inclusion of community residents (coalition-level mean of member responses to 2 items), Number of evidence-based programs implemented (Wave 2 outcome; Wave 1 covariate), Follows the Communities That Care model, Received any external funding at baseline, Level of technical assistance received, Number of active coalition members (entered in 10s in models), Assigned to full Coalition Check-Up TA (randomized binary). Stated as included in every model but never reported in any table. | 64 | none | none reported |
| Table 4, Communication row, column 1 (hierarchical linear model, programs nested in coalitions) | mixed_model | EBP fidelity / adherence (mean of 2 items, youth and parent versions) (likert_composite) | Engaging communication (coalition-level mean of member responses to 4 items). NOTE: scale bounds are internally contested - Measures states 1-4, Results states a 1.25-5 scale., EBP fidelity / adherence (mean of 2 items, youth and parent versions), Follows the Communities That Care model, Received any external funding at baseline, Level of technical assistance received, Number of active coalition members (entered in 10s in models), Assigned to full Coalition Check-Up TA (randomized binary). Stated as included in every model but never reported in any table. | 101 | none | unconditional intraclass correlation coefficient of 0.10 for fidelity at Time 2 reported as justification for the multilevel model |
| Table 4, Inclusive decision making row, column 2 | mixed_model | EBP fidelity / adherence (mean of 2 items, youth and parent versions) (likert_composite) | Inclusive decision making (coalition-level mean of member responses to 3 items), EBP fidelity / adherence (mean of 2 items, youth and parent versions), Follows the Communities That Care model, Received any external funding at baseline, Level of technical assistance received, Number of active coalition members (entered in 10s in models), Assigned to full Coalition Check-Up TA (randomized binary). Stated as included in every model but never reported in any table. | 101 | none | none reported |
| Table 4, Inclusion of community residents row, column 3 | mixed_model | EBP fidelity / adherence (mean of 2 items, youth and parent versions) (likert_composite) | Inclusion of community residents (coalition-level mean of member responses to 2 items), EBP fidelity / adherence (mean of 2 items, youth and parent versions), Follows the Communities That Care model, Received any external funding at baseline, Level of technical assistance received, Number of active coalition members (entered in 10s in models), Assigned to full Coalition Check-Up TA (randomized binary). Stated as included in every model but never reported in any table. | 101 | none | none reported |
| Table 2 col 1, Number of EBP at baseline | other | ? | - | 64 | ? | none reported |
| Table 2 col 2, Number of EBP at baseline | other | ? | - | 64 | ? | none reported |
| Table 2 col 3, Number of EBP at baseline | other | ? | - | 64 | ? | none reported |
| Table 2 col 1, Communities That Care | other | ? | - | 64 | ? | none reported |
| Table 2 col 2, Communities That Care | other | ? | - | 64 | ? | none reported |
| Table 2 col 3, Communities That Care | other | ? | - | 64 | ? | none reported |
| Table 2 col 1, Externally funded | other | ? | - | 64 | ? | none reported |
| Table 2 col 2, Externally funded | other | ? | - | 64 | ? | none reported |
| Table 2 col 3, Externally funded | other | ? | - | 64 | ? | none reported |
| Table 2 col 1, Level of technical assistance | other | ? | - | 64 | ? | none reported |
| Table 2 col 2, Level of technical assistance | other | ? | - | 64 | ? | none reported |
| Table 2 col 3, Level of technical assistance | other | ? | - | 64 | ? | none reported |
| Table 2 col 1, Number of members (in 10's) | other | ? | - | 64 | ? | none reported |
| Table 2 col 2, Number of members (in 10's) | other | ? | - | 64 | ? | none reported |
| Table 2 col 3, Number of members (in 10's) | other | ? | - | 64 | ? | none reported |
| Table 2 col 1, Constant | other | ? | - | 64 | ? | none reported |
| Table 2 col 2, Constant | other | ? | - | 64 | ? | none reported |
| Table 2 col 3, Constant | other | ? | - | 64 | ? | none reported |
| Table 3 col 1, Number of EBP at baseline | other | ? | - | 64 | ? | none reported |
| Table 3 col 2, Number of EBP at baseline (p printed literally as '0') | other | ? | - | 64 | ? | none reported |
| Table 3 col 3, Number of EBP at baseline | other | ? | - | 64 | ? | none reported |
| Table 3 col 1, Communities That Care | other | ? | - | 64 | ? | none reported |
| Table 3 col 2, Communities That Care | other | ? | - | 64 | ? | none reported |
| Table 3 col 3, Communities That Care | other | ? | - | 64 | ? | none reported |
| Table 3 col 1, Externally funded | other | ? | - | 64 | ? | none reported |
| Table 3 col 2, Externally funded | other | ? | - | 64 | ? | none reported |
| Table 3 col 3, Externally funded | other | ? | - | 64 | ? | none reported |
| Table 3 col 1, Level of technical assistance | other | ? | - | 64 | ? | none reported |
| Table 3 col 2, Level of technical assistance | other | ? | - | 64 | ? | none reported |
| Table 3 col 3, Level of technical assistance | other | ? | - | 64 | ? | none reported |
| Table 3 col 1, Number of members (in 10's) | other | ? | - | 64 | ? | none reported |
| Table 3 col 2, Number of members (in 10's) | other | ? | - | 64 | ? | none reported |
| Table 3 col 3, Number of members (in 10's) | other | ? | - | 64 | ? | none reported |
| Table 3 col 1, Constant | other | ? | - | 64 | ? | none reported |
| Table 3 col 2, Constant | other | ? | - | 64 | ? | none reported |
| Table 3 col 3, Constant | other | ? | - | 64 | ? | none reported |
| Table 4 col 1, Quality of EBP at baseline | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 2, Quality of EBP at baseline | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 3, Quality of EBP at baseline | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 1, Communities That Care | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 2, Communities That Care | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 3, Communities That Care | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 1, Externally funded | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 2, Externally funded | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 3, Externally funded | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 1, Level of technical assistance | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 2, Level of technical assistance | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 3, Level of technical assistance | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 1, Number of members (in 10's) | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 2, Number of members (in 10's) | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 3, Number of members (in 10's) | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 1, Constant | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 2, Constant | mixed_model | ? | - | 101 | ? | none reported |
| Table 4 col 3, Constant | mixed_model | ? | - | 101 | ? | none reported |

_62 of 63 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. Contradictory stated scale bounds for the headline predictor (engaging communication)  [SUSPICIOUS | confidence: high]

- **Location:** Measures, 'Engaging communication' paragraph vs Results paragraph 1; Table 1 Communication row
- **Reported:** Measures: four response options, 1 = 'Needs a lot of work' through 4 = 'Outstanding'. Results: "the mean level of engaging communication was 3.83 on a 1.25-5 scale, corresponding to 'good'". Table 1: 3.83 (0.42), n = 64.
- **Computed:** The two statements cannot both be true. Corroboration: under a normal model with mean 3.83 / SD 0.42, the expected proportion above 4 is 0.3428, whereas the 1-4 reading forces 0/64 (binomial p = 3.03e-12, 95% CI [0, 0.056]). check_sd_range shows SD 0.42 is admissible under both readings (27.8% of the maximum possible SD of 1.512 for a 1-4 range), so dispersion cannot adjudicate which scale is correct.
- **Assumptions:** The binomial corroboration assumes normality of the coalition-level aggregate; a ceiling-bounded variable would be left-skewed, which weakens that specific arithmetic (this is why I hold the finding at 'suspicious' rather than adopting the tool's own 'highly_suspicious'). The contradiction itself assumes nothing beyond the paper's own two statements. No invented range is used: both bounds are quoted from the paper.
- **Reproduce:** `metascience prop-from-normal --reported-proportion 0 --mean 3.83 --sd 0.42 --n 64 --threshold 4 --direction above`

### 2. Table 3 baseline row: one printed estimate carries three different p-values, one of which is printed as '0'  [SUSPICIOUS | confidence: high]

- **Location:** Table 3, 'Number of EBP at baseline' row, all three columns
- **Reported:** "Number of EBP at baseline | 0.01 (0.002) | .01 | 0.01 (0.001) | 0 | 0.01 (0.002) | <.001"
- **Computed:** Columns 1 and 3 print an identical coefficient and identical SE, yet report p = .01 and p < .001. Reconstructing z = B/SE = 0.01/0.002 = 5.00 and passing it to statcheck: the '<.001' cell is not flagged (computed p = 1e-06) while the '.01' cell is flagged as an error, correct_at_printed_precision = false -- identical inputs cannot legitimately give both. Column 2's p-value is printed as the literal character '0', which is not a possible p-value; this was confirmed identically in the markdown extraction and in the PDF, so it is not a transcription artefact.
- **As printed in the paper:** “Number of EBP at baseline | 0.01 (0.002) | .01 | 0.01 (0.001) | 0 | 0.01 (0.002) | <.001” _(found in a table)_
- **Assumptions:** Assumes the parenthesised values are standard errors and that Stata reports Wald z for poisson/nbreg (both supported: 8 of the 9 headline tests reproduce their printed p exactly under this reading). Important counterweight, and the reason this is not ranked 'impossible': the coefficient is printed to ONE significant figure, so its rounding interval against the SE interval admits z anywhere from roughly 2 to 10, and p = .01 is reachable inside that band. The underlying problem is therefore uninformative printed precision plus a formatting slip, not a demonstrated arithmetic violation.
- **Reproduce:** no runnable command -- the review left a placeholder in its own command. The finding's own numbers are above; re-derive from those.

### 3. The study's randomized element is stated as a model term in every model but appears in no table and is never reported  [SUSPICIOUS | confidence: high]

- **Location:** Methods, Covariates paragraph vs Tables 2, 3 and 4; Table 1
- **Reported:** Methods: "Additionally, all models included a binary variable indicating whether the coalition was assigned to receive the full Coalition Check Up TA..." and "The final retained set of covariates, apart from Coalition Check Up treatment assignment status, were the following:". Sample: "Half of these coalitions were randomly assigned to participate in the Coalition Check-Up technical assistance (TA)."
- **Computed:** No treatment-assignment row appears in Table 2, 3 or 4; the tables carry only the key predictor, Number/Quality of EBP at baseline, Communities That Care, Externally funded, Level of technical assistance, Number of members, and the Constant. Table 1 has a single 'All coalitions' column with no by-arm split and no baseline p-values, so csf_test and bayesian_table1_dispersion had nothing to consume and were correctly not run. A stated model term is therefore unverifiable, and the randomized comparison embedded in the study is invisible.
- **Assumptions:** None beyond the paper's own statements. Note the paper also says the ordinal TA-level covariate "varied between coalitions assigned to the Coalition Check-Up process and those that were not", so that covariate is partly collinear with the unreported assignment indicator -- a further reason its omission matters.
- **Reproduce:** `metascience extract --pdf-path /mnt/c/Users/gregs/agent_for_forensic_metascience/high_value_pdfs_to_run_on/10.1002--ajcp.70049/10.1002--ajcp.70049.pdf --first-page 7 --last-page 7`

### 4. All three results tables label regression coefficients and standard errors as 'M (SD)'  [SUSPICIOUS | confidence: high]

- **Location:** Tables 2, 3 and 4, column headers
- **Reported:** "| Variable | M (SD) | p | M (SD) | p | M (SD) | p |" under a spanning header reading 'Coefficient'. Results text: "Results in Tables 2-4 are shown as coefficients, and do not include effect sizes".
- **Computed:** The cells are coefficients and their standard errors, not means and SDs. This is confirmed empirically rather than assumed: 8 of the 9 headline predictor tests, and 9 of 14 reconstructed tests overall, reproduce their printed p-value exactly under the B/SE reading (e.g. z = 1.81 gives p = .0703 against a printed .07; z = 0.14 gives p = .8887 against a printed .89). Verified as printed in both the markdown and the independent PDF extraction.
- **Assumptions:** None beyond the paper's own statements. A labelling error rather than a numerical one, but a reader taking the header at face value would misread every effect estimate in the paper.
- **Reproduce:** `metascience statcheck --text "Inclusion of community residents number of EBPs: z = 1.81, p = .07. Inclusion of community residents fidelity: z = 0.14, p = .89. Communication fidelity: z = 0.88, p = .38."`

### 5. Five of 14 reconstructed p-values disagree with their own coefficient and standard error, including one headline result  [SUSPICIOUS | confidence: high]

- **Location:** Table 2 (Constant col 1; Level of technical assistance cols 1-2), Table 3 (Inclusive decision making col 2; Number of EBP at baseline col 1)
- **Reported:** "Constant | -4.51 (1.50) | <.001"; "Inclusive decision making | 8.57 (3.03) | .01"; "Level of technical assistance | -0.01 (0.17) | .97 | -0.01 (0.17) | .98"
- **Computed:** statcheck on z reconstructed as B/SE: z = 3.01 gives p = .0026 against a reported '<.001' (about 2.6x the claimed threshold, and still .0025 at the most favourable rounding z = 3.02); z = 2.83 gives p = .0047 against a reported '.01'; z = 0.06 gives p = .9522 against reported '.97' and '.98' -- two adjacent columns print an identical coefficient and SE but two different p-values. Of 14 statistics, 5 errors, 0 explained by rounding, and critically ZERO decision errors: no p-value falls on the wrong side of .05 and not one significance call flips.
- **Assumptions:** Assumes parenthesised values are SEs (see rank 4) and that the tables report Wald z. The Table 3 inclusive-decision-making error runs in the CONSERVATIVE direction (true p smaller than reported), so the substantive claim is unaffected. The identical-coefficient pairs have an entirely benign explanation: unrounded values differing slightly and both rounding to two decimals. STALT was run on the two 'p<.001' claims and returned 'consistent', but that is a direction artefact -- STALT detects p-values suspiciously SMALLER than a threshold, and here the recomputed values are LARGER (orders_of_magnitude_smaller = -0.42). statcheck is the authority for these cells.
- **Reproduce:** no runnable command -- the review left a placeholder in its own command. The finding's own numbers are above; re-derive from those.

### 6. Nine primary tests with no multiplicity correction, plus a data-driven covariate screen at p < 0.10  [SUSPICIOUS | confidence: medium]

- **Location:** Analyses / Covariates sections; Tables 2-4 key predictor rows
- **Reported:** Three leadership measures x three EBP outcomes = nine primary tests, reported p = .01, .03, .07, .03, .01, .03, .38, .96, .89. Covariates: "Variables were retained in the final models as covariates only if bivariate associations had p values under 0.10." No correction is stated anywhere.
- **Computed:** All nine primary p-values were verified against their own coefficients and SEs via statcheck (8 of 9 correct at printed precision; the ninth errs conservatively). The five nominally significant results lie between p = .01 and p = .03. Separately, required_n indicates that detecting a moderate association (r = 0.30) at 80% power with alpha = .05 two-tailed would need 85 units against the 64 coalitions analysed.
- **Assumptions:** No validated multiplicity tool exists in this toolset, so no corrected threshold is asserted as a tool output. The required_n comparison is INDICATIVE ONLY and not an exact power calculation for these models, which are Poisson/negative-binomial with six covariates rather than a simple correlation; the paper states no a-priori power analysis, so there is nothing to reproduce. Uncorrected multiplicity is entirely ordinary in this literature -- this is flagged as a design/reporting observation, not an error.
- **Reproduce:** `metascience required-n --test-type correlation --effect-size 0.3 --alpha 0.05 --power 0.8 --tails 2`

### 7. The fidelity null is asserted without any interval, and the Highlights convert it into a claim that the effect exists  [INDETERMINATE | confidence: medium]  ⚠ not backed by a sweep finding

- **Location:** Table 4; Results final paragraph; Highlights
- **Reported:** Results: "none of the inclusive leadership practices that we examined was associated with subsequent EBP fidelity (Table 4)." Table 4: Communication 0.53 (0.60) p = .38; Inclusive decision making -0.05 (0.98) p = .96; Inclusion of community residents -0.10 (0.72) p = .89; n = 101 programs in 35 coalitions. Highlights: "It is not yet clear how inclusive leadership improves evidence-based practice fidelity."
- **Computed:** The three reported p-values reproduce correctly from their own coefficients and SEs (z = 0.88 -> p = .379; z = 0.05 -> p = .960; z = 0.14 -> p = .889), so the null is arithmetically sound. What could NOT be computed is the range of effects the data still permit: absence_of_evidence requires ci_low/ci_high and the paper reports no confidence interval anywhere, for any estimate. On a 1-7 fidelity outcome, standard errors of 0.60, 0.98 and 0.72 around estimates near zero are large relative to the scale, so 'no association' is an unquantified statement. No smallest effect size of interest is stated either, so equivalence could not have been claimed even if intervals were given.
- **Assumptions:** Deriving a CI from B and SE would be interval arithmetic performed by hand, which is barred, so no bound is asserted here -- this finding records a reporting gap, not a computed contradiction, and is marked unverified for that reason. The Highlights wording ('how inclusive leadership improves... fidelity') presupposes an effect the paper's own data did not support; a second Highlight ('Including local residents in decision making may also improve the use of evidence-based practices') rests partly on an association the Results themselves call "only marginally significant, at p = .07".
- **Reproduce:** `metascience statcheck --text "Communication fidelity: z = 0.88, p = .38. Inclusive decision making fidelity: z = 0.05, p = .96. Inclusion of community residents fidelity: z = 0.14, p = .89."`

### 8. Table 1's EBP adherence cell has no resolvable denominator, and the construct is named three different ways  [INDETERMINATE | confidence: high]

- **Location:** Table 1, 'EBP adherence' row; Measures 'EBP fidelity'; Table 4 'Quality of EBP at baseline'
- **Reported:** "EBP adherence | 5.23 (1.13)", printed under a column headed "n = 64". Table 1 also reports "Use at least one evidence-based program (n, %) | 38 (59%)". Table 4 is titled "n = 101 programs in 35 coalitions".
- **Computed:** parse_cells_typed returned kind = 'ambiguous' for this cell (candidates: mean_sd, n_percent, estimate_ci) because -- alone among Table 1's continuous rows -- the label omits the '(mean, SD)' annotation that disambiguates every other one. No forensic tool was run on it, by design. Independently, the denominator cannot be 64: adherence exists only where an EBP was delivered, and the paper reports 38 coalitions using any EBP and 35 coalitions in the fidelity model. No GRIM-family check could be given a trustworthy n.
- **As printed in the paper:** “EBP adherence | 5.23 (1.13)” _(found in a table)_
- **Assumptions:** None beyond the paper's own statements. Running a check on a value of unknown meaning and unknown denominator is the cheapest route to a false accusation, so it is refused rather than forced. The three-way naming ('EBP adherence', 'EBP fidelity', 'Quality of EBP at baseline') is a documentary observation.
- **Reproduce:** no runnable command -- the review left a placeholder in its own command. The finding's own numbers are above; re-derive from those.

## What we could NOT check

- **Table 4, all three null results (Communication B = 0.53 SE = 0.60; IDM B = -0.05 SE = 0.98; ICR B = -0.10 SE = 0.72)** — The paper's headline null claim could not be evaluated with absence_of_evidence because the paper reports NO confidence intervals anywhere, and that tool requires ci_low/ci_high. Deriving a CI from B and SE would be interval arithmetic performed by hand, which is barred. No SESOI is stated either, so equivalence could not have been claimed even with intervals.
- **Effect sizes for all nine primary tests** — check_effect_plausibility could not be run: the paper explicitly declines to report standardized effect sizes ("effects are multiplicative and unit increases in key independent variables are idiosyncratic and scale-dependent"). Poisson/negative-binomial log coefficients on idiosyncratic Likert units cannot be benchmarked against the tool's empirical field distributions without a units mismatch.
- **Baseline balance across the randomized Coalition Check-Up TA arms** — csf_test and bayesian_table1_dispersion were not run because the paper reports no by-arm baseline table and no baseline p-values; Table 1 has a single 'All coalitions' column. Running either would have required inventing arm-level data. The absence is itself reported as finding rank 3.
- **Table 1, Population of service area 84,299 (108,353)** — parse_table warned of an ambiguous thousands/decimal separator and parse_cells_typed mis-typed the cell as estimate_ci. It is an unbounded continuous population count with no stated range, so GRIM, GRIMMER and SPRITE are inapplicable and check_sd_range has no defensible bound. SD exceeding the mean is unremarkable for a right-skewed population variable.
- **Table 1, EBP adherence 5.23 (1.13)** — Typed as 'ambiguous' by parse_cells_typed and additionally lacking a resolvable denominator; no forensic tool was run on it. Reported in full as finding rank 8.
- **Reliability coefficients: Cronbach's alpha 0.93 and 0.88; item correlations 0.76 and 0.80; unconditional ICC 0.10** — No validated tool in this toolset verifies internal-consistency or reliability coefficients from summary statistics alone; doing so would require the item covariance matrix, which is not reported. All five values are in ordinary ranges and none is out of bounds on its face.
- **Survey response rates: 60% (1108/1851) in Year 1 and 56% (945/1695) in Year 2** — Both percentages are printed to zero decimals against denominators near 1700-1850, where GRIM has effectively no discriminating power, so grim_percentage would return a vacuous 'consistent'. Verifying the numerator-to-percentage division is plain arithmetic with no tool that performs it, so it was not asserted either way.
- **Supporting Information S1, Tables S1 and S2 (registry hierarchy used to classify programs as EBPs)** — Referenced by the paper but not supplied with the PDF or markdown body, so the EBP coding rules that determine the primary outcome could not be inspected.
- **Sensitivity analyses omitting coalitions without EBPs** — The paper states "Sensitivity analyses omitting these coalitions yielded very similar associations to those reported here" but reports no coefficients, standard errors or p-values from them, so there is nothing to check.
- **STALT direction check on the two 'p<.001' claims (Table 2 Constant col 1; Table 3 CTC col 1)** — stalt_check returned 'consistent' for both, but that verdict is a DIRECTION ARTEFACT and must not be read as endorsing the threshold claims: STALT detects p-values suspiciously SMALLER than a threshold, whereas here the recomputed p-values are LARGER (orders_of_magnitude_smaller = -0.42 and -0.11). statcheck is the authority for those cells.
- **Table 1, EBP reach 223.5 (410.75)** — SPRITE returned 'search_exhausted' over the 0-5370 integer range, not 'no_solution_proven'. Only the latter is evidence; a failed stochastic search over a range this wide tells us about the search, not the data. GRIM and GRIMMER both passed on this row.
- **Table 1, Number of coalition members 35.78 (33.74)** — No range-based claim is made. An initial GRIMMER/SPRITE 'impossible' on this row was an artefact of a default 1-7 scale bound that the paper never states; re-run against a defensible bound the row is GRIM- and GRIMMER-consistent. Rulebook rule 4 forbids reporting a range violation resting on an invented bound.

## Limitations

- This agent reads text and tables only; it does not see figures. Any value appearing solely in a chart was not examined. (This paper's substantive results are all tabular, so the practical loss here is small.)
- The paper reports no confidence intervals for any estimate, anywhere. This blocks the absence_of_evidence check on the fidelity null and leaves the precision of every reported association unquantified.
- All NHST verification had to be routed through z-values reconstructed as B/SE from the printed coefficients and standard errors, because the narrative reports significance only as bare thresholds ('p<.05', 'p<.01') with no test statistic or df -- statcheck found zero APA-format statistics in the body text. This assumes the tables report Wald z (standard for Stata's poisson and nbreg, and for `mixed` in Table 4); if Table 4 reports t instead, its recomputed p-values would shift slightly, though none is near a decision boundary.
- The continuous-to-categorical corroboration of the scale contradiction assumes normality of the coalition-level aggregate. A ceiling-bounded variable would be left-skewed, which weakens that specific arithmetic without removing the documentary contradiction it corroborates.
- Several Table 3 coefficients are printed to one significant figure (0.01 with SE 0.002 or 0.001). Rows at that precision cannot be verified in principle, in either direction -- neither confirmed nor refuted.
- Supporting Information S1 (Tables S1 and S2, the registry hierarchy defining the primary outcome) was not supplied and could not be inspected.
- No raw data were available. The data availability statement offers the datasets "from Drs. Brown and Chilenski upon reasonable request" rather than through deposit, so none of the findings above can be settled by re-analysis.
- No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.

## Coverage

- **Statistics found:** 89; **checked:** 38
- **Tools run:** extract_pdf, statcheck, parse_table, parse_cells_typed, check_table, grim_check, grim_percentage, grimmer_check, grim_sweep, sprite_reconstruct, check_proportion_from_normal, check_summation, check_sd_range, check_regression, detect_duplication, required_n, stalt_check, flag_round_n
- **Tables checked:** Table 1 (coalition EBPs, inclusive leadership and other attributes, n=64), Table 2 (inclusive leadership -> number of EBPs, Poisson, n=64), Table 3 (inclusive leadership -> EBP reach, negative binomial, n=64), Table 4 (inclusive leadership -> EBP fidelity, mixed model, 101 programs in 35 coalitions)
- **Checkable table cells:** 78 of 143 surveyed; **checked:** 11
    - 70 could not be checked without knowing what kind of quantity the row reports
    - 8 were missing an input: n (8)

## What each check does

One entry per check that ran on this paper. The **assumptions** are the conditions under which its verdict holds; where one is unmet the verdict is capped, not merely caveated.

### `check_proportion_from_normal` — probabilistic

Tests a categorical proportion against the reported continuous mean and SD.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The headline test assumes the RAW variable is normal; skew explains a mismatch innocently, so it caps at `suspicious`.
- `highly_suspicious` needs a distribution-free violation -- Cantelli's bound, which holds for EVERY distribution.
- Independent observations (binomial sampling of the count at the threshold).
- The proportion and the mean/SD/n must describe the same sample.

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

Wells and colleagues follow 64 youth substance-misuse prevention coalitions in Pennsylvania and Missouri across two annual waves, nested inside a NIDA-funded randomized technical-assistance trial. They ask whether three facets of inclusive coalition leadership at Wave 1 -- engaging communication, inclusive decision making, and inclusion of community residents -- predict use of evidence-based practices a year later. Poisson models are fitted for the number of EBPs, negative binomial models for EBP reach, and a two-level model for implementation fidelity, each adjusted for the baseline outcome and five covariates. The reported pattern is tidy: communication and inclusive decision making predict more EBPs; all three predict greater reach; none predicts fidelity.

## What held up

The arithmetic that can be checked largely checks out, and this matters for how the rest of the review should be read. Table 1's seven two-decimal percentages jointly admit only n = 64, 128 or 192 as denominators, and each recovers exactly the count printed beside it at n = 64 (55/64, 9/64, 26/64, 41/64, 23/64, 21/64, 20/64). GRIM, GRIMMER and SPRITE all pass on the EBP count row against the paper's own stated 0-9 range. Every dispersion value sits comfortably inside its instrument bound. A cross-table duplication scan over all 63 coefficient cells found zero identical (mean, SD) pairs across 1160 comparisons; the six near-matches are digit transpositions between trivially small round values and were discounted. Sample sizes show natural non-round variation (68 coalitions dropping to 64, 101 programs, 1108/1851 and 945/1695 survey responses). And across 14 regression results reconstructed from their own coefficients and standard errors, statcheck found **zero decision errors** -- not one significance call flips. Nothing in this paper points at fabricated data.

Two sweep flags I discarded on inspection. A GRIMMER/SPRITE "impossible" on the coalition-size row (35.78, SD 33.74) was an artefact of a default 1-7 scale that the paper never states; re-run against a defensible bound the row passes, and rulebook rule 4 forbids any range claim there. A SPRITE failure on EBP reach returned `search_exhausted`, not `no_solution_proven` -- a failed stochastic search over a 0-5370 integer range tells us about the search. I also declined two statcheck flags (Table 3 Communities That Care, Table 4 baseline quality) that are fully explained by the precision at which their inputs were printed.

## Why the paper is nonetheless hard to trust as printed

The problems here are of a different kind from data-integrity anomalies. This paper is difficult to verify not because its numbers conflict with each other but because too many of them are printed too coarsely, labelled wrongly, or not printed at all.

Consider what a reader needs to size the headline effect. The paper explicitly declines to report standardized effect sizes -- "effects are multiplicative and unit increases in key independent variables are idiosyncratic and scale-dependent" -- which is a defensible choice. But it makes the raw coefficient the only available yardstick, and a raw coefficient is meaningless without a known predictor scale. That is precisely what the Measures/Results contradiction removes. Compounding it, the observed SDs of the three predictors are small (0.42, 0.29, 0.32), so no coalition in this sample moves anywhere near a full scale point: a coefficient of 1.34 log-EBPs per unit of inclusive decision making describes a contrast that does not occur in the data. With no confidence intervals anywhere in the paper, neither the positive findings nor the fidelity null carries a stated range of compatible effects.

The fidelity null deserves particular care, because the paper's own Highlights quietly convert it into a promissory note: "It is not yet clear *how* inclusive leadership improves evidence-based practice fidelity" presupposes that it does. What the data show is three coefficients near zero with standard errors of 0.60, 0.98 and 0.72 on a seven-point outcome, from 101 programs in 35 coalitions. That is a small, imprecise study reporting an unquantified absence of evidence. A second Highlight -- "Including local residents in decision making may also improve the use of evidence-based practices" -- rests in part on an association the Results themselves describe as "only marginally significant, at p = .07".

The randomized element is the strangest omission. Half of the original 68 coalitions were randomly assigned to the Coalition Check-Up TA; the Methods state the assignment indicator was in every model; it appears in no table. Because Table 1 carries a single "All coalitions" column with no arm-level split and no baseline p-values, the baseline-similarity tests (Carlisle-Stouffer-Fisher, Table-1 dispersion) had nothing to consume and were not run. That is a gap in coverage, not a clean bill of health, and I have recorded it as such rather than reporting reassurance the data cannot support.

Finally, the analysis has more forking paths than are acknowledged: nine primary tests across three exposures and three outcomes with no multiplicity adjustment, and covariates chosen by a bivariate screen at p < 0.10. The five nominally significant primary results sit between p = .01 and p = .03. No a-priori power analysis is reported. The data are offered "from Drs. Brown and Chilenski upon reasonable request" rather than deposited -- ordinary for this journal, but it does mean none of the above can be settled by re-analysis.

## Verdict

I see no sign of fabricated or manipulated data, and the substantive conclusions may well be sound. But as printed, the results tables are mislabelled, internally inconsistent in places, and in several rows too coarse to check at all, and the paper's most-quoted predictor sits on a scale the paper contradicts itself about. I would want the communication scale clarified, the treatment-assignment coefficient reported, and every estimate re-printed at full precision with confidence intervals before relying on these numbers.

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
