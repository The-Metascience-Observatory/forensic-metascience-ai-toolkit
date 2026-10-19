# Forensic review -- von Wild KRH et al. 2017

*Analysed 2026-09-02 15:21 UTC  ·  pipeline v1.15.0 (gadbfa7b37b71, uncommitted changes)*

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## New Aspects of Graft-induced Central Plasticity and Neuroregeneration at T 10 in a Rat Model
*von Wild KRH, Catoi C, Tobias von Wild, Giorgio Brunelli, Dafin Muresanu, Peter Trillenberg, Marc Heidbreder, Laura Farcas, Adrian F Gal, Marian A Taulescu, Alexandru I Gudea, Johannes C Vester, Marlene Löhnhardt. Journal of Neurology & Neurophysiology. 2017. doi:10.4172/2155-9562.1000450*

**Design:** randomized double-blind placebo-controlled experimental study in rat

<sub>Analysed as `paper`</sub>

> **HIGHLY SUSPICIOUS** — Table 3's muscle p-values 0.4146 and 0.4936, and its Combined Wei-Lachin line (MW=0.5611, 95% CI 0.5456-0.5766, N1/N2=10/3, p<0.0001), are digit-for-digit Table 2's histology numbers, not results of the muscle tests printed beside them.
>
> **In plain terms:** The muscle table reuses the nerve-histology table's p-values and its combined 'significant' line, including a sample size that belongs to a different analysis. One pasted p-value says 'not significant' while that row's own interval already rules out no difference.
>
> **Evidence:** Table 3 Muscle Marlene p=0.4146 (N1/N2=16/5, MW=0.6250) and Muscle Catoi p=0.4936 (N1/N2=11/2, MW=0.8182, 95% CI 0.5578 to 1.0000); Table 2 NNTXDIAM p=0.4146 and NNTXAREA p=0.4936; both Combined rows MW=0.5611, 95% CI 0.5456-0.5766, N1/N2=10/3, p<0.0001.
> **Rests on:** logical necessity (no assumption added)

**Verdict: does not reconcile** (confidence: high)

_The paper's own numbers contradict one another, and the contradiction reaches a result the paper depends on. This is a statement about the arithmetic as printed. It is not a finding of misconduct, and the commonest cause of it is a reporting or transcription error._

## What the authors shared

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

1 study/studies, 10 variables, 12 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| s1 | Rat T10 sural-nerve-graft RCT, Cerebrolysin vs NaCl vs nil | rct | 30 | rat | no |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| treatment group | nominal | discrete | Cerebrolysin (CERE); NaCl 0.9% sham; controls (nil) | - | measured (coin-flip randomization plus identified controls, unblinded years later as 12/11/7) | percentage GRIM on cell counts | high |
| compound muscle action potential present at 2nd Op | nominal | discrete | positive (stimulus yes); negative (stimulus no) | - | measured (intraoperative CMAP of IOAM / PNG) | DEBIT; percentage GRIM | high |
| Mann-Whitney effect size on histometric nerve measures | interval | continuous | 0-1 | P(X<Y)+0.5P(X=Y) | other: Wei-Lachin / Wilcoxon-Mann-Whitney on NNTXDIAM, AREA, AXON, MYELIN, MIN, MAX, TOTAL, CUMUL | percentage GRIM | medium |
| IOAM muscle fibre diameter | ratio | continuous | range not stated | µm, also as percent of contralateral | measured (histometric count by ML (Luebeck) and CC (Cluj)) | none -- not integer-valued | high |
| axonal regeneration/sprouting grade | ordinal | discrete | 0 none; 1 mild (1-20 axons/HPF); 2 moderate (21-50); 3 intense (>50) | - | mean of items: mean over at least 10 HPF from serial slides | percentage GRIM on cell counts | high |
| angiogenesis grade in/around SNG | ordinal | discrete | 0 none; 1 mild (1 microvessel/HPF); 2 moderate (2-3); 3 intense (>3) | - | mean of items: mean over HPF | percentage GRIM on cell counts | high |
| Gitter cell grade | ordinal | discrete | 0-3 (integers) | - | mean of items: mean Gc/HPF | percentage GRIM on cell counts | high |
| nerve-graft insertion depth | ratio | continuous | range not stated | mm | measured (histology of SNG position) | none -- not integer-valued | high |
| body weight at enrolment | ratio | continuous | 220-280 | g | measured (Charles River Sprague Dawley, 220 to 280 g) | none -- not integer-valued | high |
| Fast Blue labelled spinal neurons | nominal | discrete | not stated | - | measured (fluorescence microscopy of SC sections) | GRIM (needs stated max) | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Table 2, NNTXDIAM | mann_whitney | Mann-Whitney effect size on histometric nerve measures (proportion) | - | 13 | none | none reported |
| Table 2, NNTXAREA | mann_whitney | Mann-Whitney effect size on histometric nerve measures (proportion) | - | 13 | none | none reported |
| Table 2, NNTXAXON | mann_whitney | Mann-Whitney effect size on histometric nerve measures (proportion) | - | 13 | none | none reported |
| Table 2, NNTXMYELIN | mann_whitney | Mann-Whitney effect size on histometric nerve measures (proportion) | - | 13 | none | none reported |
| Table 2, NNTXMIN | mann_whitney | Mann-Whitney effect size on histometric nerve measures (proportion) | - | 13 | none | none reported |
| Table 2, NNTXMAX | mann_whitney | Mann-Whitney effect size on histometric nerve measures (proportion) | - | 13 | none | none reported |
| Table 2, NNTXTOTAL | mann_whitney | Mann-Whitney effect size on histometric nerve measures (proportion) | - | 13 | none | none reported |
| Table 2, NNTXCUMUL | mann_whitney | Mann-Whitney effect size on histometric nerve measures (proportion) | - | 13 | none | none reported |
| Table 2, Combined (Wei-Lachin) | other | Mann-Whitney effect size on histometric nerve measures (proportion) | - | 13 | none | none reported |
| Table 3, Muscle Marlene | mann_whitney | IOAM muscle fibre diameter (continuous) | - | 21 | none | none reported |
| Table 3, Muscle Catoi | mann_whitney | IOAM muscle fibre diameter (continuous) | - | 13 | none | none reported |
| Table 3, Combined (Wei-Lachin) | other | IOAM muscle fibre diameter (continuous) | - | 13 | none | none reported |

