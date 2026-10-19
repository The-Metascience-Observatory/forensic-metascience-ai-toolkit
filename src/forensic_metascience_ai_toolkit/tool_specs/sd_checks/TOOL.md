---
family: sd_checks
implementation:
- forensic_metascience_ai_toolkit.tools.sd_checks
tools:
  check_sd_range:
    evidence: absolute
    consumes_table_cells: true
    purpose: Checks a reported SD against the hard ceiling implied by the variable's range.
    assumptions:
    - 'min_val and max_val must be the variable''s TRUE attainable bounds. Say which via `bound_source`: an assumed range caps the verdict at `highly_suspicious`, and only a range the paper STATES (or one that is logically necessary, e.g. a percentage) can reach `impossible`.'
    - Pass decimals_sd; without it the precision is inferred from the literal, which errs wide but is a guess.
    - With n unknown the ceiling is the weakest over all n (range/sqrt(2), attained at n = 2); supplying n tightens it.
    - A negative SD is bound-free and impossible whatever else is unknown.
  grimmer_check:
    evidence: absolute
    consumes_table_cells: true
    purpose: Tests whether an SD is reachable for integer data with the reported mean and n.
    assumptions:
    - Both GRANULARITY modes (mean and SD) cap at `suspicious` unless `discreteness_source` is stated or logically necessary -- they are bound-free, not premise-free.
    - Observations must be integer-valued; ordinary continuous values otherwise read as `impossible`.
    - Printed precision must be supplied or inferred correctly -- a wrong assumed precision accuses.
    - Only integer and parity failures license `impossible`; range-dependent failures on assumed bounds cap at `suspicious`.
    - Both the sample and population SD conventions are tried; a population-only match caps at `suspicious`.
---
# `sd_checks` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## check_sd_range

<!-- description:check_sd_range -->
Check if SD is plausible given the data range. SD cannot exceed half the range. Parameters: sd, min_val, max_val, n (optional), decimals_sd (optional), bound_source (optional: 'stated' | 'logically_necessary' | 'assumed', default 'assumed'). The whole ceiling is derived from [min_val, max_val], so a range the paper never stated cannot license `impossible` -- it caps at highly_suspicious. PASS `decimals_sd`. The ceiling is a HARD mathematical bound, so the only slack a reported SD legitimately gets is its own rounding: an SD printed 3.5 asserts [3.45, 3.55), and only the bottom of that has to clear the ceiling. Without it the check uses a flat 1% margin -- 0.035 for an SD of 3.5, 0.35 for an SD of 35 -- a guess that scales with the wrong thing.
<!-- /description:check_sd_range -->

## grimmer_check

<!-- description:grimmer_check -->
GRIMMER test: check whether a standard deviation is mathematically possible for INTEGER data. You MUST pass data_type ('integer'|'likert'|'count' when the observations are whole numbers, 'continuous'|'proportion' when they are not) -- otherwise GRIMMER reports ordinary clinical values as impossible (e.g. systolic BP 128.43 +/- 15.21). ALSO pass decimals/decimals_sd as the values were PRINTED: a mean shown as '1.7' is 1 decimal, and assuming 2 shrinks its rounding interval tenfold and manufactures impossibilities. Parameters: mean, sd, n, scale_min, scale_max, decimals, decimals_sd, data_type
<!-- /description:grimmer_check -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:03 -->
   - `grimmer_check` — SDs from integer data.
<!-- /guidance:03 -->
