# Pipelines (`pipeline_config.py`)

A pipeline says which **modules** a run uses and which **tools** the tools
agent may call. It is a YAML file. The shipped ones live in
`src/forensic_metascience_ai_toolkit/pipelines/`, and any path works.

```yaml
schema_version: 1
name: tools_grim
description: Tools agent with GRIM only, no adjudication.
backend: {name: claude, model: opus, effort: high}   # optional
modules:
  - use: tools_agent
    tools: [grim_check]          # or all | {toolset: grim_family, include: [...], exclude: [...]}
    options: {figures: false}
```

```bash
metascience pipeline list                      # shipped pipelines
metascience pipeline validate my.yaml          # resolved plan; calls no model
metascience pipeline show tools_grim           # what a run records (JSON)
metascience pipeline tools                     # tools-agent tools and named toolsets
metascience run tools_grim <paper> --backend claude   # = analyze <paper> --pipeline tools_grim
metascience analyze <paper> --pipeline tools_grim --backend claude
metascience batch <corpus> --pipeline no_adjudication --backend claude
```

**Unknown keys, modules and tools are errors.** A misspelt `adjudicater`
must never silently run with no adjudication.

## Modules

| Module | Kind | Stored producer | What it is today |
|---|---|---|---|
| `tools_agent` | agent | `tool_expert` | the tools agent, formerly "tool expert" (`modules/tools_agent/prompt.md`) |
| `scientific_proofreading_agent` | agent | `science_error` | the scientific proofreading agent, formerly "science-error analyst" (`modules/scientific_proofreading_agent/prompt.md`) |
| `image_analysis` | AI review | `image_track` | the image detector, then AI screening of its candidates (`ai_screening: false`: detector only). Formerly `image_detection` + `image_review` (no longer accepted) |
| `text_forensics` | deterministic | `text_track` | tortured phrases |
| `raw_data` | deterministic | `raw_data_track` | the copy-paste detector over the paper's spreadsheets and CSVs (order 60, opt-in) |
| `adjudicator` | finaliser | — | the findings adjudicator |

**The stored producer values do not change.** `findings_v2.finding_id` hashes
the producer. Renaming `tool_expert` would give every future finding a new id,
and reviews would stop carrying across runs.

**Options:**
- `tools_agent`: `figures`.
- `image_analysis`: `ai_screening` (default true), `segment_montages`, `reassemble_tiles`.

**Backend precedence:** a CLI flag or API keyword, then the pipeline file's
`backend`. On the CLI that is the end of it: `analyze`, `run` and `batch`
refuse to start without one when the pipeline calls a model
(`cli._require_backend`, `PipelineConfig.uses_llm`). An API caller falls
through to `METASCIENCE_LLM_CLI`, then the default. The file's `model`
applies only to the file's own backend. One function,
`resolve_backend_settings`, used by the API, `analyze` and both batch entry
points. Options are booleans; anything else is refused.

**`tool_access`** (agent modules): `mcp` (default, never recorded),
`mcp_brief` or `skill`; see docs/specs/tool_access.md. Shipped arms:
`full_brief`, `full_skill`.

**`image_analysis` with `ai_screening: false`** (the shipped `image_detect`):
the detector alone, candidates filed unscreened (Phase 4; see
`modules/image_analysis/MODULE.md`).

**The image module needs the image package.** `image_analysis` (and so `image_only`, `image_detect` and the image branch of
`full`) require the separately distributed image analysis package, reached
through `image_plugin.py`. Without it the `image_forensics` channel reads
`refused` and the rest of the pipeline runs; in `image_only` or `image_detect`
there is nothing else, so the run is an error (`pipeline.outcome`; see
docs/specs/modules.md).

**Raw data** (opt-in): `raw_data_only` runs the `raw_data` module alone;
`full_raw_data` is `full` plus `raw_data`, still a complete review. Its rows
are quarantined (docs/specs/modules.md, `modules/raw_data/MODULE.md`).

**Not available yet:**
- **A module listed twice.** That needs a design for instance identity.
- **Per-module budgets.** (Per-module backends arrived in Phase 2; see
  docs/specs/modules.md.)

## Toolsets

A toolset can be:
- `all`: every tools-agent tool except the figure pass's;
- a list of tools;
- a named set from `pipelines/toolsets.yaml`, with optional `include` and `exclude`.

**Readers and `check_table` are always included** (`CORE_TOOLS`). A check that
cannot read the paper is broken, not a smaller experiment. **`extract_figures`
comes only with `options: {figures: true}`.**

A restricted toolset is enforced in four places:

