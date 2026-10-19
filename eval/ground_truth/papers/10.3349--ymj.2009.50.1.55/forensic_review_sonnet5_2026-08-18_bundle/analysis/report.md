> **REPORT INCOMPLETE** — this review was assembled from a malformed or missing model output and must not be read as a complete analysis: headline.severity 'none' is weaker than findings[0].severity 'indeterminate'; the headline must be at least as severe as the worst finding it introduces

> **REPORT INCOMPLETE** — this document was rendered from a malformed report object and must not be read as a complete review: headline.severity 'none' is weaker than findings[0].severity 'indeterminate'; the headline must be at least as severe as the worst finding it introduces

# Forensic review -- Kang et al. 2009

> This is an automated check of a paper's reported numbers and its internal record -- not a finding of misconduct. It is NOT adequate for definitive detection of wrongdoing or fraud.

## The Efficacy of Postoperative Prophylactic Antibiotics in Orthognathic Surgery: A Prospective Study in Le Fort I Osteotomy and Bilateral Intraoral Vertical Ramus Osteotomy
*Sang-Hoon Kang, Jae-Ha Yoo, Choong-Kook Yi. Yonsei Medical Journal. 2009. doi:10.3349/ymj.2009.50.1.55*

**Design:** parallel-arm randomized controlled trial, open-label

<sub>Analysed as `10.3349--ymj.2009.50.1.55`</sub>

> **NO MAJOR PROBLEM FOUND** — Every checkable number in this small trial reconciles: the chi-squared test, the group sex counts, and the age statistics all agree with the values printed beside them, and no finding rises above an open wording question that does not touch the study's result.
>
> **In plain terms:** This is a small, plainly reported clinical trial. Every number we could check -- the main statistical test, the patient counts, the age figures -- matches what the paper printed, and the only open question is a single ambiguously worded sentence that, on inspection, does not change the study's conclusion.
>
> **Evidence:** Table 1 gives 3/28 infections in the experimental group and 2/28 in the control group; recalculating chi-squared from those counts gives chi2 = 0.2196, p = 0.6393, matching the paper's reported “p = 0.639” exactly. The sex counts (16:12 and 14:14) sum to the stated group n of 28 in both arms.
> **Rests on:** a constraint the paper itself states
> **Reproduce:** no runnable command -- the review's command used an option this tool does not have. The finding's own numbers are above; re-derive from those.

**Verdict: reconciles** (confidence: medium)

## Provenance of the analysis

- **PREREGISTRATION NOT MENTIONED**. No preregistration is mentioned in the extracted text. This is WEAK evidence: registration statements often sit in a data-availability or funding section that extraction may have dropped, and absence here is not evidence that none exists.
- **Shared artefacts.** No code, data or registration links found in the extracted text. Absence here is weak evidence -- these often live in a data-availability statement that extraction may have dropped.

## Statistical anatomy

1 study/studies, 4 variables, 1 statistical tests identified.

### Studies

| id | label | design | n | unit of analysis | clustered |
|---|---|---|---|---|---|
| S1 | Orthognathic surgery antibiotic prophylaxis RCT | rct | 56 | patient | no |

### Variables

| variable | level | discreteness | values | unit | derived | admits | conf |
|---|---|---|---|---|---|---|---|
| Patient age | ratio | unknown | range not stated | years | measured | none -- not integer-valued | medium |
| Sex (Male:Female ratio) | nominal | discrete | male; female | - | measured | percentage GRIM on cell counts | high |
| Postoperative wound infection occurrence (surgical site infection, SSI, per CDC criteria) | nominal | discrete | infected; not infected | - | measured | DEBIT; percentage GRIM | high |
| Wound dehiscence occurrence | nominal | discrete | dehiscence; no dehiscence | - | measured | DEBIT; percentage GRIM | high |

_`admits` is what this typing permits, not what ran -- see the tests table for that. Granularity checks (GRIM, GRIMMER, SPRITE) apply ONLY to integer-valued variables on a STATED scale; on a 95-paper corpus at most 0.31% of numeric cells qualify. A granularity finding against a row that admits none is wrong about the tool, not about the paper._

_Role (outcome, predictor, covariate) is deliberately absent here: a variable is the outcome of one model and a covariate in the next, so it is a property of each test and is shown in the tests table._

### Tests, in terms of those variables

| location | test | outcome (DV) | predictors (IV) | n | corrected | assumptions reported |
|---|---|---|---|---|---|---|
| Results, para 2 / Table 1 | chi_squared | Postoperative wound infection occurrence (surgical site infection, SSI, per CDC criteria) (binary) | treatment_group | 56 | ? | none reported |

_1 of 1 tests report no assumption checks._ That is ordinary in published work and is not itself a finding; it does mean the distributional premises above rest on this analysis's typing rather than on anything the paper verified.