_12 of 12 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. Table 3 muscle p-values and Combined row are Table 2's histology numbers  [HIGHLY SUSPICIOUS | confidence: high]

**In plain terms.** The muscle results table reuses the nerve-histology table's p-values and its combined 'significant' line, right down to a 10-versus-3 sample size that is not the muscle rows' 16-versus-5 or 11-versus-2. For one muscle comparison the printed interval already excludes no difference, so that comparison would be significant, but the pasted p-value says it is not. The likely slip is a copied figure template; as printed, Table 3 does not report the muscle tests it names.

- **Location:** Table 3 versus Table 2
- **Reported:** Table 3 Muscle Marlene: MW=0.6250, 95% CI 0.3993 to 0.8507, N1/N2=16/5, p=0.4146. Muscle Catoi: MW=0.8182, 95% CI 0.5578 to 1.0000, N1/N2=11/2, p=0.4936. Combined (Wei-Lachin): MW=0.5611, 95% CI 0.5456 to 0.5766, N1/N2=10/3, p<0.0001. Table 2 NNTXDIAM p=0.4146 and NNTXAREA p=0.4936; Table 2 Combined is the same MW, CI, N1/N2 and p as Table 3 Combined.
- **Computed:** detect_duplication: two identical (0.4146, 0.4936) and (0.5611, 0.5456) pairs across Table 2 and Table 3 (coincidence probability about 1.6e-13). grimu_check: p=0.4146 matches no U for 16 versus 5 (nearest U=29.5 p=0.409, U=30 p=0.4328); p=0.4936 matches no U for 11 versus 2 (nearest U=7 p=0.4897 and 0.5128). check_estimate_ci on Muscle Catoi: CI excludes the Mann-Whitney null of 0.5 while p=0.4936 is not significant (recovered Wald p=0.0048; lower bound 0.5578 does not depend on the truncated upper bound of 1.0000). Table 3 Combined MW=0.5611 with N1/N2=10/3 lies below both printed muscle MWs (0.6250 and 0.8182) and does not use 16/5 or 11/2.
- **As printed in the paper:** **Table 2 and Table 3 Combined (Wei-Lachin) rows** -- “The combined result of the histological assessments shows significant superiority of the 'stimulus yes' group of animals versus the 'stimulus no' group (MW=0.5611, 95%CI 0.5456-0.5766” _(found in the PDF text layer)_
- **Assumptions:** Table 2 (nerve histometrics) and Table 3 (muscle fibre diameter) are different outcome families, so identical p-values, Combined MW/CI and N1/N2 are not a legitimate reuse of one analysis. Muscle fibre diameter is a continuous micrometre measure, so the GRIM-U lattice is the untied one. Mann-Whitney null is 0.5 as implied by the paper's MW definition P(X<Y)+0.5P(X=Y). The modal innocent cause is a forest-plot template copied from Table 2 into Table 3 without recomputing.
- **Whose standard:** logic or arithmetic. The paper contradicts itself, or the arithmetic does not work. Nothing outside the document is needed to see it.
- **Consequence:** changes a significance decision; 1 stated claim affected -- Table 3's Combined p<0.0001 is Table 2's histology combination, not a combination of the muscle rows; Muscle Catoi's own interval excludes 0.5 while the pasted p=0.4936 is non-significant. (asserted, not computed)

### 2. NNTXMAX interval excludes no difference while p=0.9017 does not  [SUSPICIOUS | confidence: high]

**In plain terms.** For one nerve-fibre measure the authors print an interval that already rules out no difference, which at their stated 5% threshold would be a significant result, and a p-value of 0.9017 that says the opposite. Those two numbers cannot both describe the same test.

- **Location:** Table 2, NNTXMAX row
- **Reported:** NNTXMAX MW=0.8000, 95% CI 0.5362 to 1.0000, N1/N2=10/3, p=0.9017. Methods: alpha=0.05 and two-sided 95% CIs.
- **Computed:** check_estimate_ci: CI excludes the null of 0.5 while reported p=0.9017 is not significant; recovered Wald p=0.0112 (upper bound truncated at 1.0000, so that recovered p is not a trustworthy point estimate). The printed lower bound 0.5362>0.5 does not depend on that truncation. grimu_check: p=0.9017 matches no U for 10 versus 3 (nearest U=13.5 p=0.8658, U=14 p=0.9326), which is the p of a near-null rank sum, not of MW=0.8000.
- **As printed in the paper:** **Table 2, NNTXMAX row** -- “| NNTXMAX | | 0,8000 | (0,5362 to 1,0000) | 10 / 3 | 0,9017 |” _(found in the paper's text)_
- **Assumptions:** The paper's MW null is 0.5. A two-sided 95% CI that does not contain 0.5 and a two-sided p>0.05 cannot both be from the same test of that null. Wald inversion of a CI truncated at 1.0 is not used as the primary evidence; the printed lower bound is. Interval construction is not named beyond 'two-sided 95% CI' of the Mann-Whitney statistic, so an exact or bootstrap interval remains an open innocent reading for the recovered Wald p, not for the lower bound versus 0.5.
- **Whose standard:** the paper's own promise. The paper promised this itself -- a guideline it claims to follow, its registration, its stated outcomes or thresholds. We are holding it to its own word.
- **Consequence:** changes a significance decision; 1 stated claim affected -- This component would be significant at the paper's alpha=0.05 if the printed 95% CI is believed, but the printed p=0.9017 is not. (asserted, not computed)

### 3. Day-90 n and CMAP-positive counts do not agree across Abstract, Results, figures and Table 4  [SUSPICIOUS | confidence: high]

**In plain terms.** The authors never settle how many rats reached the day-90 operation (16 in the abstract, 21 in the Results) or how many had a positive muscle signal (eight in the abstract and Results, eight of 16 on one figure, seven of 14 in the Discussion, seven plus-cases in Table 4). The only significant combined test is run as 10 versus 3, which matches none of those splits. The Results death tally adds up on its own; the abstract's 16 does not.

- **Location:** Abstract; Results, Surgery; Figure 4 caption; Discussion after Figure 12; Table 4; Table 2 N1/N2
- **Reported:** Abstract: 2nd Op at day 90 in 16 surviving rats; eight rats showed positive CMAPs. Results: 21 rats underwent the 2nd Op; electro-stimulation of the PNG transplant in 21 rats was positive in only 8 rats. Figure 4: 8 of 16 rats. Discussion after Figure 12: 7 out of the 14 surviving animals. Table 4 lists seven (+) cases and ten (−) cases. Table 2 Combined and components use N1/N2=10/3.
- **Computed:** Stage-1 check_summation_batch: randomized 12+11+7=30, completers 5+7+3=15, and the Results early-death addends summing to 9 are internally additive (30−9=21). Abstract 16 is not that cascade. Table 4 7+10=17; tissues from No 21 and No 28 (died at the 2nd Op) are said to have been saved, which can explain 15+2=17 rows but not 8 versus 7 positives. Table 2's 10/3 matches none of 8 vs 8, 8 vs 13, 7 vs 10, or 16 vs 5.
- **As printed in the paper:** “2nd Op at day 90 (16 surviving rats) for open proof of reinnervation” _(found in the paper's text)_
- **Assumptions:** Stimulus yes versus no is the grouping for Tables 2 and 3. Completer identities in Results (15 named animals) plus saved 2nd-Op deaths (No 21, 28) are the paper's own accounting. Direct check_summation was denied at this stage; additive identities are taken from Stage-1 check_summation_batch, which found those identities consistent.
- **Whose standard:** logic or arithmetic. The paper contradicts itself, or the arithmetic does not work. Nothing outside the document is needed to see it.
- **Consequence:** 1 stated claim affected -- Stimulus yes versus no is the grouping for the paper's only significant combined test, but the paper never pins down how many animals were yes. (asserted, not computed)

### 4. Vecuronium dose is 0.04–0.05 mg/kg in Table 1 and 80 µg/kg in Figure 5  [SUSPICIOUS | confidence: high]

**In plain terms.** The drug used to show mixed nerve-to-muscle signalling is given as 0.04 to 0.05 milligrams per kilogram in the dosing table and as 80 micrograms per kilogram on the figure, which is 0.08 milligrams per kilogram. Those are not the same dose.

- **Location:** Table 1, Vecuronium row versus Figure 5 caption
- **Reported:** Table 1: Vecuronium 0.04 - 0.05 mg/kg IV. Figure 5: Vecuronium IV (80 µg/kg). Four CMAP-positive rats received it.
- **Computed:** check_ratio: 80/1000=0.08, so 80 µg/kg is 0.08 mg/kg, which sits outside Table 1's 0.04-0.05 mg/kg range. Equivalently, Table 1's range is 40-50 µg/kg.
- **As printed in the paper:** “Vecuronium ® IV (80 µg/kg) application during artificial ventilation” _(found in the paper's text)_
- **Assumptions:** 1000 µg=1 mg is a unit identity, not a scale the paper had to state. The two printed doses are different quantities; four CMAP-positive rats are the subset that received the drug.
- **Whose standard:** logic or arithmetic. The paper contradicts itself, or the arithmetic does not work. Nothing outside the document is needed to see it.
- **Consequence:** 1 stated claim affected -- Vecuronium response is the functional proof offered for mixed cholinergic/glutamatergic transmission; the dose used is not a single printed number. (asserted, not computed)

### 5. None of Table 2's eight component p-values is a Mann-Whitney p for 10 versus 3 animals  [SUSPICIOUS | confidence: high]

**In plain terms.** The eight individual nerve-fibre p-values are presented as rank-sum tests on 10 versus 3 animals, but none of those eight numbers is a p-value that a rank-sum test on 10 versus 3 can produce. Two rows even share the same effect size and the same interval yet print different p-values. These component tests were all called non-significant, so the mismatch does not flip those calls; it means the printed p-column is not the test the methods describe.

- **Location:** Table 2, P column
- **Reported:** Eight component rows at N1/N2=10/3 with p=0.4146, 0.4936, 0.1928, 0.1020, 0.7533, 0.9017, 0.2347, 0.3505, attributed to the Wilcoxon-Mann-Whitney / Wei-Lachin family. NNTXDIAM and NNTXAREA share MW=0.4000 and 95% CI 0.0704 to 0.7296 but not the same p. NNTXTOTAL MW=0.5667, 95% CI 0.2855 to 0.8479, p=0.2347.
- **Computed:** grimu_coexistence: 8 of 8 p-values individually flagged; none matches an achievable U under exact, normal, or continuity-corrected conventions; no pairwise co-existence violation; floor p exact=0.00699; 45 achievable p-values at 4 dp. One-sided re-run of p=0.4146 also unmatched. check_estimate_ci on NNTXTOTAL (interval symmetric about the printed MW, so not truncated): recovered p=0.642 versus printed 0.2347. Shared NNTXDIAM/NNTXAREA CI recovers Wald p=0.552, which matches neither printed p.
- **As printed in the paper:** **Table 2, NNTXTOTAL row** -- “| NNTXTOTAL | | 0,5667 | (0,2855 to 0,8479) | 10 / 3 | 0,2347 |” _(found in the paper's text)_
- **Assumptions:** The paper attributes these p-values to Wilcoxon-Mann-Whitney tests at the printed 10/3. Diameter, area, myelin and related histometrics are continuous, so the default is no ties; a tie-corrected lattice was not used. Rule 12 caps a granularity miss at suspicious. Rank-sum packages can shift a p in the fourth decimal; they do not print eight unachievable values. Different tie corrections could split two p-values but would not be expected to leave MW and the 95% CI identical to four decimals.
- **Whose standard:** the paper's own promise. The paper promised this itself -- a guideline it claims to follow, its registration, its stated outcomes or thresholds. We are holding it to its own word.
- **Consequence:** changes no significance decision -- All eight component tests remain non-significant under the printed p-values; the lattice misses do not flip those NS calls. (asserted, not computed)

### 6. EMG-positive angiogenesis scores of '2 and 3' versus Table 4 case 6 scored 1  [SUSPICIOUS | confidence: medium]

**In plain terms.** The authors say EMG-positive animals had only angiogenesis scores of 2 and 3, averaging 2.57, but Table 4 gives case 6, which is EMG-positive, a score of 1. The EMG-negative average of 1.3 does match that table. This is a descriptive contrast, not a hypothesis test.

- **Location:** Figure 9 caption versus Table 4, case 6 ang cell
- **Reported:** Angiogenesis was more intense in EMG-positive cases (individual final scores of 2 and 3; score average 2.57) than in EMG-negative cases (individual final scores of 1 and 2; score average 1.3). Table 4 case 6 (+) lists ang (1); case 28 (+) has no ang grade printed. Methods grade angiogenesis 0-3.
- **Computed:** check_ratio: EMG-negative average 1.3 follows from Table 4 grades summing to 13 over 10 cases. grim_check: mean 2.57 is attainable at n=7 on a 0-3 integer scale (18/7=2.57). Stage-1: no combination of the printed positive ang grades (2, 1, 3, 3, 2, 3) averages to 2.57. Case 6 (+) scored 1 contradicts 'individual final scores of 2 and 3'.
- **As printed in the paper:** “was more intense in EMG-positive cases (individual final scores of 2 and 3; score average 2.57) than in EMG-negative cases (individual final scores of 1 and 2; score average 1.3)” _(found in the paper's text)_
- **Assumptions:** Table 4 integer ang grades are the 'individual final scores' the caption describes. n=7 for GRIM is the count of (+) cases in Table 4, which the caption does not print beside 2.57. Final scores are means over high-power fields, so 2.57 could in principle be a mean of means rather than an average of integer grades; the caption's 'individual final scores of 2 and 3' is what collides with case 6.
- **Whose standard:** logic or arithmetic. The paper contradicts itself, or the arithmetic does not work. Nothing outside the document is needed to see it.
- **Consequence:** changes no significance decision -- A descriptive contrast of angiogenesis by EMG group, not a hypothesis test. (asserted, not computed)

### 7. Methods specify a two-sided test; table captions specify a directional test  [INDETERMINATE | confidence: high]

**In plain terms.** The methods say tests were two-sided; the table captions say the combined test was directional. The printed p-values do not match either version of a 10-versus-3 rank-sum test, so a reader cannot tell which rule was used.

- **Location:** Statistical Methods versus Table 2/3 captions and Statistical Evaluation
- **Reported:** Methods: 'The level of alpha was defined as alpha=0.05, and a two-sided test was used for superiority' and 'two-sided 95% confidence intervals'. Table 3 caption and Statistical Evaluation: 'Wei-Lachin procedure, directional test, exploratory interpretation.'
- **Computed:** grimu_check one-sided on p=0.4146 at 10 versus 3 still unmatched. Which tail produced the p-column is not recoverable, because those p-values miss both the two-sided and one-sided 10-versus-3 lattices.
- **As printed in the paper:** “The level of alpha was defined as alpha=0.05, and a two-sided test was used for superiority.” _(found in the paper's text)_
- **Assumptions:** The paper also labels the analysis exploratory and warns about small n. Both phrases cannot be the procedure that produced the p-column; the printed p-values do not adjudicate which phrase was used.
- **Whose standard:** logic or arithmetic. The paper contradicts itself, or the arithmetic does not work. Nothing outside the document is needed to see it.

## What we could NOT check

- **Figure 12 muscle-fibre-diameter chart** — extract_figures was denied; group averages appear only as black squares on the figure and are not printed as numbers in the caption. Values needed for effect-size reconstruction of the CERE versus NaCl/nil contrast are unread.
- **CONSORT-style flow** — check_flow_arithmetic was denied. Additive identities were checked with Stage-1 check_summation_batch; the abstract-versus-results n clash is reported from the two quoted counts.
- **Table 4 axon-diameter mean (range) and axon-count cells** — No registered tool tests whether a printed mean lies inside a printed min–max range. Fourteen mean (range) cells and associated counts were not fed to GRIM/SPRITE (continuous µm). <sub>(28 cells)</sub>
- **CERE versus NaCl/nil muscle-fibre comparison** — Authors say the CERE effect was not statistically significant but show no CI or p for that three-arm contrast. Table 3 CIs are stimulus yes/no, not treatment arm.
- **Western blot Figure 6** — Qualitative band presence/absence; no optical-density means, SDs or n printed.
- **Publisher XML / supplements** — No JATS XML and no supplementary data files were in the paper directory. Sweep used extract_pdf plus body.md. Table 1 is a drug list, not a results table.
- **Wei-Lachin combined SE versus components** — No registered tool reconstructs a Wei-Lachin multivariate standard error from component MW intervals and a correlation. Combined MW/CI/p are internally consistent on a Wald reading; whether that interval can arise from n=10/3 given the wide component intervals was not adjudicated.

## Questions for the authors

_Corresponding author: Klaus RH von Wild <kvw@neurosci.de>_

_Each of these is answerable from what the authors already have. None presupposes an error on their part: an inconsistency is far more often a reporting slip, or a mistake by this tool in reading the number off the page, than anything else._

1. Table 3 prints Muscle Marlene p=0.4146 (N1/N2=16/5, MW=0.6250) and Muscle Catoi p=0.4936 (N1/N2=11/2, MW=0.8182), which are the same digits as Table 2 NNTXDIAM and NNTXAREA, and Table 3 Combined is MW=0.5611, 95% CI 0.5456-0.5766, N1/N2=10/3, p<0.0001 — identical to Table 2 Combined. Could you send the Mann-Whitney / Wei-Lachin output actually computed for the two muscle rows and for their combination?
   <sub>Would resolve: Settles whether Table 3 is a copied forest-plot template and what the muscle tests were.</sub>
2. Table 2 NNTXMAX prints MW=0.8000, 95% CI 0.5362 to 1.0000, p=0.9017 at N1/N2=10/3. Could you send the test output that produced that p-value and interval, including the U (or equivalent) and whether the test was two-sided or directional?
   <sub>Would resolve: The interval excludes 0.5 while p=0.9017 does not, and 0.9017 is not an achievable Mann-Whitney p for 10 versus 3.</sub>
3. The abstract has 16 rats at the day-90 operation and eight positive CMAPs; Results has 21 rats at that operation and eight positives of 21; Figure 4 has 8 of 16; the Discussion has 7 of 14; Table 4 lists seven (+) and ten (−) cases; Table 2 uses 10/3. Could you send the analysis n for stimulus yes versus no used in Tables 2 and 3, and which animals were counted as CMAP-positive?
   <sub>Would resolve: The grouping for the only significant combined test is not a single printed number.</sub>
4. Table 1 lists Vecuronium 0.04-0.05 mg/kg IV and Figure 5 lists 80 µg/kg. Could you send the dose actually given to rats 19, 21, 28 and 29?
   <sub>Would resolve: The functional proof of mixed transmission uses this dose, and the two printed values are different quantities.</sub>

## What was looked at, beyond the numbers

_Three checks sit outside the arithmetic. Whether each one ran on this paper is a property of how this run was invoked, not of the paper -- and a check that did not run has cleared nothing._

- **Figures** — **did not run**. This analysis read the paper as text; figures were not inspected, so anomalies visible only in plots would not be detected.
- **Image forensics** — **did not run**. No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.
- **Tortured phrases** — **ran**. Screening for tortured phrases was limited to matching against a fixed fingerprint dictionary (tortured phrases, LLM boilerplate, tortured acronyms), computed locally. Novel or unlisted paraphrases, non-English text, and any rewording not in the dictionary were NOT checked, and their absence here is not evidence of their absence in the paper.

## Limitations

- Stage-1 quote_not_located fired on all 12 accusations. Cause: markdown table pipes and European decimal commas (0,4146) versus the PDF text layer. Every cited span was found verbatim in body.md on re-read; this is a fact about the two extractions, not about missing numbers.
- Figure images were not read (extract_figures was denied). Captions in the text layer were read for unique counts (Figure 4: 8 of 16; Figure 5: 80 µg/kg). Group-average marks on Figure 12 were not digitized.
- Direct check_summation was denied at this stage. Additive identities 12+11+7=30, 5+7+3=15, and early-death addends=9 are taken from Stage-1 check_summation_batch, which found them consistent.
- No registered tool reconstructs a Wei-Lachin multivariate standard error from component intervals. The Combined estimate, interval and p<0.0001 are internally consistent; the apparent tightness of that interval relative to the component intervals is therefore unsettleable here and was not carried as an accusation.
- No JATS XML and no deposited raw data were available. Histometric outcomes in Table 2 are continuous micrometre measures except where named as counts; GRIM was not applied to those means.
- This pipeline does not search other papers by the same authors or other studies of Brunelli-type grafting, so any interpretation of the copied Table 3 block that needs that comparison is the reader's.

## Coverage

- **Statistics found:** 72; **checked:** 58
- **Tools run:** extract_pdf, statcheck, check_estimate_ci, grimu_check, grimu_coexistence, check_summation_batch, check_count_percent, stalt_check, multiplicity_report, parse_table, parse_cells_typed, check_table, detect_duplication, check_ratio, check_statistic_bounds, absence_of_evidence, required_n, flag_round_n, grim_check
- **Tables checked:** Table 1, Table 2, Table 3, Table 4
- **Every checkable item:** 215 registered; 215 refused with a stated reason; **0 outstanding**
    - how many were CHECKED is not measured -- no persisted item identity joins a tool call back to a manifest row, so how many items were CHECKED cannot be counted. This is not a count of zero. This is not a count of zero.
- **Stage-1 findings:** 23 raised; 12 carried into this report; 11 not carried
    - 1 accusatory finding(s) were dropped, each with a stated reason
- **Traceable to the page:** 72 of 72 checks recorded the passage their numbers were read from; 69 of those were located in the paper's own text.
- **1 quoted passage is ours, not the paper's.** Every number in it was found in the paper, but the sentence around those numbers was assembled by this review and does not appear as written -- so do not search the PDF for it. The CHECK is sourced; only the quotation marks over-promise.
- **2 quoted passages could not be found in the text we read.** That is most often our extraction or our search, not the authors -- treat those checks as unsourced.

## Narrative

This study randomises 30 rats to Cerebrolysin, saline, or no injection after a T10 sural-nerve graft into the internal oblique, and asks whether the graft reinnervates muscle with mixed cholinergic and glutamatergic transmission. The only statistically significant test the authors report is a Wei-Lachin combination of histometric nerve measures comparing 'stimulus yes' with 'stimulus no' (MW=0.5611, 95% CI 0.5456-0.5766, p<0.0001). They call the analysis exploratory, skip multiplicity adjustment, and warn about small samples.

Twenty of the thirty-four checks that ran on printed values passed. The randomisation split 12+11+7 sums to 30, the completers 5+7+3 sum to 15, 15 deaths among 30 print as 50%, all eleven Mann-Whitney point estimates sit inside their printed intervals, and the Combined estimate, interval and p<0.0001 agree with one another on a Wald reading. That is the part that holds.

What does not hold is the rest of those same tables, and it reaches the result the paper depends on. Table 3 is offered as muscle-fibre evidence of reinnervation. Its first two p-values are Table 2's first two p-values, and its Combined line is Table 2's Combined line, including N1/N2=10/3 rather than the muscle rows' 16/5 and 11/2. Table 3's caption even describes 'the combined result of the two histological assessments' while sitting on a muscle table. The ordinary reading is a forest-plot template reused without recomputing. As printed, Table 3 does not report the muscle tests it names. Muscle Catoi's own interval already excludes no difference (lower bound 0.5578), so that comparison would be significant at the authors' 5% threshold; the pasted p=0.4936 is not. A rank-sum p of 0.4146 is also not a possible value for 16 versus 5 animals, nor is 0.4936 possible for 11 versus 2.

The source table is not internally coherent either. None of the eight Table 2 component p-values is an achievable Mann-Whitney p for 10 versus 3 animals, two-sided or one-sided. Rank-sum software can move a p in the fourth decimal; it does not emit eight unachievable values. Two rows share MW=0.4000 and the same 95% CI to four decimals yet print different p-values. NNTXMAX's interval starts at 0.5362, which already excludes 0.5, while p=0.9017 does not. NNTXTOTAL's interval is symmetric about its MW and recovers p≈0.642 against a printed 0.2347. Methods promise two-sided tests and two-sided 95% CIs of the Mann-Whitney statistic; the captions say 'directional test'. The printed p-values miss both lattices, so the tail convention cannot be recovered from the numbers.

The grouping for the Combined test is never one number. The abstract has 16 rats at the day-90 operation and eight positive muscle signals; Results has 21 rats at that operation and eight positives of 21; one figure has 8 of 16; the Discussion has 7 of 14; Table 4 lists seven plus-cases and ten minus-cases. Table 2's 10 versus 3 matches none of those splits. Results' own death cascade adds up (nine early deaths, 30−9=21, then six further deaths to 15 completers); the abstract's 16 does not. Tissues saved from two animals that died at revision can explain Table 4's 17 rows. They cannot explain eight versus seven positives.

Two lesser inconsistencies sit outside those tables. Vecuronium, used as functional proof of mixed transmission, is 0.04-0.05 mg/kg in the dosing table and 80 µg/kg (0.08 mg/kg) on the figure. Angiogenesis is said to average 2.57 in EMG-positive cases with individual scores of only 2 and 3, but Table 4 scores EMG-positive case 6 as 1; the EMG-negative average 1.3 does match that table.

The Combined Wei-Lachin interval is internally consistent with p<0.0001. Whether an interval that tight can come from n=10/3 given the wide component intervals is a question this toolkit cannot settle, and it is not treated as an accusation. The descriptive surgical and histological narrative is a different kind of evidence and is not what these checks speak to.

I have no confidence in the accuracy of the statistical tables as printed.

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

### `check_ratio` — absolute

Checks that a printed ratio follows from the numerator and denominator printed with it.

**What its verdict means.** Absolute (possible vs impossible). Exact arithmetic over the printed values and their rounding intervals. Subject to the preconditions below, a flagged result cannot be produced by any dataset.

**Strongest verdict it may reach:** `impossible`

**It assumes:**
- The printed precision of all three values must be read off the literals; the attainable interval is computed at the corners of that rounding box, and a guessed precision either clears every ratio or accuses on rounding alone.
- Assumes the ratio was computed from the two values as printed. Papers routinely divide unrounded intermediates they never show, or a discounted or subgroup quantity, which is why the verdict is capped at `suspicious` and never reaches `impossible` despite the arithmetic being exact.
- A denominator whose own rounding interval spans zero makes the quotient unbounded; the check refuses rather than compares.
- Across a TABLE, the evidence is not any single row but several rows implying DIFFERENT values for a quantity that can only have one -- read `implied_denominator`.

### `check_statistic_bounds` — absolute

Checks a value against the range its measure permits BY DEFINITION -- and treats a violation as evidence about our extraction before evidence about the paper.

**What its verdict means.** Absolute (possible vs impossible). Exact arithmetic over the printed values and their rounding intervals. Subject to the preconditions below, a flagged result cannot be produced by any dataset.

**Strongest verdict it may reach:** `impossible`

**It assumes:**
- The bound is logically necessary, never conventional: a correlation is bounded by Cauchy-Schwarz, a p-value by the definition of a probability. A merely expected range is an assumption, and unknown measures are refused rather than judged against our expectations.
- The value reached us intact. This is the assumption the whole tool is built around distrusting: a decimal-point slip or a value read from the wrong column produces exactly this signature, and is far likelier than a paper printing a correlation of 11.3.
- GREG'S PRIOR, 2026-08-11, and the reason for the ordering: gross violations are uncommon even in fraudulent papers, because fabricators produce plausible numbers. So an unverified violation caps at `indeterminate` with failure_mode `extraction_suspect` -- a flag on OUR reading, explicitly not a finding.
- `impossible` requires `extraction_verified`, meaning the value was re-read in the paper itself and both the digits and the column confirmed. Verification is the price of the accusation; the escape is evidential, not the model's discretion.
- Even when verified, the tool names the innocent readings -- a typesetting error, a mislabelled row -- because a confirmed impossible value still does not establish who produced it.

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

### `grimu_check` — absolute

Checks a Mann-Whitney p against the finite set achievable at these group sizes.

**What its verdict means.** Absolute (possible vs impossible). Exact arithmetic over the printed values and their rounding intervals. Subject to the preconditions below, a flagged result cannot be produced by any dataset.

**Strongest verdict it may reach:** `impossible`

**It assumes:**
- The p must genuinely come from a Mann-Whitney U / Wilcoxon rank-sum test at these group sizes.
- The achievable set spans the normal approximation with and without continuity correction, plus the exact permutation p.
- KNOWN LIMITATION: the TIE-CORRECTED variance that scipy and R use on tied data is NOT in that set, so a correctly reported p from tied data can fall below the modelled floor. Treat an `impossible` verdict on data with heavy ties as unproven until checked against the R implementation.
- Pass one_sided for one-tailed reports. `decimals` is read from the printed literal; from a bare float it falls back to that float's shortest round-tripping decimal form, which is a LOWER bound on the printed precision, so the interval can only widen. A float carrying float-noise precision is refused rather than guessed at.

### `grimu_coexistence` — absolute

Flags near-identical Mann-Whitney p-values that cannot all arise at these group sizes.

**What its verdict means.** Absolute (possible vs impossible). Exact arithmetic over the printed values and their rounding intervals. Subject to the preconditions below, a flagged result cannot be produced by any dataset.

**Strongest verdict it may reach:** `impossible`

**It assumes:**
- All the p-values must come from Mann-Whitney tests on the SAME group sizes.
- Pass one_sided if the paper reports one-tailed tests; forcing the two-sided set manufactures accusations.
- Same tie-correction limitation as grimu_check: heavy ties can put an honest p outside the modelled set.

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

- **Analysed:** 2026-09-02 15:21 UTC
- **Pipeline version:** v1.15.0 (gadbfa7b37b71, uncommitted changes)
- **LLM backend:** grok (grok 1.0.13 (5e9a58528b76) [stable])
- **Sandbox:** Grok's `search_tool` cannot be denied: it is the only route to the forensic MCP tools. This run's sandbox is weaker than a Claude run's.
- **Prompts:** 161c6d7ed4d52b7e
- **Tool registry:** 0b06c178cea5ee68
- **Models:** grok-4.6, grok-4.6-build (editorial); grok-4.6, grok-4.6-build (sweep)
- **Reasoning effort:** high

_Two reviews are directly comparable only if the pipeline version, the prompt hash and the registry hash all match. The version alone is not sufficient: it moves about once a month, while the prompts and the tool registry move several times a day, so a difference between two runs stamped with the same version may be a change in this toolkit rather than a fact about the papers._
