# Forensic review -- Alalfy et al. 2019

*Analysed 2026-09-02 14:22 UTC  ·  pipeline v1.15.0 (g4a7971102983, uncommitted changes)*

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## Effect of subcutaneous tissue closure technique in cesarean section on postoperative wound complications in obese Egyptian women
*Mahmoud Alalfy, Ahmed Elgazzar, Tamer Fares, Omar Nagy, Ahmed Ellithy, Yossra Lasheen, Ahmed Kamel, Mahmoud Soliman, Ahmed Hassan, Ahmed Samy, Ayman M. Taher, Asmaa I. Ogila, Hany Saad, Hend Salah, Mohamed Ramadan, Mohamed Nabil, Dina L. Hatem, Mohamed Fikry. The Journal of Maternal-Fetal & Neonatal Medicine. 2019. doi:10.1080/14767058.2018.1438399*

**Design:** rct

<sub>Analysed as `paper`</sub>

> **SUSPICIOUS** — Results and Discussion report whole-cohort wound-complication rates of 12%, 10%, 18% and 20% by reprinting Table 1’s event counts as percentages of the same 397 women, whose table rates are 3%, 2.5%, 4.5% and 5%.
>
> **In plain terms:** The authors wrote that 12, 10, 18 and 20 percent of all women had each wound problem, but their own table shows those were the numbers of women, not the percentages — the table rates are about 3, 2.5, 4.5 and 5 percent.
>
> **Evidence:** Table 1: “Yes 12(3)”, “Yes 10(2.5)”, “Yes 18(4.5)”, “Yes 20(5)” of “n=397”. Results: “wound gapping occurred in 12% of cases, wound seroma occurred in 10% of cases, wound erythema occurred in 18% of cases, and wound infection occurred in 20% of cases in the whole cohort of cases.” Discussion repeats the same four percentages.
> **Rests on:** logical necessity (no assumption added)

**Verdict: unresolved** (confidence: high)

_Something could not be settled -- an anomaly that does not resolve either way, an extraction we could not confirm, or a check that could not run on the claim that matters. What it was is named. It is not a finding of misconduct, and it is not a negative result: the middle rung of three means we could not tell, which is a fact about this analysis and not about the paper._

## What the authors shared

- **PREREGISTERED** — NCT03354078, NCT02664285. Preregistration indicated (clinicaltrials). A registered study can still switch outcomes; comparing the registered primary outcome against the reported one is the check this enables, and it is not automated here. No discussion of deviations from the plan was found.
- **Shared artefacts.** This paper points at registration(s): NCT03354078, NCT02664285. No data-availability statement was detected, so the links may be incidental rather than a sharing commitment. Nothing was fetched. To analyse what they point to, supply it with --artefact.

## Statistical anatomy

