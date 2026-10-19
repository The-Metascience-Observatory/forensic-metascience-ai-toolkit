"""Accept the command shape the model actually writes.

WHO USES THIS NOW: the image analysis package's CLI (through its alias module).
The toolkit's own per-tool verbs it was written for were retired in 1.95.0 --
`metascience tool run NAME --json '{...}'` takes the MCP parameter names
directly, so it needs no rewriting. `_ALIASES` below names those retired verbs.

THE MEASUREMENT THAT MOTIVATES THIS
-----------------------------------
Every finding is supposed to carry a command that reproduces it, and the run
executes each one. Across every archived review in this repo, 342 distinct
commands were written and **205 of the 360 recorded failures are argument-shape
mismatches** -- not wrong numbers, not wrong checks, wrong *spelling* of the
invocation.

The mismatch is not random. It is completely systematic: the model writes the
MCP tool's PARAMETER NAMES as long flags, with the values inline.

    model writes   metascience check-ci --estimate 0.217 --ci-low 0.081 --ci-high 0.582
    CLI wants      metascience check-ci 0.217 0.081 0.582

    model writes   metascience summation --values 1,2,3 --expected-sum 6
    CLI wants      metascience summation --values 1,2,3 --expected 6

    model writes   metascience summation-batch --rows '[{"values":[1,2]}]'
    CLI wants      metascience summation-batch rows.json

WHY THE MODEL IS RIGHT AND THE CLI IS WRONG
-------------------------------------------
The `reproduction` field exists so a READER can re-run a finding. A command
naming `rows.json` reproduces nothing for someone who does not have
`rows.json` -- it is syntactically valid and practically useless. Faced with a
choice between a valid command and a runnable one, the model chose runnable.
That is the correct instinct, and the CLI could not express it.

So this does not teach the model the CLI's spelling. It teaches the CLI to
accept the model's, which is also the more self-describing form for a command
a human is meant to read in a report.

HOW
---
A rewrite in front of Click's parser, driven by each command's OWN signature
rather than by a hand-maintained table:

  1. `--positional-name VALUE` -> the positional, in declared order. Purely
     mechanical: Click knows its own argument names, so this stays correct as
     commands change. This alone covers the largest group.
  2. `--param-name VALUE` where an option exists under a different flag string
     but the same Python name -> renamed to the canonical flag.
  3. A SMALL explicit table for genuine name differences, where the MCP
     parameter and the CLI option are simply called different things.
  4. Inline JSON where a file path is expected -> written to a temp file and
     the path passed. This is what makes a batch command self-contained.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It never invents a value, never drops an argument it does not understand, and
never rewrites something Click already accepts. Anything unrecognised is passed
through untouched so Click still reports the error -- a compatibility shim that
silently swallows a genuine mistake would turn a loud failure into a wrong
answer, which is strictly worse.
"""
from __future__ import annotations

import tempfile
from typing import Any

import click
from typer.core import TyperGroup

#: MCP parameter name -> CLI option name, for the cases where they are simply
#: called different things and no mechanical rule can bridge them. Keyed by
#: command name so one command's vocabulary cannot leak into another's.
#:
#: Kept SMALL on purpose. Every entry here is a place where the two interfaces
#: disagree for no reason, and the right long-term fix is to make them agree
#: rather than to grow this table.
_ALIASES: dict[str, dict[str, str]] = {
    "summation": {"expected_sum": "expected"},
    "summation-batch": {"rows": "json_path"},
    "multiplicity": {"tests": "tests_json", "p_values": "p"},
    "duplication-detect": {"blocks": "json_path"},
    "raw-duplication-detect": {"blocks": "json_path"},
    "check-table": {"cells": "json_path"},
    "parse-cells": {"cells": "json_path"},
    "parse-cells-as": {"cells": "json_path"},
}


def _is_argument(param: Any) -> bool:
    """Is this a POSITIONAL parameter?

    By `param_type_name`, not `isinstance(p, click.Argument)`. Typer builds its
    commands against a VENDORED click, so `TyperArgument` is not an instance of
    the `click.Argument` this module imports -- the isinstance check returned
    False for every parameter of every command and the whole rewrite silently
    did nothing. It was silent because `rewrite_args` catches everything and
    returns the input unchanged, which is the right failure mode for a shim and
    the wrong one for finding out that the shim is inert.

    `param_type_name` is 'argument' / 'option' and is part of Click's own
    public parameter protocol, so it survives vendoring and version drift.
    """
    return getattr(param, "param_type_name", "") == "argument"


