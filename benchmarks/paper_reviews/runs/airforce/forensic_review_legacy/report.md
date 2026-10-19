# Forensic review -- Kasper et al. 2024

*Analysed 2026-09-02 13:11 UTC  ·  pipeline v1.15.0 (g4a7971102983, uncommitted changes)*

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## Multivitamin Compliance Reduces Injuries of Female Recruits at Air Force Basic Training: A Randomized Controlled Cohort Study
*Korey B. Kasper, Meredith Cockerell, Clarissa Escamilla, Richard Gonzalez. Military Medicine. 2024. doi:10.1093/milmed/usae044*

**Design:** cluster-randomized (flights) controlled cohort study of briefing modality among female BMT trainees

<sub>Analysed as `paper`</sub>

> **IMPOSSIBLE** — Table III prints video-only medical hold as 1.27% of n = 80, a share no integer count at that n can produce (1/80 is 1.25%; 1.27% is 1/79, the adjacent cell).
>
> **In plain terms:** The paper says 1.27% of the 80 video-only trainees went on medical hold, but one person out of 80 is 1.25%, not 1.27%. That 1.27% is exactly one person in the other group of 79, and it is printed in the next cell.
>
> **Evidence:** Table III: Medical hold 1.27 | 1.27 | .99, under headers Video-only cohort (n = 80) and In-person cohort (n = 79). Results: 'There were no losses or exclusions of routinely collected and linked data.'
> **Rests on:** a constraint the paper itself states

**Verdict: unresolved** (confidence: high)

_Something could not be settled -- an anomaly that does not resolve either way, an extraction we could not confirm, or a check that could not run on the claim that matters. What it was is named. It is not a finding of misconduct, and it is not a negative result: the middle rung of three means we could not tell, which is a fact about this analysis and not about the paper._

> **Table coverage:** 22 of 33 checkable cells were checked cell by cell, and 5 further table rows were checked in batch by check_summation_batch. The two counts are of different things and are not added: the batch tools report rows, not the cell identifiers this census uses, so the true combined coverage is somewhere between 22 and 27 of 33. A further 111 per-cell checks ran (`check_effect_plausibility`, `check_ratio`, `check_statistic_bounds`, `check_summation`, `detect_duplication`, `flag_round_n`, `flag_uninformative_stat`, `grim_check`, `grim_percentage`, `grim_sweep`, `grimmer_check`, `r_grim_ground_truth`, `recalc_chi_squared`, `recalc_independent_t`, `reconstruct_2x2`) and report no cell ids at all, so the top of that range is a floor rather than a ceiling.

## What the authors shared

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

