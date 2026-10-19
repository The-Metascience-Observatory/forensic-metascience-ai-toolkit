---
family: flow
implementation:
- forensic_metascience_ai_toolkit.tools.flow
tools:
  check_flow_arithmetic:
    evidence: absolute
    consumes_table_cells: false
    purpose: Reconciles a CONSORT flow diagram's own ledger by exact integer arithmetic.
    assumptions:
    - The stages are one cohort's ordered cascade exactly as the diagram prints it; re-enrollment or overlapping stages mimic a mismatch.
    - Every n is transcribed as printed; a missing or fractional operand is refused, never assumed.
    - A drop with no stated exclusions is capped `suspicious` -- an omitted attrition reason is a reporting gap, not arithmetic.
---
# `flow` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## check_flow_arithmetic

<!-- description:check_flow_arithmetic -->
Reconcile a CONSORT/participant-flow cascade by EXACT integer arithmetic: each stage minus its stated exclusions must equal the next stage; arms must sum to their stage total; nothing after randomization may exceed it. Counts of people have no rounding window, so there is no tolerance parameter. Build `stages` top-down exactly as the diagram reads: [{"label": "assessed", "n": 240, "excluded": [{"reason": "declined", "n": 12}], "arms": [{"label": "treatment", "n": 100}]}]. Every n must be a whole number the paper PRINTS -- an absent, assumed, or fractional operand makes the tool REFUSE (`indeterminate`), never accuse. A drop between stages with no stated exclusions is `unaccounted_attrition`, capped `suspicious` (papers legitimately omit attrition reasons); a broken identity with every operand printed is `impossible`. Pass `randomized_label` to anchor the analyzed<=randomized check when no stage label contains "random". A stage the paper prints in more than one place (abstract, Results, figure) carries the other printings in `also_reported: [{"n": 16, "source": "Abstract"}]`; a mismatch is `conflicting_reports` (`highly_suspicious`). A `consistent` result covers only the counts passed -- report it as "the cascade from <section> adds up", never as "the flow reconciles". Parameters: stages (list of stage objects), randomized_label (optional), description (optional)
<!-- /description:check_flow_arithmetic -->
