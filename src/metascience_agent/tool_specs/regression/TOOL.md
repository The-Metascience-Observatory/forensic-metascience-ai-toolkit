---
family: regression
implementation:
- metascience_agent.tools.regression
tools:
  check_regression:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Checks a regression coefficient's t = B/SE and its p within printed rounding.
    assumptions:
    - Assumes the reported t is B/SE and the reported p its t-distribution tail at the given df.
    - t is judged against the interval reachable from the PRINTED precision of B and SE, never a point.
    - Both sign conventions (signed t and |t|) and both tail conventions are accepted before anything is flagged.
    - Without df only the p check is skipped; the t = B/SE comparison still runs and can flag on its own.
    - An exact printed p above the achievable interval is an under-claim, capped at `suspicious`; a printed bound never is.
  check_regression_batch:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Runs the t = B/SE coefficient check over every row of a regression table in one call.
    assumptions:
    - Same premises as check_regression per row.
    - Pass per-row decimals; omitted, each row falls back to the widest plausible interval -- safe but blind.
    - A row with neither reported_t nor df is indeterminate; the aggregate is the worst row, and an all-unevaluated batch is never `consistent`.
---
# `regression` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## check_regression

<!-- description:check_regression -->
Verify regression coefficient consistency (t = B/SE). For a regression TABLE use `check_regression_batch` instead -- one call per coefficient is the single largest avoidable cost in a review. Parameters: b (coefficient), se (standard error), reported_t (optional), reported_p (optional), df (optional), decimals_b / decimals_se / decimals_t / decimals_p (optional), p_is_threshold (optional), p_relation (optional; supersedes p_is_threshold: '<' is true, '=' is false). PASS THE DECIMALS. t is recomputed from two ROUNDED values, so it is an interval whose width depends on the MAGNITUDE of SE as well as the printed precisions: B = 2.0 with SE = 0.5 pins t to about +/-0.5, while the same precisions with SE = 0.05 leave t anywhere within about +/-11. Omitted, the precisions are inferred towards the WIDEST plausible interval, which is safe but misses real discrepancies -- a value printed 0.340 is then checked as though it read 0.34. SAY WHETHER THE P IS A BOUND. "P < .001" and "P = .001" arrive here as the same float and are judged very differently: a bound is held to the number printed, an exact value gets its rounding interval. Undeclared, the p falls to the widest reading -- for a claimed "P < .001" that accepts a computed p of .006, six times the claim. SAY HOW THE P WAS PRINTED: pass `p_relation` '=' for an exact p ('p = .03'), '<' for a bound ('p < .05'), '>' for 'p > .05'. An EXACT p is checked in BOTH directions: one printed LARGER than anything the inputs allow is an under-claim, returned `suspicious` (never higher) with failure_mode `reported_p_above_recomputed`, and `decision_error` true when it crosses .05. MEASURED: 't(38) = 3.94, p = .696' (true p .00034, a documented decision error) came back `consistent` before this. A bound is checked only against over-claiming, since 'p < .05' is true of any smaller p. Left unset, a value that is no conventional bound (.696, .26) is read as exact and .05/.01/.001 keep the bound reading -- so an exact 'p = .05' or 'p = .001' needs '=' said out loud. PASS `p_adjustment='sphericity'` or `'multiplicity'` for a statistic covered by a correction the paper DECLARES (Greenhouse-Geisser / Huynh-Feldt; Bonferroni, Holm, Tukey, Scheffe): a printed p LARGER than the recomputation is then `indeterminate` (`under_claim_explained_by_adjustment`), while a p SMALLER than the numbers allow is still a finding. ONE-SIDED ONLY WHEN STATED (statcheck's rule): a p that reconciles only as a one-sided test counts as a match only when the paper says, anywhere, that its tests are one-tailed, one-sided or directional -- pass `one_tailed_stated=True` (quote it). Otherwise it is `suspicious` with failure_mode `reconciles_only_one_tailed_unstated` and the one-sided reading named beside it.
<!-- /description:check_regression -->

## check_regression_batch

<!-- description:check_regression_batch -->
Verify EVERY regression coefficient in ONE call. Use this for any regression table -- it is the normal case, and one call per coefficient is not. Measured on a real review, 79 of 111 tool calls were `check_regression` invoked once per row of a coefficient table; each call is a turn, and turns are the cost of a review. Each row is {b, se, reported_t (optional), reported_p (optional), df (optional), decimals_b, decimals_se, decimals_t, decimals_p (all optional), p_is_threshold (optional), p_relation (optional: '=', '<' or '>'; an EXACT p printed larger than B/SE allows is an under-claim, `suspicious`), df_source (optional, "reported" or "assumed"), p_adjustment (optional), one_tailed_stated (optional, true only when the paper states one-tailed / one-sided / directional tests; a p that reconciles only one-sided is otherwise `suspicious`), label (optional, carried through so a finding can name the coefficient)}. SET `p_is_threshold` TRUE ON ANY ROW WHOSE P IS A BOUND. "P < .001" and "P = .001" reach this tool as the same float; a bound is held to the number printed, an exact value gets its rounding interval. Undeclared, a claimed "P < .001" accepts a computed p of .006 -- six times the claim. PASS `df` WHERE THE PAPER GIVES IT: without df a t cannot be converted to a p, and the row comes back `indeterminate` with nothing checked. SET `df_source` TO "reported" ONLY IF THE PAPER PRINTS THE DF. If you chose the df yourself -- a large-sample/Wald-z value, n minus k, anything not on the page -- leave it out or say "assumed", and the batch will re-run at df 10, 30, 100 and 100000. A verdict that changes across that range is returned as `indeterminate`, because it is a property of your assumption and not of the paper. MEASURED on a real run: the same 68 coefficients give `suspicious` with 5 inconsistent rows at df 10 and `consistent` at df 30 and above, so an assumed df manufactured both an accusation and a clean bill on identical numbers. PASS THE `decimals_*` PER ROW, read from the literals. t is recomputed from two ROUNDED values, so it is an interval whose width depends on the MAGNITUDE of SE as well as the printed precisions: B = 2.0 with SE = 0.5 pins t to about +/-0.5, while the same precisions with SE = 0.05 leave t anywhere within about +/-11. Omitted, each row falls back to the WIDEST plausible interval, which is safe but blind -- a coefficient printed 0.340 is then checked as though it read 0.34. The aggregate severity is the WORST row, and a batch in which nothing could be evaluated returns `indeterminate`, never `consistent`. Parameters: rows (list of dicts)
<!-- /description:check_regression_batch -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:07 -->
   - `check_regression_batch` — EVERY coefficient of a regression table in
     ONE call. Pass `df` where the paper gives it, or the row cannot be
     evaluated. Use `check_regression` only for a single isolated coefficient.
<!-- /guidance:07 -->
