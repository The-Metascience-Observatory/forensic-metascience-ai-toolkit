---
family: heuristics
implementation:
- metascience_agent.tools.heuristics
tools:
  flag_round_n:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Triage flag for several distinct sample sizes that are all suspiciously round.
    assumptions:
    - 'A base-rate heuristic: fabricated papers over-represent round Ns, but so do honest recruitment targets.'
    - Needs at least three reported sizes with at least two distinct before it says anything.
    - 'Ceiling `suspicious`: a weak signal that escalates only alongside stronger findings.'
  flag_uninformative_stat:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Flags comparisons whose printed precision cannot pin down the test outcome.
    assumptions:
    - The comparison is modelled as a one-way ANOVA computed from these group means, SDs and ns.
    - Inputs are assumed uniform over their truncation intervals for the simulated p-range.
    - 'Ceiling `suspicious`: an over-claimed p is flagged with the one-way-ANOVA assumption disclosed, never escalated -- rivets_anova owns the accusation-grade reported-p check.'
    - 'The achievable p-range is Monte Carlo PLUS an exact corner search. Sampling the interior alone reaches a vertex with probability zero, and the extreme of F lives on one: the gap branded a reachable p=0.35 UNREACHABLE when the corner gives 0.307.'
---
# `heuristics` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## flag_round_n

<!-- description:flag_round_n -->
Heuristic flag (Heathers §'Big round sample sizes'): given a list of reported sample sizes (cell sizes, group sizes, or totals), flag if all are suspiciously round. Triage signal only — not proof of fabrication. Parameters: ns (list of ints), moderate_modulus (default 50), strong_modulus (default 100)
<!-- /description:flag_round_n -->

## flag_uninformative_stat

<!-- description:flag_uninformative_stat -->
Heuristic flag (Heathers §'Uninformative statistics'): for a multi-group ANOVA-style comparison, check whether the reported precision of the means/SDs is fine enough to pin down the test outcome. Returns the analytic p-range and flags if it straddles the significance threshold or is wider than `p_range_warn`. Also flags if the reported p is outside the implied range. Parameters: means (list), sds (list), ns (list), reported_p (optional), decimals_mean (default 2), decimals_sd (default 2), decimals_p (default 3), significance_threshold (default 0.05), p_range_warn (default 0.5), num_samples (default 3000), seed (default 0)
<!-- /description:flag_uninformative_stat -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:20 -->
   - `flag_uninformative_stat` — heuristic.
<!-- /guidance:20 -->
