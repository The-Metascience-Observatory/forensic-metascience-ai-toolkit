"""Which LLM CLI drives a forensic run -- Claude Code, Grok, or Codex.

Every model call in this repo used to hardcode the `claude` binary, its
flags, and its `stream-json` event shapes. Grok's headless mode is
Claude-compatible on the stream *shape* (`streaming-messages-json`) and
incompatible on the things that would silently empty a review:

* `-p` does not read stdin (a large paper dies on argv, or hangs).
* There is no `--mcp-config`; forensic tools come from `.grok/config.toml`
  via `--cwd`, and only after the folder is trusted.
* Forensic calls arrive as `use_tool` with a double-wrapped `OkayOutput`.
* There is no `--max-budget-usd` and no `/usage` probe.
* MCP results truncate at 20 KB unless `GROK_MAX_MCP_OUTPUT_BYTES` is set.
* CamelCase `--disallowedTools` is a no-op (permission-rule alias, not
  tool exposure). The kebab `--disallowed-tools` is the real denylist.

Codex (`codex exec`, measured against codex-cli 0.147.0 on 2026-09-01) is
incompatible in its own ways:

* Its `--json` stream is a DIFFERENT event vocabulary (`thread.started`,
  `item.started/completed`, `turn.completed`) that maps 1-to-N onto the
  Claude shapes, so it gets a stateful normalizer, not `normalize_event`.
* There is no `--append-system-prompt`; the system prompt travels as
  `AGENTS.md` in a per-run sandbox dir (`-C <run_dir>`), with
  `project_doc_max_bytes` raised past the 32 KiB default that would
  silently truncate the tool-expert prompt.
* MCP servers come from `-c mcp_servers.*` config overrides under
  `--ignore-user-config` (auth stays in `CODEX_HOME`; the user's
  config.toml is never loaded and never written).
* MCP calls FAIL under `approval_policy="never"` unless the server sets
  `default_tools_approval_mode="approve"` -- measured: the call errored
  and the model then FABRICATED the tool's verdict in its final answer.
* `tools.web_search=false` does NOT detach the web tool on models whose
  catalog carries `web_search_tool_type` -- the fetch still succeeded.
  Only `allowed_domains` pinned to an unresolvable sentinel actually
  blocked it ("URL ... is not safe to open").
* There is no `--max-budget-usd` and no `--max-turns`. The usage probe is
  `codex app-server`'s `account/rateLimits/read` (see `usage_guard`).

Antigravity (`agy -p`, measured against agy 1.4.2 on 2026-10-18) is
incompatible in its own ways again:

* `-p` takes the prompt as its VALUE (argv), so the prompt goes down stdin
  as one `{"event":"user",...}` line under `--input-format stream-json`.
* Its stream is `{"event": ...}` lines (`init`, `step_update`, `result`):
  a stateful normalizer, like Codex. MCP calls arrive through ONE meta-tool,
  `call_mcp_tool` `{ServerName, ToolName, Arguments}`, like Grok's
  `use_tool`. A large MCP result is NOT in the stream: it is spilled to
  `brain/<conversation>/.system_generated/steps/<n>/output.txt` under the
  config home and the model reads it with `view_file` (measured: a 53 KB
  `extract_xml` result arrived as `output: ""`).
* There is no `--mcp-config`, no `--system-prompt`, no tool allowlist flag
  and no config-home variable. Everything comes from a per-run `HOME`
  (auth stays in the OS keyring, measured): `mcp_config.json`, a
  `settings.json` with trust and permission rules, and a custom agent
  (`--agent`) whose BODY is the system prompt and whose `tools:` list is
  the built-in allowlist. Workspace `AGENTS.md` was rejected: rules are
  capped at 24 KB and our prompts are ~100 KB; the agent body carried a
  156 KB prompt with canaries at start, middle and end intact.
* A server that fails to start is dropped SILENTLY (no event, exit 0), so
  liveness is the same pre-spend stdio handshake Codex uses.
* `excludeDefaultComponents` also removes `finish`, the tool that carries
  `--json-schema` output; without it `structured_output` never appears.
* There is no `--max-budget-usd`, no `--max-turns` and no cost figure.
  The usage probe is the free `agy -p /usage --output-format json`.

A naive port therefore produces a sweep that checked nothing and still
reads as a clean paper. This module is the seam that either runs each
backend correctly or refuses out loud. Claude argv stays byte-identical
to what `_build_claude_cmd` already emitted.
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

FORENSIC_SERVER = "forensic_metascience"
MCP_TOOL_PREFIX = f"mcp__{FORENSIC_SERVER}__"
PAPER_DIR_ENV = "METASCIENCE_PAPER_DIR"

#: Default per-run sandbox root, trusted ONCE (one entry in
#: `~/.grok/trusted_folders.toml`); a fresh `mkdtemp` per paper would leak one
#: dead trust entry per run. That entry is no longer what ungates the
#: per-run subdirectory -- see `GROK_FOLDER_TRUST_ENV` -- but it is kept for
#: the grok versions where it still does.
DEFAULT_GROK_SANDBOX_ROOT = Path.home() / ".cache" / "metascience" / "grok-sandbox"

#: The switch that actually lets a per-run sandbox start its project-scoped
#: MCP server. MEASURED 2026-09-02, grok 1.0.13: with the sandbox ROOT in the
#: trust store (as `_ensure_sandbox_root_trusted` writes it) `grok mcp doctor`
#: in a fresh `run-<uuid>/` reported "folder untrusted: repo-local
#: (project-scoped) server not started", and every eval run died before
#: spend with `MCPUnavailable`. Grok's own docs (user-guide/10-hooks.md): a
#: trust grant "covers subdirectories of the same repository" -- and the
#: sandbox root is not a git repository, so in 1.0.13 nothing under it is
#: covered. The same docs name `GROK_FOLDER_TRUST=0` as the way to disable
#: folder-trust gating for a process; set in the sandbox subprocess's env
#: (both the doctor probe and the run) the doctor reported handshake OK and
#: the stage's tools discovered. It ungates project hooks too, which is
#: acceptable only because the sandbox is ours: it holds one config we
#: wrote and no hooks. Under grok 1.0.5 (the v1.3.0 eval runs) trust
#: cascaded to any subdirectory and none of this was needed.
GROK_FOLDER_TRUST_ENV = {"GROK_FOLDER_TRUST": "0"}

#: Raise well above Grok's 20 KB MCP-output default. Measured 2026-08-18:
#: `extract_pdf` on a real paper returned 20,709 bytes truncated of 95.4 KB
#: at the default, and 98,903 complete with this override.
GROK_MCP_OUTPUT_BYTES = "8000000"

#: Grok built-ins we expose. `search_tool` / `use_tool` are always-on MCP
#: meta-tools and MUST NOT appear on the denylist -- they are the only route
#: to the forensic server. That is a weaker sandbox than Claude's, and the
#: report has to say so.
GROK_BUILTIN_TOOLS = ("read_file",)

#: Belt-and-braces over `--tools read_file`. kebab-case, comma-joined.
#: `search_tool` and `use_tool` are deliberately absent.
GROK_DENIED_TOOLS = (
    "run_terminal_cmd",
    "write",
    "search_replace",
    "web_fetch",
    "web_search",
    "spawn_subagent",
)

#: Default per-run sandbox root for Codex. Unlike Grok there is no trust
#: store to seed -- `--ignore-user-config` plus `--skip-git-repo-check` is
#: the whole isolation story -- so this exists only to keep run dirs in one
#: predictable, cleanable place.
DEFAULT_CODEX_SANDBOX_ROOT = Path.home() / ".cache" / "metascience" / "codex-sandbox"

#: Codex caps project docs (AGENTS.md) at 32 KiB by default. The tool-expert
#: system prompt is several times that; a default-sized cap would silently
#: truncate the rulebook mid-sentence. MEASURED 2026-09-01: a 108,055-byte
#: AGENTS.md with canary tokens at start, middle and end arrived complete in
#: `codex debug prompt-input` under this override.
CODEX_PROJECT_DOC_MAX_BYTES = 1_048_576

#: Codex truncates tool output at `tool_output_token_limit` TOKENS (its
#: analog of Grok's 20 KB `GROK_MAX_MCP_OUTPUT_BYTES` lesson). The largest
#: measured single tool output is `extract_pdf` at ~98.9 KB (~25K tokens);
#: this ceiling leaves an order of magnitude of headroom without being
#: unbounded.
CODEX_TOOL_OUTPUT_TOKEN_LIMIT = 250_000

#: Feature flags disabled on every forensic Codex invocation. These are the
#: capability surfaces `codex features list` reports as stable-and-on that a
#: forensic sweep must not have: MEASURED 2026-09-01, without `--disable
#: apps` the model saw ~130 foreign `mcp__codex_apps__*` tools (GitHub
#: writes, site deploys, plugin installs) EVEN UNDER `--ignore-user-config`.
#: `shell_snapshot` is included because it writes state under ~/.codex on
#: every run, which `--ephemeral` does not suppress. Doubles as the recorded
#: `denied_tools` on the CODEX Backend, the same way GROK_DENIED_TOOLS does.
CODEX_DISABLED_FEATURES = (
    "shell_snapshot",
    "apps",
    "image_generation",
    "view_image",
    "browser_use",
    "in_app_browser",
    "plugins",
    "skill_search",
    "tool_suggest",
    "multi_agent",
    "computer_use",
    "sleep_tool",
)

#: The operator's personal skills stay out of the model's context.
#: `--ignore-user-config` does not cover them: Codex discovers skills from
#: directories (`~/.agents/skills`, including claude.ai-synced ones), not from
#: config.toml, and lists every one in the prompt. MEASURED 2026-10-11, codex
#: 0.160.1: a gpt-5.6-terra science agent spent its first call reading a
#: synced `pdf/SKILL.md` from the operator's home. `codex debug prompt-input`
#: shows the listing (89 `SKILL.md` references, 24,920 bytes) and this key
#: removes it (0 references, 2,554 bytes); `--disable skill_search`,
#: `--enable skip_host_skill_discovery`, `features.skills=false` and
#: `include_skills_usage_instructions=false` each left it in place. Live
#: `codex exec` on gpt-5.6-luna, asked which skills it had been told about:
#: five names without this key (one from ~/.agents/skills), "NONE" with it,
#: and 15,214 -> 9,438 tokens for the same one-line question.
CODEX_SKILLS_CONFIG = "skills.include_instructions=false"

#: The no-internet analysts run with the web tool's domain allowlist pinned
#: to a name that cannot resolve. This is NOT belt-and-braces: it is the only
#: knob that measurably blocks egress. MEASURED 2026-09-01 on gpt-5.6-sol:
#: with `tools.web_search=false` (and `{enabled=false}`) the model still
#: fetched a live time API; with this allowlist the web tool refused ("URL
#: ... is not safe to open"), search returned empty, and the read-only
#: sandbox denied the shell's DNS ("Could not resolve host").
CODEX_NO_INTERNET_DOMAIN = "metascience-no-internet.invalid"

#: Default per-run sandbox root for Antigravity. Each run gets `home/` (the
#: config home `agy` reads instead of the operator's) and `ws/` (its cwd).
DEFAULT_ANTIGRAVITY_SANDBOX_ROOT = (
    Path.home() / ".cache" / "metascience" / "antigravity-sandbox")

#: The custom agent every forensic Antigravity launch selects with `--agent`.
ANTIGRAVITY_AGENT = "forensic"

#: Built-in tools the forensic agent may use. `finish` is NOT optional: it is
#: the tool that delivers `--json-schema` output, and `excludeDefaultComponents`
#: removes it with the rest (measured 2026-10-18: no `structured_output` until
#: it was listed). `view_file` is the `Read` analog. The CLI adds
#: `call_mcp_tool`, `list_resources`, `read_resource` and `manage_task` on its
#: own when MCP is enabled; none of them reaches a shell or the network.
ANTIGRAVITY_BUILTIN_TOOLS = ("view_file", "finish")

#: The web pair, granted only to the internet-on science agent.
ANTIGRAVITY_WEB_TOOLS = ("search_web", "read_url_content")

#: Permission rules written to the run's settings.json. Belt and braces over
#: the agent's tool allowlist: these are what refused a `run_command` the
#: default agent attempted (measured, "Matches user-configured deny rule").
#: `read_url(*)` moves to `allow` on the internet-on variant.
ANTIGRAVITY_DENY_RULES = (
    "command(*)", "unsandboxed(*)", "read_url(*)", "execute_url(*)",
    "write_file(*)",
)

#: Effort levels each listed model offers (`agy models`, 2026-10-18). The
#: slug is `<base>-<effort>`; a full slug plus a different `--effort` is a
#: hard error in agy, so `antigravity_model_args` never sends both.
ANTIGRAVITY_MODELS: dict[str, tuple[str, ...]] = {
    "gemini-4-argon": ("low", "medium", "high"),
    "gemini-3.8-flash": ("low", "medium", "high"),
    "claude-opus-5-5": ("low", "medium", "high"),
    "claude-sonnet-5-5": ("low", "medium", "high"),
    "gpt-oss-120b": ("medium",),
}

_EFFORT_ORDER = ("low", "medium", "high", "xhigh", "max")
_EFFORT_SUFFIX_RE = re.compile(r"-(low|medium|high|xhigh|max)$")

_TOOLS_DISCOVERED_RE = re.compile(r"(\d+)\s+tools?\s+discovered", re.I)

#: Process-level cache for `Backend.assert_mcp_live`: SUCCESSES ONLY. 2-3
#: stages per paper share one probe; a process that switches backends
#: re-probes. A failure is never cached. MEASURED 2026-10-18, the tools_only
#: grok batch (10 workers, beside a peer's 7-worker grok batch): one failed
#: `grok mcp doctor` was cached as the string error, and every remaining
#: paper of the batch then failed instantly with the same MCPUnavailable,
#: 20 of 20, retries included -- the batch's per-paper retry re-read the
#: cache instead of the server.
_MCP_LIVE_CACHE: dict[str, None] = {}

#: Probe attempts before `assert_mcp_live` raises, and the pause before each
#: re-probe. A server that is truly broken (wrong import tree, missing
#: package) fails every attempt and still raises -- the guard stays CLOSED;
#: a handshake that lost a race with a loaded machine gets two more chances.
MCP_PROBE_ATTEMPTS = 3
MCP_PROBE_BACKOFF_SECONDS: tuple[float, ...] = (2.0, 5.0)
_probe_pause = time.sleep

_VERSION_CACHE: dict[str, str] = {}


class MCPUnavailable(RuntimeError):
    """The forensic MCP server is not actually reachable.

    Raised before spend when `grok mcp doctor` is unhealthy, and mid-stage
    when the init event has no `forensic_metascience` entry. Distinct from
    a tool returning empty: this is OUR plumbing, and a missing server
    must not read as a paper with nothing to check.
    """


class ForensicToolsNeverRan(RuntimeError):
    """Stage 1 declared MCP tools and the ledger recorded zero validated calls.

    The only layer that proves the tools were reachable *by the model*.
    Measured 2026-08-18 across 59 archived stage-1 ledgers: min 14 validated
    calls, never zero. Stage 2 is exempt -- an editorial pass may make none.

    `stage` is the raw `_run_stage` dict, carried so the batch runner can
    write a diagnostic instead of dropping a paid (or 19-second) call on
    the floor with only the traceback.
    """

    def __init__(
        self,
        message: str = "",
        stage: dict | None = None,
        prior_stages: list | None = None,
    ):
        super().__init__(message)
        self.stage = stage
        # Earlier empty-dump attempts when Grok was retried once. The last
        # attempt is `stage`; these are billed too and must reach the cost
        # ledger.
        self.prior_stages = list(prior_stages or [])


class BackendSandboxError(RuntimeError):
    """The per-run Grok sandbox could not be created or trusted."""


#: stderr substrings that mean THE ACCOUNT cannot serve any request: no
#: credit, no key, revoked auth. Every paper in a batch would fail the same
#: way, and retrying cannot fix any of them.
#:
#: CONSERVATIVE IN ONE DIRECTION ON PURPOSE. A rate limit (429), a 5xx or a
#: timeout is TRANSIENT and must stay per-paper and retryable: stopping a
#: healthy overnight batch on a hiccup is a worse failure than the cascade
#: this list exists to prevent. Only account-level refusals belong here.
FATAL_BACKEND_MARKERS: tuple[str, ...] = (
    "402", "payment required", "usage balance exhausted",
    "insufficient_quota", "insufficient quota", "credit balance",
    "401", "unauthorized", "invalid api key", "invalid_api_key",
    "not logged in", "please run /login", "authentication_error",
    # Codex phrasings. A logged-out codex exec was measured (2026-09-01)
    # emitting "401 Unauthorized" on stderr, already matched above; these
    # cover its login-nudge and plan-limit wordings. Codex has no usage
    # guard, so a hit limit is an account-level stop, not a per-paper retry.
    "run codex login", "usage limit reached",
    # Antigravity phrasings (agy changelog 1.2.13-1.3.3 and the CLI's own
    # strings; a daily or billing cap stops the run instead of retrying).
    "authentication required", "authentication expired",
    "not logged into antigravity", "individual quota reached",
    "ai credits balance is too low",
)


def fatal_backend_reason(stderr: str) -> str | None:
    """The account-level refusal in this stderr, or None.

    Returns the MARKER that matched, so the caller can name the reason rather
    than saying "the backend failed" -- `402 Payment Required: Grok Build usage
    balance exhausted` is a message an operator can act on in one step.
    """
    low = (stderr or "").lower()
    for marker in FATAL_BACKEND_MARKERS:
        if marker in low:
            return marker
    return None


class BackendUnavailable(RuntimeError):
    """The backend cannot serve ANY request: no credit, no key, revoked auth.

    Distinct from `StageError`, which is a property of one paper's run. This is
    a property of the environment, so the batch runner stops on the first one
    and keeps it OUT of the retry queue -- the same treatment
    `PreflightError` and `BudgetUnsupported` already get.

    Measured 2026-08-23: a grok batch with an exhausted xAI balance produced
    twenty identical 402s, ten tracebacks, and ten rows in `failed.jsonl`
    naming papers that had nothing wrong with them.
    """


class BudgetUnsupported(ValueError):
    """`--budget-usd` was passed to a backend with no spend cap.

    Subclass of ValueError so existing `pytest.raises(ValueError)` still
    matches; distinct so the batch runner can treat it as an environment
    / invocation fault (every paper would fail the same way) rather than a
    per-paper retryable error.
    """


@dataclass(frozen=True)
class Backend:
    name: str
    binary: str
    default_model: str
    stream_format: str
    prompt_delivery: str
    supports_budget: bool
    supports_usage_probe: bool
    mcp_strategy: str
    builtin_tools: tuple[str, ...]
    denied_tools: tuple[str, ...]
    sandbox_weaker: bool

    def assert_mcp_live(self, sandbox: Path | None) -> None:
        """Pre-spend liveness. Claude: no-op. Grok: `mcp doctor --json`.
        Codex: a direct stdio handshake with our own server, because
        `codex doctor --json`'s mcp check is config-consistency only
        (measured: durationMs=0, no process spawned).

        A SUCCESS is cached per process+backend so 2-3 stages cost one probe;
        a failure is retried (`MCP_PROBE_ATTEMPTS`, pausing
        `MCP_PROBE_BACKOFF_SECONDS`) and then raised, and never cached, so
        the next stage probes again (see `_MCP_LIVE_CACHE`). Blocking: the
        runtime calls it in a worker thread. Does NOT consult
        `mcp_servers[].status` -- on Grok that field is configuration,
        always `"connected"`, and a guard keyed on it cannot fail.
        """
        if self.mcp_strategy == "flag":
            return
        if os.environ.get("METASCIENCE_SKIP_MCP_LIVE") == "1":
            return
        if self.mcp_strategy == "cwd_config":
            def probe():
                _probe_mcp_doctor(sandbox)
        elif self.mcp_strategy in ("config_overrides", "home_config"):
            # Antigravity drops a server that fails to start without a word
            # (measured: exit 0, no event, the model went looking for a
            # config file), so it gets the same direct handshake as Codex.
            probe = _probe_mcp_stdio
        else:
            return
        key = self.name
        if key in _MCP_LIVE_CACHE:
            return
        errors: list[str] = []
        for attempt in range(max(1, MCP_PROBE_ATTEMPTS)):
            if attempt:
                pauses = MCP_PROBE_BACKOFF_SECONDS or (0.0,)
                _probe_pause(pauses[min(attempt - 1, len(pauses) - 1)])
            try:
                probe()
            except MCPUnavailable as exc:
                errors.append(str(exc))
                continue
            _MCP_LIVE_CACHE[key] = None
            return
        distinct = list(dict.fromkeys(errors))
        raise MCPUnavailable(
            distinct[-1] if len(errors) == 1 else
            f"{distinct[-1]} (failed {len(errors)} probe(s) in a row"
            + (f"; earlier: {' | '.join(distinct[:-1])}" if len(distinct) > 1 else "")
            + ")")


@dataclass
class Invocation:
    """One CLI launch. `_run_stage` reads this, never a bare argv, so a Grok
    workdir cannot be silently dropped."""

    argv: list[str]
    prompt_delivery: str
    workdir: Path | None
    env_overlay: dict[str, str]
    cleanup: Callable[[], None]
    backend: Backend
    prompt_path: Path | None = None
    allowed_tools: tuple[str, ...] = ()
    #: True when the caller asked for a turn cap the backend cannot enforce
    #: (Codex has no --max-turns). Stamped rather than raised: the internal
    #: repair call passes max_turns=1 on every backend, so raising would
    #: break repair, and dropping it silently would violate refuse-out-loud.
    #: `_run_stage` carries the stamp into the stage payload.
    max_turns_unsupported: bool = False
    #: True when the invocation declared a --json-schema / --output-schema.
    #: The Codex stream normalizer uses it to know the final agent message
    #: should parse as the structured output.
    expects_schema: bool = False
    #: The ORIGINAL (pre-strict-rewrite) schema on the codex path, so the
    #: normalizer can run `restore_from_strict` and hand downstream the same
    #: document shape a Claude run produces. None everywhere else.
    restore_schema: dict | None = None
    #: The model as the CLI was told it. Read by the usage guard on
    #: Antigravity, whose quota buckets are per model family (Gemini vs
    #: Claude-and-GPT): a Gemini run must not pause on a spent Claude bucket.
    model: str | None = None
    #: Antigravity only: the run's config home, where the CLI spills large
    #: MCP results (`brain/<conversation>/.system_generated/steps/<n>/`).
    #: The normalizer reads them back so the ledger holds the real answer.
    config_home: Path | None = None
    #: Antigravity only: shared with its stream normalizer. Records the
    #: conversation id, and `keep=True` when a schema-bearing turn ended
    #: without `finish`, which makes `cleanup` RETAIN the run dir so the
    #: retry can resume that conversation (`antigravity_resume_invocation`).
    resume_state: dict | None = None
    #: Whether this launch asked for the forensic MCP server. Image screening
    #: deliberately asks for NO server (it looks at exhibits, it does not call
    #: tools), and the init-event gate has to know that: it used to demand
    #: `forensic_metascience` unconditionally, so every Grok image screen aborted
    #: on a server the caller had deliberately withheld -- 62 of 62 escalations in
    #: the run on the embargoed 2026-09 corpus, silently blamed on folder trust. Stamped rather
    #: than inferred from the argv, because absence of a flag cannot distinguish
    #: "not asked for" from "asked for and lost".
    forensic_mcp: bool = True


CLAUDE = Backend(
    name="claude",
    binary="claude",
    default_model="opus",
    stream_format="stream-json",
    prompt_delivery="stdin",
    supports_budget=True,
    supports_usage_probe=True,
    mcp_strategy="flag",
    builtin_tools=("Read",),
    denied_tools=(
        "Bash", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch",
        "Task", "ToolSearch",
    ),
    sandbox_weaker=False,
)

GROK = Backend(
    name="grok",
    binary="grok",
    default_model="grok-4.6",
    stream_format="streaming-messages-json",
    prompt_delivery="prompt_file",
    supports_budget=False,
    supports_usage_probe=False,
    mcp_strategy="cwd_config",
    builtin_tools=GROK_BUILTIN_TOOLS,
    denied_tools=GROK_DENIED_TOOLS,
    sandbox_weaker=True,
)

CODEX = Backend(
    name="codex",
    binary="codex",
    default_model="gpt-5.6-sol",
    stream_format="codex-jsonl",
    prompt_delivery="stdin",
    supports_budget=False,
    # `codex app-server` answers account/rateLimits/read with the 5-hour and
    # weekly gauges; usage_guard.probe_codex_usage speaks it (2026-09-02).
    supports_usage_probe=True,
    mcp_strategy="config_overrides",
    # Codex has no file-read tool separate from its shell; the read-only
    # unified_exec shell is its `Read` analog (decided 2026-09-01), which is
    # why `sandbox_weaker` is True -- see `sandbox_limitation_sentence`.
    builtin_tools=("Bash",),
    denied_tools=CODEX_DISABLED_FEATURES,
    sandbox_weaker=True,
)

#: Our own agent loop over the OpenRouter API (`openrouter_loop.py`), launched
#: as a subprocess that speaks Claude's stream-json, so `_run_stage` reads it
#: unchanged. It starts the MCP servers itself and reports them live, like
#: Claude. No spend cap and no usage probe: OpenRouter bills per call and the
#: loop records `usage.cost`.
OPENROUTER = Backend(
    name="openrouter",
    binary="python",
    default_model="anthropic/claude-sonnet-5.5",
    stream_format="stream-json",
    prompt_delivery="stdin",
    supports_budget=False,
    supports_usage_probe=False,
    mcp_strategy="flag",
    builtin_tools=("Read",),
    denied_tools=(),
    sandbox_weaker=False,
)

OPENROUTER_LOOP_MODULE = "metascience_agent.openrouter_loop"

#: Google Antigravity's CLI (`agy`). Everything is delivered through a per-run
#: config HOME (see `_build_antigravity_invocation`); the built-in surface is a
#: true allowlist (the custom agent's `tools:`), so the sandbox is not weaker
#: than Claude's on that axis. No spend cap; the usage probe is `/usage`.
ANTIGRAVITY = Backend(
    name="antigravity",
    binary="agy",
    default_model="gemini-4-argon",
    stream_format="agy-stream-json",
    prompt_delivery="stdin_stream_json",
    supports_budget=False,
    supports_usage_probe=True,
    mcp_strategy="home_config",
    builtin_tools=ANTIGRAVITY_BUILTIN_TOOLS,
    denied_tools=ANTIGRAVITY_DENY_RULES,
    sandbox_weaker=False,
)

_BACKENDS = {"claude": CLAUDE, "grok": GROK, "codex": CODEX,
             "openrouter": OPENROUTER, "antigravity": ANTIGRAVITY}

#: Spellings of a backend name that resolve to it. `agy` is the command the
#: CLI installs, and what an operator types first.
_BACKEND_ALIASES = {"agy": "antigravity"}


def resolve_backend(name: str | Backend | None = None) -> Backend:
    """explicit argument → ``METASCIENCE_LLM_CLI`` → ``"claude"``."""
    if isinstance(name, Backend):
        return name
    raw = (name or os.environ.get("METASCIENCE_LLM_CLI") or "claude").strip().lower()
    raw = _BACKEND_ALIASES.get(raw, raw)
    if raw not in _BACKENDS:
        raise ValueError(
            f"unknown LLM backend {raw!r}; expected 'claude', 'grok', 'codex', "
            f"'openrouter' or 'antigravity'"
        )
    return _BACKENDS[raw]


def sandbox_root() -> Path:
    override = os.environ.get("METASCIENCE_GROK_SANDBOX_ROOT")
    return Path(override) if override else DEFAULT_GROK_SANDBOX_ROOT


def codex_sandbox_root() -> Path:
    override = os.environ.get("METASCIENCE_CODEX_SANDBOX_ROOT")
    return Path(override) if override else DEFAULT_CODEX_SANDBOX_ROOT


def antigravity_sandbox_root() -> Path:
    override = os.environ.get("METASCIENCE_ANTIGRAVITY_SANDBOX_ROOT")
    return Path(override) if override else DEFAULT_ANTIGRAVITY_SANDBOX_ROOT


def antigravity_model_args(model: str, effort: str | None) -> list[str]:
    """`--model`/`--effort` for agy, never a combination agy refuses.

    A full slug (`gemini-4-argon-high`) already names its effort, and agy
    exits 1 on a slug plus a DIFFERENT `--effort` (measured), so a slug is
    sent alone and the pipeline's effort does not override what the operator
    picked. A base name gets `--effort`, clamped to what that model offers:
    the pipeline asks for `xhigh`/`max` on Claude, and no agy model has them
    (agy picks the model's default for a base name with no effort, which
    would silently be lower than asked). Clamped DOWN to the nearest offered
    level, else the lowest offered; an unknown base is passed through as-is
    so agy refuses it by name.
    """
    model = (model or "").strip()
    if _EFFORT_SUFFIX_RE.search(model) and model not in ANTIGRAVITY_MODELS:
        return ["--model", model]
    if not effort:
        return ["--model", model]
    offered = ANTIGRAVITY_MODELS.get(model)
    if offered is None:
        return ["--model", model, "--effort", effort]
    if effort not in offered:
        want = _EFFORT_ORDER.index(effort) if effort in _EFFORT_ORDER else 2
        below = [e for e in offered if _EFFORT_ORDER.index(e) <= want]
        effort = below[-1] if below else offered[0]
    return ["--model", model, "--effort", effort]


def antigravity_model_family(model: str | None) -> str | None:
    """Which `/usage` quota group a model draws on, or None if unknown.

    `gemini` (Flash and Pro share one group; Argon also has its own weekly
    bucket) or `third_party` (Claude and GPT-OSS share one)."""
    m = (model or "").lower()
    if m.startswith("gemini"):
        return "gemini"
    if m.startswith(("claude", "gpt")):
        return "third_party"
    return None


def list_antigravity_models(timeout: float = 60.0) -> list[tuple[str, str]]:
    """The models THIS account can use, from `agy models`: [(slug, label)].

    Live, never the static table: which models appear depends on the sign-in
    (a Google Cloud project only lists the third-party models it may call,
    agy 1.3.4). Raises `RuntimeError` naming the failure; an empty list from
    a CLI that answered is returned as empty, not papered over."""
    agy = shutil.which(ANTIGRAVITY.binary)
    if agy is None:
        raise RuntimeError("agy is not on PATH; install Google Antigravity's CLI")
    try:
        proc = subprocess.run([agy, "models"], capture_output=True, text=True,
                              timeout=timeout,
                              env={**os.environ, "AGY_CLI_DISABLE_AUTO_UPDATE": "true"})
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"`agy models` failed to run: {exc}") from exc
    if proc.returncode != 0:
        raise RuntimeError(
            f"`agy models` exited {proc.returncode}: "
            f"{(proc.stderr or proc.stdout or '').strip()[:300]}")
    return parse_agy_models(proc.stdout)


def parse_agy_models(text: str) -> list[tuple[str, str]]:
    """`slug<TAB>label` lines; the "Fetching available models..." banner and
    blank lines are skipped."""
    out: list[tuple[str, str]] = []
    for line in (text or "").splitlines():
        slug, sep, label = line.strip().partition("\t")
        if not sep or not slug or " " in slug:
            continue
        out.append((slug.strip(), label.strip()))
    return out


#: Claude Code has no model-listing command; these are the aliases its
#: `--help` names (2.1.x). A full model id is accepted too.
CLAUDE_MODEL_ALIASES = ("fable", "opus", "sonnet", "haiku")

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


def parse_grok_models(text: str) -> list[tuple[str, str]]:
    """`grok models`: `  * grok-4.7 (default)` / `  - grok-4.6` lines under
    "Available models:"; the login banner is skipped."""
    out: list[tuple[str, str]] = []
    for line in (text or "").splitlines():
        m = re.match(r"\s*[*-]\s+(\S+)\s*(\(.*\))?\s*$", line)
        if m:
            out.append((m.group(1), (m.group(2) or "").strip("()")))
    return out


def parse_codex_models(text: str) -> list[tuple[str, str]]:
    """`codex debug models` JSON: the catalog entries with visibility
    `list` (the hidden ones are internal, e.g. auto-review)."""
    import json
    data = json.loads(text)
    models = data.get("models", []) if isinstance(data, dict) else data
    out: list[tuple[str, str]] = []
    for m in sorted(models, key=lambda m: m.get("priority", 999)):
        if m.get("visibility", "list") != "list":
            continue
        efforts = [e.get("effort") for e in m.get("supported_reasoning_levels") or []]
        label = m.get("display_name") or ""
        if efforts:
            label += f" (effort: {', '.join(e for e in efforts if e)})"
        out.append((m["slug"], label))
    return out


def _cli_models(argv: list[str], parse, timeout: float) -> list[tuple[str, str]]:
    exe = shutil.which(argv[0])
    if exe is None:
        raise RuntimeError(f"{argv[0]} is not on PATH")
    try:
        proc = subprocess.run([exe, *argv[1:]], capture_output=True, text=True,
                              timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"`{' '.join(argv)}` failed to run: {exc}") from exc
    if proc.returncode != 0:
        raise RuntimeError(f"`{' '.join(argv)}` exited {proc.returncode}: "
                           f"{(proc.stderr or proc.stdout or '').strip()[:300]}")
    try:
        return parse(proc.stdout)
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(f"`{' '.join(argv)}` output unparseable: {exc}") from exc


def list_openrouter_models(timeout: float = 20.0) -> list[tuple[str, str]]:
    """OpenRouter's public catalog (no key needed to list): [(id, name)]."""
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(OPENROUTER_MODELS_URL, timeout=timeout) as resp:
            data = json.load(resp)
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"{OPENROUTER_MODELS_URL} unreachable: {exc}") from exc
    return sorted((m["id"], m.get("name", "")) for m in data.get("data", []))