1. **The allowlist:** `Read` plus the toolset (`parallel.tool_agent_tools`).
2. **The MCP server.** `METASCIENCE_MCP_TOOLS` is set on the server's
   environment by every backend (Claude and OpenRouter `--mcp-config`, Codex
   `-c mcp_servers`, Grok `.grok/config.toml`, Antigravity its per-run sandbox
   config). The server intersects it with the role's surface
   and **fails closed**: if the stage is missing or unknown, a tool is unknown,
   or nothing is left to serve, it refuses to start. Without a manifest, the
   role-only behaviour is unchanged.
3. **`check_table`.** A disabled check is never called. It lands in `not_run`
   with "tool not enabled in this pipeline". This covers the split
   `n (%)` path too.
4. **The harness prepass.** The duplication and sd_range sweeps run only when
   their tool is enabled. The claim sweep has no registry tool, so it is off
   under any restricted toolset. Without a tools agent the prepass does not run.

The toolset scopes **the tools agent and the harness**. The proofreading agent
and the adjudicator keep their role surfaces.

**Prompts:**
- **System prompt.** The step-3 bullets and CLI-map lines of disabled tools are
  dropped, and a note names the tools that are available. Any statistic that
  needs a missing tool is to be recorded in `unchecked`.
- **User turn.** The `statcheck` instruction is dropped when `statcheck` is off.
- **Partial pipelines.** Every agent is told which colleagues are absent: no
  tools agent, no proofreading agent, or no adjudicator.
- **Complete reviews** keep their historical prompts, byte for byte.

## What a partial run may claim

`complete_review` is true only when all of these run:
- the tools agent, with the whole toolset;
- the proofreading agent;
- the adjudicator.

The image and text tracks have always been optional inside a complete review.

**A partial run is never the paper's review:**
- findings.v2 and run_meta carry a `pipeline` block. The harness writes it, and
  producers never see it.
- `run_kind` returns `partial_review`, or `image_track` for an image-only pipeline.
- The history parent component is `partial_review`, not `comprehensive`, so the
  workbench's paper summary does not pick it up. Its findings are still
  uploaded (`history_db.REPORT_COMPONENTS`), under `runs.kind`
  `partial_review`.
- The workbench's `latest` selection leaves it out of counts, severity and the
  queue. The paper page shows a paper's newest partial run only when the paper
  has no complete review (`Repository.partial_fallback`), and says so; a run
  picker labels it with its pipeline, e.g. "tools only · provisional".
- `corpus_stats` skips it.
- The review directory is named after the pipeline:
  `forensic_review_<pipeline>_<model>_v<release>`.

**Batch skip** (`agent.completed_review`):
- A full batch counts any complete review, whatever its options.
- A partial pipeline counts only runs with the same resolved digest.

**Adjudication not configured:**
- It goes through the same finaliser as every other skip, `apply_skip`, with
  `skipped_reason`.
- It is not an error (`is_error`).
- The database's `runs.status` stays `partial`, because the readback derives
  `adjudication.ran` from `status == "complete"`.

Also kept out of the paper's review: the workbench's default selection
(explicit run selection still reaches a partial run), the index's verdict and
worst severity, and drafts (only when its findings are named, with its scope
in the payload). `report.md` opens with a PARTIAL PIPELINE banner; the
viewer's run facts name the pipeline. A partial run's JSON repair is tool-free
(Claude); on Codex and Grok, which cannot drop their built-in tools, the repair
is not attempted and the unparsed output is a named limitation (fail closed).
Tools-agent rows filed under a disabled tool are dropped and counted either way;
reproductions of disabled tools are not executed. A failed sole deterministic
module (image-only, text-only) makes the run an error, and `pipeline.outcome`
(`ok | incomplete | error`, on run_meta and findings.v2) keeps a failed
experiment from satisfying the batch skip.

## Provenance

`run_meta.pipeline` holds:
- the resolved configuration and its digest;
- `system_prompt_sha256` for each agent label, computed on the prompt as sent.

`prompt_sha256` is computed from `prompts.prompt_blob(config)`, which covers
the configured agent modules only. For a complete review it is the historical
tool + science + adjudicator trio.

`runs.build_fingerprint(config)` and `build_matches` recompute the expected
hash from the run's own recorded pipeline. A run that predates pipelines
counts as `full`.

## Roadmap

This was Phase 1 of the modular refactor. All later phases are done:
`modules/` and the `needs:` scheduler (Phase 2, docs/specs/modules.md); tool
folders (3a); `metascience tool`, receipts, generated reproductions and
`tool_access` (3b, docs/specs/tool_access.md); the OpenRouter loop (3c);
image detection without AI review (4); display names (5, `names.py`).
The raw-data module and prompts in module folders followed (1.76).
