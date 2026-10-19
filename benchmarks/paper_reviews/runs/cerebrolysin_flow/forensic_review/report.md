# Forensic review — paper

## Headline — Level 5 — Major error affecting conclusions

**Combined Wei-Lachin CI is far narrower than every component**

Table 2 prints eight component 95% CIs at n=10/3 with widths of about 0.66 (NNTXDIAM 0.0704 to 0.7296). The Combined (Wei-Lachin) interval at the same n is 0.5456 to 0.5766, width 0.031, and is the sole significant result (p<0.0001). All eight components are non-significant and mixed in direction (MW 0.4000 to 0.8000). Independent averaging of eight endpoints would shrink a Wald interval only about 2.8-fold, not 21-fold. check_estimate_ci finds the Combined CI and p internally consistent with each other, so the defect is that this Combined row cannot come from the printed components at n=10/3.

**Verdict: does_not_reconcile** — paper severity Level 5 — Major error affecting conclusions (confidence: medium)

## Summary

The paper's only statistically significant result, the Table 2 Combined Wei-Lachin Mann-Whitney of 0.5611 (95% CI 0.5456 to 0.5766, n=10/3, p<0.0001), cannot be produced from the eight component intervals printed above it, which are about twenty-fold wider and mixed in direction. That same Combined row, including the 10/3 denominator, is reprinted as Table 3's combined muscle result beside rows whose n are 16/5 and 11/2, and Table 3's p-values 0.4146 and 0.4936 match Table 2's first two rows. Table 2 also pairs one MW and CI with two different p-values and reports NNTXMAX CI 0.5362-1.0000 against p=0.9017. Count-percent, ratio, bounds, summation and the Results attrition cascade 30 to 21 to 15 reconcile. A corrigendum should withdraw or recompute the Wei-Lachin combined tests, align Table 3, and correct the CMAP-positive counts (8 of 21 versus 8 of 16 versus 7 of 14) and the Figure 9 angiogenesis mean 2.57 versus Table 4. This review did not establish intent, did not re-analyse raw histometric files, and did not treat GRIM-U lattice misses as accusations because the paper attributes p-values to Wei-Lachin rather than exact univariate U.

## Findings

### Level 5 — Major error affecting conclusions — Combined Wei-Lachin CI is far narrower than every component

Table 2 prints eight component 95% CIs at n=10/3 with widths of about 0.66 (NNTXDIAM 0.0704 to 0.7296). The Combined (Wei-Lachin) interval at the same n is 0.5456 to 0.5766, width 0.031, and is the sole significant result (p<0.0001). All eight components are non-significant and mixed in direction (MW 0.4000 to 0.8000). Independent averaging of eight endpoints would shrink a Wald interval only about 2.8-fold, not 21-fold. check_estimate_ci finds the Combined CI and p internally consistent with each other, so the defect is that this Combined row cannot come from the printed components at n=10/3.
*(producer: tool_expert; technique: not_computational; location: Table 2, Combined (Wei-Lachin) versus component CIs)*
> Combined (Wei-Lachin) | 0,5611 | (0,5456 to 0,5766) | 10 / 3 | <0.0001

### Level 4 — Localized methodological flaw or omission — Table 3 Combined row and p-values are copied from Table 2

Table 3 reprints Table 2's Combined Wei-Lachin row in full (MW=0.5611, CI 0.5456-0.5766, N1/N2=10/3, p<0.0001), and the caption repeats those figures. Table 3's own rows are Muscle Marlene (n=16/5) and Muscle Catoi (n=11/2), so 10/3 belongs to neither. Muscle Marlene p=0.4146 and Muscle Catoi p=0.4936 are identical to Table 2 NNTXDIAM and NNTXAREA. Muscle Catoi's CI (0.5578-1.0000) excludes the MW null of 0.5, so the copied p=0.4936 is also discordant with its own interval (Wald p from the CI about 0.0048).
*(producer: tool_expert; technique: detect_duplication; location: Table 3, Combined (Wei-Lachin) row)*
> Combined (Wei-Lachin) | 0,5611 | (0,5456 to 0,5766) | 10 / 3 | <0.0001
*Merged pattern: absorbs 2 sibling finding(s).*

### Level 3 — Notable error — Table 2 NNTXDIAM and NNTXAREA share MW and CI, not p

NNTXDIAM and NNTXAREA both print MW=0.4000 and 95% CI (0.0704 to 0.7296) at n=10/3, but p=0.4146 versus p=0.4936. check_estimate_ci recovered the same Wald p=0.5521 from both intervals. The same Mann-Whitney estimate, interval and sample size cannot yield two different p-values. One of the two p-values is misaligned with the printed MW and CI.
*(producer: tool_expert; technique: check_estimate_ci; location: Table 2, NNTXDIAM and NNTXAREA rows)*
> NNTXDIAM | 0,4000 | (0,0704 to 0,7296) | 10 / 3 | 0,4146

### Level 3 — Notable error — Table 2 NNTXMAX CI excludes 0.5 but p=0.9017

