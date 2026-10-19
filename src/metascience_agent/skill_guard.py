"""The shell fence for `tool_access: skill`: a Claude Code PreToolUse hook.

MEASURED 2026-10-13, Claude Code 2.1.296: under `--permission-mode dontAsk`
the allow pattern `Bash(metascience tool run *)` DID refuse `cat
/etc/hostname`, and DID let `metascience tool run grim_check --json '{...}'
&& echo PWNED` run -- the trailing command executed. A permission pattern is
not a fence for an agent that reads untrusted paper text. This hook is.

It allows exactly three command shapes and refuses everything else:

  metascience tool run <name> --json '<json object>'
  metascience tool describe <name>
  metascience tool list [--role <role>] [--json]

The JSON must sit in ONE pair of single quotes with no single quote inside,
so the shell expands nothing in it; the whole line must match, so no `;`,
`&&`, `|`, `$(...)`, redirection or second command can ride along.

Run BY FILE PATH, stdlib only, as `<python> -I <this file> || exit 2`:
Claude Code treats only exit code 2 as "block", and any other failure as a
non-blocking error that lets the command run -- so a guard that crashes, or
an interpreter that cannot start, must still block. `-I` keeps PYTHONPATH and
user site out of it.
"""

import json
import re
import sys

_NAME = r"[a-z][a-z0-9_]{0,63}"
_ALLOWED = (
    re.compile(rf"metascience tool run {_NAME} --json '[^'\n]*'"),
    re.compile(rf"metascience tool describe {_NAME}"),
    re.compile(r"metascience tool list( --role [a-z_]{1,32})?( --json)?"),
)


def allowed(command: str) -> bool:
    """True iff `command` is exactly one of the three permitted shapes (and,
    for `run`, its quoted payload is one JSON object)."""
    if not isinstance(command, str):
        return False
    cmd = command.strip()
    if not any(p.fullmatch(cmd) for p in _ALLOWED):
        return False
    if cmd.startswith("metascience tool run "):
        payload = cmd.split(" --json ", 1)[1][1:-1]
        try:
            return isinstance(json.loads(payload), dict)
        except ValueError:
            return False
    return True


def main() -> int:
    try:
        event = json.load(sys.stdin)
        tool = event.get("tool_name")
        command = (event.get("tool_input") or {}).get("command")
    except Exception:  # noqa: BLE001 -- unreadable input blocks
        print("skill guard: unreadable hook input; refused", file=sys.stderr)
        return 2
    if tool != "Bash":
        return 0
    if allowed(command):
        return 0
    print("Refused: in this run the only shell commands allowed are "
          "`metascience tool run <name> --json '<json object>'`, "
          "`metascience tool describe <name>` and `metascience tool list`, "
          "each on its own, with the JSON in single quotes.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