1 study/studies, 13 variables, 27 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| main | RCT of continuous versus interrupted subcutaneous closure at cesarean section in obese Egyptian women | rct | 397 | participant | no |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Age (years) | ratio | unknown | 25-35 | years | measured | none -- not integer-valued | high |
| BMI | ratio | continuous | 23-45 | kg/m^2 | measured | none -- not integer-valued | high |
| Gestational age at time of CS | ratio | continuous | 35-39.7 | weeks | measured | none -- not integer-valued | high |
| No. of sutures subcutaneous | ratio | discrete | 3-13 (integers) | sutures | other: each interrupted stitch, or each continuous loop from edge to edge, counted as one suture','provenance_quote':'The number of sutures was counted using a double-check method | GRIM (needs stated max) | high |
| Operative time | ratio | continuous | 30-60 | minutes | measured | none -- not integer-valued | high |
| Estimated blood loss | ratio | continuous | 350-1000 | cc | measured | none -- not integer-valued | high |
| Subcutaneous tissue depth | ratio | continuous | 2-6.5 | cm | measured | none -- not integer-valued | high |
| Suture type | nominal | discrete | Continuous; Interrupted | - | measured (randomized allocation 1:1 to continuous or interrupted Vicryl 3-0 subcutaneous closure','provenance_quote':'The two groups were randomly selected, 200 in each group.) | DEBIT; percentage GRIM | high |
| Wound gapping | nominal | discrete | Yes; No | - | measured (clinical inspection at postoperative visits','provenance_quote':'WoundGapping Yes 12(3) No 385(97)) | DEBIT; percentage GRIM | high |
| Wound seroma | nominal | discrete | Yes; No | - | measured (clinical inspection','provenance_quote':'Woundseroma Yes 10(2.5) No 387(97.5)) | DEBIT; percentage GRIM | high |
| Wound erythema | nominal | discrete | Yes; No | - | measured (clinical inspection','provenance_quote':'Wounderythema Yes 18(4.5) No 379(95.5)) | DEBIT; percentage GRIM | high |
| Wound infection | nominal | discrete | Yes; No | - | measured (clinical inspection','provenance_quote':'Woundinfection Yes 20(5) No 377(95)) | DEBIT; percentage GRIM | high |
| Any wound complication | nominal | discrete | Yes; No | - | other: composite of gapping, seroma, erythema, infection; 42 is less than the sum of the four Yes counts (60), so events overlap','provenance_quote':'Woundcomplications Yes 42(10.6) No 355(89.4) | DEBIT; percentage GRIM | medium |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Table 3, Age | independent_t | Age (years) (continuous) | - | 397 | ? | none reported |
| Table 3, BMI | independent_t | BMI (continuous) | - | 397 | ? | none reported |
| Table 3, Gestational age | independent_t | Gestational age at time of CS (continuous) | - | 397 | ? | none reported |
| Table 3, No. of subcutaneous sutures | independent_t | No. of sutures subcutaneous (count) | - | 397 | ? | none reported |
| Table 3, Operative time | independent_t | Operative time (continuous) | - | 397 | ? | none reported |
| Table 3, Estimated blood loss | independent_t | Estimated blood loss (continuous) | - | 397 | ? | none reported |
| Table 3, Subcutaneous tissue depth | independent_t | Subcutaneous tissue depth (continuous) | - | 397 | ? | none reported |
| Table 4, Wound gapping | chi_squared | Wound gapping (binary) | - | 397 | ? | none reported |
| Table 4, Wound seroma | chi_squared | Wound seroma (binary) | - | 397 | ? | none reported |
| Table 4, Wound erythema | chi_squared | Wound erythema (binary) | - | 397 | ? | none reported |
| Table 4, Wound Infection | chi_squared | Wound infection (binary) | - | 397 | ? | none reported |
| Table 5, Age | independent_t | Age (years) (continuous) | - | 397 | ? | none reported |
| Table 5, BMI | independent_t | BMI (continuous) | - | 397 | ? | none reported |
| Table 5, Gestational age | independent_t | Gestational age at time of CS (continuous) | - | 397 | ? | none reported |
| Table 5, No. of sutures | independent_t | No. of sutures subcutaneous (count) | - | 397 | ? | none reported |
| Table 5, Operative time | independent_t | Operative time (continuous) | - | 397 | ? | none reported |
| Table 5, Estimated blood loss | independent_t | Estimated blood loss (continuous) | - | 397 | ? | none reported |
| Table 5, Subcutaneous tissue depth | independent_t | Subcutaneous tissue depth (continuous) | - | 397 | ? | none reported |
| Table 5, Suture type | chi_squared | Any wound complication (binary) | - | 397 | ? | none reported |
| Table 6, Age | logistic_regression | Any wound complication (binary) | Age (years) | 397 | ? | none reported |
| Table 6, BMI | logistic_regression | Any wound complication (binary) | BMI | 397 | ? | none reported |
| Table 6, Gestational age | logistic_regression | Any wound complication (binary) | Gestational age at time of CS | 397 | ? | none reported |
| Table 6, No. of sutures | logistic_regression | Any wound complication (binary) | No. of sutures subcutaneous | 397 | ? | none reported |
| Table 6, Operative time | logistic_regression | Any wound complication (binary) | Operative time | 397 | ? | none reported |
| Table 6, Estimated blood loss | logistic_regression | Any wound complication (binary) | Estimated blood loss | 397 | ? | none reported |
| Table 6, Subcutaneous tissue depth | logistic_regression | Any wound complication (binary) | Subcutaneous tissue depth | 397 | ? | none reported |
| Table 6, Continuous VS Interrupted Sutures | logistic_regression | Any wound complication (binary) | Suture type | 397 | ? | none reported |

