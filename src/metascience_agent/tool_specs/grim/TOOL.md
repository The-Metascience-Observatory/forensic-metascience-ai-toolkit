---
family: grim
implementation:
- metascience_agent.tools.grim
tools:
  grim_check:
    evidence: absolute
    consumes_table_cells: true
    purpose: Tests whether a mean of integer data is reachable at all for its n and printed precision.
    assumptions:
    - Observations must be integer-valued; continuous data is refused rather than judged.
    - '`decimals` must be the precision AS PRINTED -- ''5.9'' is 1, not 2; a wrong value accuses, so a missing one is refused.'
    - Both the round-half and truncation reporting conventions are tried; a truncation-only pass caps at `suspicious`.
    - Range failures on ASSUMED bounds cap at `suspicious`; only stated bounds license `impossible`.
    - 'GRANULARITY failures cap at `suspicious` unless `discreteness_source` is `stated` or `logically_necessary`: the arithmetic is airtight only if each subject contributed a whole number, and `data_type` merely asserts that.'
    - The mean and n must be printed values; figure-read inputs are refused.
  grim_percentage:
    evidence: absolute
    consumes_table_cells: true
    purpose: Tests whether a percentage can be an integer count's share of the sample.
    assumptions:
    - The percentage must be a SHARE of the sample, 100*k/n for integer k.
    - 'Mean changes, concentrations and ratios are refused: they are not constrained to multiples of 100/n.'
    - n must be the true denominator OF THIS percentage, and `decimals` must match the printed precision.
    - Both the round-half and truncation reporting conventions are tried; a truncation-only pass caps at `suspicious`. SPSS and several journal styles truncate percentages, and 9/93 = 9.6774 printed as 9.6% is a truncating reporter, not an impossibility.
  grim_sweep:
    evidence: absolute
    consumes_table_cells: true
    purpose: Finds every sample size at which several percentages could share one denominator.
    assumptions:
    - Every value must be a share of the SAME sample -- a shared denominator is exactly what is being tested.
    - An empty intersection reaches `impossible` only when n_max_source='stated' (n_max is the paper's own total N) and n_min covers the floor; otherwise the sweep refuses with `indeterminate` -- emptiness inside a range WE chose is a fact about the search, not the paper.
    - 'No data_type guard here: the caller must verify the values are count shares, not continuous percentages.'
  reconstruct_2x2:
    evidence: absolute
    consumes_table_cells: true
    purpose: Reconstructs the 2x2 tables consistent with two column percentages and a total N.
    assumptions:
    - The two percentages must be column-conditional shares of integer counts.
    - n_total must be the true total, and `decimals` must match the printed precision.
    - Impossibility is decided over EVERY column split; the balance ratio only orders the plausible ones.
    - A non-matching chi-square yields indeterminate, never an accusation.
---
# `grim` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## grim_check

<!-- description:grim_check -->
GRIM test: Check whether a mean of whole-number observations is reachable at all for its n and printed precision. ONLY valid for integer-valued observations. You MUST pass data_type: 'integer'|'likert'|'count' when the underlying observations are whole numbers, or 'continuous'|'proportion' when they are not (GRIM then refuses to evaluate instead of reporting a false anomaly -- e.g. a weight in kg). The core test -- is the mean a multiple of 1/n to its printed digits? -- needs NO scale range: a count with no stated maximum (behaviours tallied in a session, number of events, cells counted) is exactly what GRIM is for, and a missing maximum is never a reason to skip it. The range only feeds a second, separate out-of-range check. For such a count pass scale_min 0 with bound_source 'logically_necessary' and a scale_max far above every value in the column, which then cannot fire. Pass bound_source 'stated' only if the PAPER gives the range ('assumed', the default, caps an out-of-range result at 'suspicious'). Pass discreteness_source 'stated' when the paper says each subject's value is a whole number ('number of crossings were tallied', 'number of falls'); a granularity failure on an assumed discreteness caps at 'suspicious'. Use n = subjects only when each subject contributes ONE whole number: a per-subject average over k trials, items or observers moves in steps of 1/(k*n), and GRIM at 1/n then reports honest means as impossible -- if the paper averages, say so and do not run it at 1/n. Parameters: mean (number), n (int), scale_min (int, default 1), scale_max (int, default 7), decimals (int, REQUIRED -- the printed decimals), data_type (str), bound_source (str), discreteness_source (str)
<!-- /description:grim_check -->

## grim_percentage

<!-- description:grim_percentage -->
Apply GRIM test to a percentage. More powerful than testing means directly. ONLY valid when the percentage is a SHARE of the sample -- 100*k/n for an integer count k of the n units. You MUST pass data_type: 'proportion'|'binary'|'count' when the percentage is such a share, or 'continuous' when it is a mean change, a concentration or a ratio (GRIM then refuses instead of manufacturing a false impossibility -- e.g. "glucose fell 23.7%"). Parameters: percentage (0-100), n (int), decimals (int, default 1), data_type (str, REQUIRED -- omitting it refuses rather than assuming a share)
<!-- /description:grim_percentage -->

## grim_sweep

<!-- description:grim_sweep -->
GRIM n-sweep: given multiple percentages claimed to come from the SAME sample, find every n in [n_min, n_max] for which all percentages simultaneously pass GRIM. Empty intersection ⇒ they cannot share a denominator. Use when a paper reports several proportions (e.g., a row of demographic %s) but the cell size is missing or contested. Parameters: values (list of floats), n_max (int), n_min (int, default 2), decimals (int, default 1), value_type (str, 'percentage' or 'proportion', default 'percentage'), n_max_source (str, 'stated' when n_max is the paper's OWN total N, default 'assumed'; an empty intersection is only 'impossible' when the range is the paper's, because emptiness inside a range WE chose is a fact about our search -- otherwise the sweep refuses with 'indeterminate')
<!-- /description:grim_sweep -->

## reconstruct_2x2

<!-- description:reconstruct_2x2 -->
Reconstruct a 2×2 contingency table from two column-conditional percentages and a total N. Searches every (col1, col2) pair summing to n_total for ones where both percentages GRIM-pass. Optionally filters by reported chi-squared. Use when a paper gives row-percentages and a chi-squared but suppresses the cell counts. Parameters: pct_col1 (float), pct_col2 (float), n_total (int), decimals (int, default 1), value_type (str, default 'percentage'), reported_chi2 (float, optional), chi2_tolerance (float, default 0.05), balance_ratio_max (float, default 4.0)
<!-- /description:reconstruct_2x2 -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:01 -->
   - `grim_check` / `grim_percentage` — means/percentages from integer or
     Likert/count data ONLY (never continuous measures). GRIM needs whole
     numbers per subject and n, NOT a scale maximum: that is GRIMMER's and
     SPRITE's premise, not GRIM's. Run it on every mean of counts the paper
     tallies per subject (behaviour counts, events, cells) even when no
     maximum is stated, and record a skip in `unchecked` only for a reason
     that applies to GRIM itself (continuous data, a per-subject average over
     trials or observers, no n). For TABLE cells, `declare_table` (step 2a)
     replaces these per-cell calls: the harness checks every cell it covers.
     Call `grim_check` / `grim_percentage` yourself for means and percentages
     printed in prose, the abstract or a figure caption.
<!-- /guidance:01 -->

<!-- guidance:02 -->
   - `grim_sweep` — several percentages claiming a shared n; empty joint
     n-set ⇒ impossible.
<!-- /guidance:02 -->
