---
family: effect_size_from_f
implementation:
- metascience_agent.tools.effect_size_from_f
tools:
  effect_size_from_f:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Recomputes partial eta-squared (or Cohen's f) from a printed F and its degrees of freedom and compares it to the effect size printed beside it.
    assumptions:
    - The printed label names the measure the authors actually computed. Only partial eta-squared and Cohen's f follow from F and df; eta-squared, generalised eta-squared, omega-squared and model R-squared need a total sum of squares the paper does not print, and are REFUSED by name rather than scored against the partial formula.
    - Both numbers are rounded, so each implies an interval, and a flag needs the two intervals to be DISJOINT. Comparing the point values convicts honest rounding at either end.
    - df1 is the paper's, never assumed. Assuming 1 collapses the formula to F/(F + df2) -- the one-numerator-df special case -- and makes every multi-level factor look wrong.
    - The F and the effect size are assumed to come from the SAME model. A value carried over from another analysis, or an F corrected for sphericity reported against uncorrected df, produces this signature and is not an arithmetic violation.
    - 'Ceiling `suspicious`: a mismatch says the printed pair do not reconcile, not that either number is impossible.'
---
# `effect_size_from_f` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## effect_size_from_f

<!-- description:effect_size_from_f -->
Reconcile a printed effect size against the F and degrees of freedom beside it. partial eta-squared = (F*df1)/(F*df1 + df2); Cohen's f follows from it. USE THIS INSTEAD OF check_ratio. The shortcut F/(F + df2) is only the df1 = 1 special case and is wrong for every multi-level factor -- this takes df1 and REFUSES without it rather than assuming 1. measure is REQUIRED and only partial_eta_squared and cohens_f are recoverable: eta_squared, generalized_eta_squared, omega_squared and model r_squared need a total sum of squares the paper does not print, and are refused BY NAME rather than scored against the partial formula (doing that would flag every paper that honestly reports generalised eta-squared). Both numbers are rounded, so the comparison is interval-to-interval and a flag needs the two intervals to be DISJOINT. Capped at suspicious: a label naming a different effect-size family, a value carried from another model, or an F corrected for sphericity against uncorrected df all produce a mismatch and none is an arithmetic violation. Parameters: f_value (float), df1 (int, REQUIRED), df2 (int), reported_effect_size (float, optional -- omit to just compute), measure (str, default 'partial_eta_squared'), decimals_f (int), decimals_effect_size (int)
<!-- /description:effect_size_from_f -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:06 -->
   - `effect_size_from_f` — a printed **partial eta-squared** (or Cohen's f)
     against the F and df beside it. Psychology ANOVAs print η²ₚ constantly and
     it was uncheckable until now. Do NOT hand-roll it through `check_ratio`:
     `F/(F + df2)` is only the `df1 = 1` case and understates the effect for
     every multi-level factor, so an honest paper looks wrong. `eta_squared`,
     `generalized_eta_squared` and `omega_squared` need a total sum of squares
     the paper does not print and are refused by name — check the Methods for
     which measure it actually is before reporting a mismatch.
<!-- /guidance:06 -->
