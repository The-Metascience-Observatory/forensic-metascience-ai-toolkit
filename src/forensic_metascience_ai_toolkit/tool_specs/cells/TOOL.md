---
family: cells
implementation:
- forensic_metascience_ai_toolkit.tools.cellformat
- forensic_metascience_ai_toolkit.tools.celltypes
- forensic_metascience_ai_toolkit.tools.tableparse
tools:
  parse_cells_typed:
    evidence: descriptive
    consumes_table_cells: false
    purpose: Classifies table cells by kind before any check runs; renders no verdict.
    assumptions:
    - Cells returned `ambiguous` carry candidate readings and must not be fed to any forensic tool.
  parse_cells_as_declared:
    evidence: descriptive
    consumes_table_cells: false
    purpose: Parses cells under a model-declared format from a closed vocabulary; renders no verdict.
    assumptions:
    - The format NAME comes from the model; every character of the matching is code in tools/cellformat.py. No pattern is generated at run time -- a generated regex is a generated statistic, and a wrong capture becomes a plausible mean that no later layer can recognise as invented.
    - 'The declaration is a hypothesis about the table and is tested before it is applied: cells are checked against the same coherence guards the row/column-label path uses, and a declaration fitting under `min_fit` of the cells is refused wholesale.'
    - Several formats genuinely fit the same numbers -- `142 (71.0)` is a valid mean (SD) and a valid n (%). The numbers cannot choose; the declaration must come from reading the table's header, caption and footnotes, and `n_overrides_automatic` counts the cells where it contradicted them.
  parse_table:
    evidence: probabilistic
    consumes_table_cells: false
    purpose: Parses a summary table into normalised cells, and can reconcile two renderings of it.
    assumptions:
    - Parsing alone renders no verdict; a severity appears only when `cross_check` supplies a second rendering.
    - 'A cross-check disagreement is evidence about OUR EXTRACTION, not about the paper: the likeliest cause by far is that one of the two parsers mis-read the table, so confirm against the source before citing it.'
    - Both renderings must be of the SAME table; comparing different tables produces a meaningless disagreement.
    - Drops cells it cannot reduce to a scalar, such as estimate-plus-CI; use the XML cells route for those.
---
# `cells` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## parse_cells_typed

<!-- description:parse_cells_typed -->
Classify table cells BEFORE running any other check. The untyped parser read every 'X (Y)' cell as mean=X, sd=Y, so a clinical '142 (71.0)' -- a count and a PERCENTAGE -- was handed downstream as sd=71.0, manufacturing impossibilities out of an ordinary table. Returns a `kind` per cell (mean_sd | n_percent | median_iqr | median_range | estimate_ci | mean_se | numeric | count | ambiguous | non_numeric) plus a `coverage` figure -- the honest answer to how much of the table was actually understood. Cells returned as `ambiguous` carry candidate readings and MUST NOT be fed to any forensic tool: run nothing on a value whose meaning is unknown. Parameters: cells (list of {raw, row_label, col_label})
<!-- /description:parse_cells_typed -->

## parse_cells_as_declared

<!-- description:parse_cells_as_declared -->
Re-parse cells parse_cells_typed could not read, under a format YOU declare from a closed vocabulary. Use this when parse_cells_typed reports a block of cells sharing one unread shape -- its `unparsed.clusters` names the shape, gives examples, and lists the formats that would fit. A format name is <pairing>:<delimiter>. Pairings (what the numbers MEAN): mean_sd, mean_se, n_percent, median_iqr, median_range, estimate_ci. Delimiters (how the second value is WRAPPED): paren, bracket, brace, angle, plusminus, comma, semicolon, slash. So 'mean_sd:brace' reads `5.38 {1.17}`, which nothing else in this toolkit can. CHOOSE THE PAIRING BY READING THE TABLE -- its header, caption and footnotes -- not by which numbers happen to fit: `142 (71.0)` is a valid mean (SD) and a valid n (%), and only the table says which. Your declaration is then TESTED, not obeyed: each cell is checked against the same coherence guards the label path uses (an n (%) needs an integer count and a percentage in [0, 100]; an estimate must lie inside its own CI), and the declaration is REFUSED if it fits under 80% of the cells -- `misfits` then shows you what did not fit. Parameters: cells (list of {raw, row_label, col_label}), declared (str format name), min_fit (float, default 0.8)
<!-- /description:parse_cells_as_declared -->

## parse_table

<!-- description:parse_table -->
Parse a summary-statistics table into normalized cells so you don't have to hand-transcribe numbers. Accepts a markdown pipe table (from body.md), a pdfplumber `data` grid (the 'data' field from extract_pdf tables), or raw text. Returns cells [{row_label, col_label, value, sd, extras, raw}] plus parse warnings. Handles cell formats '5.38 (1.17) a', 'M=5.38, SD=1.17', '5.38±1.17', bare numbers, and merged whole-row blobs. Feed the returned cells to detect_duplication, or pass cross_check to reconcile two extractions -- NOTHING ELSE. They are UNTYPED: every "X (Y)" reads as value/sd, so a count and a percentage arrive as a mean and an SD. Never hand them to grim/grimmer/sprite/debit; use parse_cells_typed or check_table for anything per-cell. Optionally pass cross_check (the SAME table from the other source) to reconcile the two extractions. Parameters: source (str markdown/text OR list-of-rows grid), source_format ('auto'|'markdown'|'grid'|'text'), source_label (str), header_row (int, default 0), label_col (int, default 0), cross_check (optional), cross_check_format (str)
<!-- /description:parse_table -->
