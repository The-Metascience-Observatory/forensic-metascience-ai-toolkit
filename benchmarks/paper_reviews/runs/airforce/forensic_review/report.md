# Forensic review — paper

## Headline — Level 5 — Major error affecting conclusions

**Four flights were randomized but analyzed as 159 people**

Methods assigned two female flights to each briefing arm, then compared injuries and survey items with a person-level chi-squared test. With only two clusters per arm, any shared flight-level injury risk (drill instructors, barracks, training load) makes the reported MSKI p=.047 and BSI p=.037 anti-conservative. Those two p-values are the basis for the abstract's 43% and 66% relative risk reductions. A cluster-level analysis cannot be reconstructed because flight-level counts are not printed.

**Verdict: does_not_reconcile** — paper severity Level 5 — Major error affecting conclusions (confidence: medium)

## Summary

The abstract’s significant MSKI and BSI reductions (p=.047 and p=.037; 43% and 66% relative reductions) are person-level chi-squared tests after randomizing four flights, two per arm. Those p-values match unadjusted Pearson tests on 25/80 versus 14/79 MSKI and 12/80 versus 4/79 BSI. With two clusters per arm the tests are anti-conservative, and a valid cluster analysis is essentially unidentified. Table III survey percentages such as daily MVI 14.86% versus 34.25% cannot be produced from n=80 and n=79; they and the printed p-values match recovered item n of 74 and 73, contrary to the claim that all trainees completed questionnaires. Medical-hold 1.27% is impossible at n=80 (R GRIM). Printed ages 21±3 versus 23±5 contradict the no-difference claim (d=−0.48, CI −0.80 to −0.17). Injury percentages at the stated n, their Pearson p-values, BMI, and the n=80+79 flow do reconcile. The title credits MVI compliance although both arms received the same tablet. A corrigendum should qualify or withdraw the injury significance claims, print survey denominators, and correct the age sentence, medical-hold cell, and title. Nothing here established intent.

## Findings

### Level 5 — Major error affecting conclusions — Four flights were randomized but analyzed as 159 people

Methods assigned two female flights to each briefing arm, then compared injuries and survey items with a person-level chi-squared test. With only two clusters per arm, any shared flight-level injury risk (drill instructors, barracks, training load) makes the reported MSKI p=.047 and BSI p=.037 anti-conservative. Those two p-values are the basis for the abstract's 43% and 66% relative risk reductions. A cluster-level analysis cannot be reconstructed because flight-level counts are not printed.
*(producer: science_error; technique: not_computational; location: Methods, randomization and statistical analysis; Table III injury rows)*
> These flights were randomly assigned to cohorts, which would receive one of two MVI-briefing modalities.

### Level 3 — Notable error — Title credits MVI compliance; both arms received the MVI

The title states that multivitamin compliance reduces injuries. The randomized contrast is briefing modality (video versus video plus in-person SME brief). Both cohorts received the same prenatal MVI. No unsupplemented control and no mediation test of compliance are reported. The Discussion infers that the brief improved compliance which in turn reduced injuries. That causal chain is not identified by the design, which the authors themselves list as limitation (2).
*(producer: science_error; technique: not_computational; location: Title vs Methods limitation (2) and Discussion paragraph 1)*
> we infer that incorporating an in-person brief from SMEs improved compliance with the MVI which in turn significantly reduced injuries.

### Level 3 — Notable error — Table III survey percentages cannot come from n=80 and n=79

Table III headers are n=80 and n=79 (total 159), but reconstruct_2x2 finds no column split summing to 159 that produces the paired survey percentages (daily MVI 14.86 vs 34.25, most days 37.84 vs 63.01, never 20.27 vs 8.22, found-brief-effective 95.89 vs 98.63). R GRIM agrees 14.86% is impossible at n=80. Unique recovered bases (video compliance 11/74, 28/74, 15/74; in-person 25/73, 46/73, 6/73; brief items on n=73) also reproduce the printed Pearson p-values (.0063, .0023, .037, .007). Methods still state that all trainees completed questionnaires. Compliance contrasts remain; the printed denominators and completeness claim do not.
*(producer: science_error; technique: reconstruct_2x2; location: Table III survey block vs Methods questionnaire sentence)*
> Furthermore, all trainees completed questionnaires regarding their perceptions regarding the usefulness and effectiveness of their MVI briefing and were asked to quantify their MVI compliance.
*Merged pattern: absorbs 1 sibling finding(s).*

