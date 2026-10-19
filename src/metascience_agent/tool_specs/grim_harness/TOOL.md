---
family: grim_harness
implementation:
- metascience_agent.grim_harness
tools:
  list_tables:
    evidence: descriptive
    consumes_table_cells: false
    purpose: Lists every table the harness GRIM sweep covers, with the key a declaration uses and each column's printed n; renders no verdict.
    assumptions:
    - A column without an `n` has none printed in its header; the n may still be stated in Table 1 or the text, and then has to be declared.
  declare_table:
    evidence: absolute
    consumes_table_cells: true
    purpose: Records what a table's cells are (row variables, column n's, shares) and runs GRIM on every cell the declaration covers; the harness files the failures.
    assumptions:
    - The declaration IS the premise. A row declared a single integer-scored item when the paper averages several items, or a percentage declared a share of the units when it is a percentage-valued measurement, makes every failure on it a false accusation.
    - A column n is a group size. A cell that fails at it but passes at an n up to 5% smaller is reported as explained by possible non-response, not as an error.
---
# `grim_harness` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## list_tables

<!-- description:list_tables -->
List every table of the paper (main text and supplements) that the harness GRIM sweep covers, each with the key `declare_table` uses (`T1`, `T2`, ...), its label, caption, page and source file, its row labels, and its columns with the n printed in each column header (`n_source: header`) or in a header row (`header_row`). Call it once, before declaring any table. Parameters: paper_dir
<!-- /description:list_tables -->

## declare_table

<!-- description:declare_table -->
Declare what one table's cells ARE, and get GRIM on every mean and percentage cell the declaration covers. The harness enumerates; your job is the premises, which only a reader of the paper can establish. Pass `table` (the key from list_tables), and any of: `variables` (anatomy variable dicts: id, name, family, lower_bound/upper_bound, discreteness, derivation, n_items, provenance_quote); `rows` ([{row, variable_id}] binding a row label, as printed, to a variable); `default_variable_id` (every row not listed in `rows` -- only when every such row really is that variable); `columns` ([{col, n, quote, kind}]: `col` is the column number or label from list_tables, `n` an n the paper states only elsewhere -- Table 1, Methods, Results -- with the sentence that states it in `quote`, `kind` 'mean', 'percent' or 'other' for a column of bare numbers); and `percent_of_units: true` when the table's bare numbers are percentages OF THE PARTICIPANTS (or other whole units), as a caption like 'represented in percentages' or a header like '%' with no count beside it says. Cells printed as `n (%)` or `k/n (%)` need no declaration. A mean is checked only when its row is bound to an integer-valued variable: a single Likert item (`likert_item`), a count, or a summed scale. DECLARE WHAT THE PAPER SAYS, NEVER WHAT UNLOCKS A CHECK: an averaged subscale declared as one item, a model-estimated or multiply-imputed mean declared as a raw mean, or a percentage of something continuous (body fat, HbA1c, oxygen saturation) declared a share turns every failure on it into a false accusation. Test-statistic and p-value columns are skipped automatically. Returns the n bound to each column and where it came from, every failing cell, and the refusals by reason. The harness files the failures as findings after the run, one per table -- do NOT file them yourself; if one rests on a wrong declaration, call again with the correction (the last call for a table wins). Parameters: paper_dir, table, variables, rows, columns, default_variable_id, percent_of_units
<!-- /description:declare_table -->
