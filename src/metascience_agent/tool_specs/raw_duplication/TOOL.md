---
family: raw_duplication
implementation:
- copy_paste_detector.detector
tools:
  detect_raw_duplication:
    evidence: probabilistic
    consumes_table_cells: false
    purpose: Finds copy-paste signatures in participant-level supplement grids.
    assumptions:
    - Rows are assumed to be INDEPENDENT observations; a sheet whose rows are repeated measures of the same participant duplicates by construction.
    - 'Evidence is weighted by the information content of the number itself: 123.456 recurring is evidence, 100 recurring is not.'
    - Values shared BY DESIGN must be excluded by the caller via exclude_columns -- IDs, site codes, coordinates and plot-level covariates repeat legitimately.
    - data_context='pooled_or_meta_analysis' caps everything at indeterminate, because rows compiled from other papers duplicate by construction. That is a refusal, not a finding.
    - Chance collisions are modelled by a Poisson null over same-precision bins (repeated values) and an empirical collision null (matching runs), so a large sheet is not flagged merely for being large. ROW-PAIR evidence has no chance model -- it rests on information discounts and size normalisation, so read it more sceptically than the other two.
    - 'Capped at `highly_suspicious`: no arrangement of a spreadsheet is mathematically impossible.'
---
# `raw_duplication` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## detect_raw_duplication

<!-- description:detect_raw_duplication -->
Detect duplicated RAW DATA inside a supplementary data file (.xlsx/.xlsm/.csv/.tsv/.docx). Give it the FILE PATH — it loads the grid itself; never retype cells. Run it on every participant-level supplement (the ones extract_supplement flags as having many rows). It finds: duplicated participant rows (>=2 identical high-precision values in the same columns, within AND across sheets — recycled rows between "independent" sheets are the strongest signal), repeated vertical runs (fill-down/block copy-paste), and improbably specific values recurring. Matches are weighted by significant-digit information content (a match on 123.456 is evidence; a match on 100 is nothing), with automatic discounts for derived values (fractions, sqrt, log — their precision is an artifact), sorted/ID runs, and values many rows share; repeat counts are gated on a chance model, so expected coincidences are not reported. Severity caps at highly_suspicious: duplication is improbable, never impossible. Pass exclude_columns for columns that are shared BY DESIGN — IDs, codes, coordinates, site/plot-level covariates (weather, species constants), group labels. When in doubt, leave a column IN and judge the caveats. Set data_context="pooled_or_meta_analysis" when the file compiles data from OTHER papers — pooled rows duplicate by construction and the tool then refuses to accuse (indeterminate cap). Parameters: path (str), sheet (str, optional: one worksheet), exclude_columns (list of column names), data_context (str: raw_participant_level | pooled_or_meta_analysis | unknown)
<!-- /description:detect_raw_duplication -->