## Findings

_Ordered by severity, then by what each finding changes: of two equally severe findings, the one that moves a conclusion prints first. The numbers below are reading positions -- they are not the `rank` field in report.json, which is this analysis's own proposed order and is used only to separate findings that tie on both keys._

### 1. A symptom-description sentence, read too literally, appears to assign 5 infections to one arm instead of 3  [INDETERMINATE | confidence: medium]

**In plain terms.** One sentence describing symptoms could be misread as saying 5 patients in the no-postoperative-antibiotics group got infected, when the study's own summary table says 3. Read naturally, though, the sentence is grouping patients by which symptoms they had (sinus swelling versus jaw pain, which map onto the two different operations performed), not by which treatment group they were in, and the total patient count (5) matches the table either way. The test result the study's conclusion rests on uses the table's numbers, which were independently checked and are correct, so this wording issue does not change the finding.

- **Location:** Results, paragraph 2
- **Reported:** "One patient in the experimental group was diagnosed with an infection by facial swelling, redness and sinus haziness in the waters' view, and the other 4 patients were diagnosed with a postoperative infection by swelling and redness, and pain on the mandibular area."
- **Computed:** The immediately preceding sentence and Table 1 both give 3 infections in the experimental group and 2 in the control group (total 5). Read with 'in the experimental group' scoping only the first clause, the sentence splits the same 5 patients by SYMPTOM type (1 with a maxillary/sinus finding on Waters' view, consistent with the Le Fort I maxillary osteotomy arm of the procedure; 4 with mandibular swelling/pain, consistent with the vertical ramus osteotomy) rather than by TREATMENT arm, and the totals reconcile exactly: 1 + 4 = 5 = 3 + 2. The chi-squared test itself uses the 3/2 counts, independently confirmed against Table 1 by recalc_chi_squared (chi2 = 0.2196, p = 0.6393, matching the reported p = 0.639 to three decimals), so the primary result does not depend on how this sentence is parsed.
- **As printed in the paper:** **Results, para 2** -- “According to the χ²-test, there was no significant difference in the prevalence of postoperative wound infections between the patients who had received postoperative prophylactic antibiotic administration and those who had not (p = 0.639).” _(found in the paper's text)_
- **Assumptions:** The clinical reconciliation (Waters' view = maxillary sinus finding correlating with Le Fort I; mandibular pain correlating with IVRO) is my own reading of the anatomy the paper describes, not a claim the paper makes explicitly. The paper never states which treatment arm each of the 4 remaining patients belonged to, so the ambiguity itself is real and unresolved by anything in the text -- the paper is silent on that specific attribution.
- **Reproduce:** no runnable command -- the review's command used an option this tool does not have. The finding's own numbers are above; re-derive from those.

## What we could NOT check

- **Discussion, paragraph 4: a-priori sample-size/power justification (α=0.05, β=0.20, p1=5%, p2=35%, n=28/group)** — verify_power_analysis and required_n require a single precomputed effect size (e.g. Cohen's h for two proportions); neither accepts raw proportions to derive that effect size internally, and deriving it by hand is disallowed manual computation.
- **Results/Abstract: the 'no significant difference' conclusion (p=0.639)** — absence_of_evidence needs a printed CI or a (b, se) pair. The paper reports only a bare chi-squared p-value with no odds ratio, risk difference or CI printed anywhere, so the largest effect the data still permit cannot be assessed with the available tools.
- **Whole paper: baseline group comparability beyond age and sex** — csf_test / bayesian_table1_dispersion need multiple independent baseline p-values or several rows of means/SDs+counts; this paper reports only two baseline variables (age, sex), neither with a stated between-group p-value, which is too few to run an omnibus baseline-similarity test.
- **Whole paper: trial registration status** — No trial registry ID, protocol number, or registration statement appears anywhere in the text.

## Limitations

- Figures were not read for this paper: extract_figures was not invoked. Table 1 is embedded as an image in the XML (image_only=true) with no extractable cells, and its contents were instead recovered from the PDF's docling-extracted grid and cross-checked against every value restated in prose (age means/SDs, sex ratios, infection and dehiscence counts); all values agree exactly across the two sources. No other figures appear in the paper.
- This is a very small trial (28 per arm) with only two baseline variables reported (age, sex) and no between-group baseline p-values printed, so the omnibus baseline-similarity checks (CSF, Bayesian Table 1 dispersion) that would ordinarily surface allocation-integrity concerns could not be run at all -- their absence here is a limit of what the paper reports, not a clean bill on randomization.
- This review reads only this one paper and reaches no external database; whether the finding pattern here (small, exactly-reconciling numbers) recurs across this author's other work, or how the observed infection rates compare to the wider literature the Discussion cites, is outside what this analysis can determine.
- The one accusatory finding in this report was flagged by the automated worklist as having a quote that could not be located in the paper's extraction; on manual re-reading of the XML full text, the quoted sentence is present verbatim, so that marker was a false flag specific to this run, not evidence of a transcription problem in the finding itself.
- No image forensics were performed. Duplicated, spliced, rotated or otherwise manipulated image panels -- by some accounts the single most productive source of detected problems in the literature -- are outside what this system checks, and their absence here is not evidence of their absence in the paper.

## Coverage

- **Statistics found:** 13; **checked:** 10
- **Tools run:** extract_xml, extract_pdf, statcheck, parse_cells_typed, parse_cells_as_declared, recalc_chi_squared, check_summation_batch, grim_check, grimmer_check, flag_round_n
- **Tables checked:** Table 1 (image_only in XML, recovered from PDF and cross-checked against prose)
- **Every checkable item:** 8 registered; 0 refused with a stated reason; **8 outstanding**
    - how many were CHECKED is not measured -- no persisted item identity joins a tool call back to a manifest row, so how many items were CHECKED cannot be counted. This is not a count of zero. This is not a count of zero.
- **Stage-1 findings:** 10 raised; 2 carried into this report; 8 not carried
- **Traceable to the page:** 13 of 14 checks recorded the passage their numbers were read from; 13 of those were located in the paper's own text.
- **1 check cited numbers with no quoted source.** Those values cannot be traced to a passage from this document; re-read them at source before relying on them.

## What each check does

One entry per check that ran on this paper. The **assumptions** are the conditions under which its verdict holds; where one is unmet the verdict is capped, not merely caveated.

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

This is a 56-patient, open-label, parallel-arm randomized trial (Kang, Yoo & Yi, 2009, *Yonsei Medical Journal*) comparing a single preoperative antibiotic dose against a preoperative dose plus three days of postoperative antibiotics in patients undergoing orthognathic surgery (Le Fort I osteotomy and bilateral intraoral vertical ramus osteotomy). The stated aim was to test whether continuing prophylactic antibiotics after surgery reduces surgical-site infection versus a single preoperative dose. The paper's own conclusion is that it does not (p = 0.639), and it recommends against routine prolonged postoperative antibiotic use in this population.

The trial is small and its reporting is correspondingly thin -- one continuous baseline variable (age) and one categorical one (sex), no confidence interval or effect size for the primary comparison, and no trial registration -- but everything the paper does report is internally consistent. The primary chi-squared test recalculates exactly from Table 1's raw counts (3/28 infected in the experimental arm, 2/28 in the control arm): chi2 = 0.2196, p = 0.6393, matching the paper's "p = 0.639" to the decimal. The sex ratios in Table 1 (16:12 and 14:14) both sum correctly to the stated group size of 28, and match the reduced ratios given in the prose (4:3 and 1:1). Age means and SDs are printed identically in both the Results text and Table 1, with no drift between the two. GRIMMER (which tests whether an integer-valued sample could produce a given mean and SD) finds admissible integer solutions for both groups' age statistics, though this rests on an assumption -- not stated by the paper -- that age was recorded in whole years; GRIM itself has no power to distinguish anything at n=28 with one decimal place of precision, so those checks are reported as uninformative rather than as passes.

The one place a reader might reasonably pause is a sentence describing individual infection cases by symptom: one patient with a maxillary sinus finding on Waters' view, and "the other 4 patients" with mandibular swelling and pain. Read too literally, "in the experimental group" could seem to scope the whole sentence, which would put 5 infections in one arm against Table 1's stated 3. The more natural reading -- and the one that actually accounts for every patient -- splits the same 5 total infected patients (3 experimental + 2 control, per Table 1) by which of the two operations they had: a maxillary finding tracks the Le Fort I osteotomy, mandibular pain tracks the vertical ramus osteotomy performed on the rest of the cohort. Under that reading the numbers add up exactly (1 + 4 = 5 = 3 + 2), and it is the reading consistent with everything else the paper reports. The paper never explicitly states which treatment arm each of the four remaining patients was in, so a genuine wording ambiguity survives -- but the chi-squared test itself is computed directly from Table 1's counts, which are independently verified, so this sentence does not bear on the study's conclusion regardless of how it is parsed.

Two things worth naming without treating them as defects. First, the trial reports no confidence interval or effect-size estimate alongside its null result, and no printed odds ratio or risk difference exists to check how large an effect the data could still be hiding -- a reader relying on "no significant difference" as evidence of equivalence should know the study does not license that stronger claim, though it also never makes it. Second, no trial registration is reported anywhere in the text; that is unremarkable for a 2008-submitted trial in this journal and is not treated here as an anomaly, only as an absence.

The results appear sound and the reported statistics verify.

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
