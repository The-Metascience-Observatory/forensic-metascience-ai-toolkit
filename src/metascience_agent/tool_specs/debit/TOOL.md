---
family: debit
implementation:
- metascience_agent.tools.debit
tools:
  debit_check:
    evidence: absolute
    consumes_table_cells: true
    purpose: Checks that a binary variable's SD is the one its mean and n mathematically force.
    assumptions:
    - The data must be 0/1-coded; anything else is refused rather than judged.
    - decimals_mean and decimals_sd must be the PRINTED precision -- a defaulted 2 dp falsely accused 73.6% of 1 dp rows.
    - Both the sample (n-1) and population SD conventions are tried; a population-only match caps at `suspicious`.
    - Values must be printed, not read off a figure.
  debit_check_batch:
    evidence: absolute
    consumes_table_cells: true
    purpose: Runs DEBIT over many binary rows; escalates only on a pattern of impossible rows.
    assumptions:
    - Same arithmetic per row, and every row submitted must be genuinely binary.
    - Supply per-row printed decimals; the batch default of 2 dp falsely accuses 1 dp proportions.
    - Escalates only on a PATTERN of impossible rows; a lone hit stays `suspicious`.
    - A batch in which no row was evaluated is indeterminate, never `consistent`.
---
# `debit` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## debit_check

<!-- description:debit_check -->
DEBIT: For binary 0/1 variables, the SD is mathematically determined by the mean and n (SD = sqrt(k(n-k)/(n(n-1))) for k ones). Use ONLY on Table 1 rows where the variable really is a 0/1 indicator reported as a proportion with mean/SD. Pass data_type='binary'; anything else returns 'indeterminate' rather than a finding. NOTE: a row consistent only under the population-SD convention sqrt(p(1-p)) is reported as 'suspicious', NOT 'impossible' -- that is a legitimate reporting convention, not fabrication. Parameters: mean (0..1), sd, n, decimals_mean (default 2), decimals_sd (default 2), data_type (str)
<!-- /description:debit_check -->

## debit_check_batch

<!-- description:debit_check_batch -->
DEBIT batch: run DEBIT on a list of binary-variable rows. Use when a Table 1 has many 0/1 indicators. Each row: {label, mean, sd, n, decimals_mean (optional), decimals_sd (optional)}. Parameters: rows (list of dicts), decimals_mean (default 2), decimals_sd (default 2)
<!-- /description:debit_check_batch -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:04 -->
   - `debit_check` / `debit_check_batch` — binary 0/1 variables' mean+SD.
<!-- /guidance:04 -->
