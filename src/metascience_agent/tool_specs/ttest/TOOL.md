---
family: ttest
implementation:
- metascience_agent.tools.ttest
tools:
  recalc_independent_t:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Recomputes an independent-samples t-test, under both Welch and Student readings.
    assumptions:
    - Independent groups, and normality of the sampling distribution of the mean difference.
    - Welch's and Student's pooled t are BOTH accepted unless the paper states which it ran.
    - Homogeneity of variance is assumed only under the Student reading.
    - One- and two-tailed p conventions are both accepted unless stated.
    - Input rounding propagates into an achievable interval; over-claimed significance is always flagged, and an under-claim (a printed p above every p the inputs reach) only when the p was printed exact (`p_relation`).
  recalc_within_subjects_t:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Recovers the hidden pre/post correlation a paired t-test report implies.
    assumptions:
    - The reported p is assumed to come from a standard paired t-test; r is recovered by the Jane et al. identity.
    - A threshold p only lower-bounds t, so the recovered r is a lower bound.
    - 'Tail convention matters: a one-tailed p read as two-tailed is a benign explanation to rule out first.'
    - Flagged only when the WHOLE attainable r interval over the inputs' rounding box lies outside [-1, 1].
    - 'Capped at `highly_suspicious` on every branch: the paired-t reading is an assumed model, not arithmetic.'
---
# `ttest` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## recalc_independent_t

<!-- description:recalc_independent_t -->
Recalculate an independent samples t-test from group statistics. Parameters: mean1, sd1, n1, mean2, sd2, n2, reported_p (optional), reported_t (optional), use_welch (optional), p_tail (optional), decimals_p (optional), decimals_mean (optional), decimals_sd (optional), p_relation (optional). LEAVE `use_welch` UNSET unless the paper states which test it ran: Welch's and Student's (pooled) t are both standard and differ substantially at unequal n/SD, so the check accepts either by default and convicting a correct pooled t against a Welch recomputation is a false accusation. Same for `p_tail` ('two'|'one'; default accepts either -- one-tailed reports are legitimate). PASS `decimals_mean`/`decimals_sd` (the precision the table PRINTS): input rounding propagates multiplicatively into t, so reported_t is judged against the reachable t interval, not a fixed window. PASS `decimals_p` -- a p printed '.03' asserts [.025, .035); one printed '.0312' asserts [.03115, .03125). Without it the comparison uses a fixed two-decimal window plus a relative band that at p = .04 accepts a computed .06, a different significance decision. SAY HOW THE P WAS PRINTED: pass `p_relation` '=' for an exact p ('p = .03'), '<' for a bound ('p < .05'), '>' for 'p > .05'. An EXACT p is checked in BOTH directions: one printed LARGER than anything the inputs allow is an under-claim, returned `suspicious` (never higher) with failure_mode `reported_p_above_recomputed`, and `decision_error` true when it crosses .05. MEASURED: 't(38) = 3.94, p = .696' (true p .00034, a documented decision error) came back `consistent` before this. A bound is checked only against over-claiming, since 'p < .05' is true of any smaller p. Left unset, a value that is no conventional bound (.696, .26) is read as exact and .05/.01/.001 keep the bound reading -- so an exact 'p = .05' or 'p = .001' needs '=' said out loud. The under-claim side uses the LARGEST p the printed means and SDs reach (either flavor, the most conservative df), so input rounding cannot manufacture one. PASS `sampling='complex_survey'` WHEN THE PAPER SAYS SO -- survey or sampling weights, a complex survey design, NHANES WTMEC*/SDMVPSU, R's survey package, Stata svy:, PROC SURVEY*. This check then returns `indeterminate` instead of running, because a design-based estimate and its standard error are not functions of the printed means, SDs or counts: weighting moves the composition of the sample, not just its variance, so a disagreement is expected in BOTH directions and means nothing. MEASURED on an NHANES paper: six of one run's twenty severity-bearing tool findings were this one error. PASS `p_adjustment='sphericity'` or `'multiplicity'` for a statistic covered by a correction the paper DECLARES (Greenhouse-Geisser / Huynh-Feldt; Bonferroni, Holm, Tukey, Scheffe): a printed p LARGER than the recomputation is then `indeterminate` (`under_claim_explained_by_adjustment`), while a p SMALLER than the numbers allow is still a finding. REBUILT FROM SUMMARY STATISTICS: a printed p LARGER than these means/SDs imply is `indeterminate` (`under_claim_unconfirmed_test`) unless you pass `test_confirmed=True` with a quote saying the paper ran THIS test -- an ANCOVA, mixed-model, Welch or nonparametric p legitimately exceeds the simple test's. A printed p SMALLER than the summary statistics allow is still a finding.
<!-- /description:recalc_independent_t -->

## recalc_within_subjects_t

<!-- description:recalc_within_subjects_t -->
Recover the hidden pre/post correlation from a paired t-test (Jane et al.). CRITICAL: pass p_is_threshold=true when the paper prints 'p < .05' rather than an exact p -- a bound only lower-bounds t, so the recovered r is a LOWER BOUND and no inconsistency can be established from it. Also pass p_tail ('two'|'one'). reported_p may be a string such as '<0.05'. PASS decimals_mean/decimals_sd/decimals_p -- every input is rounded and the recovered r is sensitive to all of them (r can legitimately approach (sd_pre^2+sd_post^2)/(2*sd_pre*sd_post) > 1 when the SDs differ), so an exact-p r just outside [-1,1] is only reported when the WHOLE attainable interval over the rounding box lies outside it. Parameters: mean_pre, sd_pre, mean_post, sd_post, n, reported_p, p_is_threshold, p_tail, decimals_mean, decimals_sd, decimals_pPASS `sampling='complex_survey'` WHEN THE PAPER SAYS SO -- survey or sampling weights, a complex survey design, NHANES WTMEC*/SDMVPSU, R's survey package, Stata svy:, PROC SURVEY*. This check then returns `indeterminate` instead of running, because a design-based estimate and its standard error are not functions of the printed means, SDs or counts: weighting moves the composition of the sample, not just its variance, so a disagreement is expected in BOTH directions and means nothing. MEASURED on an NHANES paper: six of one run's twenty severity-bearing tool findings were this one error.
<!-- /description:recalc_within_subjects_t -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:05 -->
   - `recalc_independent_t`, `recalc_anova`, `recalc_chi_squared`,
     `recalc_f_to_p` — verify reported test statistics. With these,
     `recalc_stat_to_p` and `check_regression(_batch)`, pass `p_relation`
     for every reported p: '=' when the paper prints 'p = .xx', '<' for
     'p < .05', '>' for 'p > .05'. An exact p printed LARGER than its
     statistic allows (an under-claim, including a non-significant p on a
     significant statistic) is caught only on the exact reading.
<!-- /guidance:05 -->

<!-- guidance:08 -->
   - `recalc_within_subjects_t` — paired designs; |r| > 1 is impossible.
<!-- /guidance:08 -->
