---
family: sprite
implementation:
- metascience_agent.tools.sprite
tools:
  sprite_reconstruct:
    evidence: absolute
    consumes_table_cells: true
    purpose: Searches for integer samples matching a reported mean and SD, and proves when none exists.
    assumptions:
    - '`grim_fail` and `no_solution_proven` are bound-free but rest on the observations being integers, so they cap at `suspicious` unless `discreteness_source` is stated or logically necessary.'
    - Observations must be integers on a bounded scale; continuous measures are refused.
    - Printed precision drives which totals are admissible, so a wrong value accuses.
    - Only a proven no-solution is evidence; an exhausted search is a failed search, never an anomaly.
    - Range-dependent infeasibility rests on the scale bounds and caps at `suspicious` on assumed ones.
    - The population-SD convention is tried before accusing.
---
# `sprite` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## sprite_reconstruct

<!-- description:sprite_reconstruct -->
SPRITE: reconstruct plausible integer samples from a reported mean/SD. You MUST pass data_type ('integer'|'likert'|'count'); continuous measures are refused. ALSO pass decimals_mean/decimals_sd as PRINTED -- precision drives which totals are admissible, and assuming 2 dp for a 1-dp value produced false 'impossible' verdicts on genuine data. Outcomes: 'found' | 'no_solution_proven' (the ONLY one that is evidence) | 'grim_fail' | 'search_exhausted' (a failed search, NOT an anomaly). Parameters: mean, sd, n, scale_min, scale_max, num_samples, decimals_mean, decimals_sd, data_type
<!-- /description:sprite_reconstruct -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:13 -->
   - `sprite_reconstruct` — reconstruct distributions when mean+SD+n+range
     are all known; note bimodal/boundary-stacked shapes. **Run it on every
     bounded variable whose mean, SD and n are printed with a stated range**
     — a reconstruction whose only solutions stack at the range boundaries
     is a finding even when GRIM/GRIMMER pass, and skipping SPRITE because
     the granularity checks were quiet is how the 2026-08-21 apple-cider
     run missed the gold review's boundary-stacking finding entirely.
<!-- /guidance:13 -->
