---
family: ratio
implementation:
- forensic_metascience_ai_toolkit.tools.ratio
tools:
  check_ratio:
    evidence: absolute
    consumes_table_cells: true
    purpose: Checks that a printed ratio follows from the numerator and denominator printed with it.
    assumptions:
    - The printed precision of all three values must be read off the literals; the attainable interval is computed at the corners of that rounding box, and a guessed precision either clears every ratio or accuses on rounding alone.
    - Assumes the ratio was computed from the two values as printed. Papers routinely divide unrounded intermediates they never show, or a discounted or subgroup quantity, which is why the verdict is capped at `suspicious` and never reaches `impossible` despite the arithmetic being exact.
    - A denominator whose own rounding interval spans zero makes the quotient unbounded; the check refuses rather than compares.
    - Across a TABLE, the evidence is not any single row but several rows implying DIFFERENT values for a quantity that can only have one -- read `implied_denominator`.
---
# `ratio` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## check_ratio

<!-- description:check_ratio -->
Verify a printed RATIO against the numerator and denominator printed beside it: cost-effectiveness ratios (ICERs), rates, cost-per-outcome, any "X per Y". Nothing else in this toolkit checks a division, and a health-economics paper's entire result is one -- a cost-utility table printed all three columns and the sweep recorded "no tool performs ratio verification", missing that its three rows implied three different incremental costs where there can only be one. YOU MUST SUPPLY all three `decimals_*`: a quotient's tolerance depends on both inputs' precision AND on the denominator's magnitude (B/SE with SE=0.5 tolerates about +/-0.5; the same precisions with SE=0.05 about +/-11), so without them the tool returns `indeterminate` rather than guessing. Read `implied_denominator` / `implied_numerator` out of the result: for a TABLE of ratios, several rows implying DIFFERENT values for a quantity that can only have one is far stronger evidence than any single mismatch. Capped at `suspicious` -- ratios are often computed from unrounded intermediates the paper never shows. Parameters: numerator, denominator, reported_ratio, decimals_numerator, decimals_denominator, decimals_ratio, description (optional)
<!-- /description:check_ratio -->
