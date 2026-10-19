# Forensic review -- Kang et al. 2009

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## The Efficacy of Postoperative Prophylactic Antibiotics in Orthognathic Surgery: A Prospective Study in Le Fort I Osteotomy and Bilateral Intraoral Vertical Ramus Osteotomy
*Sang-Hoon Kang, Jae-Ha Yoo, Choong-Kook Yi. Yonsei Medical Journal. 2009. doi:10.3349/ymj.2009.50.1.55*

**Design:** Prospective two-arm randomised controlled trial (allocation by Microsoft Excel randomisation codes); 56 patients, 28 per arm; primary outcome postoperative surgical site infection at 2 weeks, analysed by chi-squared test

<sub>Analysed as `10.3349--ymj.2009.50.1.55`</sub>

> **IMPOSSIBLE** — Both baseline age standard deviations in Table 1 are larger than any sample of 28 patients aged "in their 20s" could possibly produce, so the age row and the paper's own description of who was enrolled cannot both be correct.
>
> **In plain terms:** The paper says every patient was in their twenties, but the spread it reports for patients' ages is wider than is arithmetically possible for a group of 28 people all aged between 20 and 30. One of those two statements has to be wrong. This affects how the study describes its patients -- and the argument that its narrow age range makes it better than earlier studies -- but not its main infection result, which checks out.
>
> **Evidence:** Methods: "Fifty-six patients in their 20s without a specific medical history ... were enrolled in this study." Table 1: "Age (Mean±SD) 23.9±5.84 yrs [experimental, n=28] / 24.3±6.33 yrs [control, n=28]", repeated verbatim in Results: "The mean (SD) age of the experimental group was 23.9 years (5.84) ... the control group was 24.3 years (6.33)". For n = 28 confined to [20, 30] -- the most generous possible reading of "in their 20s" -- the largest attainable sample SD is 5.0918. Reported SDs are 5.84 (115% of the ceiling) and 6.33 (124%). Under the strict [20, 29] reading the ceiling is 4.5826 and the reported values reach 127% and 138% of it.
> **Rests on:** a constraint the paper itself states
> **Reproduce:** `metascience sd-range --sd 6.33 --min-val 20 --max-val 30 --n 28 --decimals-sd 2`

**Verdict: questionable** (confidence: high)

## Provenance of the analysis

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

1 study/studies, 6 variables, 1 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| S1 | Postoperative prophylactic antibiotics vs none after Le Fort I osteotomy + bilateral IVRO | rct | 56 | individual patient | no |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Age at surgery | ratio | continuous | 20-29 | years | measured | none -- not integer-valued | high |
| Treatment arm (postoperative antibiotic prophylaxis) | nominal | discrete | experimental group (preoperative dose only, no postoperative antibiotics); control group (preoperative dose plus 1.0 g Cefpiramide twice daily until 3 days after surgery) | - | measured | DEBIT; percentage GRIM | high |
| Sex | nominal | discrete | male; female | - | measured | DEBIT; percentage GRIM | high |
| Postoperative surgical site infection at 2 weeks (CDC criteria) | nominal | discrete | infection present; no infection | - | measured | DEBIT; percentage GRIM | high |
| Wound dehiscence (recorded separately from infection) | nominal | discrete | dehiscence present; no dehiscence | - | measured | DEBIT; percentage GRIM | high |
| Duration of surgery | ratio | continuous | range not stated | hours and minutes | measured | none -- not integer-valued | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Results, final paragraph; repeated in Abstract and Conclusion | chi_squared | Postoperative surgical site infection at 2 weeks (CDC criteria) (binary) | Treatment arm (postoperative antibiotic prophylaxis) | 56 | none | none reported |

_1 of 1 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. Baseline age dispersion in both arms exceeds the ceiling set by the paper's own enrolment description  [IMPOSSIBLE | confidence: high]