### Level 3 — Notable error — Printed ages contradict the no-difference claim

Results state that no significant differences in age or BMI were detected. Table II prints age 21±3 years (n=80) versus 23±5 (n=79). check_effect_plausibility on those printed means and SDs gives d=-0.48, 95% CI [-0.80, -0.17], which excludes zero. An equal-variance t on the same inputs is t=-3.06, df=157, p=0.0026. BMI 24.1±2.6 versus 24.0±2.8 is compatible with no difference (p=0.82). Age is printed to zero decimals, so unrounded means could be closer; the printed figures as they stand do not support the no-difference sentence.
*(producer: science_error; technique: internal_contradiction; location: Results paragraph 1 vs Table II Age row)*
> No significant differences in age or BMI between cohorts were detected.

### Level 2 — Minor error — BSI 66% relative reduction exceeds the Lappe Ca-D trial

The paper reports a 66% relative and 10% absolute reduction in BSI (15% vs 5.06%) after a briefing that changed self-reported daily MVI use from 14.86% to 34.25%. Both arms received the same tablet (400 IU vitamin D and 200 mg calcium). Lappe et al., cited as the dose benchmark, randomized 5201 female Navy recruits to 2000 mg calcium plus 800 IU vitamin D versus placebo and found a 20% ITT reduction (5.3% vs 6.6%). Cohen's d on the reconstructed BSI proportions is 0.33 (95% CI 0.02-0.65), within usual medicine-RCT range; the relative-risk comparison to Lappe is the implausible piece. Magnitude is capped at suspicious.
*(producer: science_error; technique: check_effect_plausibility; location: Discussion paragraph 1 vs Introduction Lappe citation)*
> The relative and absolute risk reductions for diagnosis with BSI were 66% and 10%, respectively

### Level 2 — Minor error — Table III medical-hold 1.27% is not attainable at n=80

Medical hold is printed as 1.27% in both columns, under headers n=80 and n=79, with p=.99. Reconstruct_2x2 finds no 2x2 whose column totals sum to 159 and that reproduces both 1.27% values at two decimals. Results state there were no losses of routinely collected data, so the injury/training denominators should be 80 and 79. One event in 79 is 1.27%; one event in 80 is 1.25%, which would print as 1.25 not 1.27. The video-only cell matches the in-person value rather than n=80. Recycle-fitness 2.50% and 2.53% do match 2/80 and 2/79.
*(producer: science_error; technique: reconstruct_2x2; location: Table III, Medical hold row)*
> There were no losses or exclusions of routinely collected and linked data.

### Level 2 — Minor error — Table I lists vitamin C as 100 μg at 83% daily value

Table I prints vitamin C (ascorbic acid) as 100 μg and 83% daily value for pregnant and lactating women. NIH ODS RDAs for vitamin C are in milligrams: 85 mg in pregnancy and 120 mg in lactation. 100 mg of 120 mg is 83%, matching the printed percent; 100 μg of 120 mg is 0.08%. Typical prenatal labels use 100 mg ascorbic acid. Adjacent rows correctly use μg for vitamins A, D, folate, and B12 and mg for iron, calcium, and zinc, so the vitamin C unit is a 1000-fold error relative to the printed %DV.
*(producer: science_error; technique: factual_claim; location: Table I, Vitamin C row)*
Reproduce: not available -- no runnable command -- the review's command did not match the tool's arguments.

### Level 2 — Minor error — Stated power analysis cannot produce n=77 per cohort

