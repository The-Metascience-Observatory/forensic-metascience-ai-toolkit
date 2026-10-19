Analyze this scientific paper for statistical inconsistencies and anomalies. Use paper_id "paper" in your findings JSON.

Conduct a multi-pass sweep.

**Pass 1 — Clean text:**
Use the Read tool to read `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/airforce/paper/markdown/body.md` (a high-quality extraction of the paper body). Identify all reported statistics and run the appropriate forensic tools on each. For NHST verification, prefer `statcheck` with the `text` argument set to the body content.

**Pass 2 — Tables and figures:**
Run `extract_pdf` on `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/airforce/paper/air_force.pdf` to surface tables and content the markdown extraction may have missed (Table 1 baseline characteristics, supplementary statistics, figure captions). Run additional checks on any statistics not seen in pass 1.

Record all checks from every pass as findings in a single JSON output.