def list_backend_models(name: str, timeout: float = 60.0
                        ) -> tuple[list[tuple[str, str]], str]:
    """The models a backend offers: ([(model, label)], source).

    `source` says where the list came from -- `live` (the CLI or API asked
    now, so it reflects this sign-in) or `static` (Claude Code has no listing
    command). Raises `RuntimeError` naming the failure; an empty live answer
    is returned empty."""
    be = resolve_backend(name)
    if be.name == "claude":
        return [(a, "alias") for a in CLAUDE_MODEL_ALIASES], "static"
    if be.name == "grok":
        return _cli_models([be.binary, "models"], parse_grok_models, timeout), "live"
    if be.name == "codex":
        return _cli_models([be.binary, "debug", "models"], parse_codex_models,
                           timeout), "live"
    if be.name == "openrouter":
        return list_openrouter_models(min(timeout, 20.0)), "live"
    return list_antigravity_models(timeout), "live"


def backend_installed(backend: Backend) -> tuple[bool, str]:
    """(usable, detail): the binary's path, or for OpenRouter whether the
    API key is set (its 'binary' is this interpreter)."""
    if backend.name == "openrouter":
        key = bool(os.environ.get("OPENROUTER_API_KEY"))
        return key, "OPENROUTER_API_KEY set" if key else "OPENROUTER_API_KEY not set"
    path = shutil.which(backend.binary)
    return (path is not None), (path or f"{backend.binary} not on PATH")


