"""Pipeline configuration: which modules run, and which tools the tools agent gets.

A pipeline is a YAML file (shipped ones live in `pipelines/`; any path works)
resolved here into a validated `PipelineConfig`. Unknown keys, modules and
tools are ERRORS, never ignored: a misspelt `adjudicater:` that silently ran
no adjudication would be the absence-as-evidence failure this project exists
to refuse.

    schema_version: 1
    name: full
    backend: {name: claude, model: opus, effort: high}
    modules:
      - use: tools_agent
        tools: all              # or [grim_check], {toolset: grim_family}, {exclude: [...]}
      - use: scientific_proofreading_agent
      - use: image_analysis     # options: {ai_screening: false} -> detection only
      - use: text_forensics
      - use: adjudicator        # delete this line -> no adjudication

`full` reproduces the pipeline as it ran before this file existed, exactly:
the same prompts, allowlists and commands (pinned by tests). Module and
display names are new; the STORED producer values (`tool_expert`,
`science_error`) are not, because `findings_v2.finding_id` hashes them.

Phase 1 of the modular refactor (see docs/specs/pipeline_config.md): the
config gates the existing orchestration in `parallel.py`; nothing moves.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = 1
PIPELINES_DIR = Path(__file__).resolve().parent / "pipelines"
TOOLSETS_FILE = PIPELINES_DIR / "toolsets.yaml"
DEFAULT_PIPELINE = "full"


class PipelineConfigError(ValueError):
    """The pipeline file is not valid. The message names the key and the fix."""


# Module definitions live in each module's MODULE.md (`modules/`); this is
# the same mapping, read once. `ModuleDef` stays importable from here.
from .modules import ModuleDef, definitions as _module_definitions  # noqa: E402

MODULES: dict[str, ModuleDef] = dict(_module_definitions())

#: The analysts whose joint presence, with the adjudicator and the whole
#: toolset, makes a run a COMPLETE review. Image and text tracks have always
#: been optional inside a complete review (`--no-image-forensics`), so they do
#: not count toward it.
COMPLETE_REVIEW_MODULES = frozenset(
    {"tools_agent", "scientific_proofreading_agent", "adjudicator"})

#: Modules that always call a model (image_analysis does only with
#: `ai_screening` on; text_forensics and raw_data never do).
LLM_MODULES = COMPLETE_REVIEW_MODULES

#: Readers and the table dispatcher. Every tools-agent toolset includes them:
#: a check without a way to read the paper is not a smaller experiment, it is
#: a broken one. `check_table` dispatches only to ENABLED checks.
CORE_TOOLS = frozenset({
    "extract_pdf", "extract_xml", "extract_html", "get_table",
    "extract_supplement", "get_supplement_table",
    "parse_cells_typed", "parse_cells_as_declared", "parse_table",
    "check_table",
})

#: Options whose default is TRUE. An option at its default is not recorded, so
#: writing the default out does not change a pipeline's digest.
OPTION_DEFAULTS = {("image_analysis", "ai_screening"): True}

#: The figure pass's tools: present only with `figures: true`.
FIGURE_TOOLS = frozenset({"extract_figures"})

#: The tool fence, process-boundary version. The pipeline sets it on the MCP
#: server's environment (beside METASCIENCE_MCP_STAGE); the server registers
#: only these tools and `check_table` dispatches only to them. The model has no
#: way to write it. Unset means "the role's whole surface" -- every run before
#: pipelines, and every operator-launched server.
MCP_TOOLS_ENV = "METASCIENCE_MCP_TOOLS"


def enabled_tools_from_env() -> frozenset[str] | None:
    """None ONLY when the variable is absent. Present-but-empty is an empty
    manifest -- which the server refuses -- never "no manifest": an empty
    value must not read as "the whole surface"."""
    import os
    raw = os.environ.get(MCP_TOOLS_ENV)
    if raw is None:
        return None
    return frozenset(t.strip() for t in raw.split(",") if t.strip())


_TOP_KEYS = {"schema_version", "name", "description", "backend", "modules"}
_BACKEND_KEYS = {"name", "model", "effort"}
_MODULE_KEYS = {"use", "tools", "options", "backend", "tool_access"}

#: How an agent module reaches its tools (Phase 3b, docs/specs/tool_access.md):
#:   mcp        -- the MCP server with each tool's full description (default).
#:   mcp_brief  -- the same server, each description cut to its first
#:                 sentence, plus a `describe_tool` call for the rest.
#:   skill      -- no MCP server: the agent runs `metascience tool run ...` in
#:                 a shell fenced to that command (claude backend only).
#: The default is never written into the record, so every run before this
#: key existed keeps its digest.
TOOL_ACCESS = ("mcp", "mcp_brief", "skill")
DEFAULT_TOOL_ACCESS = "mcp"
_TOOLS_KEYS = {"toolset", "exclude", "include"}


def _tool_agent_tools() -> list[str]:
    from .registry import TOOL_AGENT, stage_tools
    return list(stage_tools(TOOL_AGENT))


@dataclass(frozen=True)
class ModuleSpec:
    use: str
    tools: tuple[str, ...] | None = None    # resolved toolset; tools_agent only
    options: dict[str, Any] = field(default_factory=dict)
    backend: dict[str, str] = field(default_factory=dict)   # per-module override
    tool_access: str = DEFAULT_TOOL_ACCESS                  # agent modules only

    @property
    def definition(self) -> ModuleDef:
        return MODULES[self.use]


@dataclass(frozen=True)
class PipelineConfig:
    name: str
    modules: tuple[ModuleSpec, ...]
    backend: dict[str, str] = field(default_factory=dict)
    description: str = ""
    source: str = ""                        # path or "<flags>"

    # -- queries -----------------------------------------------------------
    def has(self, module: str) -> bool:
        return any(m.use == module for m in self.modules)

    def module(self, module: str) -> ModuleSpec | None:
        return next((m for m in self.modules if m.use == module), None)

    def option(self, module: str, key: str, default=None):
        spec = self.module(module)
        return default if spec is None else spec.options.get(key, default)

    @property
    def figures(self) -> bool:
        return bool(self.option("tools_agent", "figures", False))

    @property
    def toolset(self) -> tuple[str, ...] | None:
        """The tools agent's resolved tools, or None when it is not configured."""
        spec = self.module("tools_agent")
        return None if spec is None else spec.tools

    @property
    def full_toolset(self) -> bool:
        """Every tool-agent tool (figure tools aside) is enabled."""
        tools = self.toolset
        if tools is None:
            return False
        want = set(_tool_agent_tools()) - FIGURE_TOOLS
        return want <= set(tools)

    @property
    def uses_llm(self) -> bool:
        """Some module calls a model: an agent, the adjudicator, or the image
        module with its AI screening on. `image_detect` and `raw_data_only`
        call none, so they need no backend."""
        for spec in self.modules:
            if spec.use == "image_analysis":
                if spec.options.get("ai_screening", True):
                    return True
            elif spec.use in LLM_MODULES:
                return True
        return False

    @property
    def complete_review(self) -> bool:
        """Both analysts, the whole toolset and the adjudicator. Only such a
        run may stand as a paper's review: a one-tool run that called itself
        `full_review` would be read as the paper having been examined."""
        return (COMPLETE_REVIEW_MODULES <= {m.use for m in self.modules}
                and self.full_toolset)

    def resolved(self) -> dict:
        """Canonical, fully-resolved form: what the run records and hashes."""
        return {
            "schema_version": SCHEMA_VERSION,
            "name": self.name,
            "backend": dict(sorted(self.backend.items())),
            "modules": [
                {"use": m.use,
                 **({"tools": sorted(m.tools)} if m.tools is not None else {}),
                 **({"options": dict(sorted(m.options.items()))}
                    if m.options else {}),
                 **({"backend": dict(sorted(m.backend.items()))}
                    if m.backend else {}),
                 **({"tool_access": m.tool_access}
                    if m.tool_access != DEFAULT_TOOL_ACCESS else {})}
                for m in sorted(self.modules, key=lambda m: m.use)],
        }

    @property
    def digest(self) -> str:
        blob = json.dumps(self.resolved(), sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    def record(self) -> dict:
        """The `pipeline` block written into run_meta and findings.v2."""
        return {**self.resolved(), "digest": self.digest,
                "complete_review": self.complete_review,
                "source": self.source}

    def describe(self) -> str:
        """Human-readable resolved plan (`metascience pipeline validate`)."""
        scope = ("complete review" if self.complete_review
                 else "PARTIAL: not a complete review")
        lines = [f"pipeline {self.name!r}  digest {self.digest}  ({scope})"]
        if self.backend:
            lines.append("backend: " + ", ".join(
                f"{k}={v}" for k, v in sorted(self.backend.items())))
        for stage_no, stage in enumerate(stages(self), 1):
            lines.append(f"stage {stage_no}:")
            for m in stage:
                d = m.definition
                extra = ""
                if m.tools is not None:
                    extra = (f"  tools: all ({len(m.tools)})" if self.full_toolset
                             else f"  tools ({len(m.tools)}): {', '.join(sorted(m.tools))}")
                if m.options:
                    extra += "  options: " + ", ".join(
                        f"{k}={v}" for k, v in sorted(m.options.items()))
                if m.tool_access != DEFAULT_TOOL_ACCESS:
                    extra += f"  tool_access: {m.tool_access}"
                lines.append(f"  - {m.use} [{d.kind}]{extra}")
        if not self.has("adjudicator"):
            lines.append("adjudication: NOT CONFIGURED -- severities stay provisional")
        return "\n".join(lines)


def stages(config: PipelineConfig) -> list[list[ModuleSpec]]:
    """Modules grouped by dependency depth. The adjudicator needs every
    producer, so it always forms the last stage. Display only in Phase 1:
    `parallel.py` still owns the actual concurrency."""
    depth: dict[str, int] = {}
    producers = [m for m in config.modules if m.definition.kind != "finalizer"]

    def _depth(name: str) -> int:
        if name not in depth:
            needs = [n for n in MODULES[name].needs if config.has(n)]
            depth[name] = 1 + max((_depth(n) for n in needs), default=-1)
        return depth[name]

    for m in producers:
        _depth(m.use)
    out: list[list[ModuleSpec]] = []
    for m in producers:
        while len(out) <= depth[m.use]:
            out.append([])
        out[depth[m.use]].append(m)
    finalizers = [m for m in config.modules if m.definition.kind == "finalizer"]
    if finalizers:
        out.append(finalizers)
    return out


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def _keys(d: Any, allowed: set[str], required: set[str], where: str) -> None:
    if not isinstance(d, dict):
        raise PipelineConfigError(f"{where}: expected a mapping, got {type(d).__name__}")
    extra = set(d) - allowed
    if extra:
        raise PipelineConfigError(
            f"{where}: unknown key(s) {sorted(extra)}; allowed: {sorted(allowed)}")
    missing = required - set(d)
    if missing:
        raise PipelineConfigError(f"{where}: missing key(s) {sorted(missing)}")


def load_toolsets(path: Path = TOOLSETS_FILE) -> dict[str, list[str]]:
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise PipelineConfigError(f"{path}: expected a mapping of toolset -> tools")
    known = set(_tool_agent_tools())
    out: dict[str, list[str]] = {}
    for name, tools in raw.items():
        if not isinstance(tools, list) or not all(isinstance(t, str) for t in tools):
            raise PipelineConfigError(f"{path}: toolset {name!r} must be a list of tool names")
        unknown = sorted(set(tools) - known)
        if unknown:
            raise PipelineConfigError(
                f"{path}: toolset {name!r} names unknown tool(s) {unknown}")
        out[str(name)] = list(tools)
    return out


def _resolve_tools(raw: Any, figures: bool, where: str) -> tuple[str, ...]:
    known = _tool_agent_tools()
    known_set = set(known)
    if raw is None or raw == "all":
        chosen = [t for t in known if t not in FIGURE_TOOLS]
    elif isinstance(raw, list):
        if not all(isinstance(t, str) for t in raw):
            raise PipelineConfigError(f"{where}.tools: every entry must be a tool name")
        chosen = list(raw)
    elif isinstance(raw, dict):
        _keys(raw, _TOOLS_KEYS, set(), f"{where}.tools")
        base: list[str]
        if "toolset" in raw:
            sets = load_toolsets()
            name = raw["toolset"]
            if name not in sets:
                raise PipelineConfigError(
                    f"{where}.tools.toolset: unknown toolset {name!r}; "
                    f"known: {sorted(sets)}")
            base = list(sets[name])
        else:
            base = [t for t in known if t not in FIGURE_TOOLS]
        chosen = base + [t for t in (raw.get("include") or []) if t not in base]
        exclude = raw.get("exclude") or []
        bad = sorted(set(exclude) & CORE_TOOLS)
        if bad:
            raise PipelineConfigError(
                f"{where}.tools.exclude: {bad} are readers/dispatch the tools "
                "agent cannot work without; they are always included")
        unknown = sorted(set(exclude) - known_set)
        if unknown:
            raise PipelineConfigError(
                f"{where}.tools.exclude: unknown tool(s) {unknown}")
        chosen = [t for t in chosen if t not in set(exclude)]
    else:
        raise PipelineConfigError(
            f"{where}.tools: expected 'all', a list of tools, or a mapping "
            "with toolset/include/exclude")
    unknown = sorted(set(chosen) - known_set)
    if unknown:
        raise PipelineConfigError(
            f"{where}.tools: unknown tool(s) {unknown}. The tools agent's tools "
            f"are listed by `metascience pipeline tools`.")
    figure_named = sorted(set(chosen) & FIGURE_TOOLS)
    if figure_named and not figures:
        raise PipelineConfigError(
            f"{where}.tools: {figure_named} belong to the figure pass; set "
            "`options: {figures: true}` instead of listing them")
    resolved = set(chosen) | CORE_TOOLS | (FIGURE_TOOLS if figures else set())
    # Registry order, so the allowlist and the prompt are deterministic.
    return tuple(t for t in known if t in resolved)


def _parse_backend(raw: Any, where: str) -> dict[str, str]:
    _keys(raw, _BACKEND_KEYS, {"name"}, where)
    from .llm_backend import _BACKENDS
    if raw["name"] not in _BACKENDS:
        raise PipelineConfigError(
            f"{where}.name: unknown backend {raw['name']!r}; "
            f"known: {sorted(_BACKENDS)}")
    return {k: str(v) for k, v in raw.items() if v is not None}


def parse(raw: Any, source: str = "<string>") -> PipelineConfig:
    """Validate a parsed YAML mapping into a PipelineConfig."""
    _keys(raw, _TOP_KEYS, {"schema_version", "modules"}, source)
    if raw["schema_version"] != SCHEMA_VERSION:
        raise PipelineConfigError(
            f"{source}: schema_version must be {SCHEMA_VERSION}, "
            f"got {raw['schema_version']!r}")
    backend: dict[str, str] = {}
    if raw.get("backend") is not None:
        backend = _parse_backend(raw["backend"], f"{source}.backend")
    entries = raw["modules"]
    if not isinstance(entries, list) or not entries:
        raise PipelineConfigError(f"{source}.modules: expected a non-empty list")
    specs: list[ModuleSpec] = []
    seen: set[str] = set()
    for i, entry in enumerate(entries):
        where = f"{source}.modules[{i}]"
        if isinstance(entry, str):
            entry = {"use": entry}
        _keys(entry, _MODULE_KEYS, {"use"}, where)
        use = entry["use"]
        if use not in MODULES:
            raise PipelineConfigError(
                f"{where}.use: unknown module {use!r}; known: {sorted(MODULES)}")
        if use in seen:
            raise PipelineConfigError(
                f"{where}.use: module {use!r} listed twice (running one module "
                "more than once arrives with the module interface, Phase 2)")
        seen.add(use)
        d = MODULES[use]
        options = entry.get("options") or {}
        _keys(options, set(d.options), set(), f"{where}.options")
        for key, value in options.items():
            # Every option today is a switch. `figures: "false"` is truthy, and
            # a typo must not turn on the figure pass.
            if not isinstance(value, bool):
                raise PipelineConfigError(
                    f"{where}.options.{key}: expected true or false, got "
                    f"{value!r}")
        options = {k: v for k, v in options.items()
                   if OPTION_DEFAULTS.get((use, k), False) is not v}
        module_backend: dict[str, str] = {}
        if entry.get("backend") is not None:
            if not d.backend_configurable:
                raise PipelineConfigError(
                    f"{where}.backend: {use!r} calls no model of its own; only "
                    "agent modules and the adjudicator take a backend")
            module_backend = _parse_backend(entry["backend"], f"{where}.backend")
        tool_access = entry.get("tool_access", DEFAULT_TOOL_ACCESS)
        if "tool_access" in entry:
            if d.kind != "agent":
                raise PipelineConfigError(
                    f"{where}.tool_access: {use!r} is not an agent module; only "
                    "the analysts reach tools on their own")
            if tool_access not in TOOL_ACCESS:
                raise PipelineConfigError(
                    f"{where}.tool_access: expected one of {list(TOOL_ACCESS)}, "
                    f"got {tool_access!r}")
        tools = None
        if use == "tools_agent":
            tools = _resolve_tools(entry.get("tools", "all"),
                                   bool(options.get("figures", False)), where)
        elif "tools" in entry:
            raise PipelineConfigError(
                f"{where}.tools: only tools_agent takes a tools list")
        specs.append(ModuleSpec(use=use, tools=tools, options=dict(options),
                                backend=module_backend, tool_access=tool_access))
    for spec in specs:
        missing = [n for n in spec.definition.needs if n not in seen]
        if missing:
            raise PipelineConfigError(
                f"{source}: module {spec.use!r} needs {missing}, which the "
                "pipeline does not list")
    name = str(raw.get("name") or Path(source).stem or "pipeline")
    return PipelineConfig(name=name, modules=tuple(specs), backend=backend,
                          description=str(raw.get("description") or ""),
                          source=source)


def resolve_backend_settings(config, backend=None, model=None, effort=None):
    """Backend, model and effort for a run: an explicit argument (CLI flag or
    API keyword) wins, then the pipeline file, then the caller's own default
    (env / DEFAULT_EFFORT, applied later). The file's model belongs to the
    file's backend and is not carried onto another one. ONE rule, used by the
    API, `analyze` and both batch entry points."""
    declared = (config.backend if config is not None else {}) or {}
    backend = backend or declared.get("name")
    if model is None and declared.get("model") and (
            backend is None or backend == declared.get("name")):
        model = declared["model"]
    effort = effort or declared.get("effort")
    return backend, model, effort


def available() -> list[str]:
    """Names of the shipped pipelines."""
    return sorted(p.stem for p in PIPELINES_DIR.glob("*.yaml")
                  if p.name != TOOLSETS_FILE.name)


def load(name_or_path: str | Path | None = None) -> PipelineConfig:
    """A shipped pipeline by name, or any YAML file by path."""
    target = str(name_or_path or DEFAULT_PIPELINE)
    path = Path(target)
    if not (path.suffix in (".yaml", ".yml") or path.is_file()):
        path = PIPELINES_DIR / f"{target}.yaml"
        if not path.is_file():
            raise PipelineConfigError(
                f"unknown pipeline {target!r}; shipped pipelines: {available()} "
                "(or pass a path to a .yaml file)")
    if not path.is_file():
        raise PipelineConfigError(f"pipeline file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PipelineConfigError(f"{path}: not valid YAML ({exc})") from exc
    source = (path.stem if path.parent == PIPELINES_DIR else str(path))
    return parse(raw, source=source)


def from_flags(*, image_forensics: bool = True, text_forensics: bool = True,
               figures: bool = False, segment_montages: bool = False,
               reassemble_tiles: bool = False) -> PipelineConfig:
    """The pipeline the pre-config flags describe. `analyze_paper` callers that
    pass no pipeline get exactly this, so their runs are unchanged."""
    modules: list[dict] = [
        {"use": "tools_agent", "tools": "all",
         **({"options": {"figures": True}} if figures else {})},
        {"use": "scientific_proofreading_agent"},
    ]
    if image_forensics:
        opts = {k: v for k, v in (("segment_montages", segment_montages),
                                  ("reassemble_tiles", reassemble_tiles)) if v}
        modules.append({"use": "image_analysis", **({"options": opts} if opts else {})})
    if text_forensics:
        modules.append({"use": "text_forensics"})
    modules.append({"use": "adjudicator"})
    config = parse({"schema_version": SCHEMA_VERSION, "name": DEFAULT_PIPELINE,
                    "modules": modules}, source="<flags>")
    return config


def from_record(record: dict | None) -> PipelineConfig | None:
    """Rebuild a run's config from its recorded `pipeline` block (None for a
    run that predates pipelines -- callers treat that as the flag default)."""
    if not isinstance(record, dict) or "modules" not in record:
        return None
    raw = {"schema_version": record.get("schema_version", SCHEMA_VERSION),
           "name": record.get("name"),
           **({"backend": record["backend"]} if record.get("backend") else {}),
           "modules": [
               {"use": m["use"],
                **({"tools": list(m["tools"])} if "tools" in m else {}),
                **({"options": m["options"]} if m.get("options") else {}),
                **({"backend": m["backend"]} if m.get("backend") else {}),
                **({"tool_access": m["tool_access"]} if m.get("tool_access") else {})}
               for m in record["modules"]]}
    return parse(raw, source=str(record.get("source") or "<record>"))