1 study/studies, 13 variables, 12 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| bmt_mvi_brief | Female BMT trainees, December 2021 squadron, video-only vs in-person MVI briefing | cluster_rct | 159 | trainee | yes |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Age, year | ratio | discrete | range not stated | years | measured | none -- not integer-valued | medium |
| BMI | ratio | continuous | range not stated | kg/m^2 | other: height (meters) and weight (kilograms) marked BMI calculated using height (meters) and weight (kilograms). | none -- not integer-valued | high |
| Found brief effective in explaining why MVI prescribed | nominal | discrete | yes; no | - | percentage: questionnaire item | DEBIT; percentage GRIM | high |
| Confident in understanding why MVI was prescribed | nominal | discrete | yes; no | - | percentage | DEBIT; percentage GRIM | high |
| Took MVI daily | nominal | discrete | yes; no | - | percentage | DEBIT; percentage GRIM | high |
| Took MVI most days | nominal | discrete | Took MVI most days; Took MVI most days (or more) | - | percentage: questionnaire; table and prose labels disagree on nesting with daily | DEBIT; percentage GRIM | medium |
| Never took MVI | nominal | discrete | yes; no | - | percentage | DEBIT; percentage GRIM | high |
| MSKI | nominal | discrete | diagnosed MSKI; no MSKI | - | percentage: sports medicine MSKI database | DEBIT; percentage GRIM | high |
| BSI | nominal | discrete | diagnosed bone stress injury; no BSI | - | percentage | DEBIT; percentage GRIM | high |
| Medical hold | nominal | discrete | yes; no | - | percentage | DEBIT; percentage GRIM | high |
| Recycle: admin issue | nominal | discrete | yes; no | - | percentage | DEBIT; percentage GRIM | high |
| Recycle: fitness failure | nominal | discrete | yes; no | - | percentage | DEBIT; percentage GRIM | high |
| Briefing modality | nominal | discrete | video-only; in-person | - | recoded: flight assignment | percentage GRIM on cell counts | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Table III, Found brief effective | chi_squared | Found brief effective in explaining why MVI prescribed (binary) | Briefing modality | 146 | ? | none reported |
| Table III, Confident | chi_squared | Confident in understanding why MVI was prescribed (binary) | Briefing modality | 146 | ? | none reported |
| Table III, Took MVI daily | chi_squared | Took MVI daily (binary) | Briefing modality | 147 | ? | none reported |
| Table III, Took MVI most days | chi_squared | Took MVI most days (binary) | Briefing modality | 147 | ? | none reported |
| Table III, Never took MVI | chi_squared | Never took MVI (binary) | Briefing modality | 147 | ? | none reported |
| Table III, MSKI | chi_squared | MSKI (binary) | Briefing modality | 159 | ? | none reported |
| Table III, BSI | chi_squared | BSI (binary) | Briefing modality | 159 | ? | none reported |
| Table III, Medical hold | chi_squared | Medical hold (binary) | Briefing modality | 159 | ? | none reported |
| Table III, Recycle: admin issue | chi_squared | Recycle: admin issue (binary) | Briefing modality | 159 | ? | none reported |
| Table III, Recycle: fitness failure | chi_squared | Recycle: fitness failure (binary) | Briefing modality | 159 | ? | none reported |
| Table II / Results, age comparison (p not printed) | independent_t | Age, year (continuous) | Briefing modality | 159 | ? | none reported |
| Table II / Results, BMI comparison (p not printed) | independent_t | BMI (continuous) | Briefing modality | 159 | ? | none reported |

_12 of 12 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. Video-only medical hold of 1.27% cannot be produced from the stated n of 80  [IMPOSSIBLE | confidence: high]

**In plain terms.** The paper reports that 1.27% of 80 video-only trainees went on medical hold. One person out of 80 is 1.25%. 1.27% is one person out of 79 — the other group's size — and that same 1.27% sits in the next cell. The likeliest ordinary cause is that 1.27 was copied into both columns. The finding of no difference in medical hold is unchanged (one event in each group still gives p = .99).

