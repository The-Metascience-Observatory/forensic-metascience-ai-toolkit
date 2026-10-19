---
family: count_percent
implementation:
- forensic_metascience_ai_toolkit.tools.count_percent
tools:
  check_count_percent:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Checks the printed count over the printed denominator against the printed percentage.
    assumptions:
    - The percentage is assumed to be over THIS n -- the assumption most likely to be wrong, since row, column and subgroup bases coexist in one table.
    - 'Ceiling `suspicious`, tighter than its class allows: a different percentage base is an ordinary reporting convention and no arithmetic disagreement rules it out.'
    - The printed percentage asserts a rounding interval, and its decimals must be supplied rather than assumed.
    - A count exceeding its denominator is reported as a wrong pairing, not as a defect in the paper.
---
# `count_percent` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## check_count_percent

<!-- description:check_count_percent -->
Does the printed COUNT over the printed denominator give the printed PERCENTAGE? Call it on every `n (%)` cell whose n you know -- it is STRICTLY STRONGER than grim_percentage there. GRIM asks whether a percentage is attainable for SOME integer numerator; this asks whether it matches THE numerator the paper printed. MEASURED: a cell reading `142 (73.0)` at n = 200 passes grim_percentage as `consistent`, because 73.0 is reachable at k = 146 -- while the printed count gives 100 x 142 / 200 = 71.0. That is a FALSE CLEAR, and it is what this check exists to catch. CAPPED AT `suspicious`, never higher. A percentage taken over a DIFFERENT base is the commonest convention in clinical tables -- row versus column percentages, subgroup denominators -- so a mismatch is evidence about which denominator was used at least as often as about the arithmetic. The result reports `implied_denominator`, which usually settles it at a glance: check it against the other denominators in the table before calling anything a defect. `decimals` is REQUIRED for a verdict: read it off the literal (`73.0` is 1). Without it the rounding interval is unknown and the result is `indeterminate` rather than a guess. A count LARGER than n returns `indeterminate`, not a flag: it proves this n is not the base for this percentage, which is a fact about the pairing. Parameters: count (int), percentage (float), n (int), decimals (int)
<!-- /description:check_count_percent -->
