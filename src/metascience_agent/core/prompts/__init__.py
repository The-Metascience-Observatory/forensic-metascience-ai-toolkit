"""Assembles what each agent is sent, and loads the output schemas.

The text lives with its owners: each agent module's system prompt is
`modules/<name>/prompt.md`, the text every role shares is the markdown beside
this file (`core/prompts/`), each tool's guidance is its family's `TOOL.md`,
and the JSON schemas are `metascience_agent/schema/`. This module reads and
assembles them so the pipeline, the eval harness and the tests all use
identical text. (Until 2026-10-18 it was `metascience_agent/prompts/`, which
held the prompt files themselves before the modular refactor.)

The normative contract for findings v2 (`findings_schema_v2()`,
`producer_findings_schema()`, `PRODUCERS`) is docs/specs/findings_v2.md.
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path

from ... import verdicts as _verdicts
from ...tools import severity as _tool_severity

#: The shared prompt text (`rulebook.md`, ...) sits beside this file.
PROMPTS_DIR = Path(__file__).resolve().parent
_PKG = PROMPTS_DIR.parents[1]
SCHEMA_DIR = _PKG / "schema"

#: WHERE EACH PROMPT LIVES (modular refactor, 2026-10-15). An agent module's
#: system prompt is beside its definition, `modules/<name>/prompt.md`; the
#: text every role shares is `core/prompts/`. The keys are the files' names
#: from before the refactor, so `_read("tool_expert.md")` and every reader of
#: a name keeps working.
PROMPT_FILES: dict[str, Path] = {
    "tool_expert.md": _PKG / "modules" / "tools_agent" / "prompt.md",
    "science_error.md": _PKG / "modules" / "scientific_proofreading_agent" / "prompt.md",
    "adjudication.md": _PKG / "modules" / "adjudicator" / "prompt.md",
    "rulebook.md": PROMPTS_DIR / "rulebook.md",
    "rulebook_roles.md": PROMPTS_DIR / "rulebook_roles.md",
    "reproduction.md": PROMPTS_DIR / "reproduction.md",
    "grok_mcp_route.md": PROMPTS_DIR / "grok_mcp_route.md",
    # Appended by `llm_backend._build_antigravity_invocation`, not here: it
    # applies to every schema-bearing Antigravity call (analysts, adjudicator,
    # image screens), so the backend seam is the one place that sees them all.
    "antigravity_route.md": PROMPTS_DIR / "antigravity_route.md",
    # Sent as the user turn when a schema-gate retry RESUMES an agy
    # conversation (`llm_backend.antigravity_resume_prompt`).
    "antigravity_resume.md": PROMPTS_DIR / "antigravity_resume.md",
}


def prompt_path(name: str) -> Path:
    """The file behind a prompt name (`"adjudication.md"`, ...)."""
    return PROMPT_FILES.get(name, PROMPTS_DIR / name)


def prompt_files() -> list[Path]:
    """Every prompt markdown file, wherever it lives: the ones sent to a model
    and any other `core/prompts/*.md`. A scanner of prompt text must read THIS
    list -- a guard globbing one folder silently misses the module prompts."""
    return sorted({*PROMPT_FILES.values(), *PROMPTS_DIR.glob("*.md")})


@lru_cache(maxsize=None)
def _read(name: str) -> str:
    return prompt_path(name).read_text()


#: Where the tools agent's step-3 guidance is assembled. The bullets live in
#: each tool family's TOOL.md (`tool_specs.guidance`), beside the tool they
#: are about, and are put back here in their numbered order -- byte for byte
#: what this file held before Phase 3b (`tests/test_pipeline_parity.py`).
TOOL_GUIDANCE_MARK = "{{TOOL_GUIDANCE}}"


def tool_expert_body() -> str:
    """`tool_expert.md` with its per-tool guidance assembled from the tool
    folders. Read this, never the raw file, for what the model is sent."""
    from ...tool_specs import guidance
    raw = _read("tool_expert.md")
    if raw.count(TOOL_GUIDANCE_MARK) != 1:
        raise ValueError("tool_expert.md must carry exactly one "
                         f"{TOOL_GUIDANCE_MARK} marker")
    return raw.replace(TOOL_GUIDANCE_MARK, "\n".join(t for _, t, _ in guidance()))


def rulebook() -> str:
    return _read("rulebook.md")


#: Tools the figure pass owns. When `--figures` is off these are removed from
#: the allowlist, not merely left unmentioned by the
#: stripped prose -- `agent._stage1_tools` states the rule for the legacy path
#: in one line: "a tool that is offered can be called."
FIGURE_TOOLS = frozenset({"extract_figures"})


#: The figure section of the sweep prompt, delimited so it can be removed when
#: the figure pass is off. Without this the flag was decorative: `--figures`
#: defaulted to off while the prompt instructed `extract_figures`
#: unconditionally, so the pass ran every time.
_FIGURE_SECTION_START = "## Figures: what the paper shows but does not print"
_FIGURE_SECTION_END = "## Procedure"


def _strip_figure_section(text: str) -> str:
    """Remove the figure instructions when the figure pass is disabled.

    An unverified figure pass can make a report WORSE, not just slower -- wrong
    figure, caption paired with the panel above, a three-panel figure read as
    one. Those are wrong-OBJECT errors and they are unbounded. So the pass is
    opt-in, and opt-in has to mean the model is not told to do it.
    """
    start = text.find(_FIGURE_SECTION_START)
    end = text.find(_FIGURE_SECTION_END, start + 1) if start != -1 else -1
    if start == -1 or end == -1:
        return text
    return text[:start] + text[end:]


def _severity_ladder() -> str:
    """The 1-9 rubric, emitted by severity9 at assembly time (R1: one severity
    source; a ladder FILE would be a second copy that drifts)."""
    from ...severity9 import rubric_markdown

    return rubric_markdown()


@lru_cache(maxsize=1)
def r_crosscheck_note() -> str:
    """What the R ground-truth engines can actually do ON THIS MACHINE.

    THE PROMPTS PROMISE A SECOND OPINION AND NEVER SAY WHETHER IT CAN BE GIVEN.
    Both analyst prompts require an `impossible` to be cross-checked against R
    before publication, and say an unobtainable cross-check drops the severity
    to `indeterminate`. Neither states whether R is installed on the machine
    running, so the model has to write about the cross-check without knowing
    whether it can happen -- and on 10.1177--0093854811403123 (MEASURED
    2026-08-22) it wrote "The GRIM-family R cross-check is still pending" and
    "Awaiting editorial-stage R GRIMMER cross-check" into two findings that
    shipped at severity 2 and 3.

    That machine HAD scrutiny and rsprite2, and the adjudicator did run
    `r_grim_ground_truth` on the first of those findings. So the notes were
    stale rather than false -- but a reader cannot tell the two apart, and both
    read as "a confirmation is on its way", which is what makes a severity-2
    accusation look provisional when it is being published. Stating the
    availability up front removes the ambiguity in both directions: where the
    engine is present there is nothing to await, and where it is absent the
    rule that should fire is not a deferral but a downgrade.

    Cached because the probe shells out to Rscript twice, and the prompt is
    assembled once per stage. Cached HERE and not in `preflight`, whose own
    tests monkeypatch the probe and need it live.

    Never raises: a prompt that cannot be built is worse than a prompt that
    says the availability is unknown.
    """
    try:
        from ...preflight import _r_crosscheck_status
        ok, detail = _r_crosscheck_status()
    except Exception:  # noqa: BLE001
        ok, detail = False, "the availability probe itself could not run"
    if ok:
        return (
            "## The R cross-check on this machine\n\n"
            f"AVAILABLE ({detail}). `r_grim_ground_truth` and "
            "`r_sprite_ground_truth` will return a real second opinion, so the "
            "cross-check rules above apply as written. RUN IT AND RECORD THE "
            "ANSWER -- do not leave a finding saying the cross-check is "
            "\"pending\" or \"awaited\". There is nothing to await, and a "
            "published accusation carrying that wording reads as provisional "
            "when it is not. Note also that the tools agent cannot call "
            "`r_grim_ground_truth` (it is adjudicator-only), so a GRIM-family "
            "`impossible` it hands over must be cross-checked HERE, and the "
            "note it wrote updated to say what the second engine said."
        )
    return (
        "## The R cross-check on this machine\n\n"
        f"**UNAVAILABLE: {detail}**\n\n"
        "It will NOT become available later in this run. Do not write "
        "\"awaiting\", \"pending\", or \"to be confirmed\" about it in `notes` -- "
        "that describes a step that is going to happen, and none is. Apply the "
        "rule instead: an `impossible` that cannot be cross-checked is "
        "`indeterminate`, and a finding that rests on one drops accordingly. "
        "Say in `notes` that the engine is absent on this machine, which is a "
        "fact about us and not about the paper."
    )


#: The per-tool list a toolset filters: from this step heading to the next.
_CHECK_LIST_START = "3. **Check each remaining statistic**"
_CHECK_LIST_END = "4. **Cross-check against the R ground truth"


def _bullet_tools(bullet: str, known: set[str]) -> set[str]:
    """Registry tools a bullet is ABOUT: the backticked names in its lead,
    before the dash that starts the explanation. The lead can wrap onto a
    continuation line (`recalc_independent_t`, ..., `recalc_f_to_p` — ...), so
    the whole bullet is read, not its first line."""
    lead = bullet.split(" — ", 1)[0]
    return {name for name in __import__("re").findall(r"`([a-z0-9_]+)`", lead)
            if name in known}


def _all_tools(text: str, known: set[str]) -> set[str]:
    return {name for name in __import__("re").findall(r"`([a-z0-9_]+)`", text)
            if name in known}


def _filter_check_list(body: str, enabled: set[str], known: set[str]) -> str:
    """Drop the per-tool bullets of step 3 whose tools are ALL disabled.

    A bullet naming at least one enabled tool stays whole; a bullet naming no
    registry tool stays (it is procedure, not a tool). Everything outside the
    step-3 list is untouched -- the toolset note says how to read it.
    """
    start = body.find(_CHECK_LIST_START)
    end = body.find(_CHECK_LIST_END, start + 1) if start != -1 else -1
    if start == -1 or end == -1:
        return body
    lines = body[start:end].split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith("   - "):
            out.append(line)
            i += 1
            continue
        j = i + 1
        while j < len(lines) and lines[j].startswith("     "):
            j += 1
        bullet = "\n".join(lines[i:j])
        named = _bullet_tools(bullet, known)
        # Kept when ANY tool it names -- in the lead or the body -- is
        # enabled: `check_regression_batch`'s bullet is also the only guidance
        # `check_regression` gets. Over-keeping costs a few lines of prompt;
        # dropping an enabled tool's guidance costs the check its guards.
        mentioned = named | _all_tools(bullet, known)
        if not named or mentioned & enabled:
            out.extend(lines[i:j])
        i = j
    return body[:start] + "\n".join(out) + body[end:]


def _toolset_note(enabled: list[str]) -> str:
    return (
        "## Tools available in this run\n\n"
        "This run is configured with a RESTRICTED toolset. You can call only "
        "these forensic tools:\n\n"
        + "\n".join(f"- `{t}`" for t in enabled)
        + "\n\nOther tools named elsewhere in these instructions are NOT "
        "available in this run and calls to them are refused. Do not "
        "approximate their checks by hand or with another tool. When a "
        "statistic could only be checked by a tool that is not available, "
        "record it in `unchecked` with the reason \"tool not enabled in this "
        "pipeline\" -- a check that was not run is not a check that passed."
    )


def tool_expert_system_prompt(figures: bool = False, *,
                              grok_mcp_route: bool = False,
                              tools: "list[str] | tuple[str, ...] | None" = None) -> str:
    """System prompt for the tool-expert agent of the parallel pipeline.

    Composition mirrors `stage1_system_prompt` (whose procedure text it
    carries forward) plus the severity ladder and the role addendum
    (`rulebook_roles.md` -- kept OUT of rulebook.md so the live two_stage
    prompt bytes stay frozen until cutover), and the CLI map FILTERED to the
    role: a map naming tools an agent cannot call invites off-list calls.

    `tools` is a pipeline's resolved toolset (`pipeline_config`). None, or a
    toolset holding every tool-agent tool, gives the historical bytes exactly
    (pinned by tests). A restricted toolset drops the step-3 bullets of tools
    it does not have, drops them from the CLI map, and appends a note naming
    what IS available and how to record the rest.
    """
    from ...registry import TOOL_AGENT, stage_tools
    body = tool_expert_body()
    if not figures:
        body = _strip_figure_section(body)
    drop = set() if figures else set(FIGURE_TOOLS)
    note = ""
    if tools is not None:
        known = set(stage_tools(TOOL_AGENT))
        enabled = set(tools)
        missing = (known - set(FIGURE_TOOLS)) - enabled
        if missing:
            body = _filter_check_list(body, enabled, known)
            drop |= missing
            available = [t for t in stage_tools(TOOL_AGENT) if t in enabled]
            note = f"\n\n---\n\n{_toolset_note(available)}"
    text = (
        f"{body}\n\n---\n\n{_severity_ladder()}"
        f"\n\n---\n\n{rulebook()}"
        f"\n\n---\n\n{_read('rulebook_roles.md')}"
        f"\n\n---\n\n{r_crosscheck_note()}"
        f"\n\n---\n\n{_read('reproduction.md')}"
        f"{note}"
    )
    if grok_mcp_route:
        text = f"{text}\n\n---\n\n{_read('grok_mcp_route.md')}"
    return text


def run_configuration_note(config, module: str) -> str:
    """What a PARTIAL pipeline does not run, said to the agents that do run.

    The role prompts promise collaborators -- the tool expert is told a
    science analyst covers methodology, the science analyst that the tool
    expert covers the statistics, both that an adjudicator ranks their rows.
    In a partial pipeline some of those are absent, and an agent relying on
    an absent colleague leaves a gap that reads as coverage. Empty for a
    complete review, so its prompts keep their historical bytes.
    """
    if config is None or config.complete_review:
        return ""
    lines = [f"## This run's configuration\n\nThis is a PARTIAL pipeline "
             f"({config.name!r}), not a complete review."]
    if module != "tools_agent" and not config.has("tools_agent"):
        lines.append(
            "- No tools agent runs. The statistics, tables and supplements your "
            "instructions say the tools agent checks are NOT being checked in "
            "this run. Do not assume they were; anything you would hand off "
            "still goes to `unchecked`.")
    if module == "tools_agent" and not config.has("scientific_proofreading_agent"):
        # THE ONE CLASS THAT WOULD OTHERWISE BE LOST (1.92.0). A number printed
        # two ways is a numeric fact a numbers-only run must still report; with
        # no proofreading agent a handoff note reaches no one. MEASURED
        # 2026-10-18 (statcheck_pvalue_errors working set, tools_only): the
        # tools agent filed 24-25 such rows per run against a prompt that told
        # it, three different ways, to hand them off, file them, and leave them.
        lines.append(
            "- No scientific proofreading agent runs, so a handoff note reaches "
            "no one. ONE class of internal contradiction is yours in this run: "
            "the SAME quantity printed with different values in two places "
            "(abstract vs Results, a sentence vs its own table, one table vs "
            "another). File each as a finding with technique "
            "`internal_contradiction`, quoting BOTH printings verbatim as two "
            "anchors (`role` `\"said\"` and `\"against\"`), each one contiguous "
            "span copied exactly. Everything else "
            "your instructions assign to that agent -- contradictions in words "
            "rather than numbers, methodology, participant flow, reporting "
            "practice -- is out of scope for this run: do not take it on, and "
            "do not describe it as covered.")
    elif module != "scientific_proofreading_agent" and not config.has(
            "scientific_proofreading_agent"):
        lines.append(
            "- No scientific proofreading agent runs. The "
            "methodology, internal-contradiction and participant-flow review "
            "your instructions assign to it is out of scope for this run; do "
            "not take it on, and do not describe it as covered.")
    if module != "adjudicator" and not config.has("adjudicator"):
        lines.append(
            "- No adjudicator runs. Your provisional severities are what the "
            "report shows, marked provisional. Apply the severity rules exactly "
            "as written; nothing downstream will correct them.")
    return "\n\n---\n\n" + "\n".join(lines)


def system_prompt_for(config, module: str, *, grok_mcp_route: bool = False) -> str:
    """The system prompt a pipeline sends one agent module -- ONE builder for
    both the command and the recorded prompt hash, so the two cannot differ.
    For a complete review this is byte-identical to the historical prompts."""
    if module == "tools_agent":
        tools = None if config is None or config.full_toolset else config.toolset
        base = tool_expert_system_prompt(
            figures=bool(config and config.figures), grok_mcp_route=grok_mcp_route,
            tools=tools)
    elif module == "scientific_proofreading_agent":
        base = science_error_system_prompt(grok_mcp_route=grok_mcp_route)
    elif module == "adjudicator":
        base = adjudication_system_prompt()
    else:
        raise ValueError(f"{module!r} is not an agent module")
    return base + run_configuration_note(config, module) + tool_access_note(config, module)


def module_tool_names(config, module: str) -> list[str]:
    """The registry tools an agent module may call in this run, in registry
    order: the role's surface, narrowed by the pipeline's toolset and the
    figure switch exactly as the MCP allowlist is."""
    from ... import parallel as _par
    from ...agent import MCP_TOOL_PREFIX
    if module == "tools_agent":
        allowed = _par.tool_agent_tools(bool(config and config.figures),
                                        None if config is None else config.toolset)
    elif module == "scientific_proofreading_agent":
        allowed = _par.SCIENCE_AGENT_TOOLS
    else:
        allowed = _par.ADJUDICATOR_TOOLS
    return [t[len(MCP_TOOL_PREFIX):] for t in allowed if t.startswith(MCP_TOOL_PREFIX)]


def tool_access_note(config, module: str) -> str:
    """What changes for the agent when its module's `tool_access` is not the
    default (docs/specs/tool_access.md). Empty for `mcp`, so every default
    prompt is unchanged."""
    spec = None if config is None else config.module(module)
    access = getattr(spec, "tool_access", "mcp")
    if access == "mcp_brief":
        return ("\n\n---\n\n## Tool descriptions in this run\n\n"
                "Each forensic tool is listed with a ONE-LINE summary. Before you "
                "first call a tool, call `describe_tool` with its name: the full "
                "description carries the guards, required precisions and refusal "
                "rules the summary leaves out, and a call made without them is the "
                "usual way a check refuses or misfires.")
    if access == "skill":
        from ...registry import BY_NAME
        lines = []
        for name in module_tool_names(config, module):
            spec_ = BY_NAME[name]
            params = ", ".join(p.name for p in spec_.params if not p.withheld)
            lines.append(f"- `{name}`: {spec_.brief} ({params})")
        return ("\n\n---\n\n## How you call your tools in this run\n\n"
                "Your forensic tools are NOT offered as tool calls in this run. "
                "Run each one with the shell command\n\n"
                "    metascience tool run <name> --json '<arguments as one JSON object>'\n\n"
                "It applies exactly the checks and refusals the tool always applies, "
                "prints the verdict on its first line and then the result as JSON. "
                "`metascience tool describe <name>` prints a tool's full instructions "
                "(guards, required precisions, refusal rules): read it before you "
                "first use a tool. Put the JSON in single quotes. These `metascience "
                "tool` commands are the ONLY shell commands you may run; anything "
                "else is refused. Wherever your instructions say to call a tool, run "
                "it this way. Read files with `Read`.\n\n"
                "Your tools (name: summary (parameters)):\n" + "\n".join(lines))
    return ""


def prompt_blob(config) -> str:
    """The provenance blob `prompt_sha256` hashes: the system prompts of the
    configured agent modules, in fixed order. For a complete review with
    figures off this is exactly the historical tool + science + adjudicator
    trio (pinned); it is built WITHOUT the Grok route, as it always was,
    because the build identity is not a function of the backend."""
    order = ("tools_agent", "scientific_proofreading_agent", "adjudicator")
    modules = [m for m in order if config is None or config.has(m)]
    return "\x00".join(system_prompt_for(config, m) for m in modules)


def science_error_system_prompt(*, grok_mcp_route: bool = False) -> str:
    """System prompt for the scientific proofreading agent (stored producer
    `science_error`) of the parallel pipeline."""
    text = (
        f"{_read('science_error.md')}\n\n---\n\n{_severity_ladder()}"
        f"\n\n---\n\n{rulebook()}"
        f"\n\n---\n\n{_read('rulebook_roles.md')}"
        f"\n\n---\n\n{_read('reproduction.md')}"
    )
    if grok_mcp_route:
        text = f"{text}\n\n---\n\n{_read('grok_mcp_route.md')}"
    return text


def adjudication_system_prompt() -> str:
    """System prompt for the FINDINGS adjudicator (the parallel pipeline's
    final ranking stage) -- distinct from the image/cross-paper adjudicators
    below, which clear pixels and issue no severities. This one ranks, so it
    gets the ladder (embedded at assembly time from severity9 -- R1, no file
    to drift) plus the shared rulebook and the role addendum."""
    return (
        f"{_read('adjudication.md')}\n\n---\n\n{_severity_ladder()}"
        f"\n\n---\n\n{rulebook()}"
        f"\n\n---\n\n{_read('rulebook_roles.md')}"
        f"\n\n---\n\n{r_crosscheck_note()}"
    )


def adjudication_schema_path() -> Path:
    return SCHEMA_DIR / "adjudication.schema.json"


@lru_cache(maxsize=None)
def adjudication_schema() -> dict:
    return json.loads(adjudication_schema_path().read_text())


# The image-finding and cross-paper adjudication prompts ship with the image
# analysis package; reached through the plugin door, so these raise
# `ImagePluginUnavailable` by name when it is not installed.
def _image_prompts():
    from ...image_plugin import load
    return load("prompts")


def image_adjudication_system_prompt(*args, **kwargs):
    return _image_prompts().image_adjudication_system_prompt(*args, **kwargs)


def image_adjudication_schema_path(*args, **kwargs):
    return _image_prompts().image_adjudication_schema_path(*args, **kwargs)


def image_adjudication_schema(*args, **kwargs):
    return _image_prompts().image_adjudication_schema(*args, **kwargs)


def cross_paper_adjudication_system_prompt(*args, **kwargs):
    return _image_prompts().cross_paper_adjudication_system_prompt(*args, **kwargs)


def cross_paper_adjudication_schema_path(*args, **kwargs):
    return _image_prompts().cross_paper_adjudication_schema_path(*args, **kwargs)


def cross_paper_adjudication_schema(*args, **kwargs):
    return _image_prompts().cross_paper_adjudication_schema(*args, **kwargs)


# SOURCED FROM THE VOCABULARY MODULES, NOT FROM THE V1 SCHEMAS. Both tuples
# used to be built at import time by reading `findings.schema.json` and
# `report.schema.json` -- the two V1 files that the legacy-pipeline deletion
# removes. `evaluation/deterministic.py` reads both on the LIVE eval path
# (`harness.py` calls it for parallel runs too), so deleting those schemas
# would have broken current-pipeline evaluation with an error pointing at a
# file nobody thought was load-bearing.
#
# The values are unchanged and pinned identical by
# `tests/test_prompt_value_tuples.py`: `tools/severity.py` exists to be the one
# severity enum ("so downstream consumers ... can rely on a single enum", its
# own docstring), and `verdicts.VERDICTS` is the same three strings the report
# schema listed. Every consumer does a membership test, so ORDER is not part of
# the contract -- but it happens to match anyway.
SEVERITY_VALUES: tuple[str, ...] = tuple(_tool_severity.SEVERITY_LEVELS)

VERDICT_VALUES: tuple[str, ...] = tuple(_verdicts.VERDICTS)


# ---------------------------------------------------------------------------
# Findings schema v2 (docs/specs/findings_v2.md). Additive: nothing above this
# line changed, and the live two_stage pipeline keeps consuming v1.
# ---------------------------------------------------------------------------

#: The canonical producer list (spec section 1.1) -- this module is its owner.
#: `fast_screen` is here FROM DAY ONE so the screen agent's arrival (Phase 9)
#: is not a schema break; its structural caps live in severity9/the screen
#: runner, not here.
PRODUCERS: tuple[str, ...] = (
    "tool_expert",
    "science_error",
    "image_track",
    "text_track",
    "raw_data_track",
    # The harness sweeps that file findings (`grim_harness.finding_rows`,
    # 2026-10-18). Written by code from the tools agent's declarations, never
    # by a model, which is why it is not that agent's producer.
    "harness",
    "fast_screen",
    "legacy_sweep",
    "legacy_editorial",
)

#: The six fixed non-tool technique values (spec section 1.2). Everything else
#: in the technique enum is DERIVED from `registry.SPECS` at load time, so a
#: new tool enters the vocabulary through the registry, never through a
#: hand-edited literal here -- the drift that produced `grim` vs `grim_check`.
NON_TOOL_TECHNIQUES: tuple[str, ...] = (
    "not_computational",
    "no_tool_exists",
    "tool_existed_unused",
    "legacy_unattributed",
    "factual_claim",
    "internal_contradiction",
)

#: The sentinel the v2 FILE carries where the technique enum belongs -- the
#: raw file deliberately validates nothing, loudly, rather than letting a
#: stale hand-maintained tool list validate the wrong things quietly.
_TECHNIQUE_PLACEHOLDER = "__TECHNIQUE_ENUM_INJECTED_AT_LOAD__"

#: Finding-level fields a producer may NEVER emit (spec section 4) -- enforced
#: by OMISSION plus `additionalProperties: false`, never by prose. `producer`
#: is here too: the harness stamps it, and a producer that could name its own
#: producer could claim another's structural privileges (fast_screen's caps
#: key on it).
_NOT_PRODUCER_WRITTEN: tuple[str, ...] = (
    "finding_id",
    "finding_id_hasher",
    "producer",
    "severity",
    # What a row claimed BEFORE `clamp_provisionals` applied an evidence
    # ceiling. Pipeline-set for the same reason `severity` is: a producer that
    # could write its own clamp history could assert it had been capped from a
    # level it never claimed, or that it had not been capped at all.
    "provisional_severity_from",
    "severity_is_provisional",
    "impossible",
    "tool_verdict",
    "severity_source",
    "computed_by",
    "adjudication",
    "legacy",
    "anchor_summary",
    # anchor_problem is deliberately NOT here: producers may (must) say WHY
    # they could not supply a passage -- the named-absence escape hatch
    # (docs/specs/anchors.md section 5). Adjudicated 2026-08-21 after the
    # simplification pass flagged the spec-vs-code disagreement.
    "quote_verified",
    "quote_source",
    "quote_problem",
    "source",
    "artefacts",
    "reproduction_kind",
    "reproduction_valid",
    "reproduction_problem",
    "reproduction_not_executed",
    "reproduction_source",
    "reproduction_call",
    "reproduction_not_generatable",
)

#: Written by the deterministic track BUILDERS (code), so only the two track
#: producers' subsets carry them: "track builders ... must still emit only
#: subset-legal keys plus quarantined/quarantine_reason" (spec section 4).
_TRACK_ONLY: tuple[str, ...] = ("quarantined", "quarantine_reason")

#: Per-producer narrowing (spec section 4): only the science agent's subset
#: contains `web_sources`/`basis` -- a producer with no web access must not be
#: offered a slot that implies it looked something up.
_SCIENCE_ONLY: tuple[str, ...] = ("web_sources", "basis")

#: Document-level keys the PIPELINE writes (spec section 2) -- run identity,
#: metadata projection, channel states, the adjudication summary, the merged
#: denominator block and provenance. The model never invents metadata, and a
#: producer that could write `channels` could report its own coverage.
_DOC_PIPELINE_ONLY: tuple[str, ...] = (
    "run_id",
    # The pipeline configuration that produced the run (`pipeline_config`).
    # Recorded by the harness; a producer that could write it could claim a
    # complete review it was not part of.
    "pipeline",
    "paper_metadata",
    "channels",
    "adjudication",
    "checks_tally",
    # The census. Pipeline-written since v1.23.0 and stripped here for the
    # reason this whole tuple exists: a key the model can see is a key the
    # model may fill, and `coverage_summary` is the INDEPENDENT denominator --
    # the one number in the document whose entire value is that no model
    # produced it.
    "coverage_summary",
    "provenance",
)

#: Producers whose findings are converter-written FULL rows (severity, legacy
#: block and all): there is no producer-facing subset for them, and offering
#: one would imply the converter is bound by it.
_CONVERTER_PRODUCERS = frozenset({"legacy_sweep", "legacy_editorial"})


def findings_schema_v2_path() -> Path:
    return SCHEMA_DIR / "findings.v2.schema.json"


@lru_cache(maxsize=None)
def findings_schema_v2() -> dict:
    """The full v2 document schema, with the technique enum injected.

    The enum is generated from the registry rather than stored in the file so
    adding a tool adds its technique in the same act (wiring-checklist step 4
    stops existing for v2) and fire-rate joins to the toolcall ledger are
    equality joins on exact registry names. A misplaced placeholder raises:
    silently skipping injection would be a hand-maintained list again.
    """
    # Lazy: registry imports the tools package,
    # prompts must not.
    from ...registry import NON_TECHNIQUE_TOOLS, SPECS

    schema = json.loads(findings_schema_v2_path().read_text())
    technique = schema["properties"]["findings"]["items"]["properties"]["technique"]
    if technique.get("enum") != [_TECHNIQUE_PLACEHOLDER]:
        raise ValueError(
            "findings.v2.schema.json technique enum is not the expected "
            f"placeholder [{_TECHNIQUE_PLACEHOLDER!r}]; refusing to guess "
            "where the generated enum belongs"
        )
    technique["enum"] = sorted(s.name for s in SPECS
                           if s.name not in NON_TECHNIQUE_TOOLS) \
        + list(NON_TOOL_TECHNIQUES)
    return schema


@lru_cache(maxsize=None)
def producer_findings_schema(producer: str, figures: bool = False) -> dict:
    """The producer-facing SUBSET of the v2 schema for one producer.

    Non-producer-written fields are stripped so `additionalProperties: false`
    rejects a forged `finding_id`/`severity`/`impossible` by schema, not by
    prose. `coverage`/`anatomy`/`statistics_register`/`figures` are required
    only of `tool_expert`, the coverage-denominator owner; other producers
    may emit them but are not schema-forced to (spec section 2).
    """
    if producer not in PRODUCERS:
        raise ValueError(f"unknown producer {producer!r}; expected one of {PRODUCERS}")
    if producer in _CONVERTER_PRODUCERS:
        raise ValueError(
            f"{producer!r} rows are converter-written full records "
            "(migrate_v2.py); no producer-facing subset schema exists for them"
        )

    schema = copy.deepcopy(findings_schema_v2())

    # Document level: drop what the pipeline writes, keep the const
    # schema_version (it cannot lie) and the surviving v1 containers.
    for key in _DOC_PIPELINE_ONLY:
        schema["properties"].pop(key, None)
    schema["required"] = [k for k in schema["required"] if k in schema["properties"]]
    if producer == "tool_expert":
        keys = ["coverage", "anatomy", "statistics_register"]
        # REQUIRED ONLY WHEN THE PASS IS ON. With `--figures` off the prose
        # instructing the figure pass is stripped and the tool is removed from
        # the allowlist, and the schema still demanded the array -- an agent
        # required to fill a field nothing told it about and no tool could
        # populate. Structured-output validation then rejects, or the model
        # invents an empty shape to satisfy it.
        if figures:
            keys.append("figures")
        for key in keys:
            if key not in schema["required"]:
                schema["required"].append(key)

    finding = schema["properties"]["findings"]["items"]
    stripped = _NOT_PRODUCER_WRITTEN
    if producer not in ("image_track", "text_track", "raw_data_track"):
        stripped = stripped + _TRACK_ONLY
    if producer != "science_error":
        stripped = stripped + _SCIENCE_ONLY
    for key in stripped:
        finding["properties"].pop(key, None)
    finding["required"] = [k for k in finding["required"] if k in finding["properties"]]

    # The title bound a producer is held to is LOOSER than the stored one:
    # `fit_title` cuts the row back to TITLE_MAX at a word boundary, the full
    # title kept in `notes`. A schema rejection costs a paid turn per
    # resubmission (see `findings_v2.PRODUCER_TITLE_MAX` for the measurement).
    from ...findings_v2 import PRODUCER_TITLE_MAX, TITLE_MAX
    title = finding["properties"]["title"]
    title["maxLength"] = PRODUCER_TITLE_MAX
    title["description"] = (
        f"Aim for at most {TITLE_MAX} characters. A longer title is accepted "
        f"up to {PRODUCER_TITLE_MAX} but stored cut to {TITLE_MAX} at a word "
        "boundary, so put the place and the discrepancy first. "
        + title.get("description", ""))

    # Producers emit the MINIMAL anchor records of spec section 3; the open
    # `additionalProperties` on the full schema exists for the annotator's
    # in-place enrichment, which is exactly what a producer must not forge.
    finding["properties"]["anchors"]["items"]["additionalProperties"] = False
    return schema
