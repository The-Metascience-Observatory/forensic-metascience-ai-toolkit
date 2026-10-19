# Antigravity route — how tools and the final answer work on this backend

This addendum is Antigravity-only.

## Forensic tools

The forensic tools are reached through `call_mcp_tool` with
`ServerName` exactly `forensic_metascience`, `ToolName` the tool's short
name (`extract_xml`, `check_table`, `grim_check`, …) and `Arguments` its
parameters. Read the tool's schema file before the first call to a tool
rather than guessing parameter names. A large result is saved to a file
and the call tells you where: open it with `view_file` and read all of it
before relying on it.

That is the validated surface. A shell, the web (unless your instructions
grant it), an editor or a subagent is still forbidden, and exploring the
filesystem is not part of the procedure.

## Your final answer

Your answer is recorded ONLY through the `finish` tool, with the complete
document as its arguments, matching the required schema. Text you write
outside `finish` is not read. Ending the turn without calling `finish` is a
dropped report, not an empty one, and is retried.
