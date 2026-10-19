"""`metascience tool`: one generic command for every registered tool.

THE command-line route to a tool. The hand-written per-tool verbs
(`metascience grim`, `metascience check-ci`, ...) called `tools/*.py`
directly, so NONE of `ToolSpec.call`'s gates ran on them -- `grim` defaulted
`decimals=2` where the MCP surface refuses a missing precision. They were
retired in 1.95.0. This command is generated from the registry and goes
through `ToolSpec.call`, exactly the path the model's MCP calls take:

  metascience tool list [--role ROLE] [--json]
  metascience tool describe NAME
  metascience tool run NAME --json '{"mean": 3.53, "n": 30, ...}'

`run` prints the verdict first (`IMPOSSIBLE: ...`, which is what a reproduction
check reads), then the result exactly as the MCP server would have returned
it. It exits 0 whatever the verdict -- a refusal is a result -- and 2 for a
usage error: an unknown tool, unreadable JSON, or a tool outside the surface
this process may serve.

THE SAME FENCE AS THE SERVER. When `METASCIENCE_MCP_STAGE` (and a pipeline's
`METASCIENCE_MCP_TOOLS` manifest) is set, `run` serves only what the MCP
server would serve under that environment, by asking the server module itself.
That is what lets a sandboxed agent use this command in place of MCP
(`tool_access: skill`) without widening what it may call. Calls are receipted
(`receipts.py`) like MCP calls.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer

tool_app = typer.Typer(
    help="Run any registered forensic tool through its validated gates "
         "(list | describe | run).",
    no_args_is_help=True)

USAGE_ERROR = 2


def _type_name(t) -> str:
    return getattr(t, "__name__", str(t))


def _served() -> dict:
    """{name: SdkMcpTool} this process may serve, decided by the MCP server's
    own filter -- or exit 2 naming why there is no surface."""
    import importlib
    try:
        mcp_server = importlib.import_module("forensic_metascience_ai_toolkit.mcp_server")
    except Exception as exc:  # ToolManifestError at import: fail closed
        _refuse(f"no tool surface: {type(exc).__name__}: {exc}", "tool_manifest_error")
    return dict(mcp_server._TOOLS_BY_NAME)


def _operator_may_run(name: str) -> bool:
    """The two CLI-only tools (`registry.CLI_ONLY`) run here for a PERSON.

    They are off the MCP surface so that no model calls them; they are not
    dangerous. With no role and no manifest in the environment this process
    is an operator at a terminal, not a fenced agent, so they are served --
    this command is their only command-line route since the per-tool verbs
    were retired. Under any fence they stay refused.
    """
    from .registry import CLI_ONLY
    fenced = any(os.environ.get(k, "").strip()
                 for k in ("METASCIENCE_MCP_STAGE", "METASCIENCE_MCP_TOOLS"))
    return name in CLI_ONLY and not fenced


def _refuse(message: str, kind: str):
    typer.echo(json.dumps({"error": message, "refusal": kind,
                           "severity": "indeterminate"}))
    raise typer.Exit(USAGE_ERROR)


@tool_app.command("list")
def list_cmd(
    role: Optional[str] = typer.Option(
        None, "--role", help="Only tools this role may call: tool_agent, "
                             "science_agent or adjudicator."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
):
    """Every registered tool, with its family, evidence class and roles."""
    from . import registry as R
    from .tool_specs import family_of
    fam = family_of()
    rows = []
    for spec in R.SPECS:
        if role and role not in spec.stages:
            continue
        rows.append({"name": spec.name, "family": fam.get(spec.name, ""),
                     "evidence": spec.evidence, "roles": sorted(spec.stages),
                     "purpose": spec.purpose})
    if as_json:
        typer.echo(json.dumps(rows, indent=1))
        return
    for r in rows:
        roles = ",".join(r["roles"]) or "cli-only"
        typer.echo(f"{r['name']:<30} {r['family']:<26} {r['evidence']:<14} {roles}")


def describe_text(name: str) -> str | None:
    """A tool's full description, parameters, assumptions and procedure
    guidance as one text -- what `metascience tool describe` prints and what
    the MCP server's `describe_tool` returns in brief mode. None if unknown."""
    from . import registry as R
    from .tool_specs import family_of, guidance_for
    spec = R.BY_NAME.get(name)
    if spec is None:
        return None
    out = [f"# {spec.name}  ({family_of().get(name, '')}; {spec.evidence})", "",
           spec.description, "", "## Parameters"]
    for p in spec.params:
        if p.withheld:
            continue
        flags = [f for f, on in (("required", p.required), ("guard", p.guard),
                                 ("exact", p.exact), ("precision", p.precision)) if on]
        out.append(f"- {p.name} ({_type_name(p.type)}"
                   + (f"; {', '.join(flags)}" if flags else "") + ")"
                   + (f": {p.help}" if p.help else ""))
    if spec.assumptions:
        out += ["", "## Assumptions"] + [f"- {a}" for a in spec.assumptions]
    notes = guidance_for(name)
    if notes:
        out += ["", "## Guidance (from the tools agent's procedure)"] + notes
    out += ["", f"Run: metascience tool run {name} --json '{{...}}'"]
    return "\n".join(out)