def _is_pathlike(param: Any) -> bool:
    return isinstance(param.type, click.Path) or getattr(
        param.type, "name", "") in ("path", "file", "filename")


def _looks_like_json(value: str) -> bool:
    v = (value or "").strip()
    return len(v) > 1 and v[0] in "[{"


def _spill(value: str) -> str:
    """Write inline JSON to a temp file and return its path.

    NOT deleted: the command about to read it runs in this same process tree,
    and a reader who wants to see what was passed can still open it. Temp
    files are the OS's to reap.
    """
    fd = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="metascience-inline-", delete=False)
    with fd:
        fd.write(value)
    return fd.name


def rewrite_args(cmd: click.Command, args: list[str]) -> list[str]:
    """Rewrite MCP-shaped arguments into what this command declares.

    Pure: takes the command's own parameter list and the raw argv tail, returns
    a new argv tail. Never raises -- a shim that can fail is a new way for a
    working command to stop working.
    """
    try:
        return _rewrite(cmd, list(args or []))
    except Exception:  # noqa: BLE001 -- see docstring
        return list(args or [])


def _rewrite(cmd: click.Command, args: list[str]) -> list[str]:
    positionals: list[click.Parameter] = [
        p for p in cmd.params if _is_argument(p)]
    by_pos_name = {p.name: p for p in positionals}
    known_flags: set[str] = {
        o for p in cmd.params if not _is_argument(p)
        for o in p.opts + p.secondary_opts}
    # Python name -> the canonical long flag, so a param addressed by its name
    # can be renamed to the spelling Click expects.
    canonical: dict[str, str] = {}
    for p in cmd.params:
        if _is_argument(p):
            continue
        longs = [o for o in p.opts if o.startswith("--")]
        if longs:
            canonical[p.name] = longs[0]

    alias = _ALIASES.get(cmd.name or "", {})
    staged: dict[str, str] = {}
    out: list[str] = []
    i = 0
    while i < len(args):
        tok = args[i]
        if not tok.startswith("--") or tok in known_flags:
            out.append(tok)
            i += 1
            continue

        # `--flag=value` and `--flag value` are both in the archive.
        if "=" in tok:
            flag, _, value = tok.partition("=")
            consumed = 1
        else:
            flag, value, consumed = tok, (args[i + 1] if i + 1 < len(args) else None), 2
        if flag in known_flags:
            out.append(tok)
            i += 1
            continue

        name = flag.lstrip("-").replace("-", "_")
        name = alias.get(name, name)

        if name in by_pos_name and value is not None:
            param = by_pos_name[name]
            staged[name] = _spill(value) if (
                _is_pathlike(param) and _looks_like_json(value)) else value
            i += consumed
            continue
        if name in canonical and value is not None:
            out.extend([canonical[name], value])
            i += consumed
            continue

        # Unrecognised: pass through untouched so Click reports it. Silently
        # dropping an argument would turn a loud failure into a wrong answer.
        out.append(tok)
        i += 1

    if not staged:
        return out
    # Positionals go FIRST and in declared order. Any the caller did not
    # supply as a flag are left to whatever positional tokens are already in
    # `out`, which keeps a half-flag half-positional invocation working.
    lead = [staged[p.name] for p in positionals if p.name in staged]
    return lead + out


class McpFriendlyGroup(TyperGroup):
    """Applies `rewrite_args` to every subcommand's arguments.

    Subclasses `TyperGroup`, not `click.Group`: Typer asserts its own group
    class, and more importantly TyperGroup carries the help formatting the CLI
    already has. A shim that quietly reverted the help output would be paying
    for compatibility with usability.

    `resolve_command` is the one hook that has BOTH the resolved command object
    and its remaining argv, which is exactly what the rewrite needs -- the
    rules are driven by the command's own declared parameters.
    """

    def resolve_command(self, ctx: click.Context, args: list[str]) -> Any:
        name, cmd, rest = super().resolve_command(ctx, args)
        if cmd is not None:
            rest = rewrite_args(cmd, rest)
        return name, cmd, rest
