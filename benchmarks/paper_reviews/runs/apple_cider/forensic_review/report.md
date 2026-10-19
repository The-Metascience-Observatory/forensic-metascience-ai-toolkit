# Forensic review — paper

## Headline — Level 3 — Notable error

**Baseline Age, Weight, Height too similar across arms (p=0.006)**

The recomputed one-way ANOVA p-values for baseline Age, Weight and Height (0.931, 0.991, 0.990) are all far above 0.9, and the Carlisle-Stouffer-Fisher test finds this excess similarity survives a conservative correlation adjustment (rho=0.5, similarity p=0.0061). Weight's own SDs (27.1, 28.5, 27.2, 28.6) are independently under-dispersed (variance-dispersion p=0.008). This subgroup was selected after seeing the whole-table dispersion screen flag it, which is a legitimate use of that screen's own recommendation but is not a pre-registered test.

**Verdict: does_not_reconcile** — paper severity Level 5 — Major error affecting conclusions (confidence: medium)

## Summary

The most serious concern is that Table 1's baseline Age, Weight and Height are statistically far too similar across the four randomised arms (Carlisle-Stouffer-Fisher similarity p=0.006, confirmed on re-run and surviving a conservative rho=0.5 adjustment for these correlated measures), reinforced by Weight's own SDs (27.1/28.5/27.2/28.6) being more uniform than sampling error predicts (p=0.008, also confirmed). This pattern is associated with fabricated or non-randomly-allocated data in the literature, though it remains a statistical improbability rather than proof of manipulation. Independently, Table 1's baseline FBS, TC and TG values for several groups do not match the same measurements printed as Table 3's own Week-0 column -- a plain internal contradiction of supposedly identical data. The Discussion also overstates Table 2's own weight/BMI reductions, and the Methods name only an independent t-test for what are mostly within-subject comparisons. Table 2's internal week-by-week trends, most percentages, and the effect-size/summation checks were internally consistent. A journal would need at minimum a corrigendum reconciling Table 1 against Table 3 and correcting the Discussion's overstated range, plus an editorial query about the baseline-similarity signal and randomisation records. This review did not have access to raw participant-level data and cannot establish whether the discrepancies reflect data fabrication, transcription error, or an unreported protocol detail.

## Findings

### Level 4 — Localized methodological flaw or omission — Baseline biochemical values disagree between Table 1 and Table 3 across four cells

Table 1's baseline (week 0) values for FBS (Groups 3 and 4), TC (Group 2) and TG (Group 4) do not match the identical measurement printed as the Week 0 column of Table 3 -- means and/or SDs differ in every case (e.g. FBS Group 3: 119.9±7.2 vs 119.9±12.2; FBS Group 4: 113.6±12.5 vs 118.6±12.5; TC Group 2: 173.6±16.3 vs 175.6±12.9; TG Group 4: 168.1±18.2 vs 166.1±18.2). This is a plain, verified internal contradiction spanning three variables and three groups, not a single arithmetic slip.
*(producer: science_error; technique: internal_contradiction; location: Table 1 (baseline biochemical row) vs Table 3, Week 0 column)*
Reproduce: `no_command_applies`
*Merged pattern: absorbs 4 sibling finding(s).*

### Level 3 — Notable error — Baseline Age, Weight, Height too similar across arms (p=0.006)

The recomputed one-way ANOVA p-values for baseline Age, Weight and Height (0.931, 0.991, 0.990) are all far above 0.9, and the Carlisle-Stouffer-Fisher test finds this excess similarity survives a conservative correlation adjustment (rho=0.5, similarity p=0.0061). Weight's own SDs (27.1, 28.5, 27.2, 28.6) are independently under-dispersed (variance-dispersion p=0.008). This subgroup was selected after seeing the whole-table dispersion screen flag it, which is a legitimate use of that screen's own recommendation but is not a pre-registered test.
*(producer: tool_expert; technique: csf_test; location: Table 1, Age/Weight/Height rows across Groups 1-4)*
> Age (years) 17.2±5.2 18.1±5.5 17.6±5.1 17.8±5.7
Reproduce: `metascience csf --p-values 0.9310,0.9905,0.9897 --method stouffer --design parallel_rct --correlation 0.5`
*Merged pattern: absorbs 2 sibling finding(s).*

### Level 3 — Notable error — Discussion claims 6-8 kg / 2.7-3.0 BMI-point reductions Table 2 doesn't support

The Discussion states ACV intake "reduced the body weight by 6-8 kg and BMIs by 2.7-3.0 points." Table 2's own week 0-to-week 12 values give weight reductions of 5.1 kg (Group 1), 7.4 kg (Group 2) and 7.0 kg (Group 3), and BMI reductions of 1.8 (Group 1), 2.9 (Group 2) and 2.8 (Group 3) points. Group 1's weight loss (5.1 kg) falls below the claimed 6-8 kg range, Group 1's BMI loss (1.8) falls well below the claimed 2.7-3.0 range, and no group's BMI loss reaches 3.0.
*(producer: science_error; technique: internal_contradiction; location: Discussion, paragraph beginning "In Lebanon, the percentage..." vs Table 2, Weight and BMI rows)*
Reproduce: `analysis_code/001_script.py`
*Merged pattern: absorbs 1 sibling finding(s).*

