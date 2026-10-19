# Modules and the scheduler (`modules/`, `core/`)

Phase 2 of the modular refactor. A pipeline (docs/specs/pipeline_config.md)
names modules; this document is the contract those modules and the core keep.

## A module is a folder

```
src/forensic_metascience_ai_toolkit/modules/
  <name>/MODULE.md   frontmatter = the module's definition; body = its documentation
  <name>/module.py   MODULE = <instance>; producers implement `run`, the finaliser `finalize`
  base.py            ModuleDef, ModuleResult, Module
  _analyst.py        the two LLM analysts' shared run / parse / retry machinery
  __init__.py        discovery: every `*/MODULE.md` is a module
```

**`MODULE.md` frontmatter.** Unknown keys, missing keys, a name that doesn't
match its folder, or an unknown kind are all errors.

| Key | Meaning |
|---|---|
| `name` | Must equal the folder name. |
| `kind` | `agent`, `deterministic`, `ai_review` or `finalizer`. |
| `producer` | The STORED producer value, hashed into `finding_id`. Never renamed. |
| `label` | The history and run_meta stage label. |
| `order` | Canonical merge order (unique). |
| `options` | Switches a pipeline may set (booleans). |
| `needs` | Modules that must FINISH first. |
| `backend_configurable` | May take its own `backend:` in a pipeline. |
| `display`, `prompt`, `description` | Informational. |

`pipeline_config.MODULES` is this registry. The core never imports a specific
module by name: `modules.load(name)` imports `modules/<name>/module.py` when a
pipeline uses it. Modules are ordinary subpackages, never loaded from file
paths, because frozen-code snapshots, `sys.modules` aliases and worker
pickling all need real import names.

**Adding a module:** add the folder, list it in a pipeline, and add tests.
Agent modules subclass `AnalystModule` and state only what differs: label,
producer, MCP role, allowlist, schema, user prompt, budget share and internet
access.

## The contract

```python
class Module:
    async def run(self, ctx: RunContext, needed: dict[str, ModuleResult]) -> ModuleResult
class Adjudicator(Module):            # the finaliser
    async def finalize(self, ctx, merged, *, docket, image_bundle, text, limitations)
        -> (findings, adj_summary, adjudicator_stage)
```

