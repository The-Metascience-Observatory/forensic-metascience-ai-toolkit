Analyze this scientific paper for statistical inconsistencies and anomalies. Use paper_id "paper" in your findings JSON.

Conduct a multi-pass sweep.

**Pass 1 — Clean text:**
Use the Read tool to read `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/apple_cider/paper/markdown/body.md` (a high-quality extraction of the paper body). Identify all reported statistics and run the appropriate forensic tools on each. For NHST verification, prefer `statcheck` with the `text` argument set to the body content.

**Pass 2 — Tables and figures:**
Run `extract_pdf` on `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/apple_cider/paper/Apple cider vinegar.pdf` to surface tables and content the markdown extraction may have missed (Table 1 baseline characteristics, supplementary statistics, figure captions). Run additional checks on any statistics not seen in pass 1.

Record all checks from every pass as findings in a single JSON output.

---

## RETRY -- your previous report was not usable

It parsed, so nothing rejected it -- but it recorded 0 finding(s) and NO tools in `coverage`, after 30 forensic tool call(s) on your ledger. That is a highlights document, not a docket.

Every check you ran is a row, including the ones that PASSED: a clean check is the evidence that the territory was examined, and without it the report cannot distinguish 'we looked and it was fine' from 'we never looked'. Fill in `coverage.tools_run` with every tool you called, `anatomy` with the studies, variables and tests you identified, and `statistics_register` with the values you read. Prefer more rows with shorter `description` fields over a few long ones -- the report is assembled from structured fields, so prose length buys nothing and crowds out coverage.