### Level 3 — Notable error — Baseline Weight SDs (27.1, 28.5, 27.2, 28.6) are more uniform than sampling error predicts

Only 0.78% of honest draws under the equal-variance null cluster this tightly (max_z-min_z=0.108, p=0.0078). This is the strongest single-row signal in Table 1 and reinforces the Age/Weight/Height CSF finding, though it is capped at suspicious and is a relative screening signal, not proof.
*(producer: tool_expert; technique: check_variance_dispersion; location: Table 1, Weight row)*
> Weight (kg) 79.0±27.1 79.3±28.5 77.2±27.2 79.1±28.6
Reproduce: `metascience variance-dispersion --sds 27.1,28.5,27.2,28.6 --ns 30,30,30,30 --homogeneous-variances true --design parallel_rct`

### Level 3 — Notable error — Independent t-test used for within-subject repeated-measures comparisons

Methods state significance was determined "by using an independent t-test," a single named procedure. But the overwhelming majority of the significance markers in Tables 2 and 3 are baseline-vs-follow-up comparisons WITHIN the same participants over time (the '*' symbol, defined as "compared with baseline (week 0)"), which are paired/repeated-measures data, not independent samples. No paired t-test, repeated-measures ANOVA, or correction for the dozens of pairwise comparisons (baseline vs 3 follow-ups x 4 groups x 3 tables, plus between-group comparisons at each week) is described anywhere in the paper.
*(producer: science_error; technique: not_computational; location: Statistical methods and data analysis (Methods) vs Tables 2 and 3 footnotes)*
Reproduce: `no_command_applies`
*Merged pattern: absorbs 1 sibling finding(s).*

### Level 2 — Minor error — No clinical trial registry number reported for this RCT

The paper reports an institutional ethics approval number (HCR/EC 2023-005) but no clinical-trial-registry identifier (e.g. ClinicalTrials.gov, ISRCTN) anywhere in the text, which is expected for a prospective RCT.
*(producer: tool_expert; technique: not_computational; location: Ethics approval / Methods sections)*
> The number/ID of the approval is HCR/EC 2023–005.
Reproduce: `no_command_applies`

### Level 2 — Minor error — Age range 12-25 pooled as one group without stratification

Inclusion criteria admit participants aged 12 to 25, a span covering early adolescence through full adulthood, yet all analyses pool this range within each of the four groups with no age-stratified analysis, no pediatric BMI-for-age percentiles (adult BMI cut-points of 27-34 kg/m2 were used uniformly), and body composition measured with a consumer bioelectrical-impedance device marketed for adult use. The resulting very wide within-group SDs for weight (~27-28 kg on means of ~77-79 kg) and height (~20-22 cm on a mean of ~157 cm) are consistent with this unaddressed age heterogeneity.
*(producer: science_error; technique: not_computational; location: Participants (Methods, inclusion criteria) and Table 1)*
Reproduce: `no_command_applies`

### Level 2 — Minor error — No dropout, exclusion after enrolment, or CONSORT-style flow is reported over 12 weeks

All four groups are reported at n=30 at every timepoint (weeks 0, 4, 8, 12) in Tables 1-3, with venous blood draws and full anthropometric batteries required at each visit over a 12-week trial in adolescents and young adults. No flow diagram, no count of screened/excluded/lost-to-follow-up participants, and no discussion of missing data appears anywhere in the paper. Zero attrition over 12 weeks with repeated blood draws is unusually low and is not addressed as a limitation.
*(producer: science_error; technique: not_computational; location: Participants (Methods) and Tables 1-3 (n=30 throughout))*
Reproduce: `metascience flow-check flow.json`

### Level 2 — Minor error — Group 3 female percentage (63.4%) does not match 19/30 under any rounding convention

19 of 30 Group 3 participants are female, which is 63.333%; the printed 63.4% falls outside the rounding interval [63.35, 63.50) computed both under round-to-nearest and truncation. The paired male figure (36.6% for 11/30) is internally consistent under truncation, so this looks like an isolated slip rather than a wrong count, and the two figures still sum to exactly 100%.
*(producer: tool_expert; technique: check_count_percent; location: Table 1, Female row, Group 3)*
> Female 60.0 (n=18) 66.7 (n=20) 63.4 (n=19) 56.7 (n=17)
Reproduce: `metascience check-count-percent --count 19 --percentage 63.4 --n 30 --decimals 1`

### Level 1 — Trivial error — Table 3 prints an undefined '#' symbol and a doubled asterisk in two cells