`ModuleResult` carries:
- `stage`: an agent's CLI stage, or None;
- `doc`: its parsed producer document;
- `record`: a deterministic track's record;
- `limitations`: this module's own;
- `extra`: anything else (an agent's resolved backend settings).

`RunContext` (`core/context.py`) is what a module may read: the pipeline, the
paper and its sources, the text, the run slug, the run-level backend, the
toolset and the budget. A module writes only through `ctx.remember`, which
records the system prompt as sent, and through its own result.

## Scheduling semantics (`core/scheduler.py`)

- **Completion, not success.** A producer starts once every module in its
  `needs` has finished, and it receives their results. It decides for itself
  what a failed dependency means. A dependency's failure never silently skips
  a dependent.
- **No layer barriers.** Modules that need nothing start together. A module
  waits only for what it names. The `stages()` display in `pipeline validate`
  is a reading aid, not a barrier.
- **One barrier: the finaliser.** The core calls the adjudicator (or, when it
  is not configured, `adjudicate.apply_skip`) after every producer has
  finished. The always-on passes run before it, in their fixed order: quote
  verification, reproductions, the harness prepass, second look, and the
  producer-constraint checks.
- **Canonical merge order.** Results are merged by `ModuleDef.order`, never by
  completion order. Rows are tools, then proofreading, then image, then text,
  then raw data. Limitations are the run-level ones first (figure scope, PDF
  stub), then each agent module's, then the image track's, then the raw-data
  module's. Finding-id suffixes and the report
  therefore don't depend on which model answered first.
- **Failures:**
  - The analysts catch their own stage failures. A failure becomes a named
    limitation, and the other analyst carries on. If every configured analyst
    fails, the run raises (`StageError`, or `BackendUnavailable` when the
    backend refused).
  - A module that raises without catching propagates out of the scheduler, as
    the image and text tracks always have.
  - A sole deterministic module that fails makes the run an error
    (`pipeline.outcome`).
- **Cancellation and cleanup.** Every task is registered in the caller's
  background list before anything is awaited. When the run stops,
  `analyze_paper_parallel`'s cleanup cancels and drains them all.

**Change from before Phase 2 (deliberate):** each analyst parses and retries
inside its own task, so the two analysts' repair and retry calls can overlap.
Their limitations are grouped per module instead of interleaved by step. What
is sent to every model is unchanged, as `tests/test_pipeline_parity.py` pins.

## Per-module backends

An agent module, or the adjudicator, may set its own `backend: {name, model,
effort}` in the pipeline file. That most specific setting wins over the
run-level one, which comes from the CLI flag or API keyword, then the
pipeline's `backend:`, then the environment, then the default.
- **Model:** if unset, the module's model is its backend's default, never
  another backend's model.
- **Effort:** if unset, the module inherits the run's effort.
- **Budget:** only Claude has a spend cap, so a budget with any module on
  another backend is refused before anything runs.
- **Run metadata:** a stage on a backend other than the run's records
  `llm_backend` in `run_meta.stages`.

## The OpenRouter backend (Phase 3c)

`backend: {name: openrouter, model: <openrouter slug>}` runs a module on our
own agent loop, `forensic_metascience_ai_toolkit.openrouter_loop`,
launched as a subprocess like the CLIs. It speaks Claude's stream-json, so the
runner, ledger and transcripts need no new branch:

- **Tools:** it starts the MCP servers in the same `--mcp-config` a Claude
  launch receives (same role fence, toolset manifest and paper directory) and
  offers only `--allowedTools`. An off-list tool is refused in the transcript,
  never called. `Read` reads files under the paper directory only.
- **Output:** a `StructuredOutput` tool whose parameters are the schema. An
  invalid call is answered with the validation error; after three retries the
  run ends `error_max_structured_output_retries`, as on Claude.
- **Cost:** OpenRouter's per-response `usage.cost`, summed. No spend cap, so a
  run with `--max-budget-usd` and an OpenRouter module is refused before it starts.
- **Effort** maps `low/medium/high` through and `xhigh/max` to `high`.
  `internet` turns on OpenRouter's `web` plugin.
- **Preflight** checks `OPENROUTER_API_KEY` instead of a CLI binary.

## The image modules need the image package (2026-10-16, v1.77.0)

`image_analysis` requires the separately distributed image
analysis package, reached only through `image_plugin.py`. When it is absent
(or `METASCIENCE_BLOCK_IMAGE_PLUGIN=1`), `image_analysis` returns a record
with `execution_status: unavailable`: the `image_forensics` channel reads
`refused`, the history `image_forensics` component is `unavailable`, a
limitation says the figures were not examined, and the analysts still run.

## One image module (2026-10-18, v1.84.2)

`image_detection` + `image_review` merged into `image_analysis`. The review
module never ran anything: the package's `pipeline.run` owns
detect-then-screen as one unit (its screening ledger and stamps are keyed to
it), and `image_review` only reported what that call had done. The review is
now a switch, `ai_screening` (default true; `false` is the `image_detect`
pipeline). Producer `image_track` and channel/stage label `image_forensics`
are unchanged, so finding ids and every reader of stored runs are too.

The old names do not parse (v1.85.0 removed the brief compatibility layer).
A pipeline's digest changed with the merge, so a partial run recorded under
the old names no longer counts as done for the batch skip and is re-run once.

## The raw-data module (2026-10-15)

`raw_data` runs `copy_paste_detector.detect_paper_duplication` over the
paper's spreadsheets and CSVs (top level plus `raw_track.SUPPLEMENT_SUBDIRS`)
in a child process (`python -m forensic_metascience_ai_toolkit.raw_track`, killed after
`METASCIENCE_RAW_DATA_TIMEOUT`, default 900 s). Opt-in: `raw_data_only`, or
`full_raw_data` (`full` plus this module, still a complete review).

- Producer `raw_data_track`. One QUARANTINED row per (file, kind) with an
  accusatory group -- never one per group (three fixture workbooks gave 2,088
  row-pair groups) -- capped at `QUARANTINE_CAP`, never the headline
  (`adjudicate._unscreened`). Groups, row pairs and rows are separate counts.
- Channel `raw_data`, present only when configured: `did_not_run` when the
  paper has no structured file (nothing read, nothing cleared), `refused` on a
  crash or timeout. The history `copy_paste` component records it
  (`unavailable` when there was nothing to read) instead of `not_requested`.

## Prompts live with their modules (2026-10-15)

An agent module's system prompt is `modules/<name>/prompt.md` (MODULE.md
`prompt: prompt.md`); the text every role shares is `core/prompts/`
(`rulebook.md`, `rulebook_roles.md`, `reproduction.md`, `grok_mcp_route.md`).
`core/prompts/__init__.py` assembles them (the `metascience_agent/prompts/`
package was retired 2026-10-18; schemas are `forensic_metascience_ai_toolkit/schema/`).
`prompts.PROMPT_FILES` maps the old names to them, so `_read("tool_expert.md")`
still works; what is sent is byte-identical (the parity oracle). Scanners of
prompt text read `prompts.prompt_files()`.

## Not yet

- **A module listed twice.** That needs instance identity.
