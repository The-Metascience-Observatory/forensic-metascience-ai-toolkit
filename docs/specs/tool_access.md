# How an agent reaches its tools (`tool_access`)

Phase 3b of the modular refactor. An agent module in a pipeline may set
`tool_access`:

```yaml
modules:
  - use: tools_agent
    tool_access: mcp_brief      # mcp (default) | mcp_brief | skill
```

The default is never written into a run's recorded config, so every run made
before the key existed keeps its digest. A non-default value changes the
digest, and `runs.build_matches` therefore keeps such runs apart.

## The three modes

| Mode | What the agent is given | Fence | Backends |
|---|---|---|---|
| `mcp` | The forensic MCP server, each tool with its full description (today's behaviour, byte for byte). | MCP server role filter + toolset manifest. | all |
| `mcp_brief` | The same server, each description cut to its first sentence (`ToolSpec.brief`, ≤240 chars), plus `describe_tool(name)`, which returns the full description, parameters with their guards, assumptions and procedure guidance. A system-prompt note tells the agent to read it before first use. | Same as `mcp`. `describe_tool` serves only tools on the stage's surface. | all |
| `skill` | No MCP server. The agent runs `metascience tool run <name> --json '<object>'` (and `tool describe` / `tool list`) through `Bash`. The system prompt lists its tools (summary + parameter names). | Three layers, below. | claude only |

## The `skill` fence

MEASURED 2026-10-13 (Claude Code 2.1.296, Sonnet): under `--permission-mode
dontAsk` the allow pattern `Bash(metascience tool run *)` refused `cat
/etc/hostname` but RAN `metascience tool run grim_check --json '{...}' &&
echo PWNED`. A permission pattern alone is not a fence for an agent that
reads untrusted paper text. So skill mode has three layers:

1. **`skill_guard.py`**, a PreToolUse hook passed with `--settings`. It allows
   exactly three line shapes: `run <name> --json '<one JSON object, single
   quoted>'`, `describe <name>` and `list [--role R] [--json]`. Anything else
   is refused: a second command, `;`, `&&`, `|`, `$(...)` (which double quotes
   would expand), redirection, `--args-file`. It runs by file path with `-I`
   and `|| exit 2`, because Claude Code blocks only on exit code 2 and lets a
   command run when the hook fails any other way. Re-measured with the hook:
   all three bypasses were refused, and the plain call ran.
2. **`dontAsk`** with only the `Bash(metascience tool ...)` patterns approved.
3. **`metascience tool run` itself** serves only what the MCP server would
   under the same environment (`METASCIENCE_MCP_STAGE`, the pipeline's
   `METASCIENCE_MCP_TOOLS`), by importing the server module's own filter.

The launch environment carries the role, the toolset manifest, the paper
directory and the run slug, so the command applies the same surface, verifies
provenance quotes against the same paper, and writes the same receipts
(`receipts.py`, `via: "cli"`).

**The ledger reads skill calls as forensic calls.** A `Bash` call that is
exactly `metascience tool run <name> --json '<object>'` is recorded under the
tool's MCP name, with the parsed arguments and the result minus the verdict
line. So the finding join, reproductions, receipts and audits work unchanged.
`describe`/`list` calls (and `describe_tool`) are `harness`. Any other `Bash`
line is what it always was.

On every non-Claude backend (Grok, Codex, Antigravity, OpenRouter), `skill` raises by
name (`llm_backend.py`): their shells have no equivalent hook here.

## Not here

- **`code` mode** (the agent writes Python against a tool library). It is
  deferred until a trusted out-of-process broker exists, because an
  importable library is not a fence.
- **Which mode should be the default.** That is decided by measurement:
  `metascience eval --pipeline` (see CHANGELOG, Phase 3b measurement).