@tool_app.command("describe")
def describe_cmd(name: str = typer.Argument(..., help="Tool name, e.g. grim_check.")):
    """A tool's full description, parameters, integrity card and guidance."""
    text = describe_text(name)
    if text is None:
        _refuse(f"unknown tool: {name}", "unknown_tool")
    typer.echo(text)


@tool_app.command("run")
def run_cmd(
    name: str = typer.Argument(..., help="Tool name, e.g. grim_check."),
    json_args: Optional[str] = typer.Option(
        None, "--json", help="The call's arguments as one JSON object."),
    args_file: Optional[Path] = typer.Option(
        None, "--args-file", help="Read the arguments from a JSON file instead."),
    paper_dir: Optional[Path] = typer.Option(
        None, "--paper-dir", help="The paper directory, for checks that verify a "
                                  "provenance quote against the paper."),
):
    """Run one tool through `ToolSpec.call` -- the gates the MCP surface applies."""
    from . import registry as R
    if (json_args is None) == (args_file is None):
        _refuse("pass exactly one of --json or --args-file", "usage")
    try:
        raw = json_args if json_args is not None else args_file.read_text(encoding="utf-8")
        args = json.loads(raw)
    except (OSError, ValueError) as exc:
        _refuse(f"arguments are not readable JSON: {exc}", "bad_arguments")
    if not isinstance(args, dict):
        _refuse("arguments must be one JSON object", "bad_arguments")
    if R.BY_NAME.get(name) is None:
        _refuse(f"unknown tool: {name}", "unknown_tool")
    served = _served()
    if name not in served and not _operator_may_run(name):
        stage = os.environ.get("METASCIENCE_MCP_STAGE", "").strip()
        _refuse(f"tool '{name}' is not on the "
                + (f"{stage} role's surface" if stage else "served tool surface")
                + "; it exists but may not be called here", "off_role_tool")
    # A misspelled argument is refused, never dropped: dropping it runs the
    # tool on its default for that parameter, which is a guess.
    known = {p.name for p in R.BY_NAME[name].params}
    unknown = sorted(set(args) - known)
    if unknown:
        _refuse(f"{name} has no parameter(s) {unknown}; see "
                f"`metascience tool describe {name}`", "bad_arguments")
    if paper_dir is not None:
        from .run_script import PAPER_DIR_ENV
        os.environ[PAPER_DIR_ENV] = str(paper_dir)
    from .tools_mcp import as_mcp_content
    # A library's own progress lines (statcheck prints several) go to stderr:
    # stdout opens with the verdict line, which is what a replay reads.
    import contextlib
    with contextlib.redirect_stdout(sys.stderr):
        try:
            result = R.BY_NAME[name].call(args)
        except Exception as exc:  # noqa: BLE001 -- the MCP server's answer, not a traceback
            result = {"error": f"{type(exc).__name__}: {exc}", "severity": "indeterminate",
                      "tool": name, "arguments": args,
                      "note": "The tool raised instead of returning a result. Check the "
                              "inputs (a missing required argument, n too small, zero "
                              "SD) and retry."}
    content = as_mcp_content(result).get("content") or []
    text = "".join(c.get("text", "") for c in content if isinstance(c, dict))
    from . import receipts
    receipts.record(name, args, text, via="cli")
    sev = result.get("severity") if isinstance(result, dict) else None
    why = ""
    if isinstance(result, dict):
        why = str(result.get("explanation") or result.get("error") or "")
    typer.echo(f"{str(sev or 'indeterminate').upper()}: {why}".rstrip())
    typer.echo(text)
    sys.stdout.flush()
