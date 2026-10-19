> **REPORT INCOMPLETE** — this review was assembled from a malformed or missing model output and must not be read as a complete analysis: headline.severity 'none' is weaker than findings[0].severity 'suspicious'; the headline must be at least as severe as the worst finding it introduces

> **REPORT INCOMPLETE** — this document was rendered from a malformed report object and must not be read as a complete review: headline.severity 'none' is weaker than findings[0].severity 'suspicious'; the headline must be at least as severe as the worst finding it introduces

# Forensic review -- Kang et al. 2009

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## The Efficacy of Postoperative Prophylactic Antibiotics in Orthognathic Surgery: A Prospective Study in Le Fort I Osteotomy and Bilateral Intraoral Vertical Ramus Osteotomy
*Sang-Hoon Kang, Jae-Ha Yoo, Choong-Kook Yi. Yonsei Medical Journal. 2009. doi:10.3349/ymj.2009.50.1.55*

**Design:** Two-arm randomised prospective trial (allocation by Microsoft Excel randomisation codes), no placebo, single surgeon, 56 patients

<sub>Analysed as `10.3349--ymj.2009.50.1.55`</sub>

> **NO MAJOR PROBLEM FOUND** — Every number this five-page trial prints reconciles with the statistics beside it -- the sole p-value reproduces exactly from the counts in Table 1, all four count rows sum, and both age mean/SD pairs are reconstructible -- but the paper's conclusion that prolonged prophylaxis "may not be necessary" is an acceptance of the null stated with no confidence interval, from a trial sized to detect only a 30-percentage-point difference in infection rate.
>
> **In plain terms:** This small trial's numbers all add up: the one statistical test it reports can be recalculated exactly from the patient counts printed in its table, and nothing in the paper contradicts anything else. What the paper cannot support is how confidently it reads its own result -- it found 3 infections in one group and 2 in the other, which tells you almost nothing, and it never says how big a real difference could still be hiding behind that.
>
> **Evidence:** Table 1: "Postoperative infection (n) 3 | 2" in arms of "(n=28)" and "(n=28)"; Results: "According to the χ²-test, there was no significant difference in the prevalence of postoperative wound infections ... (p = 0.639)." Recomputed from the printed 2x2 [[3,25],[2,26]]: Pearson χ²(1) = 0.2196, p = 0.639339 -- matching the printed 0.639 to three decimals. Counts: 16+12 = 28, 14+14 = 28, 28+28 = 56, 3+2 = 5, all exact. Ages 23.9 ± 5.84 and 24.3 ± 6.33 at n = 28 both admit valid integer (sum, sum-of-squares) solutions. Design, from the Discussion: "A smaller infection rate was set to 5%, and the difference in the estimated infection rate was set to 30%".
> **Rests on:** logical necessity (no assumption added)
> **Reproduce:** no runnable command -- the review's command used an option this tool does not have. The finding's own numbers are above; re-derive from those.

**Verdict: reconciles** (confidence: high)

## Provenance of the analysis

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

1 study/studies, 6 variables, 1 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| S1 | Prospective randomised trial of postoperative prophylactic antibiotics after Le Fort I osteotomy + bilateral IVRO | rct | 56 | patient | no |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Treatment arm | nominal | discrete | experimental group without postoperative antibiotics; control group with postoperative antibiotics for 3 days | - | measured | DEBIT; percentage GRIM | high |
| Postoperative surgical site infection (SSI) within 2 weeks, per CDC criteria | nominal | discrete | infection; no infection | - | measured | DEBIT; percentage GRIM | high |
| Wound dehiscence (n) | nominal | discrete | dehiscence; no dehiscence | - | measured | DEBIT; percentage GRIM | high |
| Age at surgery (years) | ratio | unknown | range not stated | years | measured | none -- not integer-valued | medium |
| Sex | nominal | discrete | Male; Female | - | measured | DEBIT; percentage GRIM | high |
| Duration of surgery | ratio | continuous | range not stated | hours and minutes | measured | none -- not integer-valued | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Results, final paragraph (repeated in Abstract) | chi_squared | Postoperative surgical site infection (SSI) within 2 weeks, per CDC criteria (binary) | Treatment arm | 56 | none | none reported |

_1 of 1 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. Null conclusion drawn with no confidence interval, from a design sized only for a 30-percentage-point difference  [SUSPICIOUS | confidence: high]