def backend_binary_version(backend: Backend) -> str:
    """`claude --version` / `grok --version`, cached. Best-effort."""
    if backend.name == "openrouter":
        return "openrouter_loop (OpenRouter chat completions API)"
    if backend.name in _VERSION_CACHE:
        return _VERSION_CACHE[backend.name]
    text = "not recorded"
    try:
        proc = subprocess.run(
            [backend.binary, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        line = (proc.stdout or proc.stderr or "").strip().splitlines()
        if line:
            text = line[0].strip()[:120]
    except (OSError, subprocess.SubprocessError):
        pass
    _VERSION_CACHE[backend.name] = text
    return text


def off_stage_mcp_names(allowed_tools: list[str]) -> list[str]:
    """Registered tools this stage did NOT allow -- the Grok deny complement.

    Derived from ``registry.SPECS``, never a hand list. Per-stage restriction
    cannot use an allowlist on Grok (`--allow` only auto-approves), so we
    deny everything not on this stage's list.
    """
    from .integration import forensic_tool_names
    if forensic_tool_names is None:
        raise MCPUnavailable("Forensic tool registry is not configured by a host")
    names = forensic_tool_names()

    allowed_short = {
        t[len(MCP_TOOL_PREFIX):]
        for t in allowed_tools
        if isinstance(t, str) and t.startswith(MCP_TOOL_PREFIX)
    }
    return sorted(name for name in names if name not in allowed_short)


def grok_deny_rules(allowed_tools: list[str]) -> list[str]:
    """Repeatable `--deny MCPTool(forensic_metascience__<name>)` values."""
    return [
        f"MCPTool({FORENSIC_SERVER}__{name})"
        for name in off_stage_mcp_names(allowed_tools)
    ]


def build_invocation(
    backend: Backend,
    *,
    system_prompt: str,
    allowed_tools: list[str],
    model: str,
    effort: str,
    json_schema: dict | None = None,
    budget_usd: float | None = None,
    paper_dir: str | Path | None = None,
    denied_tools: list[str] | None = None,
    mcp_config_json: str | None = None,
    max_turns: int | None = None,
    python_executable: str | None = None,
    claude_builtin_tools: list[str] | None = None,
    claude_denied_tools: list[str] | None = None,
    internet: bool = False,
    mcp_stage: str | None = None,
    run_slug: str | None = None,
    vision: bool = False,
    forensic_mcp: bool = True,
    mcp_tools: list[str] | None = None,
    permission_mode: str | None = None,
    env_overlay: dict[str, str] | None = None,
    settings_json: str | None = None,
) -> Invocation:
    """Build one CLI invocation. Claude argv is the historical byte sequence.

    `permission_mode`/`env_overlay` exist for `tool_access: skill` (Claude
    only): the agent reaches its tools through `metascience tool run` in a
    shell, so the launch needs `dontAsk` -- under which only the allowlist's
    `Bash(metascience tool ...)` patterns run and anything else is refused --
    and the environment that fences and receipts those calls. Unset, the
    argv is exactly what it always was.

    `vision=True` is the image adjudicator's variant: that stage exists to
    LOOK at panel exhibits, and a clear made without opening an image is
    demoted to insufficient_evidence in code. Claude's `Read` views images
    already; on codex the `view_image` feature is disabled on every other
    invocation and is re-enabled for this one, and nothing else changes.

    `internet=True` is the science-error agent's variant (docs/specs/
    pipeline.md section 9): the WEB PAIR moves from the denied list into the
    built-in tools on either backend, and NOTHING ELSE changes -- the argv
    parity tests pin that the delta is exactly the web pair. Code execution
    is NOT part of this seam: it is the `run_python_script` MCP tool, and
    backend shells stay denied on every invocation this module builds.
    """
    if budget_usd is not None and not backend.supports_budget:
        raise BudgetUnsupported(
            f"{backend.name} has no spend cap; re-run without --budget-usd "
            f"or use --backend claude"
        )
    if backend.name == "claude":
        builtin = list(claude_builtin_tools or CLAUDE.builtin_tools)
        denied = denied_tools if denied_tools is not None \
            else list(claude_denied_tools or CLAUDE.denied_tools)
        if internet:
            builtin = builtin + [t for t in ("WebSearch", "WebFetch")
                                 if t not in builtin]
            denied = [t for t in denied if t not in ("WebSearch", "WebFetch")]
        return _build_claude_invocation(
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            model=model,
            effort=effort,
            json_schema=json_schema,
            budget_usd=budget_usd,
            mcp_config_json=mcp_config_json or "{}",
            denied_tools=denied,
            builtin_tools=builtin,
            max_turns=max_turns,
            forensic_mcp=forensic_mcp,
            permission_mode=permission_mode,
            env_overlay=env_overlay,
            settings_json=settings_json,
        )
    if permission_mode is not None or env_overlay or settings_json:
        raise ValueError(
            f"tool_access: skill is implemented for the claude backend only, not "
            f"{backend.name}: its shell fence is Claude's dontAsk permission mode")
    if backend.name == "grok":
        return _build_grok_invocation(
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            model=model,
            effort=effort,
            json_schema=json_schema,
            paper_dir=paper_dir,
            max_turns=max_turns,
            python_executable=python_executable,
            internet=internet,
            mcp_stage=mcp_stage,
            run_slug=run_slug,
            forensic_mcp=forensic_mcp,
            mcp_tools=mcp_tools,
        )
    if backend.name == "codex":
        return _build_codex_invocation(
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            model=model,
            effort=effort,
            json_schema=json_schema,
            paper_dir=paper_dir,
            max_turns=max_turns,
            python_executable=python_executable,
            internet=internet,
            mcp_stage=mcp_stage,
            run_slug=run_slug,
            forensic_mcp=forensic_mcp,
            vision=vision,
            mcp_tools=mcp_tools,
        )
    if backend.name == "antigravity":
        return _build_antigravity_invocation(
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            model=model,
            effort=effort,
            json_schema=json_schema,
            paper_dir=paper_dir,
            max_turns=max_turns,
            python_executable=python_executable,
            internet=internet,
            mcp_stage=mcp_stage,
            run_slug=run_slug,
            forensic_mcp=forensic_mcp,
            mcp_tools=mcp_tools,
        )
    if backend.name == "openrouter":
        return _build_openrouter_invocation(
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            model=model,
            effort=effort,
            json_schema=json_schema,
            mcp_config_json=mcp_config_json or "{}",
            paper_dir=paper_dir,
            max_turns=max_turns,
            python_executable=python_executable,
            internet=internet,
            forensic_mcp=forensic_mcp,
        )
    raise ValueError(f"no invocation builder for backend {backend.name!r}")


def _build_openrouter_invocation(
    *,
    system_prompt: str,
    allowed_tools: list[str],
    model: str,
    effort: str,
    json_schema: dict | None,
    mcp_config_json: str,
    paper_dir: str | Path | None,
    max_turns: int | None,
    python_executable: str | None,
    internet: bool = False,
    forensic_mcp: bool = True,
) -> Invocation:
    """`python -m ...openrouter_loop`. The system prompt and schema go in
    FILES (a prompt on argv is the 128 KB MAX_ARG_STRLEN crash); the user
    prompt goes down stdin, as on Claude. `Read` is offered only when the
    caller allowed it, confined to the paper directory by the loop."""
    import tempfile
    run_dir = Path(tempfile.mkdtemp(prefix="openrouter-"))
    system_path = run_dir / "system_prompt.md"
    system_path.write_text(system_prompt, encoding="utf-8")
    tools = list(allowed_tools)
    if "Read" not in tools:
        tools.append("Read")
    cmd = [
        python_executable or _default_python(), "-m", OPENROUTER_LOOP_MODULE,
        "--model", model,
        "--effort", effort,
        "--mcp-config", mcp_config_json if forensic_mcp else "{}",
        "--allowedTools", ",".join(tools),
        "--system-prompt-file", str(system_path),
    ]
    if json_schema is not None:
        schema_path = run_dir / "schema.json"
        schema_path.write_text(json.dumps(json_schema), encoding="utf-8")
        cmd += ["--json-schema-file", str(schema_path)]
    if max_turns is not None:
        cmd += ["--max-turns", str(max_turns)]
    if paper_dir:
        cmd += ["--paper-dir", str(paper_dir)]
    if internet:
        cmd += ["--internet"]

    def _cleanup() -> None:
        shutil.rmtree(run_dir, ignore_errors=True)

    return Invocation(
        argv=cmd,
        prompt_delivery="stdin",
        workdir=None,
        # The loop is itself `python -m metascience_agent...`: without this it
        # imports the toolkit through the editable `.pth`, not this tree.
        env_overlay={"PYTHONPATH": forensic_pythonpath()},
        cleanup=_cleanup,
        backend=OPENROUTER,
        forensic_mcp=forensic_mcp and _claude_declares_forensic(mcp_config_json),
        allowed_tools=tuple(allowed_tools),
    )


def _claude_declares_forensic(mcp_config_json: str | None) -> bool:
    """Whether a Claude launch actually asked for the forensic server.

    Claude image screening passes `--mcp-config {}` with `--strict-mcp-config`,
    which declares nothing -- so the init event lists no servers and the
    presence check would abort exactly as it did on Grok.

    The CONFIG is the authority, not only the caller's intent: a launch that
    asked for the server and wrote no config did not get one, and stamping
    that launch `forensic_mcp=True` is what makes the gate abort on a server
    nobody ever configured. The stamp is the AND of the two.
    """
    if not mcp_config_json:
        return False
    try:
        parsed = json.loads(mcp_config_json)
    except (TypeError, ValueError):
        return True  # unparseable: assume a server was intended, fail closed
    servers = (parsed or {}).get("mcpServers") or (parsed or {}).get("mcp_servers") or {}
    return bool(servers)


def _build_claude_invocation(
    *,
    system_prompt: str,
    allowed_tools: list[str],
    model: str,
    effort: str,
    json_schema: dict | None,
    budget_usd: float | None,
    mcp_config_json: str,
    denied_tools: list[str],
    builtin_tools: list[str],
    max_turns: int | None,
    forensic_mcp: bool = True,
    permission_mode: str | None = None,
    env_overlay: dict[str, str] | None = None,
    settings_json: str | None = None,
) -> Invocation:
    # FLAG ORDER IS LOAD-BEARING FOR THE BYTE-IDENTICAL PIN. Do not "clean up".
    cmd = [
        "claude",
        "-p",
        "--model", model,
        "--effort", effort,
        "--mcp-config", mcp_config_json,
        "--strict-mcp-config",
        "--allowedTools", ",".join(allowed_tools),
        "--tools", ",".join(builtin_tools),
        "--disallowedTools", " ".join(denied_tools),
        "--append-system-prompt", system_prompt,
        "--permission-mode", permission_mode or "bypassPermissions",
        "--output-format", "stream-json",
        "--verbose",
    ]
    if json_schema is not None:
        cmd += ["--json-schema", json.dumps(json_schema)]
    if budget_usd is not None:
        cmd += ["--max-budget-usd", str(budget_usd)]
    if max_turns is not None:
        cmd += ["--max-turns", str(max_turns)]
    if settings_json is not None:
        cmd += ["--settings", settings_json]
    return Invocation(
        argv=cmd,
        prompt_delivery="stdin",
        workdir=None,
        env_overlay=dict(env_overlay or {}),
        cleanup=lambda: None,
        backend=CLAUDE,
        forensic_mcp=forensic_mcp and _claude_declares_forensic(mcp_config_json),
        allowed_tools=tuple(allowed_tools),
    )


def _build_grok_invocation(
    *,
    system_prompt: str,
    allowed_tools: list[str],
    model: str,
    effort: str,
    json_schema: dict | None,
    paper_dir: str | Path | None,
    max_turns: int | None,
    python_executable: str | None,
    internet: bool = False,
    mcp_stage: str | None = None,
    run_slug: str | None = None,
    forensic_mcp: bool = True,
    mcp_tools: list[str] | None = None,
) -> Invocation:
    run_dir = _create_grok_sandbox(
        python_executable=python_executable or _default_python(),
        paper_dir=paper_dir,
        mcp_stage=mcp_stage,
        run_slug=run_slug,
        mcp_tools=mcp_tools,
        forensic_mcp=forensic_mcp,
    )
    prompt_path = run_dir / "prompt.txt"
    # Written later by `_run_stage` so `_build_claude_cmd` never takes a
    # `prompt` parameter (tests pin that absence -- a prompt on argv is the
    # 128 KB crash).
    prompt_path.write_text("", encoding="utf-8")

    builtin = list(GROK.builtin_tools)
    denied = list(GROK.denied_tools)
    if internet:
        builtin += [t for t in ("web_search", "web_fetch") if t not in builtin]
        denied = [t for t in denied if t not in ("web_search", "web_fetch")]
    cmd: list[str] = [
        "grok",
        "--prompt-file", str(prompt_path),
        "--cwd", str(run_dir),
        "--model", model,
        "--effort", effort,
        "--tools", ",".join(builtin),
        "--disallowed-tools", ",".join(denied),
    ]
    for rule in (grok_deny_rules(list(allowed_tools)) if forensic_mcp else []):
        cmd += ["--deny", rule]
    cmd += [
        "--verbatim",
        "--append-system-prompt", system_prompt,
        "--permission-mode", "bypassPermissions",
        "--output-format", "streaming-messages-json",
    ]
    if json_schema is not None:
        cmd += ["--json-schema", json.dumps(json_schema)]
    if max_turns is not None:
        cmd += ["--max-turns", str(max_turns)]

    def _cleanup() -> None:
        shutil.rmtree(run_dir, ignore_errors=True)

    return Invocation(
        argv=cmd,
        prompt_delivery="prompt_file",
        workdir=run_dir,
        env_overlay={
            "GROK_MAX_MCP_OUTPUT_BYTES": GROK_MCP_OUTPUT_BYTES,
            "GROK_CLAUDE_MCPS_ENABLED": "false",
            "GROK_CURSOR_MCPS_ENABLED": "false",
            **GROK_FOLDER_TRUST_ENV,
            # Skills from ~/.claude and ~/.cursor still inject into a
            # forensic sweep (40+ unrelated packages on 2026-08-20). They
            # are not why an empty dump happens — siblings tool-call with
            # them present — but they are prompt pollution on every Grok
            # review. Bundled Grok skills still load; do not switch to
            # --system-prompt-override here.
            "GROK_CLAUDE_SKILLS_ENABLED": "false",
            "GROK_CURSOR_SKILLS_ENABLED": "false",
        },
        cleanup=_cleanup,
        backend=GROK,
        forensic_mcp=forensic_mcp,
        prompt_path=prompt_path,
        allowed_tools=tuple(allowed_tools),
    )


def _allows_null(schema) -> bool:
    if not isinstance(schema, dict):
        return False
    t = schema.get("type")
    if t == "null" or (isinstance(t, list) and "null" in t):
        return True
    for comb in ("anyOf", "oneOf"):
        if any(_allows_null(s) for s in schema.get(comb) or []):
            return True
    return False


def codex_strict_schema(schema: dict) -> dict:
    """Rewrite a JSON schema into the OpenAI strict-mode dialect codex sends.

    `codex exec --output-schema` forwards the schema to the API's strict
    structured-output validator, which REJECTS our schemas as-is (measured
    2026-09-01, both failure classes): every object must carry
    `additionalProperties: false`, and `required` must list EVERY key. Two
    rewrites make the same contract expressible:

    * A FREE-FORM object (no `properties` -- our `inputs`/`reported`/
      `computed`/`values` fields) cannot exist in strict mode at all; it
      becomes a STRING carrying serialized JSON. `restore_from_strict`
      parses it back after the run, so downstream consumers see the same
      dict they get from a Claude run.
    * A formerly-OPTIONAL property becomes required-but-nullable
      (`anyOf: [original, null]`); `restore_from_strict` drops those
      stand-in nulls, so an absent field stays absent downstream rather
      than arriving as None.
    * A bare `const` gains the `type` its value implies. Draft-07 lets a
      constant stand alone; the strict validator refuses it ("In
      context=('properties', 'schema_version'), schema must have a 'type'
      key"), and that is exactly what the IMAGE ADJUDICATION schema is --
      so on codex the whole stage died with exit 1, an empty stderr and a
      400 buried in its stdout stream. MEASURED 2026-09-02. Four shipped
      schemas carry such a const (image/cross-paper adjudication, image and
      text track); the two-stage findings schemas do not, which is why this
      only surfaced when the adjudicator was pointed at codex. A bare `enum`
      is treated the same way when its values share one JSON type.

    The transform is applied only on the codex path; the schema every other
    backend sends is byte-identical to before.
    """
    return _strict_node(schema)


def _json_type_of(value) -> str:
    """The JSON Schema `type` a literal implies. `bool` before `int`: in
    Python True is an int, and a schema that called a boolean "integer"
    would be rejected for a different reason."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "null"


def _strict_node(node):
    if isinstance(node, list):
        return [_strict_node(x) for x in node]
    if not isinstance(node, dict):
        return node
    node = dict(node)
    if "type" not in node:
        # A bare `const`, or a bare `enum` whose values are all one JSON
        # type, gains that type. Draft-07 allows both to stand alone.
        if "const" in node:
            node["type"] = _json_type_of(node["const"])
        elif isinstance(node.get("enum"), list) and node["enum"]:
            kinds = {_json_type_of(v) for v in node["enum"] if v is not None}
            if len(kinds) == 1:
                node["type"] = kinds.pop()
                if any(v is None for v in node["enum"]):
                    node["type"] = [node["type"], "null"]
    for comb in ("anyOf", "oneOf", "allOf"):
        if isinstance(node.get(comb), list):
            node[comb] = [_strict_node(x) for x in node[comb]]
    if isinstance(node.get("items"), dict):
        node["items"] = _strict_node(node["items"])
    for defs_key in ("$defs", "definitions"):
        if isinstance(node.get(defs_key), dict):
            node[defs_key] = {k: _strict_node(v)
                              for k, v in node[defs_key].items()}
    if node.get("type") == "object" or "properties" in node:
        props = node.get("properties")
        if not props:
            desc = str(node.get("description") or "").strip()
            return {
                "type": "string",
                "description": ((desc + " -- ") if desc else "")
                + "a JSON OBJECT serialized as a string; emit valid JSON, "
                  "e.g. \"{\\\"mean\\\": 3.53}\"",
            }
        required = set(node.get("required") or [])
        new_props = {}
        for key, sub in props.items():
            sub = _strict_node(sub)
            if key not in required and not _allows_null(sub):
                sub = {"anyOf": [sub, {"type": "null"}]}
            new_props[key] = sub
        node["properties"] = new_props
        node["required"] = list(props.keys())
        node["additionalProperties"] = False
    return node


def restore_from_strict(data, schema):
    """Undo `codex_strict_schema` on PARSED output, guided by the ORIGINAL
    schema: JSON-string stand-ins for free-form objects are parsed back to
    dicts, and nulls in formerly-optional slots are dropped (they mean
    "absent", which is what every other backend delivers). Best-effort by
    contract -- a shape the schema does not describe passes through as-is.
    """
    if not isinstance(schema, dict):
        return data
    if schema.get("type") == "object" or "properties" in schema:
        props = schema.get("properties")
        if not props:
            if isinstance(data, str):
                try:
                    parsed = json.loads(data)
                except json.JSONDecodeError:
                    return data
                return parsed if isinstance(parsed, dict) else data
            return data
        if not isinstance(data, dict):
            return data
        required = set(schema.get("required") or [])
        out = {}
        for key, value in data.items():
            sub = props.get(key)
            if (value is None and key not in required
                    and isinstance(sub, dict) and not _allows_null(sub)):
                continue
            out[key] = restore_from_strict(value, sub) if sub else value
        return out
    if isinstance(schema.get("items"), dict) and isinstance(data, list):
        return [restore_from_strict(x, schema["items"]) for x in data]
    return data


def codex_enabled_tools(allowed_tools: list[str]) -> list[str]:
    """Short names for `mcp_servers.<id>.enabled_tools` -- a true allowlist.

    Codex is the one backend with per-server tool NARROWING at discovery
    time (Grok's `--allow` only auto-approves, hence its deny complement).
    Derived from the stage's allowed `mcp__forensic_metascience__*` names,
    never a hand list. The env-var stage fence (`METASCIENCE_MCP_STAGE`)
    stays the enforced layer; this narrows what the model even sees.
    """
    return sorted(
        t[len(MCP_TOOL_PREFIX):]
        for t in allowed_tools
        if isinstance(t, str) and t.startswith(MCP_TOOL_PREFIX)
    )


def _build_codex_invocation(
    *,
    system_prompt: str,
    allowed_tools: list[str],
    model: str,
    effort: str,
    json_schema: dict | None,
    paper_dir: str | Path | None,
    max_turns: int | None,
    python_executable: str | None,
    internet: bool = False,
    mcp_stage: str | None = None,
    run_slug: str | None = None,
    vision: bool = False,
    forensic_mcp: bool = True,
    mcp_tools: list[str] | None = None,
) -> Invocation:
    run_dir = _create_codex_sandbox(
        system_prompt=system_prompt,
        json_schema=json_schema,
    )
    python_executable = python_executable or _default_python()

    env = {"PYTHONPATH": forensic_pythonpath()}
    if paper_dir:
        env[PAPER_DIR_ENV] = str(paper_dir)
    if mcp_stage:
        # The per-role fence, same channel and same measured incident as the
        # Grok flavor (see `_create_grok_sandbox`): the server registers only
        # this role's tools, whatever the discovery layer shows.
        env["METASCIENCE_MCP_STAGE"] = str(mcp_stage)
    if run_slug:
        env["METASCIENCE_RUN_SLUG"] = str(run_slug)
    if mcp_tools is not None:
        # A pipeline's toolset, narrowing the role's surface (fail-closed in
        # the server; see `mcp_server._manifest_tools`). Empty is refused
        # here rather than written as an empty, absent-looking value.
        if not mcp_tools:
            raise ValueError("empty tool manifest")
        env["METASCIENCE_MCP_TOOLS"] = ",".join(mcp_tools)
    env_inline = ", ".join(f"{k} = {_toml_str(v)}" for k, v in env.items())

    enabled = codex_enabled_tools(list(allowed_tools))
    enabled_inline = ", ".join(_toml_str(n) for n in enabled)

    if internet:
        # The science agent's variant: full web tool. The delta from the
        # no-internet invocation is EXACTLY this one -c value (argv parity
        # tests pin that); shells stay read-only on every invocation.
        web_search_cfg = "tools.web_search=true"
    else:
        web_search_cfg = (
            "tools.web_search={ enabled = false, allowed_domains = ["
            + _toml_str(CODEX_NO_INTERNET_DOMAIN)
            + "] }"
        )

    srv = f"mcp_servers.{FORENSIC_SERVER}"
    cmd: list[str] = [
        "codex", "exec",
        "--json",
        # Never load ~/.codex/config.toml (auth stays in CODEX_HOME); never
        # persist session files; never require a git repo in the sandbox.
        "--ignore-user-config",
        "--skip-git-repo-check",
        "--ephemeral",
        "-C", str(run_dir),
        "-s", "read-only",
        "-m", model,
        "-c", f"model_reasoning_effort={_toml_str(effort)}",
        "-c", 'approval_policy="never"',
        "-c", f"project_doc_max_bytes={CODEX_PROJECT_DOC_MAX_BYTES}",
        "-c", f"tool_output_token_limit={CODEX_TOOL_OUTPUT_TOKEN_LIMIT}",
        "-c", web_search_cfg,
        "-c", CODEX_SKILLS_CONFIG,
    ]
    for feature in CODEX_DISABLED_FEATURES:
        if vision and feature == "view_image":
            # The image adjudicator's one exception: it must open the
            # exhibits, and a clear made unseen is demoted in code.
            continue
        cmd += ["--disable", feature]
    if forensic_mcp:
        cmd += [
            "-c", f"{srv}.command={_toml_str(python_executable)}",
            "-c", f"{srv}.args=[{_toml_str('-m')}, {_toml_str(_forensic_mcp_module())}]",
            "-c", f"{srv}.env={{ {env_inline} }}",
            "-c", f"{srv}.enabled_tools=[{enabled_inline}]",
            # Without this, every MCP call fails under approval_policy="never"
            # -- and the measured failure mode is the model INVENTING the
            # tool's verdict afterwards, not reporting the error.
            "-c", f'{srv}.default_tools_approval_mode="approve"',
            "-c", f"{srv}.startup_timeout_sec=60",
            "-c", f"{srv}.tool_timeout_sec=600",
        ]
    if json_schema is not None:
        # A schema FILE, not an inline string (codex has no inline form).
        # Written by `_create_codex_sandbox` -- in the STRICT dialect, see
        # `codex_strict_schema`; a missing/invalid file fails fast with exit
        # 1 and a stderr sentence, before any spend.
        cmd += [
            "--output-schema", str(run_dir / "schema.json"),
            "-o", str(run_dir / "last_message.txt"),
        ]
    # Explicit stdin sentinel: the prompt NEVER goes on argv (128 KB
    # MAX_ARG_STRLEN), and `-` makes the stdin contract unambiguous.
    cmd += ["-"]

    def _cleanup() -> None:
        shutil.rmtree(run_dir, ignore_errors=True)

    return Invocation(
        argv=cmd,
        prompt_delivery="stdin",
        workdir=run_dir,
        env_overlay={},  # CODEX_HOME untouched: auth lives there.
        cleanup=_cleanup,
        backend=CODEX,
        forensic_mcp=forensic_mcp,
        allowed_tools=tuple(allowed_tools),
        max_turns_unsupported=max_turns is not None,
        expects_schema=json_schema is not None,
        restore_schema=json_schema,
    )


def _create_codex_sandbox(
    *, system_prompt: str, json_schema: dict | None,
) -> Path:
    root = codex_sandbox_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BackendSandboxError(
            f"could not create Codex sandbox root {root}: {exc}"
        ) from exc
    run_dir = root / f"run-{uuid.uuid4()}"
    try:
        run_dir.mkdir(parents=True)
    except OSError as exc:
        raise BackendSandboxError(
            f"could not create Codex run dir {run_dir}: {exc}"
        ) from exc
    # The system prompt travels as the project doc: codex has no
    # --append-system-prompt, and `-c developer_instructions=...` would put
    # tens of KB on argv (the MAX_ARG_STRLEN crash). `model_instructions_file`
    # is rejected for the same reason Grok's --system-prompt-override was: it
    # REPLACES the CLI's own base instructions instead of adding ours.
    (run_dir / "AGENTS.md").write_text(system_prompt, encoding="utf-8")
    if json_schema is not None:
        (run_dir / "schema.json").write_text(
            json.dumps(codex_strict_schema(json_schema)), encoding="utf-8"
        )
    return run_dir


def _build_antigravity_invocation(
    *,
    system_prompt: str,
    allowed_tools: list[str],
    model: str,
    effort: str,
    json_schema: dict | None,
    paper_dir: str | Path | None,
    max_turns: int | None,
    python_executable: str | None,
    internet: bool = False,
    mcp_stage: str | None = None,
    run_slug: str | None = None,
    forensic_mcp: bool = True,
    mcp_tools: list[str] | None = None,
) -> Invocation:
    """`agy` under a per-run config HOME. See the module docstring for why
    each piece lives where it does; `_create_antigravity_sandbox` writes them.
    The prompt goes down stdin as one stream-json `user` event (the runtime
    wraps it, `prompt_delivery="stdin_stream_json"`), never on argv."""
    route = antigravity_route_note()
    if route:
        system_prompt = f"{system_prompt}\n\n---\n\n{route}"
    run_dir, home, ws = _create_antigravity_sandbox(
        system_prompt=system_prompt,
        allowed_tools=list(allowed_tools),
        json_schema=json_schema,
        paper_dir=paper_dir,
        python_executable=python_executable or _default_python(),
        internet=internet,
        mcp_stage=mcp_stage,
        run_slug=run_slug,
        forensic_mcp=forensic_mcp,
        mcp_tools=mcp_tools,
    )
    cmd: list[str] = [
        "agy",
        # `-p` takes the prompt as its value; empty, with the turn read from
        # stdin under `--input-format stream-json` (measured).
        "--print=",
        "--agent", ANTIGRAVITY_AGENT,
        *antigravity_model_args(model, effort),
        "--input-format", "stream-json",
        "--output-format", "stream-json",
        # A prompt line that happens to start with "/" must not run a command.
        "--disable-slash-commands",
    ]
    if paper_dir:
        # Workspace reads are auto-allowed; a read outside the workspace is
        # soft-denied in print mode (measured: `denied_actions: read_file`).
        cmd += ["--add-dir", str(paper_dir)]
    if json_schema is not None:
        cmd += ["--json-schema", str(run_dir / "schema.json")]
    env_overlay = {
        # The whole isolation story: agy reads ~/.gemini under this HOME,
        # never the operator's. Auth is in the OS keyring, not HOME.
        "HOME": str(home),
        # The self-updater must not swap the binary under a batch.
        "AGY_CLI_DISABLE_AUTO_UPDATE": "true",
    }
    state = {
        "argv": list(cmd), "run_dir": run_dir, "home": home, "ws": ws,
        "env": dict(env_overlay), "model": model,
        "allowed_tools": tuple(allowed_tools), "forensic_mcp": forensic_mcp,
        "expects_schema": json_schema is not None,
        "conversation_id": None, "keep": False,
        "max_turns_unsupported": max_turns is not None,
    }
    return _antigravity_invocation(state)


#: Run dirs kept for a resume, by conversation id. Removed by the resumed
#: invocation's cleanup, or at interpreter exit if no resume ever came.
_ANTIGRAVITY_RESUMABLE: dict[str, dict] = {}


def _antigravity_invocation(state: dict, extra_argv: list[str] | None = None
                            ) -> Invocation:
    """One agy launch over `state`'s sandbox. Its cleanup removes the run dir
    UNLESS the turn ended without `finish` (`state["keep"]`, set by the
    normalizer), in which case the dir is registered for a resume."""
    run_dir = state["run_dir"]

    def _cleanup() -> None:
        cid = state.get("conversation_id")
        if state.get("keep") and cid:
            _ANTIGRAVITY_RESUMABLE[cid] = state
            return
        if cid:
            _ANTIGRAVITY_RESUMABLE.pop(cid, None)
        shutil.rmtree(run_dir, ignore_errors=True)

    return Invocation(
        argv=list(state["argv"]) + list(extra_argv or []),
        prompt_delivery="stdin_stream_json",
        workdir=state["ws"],
        env_overlay=dict(state["env"]),
        cleanup=_cleanup,
        backend=ANTIGRAVITY,
        forensic_mcp=state["forensic_mcp"],
        allowed_tools=tuple(state["allowed_tools"]),
        max_turns_unsupported=state.get("max_turns_unsupported", False),
        expects_schema=state["expects_schema"],
        model=state["model"],
        config_home=state["home"],
        resume_state=state,
    )


def antigravity_resume_invocation(stage: dict | None) -> Invocation | None:
    """The invocation that RESUMES the conversation a stage left unfinished,
    or None when there is none to resume.

    MEASURED 2026-10-18 (apple_cider, gemini-3.8-flash-medium): the tools
    agent declared five tables, ran statcheck, and ended its turn without
    `finish` -- before running a single check. The schema-gate retry was a
    fresh session (or a tool-less recovery call) that could only describe
    the setup it had been told about. `--conversation <id>` under the SAME
    HOME continues the model's own context, tools and all (measured: a
    resumed turn recalled a number given only in the first)."""
    cid = stage_resumable_conversation(stage)
    state = _ANTIGRAVITY_RESUMABLE.get(cid) if cid else None
    if state is None or not Path(state["run_dir"]).is_dir():
        return None
    state["keep"] = False
    return _antigravity_invocation(state, ["--conversation", cid])


def stage_resumable_conversation(stage: dict | None) -> str | None:
    """The agy conversation id a stage's final `result` event marked for
    resume (`agy_resume`), read from the stage's own transcript."""
    if not isinstance(stage, dict):
        return None
    for event in reversed(stage.get("messages") or []):
        if isinstance(event, dict) and event.get("type") == "result":
            return ((event.get("agy_resume") or {}).get("conversation_id")
                    or None)
    return None


def antigravity_resume_prompt() -> str:
    """`core/prompts/antigravity_resume.md`, the message a resumed turn gets."""
    path = Path(__file__).resolve().parent / "core" / "prompts" / "antigravity_resume.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def merge_resumed_stage(first: dict, resumed: dict) -> dict:
    """The resumed stage, carrying the whole conversation's transcript.

    The resumed stream starts where the first stopped (step numbering
    continues, nothing is replayed -- measured), so the archive is the first
    attempt's events (minus its failed `result`) followed by the
    continuation's; tool counts and wall time add up. Token usage is per
    process, not cumulative (measured), so the resumed figures stand alone
    and the first attempt's are recorded separately by its own spend row."""
    merged = dict(resumed)
    head = [e for e in (first.get("messages") or [])
            if not (isinstance(e, dict) and e.get("type") == "result")]
    merged["messages"] = head + list(resumed.get("messages") or [])
    merged["tool_calls"] = int(first.get("tool_calls") or 0) + int(
        resumed.get("tool_calls") or 0)
    merged["resumed_from_conversation"] = stage_resumable_conversation(first)
    return merged


def _discard_retained_antigravity_runs() -> None:
    for state in list(_ANTIGRAVITY_RESUMABLE.values()):
        shutil.rmtree(state["run_dir"], ignore_errors=True)
    _ANTIGRAVITY_RESUMABLE.clear()


import atexit as _atexit  # noqa: E402 -- registered beside what it cleans
_atexit.register(_discard_retained_antigravity_runs)


def antigravity_route_note() -> str:
    """`core/prompts/antigravity_route.md`: how forensic tools are called and
    that the answer counts only through `finish` (the model was measured
    ending a schema-bearing turn without it, 2026-10-18). Read from the file,
    never written here; empty when this install does not ship it."""
    path = Path(__file__).resolve().parent / "core" / "prompts" / "antigravity_route.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _create_antigravity_sandbox(
    *, system_prompt: str, allowed_tools: list[str], json_schema: dict | None,
    paper_dir: str | Path | None, python_executable: str, internet: bool,
    mcp_stage: str | None, run_slug: str | None, forensic_mcp: bool,
    mcp_tools: list[str] | None,
) -> tuple[Path, Path, Path]:
    root = antigravity_sandbox_root()
    run_dir = root / f"run-{uuid.uuid4()}"
    home, ws = run_dir / "home", run_dir / "ws"
    config = home / ".gemini" / "config"
    cli_dir = home / ".gemini" / "antigravity-cli"
    try:
        for d in (ws, config / "agents", cli_dir / "cache"):
            d.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BackendSandboxError(
            f"could not create Antigravity run dir {run_dir}: {exc}") from exc

    real_home = Path.home()
    # Skip first-run onboarding in the fresh HOME. Best-effort: absent files
    # mean agy was never run interactively here, and the login it needs is in
    # the keyring either way.
    for rel in ("antigravity-cli/cache/onboarding.json",
                "antigravity-cli/jetski_state.pbtxt"):
        src = real_home / ".gemini" / rel
        if src.is_file():
            try:
                shutil.copyfile(src, home / ".gemini" / rel)
            except OSError:
                pass

    servers: dict = {}
    if forensic_mcp:
        env = {
            "PYTHONPATH": forensic_pythonpath(),
            # The server inherits agy's environment, whose HOME is the
            # sandbox; receipts (~/.cache/metascience/receipts) and every
            # other cache would land in a directory deleted after the stage.
            "HOME": str(real_home),
        }
        if paper_dir:
            env[PAPER_DIR_ENV] = str(paper_dir)
        if mcp_stage:
            # The per-role fence, same channel as the Grok and Codex flavors.
            env["METASCIENCE_MCP_STAGE"] = str(mcp_stage)
        if run_slug:
            env["METASCIENCE_RUN_SLUG"] = str(run_slug)
        if mcp_tools is not None:
            if not mcp_tools:
                raise ValueError("empty tool manifest")
            env["METASCIENCE_MCP_TOOLS"] = ",".join(mcp_tools)
        servers[FORENSIC_SERVER] = {
            "command": python_executable,
            "args": ["-m", _forensic_mcp_module()],
            "env": env,
            # Narrows what the model sees; the stage env above is the
            # enforced layer, as on Codex.
            "enabledTools": codex_enabled_tools(allowed_tools),
            "timeoutSeconds": 600,
        }
    (config / "mcp_config.json").write_text(
        json.dumps({"mcpServers": servers}, indent=2), encoding="utf-8")

    allow = [f"mcp({FORENSIC_SERVER}/*)"] if forensic_mcp else []
    deny = list(ANTIGRAVITY_DENY_RULES)
    if internet:
        allow.append("read_url(*)")
        deny = [r for r in deny if r != "read_url(*)"]
    trusted = [str(ws)] + ([str(paper_dir)] if paper_dir else [])
    (cli_dir / "settings.json").write_text(json.dumps({
        "trustedWorkspaces": trusted,
        "permissions": {"allow": allow, "deny": deny},
    }, indent=2), encoding="utf-8")

    tools = list(ANTIGRAVITY_BUILTIN_TOOLS)
    if internet:
        tools += list(ANTIGRAVITY_WEB_TOOLS)
    frontmatter = "\n".join([
        "---",
        f"name: {ANTIGRAVITY_AGENT}",
        "description: Forensic metascience analyst",
        "mainAgent: true",
        # Nothing of the operator's: skills, rules, plugins, subagents.
        "inheritCustomizations: false",
        # No default prompt sections and no default tools -- `tools:` below
        # is then a true allowlist (measured: 8 tools, no shell, no browser).
        "excludeDefaultComponents: true",
        f"enable_mcp_tools: {'true' if forensic_mcp else 'false'}",
        "tools:",
        *[f"  - {t}" for t in tools],
        "---",
        "",
    ])
    (config / "agents" / f"{ANTIGRAVITY_AGENT}.md").write_text(
        frontmatter + system_prompt, encoding="utf-8")
    if json_schema is not None:
        (run_dir / "schema.json").write_text(
            json.dumps(json_schema), encoding="utf-8")
    return run_dir, home, ws


def antigravity_config_isolation_row() -> tuple[str, bool, str]:
    """Preflight row: the operator's agy config can never leak into a run.

    Structural, like Codex's: every invocation runs under its own HOME, so
    ~/.gemini (MCP servers, rules, skills, permissions) is never read. The
    peek at ~/.gemini/config/mcp_config.json only NAMES what is configured
    there, for the operator's context; it never fails the row.
    """
    if shutil.which(ANTIGRAVITY.binary) is None:
        return ("antigravity config isolation", False,
                "agy not on PATH; not probed")
    detail = "operator's ~/.gemini is never read: per-run HOME on every invocation"
    try:
        path = Path.home() / ".gemini" / "config" / "mcp_config.json"
        text = path.read_text(encoding="utf-8").strip() if path.is_file() else ""
        names = _enabled_mcp_names(json.loads(text)) if text else []
        foreign = [n for n in names if n != FORENSIC_SERVER]
        if foreign:
            detail += ("; operator config declares MCP server(s) "
                       + ", ".join(foreign) + " -- they cannot load into a forensic run")
    except (OSError, json.JSONDecodeError):
        pass  # JSONC or unreadable: the peek is context, not a gate
    return ("antigravity config isolation", True, detail)


def _default_python() -> str:
    import sys
    return sys.executable


def _forensic_mcp_module() -> str:
    """The forensic MCP server module, from the host hook. The server is the
    HOST's; a standalone install has none, and naming the host's module here
    produced 'No module named metascience_agent' from inside a stage instead
    of a refusal before it."""
    from . import integration
    module = integration.forensic_mcp_module
    if not module:
        raise MCPUnavailable(
            "no forensic MCP server is configured: the forensic tools belong to the "
            "host package (metascience_agent), which has not registered "
            "integration.forensic_mcp_module in this process")
    return module


def _pkg_root() -> Path:
    # llm_backend.py lives in src/metascience_agent/; PYTHONPATH is src/.
    from .integration import forensic_source_root
    return forensic_source_root or Path(__file__).resolve().parent.parent


def forensic_source_roots() -> list[Path]:
    """The source roots of THIS tree: `<root>/src` and, when it is beside it,
    `<root>/copy_paste_detector/src`.

    A child process that gets only `<root>/src` resolves `copy_paste_detector`
    through the editable install's `.pth`, i.e. whatever the SHARED checkout
    holds at that moment. MEASURED 2026-10-18: a pinned worktree run at
    1.83.0 lost every tools agent on both backends (`MCPUnavailable`) when a
    peer changed `copy_paste_detector` on main mid-day -- the server died on
    `cannot import name '_compat' from 'copy_paste_detector'
    (.../Dropbox/.../copy_paste_detector/src/...)`. A non-editable install has
    no sibling `copy_paste_detector/src`, and the package is then in
    site-packages beside this one, so only the first root is returned."""
    src = _pkg_root()
    roots = [src]
    detector = src.parent / "copy_paste_detector" / "src"
    if (detector / "copy_paste_detector").is_dir():
        roots.append(detector)
    return roots


def forensic_pythonpath(inherited: str | None = None) -> str:
    """PYTHONPATH for every child that imports the toolkit (the forensic MCP
    server, `metascience tool run`, the OpenRouter loop): this tree's roots
    FIRST, then the caller's own entries (`inherited`, default the current
    `PYTHONPATH`) that are not already listed -- e.g. the image package's
    `src` in a worktree run. Ours lead because a caller entry that shadowed
    them would recreate the mixed-tree import this exists to stop; a caller
    who wants different toolkit code already got it, since `_pkg_root` is
    wherever THIS process imported the toolkit from."""
    if inherited is None:
        inherited = os.environ.get("PYTHONPATH", "")
    entries = [str(r) for r in forensic_source_roots()]
    seen = {os.path.normcase(os.path.abspath(e)) for e in entries}
    for entry in inherited.split(os.pathsep):
        if not entry:   # an empty entry means the cwd: never inherit that
            continue
        key = os.path.normcase(os.path.abspath(entry))
        if key not in seen:
            seen.add(key)
            entries.append(entry)
    return os.pathsep.join(entries)


def _toml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _create_grok_sandbox(
    *, python_executable: str, paper_dir: str | Path | None,
    mcp_stage: str | None = None, run_slug: str | None = None,
    forensic_mcp: bool = True, mcp_tools: list[str] | None = None,
) -> Path:
    root = sandbox_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BackendSandboxError(
            f"could not create Grok sandbox root {root}: {exc}"
        ) from exc
    _ensure_sandbox_root_trusted(root)
    run_dir = root / f"run-{uuid.uuid4()}"
    grok_dir = run_dir / ".grok"
    try:
        grok_dir.mkdir(parents=True)
    except OSError as exc:
        raise BackendSandboxError(
            f"could not create Grok run dir {run_dir}: {exc}"
        ) from exc
    env = {"PYTHONPATH": forensic_pythonpath()}
    if paper_dir:
        env[PAPER_DIR_ENV] = str(paper_dir)
    if mcp_stage:
        # The per-role fence, Grok flavor. MEASURED 2026-08-21 on the first
        # live Grok parallel run: the CLAUDE path's stage-filtered server
        # held (0 off-list calls in 39), while THIS config omitted the
        # stage and the science agent executed check_estimate_ci and
        # grim_check off-role through use_tool. Same server, same env
        # channel, both routes fenced.
        env["METASCIENCE_MCP_STAGE"] = str(mcp_stage)
    if run_slug:
        # Same channel as the Claude route's `--mcp-config` env block: which
        # run these persisted scripts belong to, so two runs sharing a paper
        # directory do not share one `analysis_code/`.
        env["METASCIENCE_RUN_SLUG"] = str(run_slug)
    if mcp_tools is not None:
        # A pipeline's toolset, narrowing the role's surface (fail-closed in
        # the server; see `mcp_server._manifest_tools`). Empty is refused
        # here rather than written as an empty, absent-looking value.
        if not mcp_tools:
            raise ValueError("empty tool manifest")
        env["METASCIENCE_MCP_TOOLS"] = ",".join(mcp_tools)
    env_inline = ", ".join(
        f"{k} = {_toml_str(v)}" for k, v in env.items()
    )
    # Built only when the forensic server is wanted: image screening runs
    # without it, and must not need a host to name one.
    config = (
        f"[mcp]\n"
        f"max_output_bytes = {int(GROK_MCP_OUTPUT_BYTES)}\n"
        f"\n"
        f"[mcp_servers.{FORENSIC_SERVER}]\n"
        f"command = {_toml_str(python_executable)}\n"
        f"args = [{_toml_str('-m')}, {_toml_str(_forensic_mcp_module())}]\n"
        f"env = {{ {env_inline} }}\n"
        f"enabled = true\n"
        f"startup_timeout_sec = 60\n"
    ) if forensic_mcp else "[mcp]\n"
    (grok_dir / "config.toml").write_text(config, encoding="utf-8")
    return run_dir


def _ensure_sandbox_root_trusted(root: Path) -> None:
    """One entry in the Grok trust store, ever, for this root.

    Under grok 1.0.5 trust cascaded to `run-<uuid>/` subdirectories; under
    1.0.13 it covers only subdirectories of the same git repository, which
    this root is not, so `GROK_FOLDER_TRUST_ENV` on the subprocess is what
    ungates the run dir now. The entry stays for the versions where it still
    matters. We write the store ourselves rather than calling `grok --trust`
    per paper, which is how a corpus would leak hundreds of dead entries.
    Overridable: tests set ``METASCIENCE_GROK_SKIP_FOLDER_TRUST=1`` so the
    suite never mutates the operator's `~/.grok/trusted_folders.toml`.
    """
    if os.environ.get("METASCIENCE_GROK_SKIP_FOLDER_TRUST") == "1":
        return
    root = root.resolve()
    trust_file = Path.home() / ".grok" / "trusted_folders.toml"
    marker = f'folders."{root}"'
    try:
        if trust_file.exists() and marker in trust_file.read_text(encoding="utf-8"):
            return
        trust_file.parent.mkdir(parents=True, exist_ok=True)
        block = (
            f'\n[{marker}]\n'
            f"trusted = true\n"
            f"decided_at = {int(time.time())}\n"
        )
        with trust_file.open("a", encoding="utf-8") as fh:
            fh.write(block)
    except OSError as exc:
        raise BackendSandboxError(
            f"could not record folder trust for {root} in {trust_file}: {exc}. "
            f"Trust that directory once (Grok will then accept project MCP "
            f"servers under it) or set METASCIENCE_GROK_SKIP_FOLDER_TRUST=1 "
            f"only if you already have."
        ) from exc


def _probe_mcp_doctor(sandbox: Path | None) -> None:
    if sandbox is None:
        raise MCPUnavailable(
            "Grok MCP liveness probe needs a sandbox cwd; none was provided"
        )
    grok = shutil.which("grok")
    if grok is None:
        raise MCPUnavailable("grok CLI is not on PATH; cannot probe MCP liveness")
    try:
        proc = subprocess.run(
            [grok, "mcp", "doctor", "--json"],
            cwd=str(sandbox),
            capture_output=True, text=True, timeout=90,
            env={
                **os.environ,
                "GROK_CLAUDE_MCPS_ENABLED": "false",
                "GROK_CURSOR_MCPS_ENABLED": "false",
                # Same switch the run itself gets; a probe that is gated
                # differently from the run it vouches for proves nothing.
                **GROK_FOLDER_TRUST_ENV,
            },
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise MCPUnavailable(f"grok mcp doctor failed to start: {exc}") from exc
    raw = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise MCPUnavailable(
            "grok mcp doctor did not return JSON "
            f"(exit {proc.returncode}): {raw[:400]}"
        ) from exc
    check_doctor_payload(data)


def check_doctor_payload(data: dict) -> None:
    """Pure parser, so tests can feed the on-disk fixtures without spawning grok.

    Requires `forensic_metascience` healthy, a non-zero tool count parsed from
    the check *label* ``"N tools discovered"`` (there is no numeric field),
    and no other server. Does not consult a `status` field.
    """
    if not isinstance(data, dict):
        raise MCPUnavailable(f"grok mcp doctor payload is not an object: {type(data).__name__}")
    servers = data.get("servers") or []
    if not isinstance(servers, list):
        raise MCPUnavailable("grok mcp doctor payload has no servers list")
    ours = [s for s in servers if isinstance(s, dict) and s.get("name") == FORENSIC_SERVER]
    others = [s for s in servers if isinstance(s, dict) and s.get("name") != FORENSIC_SERVER]
    if others:
        names = ", ".join(str(s.get("name")) for s in others)
        raise MCPUnavailable(
            f"Grok MCP isolation failed: other server(s) present in doctor "
            f"output: {names}. Remove them from ~/.grok/config.toml -- a "
            f"foreign MCP is reachable via search_tool from inside a "
            f"forensic sweep."
        )
    if not ours:
        raise MCPUnavailable(
            "forensic_metascience is not in `grok mcp doctor` output. The "
            "sandbox .grok/config.toml was not loaded (folder untrusted, or "
            "the run dir was not used as --cwd)."
        )
    server = ours[0]
    if not server.get("healthy"):
        labels = "; ".join(
            f"{c.get('label')}: {c.get('detail') or ('failed' if not c.get('passed') else 'ok')}"
            for c in (server.get("checks") or [])
            if isinstance(c, dict)
        )
        raise MCPUnavailable(
            "forensic_metascience is configured but not healthy: "
            + (labels or "doctor reported healthy=false")
        )
    n_tools = 0
    for check in server.get("checks") or []:
        if not isinstance(check, dict):
            continue
        match = _TOOLS_DISCOVERED_RE.search(str(check.get("label") or ""))
        if match and check.get("passed"):
            n_tools = int(match.group(1))
    if n_tools <= 0:
        raise MCPUnavailable(
            "forensic_metascience handshake succeeded but doctor reported "
            "0 tools discovered (the count lives only in the check label). "
            "A sweep would run with no forensic tools."
        )


def _probe_mcp_stdio(python_executable: str | None = None) -> None:
    """Codex pre-spend liveness: handshake our own MCP server over stdio.

    `codex doctor --json` cannot do this -- its mcp check validates config
    consistency without spawning anything (measured: durationMs=0). So we
    speak the protocol ourselves: initialize, initialized, tools/list, and
    require at least one tool. This proves the exact server process a codex
    invocation would spawn (same interpreter, same PYTHONPATH) starts and
    serves tools; the `ForensicToolsNeverRan` ledger gate remains the proof
    the MODEL could reach it.
    """
    import sys
    python_executable = python_executable or sys.executable
    requests = (
        json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "metascience-preflight", "version": "0"},
            },
        })
        + "\n"
        + json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
        + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list",
                      "params": {}})
        + "\n"
    )
    try:
        proc = subprocess.run(
            [python_executable, "-m", _forensic_mcp_module()],
            input=requests,
            capture_output=True, text=True, timeout=90,
            env={**os.environ, "PYTHONPATH": forensic_pythonpath()},
        )
    except subprocess.TimeoutExpired as exc:
        raise MCPUnavailable(
            "forensic MCP server did not answer the stdio handshake within "
            "90s; a codex stage would hang on startup"
        ) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise MCPUnavailable(
            f"forensic MCP server failed to start for the codex liveness "
            f"probe: {exc}"
        ) from exc
    n_tools = None
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(msg, dict) and msg.get("id") == 2:
            tools = ((msg.get("result") or {}).get("tools")
                     if isinstance(msg.get("result"), dict) else None)
            n_tools = len(tools) if isinstance(tools, list) else 0
    if n_tools is None:
        err = (proc.stderr or "").strip()[:400]
        raise MCPUnavailable(
            "forensic MCP server produced no tools/list response over stdio "
            f"(exit {proc.returncode})" + (f": {err}" if err else "")
        )
    if n_tools <= 0:
        raise MCPUnavailable(
            "forensic MCP server answered the handshake but listed 0 tools. "
            "A codex sweep would run with no forensic tools."
        )


