# Forensic review -- Sharma et al. 2023

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## RETRACTED ARTICLE: Cerebrolysin Attenuates Exacerbation of Neuropathic Pain, Blood-spinal Cord Barrier Breakdown and Cord Pathology Following Chronic Intoxication of Engineered Ag, Cu or Al (50–60 nm) Nanoparticles
*Hari Shanker Sharma, Lianyuan Feng, Lin Chen, Hongyun Huang, Z Ryan Tian, Ala Nozari, Dafin F Muresanu, José Vicente Lafuente, Rudy J Castellani, Lars Wiklund, Aruna Sharma. Neurochemical Research. 2023. doi:10.1007/s11064-023-03861-8*

**Design:** Controlled laboratory experiment in rats (chronic constriction nerve-lesion model of neuropathic pain), 18 non-randomised experimental groups compared against a single control group; ANOVA followed by Dunnett's test. NOTE: the version of record carries 'RETRACTED ARTICLE' in its title.

<sub>Analysed as `10.1007--s11064-023-03861-8`</sub>

> **HIGHLY SUSPICIOUS** — Five significance decisions in the paper's two behavioural/physiological tables contradict the group means and standard deviations printed beside them: four asterisked cells cannot reach p < 0.05 under any standard test, and one comparison the text calls "not significantly altered" has a p-value below 0.002.
>
> **In plain terms:** The paper marks certain measurements with a star to say they differ significantly from the untreated control animals. For four of those starred results, the averages and spreads printed in the same row are simply too close together for any standard statistical test to declare a difference -- no matter which of the permitted group sizes or rounding you assume. Separately, one comparison the authors describe in words as showing no significant difference is in fact a large, clearly significant difference by the same arithmetic. The errors run in both directions, which means the pattern of stars in these tables cannot be reproduced from the paper's own data.
>
> **Evidence:** Table 2, Respiration cycle/min: Control "14 ± 3"; Nerve Lesion 4 wk "12 ± 9*"; Nerve Lesion 10 wk "12 ± 8*"; §CBL + NL + Al 10 wk "16 ± 6*". Table 3, Paw Withdrawal Latency (Sec): Control "6 ± 3"; NL + Al NPs 10 wk "4 ± 5*". Footnotes define "*P < 0.05 ... from control group" and "Values are Mean ± SD of 6–8 rats at each point." Taking n = 8 per group (the top of the paper's own stated range, the assumption most favourable to the authors) and allowing every rounding of the printed integers, the achievable two-tailed p-intervals are [0.354, 0.786], [0.301, 0.765], [0.182, 0.709] and [0.122, 0.672] respectively; the one-tailed intervals are [0.177, 0.393], [0.151, 0.383], [0.091, 0.355] and [0.061, 0.336]. Conversely Table 2, Arterial pH: Control "7.38 ± 0.04" versus NL + Ag NPs 10 wk "7.23 ± 0.06" (no asterisk), against the Results sentence "the values were not significantly altered (Table 2)"; at n = 6 per group the entire achievable p-interval is [0.00013, 0.00194].
> **Rests on:** a constraint the paper itself states
> **Reproduce:** no runnable command -- the review's command did not match the tool's arguments. The finding's own numbers are above; re-derive from those.

**Verdict: untrustworthy** (confidence: high)

> **Table coverage:** 0 of 525 checkable cells were checked cell by cell, and 32 further table rows were checked in batch by check_summation_batch. The two counts are of different things and are not added: the batch tools report rows, not the cell identifiers this census uses, so the true combined coverage is somewhere between 32 and 32 of 525. A further 18 per-cell checks ran (`check_summation`, `detect_duplication`, `rivets_independent_t`) and report no cell ids at all, so the top of that range is a floor rather than a ceiling.

## Provenance of the analysis

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

1 study/studies, 22 variables, 18 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| S1 | Rat chronic constriction nerve-lesion study with Ag/Cu/Al nanoparticle intoxication and cerebrolysin treatment | unknown | 348 | individual rat | no |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Body weight | ratio | continuous | range not stated | g | measured | none -- not integer-valued | high |
| Rectal temperature | interval | continuous | range not stated | degrees C | measured | none -- not integer-valued | high |
| Mean arterial blood pressure (MABP) | ratio | continuous | range not stated | Torr | measured | none -- not integer-valued | high |
| Arterial pH | interval | continuous | range not stated | - | measured | none -- not integer-valued | high |
| Arterial oxygen tension (PaO2) | ratio | continuous | range not stated | Torr | measured | none -- not integer-valued | high |
| Arterial carbon dioxide tension (PaCO2) | ratio | continuous | range not stated | Torr | measured | none -- not integer-valued | high |
| Heart rate | ratio | continuous | range not stated | beats/min | measured | none -- not integer-valued | medium |
| Respiration rate | ratio | continuous | range not stated | cycles/min | measured | none -- not integer-valued | medium |
| Von Frey mechanical hind paw stimulation withdrawal weight | ratio | continuous | range not stated | g | measured | none -- not integer-valued | high |
| Paw withdrawal latency | ratio | continuous | range not stated | seconds | measured | none -- not integer-valued | high |
| Tail flick latency to radiant heat (52 degrees C) | ratio | continuous | range not stated | seconds | measured | none -- not integer-valued | high |
| Evans blue albumin extravasation across the BSCB | ratio | continuous | range not stated | mg % | measured | none -- not integer-valued | high |
| [131]-Iodine extravasation across the BSCB | ratio | continuous | range not stated | % | measured | none -- not integer-valued | high |
| Spinal cord water content | ratio | continuous | 0-100 | % | percentage: wet vs dry cord weight | percentage GRIM | high |
| Spinal cord volume swelling | ratio | continuous | range not stated | %f | other: 'calculated from the changes of water content as described earlier' -- the paper cites a prior method but never states the transformation formula, so the mapping from water content to volume swelling cannot be reproduced | none -- not integer-valued | medium |
| Spinal cord albumin by ELISA | ratio | continuous | range not stated | µg/mg | measured | none -- not integer-valued | high |
| Spinal cord glial fibrillary acidic protein by ELISA | ratio | continuous | range not stated | pg/mg | measured | none -- not integer-valued | high |
| Spinal cord myelin basic protein by ELISA | ratio | continuous | range not stated | ng/mg | measured | none -- not integer-valued | high |
| Spinal cord heat shock protein 72 kD by ELISA | ratio | continuous | range not stated | ng/mg | measured | none -- not integer-valued | high |
| Spinal cord TNF-alpha, IL-6, IL-10 and IL-4 concentrations | ratio | continuous | range not stated | pg/mg protein | measured | none -- not integer-valued | high |
| Count of injured/distorted neurons per spinal segment | ratio | discrete | range not stated | - | other: counted by 3 independent observers, median across observers taken | GRIM (needs stated max) | high |
| Number of rats allocated per group per assay stream (Table 1) | ratio | discrete | range not stated | - | measured | GRIM (needs stated max) | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Table 2, Respiration cycle/min, Nerve Lesion 4 wk vs Control | one_way_anova | Respiration rate (continuous) | nerve lesion duration | 16 | none | none reported |
| Table 2, Respiration cycle/min, Nerve Lesion 10 wk vs Control | one_way_anova | Respiration rate (continuous) | - | 16 | none | none reported |
| Table 2, Respiration cycle/min, §CBL + NL + Al 10 wk vs Control | one_way_anova | Respiration rate (continuous) | - | 16 | none | none reported |
| Table 2, Respiration cycle/min, NL + Al NPs 8 wk vs Control | one_way_anova | Respiration rate (continuous) | - | 16 | none | none reported |
| Table 2, Body wt (g), #CBL + NL 10 wk vs Control | one_way_anova | Body weight (continuous) | - | 16 | none | none reported |
| Table 2, Arterial pH, NL + Ag NPs 10 wk vs Control (reported as NOT significant) | one_way_anova | Arterial pH (continuous) | - | 12 | none | none reported |
| Table 3, Paw Withdrawal Latency, §CBL + NL + Ag 10 wk vs Control | one_way_anova | Paw withdrawal latency (continuous) | - | 16 | none | none reported |
| Table 3, Paw Withdrawal Latency, NL + Al NPs 10 wk vs Control | one_way_anova | Paw withdrawal latency (continuous) | - | 16 | none | none reported |
| Table 3, Von Frey withdrawal weight column: 17 group-vs-control comparisons (14 starred) | one_way_anova | Von Frey mechanical hind paw stimulation withdrawal weight (continuous) | - | ? | none | none reported |
| Table 3, Paw Withdrawal Latency column: 17 group-vs-control comparisons (11 starred) | one_way_anova | Paw withdrawal latency (continuous) | - | ? | none | none reported |
| Table 3, Tail Flick Latency column: 17 group-vs-control comparisons (16 starred) | one_way_anova | Tail flick latency to radiant heat (52 degrees C) (continuous) | - | ? | none | none reported |
| Table 2, all 8 physiological variables x 17 non-control groups = 136 group-vs-control comparisons | one_way_anova | ? | - | ? | none | none reported |
| Table 4, EBA / [131]-Iodine / water content (6 measured columns) x 17 non-control groups = 102 group-vs-control comparisons | one_way_anova | ? | - | ? | none | none reported |
| Table 5, albumin/GFAP/MBP/HSP (8 columns) x 14 non-control groups = 112 group-vs-control comparisons | one_way_anova | ? | - | ? | none | none reported |
| Table 6, TNF-alpha/IL-6/IL-10/IL-4 (8 columns) x 14 non-control groups = 112 group-vs-control comparisons | one_way_anova | ? | - | ? | none | none reported |
| Figure 2, neuronal injury counts in T10/T12/L5 across control, NL and NP groups at 4/8/10 wk (values plotted only) | one_way_anova | Count of injured/distorted neurons per spinal segment (count) | - | ? | none | none reported |
| Figure 5, albumin-positive immunoreactive cell counts in T10/T12/L5 (values plotted only) | one_way_anova | ? | - | ? | none | none reported |
| Figure 8, GFAP-positive immunoreactive cell counts in T10/T12/L5 (values plotted only) | one_way_anova | ? | - | ? | none | none reported |

#### Variable/test mismatches

A parametric test is applied to an outcome this analysis typed as non-continuous. That is not proof of an error -- the typing may be wrong, and some parametric tests are robust -- but each pair below should be checked against the paper.

- **Figure 2, neuronal injury counts in T10/T12/L5 across control, NL and NP groups at 4/8/10 wk (values plotted only)**: `one_way_anova` assumes a continuous, roughly normal outcome, but **Count of injured/distorted neurons per spinal segment** is typed `count`.

_18 of 18 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. Four asterisked comparisons whose p < 0.05 is unreachable from the means and SDs printed beside them  [HIGHLY SUSPICIOUS | confidence: high]

**In plain terms.** Four results are flagged in the tables as statistically significant differences from the untreated animals. When you take the averages and the spread of values the authors themselves printed in those same rows, and give them every benefit of the doubt about group size and rounding, no standard test can produce a significant result -- the calculated likelihood of chance is between roughly 12% and 79%, where under 5% is required. One of these is a headline pain measurement the paper's main conclusion rests on, and another is a claimed benefit of the drug being tested.

- **Location:** Table 2 (Respiration cycle/min: Nerve Lesion 4 wk, Nerve Lesion 10 wk, §CBL + NL + Al 10 wk) and Table 3 (Paw Withdrawal Latency: NL + Al NPs 10 wk), each against the Control row
- **Reported:** Table 2 Control respiration 14 ± 3; NL 4 wk 12 ± 9*; NL 10 wk 12 ± 8*; §CBL + NL + Al 10 wk 16 ± 6*. Table 3 Control paw withdrawal latency 6 ± 3; NL + Al NPs 10 wk 4 ± 5*. Footnote: "*P < 0.05 ... from control group, ANOVA followed by Dunnett's test for multiple group comparison from one group."
- **Computed:** At n = 8 per group and allowing every rounding of the printed 0-decimal means and SDs, the achievable two-tailed p-intervals are [0.354, 0.786], [0.301, 0.765], [0.182, 0.709] and [0.122, 0.672]; one-tailed [0.177, 0.393], [0.151, 0.383], [0.091, 0.355] and [0.061, 0.336]. p = 0.05 lies outside every interval under Welch's and Student's tests, one- and two-tailed. All four returned severity `highly_suspicious` with the verdict "Reported p bound = 0.05 is UNREACHABLE".
- **As printed in the paper:** “Values are Mean ± SD of 6–8 rats at each point.” _(found in the paper's text)_
- **Assumptions:** n = 8 per group, the TOP of the paper's own stated range "6–8 rats at each point" and the value most favourable to the authors' significance claim; at n = 6 every p would be larger still. The rounding intervals follow from the paper's own footnote that "the values are adjusted to nearest numbers". The paper states its analysis was ANOVA followed by Dunnett's test, which is more conservative than the unadjusted t-tests recomputed here, so the discrepancy can only widen under the authors' own method. No external bound was supplied.
- **Consequence:** changes a significance decision; 4 stated claims affected -- One of the four is a primary pain outcome underpinning the abstract's hyperalgesia claim (paw-withdrawal latency worsened by aluminium nanoparticles at 10 weeks), one is a cerebrolysin-treatment claim ("Al nanoparticles showed significant increase in cerebrolysin treated nerve lesioned group"), and one supports the Results sentence "Respiration rate after nerve lesion in saline treated rats showed significant decrease after 10 weeks". (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command did not match the tool's arguments. The finding's own numbers are above; re-derive from those.

### 2. Arterial pH difference declared non-significant in the Results while its own printed values imply p below 0.002  [HIGHLY SUSPICIOUS | confidence: high]

**In plain terms.** The paper says in words that blood acidity did not change meaningfully in any group. But the numbers it prints in its own table show the nerve-injured animals given silver nanoparticles at 10 weeks had a blood pH of 7.23 against 7.38 in controls -- a difference so large relative to the spread of values that the chance of it arising randomly is under one in five hundred, at the group size most favourable to the authors' claim. This is a real and clinically meaningful shift toward acid blood that the paper reports as no change.

- **Location:** Results, Physiological Variables paragraph, against Table 2 Arterial pH (Control vs NL + Ag NPs 10 wk)
- **Reported:** "The arterial pH exhibited slight decrease in nerve lesioned group with or without nanoparticles intoxication; however, the values were not significantly altered (Table 2)." Table 2 prints Control 7.38 ± 0.04 and NL + Ag NPs 10 wk 7.23 ± 0.06, with no significance marker on the latter.
- **Computed:** At n = 6 per group the recomputed t is 5.10 at the printed values, with the whole achievable interval running t ∈ [4.34, 6.01] and p ∈ [0.00013, 0.00194] across every admissible rounding, under both Welch's and Student's tests. The entire interval lies below 0.002 -- roughly 25-fold below the paper's own alpha of 0.05.
- **Assumptions:** n = 6 per group, the BOTTOM of the stated "6–8 rats" range and the value most favourable to the authors' claim of no difference; at n = 8 the p-values would be smaller still. Rounding intervals taken from the printed 2-decimal precision. Note the direction of triage: the tool's own aggregate label for this call was `suspicious`, awarded on its heuristic that the t-interval is wide and the exact statistic cannot be pinned down; that heuristic is about precision, not about the non-significance claim. The substantive point is separate and is read off the same tool output -- the whole achievable interval sits below the paper's alpha -- so this finding is recorded one band higher than the tool's own label, and the reason is stated here rather than hidden.
- **Consequence:** changes a significance decision; 1 stated claim affected -- The Results sentence stating arterial pH was "not significantly altered" is contradicted by Table 2's own means and SDs; a fall from pH 7.38 to 7.23 is a marked acidosis reported by the paper as absent. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command did not match the tool's arguments. The finding's own numbers are above; re-derive from those.

### 3. Three mutually irreconcilable animal totals in Table 1: 348 stated, 362 in the cells, 368 in the row totals  [SUSPICIOUS | confidence: high]

**In plain terms.** The paper says 348 rats were used. Its own allocation table gives two other answers: adding up the individual entries gives 362 animals, and adding up the table's own per-group subtotals gives 368. Three group subtotals are each two animals larger than the entries they are supposed to add up, and two column totals are 8 and 6 animals smaller than the entries above them. These are whole animals, so there is no rounding that could explain the gaps -- at least some of the printed figures must be wrong, and the study's headline sample size cannot be recovered from the table meant to define it.

- **Location:** Table 1 (Experimental Protocol in Nerve Lesion), Materials and Methods; and the Animals section
- **Reported:** "Experiments were carried out on 348 male albino Wistar Rats". Table 1's printed Grand Total row reads 106 / 112 / 130 / 348. Three per-group row totals read 22, 22 and 24 against cells of 6+6+8, 6+6+8 and 8+6+8.
- **Computed:** Exact integer arithmetic at tolerance 0: 6 of 7 checked sums fail. Three row totals over-state their own cells by exactly 2 each (printed 22 vs 20; 22 vs 20; 24 vs 22). Two column Grand Totals under-state the cells above them -- the Physiological/Pain/Morphological column sums to 114 against a printed 106 (difference 8), and BSCB & Edema sums to 118 against a printed 112 (difference 6). The Biochemical Analyses column reconciles exactly at 130. The 18 printed per-group Total values sum to 368 against the stated 348 (difference 20), while the individual cells sum to 362. The printed grand total of 348 is arithmetically consistent only with the three (incorrect) column totals, not with the animals actually listed.
- **As printed in the paper:** “Experiments were carried out on 348 male albino Wistar Rats” _(found in the paper's text)_
- **Assumptions:** None beyond the paper's own statements. Animal counts must hold exactly, so the tolerance was set to zero rather than to a rounding window; every input is an integer read directly from the table. The row errors are all +2 in the same direction, which is more consistent with a transcription or typesetting slip than with a random arithmetic error -- but it is the sample size of the whole study, and no printed figure reconciles with any other.
- **Consequence:** changes no significance decision; 3 stated claims affected -- The number of animals contributing to the physiological/pain tables and to the barrier tables is stated two ways differing by 8 and 6 respectively, and the per-group n that every significance test in Tables 2-6 depends on cannot be pinned down for three groups. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command did not match the tool's arguments. The finding's own numbers are above; re-derive from those.

### 4. Descriptive statistics deliberately rounded to whole numbers, leaving most significance claims unadjudicable  [SUSPICIOUS | confidence: high]

**In plain terms.** The authors state they rounded all their averages and spreads to whole numbers "for simplicity". A whole-number average of 4 could be anything from 3.5 to 4.5, and that uncertainty is large enough that for six further starred results the underlying test could plausibly have come out either significant or not -- there is no way to tell from what is printed. One claimed effect on body weight only reaches significance if an unstated one-sided test was used at the largest permitted group size. None of these is evidence of an error; they are results the paper does not give a reader enough information to check.

- **Location:** Footnotes to Tables 2, 3, 4, 5 and 6; Table 2 (Body wt, Respiration) and Table 3 (Von Frey, Paw Withdrawal) cells
- **Reported:** Every results-table footnote states: "Values are Mean ± SD of 6–8 rats at each point. For simplicity, the values are adjusted to nearest numbers." Consequently Table 2 prints respiration as "14 ± 3", "16 ± 3*", and Table 3 prints paw withdrawal latency as "6 ± 3", "4 ± 3*".
- **Computed:** For Table 2's §CBL+NL+Al 8 wk respiration (16 ± 3* vs 14 ± 3) and Table 3's §CBL+NL+Ag 10 wk paw withdrawal (4 ± 3* vs 6 ± 3), the achievable two-tailed p-interval across the rounding box is [0.031, 0.577] with a point value of 0.204 -- reachable but not pinned, so the asterisk is neither confirmed nor refuted. For Table 2's #CBL + NL 10 wk body weight (274 ± 8* vs 267 ± 8) the smallest achievable two-tailed p is 0.051, so that asterisk is reachable only under a one-tailed test the paper never states it used, and only at the extreme corner of the rounding box at n = 8. Running the whole of Table 3 through the table dispatcher typed all 54 cells correctly as mean ± SD and then ran zero checks on them: 0 of 54, because the outcomes are continuous and no cell carries its own n.
- **As printed in the paper:** **Table 3 (Von Frey / paw withdrawal / tail flick), all 54 printed cells** -- “Values are Mean ± SD of 6–8 rats at each point. For simplicity, the values are adjusted to nearest numbers.” _(found in the paper's text)_
- **Assumptions:** n = 8 per group where a significance claim was tested. The rounding intervals follow directly from the paper's own statement that values were adjusted to the nearest whole number; no bound was invented. Rounding to integers is a legitimate presentational choice and is not itself an error -- the consequence, not the practice, is what is reported here.
- **Consequence:** 6 stated claims affected -- Six further asterisked comparisons in Tables 2 and 3 can be neither confirmed nor refuted from the printed precision, so the pain and cerebrolysin claims resting on them are unverifiable rather than demonstrably wrong. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command did not match the tool's arguments. The finding's own numbers are above; re-derive from those.

### 5. Twenty-six animals allocated to biochemical analysis in the aluminium groups, with no aluminium data in either biochemical table  [SUSPICIOUS | confidence: high]  ⚠ not backed by a sweep finding

**In plain terms.** The study's own protocol table sets aside 26 rats for laboratory protein and inflammation measurements in the aluminium-nanoparticle groups. Neither of the two tables reporting those measurements contains an aluminium group at all. The summary at the front of the paper describes these biochemical effects as being worsened by nanoparticles after listing all three metals, but only silver and copper were actually measured, so no data in the paper supports that part of the statement for aluminium.

- **Location:** Table 1 (rows F. Nerve Lesion+Al-NPs 4/8/10 wk and G. Nerve Lesion + Al-NPs 5 ml, Biochemical Analyses column) against Tables 5 and 6
- **Reported:** Table 1's Biochemical Analyses column allocates 6, 6, 6 and 8 animals to the four aluminium-nanoparticle groups. Tables 5 and 6 contain only Control, Sham, Nerve Lesion, #CBL + NL, NL + Ag NPs, §CBL + NL + Ag, NL + Cu NPs and §CBL + NL + Cu rows; both captions read "...intoxication with Ag and Cu nanoparticle...". The abstract nonetheless states that ELISA showed albumin, GFAP, MBP, HSP 72kD and the four cytokines were elevated "in nerve lesion that was exacerbated following NPs intoxication", having named Ag, Cu and Al as the nanoparticles studied.
- **Computed:** Summation of the four Al-group Biochemical Analyses allocations: 6 + 6 + 6 + 8 = 26 animals, consistent (tolerance 0). No aluminium row exists anywhere in Table 5 (20 rows) or Table 6 (20 rows), so none of those 26 animals contributes a reported biochemical value.
- **Assumptions:** None beyond the paper's own statements. The reading rests on Table 1's own column heading ("Biochemical Analyses") matching the content of Tables 5 and 6 (ELISA protein and cytokine measurements), which is how the Methods describe the biochemical stream. It is possible the aluminium biochemistry was run and simply not reported, or that the Table 1 allocation is aspirational; either explanation is ordinary, and the point is that the paper does not say which.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The abstract's biochemical claim is stated for nanoparticle intoxication generally after naming all three metals, but only silver and copper were measured, so the aluminium part of that claim has no supporting data in the paper. (asserted, not computed)
- **Reproduce:** `metascience get-table /mnt/c/Users/gregs/agent_for_forensic_metascience/cerebrolysin_run_2026-08-09/10.1007--s11064-023-03861-8/10.1007--s11064-023-03861-8.xml 5`

### 6. Five unreadable numerals and a corrupted sample-size footnote in the published barrier and biochemical tables  [SUSPICIOUS | confidence: high]

**In plain terms.** Five numbers in the published tables are printed with the wrong character in the middle -- a dash where the decimal point should be, or an accent mark where the plus-or-minus sign should be -- so they cannot be read as numbers at all. A footnote that should say the values come from "6-8 rats" has lost the 6, so that table no longer states its own group sizes. These same errors appear in both the publisher's structured text and its PDF, so they are in the published article rather than introduced by our reading of it.

- **Location:** Table 4 ([131]-Iodine and Water content columns) and Table 5 (Albumin and HSP columns, and the Table 5 footnote)
- **Reported:** Table 4: "2–16 ± 0.42**" (NL+Ag 8 wk, iodine T10-11); "1.84´0.33**" (NL+Al 10 wk, iodine T10-11); "65.63´0.34*#" (CBL+NL+Al 10 wk, water content L5-S2). Table 5: "3.28 ± 1–14**" (NL+Ag 8 wk, albumin L5-S2); "24.59´2.08**" (NL+Ag 4 wk, HSP L5-S2). Table 5 footnote: "Values are Mean ± SD of–8 rats at each point."
- **Computed:** Five data cells and one footnote are malformed in the version of record. Two cells print an en-dash where a decimal point belongs ("2–16" for what must be 2.16; "1–14" for 1.14) and three print an acute accent where the ± belongs. The Table 5 footnote has lost the "6" that the other four table footnotes print, leaving the sample size of that whole table undefined. I re-read Table 5's cells and footnote directly from the publisher XML and confirmed all three defects there; Stage 1 additionally reconciled the XML against PDF pages 7 and 8 and found the two sources agree exactly on all six, so these are defects in the published article and not artefacts of extraction.
- **As printed in the paper:** “1.98 ± 0.43** 1.86 ± 0.33** 2–16 ± 0.42** 2.23 ± 0.44**” _(found in the PDF text layer)_
- **Our check returned a different severity.** The `reconcile` check returned `indeterminate` for the sweep finding `corrupted_numerals_in_data_cells`, which this review recorded as `suspicious`. This entry asserts more than the check established, so read it as this review's judgement and not as a computed result. The finding states a reason.
- **Assumptions:** None. The reconstruction of "2–16" as 2.16 and "1–14" as 1.14 is inference from the surrounding column values and is offered as the likely intent, not as an established value; the point of the finding is that the printed characters cannot be read as numbers at all. Two of the five affected cells are SD values, so no dispersion-based check can be run on them.
- **Consequence:** changes no significance decision; 5 stated claims affected -- Five reported measurements behind starred comparisons in the barrier and biochemical tables cannot be read as numbers by any reader or re-analyst, and Table 5's footnote no longer states how many animals its values came from. (asserted, not computed)
- **Reproduce:** `metascience get-table /mnt/c/Users/gregs/agent_for_forensic_metascience/cerebrolysin_run_2026-08-09/10.1007--s11064-023-03861-8/10.1007--s11064-023-03861-8.xml 4`

### 7. Figure 8 legend, the only description of the GFAP result, states the panel shows albumin leakage  [SUSPICIOUS | confidence: high]

**In plain terms.** Figure 8 is supposed to show counts of cells stained for one particular brain protein. Its caption opens by saying so, then describes the effect being plotted as leakage of a completely different protein -- wording copied from the caption of an earlier figure. Because the caption is the only place in the paper that explains what this figure measures, a reader cannot be sure which of the two proteins the graph actually shows.

- **Location:** Figure 8 caption
- **Reported:** "Upper panel: Graphic representation of glial fibrillary acidic protein (GFAP) positive immunoreactive cells... Treatment with nanoparticles (NPs) Cu or Ag (50–60 nm) exacerbated albumin leakage at 4, 8 or 10 weeks from the nerve lesioned group significantly." The same caption prints "CBK 5 ml/kg, i.v." for CBL.
- **Computed:** The sentence describing the plotted effect is the wording of the Figure 5 legend, which really is the albumin figure. Figure 8 is defined by its own caption as GFAP immunoreactivity, and that caption is the only place the plotted quantities are described -- the values appear in no table and nowhere in the body text.
- **As printed in the paper:** “Treatment with nanoparticles (NPs) Cu or Ag (50–60 nm) exacerbated albumin leakage at 4, 8 or 10 weeks from the nerve lesioned group significantly.” _(found in the paper's text)_
- **Assumptions:** None beyond comparison of the Figure 5 and Figure 8 captions as printed. This is duplicated boilerplate, the most ordinary of copy-editing errors, and no arithmetic claim is made. Its weight comes only from the fact that the legend is load-bearing: nothing else in the paper says what Figure 8 plots.
- **Consequence:** changes no significance decision; 1 stated claim affected -- The only description of what Figure 8 plots names the wrong protein, so the GFAP cell-count result cannot be interpreted with confidence from the paper as published. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command used an option this tool does not have. The finding's own numbers are above; re-derive from those.

### 8. Control and sham tail-flick latencies of 60 and 64 seconds to a 52 °C radiant heat stimulus  [SUSPICIOUS | confidence: medium]

**In plain terms.** In the heat-sensitivity test, healthy control animals are recorded as taking 60 seconds -- and sham-operated animals 64 seconds -- to flick their tail away from a hot stimulus. In this standard test, normal animals respond within a few seconds, and researchers usually stop the test after 10 to 15 seconds specifically to avoid burning the animal. Injured animals in the same column respond in 2 to 4 seconds. The most likely explanation is a units or transcription error rather than anything about the underlying experiment, but as printed the numbers do not describe the test the paper says it ran. Note this judgement uses an outside benchmark: the paper itself never states a cut-off time.

- **Location:** Table 3, "Radiant heat thermal stimulation of tail — Tail Latency (Sec) 52 °C", Control and Sham rows
- **Reported:** Control "60 ± 3"; Sham "64 ± 2"; Nerve Lesion 10 wk "4 ± 3*"; NL + Ag NPs 10 wk "2 ± 3*". Caption specifies a "thermal radiant heat stimulus (52 °C)".
- **Computed:** No forensic arithmetic applies; this is a domain-plausibility observation and is recorded as such rather than dressed up as a computation. Normal rat tail-flick latency to a radiant stimulus of roughly 52 °C is a few seconds, and cut-off times of about 10-15 seconds are conventional precisely to prevent tissue injury. A 60-64 second latency would mean uninjured animals held their tails in a noxious stimulus for a full minute. The internal contrast is also extreme: nerve-lesioned animals in the same column reach 2-4 seconds, a 15- to 30-fold range that such an assay does not normally span.
- **As printed in the paper:** “Control 15 ± 2 6 ± 3 60 ± 3” _(found in the PDF text layer)_
- **Assumptions:** ASSUMPTION-DEPENDENT and named as such. The paper states no cut-off time, so this rests on an external benchmark not given in the paper: conventional rat tail-flick baselines and cut-offs from the thermal nociception literature. Under rulebook rule 4 an assumption-dependent finding is capped at `suspicious`, cannot be the headline, and no impossibility is claimed. A units or transcription error (for example deciseconds printed as seconds, or a different stimulus intensity than the one stated) would explain the values benignly and is the likeliest cause.
- **Consequence:** changes no significance decision -- If the control tail-flick latencies are mis-scaled or mis-transcribed, the size of the thermal hyperalgesia effect the abstract reports is not interpretable in the stated units, though the direction of the effect is unaffected. (asserted, not computed)
- **Reproduce:** `metascience get-table /mnt/c/Users/gregs/agent_for_forensic_metascience/cerebrolysin_run_2026-08-09/10.1007--s11064-023-03861-8/10.1007--s11064-023-03861-8.xml 3`

### 9. Identical mean and standard deviation for rectal temperature and arterial CO2 in the same Table 2 row  [SUSPICIOUS | confidence: medium]

**In plain terms.** In one row of the physiology table, the animals' body temperature and their blood carbon dioxide level are printed with exactly the same average and exactly the same spread, to two decimal places -- despite being entirely different things measured in different units. These two quantities happen to fall in a similar numeric range, so this can happen by chance; our estimate is roughly a 3% chance across all the comparisons available in that table. It is worth a query about how the table was assembled, not a conclusion about the study.

- **Location:** Table 2, NL + Cu NPs 10 wk row: Rectal T °C and PaCO2 Torr cells
- **Reported:** Rectal T °C "36.89 ± 0.54"; PaCO2 Torr "36.89 ± 0.54*" -- a body temperature in degrees Celsius and an arterial carbon dioxide tension in Torr, matching to two decimals on both the mean and the spread.
- **Computed:** Comparing the rectal temperature and PaCO2 columns as two 18-cell blocks yields 306 pairwise comparisons and exactly one identical (mean, SD) pair, at a corrected coincidence probability of 0.034. This is materially weaker than the 0.00011 the Stage-1 sweep reported: that figure came from a span model fitted to all eight physiological variables at once, which understates how much these two particular columns overlap. Re-running the check scoped to only the two columns that actually share the 35-37 numeric range is the honest test, and it is the number quoted here.
- **As printed in the paper:** “36.89 ± 0.54” _(found in a table)_
- **Assumptions:** The two cells describe the same animals (the same table row), so this is not a case of independent samples matching; it is two different physical quantities on one group of rats. The value is not round, so the round-number discount does not apply. A coincidence probability of 0.034 for one pair among 306 comparisons is a weak signal, and coincidence remains a plausible explanation alongside a typesetting or copy-paste slip. Per rulebook rule 11 this is capped at `suspicious`; duplication is improbable, never impossible.
- **Consequence:** changes no significance decision -- Neither value carries a claim in the paper's argument; the relevance is to the provenance of the Table 2 numbers generally, not to any conclusion. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command did not match the tool's arguments. The finding's own numbers are above; re-derive from those.

### 10. Data availability statement directing enquiries to the authors, with no deposited data or supplementary files  [SUSPICIOUS | confidence: high]

**In plain terms.** The paper does not make its data available; it says to ask the authors. That is an accepted convention and not by itself a problem. It matters here only because the underlying animal-by-animal measurements are exactly what would settle every discrepancy described above, and they are not obtainable from the published article.

- **Location:** Data Availability and Data Availability Statement sections
- **Reported:** "Enquiries about data availability should be directed to the authors." Funders listed include the Air Force Office of Scientific Research, NIH R01 AG028679, the Swedish Medical Research Council and EverNeuroPharma.
- **Computed:** No repository, accession number or supplementary data file is named for a 348-animal study supported by multiple public funders and by the manufacturer of the tested compound. No supplementary materials of any kind accompany the article, so no participant-level duplication analysis could be attempted.
- **As printed in the paper:** “Enquiries about data availability should be directed to the authors.” _(found in the paper's text)_
- **Assumptions:** None. This is a weak signal on its own and is recorded as such; directing enquiries to authors was a common and accepted convention. Its relevance here is specific: the per-animal values would settle the Table 1 accounting and every unreachable-p asterisk at once, and they are the one thing that could.
- **Consequence:** changes no significance decision -- None of the numeric discrepancies identified in this review can be resolved by a reader, because the underlying data are not available. (asserted, not computed)
- **Reproduce:** no runnable command -- the review's command used an option this tool does not have. The finding's own numbers are above; re-derive from those.

### 11. Several hundred group-versus-control comparisons reported only as asterisks, with no test statistic, degrees of freedom or exact p anywhere  [INDETERMINATE | confidence: high]

**In plain terms.** Statistics papers normally print the numbers behind each test so a reader can check them. This paper prints none -- no test values, no measures of sample structure, no exact probabilities. Every one of roughly five hundred comparisons is communicated by a star next to a number. That makes direct checking impossible; everything in this review had to be worked backwards from the averages instead. It also means there is no way to tell how many of those five hundred results would still count as significant once you account for the sheer number of comparisons being made against the same control group.

- **Location:** Statistical Treatment section; Tables 2-6; Figures 2, 5 and 8
- **Reported:** "ANOVA followed by Dunnett's test for multiple group comparison was done using one control group using commercial software StatView 5 (Abacus Concept, USA)... A p-value less than 0.05 was considered significant." Every result is carried by "*P < 0.05; **P < 0.01 from control group, #P < 0.05 from Nerve lesion".
- **Computed:** An automated NHST extraction over all 25 PDF pages recovered zero test statistics: the paper contains no F, no t, no degrees of freedom and no exact p-value anywhere. Multiplicity arithmetic could not be run either -- all 51 Table 3 comparisons submitted were dropped because their p-values are thresholds rather than values, leaving 0 evaluable tests, so no family-wise error rate and no count of claims lost to correction can be computed. The scale, from the sweep's own enumeration of the table dimensions, is on the order of 500 group-versus-control comparisons against a single shared control (Table 2: 8 variables × 17 groups; Table 3: 3 × 17; Table 4: 6 × 17; Tables 5 and 6: 8 × 14 each), plus three figure panels. The stated Dunnett's adjustment operates only within a single measure's ANOVA -- it does not span the eight variables of Table 2, the three measures of Table 3, or the five tables.
- **As printed in the paper:** **Table 3 footnote; family = 17 non-control groups x 3 pain measures** -- “*P &lt; 0.05; **P &lt; 0.01 from control group, #P &lt; 0.05 from Nerve lesion, ANOVA followed by Dunnett’s test for multiple group comparison from one group.” _(found in the paper's text)_
- **Assumptions:** None. `indeterminate` here is a refusal, not a pass: nothing could be verified by direct recalculation, which is why every check in this review had to go the longer route of reconstructing tests from the group descriptives. The multiplicity tool's refusal to coerce thresholded p-values is deliberate and is the correct behaviour; the consequence is simply that the question cannot be answered from what is printed.
- **Reproduce:** no runnable command -- the review's command used an option this tool does not have. The finding's own numbers are above; re-derive from those.

### 12. Retracted status of the version of record, with the retraction notice not among the supplied files  [INDETERMINATE | confidence: high]

**In plain terms.** The published version of this article carries the word RETRACTED in its title, meaning the journal has withdrawn it. The notice explaining why was not provided to us, so we do not know the publisher's reasons, and nothing in this review is based on them. Everything above was worked out from the article's own numbers.

- **Location:** Article title in the version of record (JATS XML article-meta and PDF)
- **Reported:** "RETRACTED ARTICLE: Cerebrolysin Attenuates Exacerbation of Neuropathic Pain, Blood-spinal Cord Barrier Breakdown and Cord Pathology Following Chronic Intoxication of Engineered Ag, Cu or Al (50–60 nm) Nanoparticles"
- **Computed:** Contextual metadata, not a forensic result. The publisher's stated grounds for retraction are unknown to this review; the notice itself was not among the supplied files.
- **Assumptions:** None. Nothing in this review reconstructs, endorses or is derived from the publisher's grounds. Every finding above was computed independently from the paper's own printed numbers and stands or falls on its own; the retraction is recorded because it bears on how the paper should be cited, not because it evidences anything checked here.
- **Reproduce:** no runnable command -- the review's command crashed when run. The finding's own numbers are above; re-derive from those.

## What we could NOT check

- **Figures 2, 5 and 8 (neuronal injury counts, albumin-positive cell counts, GFAP-positive cell counts)** — These three figures carry group means, SDs and significance markers for 6-8 rats per point that appear nowhere in the text or in any table. They are the sole source for the neuronal-injury, albumin-immunoreactivity and GFAP-immunoreactivity results, and each supports a claim made in the abstract. Figure extraction was not run and no values were digitised. Anything read off these plots would carry figure-pixel provenance and would in any case be barred from the granularity checks. This is a real hole in coverage, not a formality: a substantial block of the paper's inferential claims was not examined at all.
- **Remaining starred comparisons in Tables 2, 4, 5 and 6 (on the order of 450 cells)** — Twelve comparisons were reconstructed individually, chosen as those with the smallest mean differences relative to their SDs -- i.e. where a significance claim was most likely to be unsupportable. The rest were not recalculated. The four unreachable-p results should be read as a FLOOR on the number of unsupportable asterisks in this paper, established by a targeted rather than exhaustive search, not as a count of them.
- **Table 4, Volume Swelling (%f) columns (T10-11 and L5-S2), all rows** — Volume swelling is derived: "volume swelling (%ƒ) was calculated from the changes of water content as described earlier". The paper cites a prior method but never states the transformation, so the mapping from the water-content column to the swelling column is not reproducible from anything printed here. Checking it would require assuming a conversion factor the paper does not give. The column also carries no SDs and no significance markers.
- **Tables 2, 4, 5 and 6 -- per-cell granularity checks (GRIM, GRIMMER, SPRITE, DEBIT)** — Correctly inapplicable and not run. Every variable in these tables is a continuous physiological or biochemical measure, which bars the integer-data granularity family outright; applying it would manufacture impossibilities out of ordinary measurements. Every footnote also states n only as a range ("6-8 rats at each point"), which bars the dispersion checks too. The dispatcher run on Table 3 is the representative denominator: all 54 cells typed correctly as mean ± SD, and 0 of 54 checks could run.
- **Exact per-cell sample sizes throughout Tables 2-6 and Figures 2, 5, 8** — The paper states n only as "6-8 rats at each point", and Table 5's footnote is corrupted to "of–8 rats". No cell carries its own n. Every significance recalculation therefore had to assume a value: n = 8 where the aim was to test a significance claim and n = 6 where the aim was to test a non-significance claim, in each case the assumption most favourable to the authors.
- **Table 2 -- reconciliation against the publisher PDF** — Stage 1 reconciled Tables 3, 4 and 5 against PDF pages 6-8 and found exact agreement with the XML, including on the corrupted cells; Table 2 was not put through that cross-check. Three of the four unreachable-p findings come from Table 2. The XML table carried no alignment warnings and its 144 cells are internally coherent, and the Table 3 finding (which was PDF-reconciled) stands independently, but the gap is recorded.
- **Baseline-similarity testing (Carlisle-Stouffer-Fisher, Table 1 dispersion)** — Deliberately not run, and this is the right call rather than an omission. These methods test whether randomised arms are more similar at baseline than allocation allows. This is a non-randomised laboratory experiment with deliberately constructed treatment groups and no baseline table of randomised arms, so the null those tests assume does not exist here and any verdict would be meaningless. Rulebook rule 1 (uniformly high baseline p-values as a red flag) has nothing to attach to in this paper.
- **Rank-sum granularity checks (GRIM-U)** — Deliberately not run. The paper attributes every comparison to ANOVA with Dunnett's test; no Mann-Whitney or Wilcoxon rank-sum test is reported anywhere. Applying GRIM-U to ANOVA p-values is the toolkit's single most likely route to a false accusation, and the gate is the analyst's, not the tool's.
- **Duplication scanning of Tables 3, 4, 5 and 6 against each other and against Table 2** — Only Table 2 was scanned. Cross-table scanning was not run because the tables report different physical quantities in different units on partly different animals (Table 1 allocates distinct animals to the physiological, barrier and biochemical streams), so a cross-table match would be hard to interpret and the span model would be less reliable still. A within-table scan of Tables 4, 5 and 6 remains a reasonable further check that was not performed.
- **Supplementary materials / animal-level data** — None are provided with the article, so the strongest available data-integrity check (raw-data duplication analysis) could not be attempted. Recorded as "not provided", which is distinct from "present but unreadable".
- **Retraction notice and its stated grounds** — The version of record is titled "RETRACTED ARTICLE" but the notice itself was not among the supplied files. The publisher's reasons are unknown to this review and no finding here is derived from or reconstructs them.
- **Discussion sections and reference list** — Read only via the whole-PDF statistical extraction, which found no test statistics anywhere in the document. Not examined line by line for citation or textual anomalies beyond the figure captions and load-bearing Results sentences reported above.
- **table rows Control, Control, Control, Sham, Sham, Sham and 48 more** — check_sd_or_se not run: check_sd_or_se needs n and this cell carries none; supply n for this row (the participants paragraph or the table footnote usually states it)

## Questions for the authors

_Each of these is answerable from what the authors already have. None presupposes an error on their part: an inconsistency is far more often a reporting slip, or a mistake by this tool in reading the number off the page, than anything else._

1. Table 1 gives three different answers for the size of the study. The stated total and the printed Grand Total cell both read 348 rats; the eighteen printed per-group Total values sum to 368; and the individual allocation cells sum to 362. Within the table, the rows "C. Nerve Lesion 8 wk" and "D. Nerve Lesion + Ag-NPs 4 wk" print a Total of 22 against cells of 6 + 6 + 8, and "E. Nerve Lesion + Cu-NPs 10 wk" prints 24 against 8 + 6 + 8; the Physiological/Pain/Morphological column prints a Grand Total of 106 against cells summing to 114, and the BSCB & Edema column prints 112 against cells summing to 118. Could you say which figures are correct and provide a corrected Table 1?
   <sub>Would resolve: Establishes the true sample size and the per-group n on which every test in Tables 2-6 depends.</sub>
2. Four cells carry an asterisk (P < 0.05 from control) that we could not reproduce from the values printed beside them: Table 2 respiration 12 ± 9 (NL 4 wk), 12 ± 8 (NL 10 wk) and 16 ± 6 (§CBL + NL + Al 10 wk) against a control of 14 ± 3; and Table 3 paw withdrawal latency 4 ± 5 (NL + Al NPs 10 wk) against a control of 6 ± 3. Taking n = 8 per group and allowing every rounding of the printed whole numbers, the smallest two-tailed p we obtain for these is 0.354, 0.301, 0.182 and 0.122. Could you provide the F statistic, degrees of freedom and exact p-value from StatView for each of these four comparisons?
   <sub>Would resolve: Would either reproduce the asterisks or identify a transcription error in the descriptives; the paper prints no test statistics anywhere, so this cannot be settled from the published article.</sub>
3. The Results state that "the arterial pH exhibited slight decrease in nerve lesioned group with or without nanoparticles intoxication; however, the values were not significantly altered (Table 2)", and no asterisk is placed on the arterial pH column. Table 2 prints a control pH of 7.38 ± 0.04 against 7.23 ± 0.06 in the NL + Ag NPs 10 wk group; at n = 6 per group we obtain p between 0.00013 and 0.0019. Could you confirm the pH values and the test result for that comparison?
   <sub>Would resolve: Resolves whether the printed pH values or the stated non-significance is in error; a fall to 7.23 would be a substantive physiological finding the paper currently reports as absent.</sub>
4. Table 1 allocates 26 rats to the "Biochemical Analyses" stream across the four aluminium-nanoparticle groups (6, 6 and 6 at 4, 8 and 10 weeks, plus 8 in the cerebrolysin 5 ml/kg group), but Tables 5 and 6 contain no aluminium rows, and both captions refer only to "Ag and Cu nanoparticle". Were the ELISA protein and cytokine measurements performed on those 26 animals, and if so could the aluminium-group values be made available?
   <sub>Would resolve: The abstract reports the biochemical effects for nanoparticle intoxication after naming all three metals; this determines whether the aluminium part of that statement has supporting data.</sub>
5. Five cells in the published tables cannot be read as numbers: Table 4 prints "2–16 ± 0.42", "1.84´0.33" and "65.63´0.34", and Table 5 prints "3.28 ± 1–14" and "24.59´2.08". The Table 5 footnote also reads "Values are Mean ± SD of–8 rats at each point", where the other four tables read "6–8 rats". Could you supply the intended values for these five cells and confirm the sample-size range for Table 5?
   <sub>Would resolve: These are five reported measurements behind starred comparisons that no reader can currently read, and one table whose group sizes are undefined as printed.</sub>

## Limitations

- FIGURES WERE NOT READ. This agent reads text and tables and does not see figures; no figure extraction pass was run on this paper. That matters more than usual here: Figures 2, 5 and 8 are the sole source of the neuronal-injury, albumin-immunoreactivity and GFAP-immunoreactivity results, each of which supports a claim in the abstract, and none of those values appears in any table or in the body text. A substantial block of this paper's inferential claims was therefore not examined.
- Every per-group sample size in this paper is given as a range ("6-8 rats at each point") rather than a value, so no test could be recomputed exactly. Each reconstruction used the end of the range most favourable to the authors' own claim -- n = 8 when testing a significance claim, n = 6 when testing a non-significance claim -- which means the reported discrepancies are conservative and would widen at the other end of the range.
- The four unreachable-p results come from a targeted search of the roughly 500 asterisked comparisons in Tables 2-6, selected as the cells where a significance claim looked least supportable. They are a floor on the number of unsupportable asterisks in this paper, not a count of them.
- Three of the four unreachable-p findings sit in Table 2, which was read from the publisher XML but not independently reconciled against the PDF in this stage. Stage 1 did reconcile Tables 3, 4 and 5 against PDF pages 6-8 and found the two sources agree exactly, including on the corrupted cells, which is good evidence that the XML extraction of this article is faithful; the Table 3 finding was itself PDF-reconciled and stands independently.
- No GRIM, GRIMMER, SPRITE or DEBIT result appears in this review because every outcome variable in the paper is a continuous physiological or biochemical measure, which bars that family of checks by construction. No R cross-check was required, because no finding here reaches `impossible` -- an R engine was neither consulted nor needed.
- This system reads one paper and reaches no external source. Two questions a reader needs in order to weigh the findings are outside its reach entirely: whether similar discrepancies appear in other papers by the same authors, and how the reported effect sizes compare with equivalent values from other studies in this area. Those parts of the interpretation are the reader's, not ours.
- The multiplicity arithmetic could not be run at all, because every p-value in the paper is a threshold rather than a value. No count of claims lost to correction exists for this paper in either direction -- the absence of such a number is a fact about the reporting, not evidence that correction would leave the conclusions intact.
- The tail-flick plausibility finding rests on an external benchmark from the thermal nociception literature (normal rat latencies of a few seconds; conventional cut-offs of about 10-15 s), not on anything the paper states. Under the rulebook it is capped at `suspicious`, is not the headline, and would be resolved by the authors simply stating their cut-off time.
- No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.

## Coverage

- **Statistics found:** 704; **checked:** 37
- **Tools run:** extract_xml, get_table, extract_pdf, statcheck, parse_table, parse_cells_typed, check_table, check_summation, check_summation_batch, rivets_independent_t, detect_duplication, multiplicity_report
- **Tables checked:** Table 1 (Experimental Protocol in Nerve Lesion) -- 92 cells; all 18 row sums, 3 column sums and 2 grand-total reconciliations re-run at tolerance 0 in this stage; Al-group biochemical allocation summed separately, Table 2 (Physiological variables) -- 144 mean ± SD cells re-read at source; 5 comparisons reconstructed here (3 respiration, 1 body weight, 1 arterial pH); rectal-temperature and PaCO2 columns re-scanned for duplication with correctly-scoped spans, Table 3 (Von Frey / paw withdrawal / tail flick) -- all 54 cells re-read at source; 2 comparisons reconstructed here (paw withdrawal NL+Al 10 wk, Von Frey NL+Al 4 wk); reconciled against PDF page 6 in stage 1, Table 4 (BSCB breakdown and edema) -- 216 cells reviewed in stage 1 against PDF page 7; 3 corrupted cells identified, Table 5 (albumin, GFAP, MBP, HSP) -- 166 cells and the footnote re-read at source in this stage; 2 corrupted cells and 1 corrupted footnote confirmed; group structure checked against Table 1's allocation, Table 6 (TNF-alpha, IL-6, IL-4, IL-10) -- 166 cells reviewed; group structure checked against Table 1's allocation
- **Checkable table cells:** 525 of 902 surveyed; **checked:** 0
    - 525 could not be checked without knowing what kind of quantity the row reports
- **Where a check and this review disagreed:** 1 sweep finding recorded a severity the validated check behind it did not return (1 upgraded, 0 downgraded). 1 is marked on the entry above that cites it.
- **Traceable to the page:** 26 of 26 checks recorded the passage their numbers were read from; 22 of those were located in the paper's own text.
- **4 quoted passages are ours, not the paper's.** Every number in them was found in the paper, but the sentence around those numbers was assembled by this review and does not appear as written -- so do not search the PDF for it. The CHECK is sourced; only the quotation marks over-promise.

## What each check does

One entry per check that ran on this paper. The **assumptions** are the conditions under which its verdict holds; where one is unmet the verdict is capped, not merely caveated.

### `check_summation` — probabilistic

Checks that printed values sum to their stated total within accumulated rounding.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The values are assumed exhaustive, non-overlapping addends of the stated total; overlap or an omitted row mimics a mismatch.
- The window derives from the printed decimals of every addend and of the total; with neither decimals nor tolerance it refuses.
- Count columns that must hold exactly take tolerance = 0; percentage columns legitimately misbalance by rounding.

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

### `rivets_independent_t` — probabilistic

Maps the t and p reachable from rounded inputs, and flags hand-calculation signatures.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The reported t and p are assumed computed from these summaries by an independent-samples t-test.
- Welch and Student readings are both accepted, as are both tail conventions, unless the paper states them.
- Monte Carlo draws uniformly over each printed value's truncation interval.
- A point match plus a rare hit rate is read as a hand-calculation signature.
- Pass a bound p as the STRING, never the float.

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

This is a rat study of chronic constriction nerve injury as a model of neuropathic pain. Three engineered metal nanoparticles (Ag, Cu, Al, 50-60 nm) are given intraperitoneally, and cerebrolysin -- a peptide preparation made by EverNeuroPharma, one of the study's listed funders -- is given intravenously. The paper reports that nerve lesion produces progressive hyperalgesia, blood-spinal cord barrier breakdown, cord edema, cytokine elevation and structural damage; that all three nanoparticles worsen all of it; and that cerebrolysin reverses all of it. The version of record is titled "RETRACTED ARTICLE". The retraction notice was not among the files supplied, so nothing below is derived from or reconstructs the publisher's grounds; every finding comes from the paper's own numbers.

## How this paper resists being checked

Almost every standard forensic check is inapplicable here, and that is worth stating before any finding, because the absence of such findings is not evidence the values are sound. The granularity family (GRIM, GRIMMER, SPRITE, DEBIT) works only on whole-number data; every outcome in this paper is a continuous physiological or biochemical measure, so those checks correctly refuse. Running the dispatcher over Table 3 typed all 54 cells successfully and then ran zero checks on them -- 0 of 54 -- for two independent structural reasons: continuous outcomes, and no cell carrying its own sample size. The same reasoning applies unchanged to Tables 2, 4, 5 and 6.

On top of that, the paper prints no test statistic, no degrees of freedom and no exact p-value anywhere in 25 pages. An automated extraction over the whole document recovered zero. Roughly five hundred comparisons are communicated entirely by asterisks. And the authors state in every table footnote that "for simplicity, the values are adjusted to nearest numbers" -- their descriptives are rounded to integers, which is a legitimate presentational choice that happens to destroy the precision a reader would need to reconstruct the tests.

The only route left is to work backwards from the group means and SDs. That is what was done.

## What the reconstruction showed

Twelve comparisons were reconstructed, chosen as the cells where a significance claim looked least supportable. Four could not be produced at all, and one comparison the paper calls non-significant turns out to be strongly significant. The direction matters: this is not a systematic bias toward more stars, which would be the signature of over-eager analysis. Errors run both ways, which is the signature of a table whose significance markers were not generated by the tests the paper describes.

Two details make these harder to explain away than they might look. First, every reconstruction used the sample size most favourable to the authors -- the top of the stated 6-8 range when testing a significance claim, the bottom when testing a claim of no difference. Second, the paper says it used ANOVA with Dunnett's correction, which is *more* conservative than the unadjusted two-group tests recomputed here. Both choices push in the authors' favour, and the discrepancies survive both.

A thirteenth comparison sits on the fence and is reported here rather than as a finding: Table 3's Von Frey weight for NL + Al NPs at 4 weeks (9 ± 5, unstarred) against a control of 15 ± 2 gives an achievable p-interval of [0.005, 0.082] at n = 6, which straddles 0.05. It cannot be adjudicated, and it is not counted against the paper.

## The arithmetic that does not depend on any test

Table 1 is the study's allocation table and it should be the easiest thing in the paper to verify: eighteen rows of whole animals. Six of seven sums fail at zero tolerance. What makes this more than a typo is the internal structure of the failures. Three row totals over-state by exactly two each; two column totals under-state by eight and six; and the printed grand total of 348 -- which matches the figure in the Methods text -- is arithmetically consistent only with the incorrect column totals, not with the animals actually listed. There is a consistent chain from the wrong intermediate figures to the headline N, and no chain from the actual data.

## What the paper collected but did not report

Table 1 sets aside 26 rats for biochemical analysis across the four aluminium-nanoparticle groups. Tables 5 and 6 -- the biochemical tables -- contain no aluminium rows at all; their captions cover only silver and copper. The abstract, having named all three metals, states that the ELISA proteins and cytokines were elevated "in nerve lesion that was exacerbated following NPs intoxication". For aluminium, no data in the paper supports that.

## Consistency, where it was found

It is worth saying what did reconcile. Fifteen of Table 1's eighteen per-group row totals add up exactly, and the Biochemical Analyses column reconciles exactly at 130. A duplication scan of Table 2's rectal-temperature and PaCO2 columns turned up exactly one identical pair among 306 comparisons, at a corrected coincidence probability of 0.034 -- weak, and materially weaker than the sweep's first estimate of 0.0001, which came from a span model fitted across variables that do not share a range. That correction is recorded because a duplication finding presented at the wrong strength is worse than none.

But this is thin. Most of the paper could not be checked, and among the small set of claims that could be, several do not hold.

## The bottom line

Four significance markers cannot be produced from the numbers printed beside them; one stated non-significance is contradicted by the same table at roughly twenty-five times the paper's own threshold; the study's sample size is stated three different ways by its own allocation table; five published values cannot be read as numbers; and the animal-level data that would settle all of it are not available. Two of the unsupportable asterisks sit on the primary pain outcome and on a claimed cerebrolysin benefit, which are the paper's central claims.

I have no confidence in the accuracy of the statistics reported in this study, and its conclusions should not be relied upon without the underlying per-animal data being made available for re-analysis.

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
