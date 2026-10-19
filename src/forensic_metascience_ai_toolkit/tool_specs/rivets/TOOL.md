---
family: rivets
implementation:
- forensic_metascience_ai_toolkit.tools.rivets
tools:
  rivets_anova:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Maps the F and p reachable from rounded inputs, and flags hand-calculation signatures.
    assumptions:
    - The reported F and p are assumed computed from these summaries by a classical one-way ANOVA.
    - Monte Carlo draws uniformly over each printed value's truncation interval.
    - Printed decimals must be supplied; the defaults assume more precision than most papers report.
    - A point match plus a rare hit rate is read as a hand-calculation signature -- the RIVETS premise itself.
    - Pass a bound p as the STRING, never the float, or it reads as an unreachable exact value.
  rivets_independent_t:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Maps the t and p reachable from rounded inputs, and flags hand-calculation signatures.
    assumptions:
    - The reported t and p are assumed computed from these summaries by an independent-samples t-test.
    - Welch and Student readings are both accepted, as are both tail conventions, unless the paper states them.
    - Monte Carlo draws uniformly over each printed value's truncation interval.
    - A point match plus a rare hit rate is read as a hand-calculation signature.
    - Pass a bound p as the STRING, never the float.
---
# `rivets` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## rivets_anova

<!-- description:rivets_anova -->
RIVETS for one-way ANOVA: Monte Carlo over the truncation interval of group means/SDs to surface the F-range, p-range, and exact-match hit rates. A reported_p OUTSIDE the achievable [p_min, p_max] is flagged at the same severity as an out-of-range reported_f. PASS THE PRINTED PRECISION: decimals_mean/decimals_sd/decimals_p must be the decimals AS PRINTED -- the defaults assume more precision than most papers report, which narrows the achievable interval and manufactures accusations. If the paper gives a BOUND ("p < .001"), pass it as that STRING, never as the float 0.001. Prefer this over recalc_anova, which is precision-blind and flags statistics sitting inside their own rounding interval. Parameters: means (list), sds (list), ns (list), reported_f (optional), reported_p (optional, float or threshold string), decimals_mean (default 2), decimals_sd (default 2), decimals_f (default 3), decimals_p (default 3), p_is_threshold (set TRUE when the paper printed 'p < .001' rather than an exact p -- the float cannot carry it and reading a bound as exact is a large false-accusation class), num_samples (default 5000), seed (default 0)PASS `sampling='complex_survey'` WHEN THE PAPER SAYS SO -- survey or sampling weights, a complex survey design, NHANES WTMEC*/SDMVPSU, R's survey package, Stata svy:, PROC SURVEY*. This check then returns `indeterminate` instead of running, because a design-based estimate and its standard error are not functions of the printed means, SDs or counts: weighting moves the composition of the sample, not just its variance, so a disagreement is expected in BOTH directions and means nothing. MEASURED on an NHANES paper: six of one run's twenty severity-bearing tool findings were this one error.
<!-- /description:rivets_anova -->

## rivets_independent_t

<!-- description:rivets_independent_t -->
RIVETS for independent two-sample t-test: detects hand-calculation by checking if the reported t equals the value computed from the truncated mean/SD inputs while Monte Carlo across the truncation interval rarely produces that exact value. Also surfaces the analytic [t_min, t_max] and [p_min, p_max] given the rounding precision of the inputs. A reported_p OUTSIDE the achievable [p_min, p_max] is flagged at the same severity as an out-of-range reported_t. PASS THE PRINTED PRECISION: decimals_mean/decimals_sd/decimals_p must be the decimals AS PRINTED -- the defaults assume more precision than most papers report, which narrows the achievable interval and manufactures accusations. If the paper gives a BOUND ("p < .001"), pass it as that STRING, never as the float 0.001: an exact 0.001 against an achievable 1e-6 reads as unreachable. Prefer this over recalc_independent_t, which is precision-blind and flags statistics that sit inside their own rounding interval. Parameters: mean1, sd1, n1, mean2, sd2, n2, reported_t (optional), reported_p (optional float; set p_is_threshold=true if the paper printed a BOUND rather than an exact p), decimals_mean (default 2), decimals_sd (default 2), decimals_t (default 3), decimals_p (default 3), use_welch (optional; LEAVE UNSET unless the paper states the test -- Welch's and Student's pooled t are both standard readings and either is accepted by default), p_tail (optional; 'two'|'one', default accepts either -- a one-tailed report is legitimate), num_samples (default 10000), seed (default 0)PASS `sampling='complex_survey'` WHEN THE PAPER SAYS SO -- survey or sampling weights, a complex survey design, NHANES WTMEC*/SDMVPSU, R's survey package, Stata svy:, PROC SURVEY*. This check then returns `indeterminate` instead of running, because a design-based estimate and its standard error are not functions of the printed means, SDs or counts: weighting moves the composition of the sample, not just its variance, so a disagreement is expected in BOTH directions and means nothing. MEASURED on an NHANES paper: six of one run's twenty severity-bearing tool findings were this one error.
<!-- /description:rivets_independent_t -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:21 -->
   - `rivets_independent_t`, `rivets_anova` — hand-calculation signatures.
<!-- /guidance:21 -->
