---
family: variance_dispersion
implementation:
- metascience_agent.tools.variance_dispersion
tools:
  check_variance_dispersion:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Tests whether reported SDs across groups are more similar to one another than sampling error allows.
    assumptions:
    - Under normality s^2 ~ sigma^2 chi2_{n-1}/(n-1), so standardising by MS_w leaves only relative spread; the null is bootstrapped from that chi-square.
    - Groups are assumed to share a population variance -- `homogeneous_variances` is required, and gates the CONSISTENT verdict too, because a violated assumption blinds the test (measured 0.0% detection) rather than making it accusatory.
    - 'Dispersion is measured as max_z - min_z, not SD_z: the source paper measured the range as more robust to heterogeneity (AUROC 0.827 vs 0.761).'
    - Printed precision is read from the SD LITERAL; a rounding step above 0.25 of the SD is refused, because coarse rounding drives honest SDs onto identical values (60% of honest samples at SD~2.0 printed to 0dp).
    - Cluster, multi-site, stepped-wedge, crossover, matched, stratified and minimised designs constrain variances by construction and are refused.
    - 'The verdict is RELATIVE and every result sets `reference_required`: the validating study''s AUROC 1.00 came from comparing genuine against fabricated sets, while both looked significant against the theoretical null in absolute terms.'
    - Severity is capped at `suspicious`; over-similar SDs are improbable, never impossible.
---
# `variance_dispersion` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## check_variance_dispersion

<!-- description:check_variance_dispersion -->
Are these standard deviations too SIMILAR to each other? Sample variances are themselves random, and fabricators who add noise to the means forget that the DISPERSIONS need their own noise. Standardises each variance by the within mean square (z2 = s2/MS_w) and compares max_z - min_z against a parametric bootstrap of the chi-square null; one-sided, for excessive consistency. Hartgerink, Voelkel, Wicherts & van Assen (2019) measured this as the single best fabrication detector tested (AUROC 1.00 on raw data), against 0.38-0.51 for terminal digits and 0.02-0.16 for Benford -- which is why this toolkit has no digit-preference check. Pass `sds`, `ns`, and the SDs AS PRINTED in `sd_texts` (e.g. ['2.11','2.08']): coarse rounding collapses honest SDs onto identical values -- at SD~2.0 printed to 0dp, 60% of HONEST samples give six identical SDs -- so without the printed precision a rounding artifact is indistinguishable from the signature. `homogeneous_variances` is REQUIRED and gates the reassuring verdict too: the source paper's own preregistered analysis scored AUROC 0.264 (inverted, worse than chance) from getting it wrong, and a violated assumption makes this test BLIND rather than accusatory, so an unstated assumption cannot return `consistent` either. Needs >=3 groups that are comparable units on ONE instrument; cluster/multi-site/stratified/crossover/matched designs constrain variances by construction and are refused. SEVERITY IS CAPPED AT `suspicious` AND EVERY RESULT SETS `reference_required`: the paper's AUROC 1.00 was RELATIVE -- every dataset it saw, genuine and fabricated alike, looked significant against the theoretical null, and only comparison against known-genuine data separated them. This ranks candidates for human review; it never convicts. Parameters: sds (list), ns (list), sd_texts (list of the printed literals), homogeneous_variances (required), design, iterations (default 100000), seed (default 0)
<!-- /description:check_variance_dispersion -->
