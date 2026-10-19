Analyze this scientific paper for statistical inconsistencies and anomalies. Use paper_id "10.1007--s11031-011-9216-y" in your findings JSON.

Conduct a multi-pass sweep.

**Pass 1 — Full text and tables (XML):**
Run `extract_xml` on `/mnt/c/Users/gregs/agent_for_forensic_metascience/eval/ground_truth/papers/10.1007--s11031-011-9216-y/10.1007--s11031-011-9216-y.xml`. This is the authoritative source for BOTH the body text and the tables: merged cells are already expanded and multi-row headers flattened into composite column labels, which no PDF or markdown extraction can reproduce.

For every table it returns, pass the table's `cells` STRAIGHT to `parse_cells_typed`, then run `check_table` once on the typed cells — do not route them through `parse_table` first, and do not check cells one at a time. Read each table's `footnotes` before typing: they define whether a cell is `n (%)` or `mean (SD)`. For NHST verification, run `statcheck` with the `text` argument set to the returned body text.

Respect the per-table flags — each one exists because ignoring it produces a false accusation:
- `spans` lists every merged cell. A merged value is placed ONCE, at its first covered position, and the continuations are empty ON PURPOSE. Do not fill them in: a value spanning four columns is one measurement, and copying it across would create identical (mean, SD) pairs that trip `detect_duplication` — a finding invented by the extraction, against a paper that did nothing wrong.
- `alignment_uncertain: true` means the source rows were ragged and a column label may be shifted by one. A shifted label puts a mean under the wrong group and hands GRIM/GRIMMER a triple the paper never reported. Reconcile against the PDF, or record the table as unchecked.
- `image_only: true` means the table is a picture and has no cells. Get it from the PDF; if there is no PDF, record it in `unchecked` — never report it as checked.
- XML has no pages. Write `location` as `"Table 2, Age row"` or `"Results, para 2"`, never a page number you did not see.

**Pass 2 — PDF cross-check and figures:**
Run `extract_pdf` on `/mnt/c/Users/gregs/agent_for_forensic_metascience/eval/ground_truth/papers/10.1007--s11031-011-9216-y/10.1007--s11031-011-9216-y.pdf` for three specific purposes ONLY: (a) reconcile any table flagged `alignment_uncertain`, passing the PDF grid as `parse_table`'s `cross_check`; (b) recover any table the XML reports as `image_only`; (c) read figure captions and any statistic that appears only in a figure.

Do NOT re-sweep statistics already checked in Pass 1. The same statistic checked twice produces two findings and inflates the apparent problem count, which is itself a distortion of the paper.

Record all checks from every pass as findings in a single JSON output.