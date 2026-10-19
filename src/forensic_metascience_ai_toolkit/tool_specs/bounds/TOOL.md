---
family: bounds
implementation:
- forensic_metascience_ai_toolkit.tools.bounds
tools:
  check_statistic_bounds:
    evidence: absolute
    consumes_table_cells: true
    purpose: Checks a value against the range its measure permits BY DEFINITION -- and treats a violation as evidence about our extraction before evidence about the paper.
    assumptions:
    - 'The bound is logically necessary, never conventional: a correlation is bounded by Cauchy-Schwarz, a p-value by the definition of a probability. A merely expected range is an assumption, and unknown measures are refused rather than judged against our expectations.'
    - 'The value reached us intact. This is the assumption the whole tool is built around distrusting: a decimal-point slip or a value read from the wrong column produces exactly this signature, and is far likelier than a paper printing a correlation of 11.3.'
    - 'GREG''S PRIOR, 2026-08-11, and the reason for the ordering: gross violations are uncommon even in fraudulent papers, because fabricators produce plausible numbers. So an unverified violation caps at `indeterminate` with failure_mode `extraction_suspect` -- a flag on OUR reading, explicitly not a finding.'
    - '`impossible` requires `extraction_verified`, meaning the value was re-read in the paper itself and both the digits and the column confirmed. Verification is the price of the accusation; the escape is evidential, not the model''s discretion.'
    - Even when verified, the tool names the innocent readings -- a typesetting error, a mislabelled row -- because a confirmed impossible value still does not establish who produced it.
---
# `bounds` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## check_statistic_bounds

<!-- description:check_statistic_bounds -->
Is a value inside the range its measure LOGICALLY permits? Call it the moment you hold a statistic that looks impossible on its face -- a correlation above 1, a p-value above 1, a percentage above 100, an alpha above 1. IT WILL NOT LET YOU ACCUSE THE PAPER, and that is deliberate. A value that far outside its own definition is not the kind of error that survives to publication in an honest paper OR a fabricated one -- fabricators produce plausible numbers, because that is the point of fabricating them. The likeliest author of the error is whoever read the page, which was us. So the verdict is `indeterminate` with failure_mode `extraction_suspect`, and the result names the specific decimal-point slip that would explain it (11.3 as a correlation reads as 0.113 with the point two places out). GO AND CHECK THE SOURCE. Re-read the value in the paper itself: the decimal point against the printed figure, and the COLUMN -- a mean or a test statistic read out of the wrong column is the other common cause. If the value is confirmed there, call this again with extraction_verified=true and it returns `impossible`, which the bound then fully licenses. Verification is the price of the accusation. Parameters: value, measure (r/correlation, p_value, percentage, proportion, r_squared, kappa, icc, cronbach_alpha, auc, sd, se, variance, chi_squared, f_statistic, n), extraction_verified (default false), source_quote.
<!-- /description:check_statistic_bounds -->
