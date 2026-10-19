---
name: tools_agent
kind: agent
producer: tool_expert          # STORED value, hashed into finding_id -- never rename
label: tool_agent              # history / run_meta stage label
order: 10
options: [figures]
backend_configurable: true
display: Tools agent
prompt: prompt.md
---
# Tools agent

The numeric analyst (formerly the "tool expert"). It reads the paper's text,
tables and supplements and checks reported statistics with the validated
forensic tools over MCP. It has no internet access and runs no code.

- **Tools:** the pipeline's `tools:` list (default: the whole tool-agent role
  surface). The MCP server, `check_table` and the harness prepass all enforce
  the list (docs/specs/pipeline_config.md).
- **Output:** findings-v2 rows with producer `tool_expert`, plus the coverage,
  anatomy and statistics register that the document carries.
- **Failure:** an empty or truncated report is retried once. A stage that made
  no forensic calls on either attempt is a refusal (`no_forensic_calls`), never
  a clean paper.
