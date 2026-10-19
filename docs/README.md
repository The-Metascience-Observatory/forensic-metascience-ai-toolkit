# docs/

Start with the repository's [README](../README.md) (what the toolkit does and
how to run it) and [CLAUDE.md](../CLAUDE.md) (environment, architecture,
correctness invariants; `AGENTS.md` is the same file). Benchmarks, including
the paid gold-paper eval, are indexed in [benchmarks/README.md](../benchmarks/README.md). Read
[LESSONS.md](../LESSONS.md) before measuring anything. This folder holds the
detail those point to.

Where a document and the code disagree, the code wins; say so in the document.
Image analysis is a separate, privately distributed package; its documentation
lives in that repository, not here.

## Contracts (current; code and tests cite these paths and section numbers)

| Document | What it specifies |
|---|---|
| [specs/modules.md](specs/modules.md) | Module folders (`MODULE.md`, `module.py`, `prompt.md`), the scheduler, per-module backends, raw-data and image modules. **The current pipeline shape.** |
| [specs/pipeline_config.md](specs/pipeline_config.md) | Pipeline YAML, `metascience pipeline …` / `metascience run`, toolsets, partial runs |
| [specs/pipeline.md](specs/pipeline.md) | The 2026-08 design of the parallel pipeline: budget split, failure matrix, roles, backends, output file names. Design record; §3, §4, §9, §10 normative |
| [specs/findings_v2.md](specs/findings_v2.md) | The findings record and document: fields, producers, finding ids, severity rules |
| [specs/adjudicator.md](specs/adjudicator.md) | The adjudicator: docket, what `apply()` may and may not change, failure modes |
| [specs/anchors.md](specs/anchors.md) | Per-finding location anchors and how the viewer finds a quote |
| [specs/tool_access.md](specs/tool_access.md) | `tool_access` modes (`mcp`, `mcp_brief`, `skill`) and the skill-mode fence |
| [specs/webapp_db.md](specs/webapp_db.md) | The local findings database (Postgres): schema, `db-push`, proof queries |
| [workbench_storage.md](workbench_storage.md) | The review workbench: local SQLite cache, sync journal, review outbox, media |
| [analysis_history.md](analysis_history.md) | Versioned run history (`.analysis_runs/`), the `history-*` commands |
| [tool_reference.md](tool_reference.md) | Every forensic tool for humans: when it applies, what it refuses, its CLI verb. Sent to no model; `metascience tool list` / `describe` is the live source |

## Doctrine and decisions

| Document | Why read it |
|---|---|
| [errorlevels.md](errorlevels.md) | The 1-9 severity ladder explained for humans, with worked cases. [severity_ladder.json](severity_ladder.json) is the generated machine copy (do not edit by hand) |
| [GRIM_CONTEXT_DEPENDENCY.md](GRIM_CONTEXT_DEPENDENCY.md) | Nineteen innocent reasons a GRIM "impossible" can appear. Read before acting on one |
| [FORENSIC_INTEGRITY_HARDENING.md](FORENSIC_INTEGRITY_HARDENING.md) | The cardinal rule (no false accusations), recurring failure patterns, a contributor checklist |
| [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) | Open and decided design questions, dated |
| [WHITEPAPER_checks_we_declined.md](WHITEPAPER_checks_we_declined.md) | Why some published checks (STALT "hidden tiny p") are not accusation-grade |
| [HAIKU_IN_THE_LOOP.md](HAIKU_IN_THE_LOOP.md) | Whether a secondary model writes into a review (it does not), and the tripwire for it |
| [VALUE_REGISTER_DESIGN.md](VALUE_REGISTER_DESIGN.md) | The value register (`value_register.json`): every reported number, typed and linked |
| [DIGITS_PLAN.md](DIGITS_PLAN.md) | Proposed, not started: a last-digit-preference check on individual observations (Carlisle 2021), and why it is IPD-only |
| [SPOT_ANALYSIS.md](SPOT_ANALYSIS.md) | What the SPOT benchmark (Son et al. 2025) measures, and what to adopt from it |

## Elsewhere in this folder

- [reference/](reference/README.md): Heathers, *An Introduction to Forensic
  Metascience* (CC-BY 4.0), which the doctrine cites by line.
- [reviews/](reviews/): dated engineering audits, unedited.
- [archive/](archive/README.md): finished or abandoned design notes,
  measurements and handoffs. Historical; each opens with what is still true.
