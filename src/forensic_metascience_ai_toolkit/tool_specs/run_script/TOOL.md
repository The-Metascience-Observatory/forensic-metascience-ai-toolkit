---
family: run_script
implementation:
- forensic_metascience_ai_toolkit.run_script
tools:
  run_python_script:
    evidence: descriptive
    consumes_table_cells: false
    purpose: Sandboxed, network-off code execution for the science agent; renders no verdict.
    assumptions:
    - The captured output is evidence of what the script computed, never of what the paper says -- transcription into the script is the residual risk, so findings still carry verbatim source quotes.
    - A code result can motivate a finding but never establish `impossible`; only a validated registry tool can.
---
# `run_script` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## run_python_script

<!-- description:run_python_script -->
Run a short Python script in a NETWORK-OFF sandbox and get its captured stdout/stderr back. This is your ONLY route to running code, and it exists for checks no registry tool covers: bespoke arithmetic over odd data presentations, unit conversions, reshaping a table before a real check. Every load-bearing number you report must come from the CAPTURED OUTPUT returned here or from a registry tool -- never from your own arithmetic. The script is persisted to analysis_code/ BEFORE it runs, and your finding cites that file as its reproduction. Rules: if a registry tool covers the check, you MUST use the tool instead (a code result can never establish `impossible` -- only a validated registry tool can); no network (it is disabled at the OS level, do not try); print() what you need, the result is the captured output. Parameters: code (the script), label (short slug for the filename), timeout_seconds (default 60, max 300)
<!-- /description:run_python_script -->
