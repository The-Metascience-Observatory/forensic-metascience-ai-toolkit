---
family: readers
implementation:
- metascience_observatory_image_analysis.extraction.figures
- metascience_observatory_image_analysis.extraction.html
- metascience_observatory_image_analysis.extraction.jats
- metascience_observatory_image_analysis.extraction.pdf
- metascience_observatory_image_analysis.extraction.supplements_read
tools:
  extract_figures:
    evidence: descriptive
    consumes_table_cells: false
    purpose: Locates, crops and captions the figures in a PDF; renders no verdict.
    assumptions:
    - Values later read off the cropped artwork carry measured provenance and are barred from exact-arithmetic checks.
  extract_pdf:
    evidence: descriptive
    consumes_table_cells: false
    purpose: Extracts text and resolvable tables from a PDF; renders no verdict.
    assumptions:
    - An empty `tables` list does not mean the paper has no tables -- unresolvable grids remain in `text`.
  extract_xml:
    evidence: descriptive
    consumes_table_cells: false
    purpose: Indexes body text and tables from publisher XML; renders no verdict.
    assumptions:
    - Tables flagged alignment_uncertain or image_only must be reconciled against the PDF before use.
  get_table:
    evidence: descriptive
    consumes_table_cells: false
    purpose: Fetches one XML table in full with its label, caption and footnotes; renders no verdict.
    assumptions:
    - Footnotes define cell semantics -- 'n (%)' versus 'mean (SD)' -- so read them before typing cells.
  extract_html:
    evidence: descriptive
    consumes_table_cells: false
    purpose: Extracts full text from a publisher HTML article; renders no verdict.
    assumptions:
    - A LANDING PAGE IS NOT THE ARTICLE. Publishers serve abstract-only stubs at article URLs, and treating one as the full text makes every 'not reported' finding an artefact of what we failed to fetch; the extractor defends against this and says when it has a stub.
  extract_supplement:
    evidence: descriptive
    consumes_table_cells: false
    purpose: Reads supplementary .docx/.xlsx/.csv tables into checkable cells; renders no verdict.
    assumptions:
    - '''Present but unreadable'' is itself the result; do not report such a supplement as absent.'
  get_supplement_table:
    evidence: descriptive
    consumes_table_cells: false
    purpose: Fetches ONE sheet of a supplement, whole or by row window; renders no verdict.
    assumptions:
    - 'The counterpart to extract_supplement''s index: an oversized supplement returns an index, and treating that index as the supplement''s contents is the error this pair exists to prevent.'
    - A windowed result reports its own window; rows outside it were not returned and are evidence of nothing.
    - The header row comes back with every window -- a grid of numbers without its column names is not checkable.
    - Row numbering is shared with `cells[].row`, so the grid view and the cell view window on one coordinate.
---
# `readers` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## extract_figures

<!-- description:extract_figures -->
Locate every figure in a PDF, crop it, and pair it with its caption. Runs LOCALLY via PyMuPDF -- no network, no API, no token cost. Use it when a paper's outcome appears only in a chart, which is common: the group means and SD/SEM needed to compute an effect size often appear nowhere in the text or tables. Uses CAPTION-ANCHORED cropping rather than embedded-image extraction, because most journal charts are VECTOR linework that `get_images()` does not see at all. Returns per figure: label, page, caption, crop path, `crop_confidence`, and `error_bar_meaning` read out of the caption (SD | SEM | CI | IQR | range, or null). A null there matters -- SD, SEM and a 95% CI half-width differ by sqrt(n) and ~1.96*sqrt(n), so a figure whose error bars are unlabelled cannot yield an effect size at all, and the tool says so instead of assuming SEM. ALWAYS CHECK `crop_confidence` BEFORE READING AN IMAGE. `high` = the artwork was located and cropped to. `partial` = the figure continues past the crop, walled off by a paragraph or another caption, so anything you read is from an INCOMPLETE view of it. `low` = a crop was made but holds too little ink to be a chart, so it is probably a header sliver -- read the page image named in the figure's `warnings` instead. `none` = no artwork was found near the caption and `image_path` IS THE WHOLE PAGE, not the figure; this happens on papers that collect their figure legends onto a separate page, and on captions whose artwork sits on the adjacent page (a known limitation). Reporting a value read from a `low` or `none` image without saying so is a fabricated measurement. Anything you subsequently READ OFF THE MARKS is tier-2 `figure_pixels` provenance and is barred from GRIM, GRIMMER, SPRITE and DEBIT. Caption TEXT is printed and carries normal provenance. Parameters: pdf_path, out_dir (optional), dpi (default 150), render_pages
<!-- /description:extract_figures -->

## extract_pdf

<!-- description:extract_pdf -->
Extract text and tables from a PDF file for forensic analysis. Returns structured content including page text and table data. Output is capped at max_chars (default 50000); if the result says TRUNCATED, call again with first_page/last_page (1-based, inclusive) to fetch specific pages. A PDF table is only returned when it can actually be resolved into a grid. AN EMPTY `tables` DOES NOT MEAN THE PAPER HAS NO TABLES: a table whose rules pdfplumber cannot find is still printed in `text`, so search there for "Table 1" and read the numbers from the page. `tables_rejected` counts candidates dropped as segmented prose or reference-list text -- an inference from text alignment alone accepts ANY page, and on one prose paper it produced twelve "tables", the first being the title page. Prefer extract_xml + get_table wherever an .xml exists.
<!-- /description:extract_pdf -->

## extract_xml

<!-- description:extract_xml -->
Extract body text and TABLES from a publisher XML full text (JATS, PMC or Elsevier). PREFER THIS OVER extract_pdf whenever an .xml exists: tables come back as a dense rectangular cell grid with colspan/rowspan already expanded and multi-row headers flattened into composite column labels, which neither a PDF extraction nor markdown can represent. Measured on a real clinical Table 1, the PDF route recovers 7 usable cells per table and the XML route 86. THIS RETURNS A TABLE INDEX, NOT THE GRIDS -- table number, label, caption, section, shape and footnote count per table. Call get_table(xml_path, table_num) for the cells of each table you actually want. That extra hop exists for a reason: returning every grid at once produced a 184 kB result the harness could not deliver, so it spilled to a file and about 60% of it went unread. One table at a time always arrives. get_table returns `cells` -- ready-made {raw, row_label, col_label, row} records: pass those STRAIGHT to parse_cells_typed and check_table, UNCHANGED AND INCLUDING `row`. `row` is the cell coordinate the value register joins each verdict back to; two columns of one row can print the same number, so the text alone cannot identify a cell. Dropping it does not degrade the join, it ends it: every verdict then carries `row: None`, matches nothing, and the paper reports zero checks attached however many ran. Do NOT rebuild these records by hand. Do NOT route them through parse_table first; it drops every cell it cannot reduce to a scalar, which silently discards the estimate(CI) cells that are the highest-yield check on clinical papers. Use parse_table only to reconcile two extractions via cross_check. A merged cell appears ONCE, at its anchor position, with empty continuations: that is deliberate -- one measurement is one value, and repeating it would fabricate a duplication finding. XML HAS NO PAGE NUMBERS: cite the table label and section, never a page. A table with `alignment_uncertain: true` had ragged source rows and its column labels may be shifted -- reconcile against the PDF before reporting from it. A table with `image_only: true` is a picture and has NO cells: get it from the PDF, and if there is no PDF record it in `unchecked`. Read each table's `footnotes` before typing its cells -- they define whether a cell is "n (%)" or "mean (SD)". Text is capped at max_chars; when TRUNCATED call again with first_section/last_section (1-based, inclusive). Parameters: xml_path (str), max_chars (int, default 50000), first_section, last_section
<!-- /description:extract_xml -->

## get_table

<!-- description:get_table -->
Fetch ONE table from a publisher XML, in full, with the identity the checking tools need. Call it after extract_xml, which returns only an index. Returns `cells` ({raw, row_label, col_label}) for parse_cells_typed and check_table, the `data` grid a human reads, `headers`, and -- the part that was previously lost at this boundary -- `label`, `caption` and `footnotes`. READ THE FOOTNOTES BEFORE TYPING THE CELLS. They are what decide whether "142 (71.0)" is "n (%)" or "mean (SD)", and getting that wrong inverts every granularity check downstream. The label is what a finding should cite: say "Table 2", never a page number, because XML has none. A table with `image_only: true` is a picture and has no cells -- get it from the PDF, and if there is no PDF record it in `unchecked`. One with `alignment_uncertain: true` had ragged source rows and its column labels may be shifted; reconcile against the PDF before reporting from it. If the number does not exist the result lists the ones that do. THE GRID IS COMPLETE ON THE FIRST CALL. `data` carries every number the paper printed -- verified over all 475 tables in the corpus -- so you never have to page anything to be sure you have seen a value. `data_is_complete` confirms it. Only `cells` (the check_table format, roughly four times the size for the same content because both labels repeat on every cell) is windowed. `how_to_get_more` therefore says which of two DIFFERENT things is happening: if it mentions paging `cells`, nothing is missing and you only need to continue when you are feeding check_table; if it begins THE GRID IS TRUNCATED, a printed number really is absent and you must continue. Parameters: xml_path (str), table_num (int), first_row (int, optional -- 1-based grid row to resume from), last_row (int, optional)
<!-- /description:get_table -->

## extract_html

<!-- description:extract_html -->
Extract body text and TABLES from FETCHED PUBLISHER HTML full text -- the fallback when a paper has no .xml. Same cells/spans/alignment_uncertain/image_only contract as extract_xml; treat its output identically (pass `cells` STRAIGHT to parse_cells_typed and check_table, never through parse_table first). UNLIKE extract_xml, a fetched HTML file can be a landing page, cookie gate, or JS-rendered app shell rather than the article -- it will look plausible (a real title, a real abstract, even a populated nav/metrics table). This tool runs a landing-page/decoy check BEFORE any parsing and returns a structured `error` if the page fails it -- that refusal IS the result: do NOT attempt to recover text from the raw file yourself. Record it and fall back to extract_pdf or Read on body.md for this paper instead. Do not treat a returned error as "zero tables found" -- that reads as a clean paper when the paper was never actually read. A merged cell appears ONCE, at its anchor position, with empty continuations -- same reasoning as extract_xml: repeating it fabricates a duplication finding. A table with `alignment_uncertain: true` had ragged source rows; reconcile against the PDF. A table with `image_only: true` had no populated rows (most likely never rendered by the page's own JavaScript) and has NO cells: get it from the PDF, or record it in `unchecked`. HTML has no standard footnote convention, unlike JATS -- `footnotes` may be empty even when a table needs one to disambiguate `n (%)` from `mean (SD)`; reconcile against the PDF if a cell's meaning is unclear. HTML HAS NO PAGE NUMBERS: cite the table label and section, never a page. Text is capped at max_chars; when TRUNCATED call again with first_section/last_section (1-based, inclusive) -- HTML is currently always one section, so this mainly reserves interface parity with extract_xml. Tables are never truncated. Parameters: html_path (str), max_chars (int, default 50000), first_section, last_section
<!-- /description:extract_html -->

## extract_supplement

<!-- description:extract_supplement -->
Read a SUPPLEMENTARY file in ANY format -- .pdf, .docx, .xlsx, .csv, .tsv, .html, .epub, .xml, .txt/.md, and scanned images (.jpg/.png/.tif) -- and return its tables in the same shape as extract_xml: a `data` grid plus ready-made `cells` for parse_cells_typed. USE THIS FOR A SUPPLEMENTARY PDF TOO; extract_pdf returns grids with no `cells`, so its output cannot be handed to check_table. Sweep supplements exactly as you would a main table -- they are where a paper's unchecked numbers hide. A spreadsheet of PARTICIPANT-LEVEL data (flagged in the table warnings when a sheet has many rows) is worth MORE than a summary table: it supports checks the paper's own tables cannot, and it is what detect_duplication is for. Merged cells follow the same rule as elsewhere -- the value sits at its anchor and the continuations are empty; do not fill them in. READ THE REFUSAL BEFORE YOU RECORD ONE -- these are different facts and the result tells you which you have. `ocr_unavailable: true` means no OCR engine is installed on THIS machine and says NOTHING about the file: never write "the supplement has no tables" on the strength of it. `no_text_layer: true` means the PDF pages are pictures. `unreadable_format` means the format itself cannot be opened (legacy .doc, .xls, .zip, .tex). An empty `tables` list with none of those means the file WAS read and held no table. Every one of these goes in `unchecked` -- do NOT report the supplement as absent. "Present but unreadable" and "not provided" are different facts about a paper. A table transcribed from an IMAGE carries provenance "ocr_table" on every cell; pass it through to check_table, which will refuse the exact-arithmetic family on those cells. That refusal is correct: the paper printed a last digit, but we do not know we read it correctly, and this family's verdict turns entirely on that digit. Human confirmation against the image is the only route to a verdict there. A PDF table with `grid_strategy: "text_alignment"` had NO ruled lines: its columns were inferred from where words line up, so a value may sit under the wrong heading and a `mean (SD)` may have been split across a boundary nobody drew. Treat those cells as provisional. Parameters: path (str)
<!-- /description:extract_supplement -->

## get_supplement_table

<!-- description:get_supplement_table -->
Fetch ONE sheet of a supplement, in full or by row window. Call it whenever extract_supplement comes back with `oversized: true` -- that result is an INDEX (every sheet, its shape, its first rows), not the supplement, and treating it as the contents is the mistake this pair exists to prevent. Same relationship as extract_xml -> get_table. MEASURED: every spreadsheet supplement in the working corpus serialises to between 0.5M and 1.9M characters, far over any single-result limit. Before this existed the honest answer was to refuse them, and on 10.1038/s41537-025-00576-3 that meant the latent-class model-selection statistics -- the BIC and fit indices justifying the four-class solution the whole paper rests on -- were never checked. `table` takes the sheet NUMBER the index prints or the sheet NAME; you have both after reading the index. `first_row`/`last_row` are 1-based and inclusive over the sheet's data rows (the header is always returned) and a windowed result says so in `window_note` -- rows outside the window were not returned and are evidence of nothing. Returns `cells` for parse_cells_typed and check_table, windowed to match. Parameters: path (str), table (int or str), first_row (int, optional), last_row (int, optional)
<!-- /description:get_supplement_table -->
