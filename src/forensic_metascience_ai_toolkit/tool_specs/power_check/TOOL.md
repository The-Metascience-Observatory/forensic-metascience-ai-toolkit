---
family: power_check
implementation:
- forensic_metascience_ai_toolkit.tools.power_check
tools:
  required_n:
    evidence: descriptive
    consumes_table_cells: false
    purpose: Computes the sample size a design needs for a target power; a pure calculator.
    assumptions:
    - Uses the standard model for the named test; it renders no verdict about any paper.
  verify_power_analysis:
    evidence: probabilistic
    consumes_table_cells: false
    purpose: Recomputes a stated a-priori power analysis and compares it to the N actually recruited.
    assumptions:
    - The named test and effect-size metric are assumed to be what the paper actually powered.
    - A small tolerance absorbs documented differences between G*Power, pwr and PASS.
    - Over-recruiting is treated as correct practice, never a discrepancy.
    - Indeterminate unless EVERY input was stated, which is the modal honest outcome.
    - It cannot detect an analysis that reproduces but powers the wrong hypothesis.
---
# `power_check` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## required_n

<!-- description:required_n -->
Smallest sample size meeting a target power, by exact noncentral distributions. Returns per-group and total n plus the achieved power at that n. Answers 'what N would this design have needed?' -- ask it of ANY comparison whose effect size you have, not only where the paper reports a power analysis; most papers report none, and that is exactly when the question is worth asking. PASS `actual_n` whenever you know the sample actually used: the reply then adds a `design_sensitivity` block comparing the design the paper HAD against the design its own reported effect needs. `tails=1` for a directional hypothesis the paper states -- do not assume one. This tool renders NO verdict about the paper and its severity is always `consistent`: a study being small is a fact about its sensitivity, not a defect, and it is for the reader to weigh. test_type: two_sample_t | one_sample_t | paired_t | anova_oneway | correlation | chi_square | two_proportions. Parameters: test_type, effect_size, alpha (default 0.05), power (default 0.80), tails (default 2), groups (default 2), df (optional), actual_n (optional)
<!-- /description:required_n -->

## verify_power_analysis

<!-- description:verify_power_analysis -->
Recompute a paper's stated a-priori power analysis and compare it to the N actually recruited. Uses exact noncentral distributions (noncentral t/F/chi-square, Fisher z), verified to exact agreement with R `pwr`. Returns `indeterminate` unless EVERY input needed to reproduce the calculation was actually stated by the paper -- in practice most power statements cannot be checked at all, and that is a reportable finding in itself rather than a failure. test_type: two_sample_t | one_sample_t | paired_t | anova_oneway | correlation | chi_square | two_proportions. Parameters: test_type, effect_size, alpha, target_power, n_reported, n_reported_is_per_group (default false), tails (1 or 2, ONLY as stated by the paper -- left unset the check tries both and refuses rather than accuse on our assumed convention), groups (default 2), df, allows_attrition_inflation (default true), allocation_ratio (default 1.0; anything else is refused)
<!-- /description:verify_power_analysis -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:17 -->
   - `verify_power_analysis` — a stated a-priori power calculation against the N
     actually recruited. Most published power statements cannot be reproduced
     because inputs are missing; that is a REPORTING finding worth recording,
     not a tool failure.
<!-- /guidance:17 -->

<!-- guidance:18 -->
   - `required_n` — "what N would this design have needed?", asked of ANY
     comparison whose effect size you have, not only where the paper reports a
     power analysis. Pass `actual_n` and it returns a `design_sensitivity` block
     comparing the design the paper HAD against the design its own reported
     effect needs. It renders NO verdict and its severity is always
     `consistent`: a study being small is a fact about its sensitivity, not a
     defect, and it is the reader's to weigh. Pass `tails=1` only where the
     paper STATES a directional hypothesis.
<!-- /guidance:18 -->
