Review the paper `paper`. Use `paper_id`: "paper" in the findings JSON.

The paper's PDF is `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/apple_cider/paper/Apple cider vinegar.pdf`; read it with `extract_pdf` -- your primary source.
A pre-extracted body is `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/apple_cider/paper/markdown/body.md` (use `Read`).

Pass 1 -- read the ENTIRE main text linearly, building the claims register (primary outcome, doses, durations, group sizes, directions of effect) and every participant count.
Pass 2 -- run the flow arithmetic through `check_flow_arithmetic`, verify drifting denominators with the integer cross-checks, verify named entities per the web-facts discipline, and file findings.