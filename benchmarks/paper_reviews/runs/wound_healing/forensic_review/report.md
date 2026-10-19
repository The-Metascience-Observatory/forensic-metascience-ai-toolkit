# Forensic review — paper

## Headline — Level 4 — Localized methodological flaw or omission

**Table 2 BMI range 23.0-45.0 contradicts BMI>30 inclusion**

Inclusion required BMI>30 and Methods state there is no group with BMI below 30 because the study was restricted to obese women. Table 2 prints BMI range 23.0-45.0 (mean 34.5, SD 3.6). Those two statements cannot both be true: either non-obese women were enrolled, or the reported range is wrong. The abstract and title frame the trial as a study of obese women.

**Verdict: unresolved** — paper severity Level 4 — Localized methodological flaw or omission (confidence: medium)

## Summary

The most trust-undermining defect is Table 2's BMI range of 23.0–45.0 against the Methods inclusion rule BMI>30 and the explicit claim that the study has no women with BMI below 30; the title and abstract present the trial as a study of obese women. Results and Discussion also print Table 1 event counts (12, 10, 18, 20 of 397) as cohort percentages, inflating gapping, seroma, erythema, and infection about four-fold relative to the table's 3%, 2.5%, 4.5%, and 5%. Figure 1 and the Methods attrition narrative reconcile (411 assessed, 11 declined, 400 randomized 1:1, 3 lost, 199 and 198 analysed), and the six result tables' cell counts, percentages, and Table 4 odds ratios match one another. Methods never define the four wound outcomes, name the Table 4 test, report a sample-size calculation, describe sequence generation or allocation concealment, specify skin closure, or record ethics-committee approval. A corrigendum should correct the BMI range or the inclusion claim, restore the prose incidences to the table values, and supply the missing CONSORT items. This review did not independently re-fetch the ClinicalTrials.gov record, did not establish intent, and the table-level arithmetic screen otherwise reconciled on the printed values.

## Findings

### Level 4 — Localized methodological flaw or omission — Methods omit outcome definitions, analysis, randomization, and ethics

This interventional RCT reports wound gapping, seroma, erythema, infection, and a 42-event composite without diagnostic criteria, a named statistical test for Table 4, a sample-size calculation, sequence generation, or allocation concealment. Skin closure is never specified even though surgeons closed skin and subcutaneous layers. The only ethics statement is informed consent; no ethics-committee approval is recorded.
*(producer: science_error; technique: not_computational; location: Patients and methods)*
> Randomization of cases was done to the 400 pregnant women who were consented to participate in the study and were distributed in two groups: group A and group B. The randomization allocation was 1:1.

### Level 4 — Localized methodological flaw or omission — Table 2 BMI range 23.0-45.0 contradicts BMI>30 inclusion

Inclusion required BMI>30 and Methods state there is no group with BMI below 30 because the study was restricted to obese women. Table 2 prints BMI range 23.0-45.0 (mean 34.5, SD 3.6). Those two statements cannot both be true: either non-obese women were enrolled, or the reported range is wrong. The abstract and title frame the trial as a study of obese women.
*(producer: science_error; technique: internal_contradiction; location: Patients and methods versus Table 2, BMI row)*
> with BMI>30 (so, we do not have a group of women with BMI below 30 as our focus in the present research was to assess the obese women)

*Not the paper's words as printed: Every number here appears in the paper, but this exact sentence does not -- it was composed by the review, so searching the PDF for it will find nothing.*

### Level 3 — Notable error — Results treat Table 1 counts 12, 10, 18, 20 as cohort percentages

Results and Discussion state that wound gapping, seroma, erythema, and infection occurred in 12%, 10%, 18%, and 20% of the whole cohort. Table 1 prints those same integers as counts with percentages 12 (3%), 10 (2.5%), 18 (4.5%), and 20 (5%) at n=397. check_count_percent on 12/397 versus printed 12% yields 3.02%, outside the rounding interval, with implied denominator about 100. The same Discussion paragraph later gives arm counts 10 (5.1%) and 2 (1%) for gapping, which cannot be a 12% cohort rate. Between-group Table 4 comparisons are unaffected.
*(producer: science_error; technique: check_count_percent; location: Results Description and Discussion versus Table 1)*
> wound gapping occurred in 12% of cases, wound seroma occurred in 10% of cases, wound erythema occurred in 18% of cases, and wound infection occurred in 20% of cases in the whole cohort of cases.

*Not the paper's words as printed: Every number here appears in the paper, but this exact sentence does not -- it was composed by the review, so searching the PDF for it will find nothing.*
Reproduce: not available -- no runnable command -- the review's command did not match the tool's arguments.
*Merged pattern: absorbs 1 sibling finding(s).*

### Level 3 — Notable error — Registered 1-month primary outcome not the paper's 7-day follow-up

NCT03354078 was first submitted 19 November 2017 after a stated 18 June 2017 start, so registration is retrospective. The registered primary outcome is participants without seroma, erythema, and infection at one month after cesarean. The paper says most complications were diagnosed at 7 days and does not report 1-month results. Registry eligibility is age 18-40 years; the paper includes ages 25-35. The paper dates the study to December 2017, while the registry lists completion 23 November 2017 and the journal received the manuscript 1 December 2017.
*(producer: science_error; technique: factual_claim; location: Abstract NCT ID, Methods follow-up, versus ClinicalTrials.gov NCT03354078)*
> The time interval from the wound closure till diagnosis of the wound complications (erythema, seroma, wound infection, and wound gapping) in most of the patients was 7d (at first visit postoperative)

*Not the paper's words as printed: Every number here appears in the paper, but this exact sentence does not -- it was composed by the review, so searching the PDF for it will find nothing.*

