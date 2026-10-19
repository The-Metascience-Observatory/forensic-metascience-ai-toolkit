---
family: table1_dispersion
implementation:
- metascience_agent.tools.table1_dispersion
tools:
  bayesian_table1_dispersion:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Estimates Table 1 baseline dispersion (tau) to flag under- or over-dispersion versus chance.
    assumptions:
    - Under proper simple randomisation baseline p-values are uniform and z^2 ~ chi2_1, so E[z^2] = 1.
    - The CI on tau inverts the EXACT chi-square null of mean(z^2); a percentile bootstrap was used until it was measured to accuse 35.9% of honest 2-row tables.
    - Rows are treated as equicorrelated at rho = 0.5, discounting k rows to k/(1+(k-1)rho) effective degrees of freedom -- so a table of ANY size is worth about 2 df, and large tables are not thereby more accusable.
    - Stratified, minimised, cluster, matched and crossover designs are refused; an unstated design caps the verdict.
    - Escalation also requires csf_test's correlation-aware combination of the same p-values to corroborate; csf finding nothing vetoes it.
    - 'An elevated tau whose CI does not exclude tau = 1 is reported `indeterminate`, never `consistent`: too few effective df to convict OR to clear.'
---
# `table1_dispersion` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## bayesian_table1_dispersion

<!-- description:bayesian_table1_dispersion -->
Bayesian-style Table 1 dispersion (Heathers §'Bayesian Table 1 analysis', Bolland 2022): for each baseline row → p-value → z-score, then estimate the precision multiplier τ̂ = sqrt(1/mean(z²)). τ̂ > 1 indicates under-dispersion (suspicious uniformity, the Carlisle/Fujii signature); τ̂ < 1 indicates over-dispersion (possible randomization failure). Handles mixed continuous/categorical rows. Each row is either {label?, means, sds, ns} for continuous or {label?, counts: [[r1c1, r1c2,...], ...]} for categorical. ALWAYS PASS `design` IF THE PAPER STATES ONE. Cluster-randomised, multi-site, stepped-wedge, crossover, matched-pairs, stratified and minimised allocation force baseline balance BY CONSTRUCTION and are refused outright; without a stated design the verdict is CAPPED below `highly_suspicious`. Baseline rows within a trial are correlated, so the CI is correlation-aware and a sensitivity profile across rho is always returned -- pass `correlation` only if it is genuinely known or estimable. The CI on τ̂ inverts the exact chi-square null of mean(z²); a percentile bootstrap was used until it was measured to accuse 35.9% of HONEST 2-row tables and 27.6% of 3-row ones. Parameters: rows (list of dicts), design (required in practice), correlation (optional), num_bootstrap (default 1000, audit-only), ci_level (default 0.95), seed (default 0)
<!-- /description:bayesian_table1_dispersion -->