- **Location:** Table III, Medical hold row, video-only column
- **Reported:** Medical hold 1.27% (video-only, n = 80) and 1.27% (in-person, n = 79), p = .99. The paper states there were no losses or exclusions of routinely collected and linked data.
- **Computed:** R scrutiny (percentage share) rejects 1.27% at n = 80 and accepts it at n = 79; 1.25% at n = 80 is consistent (1/80). Pearson chi-squared on 1/80 vs 1/79 gives p = 0.992858, matching the printed .99. Stage-1 GRIM: implied count at n = 80 is 1.016; nearest attainable share is 1/80 = 1.25%.
- **As printed in the paper:** **Table III, Medical hold row, video-only** -- “| Medical hold | 1.27 | 1.27 | .99 |” _(found in the paper's text)_
- **Assumptions:** The medical-hold percentage is a share of enrolled trainees. The paper's 'no losses or exclusions of routinely collected and linked data' makes n = 80 the analysis denominator for this row, not a survey-missingness problem.
- **Whose standard:** the paper's own promise. The paper promised this itself -- a guideline it claims to follow, its registration, its stated outcomes or thresholds. We are holding it to its own word.
- **Consequence:** changes no significance decision -- The printed p = .99 still matches one medical-hold event in each arm; only the video-only percentage is misstated, and training delays are not a load-bearing claim. (asserted, not computed)

### 2. Flights were randomized but injuries were tested as if trainees were independent  [SUSPICIOUS | confidence: medium]

**In plain terms.** Whole groups of about 40 trainees, not individual people, were assigned to the video or the in-person briefing, but the injury tests treated each trainee as an independent coin-flip. That makes a p-value of .047 look more decisive than the design supports. The authors list this as a limitation; they do not say how much it moves the result, and the paper does not contain the number needed to find out.

- **Location:** Methods, randomization and analysis; Discussion limitations
- **Reported:** Four flights were randomly assigned to two briefing modalities. 'Associations between categorical variables were analyzed using the chi-squared test.' Limitation (1): 'it used block rather than individual randomization.'
- **Computed:** No intra-cluster correlation is printed, so a design effect cannot be recovered. Two clusters per arm is too few for a cluster-robust variance. Individual-level chi-squared on this design is anti-conservative for the injury tests that carry the title (p = .047 and p = .037).
- **As printed in the paper:** “These flights were randomly assigned to cohorts, which would receive one of two MVI-briefing modalities.” _(found in the paper's text)_
- **Assumptions:** This is a reviewer-supplied reporting and analysis standard (CONSORT 2010 cluster-trial extension, item 12a: how clustering was taken into account), not a standard the paper claims to follow. The authors already name block randomization as a limitation. Severity is capped at suspicious because the obligation is external.
- **Whose standard:** a named guideline. An external reporting standard (CONSORT, STROBE, ARRIVE, PRISMA, CHEERS) and a specific item within it, named so you can look it up.
- **Consequence:** 2 stated claims affected -- Ignoring clustering in a two-cluster-per-arm design anti-conservatively inflates the MSKI and BSI chi-squared tests that carry the paper's injury claims; the design effect is not recoverable from the printed numbers. (asserted, not computed)

### 3. Printed age means are too coarse to support the claim of no age difference  [SUSPICIOUS | confidence: medium]

**In plain terms.** The paper says the two groups did not differ in age, but it only prints ages as 21 versus 23 years with no test. Numbers that coarse cannot show whether that claim is true. If the in-person group really was older, that could matter for injury comparisons; the printed figures do not settle it. Body-mass index, printed more finely, is compatible with no difference.

- **Location:** Table II, Age row; Results sentence claiming no age difference
- **Reported:** Age 21 ± 3 (video-only, n = 80) versus 23 ± 5 (in-person, n = 79). 'No significant differences in age or BMI between cohorts were detected.' No t, df, or p is printed for age.
- **Computed:** Stage-1 uninformative-stat check on the 0-decimal means: attainable p-range [6e-07, 0.135], which straddles 0.05. Point Welch t from the rounded means is p = 0.002753 (Student p = 0.002581). Hedges' g from the same rounded statistics is −0.483, 95% CI [−0.801, −0.170]. BMI 24.1 ± 2.6 vs 24.0 ± 2.8 gives Welch p = 0.816, compatible with the NS claim.
- **As printed in the paper:** **Table II, Age row** -- “| Age, year | 21 ± 3 | 23 ± 5 |” _(found in the paper's text)_
- **Assumptions:** The 0-decimal means and SDs are rounded as printed. The point p from those rounded values is not evidence the authors missed a significant difference: the paper's NS claim remains compatible with the rounding interval. This is the Heathers uninformative-statistics heuristic, a reviewer-supplied standard, so the finding is capped at suspicious. The flag-uninformative tool could not be re-run at this stage (denied); the p-range is the Stage-1 result, and the point t and effect size were re-run.
- **Whose standard:** a norm we supplied (capped at `suspicious`). A standard the REVIEWER supplied, which this paper never claimed to follow. It may still be the right standard -- but it is ours, not theirs, and findings resting on one are capped.
- **Consequence:** 1 stated claim affected -- The 0-decimal age means are too coarse to confirm or refute the 'no significant difference in age' claim; a true age difference would be a confounder of the injury comparison. (asserted, not computed)

### 4. Survey percentages in Table III cannot be produced from the printed n of 80 and 79  [SUSPICIOUS | confidence: high]

**In plain terms.** The paper says every trainee filled in the questionnaire and heads those rows with 80 and 79 people. The percentages only work if about 73 or 74 people answered, and the printed p-values match those smaller counts. About six or seven people's answers are missing from each group. The compliance comparisons still go in the same direction once that smaller sample is used; the table simply does not say that was the sample.

- **Location:** Table III, briefing-effectiveness and MVI-compliance survey rows; Methods completeness sentence
- **Reported:** Column headers n = 80 and n = 79. Video-only: 95.89, 90.41, 14.86, 37.84, 20.27. In-person: 98.63, 34.25, 63.01, 8.22 (100% confidence is the remaining survey cell). Methods: 'all trainees completed questionnaires regarding their perceptions regarding the usefulness and effectiveness of their MVI briefing and were asked to quantify their MVI compliance.'
- **Computed:** R scrutiny rejects those two-decimal shares at n = 80 and n = 79 and accepts them at n = 73 (video briefing items 95.89 and 90.41; all four in-person survey items) and n = 74 (video compliance 14.86, 37.84, 20.27). Stage-1 grim_sweep found no joint n ≤ 80 for the five video-only survey percentages. Pearson chi-squared on the reconstructed tables 70/73 vs 72/73, 66/73 vs 73/73, 11/74 vs 25/73, 28/74 vs 46/73, and 15/74 vs 6/73 reproduces the printed p-values .31, .007, .0063, .0023, and .037. Missingness versus enrolment is 6–7 people per arm.
- **As printed in the paper:** **Table III, video-only survey percentages** -- “Video- only cohort ( n = 80) (%)” _(found in the paper's text)_
- **Assumptions:** The survey percentages are shares of respondents on each item. Item-level skip after a form was handed in remains possible; 'completed questionnaires' is not an explicit per-item completeness statement. The 6–7 person gap exceeds the three-patient-or-5%-of-n missingness bound used to separate ordinary available-case analysis from a reporting problem.
- **Whose standard:** the paper's own promise. The paper promised this itself -- a guideline it claims to follow, its registration, its stated outcomes or thresholds. We are holding it to its own word.
- **Consequence:** changes no significance decision -- Printed survey p-values match Pearson chi-squared at the implied n of 73–74, so the significance claims survive; the column headers 80 and 79 are not the analysis denominators. (asserted, not computed)

### 5. Vitamin C listed as 100 micrograms at 83% daily value  [SUSPICIOUS | confidence: high]

**In plain terms.** The table that describes the tablet lists vitamin C as 100 micrograms with 83% of the daily value. A microgram dose that large a share of the daily value cannot be right: neighbouring vitamins that really are measured in micrograms are listed that way, and 83% is the usual pairing with 100 milligrams. This is a label error in the description of what was handed out, not an error in the injury counts.

- **Location:** Table I, Vitamin C row
- **Reported:** Vitamin C (as ascorbic acid) 100 μg, 83% daily value for pregnant and lactating women. Adjacent Vitamin D is 10 μg (400 IU) at 67% DV; vitamins A, folate, and B12 also use μg.
- **Computed:** No arithmetic on a printed reference DV is possible because the paper does not print those reference amounts. 100 μg at 83% DV is incompatible with the μg unit used correctly on the adjacent rows: 83% of a pregnant/lactating vitamin-C daily value is the conventional pairing with 100 mg, not 100 μg.
- **As printed in the paper:** “| Vitamin C (as ascorbic acid) | 100 μ g | 83 |” _(found in the paper's text)_
- **Assumptions:** The incompatibility is between the printed unit and the printed %DV in the same row, read against adjacent rows that use μg for genuinely microgram nutrients. This does not change any trial outcome statistic.
- **Whose standard:** logic or arithmetic. The paper contradicts itself, or the arithmetic does not work. Nothing outside the document is needed to see it.
- **Consequence:** changes no significance decision -- A unit error in the supplement-facts table used to describe the intervention; it does not change the trial's outcome statistics. (asserted, not computed)

## What we could NOT check

- **Power analysis control-arm compliance rate** — Paper states a 25% relatively greater daily MVI compliance and n = 77/group at power 0.99, but never prints the control proportion needed to convert that relative increase into a two-proportion effect size.
- **Age and BMI hypothesis tests** — Paper claims no significant differences but prints no t, df, or p. Recalculation from 0-decimal age means is uninformative (p-range straddles 0.05).
- **Null claims (training delays; age/BMI)** — No confidence intervals are printed, so the largest effect compatible with those nulls cannot be bounded.
- **Publisher XML / HTML** — No JATS XML or publisher HTML was present; tables were taken from the PDF extraction and body.md and agreed.
- **Supplementary data file** — None provided. DATA AVAILABILITY says all relevant data are in the manuscript.
- **Figures** — Paper has no data figures. extract_figures was not run. Nothing unique is carried only in a plot.
- **Table I percent-daily-value arithmetic** — Reference DV amounts are not printed, so %DV cannot be verified except via the Vitamin C unit incompatibility.
- **CSF / Table 1 dispersion** — Only two baseline variables, no printed baseline p-values, and allocation was by flight (cluster). Dispersion tools refuse or are uninformative here.
- **Survey item wording and missingness counts** — Questionnaire items and per-item n are not printed; implied ns 73/74 come from GRIM, not from a reported denominator.
- **Intra-cluster correlation / design effect** — No ICC is printed, so the individual-level chi-squared tests cannot be re-run with a cluster adjustment.
- **table rows Found brief effective in explaining why MVI prescribed, Found brief effective in explaining why MVI prescribed, Confident in understanding why MVI was prescribed, Confident in understanding why MVI was prescribed, Took MVI daily, Took MVI daily and 16 more** — check_count_percent not run: required inputs not present in this cell <sub>(22 cells; recorded by the dispatcher, not by the reviewer)</sub>
- **table rows Found brief effective in explaining why MVI prescribed, Confident in understanding why MVI was prescribed, Took MVI daily, Took MVI most days, Never took MVI, MSKI and 5 more** — grim_percentage not run: grim_percentage needs n and this cell carries none, but its col_label prints 'n = 80'. Pass n=80 explicitly to run this check -- it is not used automatically, because an enrolled n is not always the n behind a given row, and this check accuses when n is too large. <sub>(11 cells; recorded by the dispatcher, not by the reviewer)</sub>
- **table rows Found brief effective in explaining why MVI prescribed, Confident in understanding why MVI was prescribed, Took MVI daily, Took MVI most days, Never took MVI, MSKI and 5 more** — check_count_percent not run: check_count_percent needs n and this cell carries none, but its col_label prints 'n = 80'. Pass n=80 explicitly to run this check -- it is not used automatically, because an enrolled n is not always the n behind a given row, and this check accuses when n is too large. <sub>(11 cells; recorded by the dispatcher, not by the reviewer)</sub>
- **table rows Found brief effective in explaining why MVI prescribed, Confident in understanding why MVI was prescribed, Took MVI daily, Took MVI most days, Never took MVI, MSKI and 5 more** — grim_percentage not run: grim_percentage needs n and this cell carries none, but its col_label prints 'n = 79'. Pass n=79 explicitly to run this check -- it is not used automatically, because an enrolled n is not always the n behind a given row, and this check accuses when n is too large. <sub>(11 cells; recorded by the dispatcher, not by the reviewer)</sub>
- **table rows Found brief effective in explaining why MVI prescribed, Confident in understanding why MVI was prescribed, Took MVI daily, Took MVI most days, Never took MVI, MSKI and 5 more** — check_count_percent not run: check_count_percent needs n and this cell carries none, but its col_label prints 'n = 79'. Pass n=79 explicitly to run this check -- it is not used automatically, because an enrolled n is not always the n behind a given row, and this check accuses when n is too large. <sub>(11 cells; recorded by the dispatcher, not by the reviewer)</sub>
- **table rows Age, year, Age, year, BMI, BMI** — check_sd_or_se not run: check_sd_or_se needs n and this cell carries none; supply n for this row (the participants paragraph or the table footnote usually states it) <sub>(4 cells; recorded by the dispatcher, not by the reviewer)</sub>
- **table rows Total, n, Total, n** — no applicable check not run: a bare count contributes to table-level checks only <sub>(2 cells; recorded by the dispatcher, not by the reviewer)</sub>

## Questions for the authors

_Each of these is answerable from what the authors already have. None presupposes an error on their part: an inconsistency is far more often a reporting slip, or a mistake by this tool in reading the number off the page, than anything else._

1. Table III prints medical hold as 1.27% in the video-only column (n = 80) and 1.27% in the in-person column (n = 79). One of 79 is 1.27%; one of 80 is 1.25%. Could you send the medical-hold counts in each arm?
   <sub>Would resolve: Settles whether the video-only 1.27% is a copy of the adjacent cell or a different denominator.</sub>
2. Table III survey percentages (for example 95.89% and 14.86% in the video-only column, 98.63% and 34.25% in the in-person column) do not match integer counts at the printed n of 80 and 79, but do match n = 73 and n = 74, and the printed p-values match chi-squared tests on those smaller bases. Methods says all trainees completed the questionnaires. Could you send the number of respondents for each survey item?
   <sub>Would resolve: Settles whether the survey analysis used item-level available cases of 73–74 rather than the enrolment headers.</sub>
3. Table II reports age as 21 ± 3 versus 23 ± 5 years and the Results text says no significant age difference was detected, with no t or p printed. Could you send the unrounded means, SDs, and the test used for that comparison?
   <sub>Would resolve: The 0-decimal means leave a p-range that straddles 0.05, so the NS age claim cannot be checked from the printed figures.</sub>
4. Table I lists Vitamin C as 100 μg at 83% daily value for pregnant and lactating women. Could you confirm whether the tablet contains 100 mg or 100 μg?
   <sub>Would resolve: The printed unit is incompatible with the printed %DV given how μg is used on adjacent rows.</sub>
5. Age and BMI hypothesis tests: Would you be able to share the underlying values for this? Our reading of the article as published did not locate them, though they may well be somewhere we did not look, or in material we were not able to obtain. Summary statistics on their own would be enough.
   <sub>Would resolve: Promoted from a check this review could not run. The review recorded: “Paper claims no significant differences but prints no t, df, or p. Recalculation from 0-decimal age means is uninformative (p-range straddles 0.05).” That is quoted rather than paraphrased, because the sentence is this review's reading and not a verified fact about the article -- if it is mistaken, the answer is simply that the values are where we did not look.</sub>

## What was looked at, beyond the numbers

_Three checks sit outside the arithmetic. Whether each one ran on this paper is a property of how this run was invoked, not of the paper -- and a check that did not run has cleared nothing._

- **Figures** — **did not run**. This analysis read the paper as text; figures were not inspected, so anomalies visible only in plots would not be detected.
- **Image forensics** — **did not run**. No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.
- **Tortured phrases** — **ran**. Screening for tortured phrases was limited to matching against a fixed fingerprint dictionary (tortured phrases, LLM boilerplate, tortured acronyms), computed locally. Novel or unlisted paraphrases, non-English text, and any rewording not in the dictionary were NOT checked, and their absence here is not evidence of their absence in the paper.

## Limitations

- quote_not_located fired on all six Stage-1 accusations. Every quoted span is present verbatim in body.md (markdown pipe tables and Methods/Results prose). The global cause is table-pipe versus PDF text-layer matching, not missing evidence; it is recorded once here and not as six separate weaknesses.
- Python grim_percentage, grim_sweep, flag_uninformative_stat, and check_summation were denied at this stage. Medical-hold and survey GRIM cells were cross-checked with R scrutiny (percentage_share); chi-squared, 2×2 reconstruction, effect size, ratios, multiplicity, and t-tests were re-run. The age p-range [6e-07, 0.135] is the Stage-1 uninformative-stat result and could not be re-derived here.
- Figures were not read. The paper has no data figures; nothing unique is carried only in a plot.
- No JATS XML or publisher HTML was present. Tables were read from body.md.
- No participant-level file is held. DATA AVAILABILITY states that all relevant data are in the manuscript; survey analysed n (73–74) is not among the included figures.
- Whether similar denominator or copy-across errors appear in other papers by these authors, and what injury reductions other briefing or supplement studies in this setting report, are outside the reach of a single-paper check.

## Coverage

- **Statistics found:** 72; **checked:** 58
- **Tools run:** extract_pdf, extract_xml, statcheck, parse_table, parse_cells_typed, check_table, grim_percentage, grim_sweep, grim_check, grimmer_check, r_grim_ground_truth, recalc_chi_squared, recalc_independent_t, flag_uninformative_stat, check_effect_plausibility, check_ratio, check_summation_batch, reconstruct_2x2, verify_power_analysis, required_n, multiplicity_report, flag_round_n, detect_duplication, check_statistic_bounds
- **Tables checked:** Table I, Table II, Table III
- **Checkable table cells:** 33 of 69 surveyed; **checked:** 22
    - 4 could not be checked without knowing what kind of quantity the row reports
    - 29 were missing an input: n (29)
- **Every checkable item:** 106 registered; 69 refused with a stated reason; **37 outstanding**
    - how many were CHECKED is not measured -- no persisted item identity joins a tool call back to a manifest row, so how many items were CHECKED cannot be counted. This is not a count of zero. This is not a count of zero.
- **Stage-1 findings:** 26 raised; 8 carried into this report; 18 not carried
- **Where a check and this review disagreed:** 2 sweep findings recorded a severity the validated check behind them did not return (0 upgraded, 2 downgraded). 1 is an explained downgrade on an entry above, counted here and not marked there: the check said more, this review said less and said why, which is what stage 2 is for. 1 sits on a sweep finding no entry in this report cites, so this line is the only place it appears.
- **Traceable to the page:** 129 of 129 checks recorded the passage their numbers were read from; 127 of those were located in the paper's own text.
- **2 quoted passages are ours, not the paper's.** Every number in them was found in the paper, but the sentence around those numbers was assembled by this review and does not appear as written -- so do not search the PDF for it. The CHECK is sourced; only the quotation marks over-promise.

## Narrative

This study assigns four flights of female Air Force basic trainees (80 to a dietitian video, 79 to the same video plus an in-person briefing) and reports that the in-person briefing raised self-reported multivitamin compliance and cut musculoskeletal injury (31.25% vs 17.72%, p = .047) and bone-stress injury (15% vs 5.06%, p = .037).

Twenty-four of thirty-five numeric checks passed, including nine collapsed table-level passes. The injury percentages uniquely reconstruct as 25/80 versus 14/79 and 12/80 versus 4/79. Pearson chi-squared on those tables reproduces the printed p-values. The 43% and 66% relative risk reductions, the 7.4 number-needed-to-brief, and 5.4 injuries prevented per briefing of 40 all follow from the printed rates. Cohort sizes 80 + 79 = 159. BMI 24.1 ± 2.6 versus 24.0 ± 2.8 is compatible with no difference (Welch p = 0.816). Those are the numbers the title rests on, and they add up.

What does not add up is a training-delay cell in the same table. Medical hold is printed as 1.27% in both arms. One event in 79 trainees is 1.27%; one event in 80 is 1.25%. Both the Python GRIM engine and R scrutiny reject 1.27% at n = 80 and accept it at n = 79. The paper states there were no losses of routinely collected data, so 80 is the denominator that cell owed. The printed p = .99 still matches one event in each arm, so the non-difference claim is intact; the video-only percentage is the adjacent cell copied over.

The survey block of Table III is a different denominator problem. Methods says all trainees completed the questionnaires, and the columns are headed n = 80 and n = 79. Nine of ten two-decimal survey percentages are impossible at those ns. They are uniquely possible at 73 (briefing items) and 74 (compliance items) in the video-only arm and at 73 in the in-person arm — six or seven people short of enrolment. Pearson chi-squared on those reconstructed tables reproduces every printed survey p-value, so the tests used the smaller bases. Item-level skip after handing in a form is the ordinary reading; the completeness sentence is what makes the gap a reporting problem rather than a silent available-case convention.

Two further open questions, neither an arithmetic break in a printed figure. Allocation was by flight (two clusters per arm) and the analysis was an individual-level chi-squared; the authors list block randomization as a limitation, and that design makes p = .047 and p = .037 anti-conservative by an unknown factor. Age is printed as 21 ± 3 versus 23 ± 5 years with no t or p; the rounded point comparison would be a medium difference, but the 0-decimal rounding window for p straddles .05, so the claim of no age difference is uncheckable. Table I lists vitamin C as 100 μg at 83% daily value, which cannot be the same quantity as the milligram-scale pairing those facts conventionally describe.

Yates and Fisher on the injury tables would not meet α = 0.05; the paper named chi-squared and expected counts exceed 5, so Pearson is the test it ran. Uncorrected testing of ten Table III rows is ordinary; under that ten-test family three of six p < .05 results, including both injury tests, would be lost to Benjamini–Hochberg, while the two-test injury family loses none under that same rule.

The injury statistics reconcile with the tests printed beside them. The medical-hold percentage cannot be produced from its stated n, and the survey results were computed on a smaller sample than the table and Methods describe. Those two problems are not settled by the paper as printed.

## What each check does

One entry per check that ran on this paper. The **assumptions** are the conditions under which its verdict holds; where one is unmet the verdict is capped, not merely caveated.

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

### `flag_uninformative_stat` — probabilistic

Flags comparisons whose printed precision cannot pin down the test outcome.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The comparison is modelled as a one-way ANOVA computed from these group means, SDs and ns.
- Inputs are assumed uniform over their truncation intervals for the simulated p-range.
- Ceiling `suspicious`: an over-claimed p is flagged with the one-way-ANOVA assumption disclosed, never escalated -- rivets_anova owns the accusation-grade reported-p check.
- The achievable p-range is Monte Carlo PLUS an exact corner search. Sampling the interior alone reaches a vertex with probability zero, and the extreme of F lives on one: the gap branded a reachable p=0.35 UNREACHABLE when the corner gives 0.307.

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

### `r_grim_ground_truth` — descriptive

Cross-checks our GRIM against R's canonical scrutiny package.

**What its verdict means.** Descriptive. Extracts, parses or computes a quantity; it does not itself render a verdict about the paper.

**Strongest verdict it may reach:** `indeterminate`

**It assumes:**
- Reports R's verdict. A disagreement between engines means OUR tooling is wrong; it is never evidence about the paper.

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

### `reconstruct_2x2` — absolute

Reconstructs the 2x2 tables consistent with two column percentages and a total N.

**What its verdict means.** Absolute (possible vs impossible). Exact arithmetic over the printed values and their rounding intervals. Subject to the preconditions below, a flagged result cannot be produced by any dataset.

**Strongest verdict it may reach:** `impossible`

**It assumes:**
- The two percentages must be column-conditional shares of integer counts.
- n_total must be the true total, and `decimals` must match the printed precision.
- Impossibility is decided over EVERY column split; the balance ratio only orders the plausible ones.
- A non-matching chi-square yields indeterminate, never an accusation.

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

### `verify_power_analysis` — probabilistic

Recomputes a stated a-priori power analysis and compares it to the N actually recruited.

**What its verdict means.** Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. A flagged result is unlikely if those assumptions hold; if one fails, the finding may have an innocent explanation. Never reported as `impossible`.

**Strongest verdict it may reach:** `highly_suspicious`

**It assumes:**
- The named test and effect-size metric are assumed to be what the paper actually powered.
- A small tolerance absorbs documented differences between G*Power, pwr and PASS.
- Over-recruiting is treated as correct practice, never a discrepancy.
- Indeterminate unless EVERY input was stated, which is the modal honest outcome.
- It cannot detect an analysis that reproduces but powers the wrong hypothesis.

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

- **Analysed:** 2026-09-02 13:11 UTC
- **Pipeline version:** v1.15.0 (g4a7971102983, uncommitted changes)
- **LLM backend:** grok (grok 1.0.13 (5e9a58528b76) [stable])
- **Sandbox:** Grok's `search_tool` cannot be denied: it is the only route to the forensic MCP tools. This run's sandbox is weaker than a Claude run's.
- **Prompts:** 161c6d7ed4d52b7e
- **Tool registry:** 0b06c178cea5ee68
- **Models:** grok-4.6, grok-4.6-build (editorial); grok-4.6, grok-4.6-build (sweep)
- **Reasoning effort:** high

_Two reviews are directly comparable only if the pipeline version, the prompt hash and the registry hash all match. The version alone is not sufficient: it moves about once a month, while the prompts and the tool registry move several times a day, so a difference between two runs stamped with the same version may be a change in this toolkit rather than a fact about the papers._
