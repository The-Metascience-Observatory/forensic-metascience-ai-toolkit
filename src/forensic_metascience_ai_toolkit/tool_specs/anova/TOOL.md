---
family: anova
implementation:
- forensic_metascience_ai_toolkit.tools.anova
tools:
  recalc_anova:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Recomputes a one-way ANOVA F and p from group summaries and compares them to the report.
    assumptions:
    - The reported F and p are assumed to come from a classical fixed-effects one-way ANOVA, not Welch's.
    - 'Homogeneity of variance across groups: MS_within pools the group SDs.'
    - Independent observations within and between groups.
    - Normality of the sampling distribution of the group means.
    - Rounding propagates multiplicatively into F, so the reported value is matched against an achievable interval.
    - An exact printed p above the achievable interval is an under-claim, capped at `suspicious`; a printed bound never is.
  recalc_f_to_p:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Verifies a reported p against the range its rounded F and df imply.
    assumptions:
    - The reported p is assumed to be the upper-tail F probability at the printed df.
    - The printed F is rounded, so it asserts a p RANGE; a p below it is flagged, and a p above it only when printed exact (`p_relation`).
    - The F must come from the test its df describe, whose assumptions are inherited.
---
# `anova` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## recalc_anova

<!-- description:recalc_anova -->
Recalculate a one-way ANOVA from group statistics. Parameters: means (list), sds (list), ns (list), reported_f (optional), reported_p (optional), decimals_p (optional), decimals_mean (optional), decimals_sd (optional), p_relation (optional). PASS `decimals_mean`/`decimals_sd` (the precision the table PRINTS) -- rounding of the input means/SDs propagates multiplicatively into F, so reported_f is judged against the F interval reachable from the printed precision, not a fixed window; without them the precision is inferred from the parsed values, erring wide. PASS `decimals_p` -- a p printed '.03' asserts [.025, .035); one printed '.0312' asserts [.03115, .03125). Without it the comparison uses a fixed two-decimal window plus a relative band that at p = .04 accepts a computed .06, which is a different significance decision. SAY HOW THE P WAS PRINTED: pass `p_relation` '=' for an exact p ('p = .03'), '<' for a bound ('p < .05'), '>' for 'p > .05'. An EXACT p is checked in BOTH directions: one printed LARGER than anything the inputs allow is an under-claim, returned `suspicious` (never higher) with failure_mode `reported_p_above_recomputed`, and `decision_error` true when it crosses .05. MEASURED: 't(38) = 3.94, p = .696' (true p .00034, a documented decision error) came back `consistent` before this. A bound is checked only against over-claiming, since 'p < .05' is true of any smaller p. Left unset, a value that is no conventional bound (.696, .26) is read as exact and .05/.01/.001 keep the bound reading -- so an exact 'p = .05' or 'p = .001' needs '=' said out loud. PASS `sampling='complex_survey'` WHEN THE PAPER SAYS SO -- survey or sampling weights, a complex survey design, NHANES WTMEC*/SDMVPSU, R's survey package, Stata svy:, PROC SURVEY*. This check then returns `indeterminate` instead of running, because a design-based estimate and its standard error are not functions of the printed means, SDs or counts: weighting moves the composition of the sample, not just its variance, so a disagreement is expected in BOTH directions and means nothing. MEASURED on an NHANES paper: six of one run's twenty severity-bearing tool findings were this one error. PASS `p_adjustment='sphericity'` or `'multiplicity'` for a statistic covered by a correction the paper DECLARES (Greenhouse-Geisser / Huynh-Feldt; Bonferroni, Holm, Tukey, Scheffe): a printed p LARGER than the recomputation is then `indeterminate` (`under_claim_explained_by_adjustment`), while a p SMALLER than the numbers allow is still a finding. REBUILT FROM SUMMARY STATISTICS: a printed p LARGER than these means/SDs imply is `indeterminate` (`under_claim_unconfirmed_test`) unless you pass `test_confirmed=True` with a quote saying the paper ran THIS test -- an ANCOVA, mixed-model, Welch or nonparametric p legitimately exceeds the simple test's. A printed p SMALLER than the summary statistics allow is still a finding.
<!-- /description:recalc_anova -->

## recalc_f_to_p

<!-- description:recalc_f_to_p -->
Verify F-to-p conversion for any ANOVA-style result (one-way, two-way, N-way). Use when the paper reports F, df1, df2, and a p-value but does not give group means/SDs. Parameters: f_value (float), df1 (int, between/numerator), df2 (int, within/denominator), reported_p (float, optional), decimals_p (optional), decimals_f (optional), p_relation (optional).PASS `decimals_p` -- a p printed '.03' asserts [.025, .035); one printed '.0312' asserts [.03115, .03125). ALSO PASS `decimals_f`: the reported F is rounded and p is monotone in F, so a printed 'F(1,10)=2.0' asserts F in [1.95, 2.05) and a whole p-range; comparing the reported p to the single p of the printed F convicts honestly rounded reports. DF THE PAPER DOES NOT PRINT IS AN ASSUMED BOUND: never pass a df2 you inferred from the design -- OMIT it. With df2 omitted the tool checks the reported p for attainability over EVERY df2 (including the large-df2 chi-square limit) and accuses only when no denominator df explains it; an invented df2=20 against F(3,?)=6.951, p=.0001 manufactured a measured false positive that df2->inf reconciles exactly. SAY HOW THE P WAS PRINTED: pass `p_relation` '=' for an exact p ('p = .03'), '<' for a bound ('p < .05'), '>' for 'p > .05'. An EXACT p is checked in BOTH directions: one printed LARGER than anything the inputs allow is an under-claim, returned `suspicious` (never higher) with failure_mode `reported_p_above_recomputed`, and `decision_error` true when it crosses .05. MEASURED: 't(38) = 3.94, p = .696' (true p .00034, a documented decision error) came back `consistent` before this. A bound is checked only against over-claiming, since 'p < .05' is true of any smaller p. Left unset, a value that is no conventional bound (.696, .26) is read as exact and .05/.01/.001 keep the bound reading -- so an exact 'p = .05' or 'p = .001' needs '=' said out loud. PASS `p_adjustment='sphericity'` or `'multiplicity'` for a statistic covered by a correction the paper DECLARES (Greenhouse-Geisser / Huynh-Feldt; Bonferroni, Holm, Tukey, Scheffe): a printed p LARGER than the recomputation is then `indeterminate` (`under_claim_explained_by_adjustment`), while a p SMALLER than the numbers allow is still a finding. ONE-TAILED ONLY WHEN STATED (statcheck's rule): at df1 = 1, F(1, df2) = t(df2)^2 and half the p is the one-tailed p. That reading explains a too-small p only when the paper says, anywhere, that its tests are one-tailed, one-sided or directional -- then pass `one_tailed_stated=True` (quote it) and the result is `indeterminate`. Otherwise it is `suspicious` with failure_mode `reconciles_only_one_tailed_unstated` and the one-tailed reading named beside it. MEASURED 2026-10-18: the unstated rescue hid 21 of the 49 errors in Wicherts, Bakker & Molenaar's (2011) hand coding and decided no correct statistic.
<!-- /description:recalc_f_to_p -->