#### Variable/test mismatches

A parametric test is applied to an outcome this analysis typed as non-continuous. That is not proof of an error -- the typing may be wrong, and some parametric tests are robust -- but each pair below should be checked against the paper.

- **Table 3, No. of subcutaneous sutures**: `independent_t` assumes a continuous, roughly normal outcome, but **No. of sutures subcutaneous** is typed `count`.
- **Table 5, No. of sutures**: `independent_t` assumes a continuous, roughly normal outcome, but **No. of sutures subcutaneous** is typed `count`.

_27 of 27 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. Results and Discussion reprint Table 1 event counts as whole-cohort percentages  [SUSPICIOUS | confidence: high]

**In plain terms.** In two narrative sections the authors say 12, 10, 18 and 20 percent of the whole group had each wound problem. Their own table uses those same four numbers as head-counts, and the true shares of the 397 women are about four times smaller. A reader of the story will overstate how common the complications were; the head-to-head comparison between suture methods is a separate set of figures and is not changed by this.

- **Location:** Results Description and Discussion, whole-cohort wound-complication rates vs Table 1
- **Reported:** Results: “wound gapping occurred in 12% of cases, wound seroma occurred in 10% of cases, wound erythema occurred in 18% of cases, and wound infection occurred in 20% of cases in the whole cohort of cases.” Discussion repeats “the percentage of wound gapping occurred in 12% of cases … wound infection occurred in 20% of cases.” Table 1, n=397: gapping 12 (3), seroma 10 (2.5), erythema 18 (4.5), infection 20 (5).
- **Computed:** 12/397 = 3.02%, which matches Table 1’s printed 3% and not the prose 12% (implied denominator about 100, not 397). 10/397 = 2.52% vs prose 10%; 20/397 = 5.04% vs prose 20%. Stage 1: 18/397 prints as 4.5%. The Abstract reports the Table 4 p-values and odds ratios, not these inflated percentages.
- **Assumptions:** The Results sentence states the rates are of the whole cohort; Table 1 gives n=397 after exclusion of 3 cases. The implied base of 100 is not a sample size the paper prints, which rules out a silent subgroup denominator. A 0-decimal 12% is attainable at n=397 as some other count, so this is a contradiction between two printed renderings of the same four numerators, not a granularity impossibility. Likeliest innocent reading: the event counts were pasted into a percentage sentence twice.
- **Whose standard:** logic or arithmetic. The paper contradicts itself, or the arithmetic does not work. Nothing outside the document is needed to see it.
- **Consequence:** changes no significance decision; 4 stated claims affected -- The four whole-cohort complication rates in Results and Discussion are fourfold higher than Table 1; the interrupted-versus-continuous tests in Table 4 are unchanged. (asserted, not computed)

### 2. Table 2 BMI range starts at 23.0 while Methods excludes BMI below 30  [SUSPICIOUS | confidence: high]

**In plain terms.** The methods say every woman had a body-mass index above 30 — that is the paper’s own rule for who was obese and who was enrolled — yet the summary table lists a lowest value of 23. Those two statements cannot both be right. The average and midpoint still look like an obese group, so a mistyped 23 for 33 is a live possibility, but the printed range as it stands includes women the authors said they did not have.

