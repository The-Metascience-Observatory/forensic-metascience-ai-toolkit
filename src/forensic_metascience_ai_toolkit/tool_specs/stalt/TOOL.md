---
family: stalt
implementation:
- forensic_metascience_ai_toolkit.tools.stalt
tools:
  stalt_check:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Checks a recomputed p against the threshold the paper printed for it.
    assumptions:
    - The recomputed p must be of the SAME test the printed threshold describes.
    - 'The threshold is read as an upper-bound claim: any p at or below it is consistent.'
    - A factor-of-two overshoot is tolerated as a one- versus two-tailed artefact.
    - Escalation scales with the size of the overshoot.
---
# `stalt` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## stalt_check

<!-- description:stalt_check -->
STALT: Check if a p-value hidden behind a threshold (e.g., 'p<0.05') is suspiciously small. Parameters: calculated_p (the actual p-value), reported_threshold (e.g., '<0.05')
<!-- /description:stalt_check -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:12 -->
   - `stalt_check` — exact p recovered behind a "p<X" threshold.
<!-- /guidance:12 -->
