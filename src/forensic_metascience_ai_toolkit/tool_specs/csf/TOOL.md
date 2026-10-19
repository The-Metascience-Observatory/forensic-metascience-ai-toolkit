---
family: csf
implementation:
- forensic_metascience_ai_toolkit.tools.csf
tools:
  csf_test:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Combines baseline p-values to detect arms more similar than randomisation allows.
    assumptions:
    - Baseline p-values are mutually independent and uniform under simple randomisation, unless a correlation is supplied.
    - Unknown correlation is handled by an equicorrelated null and the verdict read at a conservative rho = 0.5.
    - 'Simple randomisation is required: cluster, multi-site, stepped-wedge, crossover, matched and stratified designs are refused.'
    - An unstated or unrecognised design caps the verdict below `highly_suspicious`.
    - One-sided for EXCESS similarity, and at least three usable p-values are needed.
---
# `csf` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## csf_test

<!-- description:csf_test -->
Carlisle-Stouffer-Fisher baseline-similarity test: combine a randomised trial's baseline p-values to detect groups MORE similar than randomisation allows. One-sided for EXCESS similarity -- uniformly HIGH baseline p-values are the red flag, never reassurance. ALWAYS PASS `design` IF THE PAPER STATES ONE. Cluster-randomised, multi-site, stepped-wedge, crossover, matched-pairs, stratified and minimised allocation all break baseline independence BY CONSTRUCTION, and the test refuses on them rather than flagging: an uncorrected run flagged a correctly-randomised cluster trial about 71% of the time. Without a stated design the verdict is capped below `highly_suspicious`, because stratified allocation would explain extreme uniformity innocently. Baseline rows are also correlated within a trial (weight/height/BMI/waist measure roughly one thing); the null is correlation-aware and a sensitivity profile across rho is always returned. Pass `correlation` only if it is genuinely known or estimable. Parameters: p_values (list), method ('stouffer'|'fisher', default 'stouffer'), design (e.g. 'parallel_rct', 'cluster_randomized', 'stratified'), correlation (optional float)
<!-- /description:csf_test -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:14 -->
   - `csf_test`, `bayesian_table1_dispersion` — Table 1 baseline similarity
     (remember: HIGH similarity is the red flag; see rulebook). **On any
     multi-arm baseline table, `csf_test` is MANDATORY, and run it on the
     COHERENT variable block** (the anthropometrics together, the
     biochemistry together), not only across the whole table — mixing
     unrelated blocks dilutes a rigged one (MEASURED 2026-08-21 on the apple-cider gold
     paper: age/weight/height at per-row p = 0.93/0.99/0.99 washed out to a
     whole-table similarity p of 0.19 beside eight biochemical rows, and the
     run published reassurance). The bayesian screen is deliberately
     conservative: its `consistent` is NEVER clearance on its own, and its
     `indeterminate` naming a row subset means csf_test on that subset is
     the next call, not optional.
<!-- /guidance:14 -->