### Level 2 — Minor error — Citation [1] does not support the 3% to 30% CS complication range

The paper cites Brown et al. 2010 for cesarean wound-complication incidence ranging from 3% to 30%. That paper is a plastic-surgery study of psychosocial distress and self-rated scar severity in 82 patients and does not report cesarean wound-complication incidence. Wound-infection risk factors are cited to Menacker and Hamilton 2010 (ref 7) plus Wloch et al. 2012 (ref 8); the Menacker NCHS data brief is about US cesarean-rate trends, not wound-infection predictors, while Wloch is an SSI risk-factor cohort.
*(producer: science_error; technique: factual_claim; location: Introduction, paragraph 2, references [1] and [7])*
> Postoperative wound complications are one of the great issues in CS with an incidence ranging from 3% to 30% [1].

### Level 2 — Minor error — Table 1 interrupted n=199 after losing 2 cannot equal 200-2

Methods and Figure 1 allocate 200 to interrupted, lose 1 to follow-up, and analyze 199. Table 1 prints Interrupted 199 (50.1) after lost follow-up of 2 women. Using Table 1's own operands, 200 minus 2 leaves 198, not 199. Both suture-type rows say lost follow-up of 2 women, which would be 4 exclusions, while the Table 1 header is n=397 after exclusion of 3 cases. The CONSORT cascade as printed (411-11=400; 200-1=199; 200-2=198) reconciles.
*(producer: science_error; technique: check_flow_arithmetic; location: Table 1, Suture Type rows versus Figure 1)*
> Interrupted 199(50.1)afterlostfollowupof2women
Reproduce: not available -- no runnable command -- the review's command did not match the tool's arguments.

## Findings set aside by the adjudicator (retained on the record)

- **merged into `f_a6b28cb05fe71636`**: Results print Table 1 counts as cohort percentages

## Reporting conventions

- **0 of 25** granularity checks reconcile only if the reporter TRUNCATES rather than rounds (SPSS's default, and several journal styles).
- **0 of 25** granularity checks reconcile only under the POPULATION (n) SD rather than the sample (n-1) SD (numpy's `std` default, Excel's STDEVP).
- These are NOT findings and no severity rests on them. Choosing a convention is not fabrication, and one instance is a house style. **The rate is the signal**: a high proportion beside genuine `impossible` findings is grounds to look harder, not evidence in itself.

## What we could NOT check

- **This section is not a coverage statement for this run.** The tool docket did not survive serialization -- the ledger records 26 check(s) that the filed report does not itemise -- so the territory below is what happened to be recorded, not the complement of what was examined.
- Table 4 odds ratios and p-values: Handoff to tool expert: reconstruct_2x2 / chi-square or Fisher from 10 vs 2, 9 vs 1, 14 vs 4, 17 vs 3 at n=198/199, and OR 5.239, 9.429, 3.709, 6.136 with printed CIs.
- Table 3 baseline p-values and SDs: Handoff to tool expert: independent-t recalculation and baseline dispersion/CSF on age, BMI, gestational age, sutures, blood loss, and depth.
- Table 2 means, SDs, and ranges: Handoff to tool expert: SD-range/GRIMMER on age 25-35, BMI printed range 23.0-45.0 versus inclusion BMI>30, operative time 30-60, blood loss 350-1000, depth 2.0-6.5.
- Table 6 logistic model: Handoff to tool expert: whether OR 7.743 for continuous versus interrupted is consistent with Table 5 counts 33/198 vs 9/199 after the printed covariates; eight covariates with 42 events.
- Four correlated wound outcomes: Handoff to tool expert: multiplicity; no correction is described for four primary-like 2x2 tests plus a composite.
- Table 1 composite 42 versus sum of four Yes counts 60: 12+10+18+20=60 specific events versus 42 women with any complication. Likely overlapping complications, which the paper never states. Not filed as arithmetic error.
- Data availability: No data-availability statement is present, so this is omission rather than state-but-withhold.
- Figure 1 CONSORT graphic: Counts were read from the caption and adjacent methods text; the diagram itself was not independently digitized.

## Limitations

- the tool_agent stage returned a TRUNCATED report (1 finding(s), no tools recorded in its coverage) (78 forensic calls on its ledger); retried once
- the tool_agent retry was empty too; its coverage is unusable
- the tool_agent ran 78 forensic tool call(s) but its report records no tools in `coverage`; those results did not survive into the docket and this review's coverage is understated
- Checks recorded as passing: 1 filed as findings, 19 on the tool ledger (18 of them per-cell checks collapsed by check_table); undecided: 0. The two counts differ, so the filed report does not describe everything the tools did.
- Channel `image_forensics` did not produce a retained result: did_not_run — image track disabled.

## Coverage

- statistics found: 0; checked: ?
- tools run: bayesian_table1_dispersion, check_count_percent, check_effect_plausibility, check_estimate_ci, check_sd_range, check_summation_batch, check_table, csf_test, detect_duplication, extract_pdf, flag_round_n, grim_check, grimmer_check, multiplicity_report, parse_cells_as_declared, parse_cells_typed, parse_table, recalc_chi_squared, recalc_independent_t, required_n, rivets_independent_t, sprite_reconstruct, stalt_check, statcheck  *(recovered from the tool-call ledger; the producer's own report listed none)*
- The docket did not survive serialization. The tool list above was rebuilt from the transcript, but the findings, anatomy and statistics register from those calls are gone and the counts below are not a coverage statement. See Limitations.

---
*pipeline 1.15.0 · run r_10a87ba9b98aec53 · analysed 2026-09-02T14:52:43Z · backend grok*

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