Methods say alpha 0.05, power 0.99, and a 25% relatively greater daily MVI compliance yielded 77 trainees per cohort. A two-proportion calculation at power 0.99 for a 25% relative increase needs hundreds to thousands per arm across baselines 0.15-0.50 (e.g. 0.15 vs 0.1875 needs n=3655). Even at the conventional power 0.80 the same relative effect needs n=1562 at baseline 0.15. A 25 percentage-point increase at power 0.80 gives n=48-60, nearer 77, so the printed 'relatively greater' and 'power of 0.99' jointly do not produce the stated sample size.
*(producer: science_error; technique: not_computational; location: Methods, power analysis paragraph)*
> a power analysis calculation was completed using α≤ 0.05 for the significance level, a power of 0.99. We estimated a 25% relatively greater daily MVI compliance in trainees receiving the in-person brief compared to those viewing the video alone, which yielded a need for each cohort to have 77 trainees to demonstrate a significant difference.

### Level 2 — Minor error — Reference 8 does not support the 22 mg iron claim

The Introduction states that 27 mg of iron approximates the estimated 22 mg daily requirement for females in military training and cites reference 8. Reference 8 is Martineau et al., BMJ 2017, an IPD meta-analysis of vitamin D for acute respiratory tract infections. It does not estimate iron requirements. The paper's own reference 17 (IOM mineral requirements for military personnel) is the work that would support a training-adjusted iron figure.
*(producer: science_error; technique: factual_claim; location: Introduction, MVI contents paragraph; References 8 and 17)*

### Level 1 — Trivial error — Results sentence repeats the in-person-cohort clause

The compliance Results paragraph prints the same clause twice in succession: 'a significantly higher proportion within the in-person cohort, a significantly higher proportion within the in-person cohort'. The numbers that follow (63.01% vs 37.84%, p=.0023) are otherwise the Table III most-days row. Cosmetic duplication in a load-bearing Results sentence.
*(producer: science_error; technique: not_computational; location: Results, compliance paragraph)*
> compared to the video-only cohort, a significantly higher proportion within the in-person cohort, a significantly higher proportion within the in-person cohort reported taking the MVI on most days (or more) (63.01% vs.  37.84%, P = .0023)

## Findings set aside by the adjudicator (retained on the record)

- **merged into `f_95a86369714ce8ef`**: All-data-included claim omits survey denominators

## What we could NOT check

- **This section is not a coverage statement for this run.** The tool docket did not survive serialization -- the ledger records 12 check(s) that the filed report does not itemise -- so the territory below is what happened to be recorded, not the complement of what was examined.
- Table III chi-squared p-values (MSKI .047, BSI .037, daily .0063): Handoff to tool expert: reconstructed MSKI 25/80 vs 14/79 and BSI 12/80 vs 4/79 match the printed uncorrected chi-square p-values; Yates-corrected p=0.072 and 0.069 would both exceed 0.05. Daily p=.0063 matches 11/74 vs 25/73, i.e. the implied survey n not the table header.
- Table III survey cell counts: Counts are not printed. Implied denominators come from analysis_code/001_implied_denominators_table3.py (unique n=73 or 74). grim_percentage was not available on this MCP; reconstruct_2x2 was used instead.
- Flight-level injury counts: Four flights were the randomized units; per-flight MSKI/BSI counts are not reported, so ICC and a cluster-level test cannot be computed.
- Age test details: No t, df, or p is printed for the 'no significant differences in age' claim. The contradiction uses printed means/SDs only; unrounded ages could differ.
- Supplements: Instruction is not to read supplements; none were opened.
- Unconsented exempt RCT: Trainees were not told they were in a randomized experiment; IRB number FWH20220101E is given as exempt QI. Disclosed, so not a withheld-ethics finding; journal ethics of publishing that design is outside this beat.

## Limitations

- the tool_agent stage returned an EMPTY report (0 forensic calls on its ledger); retried once
- the tool_agent retry was empty too; its coverage is unusable
- Checks recorded as passing: 1; undecided: 0.
- Channel `image_forensics` did not produce a retained result: did_not_run — image track disabled.

## Coverage

- statistics found: 0; checked: ?
- tools run: none recorded
- The docket did not survive serialization. This block is EMPTY BECAUSE OF THAT, not because nothing ran. See Limitations.

---
*pipeline 1.15.0 · run r_efb46f129a408c14 · analysed 2026-09-02T13:56:30Z · backend grok*

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

