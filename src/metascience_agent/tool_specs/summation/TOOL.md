---
family: summation
implementation:
- metascience_agent.tools.summation
tools:
  check_summation:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Checks that printed values sum to their stated total within accumulated rounding.
    assumptions:
    - The values are assumed exhaustive, non-overlapping addends of the stated total; overlap or an omitted row mimics a mismatch.
    - The window derives from the printed decimals of every addend and of the total; with neither decimals nor tolerance it refuses.
    - Count columns that must hold exactly take tolerance = 0; percentage columns legitimately misbalance by rounding.
  check_summation_batch:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Runs every summation check in one call; the worst row sets the verdict.
    assumptions:
    - Same premises as check_summation per row.
    - Give `decimals` per row; a row with no printed precision is refused rather than guessed.
    - An all-unevaluated batch is indeterminate, never `consistent`.
---
# `summation` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## check_summation

<!-- description:check_summation -->
Check if values sum to expected total (e.g., percentages to 100). For MORE THAN ONE sum, use `check_summation_batch` instead -- one call per sum is the single largest avoidable cost in a review. YOU MUST SUPPLY `decimals`: the window a sum is allowed depends on how many addends there are and how precisely each was printed. Twenty values printed to one decimal permit the total to be off by +/-1.0; two values printed to two decimals permit +/-0.01. Without it the tool RETURNS `indeterminate` rather than guessing, because there is no safe default -- the old flat 0.5 was twenty times too tight for the first column and fifty times too loose for the second. Use `tolerance` only where something other than rounding sets the window (a count column that must hold exactly takes tolerance=0). Parameters: values (list), expected_sum, decimals (int, or list of int per value), decimals_total (optional), tolerance (optional), description (optional)
<!-- /description:check_summation -->

## check_summation_batch

<!-- description:check_summation_batch -->
Run EVERY summation check in ONE call. Use this whenever a paper has more than one thing that must add up -- CONSORT/flow-diagram arms, table column totals, percentage columns, subgroup counts against their total. Measured on a real review, 55 of 124 tool calls were `check_summation` invoked once per sum; each call is a turn, and turns are the cost of a review. Each row is {values, expected_sum, description, tolerance (optional, overrides the batch default -- a percentage column rounding to 100 needs a wider window than a count column that must be exact), decimals (int or list of int -- the printed precision of the addends), decimals_total}. GIVE `decimals` PER ROW: the window a sum is allowed depends on how many addends there are and how precisely each was printed, so one window across a whole batch is wrong for most of it, and a row with no precision returns `indeterminate` rather than guessing. The aggregate severity is the WORST row, and a batch in which nothing could be evaluated returns `indeterminate`, never `consistent`. Parameters: rows (list of dicts), tolerance (optional batch-wide override)
<!-- /description:check_summation_batch -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:11 -->
   - `check_summation_batch` — EVERY sum in ONE call: flow-diagram arms,
     column totals, percentage columns, subgroups against their total.
     Use `check_summation` only for a single isolated sum.
<!-- /guidance:11 -->
