---
family: duplication
implementation:
- metascience_agent.tools.duplication
tools:
  detect_duplication:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Finds identical (mean, SD) pairs recurring across supposedly independent samples.
    assumptions:
    - Blocks are assumed to describe INDEPENDENT samples unless they share a sample_id; confirm editorially before accusing.
    - The chance model is Poisson over all comparisons, with spans inferred from the observed values.
    - Round values collide by chance far more often and are discounted.
    - 'Capped at `highly_suspicious`: duplication is improbable, never impossible.'
---
# `duplication` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## detect_duplication

<!-- description:detect_duplication -->
Detect duplicated/copy-pasted summary statistics WITHIN a table and ACROSS tables/studies. This catches identical (mean, SD) pairs appearing in two supposedly-independent samples — a data-integrity red flag that per-cell GRIM/GRIMMER cannot see. ALWAYS run this when a paper reports 2+ tables of means/SDs (e.g. one per study): compare every table against every other. Each block = {label, sample_id (blocks sharing a sample_id describe the SAME participants and are EXPECTED to match — set this to avoid false positives), independent (bool, default true), cells: [{label, value, sd}]}. Use parse_table to build the cells. Severity is keyed on the count of identical pairs (>=3 => highly_suspicious) and capped at highly_suspicious. Parameters: blocks (list of dicts), decimals_mean (int, default 2), decimals_sd (int, default 2), near_match (bool, default true)
<!-- /description:detect_duplication -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:22 -->
   - `detect_duplication` — **when the paper has 2+ tables/studies of
     means/SDs, ALWAYS run this**, comparing every table against every other
     (and within each table). Identical (mean, SD) pairs across independent
     studies are a copy-paste / recycled-data red flag that per-cell checks
     cannot see. Build each block's `cells` from `parse_table` output; set
     `sample_id` so blocks describing the SAME participants aren't
     false-flagged (see rulebook rule 11).
     A `Total` / `Overall` / `All participants` column is NOT an independent
     sample — it aggregates the arms printed beside it, so a match between an
     arm and the total is arithmetic, not duplication. Never flag it. The same
     goes for a subgroup row against the group that contains it. This matters
     more than it used to: XML recovers whole tables where PDF extraction lost
     most cells, so these legitimate repeats now reach the tool on every paper.
<!-- /guidance:22 -->