Table 3's footnotes define only three symbols (*, dagger, double-dagger), but the Group 2 FBS cells at Week 8 and Week 12 print "115.4±12.6*#*†" and "110.1±12.2*#*†" -- an undefined '#' sandwiched between two asterisks. No other cell in the table carries a repeated or undefined symbol.
*(producer: science_error; technique: not_computational; location: Table 3, FBS row, Group 2, Week 8 and Week 12)*
Reproduce: `no_command_applies`
*Merged pattern: absorbs 1 sibling finding(s).*

## Findings set aside by the adjudicator (retained on the record)

- **merged into `f_3b213d597e3b6533`**: Table 1 and Table 3 print different baseline FBS SDs for Group 3 (7.2 vs 12.2)
- **merged into `f_3b213d597e3b6533`**: Table 1 and Table 3 print different baseline FBS means for Group 4 (113.6 vs 118.6)
- **merged into `f_3b213d597e3b6533`**: Table 1 and Table 3 print different baseline TG means for Group 4 (168.1 vs 166.1)
- **merged into `f_3b213d597e3b6533`**: Table 1 vs Table 3: different baseline TC mean/SD for Group 2
- **merged into `f_d6633f134967cd3c`**: Discussion's '6-8 kg / 2.7-3.0 points' summary undershoots Table 2's own range
- **merged into `f_2b248813e814c6a3`**: Table 3 Group 2 cells carry an undefined '#' symbol not listed in the footnotes
- **merged into `f_f8da056b67e0b51e`**: Methods says 'independent t-test' for within-subject week-0 comparisons

## What we could NOT check

- Table 2, all within-group week4/week8 comparisons and all between-group (†/‡) comparisons not individually spot-checked: Paper reports only p<0.05 thresholds with no exact p, t, or F values; recalc_within_subjects_t on the pairs I did check returned indeterminate because a threshold p only lower-bounds the implied correlation. Budget did not permit exhaustive per-cell threshold checks across all ~80 anthropometric and ~48 biochemical cells; week0-vs-week12 pairs for Weight, BMI (all 4 groups) and FBS (Group 3, Group 4) were checked as representative.
- Between-group comparisons marked with †/‡ symbols throughout Tables 2 and 3: No effect sizes, exact p-values, or test statistics printed; only the independent t-test threshold is stated in Methods. No family-wise correction is reported across this large number of comparisons (multiplicity_report could not be run meaningfully without exact p-values).
- Whole paper: No supplementary data files were found alongside this PDF/markdown bundle to run detect_raw_duplication or extract_supplement on.
- Methods, Statistical methods paragraph: No a priori power/sample-size analysis is reported, so verify_power_analysis has no inputs to check against; required_n was instead run in the reverse direction (design sensitivity) on the headline Weight and BMI Group3-vs-placebo week12 comparisons.
- CONSORT-style participant flow (enrollment, allocation, follow-up, attrition): The paper reports no dropout/attrition figures at all across 12 weeks in a 120-person trial with self-administered diaries; this is a flow-arithmetic/prose consistency issue that belongs to the science-error analyst's territory, not this sweep's.
- Table 1, Weight/Height rows: Handoff to tool expert: SD-range plausibility (check_sd_range / check_variance_dispersion) on weight (mean~77-79, SD~27-28, n=30) and height (mean~157, SD~20-22, n=30) given stated inclusion bounds (age 12-25, BMI 27-34 kg/m2) was not run by this analyst; belongs to the tool expert's numeric beat.
- Tables 2 and 3, all significance markers: Handoff to tool expert: recommend multiplicity_report over the full set of reported p<0.05 comparisons (baseline-vs-timepoint x group x variable x table, plus between-group markers) to quantify the uncorrected-multiple-comparisons problem flagged in the design_analysis_mismatch finding.
- Data availability statement: Paper states 'All data relevant to the study are included in the article or uploaded as supplementary information,' but this analyst does not read supplements; whether a supplement was actually delivered is left to the tool expert / supplement review.
- OMRON HBF-306C bioelectrical impedance device: Attempted a web lookup for a stated minimum-age restriction on this consumer device (relevant to the 12-25 year age range enrolled) but the manufacturer manual text could not be reliably parsed; no verbatim quote was obtained, so no factual finding was filed.

## Limitations

- the tool_agent stage returned an EMPTY report (30 forensic calls on its ledger); retried once
- Checks recorded as passing: 17; undecided: 5.
- Channel `image_forensics` did not produce a retained result: did_not_run — image track disabled.

## Coverage

- statistics found: 25; checked: 25
- tools run: bayesian_table1_dispersion, csf_test, check_count_percent, check_summation, check_variance_dispersion, recalc_within_subjects_t, grim_percentage, statcheck, check_effect_plausibility, required_n, extract_pdf

---
*pipeline 1.11.1 · run r_65469ad0937594ba · analysed 2026-08-23T02:49:50Z · backend claude*

## About this report

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