def codex_config_isolation_row() -> tuple[str, bool, str]:
    """Preflight row: the user's Codex config can never leak into a run.

    Structural rather than probed: every invocation this module builds passes
    `--ignore-user-config`, so foreign MCP servers or settings in
    ~/.codex/config.toml cannot load (measured caveat: the `apps` feature
    injects its own tools regardless, which is why CODEX_DISABLED_FEATURES
    carries it). The best-effort `codex mcp list --json` peek only NAMES what
    the user has configured, for the operator's context -- it never fails the
    row and this pipeline never mutates that file.
    """
    codex = shutil.which("codex")
    if codex is None:
        return ("codex config isolation", False, "codex not on PATH; not probed")
    detail = ("user config is never loaded: --ignore-user-config on every "
              "invocation")
    try:
        proc = subprocess.run(
            [codex, "mcp", "list", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        raw = (proc.stdout or "").strip() or "[]"
        names = _enabled_mcp_names(json.loads(raw))
        foreign = [n for n in names if n != FORENSIC_SERVER]
        if foreign:
            detail += (
                "; user config declares MCP server(s) "
                + ", ".join(foreign)
                + " -- they cannot load into a forensic run"
            )
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass  # the peek is context, not a gate
    return ("codex config isolation", True, detail)


def grok_mcp_isolation_row() -> tuple[str, bool, str]:
    """Preflight row: no enabled foreign server in the user's Grok config.

    Uses `grok mcp list --json` (configuration), not doctor (liveness -- that
    is `assert_mcp_live`'s job and needs a sandbox). An empty list is OK.
    """
    grok = shutil.which("grok")
    if grok is None:
        return ("grok MCP isolation", False, "grok not on PATH; not probed")
    try:
        proc = subprocess.run(
            [grok, "mcp", "list", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        raw = (proc.stdout or "").strip() or "[]"
        data = json.loads(raw)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return ("grok MCP isolation", False, f"probe failed: {exc}")
    names = _enabled_mcp_names(data)
    foreign = [n for n in names if n != FORENSIC_SERVER]
    if foreign:
        return (
            "grok MCP isolation",
            False,
            "foreign MCP server(s) enabled in ~/.grok/config.toml: "
            + ", ".join(foreign)
            + " -- reachable via search_tool from a forensic sweep. "
            "Remove or disable them; this pipeline will not mutate that file.",
        )
    return ("grok MCP isolation", True, "no foreign MCP servers enabled")


def _enabled_mcp_names(data) -> list[str]:
    names: list[str] = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = (data.get("servers") or data.get("mcp_servers")
                 or data.get("mcpServers") or [])
        if isinstance(items, dict):
            items = [
                {"name": k, **(v if isinstance(v, dict) else {})}
                for k, v in items.items()
            ]
    else:
        return names
    for item in items:
        if isinstance(item, str):
            names.append(item)
            continue
        if not isinstance(item, dict):
            continue
        enabled = item.get("enabled", True)
        if enabled is False or item.get("disabled") is True:
            continue
        name = item.get("name") or item.get("server")
        if name:
            names.append(str(name))
    return names


#: Backends whose init event names no MCP servers at all, keyed to the
#: wording the discovery note uses. Absence there is unknown, not missing.
_SILENT_INIT_BACKENDS = {"codex": "codex exec", "antigravity": "agy"}


def mcp_discovery_from_init(event: dict, backend: Backend,
                           forensic_mcp: bool = True) -> dict:
    """Tri-state record of what the init event declared.

    `status_is_live` is False on Grok: the field is configuration-only and
    always reads `connected`, so a guard keyed on it cannot fail.

    Codex declares NOTHING here -- its stream has no event that lists MCP
    servers -- and that absence must not read as a missing server or abort
    the stage. `declared` is None (unknown, not False); liveness comes from
    the pre-spend stdio probe and the `ForensicToolsNeverRan` ledger gate.

    `forensic_mcp=False` INVERTS the contract rather than disabling it. An
    invocation that asked for no server must be launched with no server, so the
    check becomes "the list is empty" -- and any server present, ours or
    foreign, is still a hard abort. That is the half that matters for image
    screening: the isolation guarantee, not the presence guarantee. Demanding
    presence there is what aborted every Grok image screen after the standalone
    package extraction.
    """
    if not forensic_mcp and backend.name not in _SILENT_INIT_BACKENDS:
        servers = event.get("mcp_servers") or []
        names = [str(e.get("name")) if isinstance(e, dict) else str(e)
                 for e in servers]
        names = [n for n in names if n and n != "None"]
        return {
            "declared": False,
            "requested": False,
            "status_is_live": False,
            "status": None,
            "servers": names,
            "foreign": names,
            "ok": not names,
        }
    if backend.name in _SILENT_INIT_BACKENDS:
        return {
            "declared": None,
            "status_is_live": False,
            "status": None,
            "servers": None,
            "foreign": [],
            "ok": True,
            "note": (f"{_SILENT_INIT_BACKENDS[backend.name]} stream does not "
                     "report MCP servers; liveness from the pre-spend stdio "
                     "probe plus the tool ledger"),
        }
    servers = event.get("mcp_servers") or []
    names: list[str] = []
    our_status = None
    for entry in servers:
        if isinstance(entry, dict):
            name = entry.get("name")
            if name:
                names.append(str(name))
            if name == FORENSIC_SERVER:
                our_status = entry.get("status")
        elif isinstance(entry, str):
            names.append(entry)
    declared = FORENSIC_SERVER in names
    foreign = [n for n in names if n != FORENSIC_SERVER]
    # The OpenRouter loop starts the servers itself and reports what its
    # own MCP handshake returned, so its status is as live as Claude's.
    status_is_live = backend.name in ("claude", "openrouter")
    ok = declared and not foreign
    if status_is_live:
        ok = ok and our_status == "connected"
    return {
        "declared": declared,
        "status_is_live": status_is_live,
        "status": our_status,
        "servers": names,
        "foreign": foreign,
        "ok": ok,
    }


def mcp_discovery_error(disc: dict) -> str | None:
    if disc.get("ok"):
        return None
    if disc.get("foreign"):
        return (
            "init event listed foreign MCP server(s): "
            + ", ".join(disc["foreign"])
            + " -- a forensic sweep must not be able to call them"
        )
    if not disc.get("declared"):
        # Deliberately does NOT name a cause. The previous wording asserted a
        # folder-trust/cwd failure, which this function cannot distinguish from
        # a config written without the server -- and when the real cause was the
        # latter it sent an investigation after the wrong thing for 62 papers.
        return (
            "init event has no forensic_metascience server. Either the server "
            "was not configured for this launch (check the invocation's "
            "forensic_mcp intent and the MCP config it wrote) or the CLI "
            "refused to load it (on Grok, check folder trust and that --cwd "
            "points at the run dir holding .grok/config.toml)."
        )
    if disc.get("status_is_live") and disc.get("status") != "connected":
        return (
            f"forensic_metascience init status is {disc.get('status')!r}, "
            "not connected"
        )
    return "MCP discovery from init event failed"


def normalize_event(event: dict, backend: Backend | None) -> dict:
    """Rewrite one stream event so archives are comparable across backends.

    Claude: identity. Grok: `use_tool` → `mcp__forensic_metascience__<short>`
    with inner arguments lifted to `input`; `read_file` → `Read`; `OkayOutput`
    envelope unwrapped to the inner JSON string. `search_tool` is left named
    `search_tool` (a harness tool). A `use_tool` aimed at a foreign server is
    left alone so the ledger records it as `UNVALIDATED` -- which is the truth.
    """
    if backend is None or backend.name != "grok" or not isinstance(event, dict):
        return event
    etype = event.get("type")
    if etype == "assistant":
        message = event.get("message")
        if not isinstance(message, dict):
            return event
        content = message.get("content")
        if not isinstance(content, list):
            return event
        new_content = [
            _rewrite_tool_use(block) if isinstance(block, dict) else block
            for block in content
        ]
        new_message = dict(message)
        new_message["content"] = new_content
        new_event = dict(event)
        new_event["message"] = new_message
        return new_event
    if etype == "user":
        message = event.get("message")
        if not isinstance(message, dict):
            return event
        content = message.get("content")
        if not isinstance(content, list):
            return event
        new_content = [
            _unwrap_tool_result(block) if isinstance(block, dict) else block
            for block in content
        ]
        new_message = dict(message)
        new_message["content"] = new_content
        new_event = dict(event)
        new_event["message"] = new_message
        return new_event
    return event


#: Grok built-in names -> the Claude names the ledger/audit vocabulary uses,
#: so archives stay byte-comparable across backends. The web pair is a
#: legitimate surface on an internet-on science agent; run_terminal_cmd and
#: write are ALWAYS breaches (backend shells stay denied -- code execution
#: rides the run_python_script MCP tool), mapped so a breach record reads
#: identically whichever backend produced it.
_GROK_BUILTIN_NAMES = {
    "read_file": "Read",
    "web_search": "WebSearch",
    "web_fetch": "WebFetch",
    "run_terminal_cmd": "Bash",
    "write": "Write",
}


def _rewrite_tool_use(block: dict) -> dict:
    if block.get("type") != "tool_use":
        return block
    name = block.get("name")
    if name in _GROK_BUILTIN_NAMES:
        rewritten = dict(block)
        rewritten["name"] = _GROK_BUILTIN_NAMES[name]
        rewritten["grok_meta_tool"] = name
        return rewritten
    if name != "use_tool":
        return block
    inp = block.get("input") if isinstance(block.get("input"), dict) else {}
    tool_name = inp.get("tool_name") or ""
    if not isinstance(tool_name, str) or "__" not in tool_name:
        return block
    server, _, short = tool_name.partition("__")
    if server != FORENSIC_SERVER or not short:
        return block
    rewritten = dict(block)
    rewritten["name"] = f"{MCP_TOOL_PREFIX}{short}"
    rewritten["input"] = inp.get("tool_input") if isinstance(inp.get("tool_input"), dict) else {}
    rewritten["grok_meta_tool"] = "use_tool"
    rewritten["grok_raw_input"] = copy.copy(inp)
    return rewritten


def _unwrap_tool_result(block: dict) -> dict:
    if block.get("type") != "tool_result":
        return block
    inner = block.get("content")
    text = _tool_result_text(inner)
    unwrapped, meta = _unwrap_okay_output(text)
    if unwrapped is None:
        return block
    rewritten = dict(block)
    rewritten["content"] = unwrapped
    rewritten["grok_raw_content"] = text
    if meta:
        rewritten["grok_result_meta"] = meta
    return rewritten


def _tool_result_text(inner) -> str:
    if isinstance(inner, str):
        return inner
    if isinstance(inner, list):
        return "".join(
            p.get("text", "") for p in inner if isinstance(p, dict)
        )
    return ""


def _unwrap_okay_output(text: str) -> tuple[str | None, dict | None]:
    """Return (inner_json_string, meta) or (None, None) if not an envelope."""
    if not text or not text.lstrip().startswith("{"):
        return None, None
    try:
        outer = json.loads(text)
    except json.JSONDecodeError:
        return None, None
    if not isinstance(outer, dict):
        return None, None
    output = outer.get("output")
    if not (isinstance(output, dict) and "OkayOutput" in output):
        return None, None
    payload = output["OkayOutput"]
    meta = {
        "server_name": outer.get("server_name"),
        "tool_name": outer.get("tool_name"),
    }
    if isinstance(payload, str):
        return payload, meta
    if isinstance(payload, dict):
        return json.dumps(payload), meta
    return None, None


#: Codex item types -> the Claude tool names the ledger/audit vocabulary
#: uses, same argument as `_GROK_BUILTIN_NAMES`: a shell or web use must
#: read identically in an archive whichever backend produced it.
_CODEX_ITEM_TOOL_NAMES = {
    "command_execution": "Bash",
    "web_search": "WebSearch",
}


def make_stream_normalizer(backend: Backend | None, *,
                           expects_schema: bool = False,
                           restore_schema: dict | None = None,
                           config_home: Path | None = None,
                           resume_state: dict | None = None):
    """The per-stage stream adapter. Claude/Grok: a stateless wrapper around
    `normalize_event` (existing behavior, untouched). Codex: a STATEFUL
    normalizer, because its events map 1-to-N onto the Claude shapes -- a
    completed `mcp_tool_call` carries call and result together, and the
    final Claude-style `result` event has to be synthesized from state.
    Antigravity: stateful too (text arrives as deltas per step, a tool as an
    ACTIVE/DONE pair), and it reads spilled MCP results from `config_home`.
    """
    if backend is not None and backend.name == "codex":
        return CodexStreamNormalizer(expects_schema=expects_schema,
                                     restore_schema=restore_schema)
    if backend is not None and backend.name == "antigravity":
        return AntigravityStreamNormalizer(config_home=config_home,
                                           expects_schema=expects_schema,
                                           resume_state=resume_state)
    return _EventNormalizer(backend)


#: agy built-in names -> the Claude names the ledger/audit vocabulary uses,
#: the `_GROK_BUILTIN_NAMES` argument: a shell or web use must read the same
#: in an archive whichever backend produced it. The shell and write tools are
#: never on the forensic agent's allowlist, so seeing one is a breach, mapped
#: so the record reads identically. `finish` is the schema channel, the
#: analog of Claude's `StructuredOutput` (a harness tool, not a forensic one).
_AGY_BUILTIN_NAMES = {
    "view_file": "Read",
    "search_web": "WebSearch",
    "read_url_content": "WebFetch",
    "run_command": "Bash",
    "write_to_file": "Write",
    "replace_file_content": "Edit",
    "multi_replace_file_content": "Edit",
    "sed_file": "Edit",
    "finish": "StructuredOutput",
}


class AntigravityStreamNormalizer:
    """Map `agy --output-format stream-json` events onto the Claude shapes.

    MEASURED against agy 1.4.2 (2026-10-18). Every line is
    `{"event": <name>, <name>: {...}}`:

    * `init` -> `system/init` (no MCP server list exists; see
      `_SILENT_INIT_BACKENDS`). `init.tools` is the CLI's whole registry even
      under `--agent` (measured), so it is kept as `agy_registry_tools`, never
      as the tools the model had.
    * `step_update` with `step_type: agent_response` streams `text_delta`
      fragments while ACTIVE and carries that call's `usage` when DONE; one
      assistant event is emitted per step, at DONE.
    * `step_type: tool` is an ACTIVE (call) / DONE or ERROR (result) pair
      sharing a `step_index`. `call_mcp_tool` becomes
      `mcp__<ServerName>__<ToolName>` with `Arguments` as its input -- a
      wrong server name stays wrong, so the ledger records it UNVALIDATED.
    * A large MCP result arrives as `output: ""` and lives in
      `brain/<conversation>/.system_generated/steps/<step>/output.txt`; it is
      read back (`agy_output_spilled: true`), and a spill that cannot be
      found is marked `"missing"` rather than passed off as an empty answer.
    * `result` carries `status`, `usage`, `num_turns` and, under
      `--json-schema`, `structured_output` (agy validates it itself, so no
      strict-dialect restore). No cost key is emitted: agy reports none,
      and `_run_stage` then records `cost_reported: False`.
    """

    def __init__(self, *, config_home: Path | None = None,
                 expects_schema: bool = False,
                 resume_state: dict | None = None):
        self.config_home = Path(config_home) if config_home else None
        self.expects_schema = expects_schema
        self.resume_state = resume_state
        self._conversation: str | None = None
        self._text: dict[int, list[str]] = {}
        self._open_tools: set[int] = set()

    def feed(self, event: dict) -> list[dict]:
        if not isinstance(event, dict):
            return [event]
        kind = event.get("event")
        if kind == "init":
            init = event.get("init") or {}
            self._conversation = event.get("conversation_id")
            if self.resume_state is not None and self._conversation:
                self.resume_state["conversation_id"] = self._conversation
            return [{
                "type": "system",
                "subtype": "init",
                "session_id": self._conversation,
                "model": init.get("model"),
                "cwd": init.get("cwd"),
                "permissionMode": init.get("permission_mode"),
                "agy_registry_tools": init.get("tools"),
                "agy_raw": event,
            }]
        if kind == "step_update":
            return self._step(event)
        if kind == "result":
            return [self._result(event)]
        return [event]

    def _step_id(self, step: dict) -> str:
        conv = step.get("conversation_id") or self._conversation or "agy"
        return f"agy-{conv}-{step.get('step_index')}"

    def _step(self, event: dict) -> list[dict]:
        step = event.get("step_update") or {}
        stype = step.get("step_type")
        state = step.get("state")
        index = step.get("step_index")
        if stype == "agent_response":
            delta = step.get("text_delta")
            if isinstance(delta, str) and delta:
                self._text.setdefault(index, []).append(delta)
            if state != "DONE":
                return [event]
            text = "".join(self._text.pop(index, []))
            usage = _agy_usage(step.get("usage"))
            return [{
                "type": "assistant",
                "message": {
                    "id": self._step_id(step),
                    "content": ([{"type": "text", "text": text}]
                                if text.strip() else []),
                    "usage": usage,
                },
                "agy_raw": event,
            }]
        # `finish` opens as `step_type: tool` and closes as `step_type:
        # finish` (measured), so both kinds are one tool call.
        if stype in ("tool", "finish"):
            info = step.get("tool_info") or {}
            if stype == "finish" and not info.get("name"):
                # A `finish` DONE with no prior ACTIVE carries no tool_info
                # (measured on the first agy apple_cider eval, 2026-10-18: the ledger got a
                # tool named ""). It is still the schema channel.
                info = {**info, "name": "finish"}
            out: list[dict] = []
            if index not in self._open_tools:
                self._open_tools.add(index)
                out.append(self._tool_use(step, info, event))
            if state in ("DONE", "ERROR"):
                self._open_tools.discard(index)
                out.append(self._tool_result(step, info, state, event))
            return out or [event]
        return [event]

    @staticmethod
    def _tool_name_and_input(info: dict) -> tuple[str, dict, dict]:
        name = str(info.get("name") or "")
        params = info.get("parameters") if isinstance(info.get("parameters"), dict) else {}
        extra: dict = {"agy_tool": name}
        if name == "call_mcp_tool":
            server = str(params.get("ServerName") or "")
            tool = str(params.get("ToolName") or "")
            args = params.get("Arguments")
            extra["agy_raw_input"] = copy.copy(params)
            if server and tool:
                return (f"mcp__{server}__{tool}",
                        args if isinstance(args, dict) else {}, extra)
            return name, params, extra
        if name == "view_file":
            return ("Read", {"file_path": params.get("AbsolutePath"), **params},
                    extra)
        if name == "read_url_content":
            return "WebFetch", {"url": params.get("Url"), **params}, extra
        if name == "search_web":
            return "WebSearch", {"query": params.get("query"), **params}, extra
        if name == "run_command":
            return "Bash", {"command": params.get("CommandLine"), **params}, extra
        return _AGY_BUILTIN_NAMES.get(name, name), params, extra

    def _tool_use(self, step: dict, info: dict, raw: dict) -> dict:
        name, tool_input, extra = self._tool_name_and_input(info)
        block = {"type": "tool_use", "id": self._step_id(step), "name": name,
                 "input": tool_input, **extra}
        return {
            "type": "assistant",
            "message": {"id": self._step_id(step) + "-call", "content": [block]},
            "agy_raw": raw,
        }

    def _tool_result(self, step: dict, info: dict, state: str, raw: dict) -> dict:
        block: dict = {"type": "tool_result", "tool_use_id": self._step_id(step)}
        err = info.get("error")
        if state == "ERROR" or err:
            block["is_error"] = True
            block["content"] = (str(err.get("message") or err)
                                if isinstance(err, dict) else str(err or ""))
        else:
            content = info.get("output")
            content = content if isinstance(content, str) else (
                "" if content is None else json.dumps(content))
            if content == "" and info.get("name") == "call_mcp_tool":
                spilled = self._read_spill(step)
                if spilled is None:
                    block["agy_output_spilled"] = "missing"
                else:
                    content = spilled
                    block["agy_output_spilled"] = True
            block["content"] = content
        return {"type": "user", "message": {"content": [block]}, "agy_raw": raw}

    def _read_spill(self, step: dict) -> str | None:
        if self.config_home is None:
            return None
        conv = step.get("conversation_id") or self._conversation
        if not conv:
            return None
        path = (self.config_home / ".gemini" / "antigravity-cli" / "brain"
                / str(conv) / ".system_generated" / "steps"
                / str(step.get("step_index")) / "output.txt")
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def _result(self, event: dict) -> dict:
        res = event.get("result") or {}
        status = str(res.get("status") or "")
        out: dict = {
            "type": "result",
            "result": res.get("response"),
            "num_turns": res.get("num_turns"),
            "duration_ms": int(float(res.get("duration_seconds") or 0) * 1000),
            "usage": _agy_usage(res.get("usage")),
            "agy_status": status,
            "agy_raw": event,
        }
        if isinstance(res.get("structured_output"), dict):
            out["structured_output"] = res["structured_output"]
        if res.get("denied_actions"):
            out["permission_denials"] = res["denied_actions"]
        if status != "SUCCESS":
            out["is_error"] = True
            out["subtype"] = f"agy_{status.lower() or 'unknown'}"
            out["errors"] = [str(res["error"])] if res.get("error") else []
        elif self.expects_schema and "structured_output" not in out:
            # agy does NOT force a schema-bearing turn to end in `finish`:
            # MEASURED 2026-10-18, gemini-3.8-flash-low explored the file
            # system, ended with `response: ""` and `status: SUCCESS`, and no
            # document existed. Claude's CLI would have ended at its schema
            # gate; this is the same fact, so it gets the same subtype and
            # the analysts' and adjudicator's one corrective retry.
            out["is_error"] = True
            out["subtype"] = "error_max_structured_output_retries"
            out["agy_no_finish"] = True
            if self.resume_state is not None:
                # Keep the sandbox: the retry resumes THIS conversation.
                self.resume_state["keep"] = True
                out["agy_resume"] = {"conversation_id": self._conversation}
            out["errors"] = [
                "the turn ended without calling `finish`: no structured "
                "output was delivered; the final document must be the "
                "arguments of a `finish` call"]
        return out


def _agy_usage(usage) -> dict:
    """agy usage -> the ledger's names. Thinking tokens are billed output, as
    they are in Claude's `output_tokens`, so they are added in and also kept
    under their own name."""
    u = usage if isinstance(usage, dict) else {}
    thinking = int(u.get("thinking_tokens", 0) or 0)
    return {
        "input_tokens": int(u.get("input_tokens", 0) or 0),
        "output_tokens": int(u.get("output_tokens", 0) or 0) + thinking,
        "thinking_tokens": thinking,
        "cache_read_input_tokens": int(u.get("cache_read_tokens", 0) or 0),
        "cache_creation_input_tokens": 0,
    }


class _EventNormalizer:
    """Stateless: one raw event in, one normalized event out."""

    def __init__(self, backend: Backend | None):
        self._backend = backend

    def feed(self, event: dict) -> list[dict]:
        return [normalize_event(event, self._backend)]


class CodexStreamNormalizer:
    """Map `codex exec --json` events onto the Claude stream-json shapes.

    Every synthesized event keeps the original under `codex_raw` (the
    `grok_raw_*` breadcrumb convention). Events with no Claude analog
    (turn.started, reasoning items, item.updated) pass through unchanged --
    `_run_stage` ignores unknown types, and the archive stays complete.

    The synthetic final `result` event carries NO `total_cost_usd` key:
    codex reports token usage only, so stage cost stays 0.0 -- never
    fabricated -- and `_run_stage` records `cost_reported: False` beside it,
    so the zero is not read as a measured one.
    """

    def __init__(self, *, expects_schema: bool = False,
                 restore_schema: dict | None = None):
        self.expects_schema = expects_schema
        self.restore_schema = restore_schema
        self._last_text: str | None = None
        self._open_items: set[str] = set()

    def feed(self, event: dict) -> list[dict]:
        if not isinstance(event, dict):
            return [event]
        etype = event.get("type")
        if etype == "thread.started":
            return [{
                "type": "system",
                "subtype": "init",
                "session_id": event.get("thread_id"),
                "codex_raw": event,
            }]
        if etype == "item.started":
            item = event.get("item") or {}
            use = self._tool_use_event(item, event)
            if use is not None:
                self._open_items.add(str(item.get("id")))
                return [use]
            return [event]
        if etype == "item.completed":
            item = event.get("item") or {}
            itype = item.get("type")
            if itype == "agent_message":
                text = item.get("text") or ""
                self._last_text = text
                return [{
                    "type": "assistant",
                    "message": {
                        "id": item.get("id"),
                        "content": [{"type": "text", "text": text}],
                    },
                    "codex_raw": event,
                }]
            result = self._tool_result_event(item, event)
            if result is not None:
                out: list[dict] = []
                if str(item.get("id")) not in self._open_items:
                    # No item.started was seen -- emit the call too, so the
                    # ledger never records a result with no call.
                    use = self._tool_use_event(item, event)
                    if use is not None:
                        out.append(use)
                self._open_items.discard(str(item.get("id")))
                out.append(result)
                return out
            return [event]
        if etype == "turn.completed":
            usage = event.get("usage") or {}
            result_event: dict = {
                "type": "result",
                "result": self._last_text,
                # `cached_input_tokens` / `cache_write_input_tokens` are the
                # codex names for what the ledger records as cache reads and
                # cache creation.
                "usage": {
                    "input_tokens": int(usage.get("input_tokens", 0) or 0),
                    "output_tokens": int(usage.get("output_tokens", 0) or 0),
                    "cache_read_input_tokens": int(
                        usage.get("cached_input_tokens", 0) or 0),
                    "cache_creation_input_tokens": int(
                        usage.get("cache_write_input_tokens", 0) or 0),
                },
                "codex_raw": event,
            }
            if self.expects_schema and self._last_text:
                try:
                    parsed = json.loads(self._last_text)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    if self.restore_schema is not None:
                        # Undo the strict-dialect rewrites (JSON-string
                        # stand-ins back to dicts, stand-in nulls dropped)
                        # so downstream sees the Claude-run shape.
                        parsed = restore_from_strict(
                            parsed, self.restore_schema)
                    result_event["structured_output"] = parsed
            return [result_event]
        if etype in ("turn.failed", "error"):
            message = self._error_message(event)
            return [{
                "type": "result",
                "is_error": True,
                "subtype": ("codex_turn_failed" if etype == "turn.failed"
                            else "codex_stream_error"),
                "result": self._last_text,
                "errors": [message] if message else [],
                "codex_raw": event,
            }]
        return [event]

    @staticmethod
    def _error_message(event: dict) -> str:
        err = event.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or err)
        if err is not None:
            return str(err)
        return str(event.get("message") or "")

    @staticmethod
    def _tool_use_event(item: dict, raw: dict) -> dict | None:
        itype = item.get("type")
        if itype == "mcp_tool_call":
            server = str(item.get("server") or "")
            tool = str(item.get("tool") or "")
            if not server or not tool:
                return None
            # Forensic calls become `mcp__forensic_metascience__<tool>` --
            # the exact string the model itself sees (measured 2026-09-01)
            # and the string the ledger validates. A foreign server keeps
            # its own name, so the ledger records it UNVALIDATED, which is
            # the truth.
            name = f"mcp__{server}__{tool}"
            tool_input = item.get("arguments")
        elif itype in _CODEX_ITEM_TOOL_NAMES:
            name = _CODEX_ITEM_TOOL_NAMES[itype]
            if itype == "command_execution":
                tool_input = {"command": item.get("command")}
            else:
                tool_input = {"query": item.get("query")}
        else:
            return None
        return {
            "type": "assistant",
            "message": {
                "id": item.get("id"),
                "content": [{
                    "type": "tool_use",
                    "id": item.get("id"),
                    "name": name,
                    "input": tool_input if isinstance(tool_input, dict) else {},
                }],
            },
            "codex_raw": raw,
        }

    @staticmethod
    def _tool_result_event(item: dict, raw: dict) -> dict | None:
        itype = item.get("type")
        if itype not in ("mcp_tool_call", *_CODEX_ITEM_TOOL_NAMES):
            return None
        is_error = False
        if itype == "mcp_tool_call":
            error = item.get("error")
            if error:
                is_error = True
                content = (str(error.get("message") or error)
                           if isinstance(error, dict) else str(error))
            else:
                result = item.get("result")
                if isinstance(result, dict) and isinstance(
                        result.get("content"), list):
                    content = result["content"]
                elif result is None:
                    content = ""
                elif isinstance(result, str):
                    content = result
                else:
                    content = json.dumps(result)
        elif itype == "command_execution":
            content = str(item.get("aggregated_output") or "")
            exit_code = item.get("exit_code")
            if isinstance(exit_code, int) and exit_code != 0:
                is_error = True
        else:  # web_search: the stream carries no result payload
            content = ""
        block: dict = {
            "type": "tool_result",
            "tool_use_id": item.get("id"),
            "content": content,
        }
        if is_error:
            block["is_error"] = True
        return {
            "type": "user",
            "message": {"content": [block]},
            "codex_raw": raw,
        }


def as_invocation(cmd) -> Invocation:
    """Accept today's list[str] tests and a real Invocation the same way."""
    if isinstance(cmd, Invocation):
        return cmd
    return Invocation(
        argv=list(cmd),
        prompt_delivery="stdin",
        workdir=None,
        env_overlay={},
        cleanup=lambda: None,
        backend=CLAUDE,
        allowed_tools=(),
    )


def reset_mcp_live_cache() -> None:
    _MCP_LIVE_CACHE.clear()


def sandbox_limitation_sentence(backend: Backend) -> str | None:
    if not backend.sandbox_weaker:
        return None
    if backend.name == "codex":
        return (
            "Codex's read-only shell is kept as its only file-read tool: the "
            "model can run arbitrary read-only commands the prompt forbids "
            "using for analysis (writes and network egress are denied by the "
            "sandbox). This run's sandbox is weaker than a Claude run's."
        )
    return (
        "Grok's `search_tool` cannot be denied: it is the only route to the "
        "forensic MCP tools. This run's sandbox is weaker than a Claude run's."
    )