**In plain terms.** The trial was built to spot a very large difference: roughly 5 out of 100 patients getting infected in one group versus 35 out of 100 in the other. What it actually saw was 3 infections against 2. With numbers that small, a difference that would matter to a real patient could easily be present and go undetected -- and the paper never says what range of differences its data can rule out. So "we found no difference" is not the same as "there is no difference", and the recommendation to stop antibiotics earlier rests on the weaker of those two. Note this is a limitation of what the study can conclude, not a sign that any number in it is wrong; the authors are unusually open about their design assumptions, which is what makes this visible at all.

- **Location:** Abstract (Results and Conclusion); Results, final paragraph; Discussion, sample-size paragraph
- **Reported:** "Conclusion: Prolonged prophylactic antibiotic use after orthognathic surgery may not be necessary, provided that there are no other significant factors for wound infections." The supporting evidence is p = 0.639 alone. The Discussion states the design: "The samples were selected at a significance level of α=0.05 and a test power β=0.20. A smaller infection rate was set to 5%, and the difference in the estimated infection rate was set to 30%". No confidence interval, effect size, or risk difference is reported anywhere in the paper.
- **Computed:** recalc_chi_squared on the printed 2x2 [[3,25],[2,26]] returns a Fisher odds ratio of 1.56 -- the point estimate favours MORE infection in the arm that received fewer antibiotics, the opposite direction from the conclusion's framing, though on 3 versus 2 events it is indistinguishable from no difference (Fisher p = 1.0). The trial's own stated target was a 5% versus 35% infection rate; the observed contrast is 3/28 versus 2/28, a difference of one patient. No registered tool in this kit derives a confidence interval from a 2x2 count table, so the largest difference these data still permit could not be quantified -- that gap is recorded rather than estimated.
- **Assumptions:** None beyond the paper's own statements. The design parameters (α = 0.05, 5% smaller rate, 30% difference, 28 per group) and the event counts are all quoted as printed. The odds ratio of 1.56 is tool output, not hand arithmetic. The direction of the point estimate is noted, not interpreted as evidence of harm.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The paper's single recommendation -- that prolonged postoperative prophylaxis may be unnecessary -- is argued from a non-significant p-value alone, with nothing stating how large a clinically meaningful difference in infection rate the trial could still have missed. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command used an option this tool does not have. The finding's own numbers are above; re-derive from those.

### 2. Chi-squared applied where expected cell counts are 2.5, half the conventional minimum  [SUSPICIOUS | confidence: high]

**In plain terms.** The statistical test the authors used is an approximation that needs a reasonable number of expected events in each cell of the table; here it expects only 2.5, about half what the rule of thumb asks for. A different test designed for small counts is the standard choice in that situation. It changes nothing about the answer -- every version of the test says the same thing, that no difference was detected -- but it means the specific number 0.639 should not be read as precise.

