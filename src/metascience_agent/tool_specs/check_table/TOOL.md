---
family: check_table
implementation:
- metascience_agent.dispatch
tools:
  check_table:
    evidence: absolute
    consumes_table_cells: true
    purpose: Runs every applicable check on a typed table in one call; the worst row wins.
    assumptions:
    - A ROUTER, so the `absolute` class above describes only its CEILING, not every row it returns. `impossible` can still only come from a bound-free arithmetic check; but a `highly_suspicious` or `suspicious` row may have come from a probabilistic one (a Wald-CI judgement, a dispersion plausibility). Read the per-row `tool` and look up ITS card -- the routed check's evidence class governs, not this one.
    - Variables must be truthfully declared -- data_type, bounds and bound_source gate every downstream check.
    - Declare provenance for figure-read values; the exact-arithmetic checks then refuse them rather than judge them.
---
# `check_table` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## check_table

<!-- description:check_table -->
Run EVERY applicable check on a whole table in ONE call. Use this for any table instead of calling per-cell tools one at a time -- a real run made 58 tool calls on one paper, 51 of them the same check repeated per cell. Pass the typed `cells`, the `variables` you declared in Pass 0, and `bindings` mapping each row label to a variable id. Which checks apply is then DETERMINED by cell kind x variable family; you do not choose them. A declared variable also RESOLVES cells that syntax alone must refuse: `48.90 (14.46)` under a bare label is ambiguous, but once you declare the variable continuous the reading is fixed. That is what makes declaring variables pay. Returns every non-consistent result in full, a count of the consistent ones, and a machine-generated `not_run` list giving the REASON each check was refused -- so coverage does not depend on you remembering. ALWAYS report the denominator: 3 suspicious out of 140 checks and 3 out of 4 are different papers. Set `provenance` to measured_raster / measured_vector when the values were read off a figure; the exact-arithmetic checks then refuse them automatically. IF THE RESULT CARRIES A NON-EMPTY `declaration_template`, CALL THIS TOOL AGAIN WITH IT FILLED IN. That field is this tool telling you precisely which variables are blocking checks it could otherwise run: each row hands you a `declare` block to pass as `variables`, a `bind` block to pass as `bindings`, and `would_unlock` naming the checks you get back for it. A non-empty template means cells that ARE checkable are going unchecked for want of one declaration each -- MEASURED on real tables, 88% of consumable-but-unrunnable cells are blocked on exactly this, and one table offered 7 declarations covering 15 cells. Declare from the paper, never from a guess: set `bounds_are_stated` true ONLY if the paper states the range, because a fabricated bound INVERTS a check rather than weakening it. Parameters: cells, variables, bindings, provenance
<!-- /description:check_table -->
