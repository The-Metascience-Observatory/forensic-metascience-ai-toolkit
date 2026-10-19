---
family: estimates
implementation:
- metascience_agent.tools.estimates
tools:
  absence_of_evidence:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Tests whether a stated 'no effect' conclusion survives its own confidence interval.
    assumptions:
    - 'The null must be locatable: 1 for ratio measures, 0 for differences; without `measure` it declines.'
    - The CI is taken at face value; the verdict targets the CLAIM made about it, not the data.
    - Equivalence is judged only against a supplied SESOI; with none it describes the interval and declines.
  check_estimate_ci:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Reconciles a point estimate with its own CI and reported p on the correct scale.
    assumptions:
    - 'CIs are assumed Wald-type: symmetric on the linear scale, or on the LOG scale for OR/RR/HR/IRR -- pass `measure`.'
    - Exact, profile and bootstrap CIs are legitimately asymmetric and can fail the midpoint check innocently.
    - Alternative confidence levels are tried before a 'wrong p' is reported only when the paper states no level; a STATED level is never overridden. p is recovered by normal approximation.
    - A p that cannot be placed against alpha at its own printed precision is not classified.
    - 'A threshold p (''P < .001'', passed with `reported_p_operator`) is an interval claim: flagged only when the bound is unreachable at the stated level AND at the one common level that could still rescue it.'
---
# `estimates` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## absence_of_evidence

<!-- description:absence_of_evidence -->
Test whether a paper's stated 'no effect' / 'no difference' conclusion survives its own confidence interval. 'Not significant' is not 'no effect': this reports the largest effect the interval still permits. ALWAYS PASS `measure` -- the null is 1 for a ratio measure (OR/RR/HR/IRR) and 0 for a difference, and without it this tool cannot tell which, so it DECLINES to judge. Omitting it used to invert the verdict: the odds-ratio interval [0.85, 1.42] was reported as EXCLUDING the null. WITHOUT a smallest effect size of interest (sesoi) it describes the interval and declines to judge equivalence -- that cannot be claimed against an unstated threshold. IF THE PAPER PRINTS NO INTERVAL, pass `b` and `se` instead and one is derived -- the same Wald arithmetic `check_regression` performs, marked `interval_source: derived` so it never passes as the paper's. Give `df` for the t distribution; without it the normal is used and the result says so. Measured: 7 archived papers could not be checked here at all for want of an interval, and in two of them the null result was the paper's own conclusion. Parameters: ci_low, ci_high OR b, se (+ optional df), measure (required in practice), sesoi (optional), claim_of_no_effect (default true), null_value (optional; pass instead of `measure` only when you know the null exactly)
<!-- /description:absence_of_evidence -->

## check_estimate_ci

<!-- description:check_estimate_ci -->
Reconcile a point estimate against its own confidence interval: interval ordered and containing the estimate, estimate at the CI-implied midpoint ON THE CORRECT SCALE, and the p recovered from the CI agreeing with the reported p. PASS `measure` -- for ratio measures (OR/RR/HR/IRR) the CI is symmetric in LOG space, and checking linear symmetry misfires on 100% of hazard ratios at SE_log = 0.4 (measured, 2000/2000; the scale inference is what keeps the unlabelled path clean). A 'wrong' p is tested against alternative confidence levels before being flagged -- but only when the paper states NO level. PASS `confidence_level` ONLY IF THE PAPER STATES IT (0.95, 0.90, 0.80), and omit it otherwise: a STATED level is never overridden, and a p that reconciles only at a different level returns `suspicious` with failure_mode `reconciles_only_at_other_level` (MEASURED: an 80% CI 0.31-2.43 around 1.37 printed P = .01, later corrected by the journal to P = .10, came back `consistent` as 'behaves like a 95% CI'). Unstated, 95% is assumed and a level rescue is a note. Parameters: estimate, ci_low, ci_high, measure (optional), reported_p (optional), reported_p_operator (default "="), confidence_level (optional; only when stated), null_value (optional; defaults to 1 for ratios, 0 otherwise), decimals (optional). A THRESHOLD p IS EXPRESSIBLE AND MUST BE PASSED AS ONE: for 'P < .001' pass reported_p=0.001 with reported_p_operator='<' ('<=', '>', '>=' likewise for 'P ≤ .05' or 'P > .99'). Never coerce 'P < .001' to reported_p=0.001 alone -- that asserts equality and can be rescued as a mislabelled CI level -- and never omit the p because it is a threshold: that silently skips the p cross-check and records the row as consistent (measured: an abstract-headline 'ARR 0.185 (0.046-0.748), P < .001' whose CI-implied p is .018 passed clean under both encodings). PASS `decimals` -- the PRINTED precision of the COARSEST of the three numbers, since a comparison among them is only known to that precision. Without it the tolerance is re-derived from the parsed floats, and it errs WIDE: a bound printed 1.40 reads as one decimal, because str(1.40) is '1.4', so the tolerance comes out ten times too LOOSE and a real discrepancy can be waved through. An integral 5 reads at zero decimals, which is what it asserts.PASS `sampling='complex_survey'` WHEN THE PAPER SAYS SO (survey weights, NHANES WTMEC*, R's survey package, Stata svy:, PROC SURVEY*). The p-vs-CI comparison then becomes ONE-SIDED: a design-based interval uses a t with the survey degrees of freedom, and p is monotone decreasing in df, so the normal-approximation recovery is a LOWER BOUND on p. A printed p ABOVE it is reachable at some df and is not reported; a printed p BELOW it is reachable at no df and still is. Ordering, containment and the midpoint check are unaffected.
<!-- /description:check_estimate_ci -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:15 -->
   - `check_estimate_ci` — an effect estimate against its own confidence
     interval. **The highest-yield check on clinical and epidemiological
     papers**, where estimates with CIs outnumber mean(SD) cells more than two
     to one. ALWAYS pass `measure` (OR/RR/HR/IRR): those intervals are
     symmetric in LOG space, and a linear check misfires on about a third of
     hazard ratios.
<!-- /guidance:15 -->

<!-- guidance:16 -->
   - `absence_of_evidence` — whenever the paper concludes "no effect", "no
     difference" or "comparable". Reports the largest effect the interval still
     permits. Without a stated SESOI it declines to judge, and that refusal is
     the correct result to record.
<!-- /guidance:16 -->