- **Location:** Table 2, BMI row vs Patients and methods inclusion criteria
- **Reported:** Methods: “with BMI>30 (so, we do not have a group of women with BMI below 30 as our focus in the present research was to assess the obese women)”; exclusions include “women with BMI<30”. Table 2: “BMI 23.0–45.0 34.5±3.6 34.0”.
- **Computed:** A contiguous Methods span that the sample contains no woman with BMI below 30 cannot both be true with a printed BMI minimum of 23.0. Mean 34.5 and median 34.0 remain compatible with an obese sample.
- **As printed in the paper:** “BMI 23.0–45.0 34.5±3.6 34.0” _(found in the paper's text)_
- **Assumptions:** none beyond the paper's own statements. Innocent readings include a mistyped lower bound (33.0 printed as 23.0) or unreported protocol deviations. Stage 1 confirmed the 23.0–45.0 range on the PDF page image.
- **Whose standard:** the paper's own promise. The paper promised this itself -- a guideline it claims to follow, its registration, its stated outcomes or thresholds. We are holding it to its own word.
- **Consequence:** 1 stated claim affected -- The claim that the analysed cohort is obese women with BMI>30 is incompatible with the printed BMI range starting at 23.0. (asserted, not computed)

### 3. Table 3 subcutaneous-depth p=.127 does not match a t-test on the printed means  [SUSPICIOUS | confidence: medium]

**In plain terms.** For thickness of the fat layer under the skin, the paper prints group averages 4.5 versus 4.4 centimetres and a probability of .127 that such a difference arose by chance. Recalculating from those averages and spreads gives a probability of about .30, not .127. Both figures still count as “not a statistically significant difference,” so the claim that the two suture groups started similar on this measure is unchanged. The paper never says which test produced .127.

- **Location:** Table 3, Subcutaneous tissue depth row
- **Reported:** “Subcutaneoustissuedepth(cm) 4.5±1 4.4±0.9.127” for continuous vs interrupted.
- **Computed:** Welch two-tailed p = 0.295708 (t = 1.0471, df = 390.28); Student two-tailed p = 0.295573 (t = 1.0474, df = 395); one-tailed p = 0.147854. None matches reported p = 0.127 (p_matches false; difference 0.169). Both the printed and the recalculated values are above .05.
- **As printed in the paper:** **Table 3, Subcutaneous tissue depth** -- “Subcutaneous tissue depth (cm) 4.5 ± 1 4.4 ± 0.9 .127” _(found in the PDF text layer)_
- **Assumptions:** Group sizes n=198 and n=199 are taken from Table 4 column headers and Methods, not printed on Table 3 itself. The paper never names the test; Table 3 presents mean±SD with a p, and the other six Table 3 rows match independent t-tests, which is why a t-test is the working reading. A rank-sum test is not named and is not ruled out.
- **Whose standard:** logic or arithmetic. The paper contradicts itself, or the arithmetic does not work. Nothing outside the document is needed to see it.
- **Consequence:** changes no significance decision; 1 stated claim affected -- Both the printed p=.127 and the recalculated p≈.296 are non-significant; the baseline “no difference” claim is unchanged. (asserted, not computed)

### 4. Table 1 attributes two lost-to-follow-up cases to the interrupted arm, which lost one  [SUSPICIOUS | confidence: high]

**In plain terms.** The flow diagram and the methods say one woman in the interrupted-suture group did not return, leaving 199 analysed. Table 1 still lists 199 women but writes that two were lost — the same “lost follow up of 2 women” phrase already used, correctly, for the other group. The analysed numbers add up; the phrase on that row does not.

- **Location:** Table 1, Interrupted row vs Figure 1 and Methods
- **Reported:** Table 1: “Interrupted 199(50.1)afterlostfollowupof2women” and the same “after lost follow up of 2 women” clause on the Continuous 198 (49.9) row. Methods: “Two cases from the continuous group and one case from the interrupted group did not come for the follow up after CS.” Figure 1: interrupted lost N=1, analysed N=199; continuous lost N=2, analysed N=198.
- **Computed:** Stage 1: 200 minus 1 = 199; 200 minus 2 = 198. Analysed 199 matches one loss, not two. 199/397 = 50.1% is internally consistent. Stage 1 summation batch: 1+199=200 and 2+198=200 reconcile; the error is the copied “2 women” clause on the interrupted row.
- **As printed in the paper:** “Interrupted 199(50.1)afterlostfollowupof2women” _(found in the paper's text)_
- **Assumptions:** none beyond the paper's own statements. Innocent reading: the Continuous-row clause was copied onto the Interrupted row.
- **Whose standard:** logic or arithmetic. The paper contradicts itself, or the arithmetic does not work. Nothing outside the document is needed to see it.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The interrupted arm’s analysed n=199 matches one loss, not two; no outcome comparison uses a denominator of 198 for that arm. (asserted, not computed)

## What we could NOT check

- **Publisher XML** — extract_xml: no XML full text at the paper path; sweep used PDF + body.md.
- **Figure 1 image crop** — extract_figures was denied. CONSORT counts were read from the markdown extraction of Figure 1 and checked as sums, not from a figure-pixel pass.
- **Supplementary files** — No supplementary data files were present in the paper directory.
- **Table 2 vs Table 3 vs Table 5 pooled means** — No registered tool checks whether two group means/SDs pool to the printed overall mean.
- **A-priori power calculation** — The paper prints none. verify_power_analysis cannot run without stated inputs.
- **ClinicalTrials.gov NCT03354078** — The identifier is printed. Registration contents and date versus the June–December 2017 enrolment window were not retrieved.
- **Table 3 check_table cells** — check_table ran 0 of 18 dispatched checks because group n was not in Table 3 column headers. Independent t-tests were run separately with n1=198, n2=199.
- **GRIM on n=397 means to 1 decimal** — grim_check refused for no discriminating power. Not a pass.
- **Discussion statistics from cited trials** — Pain 0.17 vs 0.51 p=.04, operative time 24.6 vs 32.9 min p<.0001, and De Vivo ORs belong to cited papers, not this dataset.
- **detect_tortured_phrases / image duplication** — Those detectors were not available or were permission-denied on this backend.
- **table rows Age (years), Age (years), BMI, BMI, Gestational age at time of CS, Gestational age at time of CS and 6 more** — check_sd_or_se not run: check_sd_or_se needs n and this cell carries none; supply n for this row (the participants paragraph or the table footnote usually states it) <sub>(12 cells; recorded by the dispatcher, not by the reviewer)</sub>
- **table rows No. of subcutaneous sutures, No. of subcutaneous sutures** — grim_check not run: grim_check needs n and this cell carries none; supply n for this row (the participants paragraph or the table footnote usually states it) <sub>(2 cells; recorded by the dispatcher, not by the reviewer)</sub>
- **table rows No. of subcutaneous sutures, No. of subcutaneous sutures** — grimmer_check not run: grimmer_check needs n and this cell carries none; supply n for this row (the participants paragraph or the table footnote usually states it) <sub>(2 cells; recorded by the dispatcher, not by the reviewer)</sub>
- **table rows No. of subcutaneous sutures, No. of subcutaneous sutures** — sprite_reconstruct not run: sprite_reconstruct needs n and this cell carries none; supply n for this row (the participants paragraph or the table footnote usually states it) <sub>(2 cells; recorded by the dispatcher, not by the reviewer)</sub>

## Questions for the authors

_Corresponding author: Mahmoud Alalfy <mahmoudalalfy@ymail.com>_

_Each of these is answerable from what the authors already have. None presupposes an error on their part: an inconsistency is far more often a reporting slip, or a mistake by this tool in reading the number off the page, than anything else._

1. Results and Discussion state that wound gapping, seroma, erythema and infection occurred in 12%, 10%, 18% and 20% of the whole cohort, while Table 1 prints 12 (3), 10 (2.5), 18 (4.5) and 20 (5) of 397. Could you confirm which figures are the intended whole-cohort rates?
   <sub>Would resolve: Settles whether the narrative rates are a count-as-percent transcription or a different analysis.</sub>
2. Methods states inclusion with BMI>30 and “we do not have a group of women with BMI below 30,” while Table 2 prints BMI range 23.0–45.0 (mean 34.5±3.6). Could you send the minimum BMI in the 397 analysed women?
   <sub>Would resolve: Settles whether the 23.0 lower bound is a typo or an enrolment deviation from the stated criterion.</sub>
3. Table 3 reports subcutaneous tissue depth 4.5±1 vs 4.4±0.9, p=.127. An independent t-test on those means, SDs and n=198 vs 199 gives p≈.296. Could you say which test and software produced .127?
   <sub>Would resolve: Settles whether the mismatch is an unnamed rank-sum (or other) procedure or a misreported p.</sub>
4. Table 1’s Interrupted row reads “199 (50.1) after lost follow up of 2 women,” while Methods and Figure 1 give one interrupted loss and analysed n=199. Could you confirm the interrupted arm’s lost-to-follow-up count?
   <sub>Would resolve: Settles a copied clause versus a real second loss that would make analysed n=198.</sub>

## What was looked at, beyond the numbers

_Three checks sit outside the arithmetic. Whether each one ran on this paper is a property of how this run was invoked, not of the paper -- and a check that did not run has cleared nothing._

- **Figures** — **did not run**. This analysis read the paper as text; figures were not inspected, so anomalies visible only in plots would not be detected.
- **Image forensics** — **did not run**. No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.
- **Tortured phrases** — **ran**. Screening for tortured phrases was limited to matching against a fixed fingerprint dictionary (tortured phrases, LLM boilerplate, tortured acronyms), computed locally. Novel or unlisted paraphrases, non-English text, and any rewording not in the dictionary were NOT checked, and their absence here is not evidence of their absence in the paper.

## Limitations

- quote_not_located fired on all four Stage-1 accusations; every quoted span is present in the markdown extraction (PDF extraction collapses spaces), so the marker is an instrument fact, not a missing source.
- Figures were not read as images. CONSORT flow counts were taken from the markdown extraction of Figure 1 and checked as sums; no other figure carried unique numeric results.
- No publisher XML and no supplementary data files were available. ClinicalTrials.gov NCT03354078 was not retrieved, so registration timing and outcome correspondence are unchecked.
- The paper has no statistical-methods paragraph (no named t-test, chi-square, logistic model, tails, or software), so the Table 3 subcutaneous-depth mismatch cannot be pinned to a named procedure.
- Whether similar reporting slips appear in other papers by the same authors, and how these wound-complication rates sit against other trials in the same comparison, are outside the reach of a single-paper check.
- RIVETS and standalone check_summation were permission-denied on this recheck; the depth p-value was re-run with recalc_independent_t, and lost-to-follow-up arithmetic is taken from Stage-1 summation-batch output.

## Coverage

- **Statistics found:** 118; **checked:** 96
- **Tools run:** extract_pdf, extract_xml, parse_table, parse_cells_typed, parse_cells_as_declared, check_summation_batch, check_count_percent, check_estimate_ci, recalc_chi_squared, recalc_independent_t, grim_check, grimmer_check, check_sd_range, check_table, csf_test, bayesian_table1_dispersion, statcheck, multiplicity_report, detect_duplication, flag_round_n, check_effect_plausibility, required_n
- **Tables checked:** Table 1, Table 2, Table 3, Table 4, Table 5, Table 6, Figure 1 CONSORT
- **Every checkable item:** 230 registered; 124 refused with a stated reason; **106 outstanding**
    - how many were CHECKED is not measured -- no persisted item identity joins a tool call back to a manifest row, so how many items were CHECKED cannot be counted. This is not a count of zero. This is not a count of zero.
- **Stage-1 findings:** 42 raised; 4 carried into this report; 38 not carried
- **Where a check and this review disagreed:** 3 sweep findings recorded a severity the validated check behind them did not return (0 upgraded, 3 downgraded). 3 sit on sweep findings no entry in this report cites, so this line is the only place they appear.
- **Traceable to the page:** 96 of 96 checks recorded the passage their numbers were read from; 87 of those were located in the paper's own text.
- **9 quoted passages are ours, not the paper's.** Every number in them was found in the paper, but the sentence around those numbers was assembled by this review and does not appear as written -- so do not search the PDF for it. The CHECK is sourced; only the quotation marks over-promise.

## Narrative

This trial randomised 400 women having a first caesarean to continuous or interrupted Vicryl 3-0 closure of the subcutaneous layer (analysed 198 vs 199) and concluded that interrupted closure is superior on four wound complications.

The arm-level comparisons that carry that conclusion check. Table 4’s four 2×2 tables reproduce the printed p-values and odds ratios (gapping 10/198 vs 2/199, p=.019, OR=5.239; seroma 9 vs 1, p=.011, OR=9.429; erythema 14 vs 4, p=.015, OR=3.709; infection 17 vs 3, p=.001, OR=6.136). Table 1’s n(%) cells, the composite 33+9=42 in Table 5, the flow-diagram cascade 411−11=400 with 200−1=199 and 200−2=198, six of seven Table 3 t-tests, the Table 6 odds-ratio intervals, and the suture-count reconstruction all reconcile. Forty-one of fifty checks passed; every granularity item matched on its printed values, with no rounding or population-SD allowance needed. Baseline similarity was unremarkable (similarity p=.883; τ̂=0.72).

What does not settle is how the same four event counts are written in prose. Table 1 prints 12 (3), 10 (2.5), 18 (4.5) and 20 (5) of 397. The Results description, and again the opening of the Discussion, call those 12%, 10%, 18% and 20% “of cases in the whole cohort.” That sentence names the 397-woman cohort as the base, so a silent subgroup denominator is not available as an explanation: 12 events in 397 is 3%, and the printed 12% implies a base of about 100, a size the paper never uses. The Abstract does not repeat the inflated rates. The likeliest innocent reading is that the numerators were pasted into a percentage sentence and never converted. A reader who uses the Discussion’s rates will think complications were four times as common as the table shows. The between-arm claims are untouched.

A second pair of passages cannot both be true of the cohort. Methods states BMI>30 and “we do not have a group of women with BMI below 30”; Table 2 prints BMI range 23.0–45.0. Mean 34.5 and median 34.0 still look like an obese sample, so a mistyped 23.0 for 33.0 remains live, but the two statements as printed conflict.

Table 1 copies “after lost follow up of 2 women” onto both arms. Interrupted analysed n=199 matches Methods and Figure 1 (one loss), not two. And Table 3’s subcutaneous-depth p=.127 does not come from a t-test on 4.5±1 vs 4.4±0.9 (that t-test is p=.296); both values are non-significant. Tests are never named, so a rank-sum remains possible; the other six Table 3 rows do match t-tests.

The numbers that support interrupted versus continuous closure reconcile with each other. The whole-cohort rates in the Results and Discussion, and the BMI inclusion statement, do not.

The arm-comparison figures check; the whole-cohort rates in the narrative and the body-mass-index range do not, and those contradictions need to be resolved before the descriptive results are used.

## What each check does

One entry per check that ran on this paper. The **assumptions** are the conditions under which its verdict holds; where one is unmet the verdict is capped, not merely caveated.

### `bayesian_table1_dispersion` — probabilistic

Estimates Table 1 baseline dispersion (tau) to flag under- or over-dispersion versus chance.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- Under proper simple randomisation baseline p-values are uniform and z^2 ~ chi2_1, so E[z^2] = 1.
- The CI on tau inverts the EXACT chi-square null of mean(z^2); a percentile bootstrap was used until it was measured to accuse 35.9% of honest 2-row tables.
- Rows are treated as equicorrelated at rho = 0.5, discounting k rows to k/(1+(k-1)rho) effective degrees of freedom -- so a table of ANY size is worth about 2 df, and large tables are not thereby more accusable.
- Stratified, minimised, cluster, matched and crossover designs are refused; an unstated design caps the verdict.
- Escalation also requires csf_test's correlation-aware combination of the same p-values to corroborate; csf finding nothing vetoes it.
- An elevated tau whose CI does not exclude tau = 1 is reported `indeterminate`, never `consistent`: too few effective df to convict OR to clear.

### `check_count_percent` — probabilistic

Checks the printed count over the printed denominator against the printed percentage.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The percentage is assumed to be over THIS n -- the assumption most likely to be wrong, since row, column and subgroup bases coexist in one table.
- Ceiling `suspicious`, tighter than its class allows: a different percentage base is an ordinary reporting convention and no arithmetic disagreement rules it out.
- The printed percentage asserts a rounding interval, and its decimals must be supplied rather than assumed.
- A count exceeding its denominator is reported as a wrong pairing, not as a defect in the paper.

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

### `check_sd_range` — absolute

Checks a reported SD against the hard ceiling implied by the variable's range.

**What its verdict means.** Absolute (possible vs impossible). Exact arithmetic over the printed values and their rounding intervals. Subject to the preconditions below, a flagged result cannot be produced by any dataset.

**Strongest verdict it may reach:** `impossible`

**It assumes:**
- min_val and max_val must be the variable's TRUE attainable bounds. Say which via `bound_source`: an assumed range caps the verdict at `highly_suspicious`, and only a range the paper STATES (or one that is logically necessary, e.g. a percentage) can reach `impossible`.
- Pass decimals_sd; without it the precision is inferred from the literal, which errs wide but is a guess.
- With n unknown the ceiling is the weakest over all n (range/sqrt(2), attained at n = 2); supplying n tightens it.
- A negative SD is bound-free and impossible whatever else is unknown.

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

### `csf_test` — probabilistic

Combines baseline p-values to detect arms more similar than randomisation allows.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- Baseline p-values are mutually independent and uniform under simple randomisation, unless a correlation is supplied.
- Unknown correlation is handled by an equicorrelated null and the verdict read at a conservative rho = 0.5.
- Simple randomisation is required: cluster, multi-site, stepped-wedge, crossover, matched and stratified designs are refused.
- An unstated or unrecognised design caps the verdict below `highly_suspicious`.
- One-sided for EXCESS similarity, and at least three usable p-values are needed.

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

### `parse_cells_as_declared` — descriptive

Parses cells under a model-declared format from a closed vocabulary; renders no verdict.

**What its verdict means.** Descriptive. Extracts, parses or computes a quantity; it does not itself render a verdict about the paper.

**Strongest verdict it may reach:** `indeterminate`

**It assumes:**
- The format NAME comes from the model; every character of the matching is code in tools/cellformat.py. No pattern is generated at run time -- a generated regex is a generated statistic, and a wrong capture becomes a plausible mean that no later layer can recognise as invented.
- The declaration is a hypothesis about the table and is tested before it is applied: cells are checked against the same coherence guards the row/column-label path uses, and a declaration fitting under `min_fit` of the cells is refused wholesale.
- Several formats genuinely fit the same numbers -- `142 (71.0)` is a valid mean (SD) and a valid n (%). The numbers cannot choose; the declaration must come from reading the table's header, caption and footnotes, and `n_overrides_automatic` counts the cells where it contradicted them.

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

### `recalc_chi_squared` — probabilistic

Recomputes chi-squared under both 2x2 conventions, plus Fisher's exact p.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- Independent observations, each unit counted in exactly one cell.
- Expected cell counts large enough for the chi-square approximation, conventionally at least 5.
- Both the Pearson and Yates conventions are tried, and Fisher's p, before anything is flagged.
- The likelihood-ratio (G-test) convention is NOT tried, so a paper reporting G can mismatch innocently.

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

### `statcheck` — probabilistic

Extracts APA-style results and recomputes their p-values for internal consistency.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- Each p is recomputed assuming a two-tailed, unadjusted test.
- Only APA-formatted results are extracted; everything else is invisible to it.
- A p correct at its own printed precision is not an error.
- Inconsistencies are near-universal in honest work and must never support a misconduct verdict alone.

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

**What it has been tested on.** Tested on 35 runs over 19 papers (28 runs over 16 papers classified by design). Almost all of them are
primary biomedical or psychology research and most are human randomised
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

## Provenance

- **Analysed:** 2026-09-02 14:22 UTC
- **Pipeline version:** v1.15.0 (g4a7971102983, uncommitted changes)
- **LLM backend:** grok (grok 1.0.13 (5e9a58528b76) [stable])
- **Sandbox:** Grok's `search_tool` cannot be denied: it is the only route to the forensic MCP tools. This run's sandbox is weaker than a Claude run's.
- **Prompts:** 161c6d7ed4d52b7e
- **Tool registry:** 0b06c178cea5ee68
- **Models:** grok-4.6, grok-4.6-build (editorial); grok-4.6, grok-4.6-build (sweep)
- **Reasoning effort:** high

_Two reviews are directly comparable only if the pipeline version, the prompt hash and the registry hash all match. The version alone is not sufficient: it moves about once a month, while the prompts and the tool registry move several times a day, so a difference between two runs stamped with the same version may be a change in this toolkit rather than a fact about the papers._