**In plain terms.** To say the average age was 24 with a spread of 6.3 years is to say a fair number of patients were in their thirties and a fair number in their teens. But the paper states everyone enrolled was in their twenties, and no group of 28 people all aged 20 to 30 can have a spread that wide -- the arithmetic simply does not allow it. The same problem appears in both treatment groups, so it is not one mistyped number. Reconciling the reported spread would need patients ranging over at least 13 years, mostly clustered at the two extremes. This matters twice over: the description of who was studied is wrong somewhere, and the paper argues in its discussion that its narrow age range is what makes it more reliable than earlier work. It does not, however, affect the infection comparison that is the study's main result.

- **Location:** Table 1, Age (Mean±SD) row, both columns; values repeated in Results paragraph 1; enrolment criterion in Patients and Methods paragraph 1
- **Reported:** "Fifty-six patients in their 20s" enrolled. Table 1 Age (Mean±SD): 23.9±5.84 yrs (experimental, n=28) and 24.3±6.33 yrs (control, n=28). The Results text prints the same two pairs independently of the table.
- **Computed:** For n = 28 on [20, 30], max attainable sample SD = 5.0918; reported 5.84 is 114.7% of it and 6.33 is 124.3% of it (both `impossible`). On the strict [20, 29] reading the ceiling is 4.5826 and the values reach 127.4% and 138.1%. SD/SE confusion is ruled out: read as a standard error, 6.33 implies an SD of 33.5 years, 6.6 times the ceiling, and the tool returns likely_interpretation = "neither". Bracketing the minimum age span that would admit SD = 6.33: a 12-year span (20-32) still fails (SD is 103.6% of the ceiling); 13 years (20-33) is the first that succeeds, and even there the SD sits at 95.6% of the theoretical maximum, attainable only if patients are stacked almost entirely at the two extremes.
- **As printed in the paper:** “Fifty-six patients in their 20s without a specific medical history” _(found in the paper's text)_
- **Our check returned a different severity.** The `check_sd_range` check returned `consistent` for the sweep finding `age_sd_minimum_span_bracket`, which this review recorded as `indeterminate`. This entry asserts more than the check established, so read it as this review's judgement and not as a computed result. The finding states a reason.
- **Assumptions:** The numeric bound [20, 30) is my mapping of the paper's English phrase "in their 20s"; the paper gives no explicit numeric inclusion range. The mapping is forced by the language, and the finding is deliberately reported against the generous [20, 30] reading rather than the strict [20, 29] one so that it does not turn on how tightly the phrase is read. Table 1 is an image in the JATS XML and pdfplumber returned no table grid, so the eight cells were read from PDF page 3; the two age cells are independently corroborated by the machine-extracted Results prose, which prints the identical means and SDs. Both arms fail separately, so this is not a single mistyped cell.
- **Consequence:** changes no significance decision; 2 stated claims affected -- Undermines the Table 1 description of the enrolled sample and the Discussion's claim that a narrow patient age range distinguishes this study from prior work criticised for "wide range of patient's age"; the primary infection comparison does not use these values and is unaffected. (asserted, not computed)
- **Reproduce:** `metascience sd-range --sd 6.33 --min-val 20 --max-val 30 --n 28 --decimals-sd 2`

### 2. Negative conclusion drawn from five total events, with no interval and a design powered only for a 30-percentage-point difference  [SUSPICIOUS | confidence: high]

**In plain terms.** The study concludes that continuing antibiotics after surgery may be unnecessary. But it was designed only to detect a very large difference -- 5% of patients infected in one group versus 35% in the other -- and it saw nothing of the sort: three infections against two. A trial built to spot a gap that big cannot tell you that a smaller but still clinically important gap is absent. The paper also reports no range of plausible values around its result, so a reader has no way to judge how large a real difference could still be hiding in these numbers. Notably, the point estimate that can be recovered actually leans slightly toward the patients who kept taking antibiotics doing better, on a total of five infections across the whole study. The finding here is not that the conclusion is wrong, but that the study is too small to establish it.

- **Location:** Abstract (Conclusion); Discussion, paragraph beginning "Therefore, this study was undertaken"; Discussion, final paragraph
- **Reported:** "Conclusion: Prolonged prophylactic antibiotic use after orthognathic surgery may not be necessary, provided that there are no other significant factors for wound infections." Sample size justification: "The samples were selected at a significance level of α=0.05 and a test power β=0.20. A smaller infection rate was set to 5%, and the difference in the estimated infection rate was set to 30%." No confidence interval, odds ratio, risk difference or test statistic is reported anywhere in the paper.
- **Computed:** The trial was sized to detect 5% versus 35%, a 30-percentage-point gap. The observed contrast was 3 of 28 (10.7%) versus 2 of 28 (7.1%). The recalculation recovers a Fisher odds ratio of 1.56, i.e. the point estimate favours the arm that did receive postoperative antibiotics, on a total of five events. The paper also mislabels its own parameter: β is the Type II error rate, so β = 0.20 corresponds to power = 0.80, not to "a test power β=0.20".
- **As printed in the paper:** “Twenty eight patients were enrolled in each group. The samples were selected at a significance level of α= 0.05 and a test power β= 0.20. A smaller infection rate was set to 5%, and the difference in the estimated infection rate was set to 30%, based on previous report that the incidence of postoperative wound infection using prophylactic antibiotics, ranges from 5.6% to 33.4%.” _(found in the paper's text)_
- **Assumptions:** No arithmetic here is impossible; the concern is inferential and the severity is asserted, not computed. absence_of_evidence could not be run because the paper reports no interval for any effect measure, and verify_power_analysis could not be run because it requires Cohen's h, which the paper does not state and which I am barred from computing by hand. The odds ratio of 1.56 is taken from the chi-squared recalculation, not computed independently.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The Abstract's and Discussion's conclusion that prolonged prophylaxis "may not be necessary" is an absence-of-evidence inference from five events, with no interval reported to bound the effect the trial could have missed. (asserted, not computed)
- **Reproduce:** `metascience chi2 --observed '[[3,25],[2,26]]' --reported-p 0.639 --decimals-p 3`

### 3. Chi-squared test applied to a table whose expected counts fall to 2.5, with no assumption check and no exact alternative  [SUSPICIOUS | confidence: high]

**In plain terms.** The single statistical test in this paper is the standard chi-squared test, and the number it produces is arithmetically correct. But that test is not valid on a table this sparse: with only five infections spread across 56 patients, the counts are far too small for the approximation the test relies on. The appropriate test for such small numbers, Fisher's exact test, gives a p-value of 1.00 rather than 0.639. This does not reverse the conclusion -- neither test finds a difference -- but the reported 0.639 makes the comparison look more precise than it is, and the paper neither checks the assumption nor mentions the exact alternative.

- **Location:** Results, final paragraph (repeated in Abstract); Patients and Methods, statistical analysis sentence
- **Reported:** "Statistical analysis was performed using a χ²-test on the Statistical Package for the Social Sciences (SPSS for windows, ver. 12.0)." "According to the χ²-test, there was no significant difference in the prevalence of postoperative wound infections ... (p = 0.639)." No χ² statistic, no degrees of freedom, and no assumption check are reported; Fisher's exact test is not mentioned.
- **Computed:** An uncorrected Pearson chi-squared on [[3,25],[2,26]] gives χ² = 0.2196, df = 1, p = 0.6393, matching the reported 0.639 exactly, so the test the authors ran is identifiable and its arithmetic is correct. However both infection cells have an expected count of 2.5, below the conventional minimum of 5 for an uncorrected Pearson chi-squared. Fisher's exact test on the same table returns p = 1.00.
- **As printed in the paper:** “Statistical analysis was performed using a χ²-test on the Statistical Package for the Social Sciences (SPSS for windows, ver. 12.0, SPSS Inc., Chicago, IL, USA).” _(found in the paper's text)_
- **Our check returned a different severity.** The `recalc_chi_squared` check returned `consistent` for the sweep finding `chi_squared_expected_counts_below_five`, which this review recorded as `suspicious`. This entry asserts more than the check established, so read it as this review's judgement and not as a computed result. The finding states a reason.
- **Assumptions:** The expected-count threshold of 5 is the conventional rule of thumb, not a mathematical bound; the paper states no assumption check either way. The cell counts 3/28 and 2/28 are taken from Table 1 and are independently confirmed by the Results narrative, whose breakdown of infected patients (one plus "the other 4") sums to five.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The headline p = 0.639 comes from a test whose assumptions this table violates; the appropriate exact test gives p = 1.00, so the "no significant difference" conclusion holds but the reported precision does not. (asserted, not computed)
- **Reproduce:** `metascience chi2 --observed '[[3,25],[2,26]]' --reported-p 0.639 --decimals-p 3`

### 4. Baseline balance not assessable from two rows, one of which rests on the impossible age SDs  [INDETERMINATE | confidence: high]

**In plain terms.** A standard check asks whether the two groups look suspiciously similar at the start, which can be a sign that patients were not really assigned at random. Here that check cannot be done: the paper reports only two baseline characteristics, age and sex, and the age figures are the ones already shown to be impossible. Two characteristics is far too few to draw any conclusion from, and one of them is unreliable. This is a gap in what can be verified, not evidence that anything is wrong -- but neither should it be read as confirmation that the randomisation worked.

- **Location:** Table 1, all baseline rows (Age, Sex)
- **Reported:** Age 23.9±5.84 vs 24.3±6.33 (n = 28 each); Sex (Male : Female) 16 : 12 vs 14 : 14. The paper reports no baseline p-values and makes no explicit claim of baseline balance.
- **Computed:** The dispersion tool returns τ̂ = 2.40 (90% CI 1.87 to 4.09), nominally indicating under-dispersion, from derived baseline p-values of 0.81 (age) and 0.59 (sex). I do not treat this as a finding. The estimate rests on n_rows = 2, the correlation-aware CSF cross-check on the same p-values returned `indeterminate`, and the K-S test against uniformity gives p = 0.33. Decisively, the age p-value of 0.81 is derived from the very SDs shown above to exceed their mathematical ceiling, and inflating an SD mechanically pushes that p-value upward -- so the apparent uniformity is partly manufactured by an input already known to be corrupt.
- **Assumptions:** The tool was run with design = parallel_rct as stated by the paper ("randomization codes generated by Microsoft Excel"). Downgraded from the sweep's `suspicious` to `indeterminate` for the reasons above. This must NOT be read in the opposite direction either: 0.81 and 0.59 are not the Carlisle signature of near-unity baseline p-values, and nothing here provides reassurance that the allocation was sound -- there is simply too little baseline data to judge.
- **Reproduce:** `metascience table1-dispersion --rows '[{"label":"Age (years)","means":[23.9,24.3],"sds":[5.84,6.33],"ns":[28,28]},{"label":"Sex (male:female)","counts":[[16,12],[14,14]]}]' --design parallel_rct`

### 5. Unblinded trial with the primary outcome adjudicated by the operating surgeon  [INDETERMINATE | confidence: high]

**In plain terms.** Patients in the no-antibiotic group were not given a dummy treatment, so everyone involved knew who was getting what. Two of the four criteria used to declare an infection are judgement calls -- swelling, redness, pain -- and one of them is simply the surgeon deciding an infection is present. Since a single surgeon operated on every patient and was not kept unaware of group assignment, the counts of three infections versus two carry less weight than they would in a blinded study. This does not mean the counts are wrong, only that they rest on unblinded judgement.

- **Location:** Patients and Methods, paragraphs 1-2 and the CDC criteria list
- **Reported:** "The patients in the experimental group received only 1.0 g of a third-generation cephalosporin (Cefpiramide) intravenously 30 minutes before surgery and did not receive the placebo." "A horizontal maxillary osteotomy and vertical ramus mandibular osteotomy were performed by the same oral surgeon." The adopted CDC criteria include "pain or tenderness, localized swelling, redness or heat" and, as criterion 4, "Diagnosis of SSI by the surgeon or attending physician."
- **Computed:** No tool in the suite evaluates blinding; this is a reading of the Methods, recorded so it is not silently omitted. Allocation itself was by Excel-generated randomisation codes, which is a defensible method, so the concern is outcome assessment rather than allocation.
- **As printed in the paper:** “The patients in the experimental group received only 1.0 g of a third-generation cephalosporin (Cefpiramide) intravenously 30 minutes before surgery and did not receive the placebo. ... A horizontal maxillary osteotomy and vertical ramus mandibular osteotomy were performed by the same oral surgeon” _(found in the paper's text, across an ellipsis)_
- **Assumptions:** This is a qualitative risk-of-bias judgement with no numeric content, asserted rather than computed. It implies no direction of error.
- **Reproduce:** no runnable command -- the review did not supply a command here. The finding's own numbers are above; re-derive from those.

### 6. No participant flow, attrition figures, or trial registration reported  [INDETERMINATE | confidence: high]

**In plain terms.** The paper never says whether any patient dropped out, was excluded, or missed follow-up -- all 56 enrolled patients simply appear in the results. Over a two-week window after surgery that is quite believable, so this is not suspicious on its own. It does mean a reader cannot independently check the analysed group against the group originally enrolled.

- **Location:** Patients and Methods, paragraph 1; Results throughout
- **Reported:** "Fifty-six patients in their 20s ... were enrolled in this study." All 56 appear in the analysis (28 per arm in Table 1). No exclusions, withdrawals or losses to follow-up are mentioned anywhere, there is no CONSORT flow diagram, and no trial registration number appears. IRB approval by Yonsei University College of Dentistry is stated.
- **Computed:** No tool applies: the finding is the absence of numbers rather than a value to test. The group sizes 28/28/56 are not suspiciously round in the 50/100 sense, so no round-N concern arises, and all reported counts reconcile exactly.
- **As printed in the paper:** “Fifty-six patients in their 20s without a specific medical history ... were enrolled in this study.” _(found in the paper's text, across an ellipsis)_
- **Assumptions:** Complete retention is not implausible over a two-week postoperative window in a hospitalised surgical cohort, and prospective registration was not yet routine for a 2009 paper accepted in April 2008. Recorded as a transparency gap of its era, not as a signal in itself.
- **Consequence:** changes no significance decision -- The analysed sample cannot be reconciled against enrolment independently, though every reported count is internally consistent. (asserted, not computed)
- **Reproduce:** no runnable command -- the review did not supply a command here. The finding's own numbers are above; re-derive from those.

## What we could NOT check

- **Table 1 (XML rendering)** — The JATS XML reports Table 1 as image_only with n_rows: 0 -- it is a picture and carries no cells. pdfplumber also returned no tables, rejecting all five page candidates as segmented prose. The eight cell values were therefore read from PDF page 3 text rather than machine-extracted from a grid. The two age cells and the four counts are independently corroborated by the Results prose, which the XML did render as machine-readable text and which prints the same means, SDs, sex ratios and infection counts.
- **Discussion, sample-size justification** — verify_power_analysis was not run. For two proportions it requires Cohen's h; the paper states raw proportions (5% and 35%) and converting them needs an arcsine transform. Computing that by hand is barred, and supplying a self-computed effect size would make the tool's verdict unauditable. The substantive design point is reported instead, and requires no arithmetic.
- **Abstract Conclusion and Discussion, final paragraph** — absence_of_evidence was not run. It requires ci_low and ci_high, and the paper reports no confidence interval for any effect measure -- not for the risk difference, not for an odds ratio. Deriving an interval by hand is barred.
- **Table 1, Age row** — GRIM and SPRITE were not run. Both require integer-valued observations, and the paper nowhere states that ages were recorded as whole years. Forcing data_type='integer' to obtain a verdict would rest the result on an assumption the paper never makes. The sweep's refusal here was correct and I did not override it.
- **Table 1, Sex row** — debit_check was not run. DEBIT requires a binary variable reported as a mean with an SD; sex is printed as a male:female count ratio (16:12, 14:14), with no mean or SD, so the check has no applicable inputs.
- **Results, primary chi-squared test** — multiplicity_report was not run, deliberately. The paper contains exactly one inferential test of one hypothesis; running a multiplicity analysis on a family of one would manufacture the appearance of a problem that does not exist.
- **Results, primary chi-squared test** — grimu_check and grimu_coexistence were not run. Rank-sum granularity applies only to Mann-Whitney U / Wilcoxon p-values; this paper's only p-value comes from a chi-squared test, and applying GRIM-U to it would be the most likely route to a false accusation.
- **Results, paragraphs 1-2 (duration of surgery)** — The average duration of surgery is reported as "3 hours and 40 minutes" and "3 hours and 55 minutes" with no dispersion, no n-specific figures and no test, so no granularity or consistency check applies. The only stated bound, "The duration of surgery was less than 5 hours", is satisfied by both values.
- **Supplementary materials** — No supplementary files accompany this paper in the provided directory; only the XML and the PDF are present. Recorded as genuinely absent rather than present-but-unreadable.
- **Whole paper -- statcheck** — statcheck recovered zero statistics, not through tool failure but because the paper never prints a test statistic or degrees of freedom anywhere, giving only a bare "p = 0.639". There is no APA-form triple to audit; verification was possible only because the underlying cell counts appear in Table 1.

## Questions for the authors

_Each of these is answerable from what the authors already have. None presupposes an error on their part: an inconsistency is far more often a reporting slip, or a mistake by this tool in reading the number off the page, than anything else._

1. Table 1 and the Results text both give the mean age as 23.9 ± 5.84 years (experimental, n = 28) and 24.3 ± 6.33 years (control, n = 28), while the Methods state that enrolment was limited to "Fifty-six patients in their 20s". For 28 patients aged between 20 and 30 the largest attainable standard deviation is 5.09. Could you provide the observed minimum and maximum age in each arm, so the reported dispersion can be reconciled with the stated enrolment criterion?
   <sub>Would resolve: This is the only question that can settle whether the headline finding is a transcription/typesetting error confined to two cells or a misdescription of the enrolled sample, which in turn determines whether the Discussion's narrow-age-range argument stands.</sub>
2. The primary comparison is 3 of 28 versus 2 of 28, which gives expected counts of 2.5 in both infection cells. Was Fisher's exact test considered as an alternative to the reported χ²-test, and could you report the χ² statistic and degrees of freedom alongside the p = 0.639?
   <sub>Would resolve: Establishes whether the assumption violation was noticed and how the analysis was specified; Fisher's exact on the same table gives p = 1.00, and the paper reports no test statistic or df that would let a reader identify the test independently.</sub>
3. The Discussion states that "The samples were selected at a significance level of α=0.05 and a test power β=0.20", with a smaller infection rate of 5% and an estimated difference of 30%. Could you confirm that β = 0.20 denotes 80% power, and provide the calculation showing that n = 28 per group achieves that power for 5% versus 35%?
   <sub>Would resolve: Resolves the parameter-labelling ambiguity and lets the sample-size justification be reproduced; it also documents the effect size the trial was actually designed to detect, against an observed contrast of 10.7% versus 7.1%.</sub>
4. Given that the experimental group "did not receive the placebo" and that CDC criterion 4 is "Diagnosis of SSI by the surgeon or attending physician", who assessed each patient for surgical site infection, and was that assessor aware of the treatment allocation?
   <sub>Would resolve: Determines the risk of bias in the primary outcome; with a single operating surgeon, an unblinded design and partly subjective criteria, the answer bears directly on how much weight the 3-versus-2 event counts can carry.</sub>
5. Were any of the 56 enrolled patients excluded, withdrawn, or lost to follow-up before the two-week assessment, and was this trial registered before enrolment began?
   <sub>Would resolve: The paper reports no participant flow and no registration number, so the analysed sample cannot be reconciled against enrolment; a simple statement would close the gap.</sub>

## Limitations

- This agent reads text and tables only. It does not see figures, and no claim in this report rests on anything read off an image. This paper contains no figures.
- Table 1 is an image in the publisher XML and pdfplumber recovered no table grid from the PDF, so its eight cells were read from PDF page 3 text rather than machine-extracted. The two age values that carry the headline finding are independently corroborated by the machine-extracted Results prose, which prints identical means and SDs; the count cells are corroborated by the Results narrative and by the chi-squared recalculation. Confidence in these specific values is therefore high despite the extraction route.
- The numeric age bound [20, 30) is my mapping of the paper's phrase "in their 20s", which the paper never states as an explicit numeric inclusion criterion. The finding is reported against this generous reading rather than the strict [20, 29] one precisely so that it does not turn on how tightly the phrase is read.
- The paper's sample-size calculation could not be reproduced: verify_power_analysis requires Cohen's h and the paper reports only raw proportions. The design criticism made here rests on the stated proportions themselves, not on a recomputed power figure.
- No confidence interval could be computed for the infection comparison, because the paper reports none and deriving one by hand is barred. The statement that the data cannot bound the effect being missed is therefore qualitative.
- Baseline balance could not be meaningfully assessed: the paper reports only two baseline characteristics, and one of them is the age row already shown to be arithmetically impossible.
- The specific thing this review could not resolve: whether the two age standard deviations are transcription or typesetting errors, or whether the enrolled sample was not in fact confined to patients in their twenties. Only the raw ages would settle it, and the distinction matters for how much of Table 1 a reader should rely on.
- No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.

## Coverage

- **Statistics found:** 24; **checked:** 20
- **Tools run:** extract_xml, extract_pdf, check_sd_range, check_sd_or_se, recalc_chi_squared, bayesian_table1_dispersion, statcheck, parse_cells_typed, check_table, check_summation_batch, grim_check, detect_duplication
- **Tables checked:** Table 1: Results according to the Postoperative Antibiotic Prophylaxis (image_only in the JATS XML; grid read from PDF page 3 and cross-confirmed against the Results prose; 8 data cells, all covered by targeted tools, 0 of 8 by the batched check_table pass)
- **Where a check and this review disagreed:** 2 sweep findings recorded a severity the validated check behind them did not return (2 upgraded, 0 downgraded). 2 are marked on the entry above that cites them.

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

### `parse_cells_typed` — descriptive

Classifies table cells by kind before any check runs; renders no verdict.

**What its verdict means.** Descriptive. Extracts, parses or computes a quantity; it does not itself render a verdict about the paper.

**Strongest verdict it may reach:** `indeterminate`

**It assumes:**
- Cells returned `ambiguous` carry candidate readings and must not be fed to any forensic tool.

### `recalc_chi_squared` — probabilistic

Recomputes chi-squared under both 2x2 conventions, plus Fisher's exact p.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- Independent observations, each unit counted in exactly one cell.
- Expected cell counts large enough for the chi-square approximation, conventionally at least 5.
- Both the Pearson and Yates conventions are tried, and Fisher's p, before anything is flagged.
- The likelihood-ratio (G-test) convention is NOT tried, so a paper reporting G can mismatch innocently.

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

This is a 56-patient prospective trial from Yonsei University comparing a single preoperative dose of cefpiramide against the same dose continued twice daily for three postoperative days, in patients undergoing Le Fort I osteotomy with bilateral intraoral vertical ramus osteotomy. Allocation was by Excel-generated randomisation codes, 28 per arm. The primary outcome was surgical site infection at two weeks, judged against CDC criteria. Three infections occurred in the arm receiving no postoperative antibiotics and two in the arm that continued them; the authors report a chi-squared p of 0.639 and conclude that prolonged prophylaxis "may not be necessary".

## What verifies, and it is worth saying first

The count layer of this paper is clean. Every sum reconciles exactly with zero tolerance: 16 + 12 and 14 + 14 both give 28, the arms sum to 56, the five infections split 3 and 2, and the narrative breakdown of infected patients -- one diagnosed by sinus haziness plus "the other 4" -- sums to the same five. The sex ratios quoted in prose, 4:3 and 1:1, match the table's 16:12 and 14:14. The single inferential statistic reproduces exactly: an uncorrected Pearson chi-squared on 3/28 versus 2/28 returns 0.2196 on 1 degree of freedom, p = 0.6393, against a reported 0.639. That recalculation also resolves an ambiguity in the Results narrative, pinning the tested counts to 3 versus 2 and confirming that the one patient with wound dehiscence was not folded into the infection count. And the observed infection rates, roughly 11% and 7%, sit close to the 10-15% the authors themselves cite for clean-contaminated orthognathic procedures, so nothing in the outcome data is implausible on its face.

Note what made that verification possible. The paper prints no chi-squared statistic and no degrees of freedom anywhere -- only a bare p. Independent checking worked solely because the cell counts appear in Table 1, which is the reason cell counts outrank stated p-values in the verification hierarchy.

## The reasoning behind the triage

Three of the sweep's calls needed correcting or consolidating, and the reasoning matters more than the outcome.

The six separate age findings are one defect, not six. They reduce to a single statement -- the reported age dispersion cannot be reconciled with the stated sample -- approached from four directions: the strict reading of the enrolment phrase, a deliberately generous reading, the SD-versus-SE rescue attempt, and a bracketing of the minimum age span that would work. All four agree, and reporting them as separate hits would inflate the apparent weight of one problem. They are merged.

The baseline-dispersion result required correcting in the opposite direction from usual. The tool returned a precision multiplier of 2.40, nominally under-dispersion, which the sweep graded `suspicious`. I have downgraded it to `indeterminate`, and the reason is specific rather than cautious: the estimate rests on two baseline rows, the correlation-aware cross-check on the same p-values returned `indeterminate`, and the age p-value of 0.81 is derived from the very standard deviations shown to exceed their mathematical ceiling. Inflating an SD mechanically pushes that p-value upward, so the apparent uniformity is in part an artefact of an input already known to be corrupt. It should not be read the other way either -- 0.81 and 0.59 are nothing like the near-unity signature that indicates non-random allocation, and nothing here reassures anyone that the randomisation was sound. There is simply too little baseline data to judge, and that is the honest answer.

Finally, the sweep declined to run GRIM on the age means, on the ground that the paper nowhere states ages were recorded in whole years. That refusal was correct and I did not override it. Had ages been integers, both means would fail -- but that conclusion would rest entirely on an assumption the authors never made, and the age anomaly is established without it, from the paper's own words.

## What the numbers cannot settle

Two things about this trial sit outside arithmetic. The study was sized to detect a difference between a 5% and a 35% infection rate -- thirty percentage points -- and observed 10.7% against 7.1%. A trial built to spot a gap that large is close to blind to anything smaller, and the recovered odds ratio of 1.56 actually points, weakly and on five events, toward the arm that kept taking antibiotics. With no interval reported for any effect measure, a reader has no way to bound what this study could have missed. That is the gap between "we found no difference" and "there is no difference", and the Conclusion crosses it.

The second is assessment. The experimental group explicitly "did not receive the placebo", one surgeon operated on every patient, and the fourth of the four adopted CDC criteria is diagnosis by that surgeon. Allocation was sound in method; adjudication was not blinded. Three-versus-two is a fragile margin to rest on unblinded judgement.

## Verdict

The primary result of this paper checks out, and its counts are coherent throughout. But its baseline table contains an arithmetic contradiction against the paper's own description of who was enrolled, in both arms; its one test is invalid for the sparse table it was run on; and its clinical conclusion is stronger than five events and no interval can support. I would not rely on Table 1 without the raw ages, and I would not change practice on this study's conclusion.

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