- **Location:** Patients and Methods, statistical analysis sentence; Results, final paragraph; against Table 1 infection row
- **Reported:** "Statistical analysis was performed using a χ²-test on the Statistical Package for the Social Sciences (SPSS for windows, ver. 12.0, SPSS Inc., Chicago, IL, USA)." The test is applied to 3 infections of 28 versus 2 of 28, and reported as p = 0.639. No exact test is mentioned.
- **Computed:** recalc_chi_squared returns expected counts of 2.5 in both infection cells -- half the conventional minimum of 5 for the chi-squared approximation. The reported p = 0.639 is reproduced exactly by the uncorrected Pearson statistic (χ²(1) = 0.2196, p = 0.639339), which identifies the convention used. The two alternatives appropriate to these counts both give p = 1.0: Yates-corrected χ² = 0.0000, and Fisher's exact p = 1.0.
- **As printed in the paper:** **Results, final paragraph, and Table 1 infection row** -- “According to the χ²-test, there was no significant difference in the prevalence of postoperative wound infections between the patients who had received postoperative prophylactic antibiotic administration and those who had not (p = 0.639).” _(found in the paper's text)_
- **Our check returned a different severity.** The `recalc_chi_squared` check returned `consistent` for the sweep finding `chi_squared_expected_counts_below_five`, which this review recorded as `suspicious`. This entry asserts more than the check established, so read it as this review's judgement and not as a computed result. The finding states a reason.
- **Assumptions:** The 5-per-cell minimum for the chi-squared approximation is Cochran's conventional rule (Cochran 1954), an external norm this paper never claims to follow. Uncorrected 2x2 chi-squared on small counts was routine in clinical reporting in 2008-2009, when this was submitted and published.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The stated finding of no difference stands under every convention -- Pearson p = 0.639, Yates p = 1.0 and Fisher's exact p = 1.0 are all non-significant -- so the test choice makes the reported p optimistically precise rather than wrong in direction. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command used an option this tool does not have. The finding's own numbers are above; re-derive from those.

### 3. The trial's only inferential test is reported as a bare p-value, with no test statistic and no degrees of freedom  [SUSPICIOUS | confidence: high]

**In plain terms.** When researchers report a statistical test, they normally print the test's own value alongside the p-value, so a reader can check that the two agree. This paper prints only the p-value. It happens to be correct -- the counts in the table let us recompute it and it matches exactly -- but that was luck of layout rather than design: if the table had shown percentages instead of patient counts, the paper's one and only statistical claim could not have been checked by anyone.

- **Location:** Results, final paragraph, and Abstract
- **Reported:** "According to the χ²-test, there was no significant difference in the prevalence of postoperative wound infections between the patients who had received postoperative prophylactic antibiotic administration and those who had not (p = 0.639)." The chi-squared value and its degrees of freedom appear nowhere in the paper.
- **Computed:** statcheck returned 0 parseable statistics across the full Results and Discussion text -- not a failure of the scanner, but the correct answer for a paper that reports no test statistic anywhere. There is consequently no internal redundancy against which a reader could have checked the p-value from the sentence reporting it. Recovery was possible here only because Table 1 happens to print the underlying cell counts; from those, Pearson χ²(1) = 0.2196 gives p = 0.639339.
- **As printed in the paper:** **Results and Discussion, prose** -- “According to the χ²-test, there was no significant difference in the prevalence of postoperative wound infections between the patients who had received postoperative prophylactic antibiotic administration and those who had not (p = 0.639).” _(found in the paper's text)_
- **Assumptions:** The expectation that a reported test carries its statistic and degrees of freedom is a reporting norm I am supplying; this paper claims no reporting guideline. No numerical error is alleged -- the p-value is correct.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The paper's sole confirmatory claim would have been unverifiable by any reader had Table 1 not independently printed the four cell counts the test was computed from. (asserted, not computed)
- **Reproduce:** `metascience statcheck --text "According to the chi2-test, there was no significant difference in the prevalence of postoperative wound infections between the patients who had received postoperative prophylactic antibiotic administration and those who had not (p = 0.639)."`

### 4. Outcome assessed unblinded by the operating surgeon, on partly subjective infection criteria  [SUSPICIOUS | confidence: medium]

**In plain terms.** Deciding whether a surgical wound is infected involves judgement calls about swelling, redness and pain. In this trial the surgeon who performed every operation also knew which patients had been given the extra antibiotics, and no one independent was brought in to make that call. That does not mean the counts are wrong, and the paper is upfront that no dummy treatment was used -- but a reader who assumes a randomised trial means an impartial assessment should know that this one did not have one.

- **Location:** Patients and Methods: allocation paragraph and the SSI criteria list
- **Reported:** "The patients in the experimental group received only 1.0 g of a third-generation cephalosporin (Cefpiramide) intravenously 30 minutes before surgery and did not receive the placebo." Surgery was performed "by the same oral surgeon". The outcome definition includes "pain or tenderness, localized swelling, redness or heat, and a superficial incision deliberately opened by surgeon" and "Diagnosis of SSI by the surgeon or attending physician". The paper states no blinding of patients, of the surgeon, or of the outcome assessor.
- **Computed:** No computation. This is a design reading: allocation was randomised (Excel codes) but not masked, and two of the four CDC criteria the paper adopts are assessor-judged rather than laboratory-confirmed, with the assessor being the clinician who both knew the allocation and performed the operation.
- **As printed in the paper:** “The patients in the experimental group received only 1.0 g of a third-generation cephalosporin (Cefpiramide) intravenously 30 minutes before surgery and did not receive the placebo.” _(found in the paper's text)_
- **Assumptions:** CONSORT 2001 item 11 (current when this was submitted in March 2008) asks whether participants, those administering care, and those assessing outcomes were blinded, and if not, how the lack of blinding was addressed. The paper does not claim to follow CONSORT. The direction of any resulting bias is not determinable from what is reported, and with 3 and 2 events the question does not affect the significance of the result. The paper is transparent that no placebo was given, which is to its credit.
- **Consequence:** 1 stated claim affected -- The infection counts that the single reported test is computed from were judged in part on subjective signs by an unmasked assessor, which bears directly on the primary outcome. (asserted, not computed)
- **Reproduce:** `No command applies: this is a design observation read from the Methods, not a computation.`

### 5. "Test power β=0.20" mislabels the type II error rate in the sentence justifying the sample size  [SUSPICIOUS | confidence: high]

**In plain terms.** One sentence calls the number 0.20 the study's "test power". By standard convention 0.20 there is the chance of missing a real effect, which makes the power 0.80 -- and 0.80 is what the study's group sizes fit. Taken literally the sentence would describe a study designed to fail four times out of five. It is a wording slip that changes none of the results, but it sits in the one sentence a reader would use to check how the sample size was chosen.

- **Location:** Discussion, sample-size paragraph
- **Reported:** "The samples were selected at a significance level of α=0.05 and a test power β=0.20."
- **Computed:** No computation. As printed, the sentence asserts 20% power alongside α = 0.05, which describes a design no one would run and which is inconsistent with the 28-per-group sample the same paragraph reports. The conventional reading -- β as the type II error rate, giving power of 1 − β = 0.80 -- is the one the stated sample size fits.
- **Assumptions:** None beyond the paper's own statements. The intended meaning is unambiguous from context; this is recorded because it sits in a load-bearing methods sentence rather than in incidental text.
- **Consequence:** changes no significance decision -- No reported number changes; the sample size of 28 per arm is stated independently and is consistent with the conventional reading of β = 0.20 as the type II error rate. (asserted, not computed)
- **Reproduce:** `No command applies: this is a notation error read off the sentence, not a computation.`

### 6. No numeric age range reported, leaving the cohort-homogeneity premise that motivates the study unverifiable  [INDETERMINATE | confidence: medium]

**In plain terms.** The paper describes its patients only as being "in their 20s", and never gives the youngest and oldest ages. Its own spread figures suggest a wider age span than that phrase implies, though a genuinely lopsided age distribution would explain both without anything being wrong -- and the arithmetic of the age figures themselves checks out. This matters because the study's whole rationale is that earlier trials were muddied by patients of widely varying ages, so a reader has no way to confirm that this trial actually avoided the problem it set out to fix. This is an open question, not an error.

- **Location:** Patients and Methods, first sentence; Table 1 Age row; Discussion, paragraph 3
- **Reported:** "Fifty-six patients in their 20s without a specific medical history ... were enrolled in this study." Table 1 gives ages as "23.9±5.84 yrs" and "24.3±6.33 yrs". The Discussion criticises prior work because "wide range of patient's age, small group size, and various osteomies may cause difficulties when precisely evaluating the efficacy of prophylactic antibiotics", and positions this study as examining "young patients". No minimum or maximum age is printed anywhere.
- **Computed:** Both age cells PASS the arithmetic check that applies to them: grimmer_check finds valid integer (sum, sum-of-squares) solutions for 23.9 ± 5.84 at n = 28 (five combinations, e.g. sum 669, sum-of-squares 16905) and for 24.3 ± 6.33 (four combinations), so the printed pairs are internally coherent. Separately, check_sd_range against an age band of 20-29 returns both SDs above the 4.583 ceiling that band permits (5.84 is 1.27x, 6.33 is 1.38x) -- but [20, 29] is MY translation of the prose "in their 20s", not numerals the paper prints, so that result establishes nothing about the paper. check_proportion_from_normal on 0 of 28 below age 20 gives binomial p = 0.00062 yet explicitly does NOT violate its distribution-free bound [0.0000, 0.6916], so a skewed age distribution accounts for the SDs without any reporting error.
- **As printed in the paper:** **Patients and Methods, first sentence, against Table 1 Age row** -- “Fifty-six patients in their 20s without a specific medical history” _(found in the paper's text)_
- **Assumptions:** The [20, 29] range is assumed, not stated -- it is a reading of the phrase "in their 20s", which reads at least as naturally as loose shorthand for a young-adult cohort as it does as an inclusion criterion. The paper is silent, so the innocent explanation stands and this is graded indeterminate rather than as a defect. CONSORT 2001 item 3 (eligibility criteria for participants) is cited as the reason a numeric range would have settled it; the paper does not claim CONSORT.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The study's stated rationale is that a narrow, young age range removes a confounder that compromised earlier trials, and with no numeric range printed a reader cannot check whether this cohort was in fact narrower than the ones it criticises. (asserted, not computed)
- **Reproduce:** no runnable command -- the review could not produce one that runs. The finding's own numbers are above; re-derive from those.

## What we could NOT check

- **Discussion, sample-size paragraph (α = 0.05, β = 0.20, 5% smaller rate, 30% difference, 28 per group)** — verify_power_analysis and required_n both need the effect size on the test's own metric -- Cohen's h for a two-proportion design. The paper prints the two proportions but not h, and deriving h requires arcsine arithmetic this stage may not perform by hand. The stated design is therefore recorded but not reproduced. A genuine gap in the toolkit for proportion-based power statements.
- **Abstract and Results, the p = 0.639 null claim** — absence_of_evidence needs either a confidence interval or a coefficient with a standard error, and the paper prints neither. No registered tool derives an interval from a 2x2 count table, so the largest difference in infection rate the data still permit could not be quantified. Reported as a finding rather than a computed bound.
- **Table 1, Wound dehiscence row (0 versus 1)** — The paper reports no test on this row and makes no claim about it. Tabulating a comparison the authors did not make would manufacture a test that does not exist in the paper.
- **Age means 23.9 and 24.3 (GRIM)** — GRIM has no discriminating power at n = 28 with one decimal place -- every value printable to 1 dp is attainable as a mean of 28 integers. The age means were therefore NOT cleared by GRIM; the check simply could not have caught anything. GRIMMER, which can discriminate here, passed both cells.
- **Baseline similarity (csf_test and bayesian_table1_dispersion not run)** — Not applicable. The paper reports no baseline p-values at all -- Table 1 gives age, sex, infection and dehiscence with no between-arm comparisons -- so there is no set of baseline p-values to test for excess uniformity, and two baseline rows would make a dispersion estimate uninformative even if constructed.
- **Cross-table duplication (detect_duplication not run)** — Not applicable. The paper contains exactly one table describing one sample, so there is no second block of means and SDs to compare it against.
- **Multiplicity correction (multiplicity_report not run)** — Not applicable. The paper reports a single planned confirmatory test of a single hypothesis; there is no family to correct over.
- **Group sizes 56, 28, 28 (flag_round_n not run)** — A deliberate decision. Roundness carries no signal here: the paper states that 28 per arm came from an a-priori sample-size calculation, so the value is design-determined rather than a convenient total.
- **Literature values cited in the Discussion (52.6%; 10-15%; 5.6-33.4%)** — Statistics attributed to references 13, 14 and 17, not computed from these data, and no denominators are given for them here. Verifying them requires the cited papers, which are outside the scope of a single-paper analysis.
- **Average duration of surgery (3 h 40 min; 3 h 55 min)** — Reported as means with no SD, no dispersion and no accompanying test, in hours-and-minutes form. No granularity or comparison check applies to a location statistic with no spread and no comparison claimed.
- **Supplementary materials** — No supplementary files are referenced in the article text and none are present in the paper directory. Recorded as not provided, which is distinct from present-but-unreadable.

## Questions for the authors

_Each of these is answerable from what the authors already have. None presupposes an error on their part: an inconsistency is far more often a reporting slip, or a mistake by this tool in reading the number off the page, than anything else._

1. Table 1 reports mean ages of 23.9 ± 5.84 years and 24.3 ± 6.33 years, while Patients and Methods describes the cohort as "Fifty-six patients in their 20s". Could you send the minimum and maximum age in each arm, so the age span of the cohort can be compared with the "wide range of patient's age" the Discussion identifies as a limitation of earlier studies?
   <sub>Would resolve: Settles whether the cohort was in fact age-homogeneous, which is the premise the study's rationale rests on, and resolves the only open tension between the prose and the printed dispersion.</sub>
2. With 3 and 2 infections in arms of 28, the expected counts in both infection cells are 2.5. The reported p = 0.639 reproduces exactly as an uncorrected Pearson chi-squared; Yates-corrected and Fisher's exact both give p = 1.0 on the same counts. Could you confirm which SPSS output the reported value was taken from, and whether an exact test was also examined?
   <sub>Would resolve: Confirms the test convention and establishes whether the small-count alternatives were considered, which the Methods sentence does not say.</sub>
3. Could you supply a confidence interval, or a risk difference with its standard error, for the comparison of 3/28 versus 2/28 infections between arms?
   <sub>Would resolve: Would let a reader see how large a difference in infection rate the trial can still exclude, which is what the conclusion that prolonged prophylaxis "may not be necessary" depends on and which the paper does not report.</sub>
4. The Discussion states "a significance level of α=0.05 and a test power β=0.20", with a smaller infection rate of 5% and an estimated difference of 30%. Could you confirm whether β=0.20 denotes the type II error rate (that is, power of 0.80), and send the calculation that produced 28 patients per group?
   <sub>Would resolve: Resolves the notation in the load-bearing sample-size sentence and would allow the stated power calculation to be reproduced, which could not be done from the values printed.</sub>

## Limitations

- This agent reads text and does not see figures. The figure pass was not run and no figure was read. Nothing was lost to that here: the paper contains no figures at all -- the XML returned no figure elements, the PDF text layer over all five pages contains no figure caption, and the only display item is Table 1.
- Table 1 is an image in the publisher XML and carries no cells, so it would have gone unchecked from that source alone. It was recovered from the PDF text layer on page 3, and every value in it is independently restated in the Results prose (both age mean/SD pairs, both sex ratios, both infection counts), so the numbers checked here are corroborated by two agreeing extractions rather than single-sourced.
- The `quote_not_located` marker fired on all 7 of the sweep's accusations. This is an instrument artefact, not a weakness in the evidence: the sweep copied its spans from the PDF text layer, which carries justification double-spaces ("Fifty-six  patients  in  their  20s") and renders the chi glyph in a private-use codepoint, so those spans cannot match the XML body text they are searched against. Every one of the seven was located verbatim in the paper on re-reading. Zero of seven was a real problem.
- GRIM could not discriminate at n = 28 with one-decimal means, so the two age means were not cleared by it -- only GRIMMER, which can discriminate here and passed both cells. A reader should not read the age row as having survived every granularity check available.
- No tool in this kit derives a confidence interval from a 2x2 count table, and none derives Cohen's h from two proportions. The two quantities that would most sharpen this review -- how large a difference in infection rate the data still permit, and what the stated power calculation actually implies -- could therefore not be computed, only described.
- This analysis reads one paper and reaches no network. Two questions a reader needs in order to weigh these findings are outside its reach entirely: whether similar patterns appear in other papers by the same authors, and how these infection rates and design choices compare with other orthognathic-surgery trials of the same period. The interpretation is partly ours and partly the reader's.
- The paper prints very few numbers -- one table of four rows, one p-value, two prose mean/SD pairs. The verification denominator is correspondingly small, which is a fact about the paper's brevity rather than about the thoroughness of the checks: nearly everything it prints was checkable and was checked.
- No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.

## Coverage

- **Statistics found:** 17; **checked:** 9
- **Tools run:** extract_xml, extract_pdf, statcheck, parse_cells_typed, recalc_chi_squared, check_summation_batch, grim_check, grimmer_check, check_sd_range, check_proportion_from_normal
- **Tables checked:** Table 1 (image-only in XML; recovered from PDF page 3 and cross-checked against the Results prose)
- **Every checkable item:** 8 registered; 0 refused with a stated reason; **8 outstanding**
    - how many were CHECKED is not measured -- no persisted item identity joins a tool call back to a manifest row, so how many items were CHECKED cannot be counted. This is not a count of zero. This is not a count of zero.
- **Stage-1 findings:** 15 raised; 8 carried into this report; 7 not carried
- **Where a check and this review disagreed:** 3 sweep findings recorded a severity the validated check behind them did not return (1 upgraded, 2 downgraded). 1 is marked on the entry above that cites it. 2 are explained downgrades on an entry above, counted here and not marked there: the check said more, this review said less and said why, which is what stage 2 is for.
- **Traceable to the page:** 20 of 20 checks recorded the passage their numbers were read from; 19 of those were located in the paper's own text.
- **1 quoted passage is ours, not the paper's.** Every number in it was found in the paper, but the sentence around those numbers was assembled by this review and does not appear as written -- so do not search the PDF for it. The CHECK is sourced; only the quotation marks over-promise.

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

This is a small single-centre trial from Yonsei University asking whether prophylactic antibiotics need to be continued after orthognathic surgery. Fifty-six young patients undergoing Le Fort I osteotomy with bilateral intraoral vertical ramus osteotomy, all operated on by the same surgeon, were randomised by Excel-generated codes to receive a single 1.0 g preoperative dose of cefpiramide alone, or the same dose plus twice-daily cefpiramide to the third postoperative day. Surgical site infections were assessed at two weeks against CDC criteria. Three infections occurred in the experimental arm and two in the control arm, and the authors conclude that prolonged prophylaxis may not be necessary.

## What the checks bought

The arithmetic here is clean, and the cleanliness is worth stating precisely rather than in the aggregate. The paper's single inferential result reproduces exactly from the counts it prints: the 2x2 of 3/28 against 2/28 gives Pearson chi-squared of 0.2196 on one degree of freedom and p = 0.639339, against the printed p = 0.639. Every count reconciles with exact tolerance -- the sex counts against each arm (16 + 12 = 28, 14 + 14 = 28), the arms against the stated total (28 + 28 = 56), and the per-arm infections against the five patients narrated individually in the Results (3 + 2 = 5). Both age mean/SD pairs are reconstructible from integer ages at n = 28: valid sum and sum-of-squares combinations exist for 23.9 ± 5.84 and for 24.3 ± 6.33. That is what a carefully prepared paper looks like, and on a paper this short it is close to everything there was to check.

One qualification a reader is owed: the age means were not cleared by every available check. GRIM has no resolution at n = 28 with one decimal place, so it could not have caught anything there and correctly returned no verdict. GRIMMER, which can discriminate at these values, passed both.

## Where the trouble is, and where it is not

Nothing in this paper contradicts anything else in it. The open questions are all about what the result can be made to support.

The central one is that a conclusion of "no difference" is drawn from an event count of three against two. The paper is more forthcoming than most about how it was sized -- it states plainly that it targeted a contrast between a 5% and a 35% infection rate -- and that candour is what makes the problem legible. A trial built for a 30-percentage-point gap has essentially no purchase on the differences that would actually change clinical practice, and the paper reports no interval, no risk difference and no effect size that would tell a reader which differences remain live. The point estimate recoverable from the counts is an odds ratio of 1.56, pointing weakly toward more infection in the arm that received fewer antibiotics -- the opposite of the conclusion's direction, though on five events in total that is noise rather than signal. It cannot be given an interval here because no tool in this kit derives one from a 2x2 table, and that limitation is ours to own.

The test choice compounds this rather than causing it. Expected counts of 2.5 per infection cell are half what the chi-squared approximation conventionally wants, and the exact alternatives appropriate at these counts both return p = 1.0. The conclusion is unaffected in direction under every convention, so this makes the figure 0.639 falsely precise rather than wrong -- and uncorrected chi-squared on small 2x2 tables was ordinary practice in 2008. It is also worth noting that the paper reports neither the chi-squared statistic nor its degrees of freedom, so its one confirmatory claim was recoverable only because Table 1 happens to print patient counts rather than percentages.

Two design points belong beside these. The trial was randomised but not masked -- the paper says so directly, which is to its credit -- and two of the four CDC criteria it adopts are assessor-judged, with the assessment made by the surgeon who performed every operation and knew each allocation. And the study motivates itself by criticising earlier work for a "wide range of patient's age", while printing no age range of its own; its dispersion figures sit awkwardly with the phrase "in their 20s", though a lopsided age distribution would reconcile both without any reporting error, and the arithmetic of those figures checks out. I have graded that last point as unresolved rather than as a defect, because the paper is simply silent on the question and the innocent reading is at least as natural as the alternative.

A note on one thing I did not do. The sweep flagged both age standard deviations as exceeding what an age band of 20 to 29 permits. That band is a translation of prose, not a range the paper prints, and a bound the reviewer supplies can invert this kind of check rather than merely weaken it. It has been capped accordingly and is reported as an open question about missing information, not as an anomaly in the numbers.

The reported statistics in this paper verify against each other. What warrants caution is not the arithmetic but the strength of the inference drawn from five events.

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