NNTXMAX reports MW=0.8000 with 95% CI 0.5362 to 1.0000 at n=10/3, which excludes the Mann-Whitney null of 0.5, but the printed p=0.9017 is non-significant. check_estimate_ci recovered p=0.0112 from the CI and flagged that the interval excludes the null while the p does not. The upper bound is censored at 1, but the lower bound 0.5362 already lies above 0.5, so the discordance does not depend on the Wald midpoint. If the CI is right the row is significant; if the p is right the CI is wrong.
*(producer: tool_expert; technique: check_estimate_ci; location: Table 2, NNTXMAX row)*
> NNTXMAX | 0,8000 | (0,5362 to 1,0000) | 10 / 3 | 0,9017

### Level 2 — Minor error — Angiogenesis mean 2.57 does not match Table 4 scores

The Figure 9 caption says EMG-positive angiogenesis scores were 2 and 3 with average 2.57, which is 18/7 (four 3s and three 2s). Table 4 lists ang(2), ang(1), ang(3), ang(3), ang(2), ang(3) for six of seven EMG-positive cases and omits ang for case 28. Case 6 is scored 1, which the caption excludes. The EMG-negative average 1.3 does match the ten Table 4 scores (sum 13).
*(producer: tool_expert; technique: not_computational; location: Figure 9 caption versus Table 4 ang scores)*
> more intense in EMG-positive cases (individual final scores of 2 and 3; score average 2.57) than in EMG-negative cases (individual final scores of 1 and 2; score average 1.3)

### Level 2 — Minor error — CMAP-positive count printed as 8, 7 and 7 of 14

The abstract and Results say eight rats showed positive CMAPs, Figure 4 says 8 of 16, and Results also say stimulation in 21 rats was positive in only 8. Table 4 lists seven EMG-positive cases (5, 6, 10, 13, 19, 21, 28). Discussion later says positive EMG potentials in 7 of 14 surviving animals. The same binary outcome is given three different numerators and three different denominators.
*(producer: tool_expert; technique: internal_contradiction; location: Abstract; Results; Table 4; Figure 4 caption; Discussion)*
> Eight rats showed positive CMAPs. Reinnervation and neuromodulation were demonstrated by counting and comparison of the grafted muscle fibers diameter.

## Findings set aside by the adjudicator (retained on the record)

- **discarded** (misapplication): All eight Table 2 Mann-Whitney p-values miss the U lattice — The paper attributes these p-values to the Wei-Lachin procedure, a large-sample multivariate generalization of Wilcoxon-Mann-Whitney, not to an exact univariate U. A Wald or other Wei-Lachin variance estimator will miss the untied lattice, so GRIM-U does not license a U-lattice accusation. Component p-versus-CI discordances are kept separately.
- **merged into `f_7931f5b108f6ebeb`**: Table 3 p-values 0.4146 and 0.4936 match Table 2
- **merged into `f_7931f5b108f6ebeb`**: Table 3 Muscle Catoi CI excludes 0.5 but p=0.4936

## Reporting conventions

- **0 of 1** granularity checks reconcile only if the reporter TRUNCATES rather than rounds (SPSS's default, and several journal styles).
- **0 of 1** granularity checks reconcile only under the POPULATION (n) SD rather than the sample (n-1) SD (numpy's `std` default, Excel's STDEVP).
- These are NOT findings and no severity rests on them. Choosing a convention is not fabrication, and one instance is a house style. **The rate is the signal**: a high proportion beside genuine `impossible` findings is grounds to look harder, not evidence in itself.

## What we could NOT check

- Participant flow (abstract 16 survivors vs Results 21 at 2nd Op vs 15 completers; 14 deaths vs 15 deaths): Handoff to science-error track: CONSORT/flow identities are owned by check_flow_arithmetic, not this sweep.
- Figure 12 muscle-fiber diameter percentages: Figure carries unique group averages not printed as numbers in the text; no means/SDs available for check_effect_plausibility, required_n, or SPRITE.
- Table 4 remaining case-level histology grades and axon (min-max) counts: Descriptive per-animal ordinal scores and continuous micrometre diameters; GRIM/SPRITE do not apply to continuous diameters, and no group mean+SD+n+range is printed for a SPRITE reconstruction.
- CERE versus NaCl versus nil muscle-fiber comparison: No arm-level means, SDs or CI printed; absence_of_evidence and effect-size tools cannot run on the drug contrast.
- No XML full text: Publisher XML was not in the paper bundle; tables were taken from extract_pdf and body.md.
- Supplementary files: No supplementary spreadsheet or PDF was provided with this bundle.
- Power analysis: No a-priori power calculation is reported; verify_power_analysis has no inputs.

## Limitations

- the science_agent stage produced no parseable findings JSON
- Checks recorded as passing: 9 filed as findings, 21 on the tool ledger (12 of them per-cell checks collapsed by check_table); undecided: 3. The two counts differ, so the filed report does not describe everything the tools did.
- Channel `image_forensics` did not produce a retained result: did_not_run — image track disabled.
- Channel `science_error` did not produce a retained result: refused — error_stalled.

## Coverage

- statistics found: 72; checked: 48
- tools run: extract_pdf, parse_table, statcheck, check_estimate_ci, grimu_check, grimu_coexistence, check_summation_batch, check_count_percent, check_ratio, check_table, detect_duplication, multiplicity_report, stalt_check, check_statistic_bounds, absence_of_evidence, flag_round_n

---
*pipeline 1.15.0 · run r_0049688599592e2c · analysed 2026-09-02T15:46:28Z · backend grok*

## About this report

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

