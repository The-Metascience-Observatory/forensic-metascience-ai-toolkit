---
family: chi_squared
implementation:
- metascience_agent.tools.chi_squared
tools:
  recalc_chi_squared:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Recomputes chi-squared under both 2x2 conventions, plus Fisher's exact p.
    assumptions:
    - Independent observations, each unit counted in exactly one cell.
    - Expected cell counts large enough for the chi-square approximation, conventionally at least 5.
    - Both the Pearson and Yates conventions are tried, and Fisher's p, before anything is flagged.
    - The likelihood-ratio (G-test) and Fisher-Freeman-Halton p are tried only in the under-claim direction, so a paper reporting a G p BELOW Pearson's can still mismatch innocently.
    - An exact printed p above every convention's p is an under-claim, capped at `suspicious`; a printed bound never is.
---
# `chi_squared` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## recalc_chi_squared

<!-- description:recalc_chi_squared -->
Recalculate chi-squared test from contingency table. Parameters: observed (2D list), reported_chi2 (optional), reported_p (optional), use_yates (default false), decimals_p (optional), p_relation (optional). PASS `decimals_p` -- a p printed '.03' asserts [.025, .035); one printed '.0312' asserts [.03115, .03125). Without it the comparison uses a fixed two-decimal window plus a relative band that at p = .04 accepts a computed .06, a different significance decision. IS THE TABLE PAIRED? A McNemar test -- the same subjects measured twice -- uses (b-c)^2/(b+c) on the discordant cells, NOT a chi-squared of independence, and the two designs produce identical-looking counts. Pass paired=true when the paper says McNemar (or reports a pre/post agreement table). You do not have to: McNemar is computed on every 2x2 and tried in the same both-conventions match, so a statistic only it explains comes back consistent rather than flagged. `paired` decides which test is the HEADLINE calculated_* value. AND CHECK THE TABLE YOU BUILT. The measured failure here was a 4-category gaze breakdown flattened into a 2x2 that was not the paper's table at all -- no guard in this tool can detect that, and a mismatch against a table the paper never printed is an accusation about your own reconstruction. SAY HOW THE P WAS PRINTED: pass `p_relation` '=' for an exact p ('p = .03'), '<' for a bound ('p < .05'), '>' for 'p > .05'. An EXACT p is checked in BOTH directions: one printed LARGER than anything the inputs allow is an under-claim, returned `suspicious` (never higher) with failure_mode `reported_p_above_recomputed`, and `decision_error` true when it crosses .05. MEASURED: 't(38) = 3.94, p = .696' (true p .00034, a documented decision error) came back `consistent` before this. A bound is checked only against over-claiming, since 'p < .05' is true of any smaller p. Left unset, a value that is no conventional bound (.696, .26) is read as exact and .05/.01/.001 keep the bound reading -- so an exact 'p = .05' or 'p = .001' needs '=' said out loud. For the under-claim the LARGEST p across Pearson, Yates, Fisher, McNemar, likelihood ratio (G) and, on a 2xC table, the exact Fisher-Freeman-Halton is used, so a paper that ran any of them is not flagged. PASS `sampling='complex_survey'` WHEN THE PAPER SAYS SO -- survey or sampling weights, a complex survey design, NHANES WTMEC*/SDMVPSU, R's survey package, Stata svy:, PROC SURVEY*. This check then returns `indeterminate` instead of running, because a design-based estimate and its standard error are not functions of the printed means, SDs or counts: weighting moves the composition of the sample, not just its variance, so a disagreement is expected in BOTH directions and means nothing. MEASURED on an NHANES paper: six of one run's twenty severity-bearing tool findings were this one error. PASS `p_adjustment='sphericity'` or `'multiplicity'` for a statistic covered by a correction the paper DECLARES (Greenhouse-Geisser / Huynh-Feldt; Bonferroni, Holm, Tukey, Scheffe): a printed p LARGER than the recomputation is then `indeterminate` (`under_claim_explained_by_adjustment`), while a p SMALLER than the numbers allow is still a finding.
<!-- /description:recalc_chi_squared -->
