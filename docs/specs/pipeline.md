# Spec: Parallel Pipeline, Prompts & Backends

> Design record of the 2026-08 overhaul. Sections 3, 4, 9, 10 remain
> normative; the current orchestration contract is docs/specs/modules.md and
> docs/specs/pipeline_config.md.

**Status:** approved 2026-08-21. **Cutover SHIPPED 2026-08-21 (v1.0.0)**:
`two_stage` aliases `parallel` with `mode_requested` recorded. **The serial
body was DELETED in v1.27.0** — ~11,800 lines, after the grok measurement of
2026-09-02 (parallel ≥ legacy recall on all three fixtures, 0–1 false
positives) and after every legacy-only capability was ported or dropped with
its reason recorded. Readers of archived v1 output are untouched.

---

## 1. Pipeline shape

```
resolve sources / extraction
  core/scheduler.py: each module starts when the modules in its `needs:` finish
  ├─ tools_agent (producer tool_expert; no web, no code)
  ├─ scientific_proofreading_agent (producer science_error; web ON, code ON)
  ├─ image_analysis: detect, then AI-screen (optional, separately distributed package)
  ├─ text_forensics (subprocess)
  └─ raw_data (opt-in, subprocess)
     ↓ MERGE in ModuleDef.order: analysts' findings + image rows + text rows
              + raw-data rows + checks_tally       ← merge happens FIRST
     ↓ PRE-adjudication annotators on the MERGED set
  ADJUDICATOR (contract in adjudicator.md) → apply()
     ↓ POST-adjudication annotators
  render_report (structural, from adjudicated findings)
```

Which modules run is chosen by the pipeline file (docs/specs/pipeline_config.md);
when each starts is `core/scheduler.py`, from each module's `needs:`
(docs/specs/modules.md). The image branch belongs to the separately distributed
image analysis package, reached only through `image_plugin.py` (since v1.77.0).
Without the package the `image_forensics` channel reads `refused`, its history
component is `unavailable`, and the analysts still run. With it, the package's
`image_forensics.pipeline.run` owns detection plus screening (since v1.36.0),
on by default in full runs; `--no-image-forensics` disables it. Detection and
screening overlap the analysts; the coordinator awaits the result at the merge.
Image analysis is never exposed as an analyst MCP tool.

The module returns screened v2 `findings`, detector/screening `coverage`,
`limitations`, and `execution_status` (`disabled`, `failed`, `incomplete`, or
`completed`) alongside the legacy detector record. Run metadata retains these
facts; the report renders image coverage through the channel detail. Refusal,
timeout, unresolved screening, and truncated detection cannot read as image
clearance. Other analysts' results survive image failures. The coordinator owns
and awaits background-task cleanup on cancellation or any early exit; screening
releases its own ledger lease on cancellation. Existing artifacts, fingerprints,
and standalone cross-paper operations retain their contracts.

Rules:

- **Merge precedes the pre-adjudication annotators.** Annotators run once, on
  the merged set — never per-producer (a per-producer run would let the two
  agents' quote/ledger adjudications diverge).
- Mandatory image AI screening stays upstream as a producer-side publication
  gate; its decision rides in `inputs.ai_screening`.
- Concurrency is safe as-is (verified): preflight caches per process,
  `usage_guard` serializes on an asyncio.Lock, `record_spend` has no await
  inside; two `claude -p` processes are independent print-mode sessions.
  Accepted risks: joint session-limit overshoot (same exposure batch
  concurrency already accepts) and provider rate limits (→ failure matrix §5).
- As built, `agent._run_stage_requiring_forensic_tools` wraps the tools
  agent's stage (the `ForensicToolsNeverRan` check, plus
  `GROK_EMPTY_DUMP_RETRIES` extra attempts on Grok), and both analysts get
  one bounded retry of an empty report through `retry_if_empty` in
  `modules/_analyst.py`.

## 2. Modes and back-compat

| Mode string | Meaning |
|---|---|
| `parallel` | Canonical name for the pipeline. |
| `two_stage` | A **deprecated alias for `parallel`** since the v1.0.0 cutover — logged, with `mode_requested` recorded in run_meta. The serial body it once named was deleted in v1.27.0. |
| `single_stage` | REMOVED in v1.19.0. It was out of scope for this overhaul and stayed untested for its whole life, which is the worst of both; the 2026-09-02 audit deleted it. |

Any other mode string raises.

> **Enrichment port completed, v1.24.0-v1.25.0.** Beyond the census, three
> more legacy-writer behaviours reached the parallel path: the sandbox audit's
> `guards` block (v1.23.1 — v1.22.0's port had dropped it, leaving the
> viewer's guard pane empty on every parallel run), severity reconciliation
> onto the 1-9 ladder (v1.24.0), and the dispatcher's machine-generated
> refusal list plus the supplement record (v1.25.0).
>
> **DELIBERATELY NOT PORTED: the highlight workbook.**
> `_write_raw_duplication_highlights` re-runs `detect_raw_duplication` on each
> `raw_duplication` finding and writes `forensic_review/highlighted/<stem>.xlsx`,
> which the workbench's spreadsheet pane links when present. It is dropped with
> the legacy writer for two reasons, recorded here so the absence is a decision
> rather than an oversight: v2 findings carry `technique` but not `inputs`, so
> the detector's arguments (`path`, `sheet`, `exclude_columns`) have no source
> in a v2 finding and would have to be reconstructed from the tool ledger; and
> **no archived parallel run has ever produced a `raw_duplication` finding**,
> so the port would ship dormant. Revisit if a real parallel run produces that
> technique — the workbench link degrades to absent, not to a wrong answer.

> **Census port, v1.23.0.** The enrichment block named below now runs on the
> parallel path and attaches to the adjudicated object as
> `findings.v2.json -> coverage_summary`. Six of its blocks were ported
> (`checkable`, `completeness`, `computation_audit`, `statistics_register`
> validation, `text_integrity`, `extraction`). `stage1_reconciliation` was
> deliberately NOT ported: its two inputs are a v1 stage-1 findings list and a
> `report_obj`, neither of which exists in v2, and the question it asks --
> did every produced finding end the run with a disposition -- is answered by
> `adjudication.docket.n_not_adjudicated`. Six further blocks were dropped as
> already answered in v2 (`tools_run` and `stats_found` by `coverage`,
> `stats_checked` and `tables_checked` by `checks_tally`, `harness_sweep` by
> `run_meta.exhaustive_checks`, and `undelivered` in part by
> `run_meta.delivery`).

During migration `parallel` landed BESIDE the old body so A/B eval could
compare the two on the same papers.

## 3. Budget split (Claude backend only; Grok has no spend cap — see §11)

For per-paper budget B:

- tool-expert agent: `0.40 · B`
- science-error agent: `0.25 · B`
- adjudicator: the remainder, subject to `MIN_ADJUDICATOR_BUDGET_USD = 0.20`.
  Below the floor: **skip adjudication** and ship a findings-only result
  (merged, provisional severities, doc-level failure record).
- Report limitation notes name WHICH agent was budget/timeout-truncated
  (a truncated agent must announce itself — the existing invariant, per agent).
- **cross_check stamp (normative, corrected rule):** on ANY
  adjudicator-skip/fail path, every finding carrying `impossible: true` is
  stamped `cross_check: "not_run"`, rendered as a report limitation, and
  **barred from headline use**. Reason: `r_grim_ground_truth` is
  adjudicator-only under the new roles (§6), so with no adjudicator the
  required R cross-check never ran — and an unrun cross-check must never read
  as a passed one (the `_r_unavailable` invariant, inverted).

## 4. Failure matrix (normative)

| Event | Behavior | Batch record |
|---|---|---|
| One agent fails, other survives | Proceed with survivor; loud limitation naming the dead agent; `is_error` true | `partial.jsonl` (cost row recorded) |
| Both agents fail | `StageError` | `failed.jsonl`, spend recorded |
| Adjudicator fails or is skipped (floor/timeout) | **Fail OPEN**: findings ship with provisional severity + `severity_is_provisional: true` + doc-level failure record; `cross_check: "not_run"` stamp per §3. Findings are never lost. | `partial.jsonl` |
| Empty-dump / tools-never-ran (either agent, either backend) | `_run_agent_requiring_output` retries up to `GROK_EMPTY_DUMP_RETRIES`, per agent; both attempts billed | — |
| Image/text track subprocess fails | As today: named channel state, never a silent absence | — |
| Preflight failure | Fails CLOSED before any spend, re-raised without a `failed.jsonl` row (environment fault) — unchanged | — |
| Usage-guard probe failure | Fails OPEN — unchanged; one guard call covers each agent stage | — |

## 5. Annotator relocation

The plan for splitting the legacy chain around the adjudicator is below. As
built, the chain lives in `parallel.py`: `_coordinate_analysis` runs quotes,
reproductions, the harness prepass, the second-look worklist and the checks
tally before the adjudicator, then anchors, consequence and the reassurance
scan after it; `_write_parallel_outputs_impl` runs sourcing, severity
reconciliation and the census. Where this table and the code differ (for
example consequence, sourcing and severity reconciliation now run after the
adjudicator), the code is current.

| Pass (legacy name) | Planned position | Note |
|---|---|---|
| quotes (provenance adjudication) | PRE | must precede everything reading `provenance_verdict` |
| reproductions | PRE | reproduction strings checked before the docket |
| exhaustive checks | PRE | |
| consequence | PRE | feeds the adjudicator's severity question |
| severity reconciliation (tool-verdict join) | PRE | the docket needs `tool_verdict` populated |
| uncomputed / supplied-norm / unanchored-norm clamps | PRE (on provisional) **and** POST (re-applied to final 1–9 via severity9 caps) | clamps may never be weaker after adjudication than before |
| sourcing | PRE | copies quote verdicts onto findings |
| second_look worklist | PRE | handed to the adjudicator as input |
| titles | POST | operates on final records; adjudicator title rewrites preserved |
| 1–9 clamps (`severity9` channel caps, quarantine, +2 upgrade limit) | POST | code-enforced, per adjudicator.md — no ceiling (v1.14.0); merged pattern findings are EXEMPT from the +2 upgrade limit |
| anchors (`anchors.annotate_findings`, Part C) | POST (finalizer) | never fails the run |
| web_unbacked / code_unbacked (NEW, §9) | PRE | fabrication guards must be visible to the adjudicator |

## 6. Registry roles

`registry.py` replaces `STAGE1`/`STAGE2` with three roles. Deprecated aliases
(`STAGE1_TOOLS`/`STAGE2_TOOLS`) are kept through migration and deleted at
Phase 7. The rename + snapshot regen is ONE commit.

Counts below are the 2026-08 design. At 1.77.0, `registry.stage_tools` gives
TOOL_AGENT 56, SCIENCE_AGENT 17 (the 15 below plus `check_effect_plausibility`
and `paired_d_interval`) and ADJUDICATOR 42; the registry is the record.

- **TOOL_AGENT** — the 54-tool stage-1 set of 2026-08, byte-for-byte unchanged.
  It does NOT get `check_flow_arithmetic`: CONSORT/flow is the science agent's
  territory (prevents double-counting the same mismatch across producers).
- **SCIENCE_AGENT** — exactly these 15 registry tools (13 existing + the new
  flow tool + the Phase-0 code-execution tool), plus harness `Read` and web
  (§9): `extract_pdf`, `extract_xml`, `extract_html`, `get_table`,
  `parse_table`, `parse_cells_typed`, `parse_cells_as_declared`,
  `check_summation`, `check_summation_batch`, `check_ratio`,
  `check_count_percent`, `check_statistic_bounds`, `check_flow_arithmetic`
  (NEW), `reconstruct_2x2`, and `run_python_script` (NEW — the sandboxed
  code-execution MCP tool per the Phase-0 resolution, §10;
  SCIENCE_AGENT-stage only, never on the other roles).
  Exclusions are stated in its prompt as handoff rules phrased as
  **categories, never tool names** (§8).
- **ADJUDICATOR** — today's 39-tool stage-2 set + `check_flow_arithmetic`
  (40 total), plus `Read`; **no web, no code** (reconciliation R2: the
  spot-check surface is escalation-safe because `apply()` caps bind in code).
  The stage2-only tools `check_proportion_from_normal` and
  `r_grim_ground_truth` become adjudicator-only — cross-checks before
  publishing top-severity claims are its job by name.

`tests/test_tool_exposure.py` gains: three-way agreement on the three roles
(MCP server / CLI / role allowlists); a science-prompt mirror of the
recommends-only-callable-tools test; and a DISJOINTNESS test pinning that no
GRIM/SPRITE/statcheck tool name appears in `science_error.md`. Weakening the
disjointness test is how guards stop guarding — fix the prompt, not the test.

## 7. New tool: `check_flow_arithmetic`

`src/metascience_agent/tools/flow.py`, pure function, result dict with
`severity` per repo convention.

**Input shape:**

```jsonc
{
  "stages": [                       // ordered; the CONSORT cascade top-down
    { "label": "assessed",  "n": 240,
      "excluded": [ {"reason": "declined", "n": 12},
                    {"reason": "ineligible", "n": 28} ],   // optional
      "arms": [ {"label": "treatment", "n": 100},
                {"label": "control",   "n": 100} ] }        // optional
  ],
  "randomized_label": "randomized"  // optional; names the stage the
}                                   // analyzed≤randomized check anchors on
```

**Checks (all exact integer arithmetic — no tolerance):**
1. Step arithmetic: `stages[i+1].n == stages[i].n − Σ stages[i].excluded[].n`
   whenever `excluded` is supplied.
2. Arms sum-to-total: for any stage carrying `arms`, `Σ arms[].n == n`.
3. Monotonicity: no later stage's `n` (nor any arm total) exceeds the
   randomized stage's `n`.
4. Attrition accounting: a drop between stages with NO `excluded` entries is
   flagged, not condemned.

**Failure modes** (distinct `failure_mode` values, never fused):
`step_mismatch`, `arms_dont_sum`, `analyzed_exceeds_randomized`,
`unaccounted_attrition` (this one is **capped `suspicious`** — papers
legitimately omit attrition reasons).

**Evidence class:** `EVIDENCE_ABSOLUTE`. `impossible` only when EVERY number
in the failing identity was supplied as printed by the paper; any assumed or
absent operand → guard path → `indeterminate` (a tool pointed at the wrong
data must refuse, not accuse).

**Wiring checklist (per CLAUDE.md, all steps mandatory):**
1. `tools/flow.py` + export in `tools/__init__.py`.
2. `ToolSpec` in `registry.py` with `stages = {SCIENCE_AGENT, ADJUDICATOR}`
   (MCP wrapper and allowlists derive; nothing to edit elsewhere).
3. `technique` enum: automatic once Part A's registry-derived enum lands; in
   Phase 3 (pre-Part-A-enum) add `check_flow_arithmetic` to
   `findings.v2.schema.json` by hand (the v1 file is gone as of v1.27.0).
4. CLI verb `flow-check` in `cli.py`; registry `cli="flow-check"`.
5. Model guidance in the ToolSpec `description` + rulebook rule 15 (§8).
6. `tests/test_flow.py`; regenerate `tests/data/registry_snapshot.json`;
   `CASES` entry in `tests/test_registry_equivalence.py`.

## 8. Prompt suite

Assemblers in `core/prompts/__init__.py` (`prompts/__init__.py` until 2026-10-18): `tool_expert_system_prompt()`,
`science_error_system_prompt()`, `adjudication_system_prompt()`.
`grok_mcp_route.md` is appended per backend as today.

The file names below are the design-time names. Since 2026-10-15 each agent's
text is `modules/<name>/prompt.md` (`tool_expert.md` is
`modules/tools_agent/prompt.md`, `science_error.md`
`modules/scientific_proofreading_agent/prompt.md`, `adjudication.md`
`modules/adjudicator/prompt.md`) and the shared text (`rulebook.md`,
`rulebook_roles.md`, `reproduction.md`, `grok_mcp_route.md`) is
`core/prompts/`. `prompts.PROMPT_FILES` maps the old names to these files.
`stage2_editorial.md` no longer exists. The analysts no longer receive a CLI
map: reproductions are generated (`core/prompts/reproduction.md`), and
`registry.cli_syntax_reference` is not sent.

**`tool_expert.md`** (evolves from `stage1_sweep.md`):
- Carries over VERBATIM: tool discipline, `source_quote`/locator rules, the
  figures section (strippable; markers byte-identical), Procedure, Pass 0/0b.
- Drops: the "textual and semantic flags" item (moves to the science agent).
- Adds: the two-analyst mission paragraph + handoff rule; output section =
  the findings-v2 **producer subset** schema with an embedded example JSON;
  severity framed as two axes (evidence verdict enum + provisional 1–9 from
  the severity9 rubric).

**`science_error.md`** (NEW) — section outline, in order:
1. **Mission** — main text ONLY, entire paper, source-priority order
   (XML → HTML → PDF-via-cache); **no supplements** — "the other agent reads
   them".
2. **Scope boundary** (load-bearing) — handoff rules phrased as CATEGORIES,
   never tool names: "digit-granularity, dispersion and duplication checks
   belong to the other analyst"; suspicion in a foreign category becomes an
   `unchecked` note, not a finding. (A tool-name list would fail §6's
   disjointness test; weakening that test instead is forbidden.)
3. **CONSORT / patient-flow procedure** — enumerate every N → build
   stages/arms → `check_flow_arithmetic`; denominator drift via
   `check_ratio`/`check_count_percent`; the no-mental-arithmetic law restated.
4. **Contradiction hunting** — claims register; quote BOTH passages verbatim.
5. **Factual verification with internet** — proteins/genes, antibody catalog
   numbers, misidentified cell lines; lookups are for FACTS — never search
   the paper's title/authors/critiques (independence preserved); prefer
   primary databases.
6. **Citation-of-lookup discipline** — every lookup-based claim records
   `web_sources [{url, title, quote, accessed}]`; an unrecorded lookup did
   not happen (the pipeline checks the ledger, §10); memory-based factual
   claims are capped and marked `basis: model_knowledge`.
7. **Code execution** — scripts only for un-tooled arithmetic/data-wrangling;
   load-bearing numbers come only from captured script output or tool
   results; every script is persisted (§10); no network in the shell.
8. **Severity** — two axes + the severity9 rubric.
9. **Output discipline** — findings-v2 producer subset with embedded example
   JSON showing three findings: a CONSORT mismatch at level 5, a reagent
   mismatch with `web_sources` at level 4, an internal contradiction at
   level 3.

**Shared material:**
- The rulebook stays ONE file, gaining a "who each rule binds" preamble table
  (tool expert / science agent / adjudicator per rule) and **rule 15** (flow
  arithmetic, web-fact, and code discipline). The severity intro is rewritten
  for the two axes.
- Ladder text is emitted by `severity9.rubric_markdown()` at assembly time —
  no separate ladder .md to drift (reconciliation R1; supersedes the
  `severity_ladder.md` idea). `severity9.py` IS the ladder;
  `docs/errorlevels.md` is its narrative appendix -- rationale and worked
  cases for people, read by no code, and deliberately kept out of the
  prompts (its cases carry a venue-prestige calibration bias).
- `registry.cli_syntax_reference(stage=)` gains a role filter so each agent's
  CLI map names only tools that agent can call.

**Prompt-contract tests:** each embedded example JSON is validated against the
LIVE producer-subset schema by a test (an example that rots is a guard that
stopped guarding); the disjointness and recommends-only-callable tests per §6.

## 9. Internet + code mechanics per backend

One seam: `internet: bool` + `code: bool` parameters on `build_invocation`.

**Claude — tool-expert agent (and adjudicator):** unchanged from today.
`--tools Read`; `--disallowedTools "Bash Edit Write NotebookEdit WebFetch
WebSearch Task ToolSearch"`; `--allowedTools` = the role's
`mcp__forensic_metascience__*` names; `--mcp-config` + `--strict-mcp-config`.
Today's no-web argv stays **byte-pinned** by the existing fixture.

**Claude — science-error agent (normative; corrected per the Phase-0 spike
RESULTS — code execution is the `run_python_script` MCP tool of §10, never a
backend shell):**
- `--tools` = `Read,WebSearch,WebFetch` (built-ins ONLY — the spike proved
  WebSearch rides `--tools`). **MCP tools are NOT named in `--tools`.** They
  are delivered exactly as today's byte-pinned production argv delivers
  them: `--mcp-config` + `--strict-mcp-config` serves the server,
  `--allowedTools` lists the SCIENCE_AGENT role's
  `mcp__forensic_metascience__*` names (including `run_python_script`) for
  auto-approval, and off-list MCP calls are the ledger's audited
  `forensic_mcp_offlist` surface — the same soft-enforcement-plus-audit
  contract every existing stage runs under. (An earlier draft required the
  MCP names inside `--tools`; REVERSED — untested against the CLI, and the
  live mechanism demonstrably delivers the tools. The underlying concern
  survives as a TEST, not an argv shape: a Phase-3 integration assertion
  that a science-agent invocation actually exposes its 15 registry tools —
  init-event tool discovery, the `mcp_discovery` machinery — so "zero
  registry tools configured" can never ship silently.)
- Denied list: `Bash`, `Edit`, `Write`, `NotebookEdit`, `Task`, `ToolSearch`
  (loses ONLY the web pair relative to today — **Bash/Write stay DENIED**
  per the Phase-0 resolution, §10; no shell ever opens).
- A SECOND pinned argv fixture covers the internet+code variant.
- Phase-0 spike RESULTS (2026-08-21, run): WebSearch WORKS under
  `claude -p --tools WebSearch` — a normal `tool_use` event in the stream
  (ledger-visible), correct answer, billed inside `total_cost_usd`; the
  documented WebFetch-only fallback is NOT needed. The CLI provides NO Bash
  sandbox (its "sandboxes with no internet access" help text is only the
  skip-permissions recommendation) — hence the §10 resolution.

**Grok — science-error agent:**
- `--tools read_file,web_search,web_fetch`, **plus the always-on
  `search_tool`/`use_tool` meta-tools — Grok's ONLY route to the MCP server
  (and, through it, to `run_python_script`) — which must never appear in any
  deny list.**
- `--disallowed-tools` drops only `web_fetch`, `web_search` (retains
  `run_terminal_cmd`, `write`, `search_replace`, `spawn_subagent` —
  **run_terminal_cmd/write stay DENIED** per the Phase-0 resolution, §10).
  Kebab-case flag only; camelCase `--disallowedTools` is a no-op on Grok.
- Per-role MCP restriction stays deny-complement via `grok_deny_rules`
  derived from `registry.SPECS` — never a hand list.

**`normalize_event` additions** (ledgers/archives stay byte-comparable across
backends): `web_search → WebSearch`, `web_fetch → WebFetch`,
`run_terminal_cmd → Bash`, `write → Write`, each carrying a `grok_meta_tool`
breadcrumb like the existing `use_tool` rewrite. (Under the §10 resolution
`run_terminal_cmd`/`write` stay denied on both agents, so those two mappings
should only ever fire on a surface-breach event — the mapping is kept so a
breach is named in Claude vocabulary.)

**Ledger surfaces:** the existing enum
(`forensic_mcp | harness | builtin_allowed | UNVALIDATED`) gains `web`
(WebSearch/WebFetch when on the agent's allowlist) and `agent_code`
(`run_python_script` calls, science agent only — the locked decision gives
sandbox_audit this surface for that stage alone). `validated` stays `False`
for both — web text and ad-hoc code are never validated evidence, even
though `run_python_script` rides the forensic MCP server.

**`_sandbox_audit`:** parameterized by the agent's ACTUAL denied list +
internet/code flags — no more hardcoded `DENIED_TOOLS` description. A web or
code call by a no-web/no-code agent is a named surface breach.

**Script persistence:** BY CONSTRUCTION — the MCP server writes every
`run_python_script` script to `<review_dir>/analysis_code/NNN_label.py`
before executing it (§10); there is no collection step to forget.
`reproduction_kind` gains `script` pointing at the persisted file (R4). Findings gain `computed_by:
registry_tool | agent_code | model_reading | deterministic_track`;
`agent_code` is legal only on `producer: science_error` rows, caps
provisional severity at 4, and can never reach `impossible` (structural, per
findings_v2.md).

**Fabrication guards — all three ship with KNOWN-POSITIVE tests** (a guard
that never fires is indistinguishable from a broken one, LESSONS #4):
1. `web_unbacked` annotator: a finding citing `web_sources` against an empty
   web ledger must flag.
2. `code_unbacked` annotator: computed numbers citing a script with no
   matching `run_python_script` call must flag.
3. Adjudicator `evidence_quote` fabrication: a clear whose quote cannot be
   located in the paper is demoted to `kept` (contract in adjudicator.md;
   the known-positive lives with the pipeline tests).

## 10. Guardrail-4 contingency (BINDING) — RESOLVED by the Phase-0 spikes

A limitation sentence does **not** satisfy the network-off-shell guardrail.
**Phase-0 result (2026-08-21, spikes run):** the CLI provides NO Bash sandbox,
so the contingency resolves to a DESIGN CHANGE, strictly stronger than the
approved (a) harness-sandbox / (b) code-disabled fallback — **code execution
is an MCP tool, not a backend shell**:

- New registry tool **`run_python_script(code, label)`** on the forensic MCP
  server, `stages = {SCIENCE_AGENT}` only. The server writes the script to
  `<review_dir>/analysis_code/NNN_label.py`, executes it under `unshare -rn`
  (verified working unprivileged on this box; `bwrap --unshare-net` as
  fallback; NEITHER available → structured refusal with `code_disabled`)
  with the venv python, cwd = scratch, paper dir read-only, a timeout, and
  captured stdout/stderr returned as the result.
- ONE implementation, byte-identical on Claude AND Grok (Grok reaches MCP via
  `use_tool` anyway): network isolation enforced in OUR code, scripts
  persisted by construction, every call in the forensic ledger.
- `Bash`/`Write` (Claude) and `run_terminal_cmd`/`write` (Grok) stay DENIED
  on both agents — no shell ever opens.
- `run_meta` records `{mcp_sandbox: unshare|bwrap}` or `code_disabled`. Grok
  is covered by the same rule by construction (same server, same sandbox) —
  never merely a second `sandbox_limitation` sentence.

**Wiring (per the CLAUDE.md checklist, decided):** `run_python_script` gets a
`ToolSpec` in `registry.py` with `stages = frozenset({SCIENCE_AGENT})` so the
MCP server and deny-complements derive it like any tool — but it is
INFRASTRUCTURE, not a forensic technique: **no CLI verb** (`cli=None`; a
code-backed finding's reproduction is `reproduction_kind: "script"` pointing
at the persisted `analysis_code/` file — a CLI verb would duplicate that
badly), **excluded from the generated `technique` enum** exactly as the
extraction tools are (the enum generator carries an explicit
`NON_TECHNIQUE_TOOLS` set — extraction tools + `run_python_script` — with a
test pinning membership), and the registry snapshot + `CASES` entry are
regenerated deliberately per checklist step 8. Ledger surface: its calls
classify `agent_code`, `validated: False` — the sandbox_audit surface the
locked decision names — even though the call rides the forensic MCP server
(NORMATIVE resolution of the critic's open question #2).

## 11. Grok parity checklist

*Historical.* This is the pre-cutover checklist; its boxes were never ticked
in this file. Grok runs the parallel pipeline (`--backend grok`); see
CHANGELOG.md for what shipped and when.

Every item must hold before Grok is offered on the parallel mode:

- [ ] Identical prompt bytes per agent (assemblers shared; only
      `grok_mcp_route.md` differs, appended per backend as today).
- [ ] Full role tool access via `search_tool`/`use_tool`; meta-tools absent
      from every deny list; per-role restriction by deny-complement from
      `registry.SPECS`.
- [ ] Science-agent web/code toggles per §9; guardrail-4 (a)/(b) resolved and
      recorded — Grok is not exempt.
- [ ] `normalize_event` maps the four new tool names; ledgers byte-comparable
      with Claude runs (existing test pattern extended).
- [ ] `GROK_EMPTY_DUMP_RETRIES` wired through `_run_agent_requiring_output`
      for BOTH agents (two empty-dump exposures per paper, both billed —
      accepted risk).
- [ ] No spend cap on Grok (`supports_budget=False`): the §3 budget split
      does not apply; wall-clock + `--max-turns` are the only brakes, and
      run_meta says so.
- [ ] `sandbox_weaker=True` recorded in run_meta; report language reflects it.
- [ ] `GROK_MCP_OUTPUT_BYTES` override preserved (20 KB default truncates
      real `extract_pdf` output — measured 2026-08-18).
- [ ] Pinned argv fixture for the Grok science-agent variant.
- [ ] One live Grok gold-paper run at Phase 7 (master verification list).

## 11b. Codex parity checklist

Every item must hold before Codex is offered on the parallel mode (all
measured against codex-cli 0.147.0, 2026-09-01):

- [x] Identical prompt bytes per agent: the MCP tool names Codex shows the
      model are the SAME `mcp__forensic_metascience__*` strings Claude uses
      (measured via a live tool-inventory canary), so no codex-specific route
      preamble exists at all — nothing to drift.
- [x] System prompt via `AGENTS.md` in the per-run sandbox (`-C <run_dir>`),
      `project_doc_max_bytes` raised (default 32 KiB truncates the
      tool-expert prompt; 108 KB canary measured intact).
- [x] MCP isolation via `--ignore-user-config` + `-c mcp_servers.*`
      overrides; the user's config.toml is never loaded and never written.
      `--disable apps` is mandatory: without it ~130 foreign
      `mcp__codex_apps__*` tools appear EVEN under `--ignore-user-config`.
- [x] The operator's skills stay out of the prompt:
      `-c skills.include_instructions=false` (2026-10-11). Codex lists
      `~/.agents/skills` from disk whatever the config says; a terra science
      agent read a synced `SKILL.md` as its first call before this.
- [x] The shell is the Read analog, so the sandbox audit files a shell call
      made only of text reads (`rg`, `grep`, `cat`, `head`, `tail`, `wc`,
      `pdftotext`, print-only `sed -n`, `find` without actions; pipes, `;`
      and redirects to `/dev/null`) as `builtin_allowed`
      (`agent._shell_reads_only`). Anything else stays a severe breach.
- [x] Cost is unknown, not zero: stages record `cost_reported: False`,
      run_meta names them in `cost_unreported_stages`, and the webapp index
      shows no cost for such a run.
- [x] `enabled_tools` narrowing derived from the registry stage allowlist;
      `METASCIENCE_MCP_STAGE` env fence stays the enforced layer.
- [x] `default_tools_approval_mode="approve"` present — without it MCP calls
      fail under `approval_policy="never"` and the model was measured
      fabricating the tool's verdict afterwards.
- [x] Internet delta is exactly one `-c tools.web_search` value; the
      no-internet form pins `allowed_domains` to an unresolvable sentinel,
      because `false` alone does NOT detach the web tool (measured: the
      fetch succeeded; the sentinel blocked it).
- [x] Stateful normalizer maps the codex event stream onto Claude shapes;
      ledgers byte-comparable (`command_execution`→Bash, `web_search`→
      WebSearch, forensic `mcp_tool_call`→`mcp__forensic_metascience__*`,
      foreign servers UNVALIDATED); golden fixture is a real captured
      stream.
- [x] Status-line heartbeat (v1.13.1): a progress snapshot per stream
      event, "thinking" during reasoning items, and the token segment
      hidden (`live_tokens: False`) because codex reports usage only in
      the final `turn.completed` — measured 6.5 minutes of healthy silence
      otherwise read as a hang.
- [x] No spend cap AND no turn cap (`supports_budget=False`, no
      `--max-turns`): wall-clock + stall watchdog are the only brakes;
      `max_turns_unsupported` is stamped into the stage payload rather than
      silently dropped or fatally raised (the repair call passes
      `max_turns=1` on every backend).
- [x] No cost figure in the stream: stage cost stays 0.0, degraded like
      Grok's, never synthesized.
- [x] `sandbox_weaker=True` with a codex-specific limitation sentence (the
      read-only shell is kept as the file-read analog — decided 2026-09-01).
- [x] `tool_output_token_limit` set explicitly (codex's analog of the Grok
      20 KB truncation lesson); ceiling leaves ~10x headroom over the
      largest measured `extract_pdf` output.
- [x] Empty-dump retry NOT extended to codex — it is a measured Grok
      pathology; extend only if live codex runs reproduce it.
- [x] Pre-spend liveness: direct stdio JSON-RPC handshake with our own
      server (`codex doctor --json` is config-consistency only, durationMs=0
      measured); the `ForensicToolsNeverRan` ledger gate stays the backstop.
- [x] One live Codex gold-paper run, read end-to-end per the standing
      read-the-output rule. MEASURED 2026-09-01, apple_cider, gpt-5.6-sol
      effort high, 28m58s: verdict `does_not_reconcile` (matches gold), 20
      findings (8 severity-bearing: 2xS5 1xS4 2xS3 2xS2 1xS1, 0 discarded),
      tool agent 235/235 ledger calls `forensic_mcp` validated (zero
      unvalidated, zero off-list), every finding's `inputs` restored to a
      real dict by the strict-schema round-trip, provenance recorded
      backend/binary-version/limitation sentence. The first attempt is the
      reason the strict transform exists: both stages died on the API's
      strict-schema validator before it.

## 11c. Antigravity parity checklist

Measured against agy 1.4.2, 2026-10-18 (`--backend antigravity`, alias `agy`;
`metascience models --backend antigravity` lists the account's models live).

- [x] Prompt never on argv: `-p` takes its prompt as a value, so it is
      `--print=` with the turn sent down stdin as one
      `{"event":"user","message":{"content":...}}` line under
      `--input-format stream-json` (`prompt_delivery="stdin_stream_json"`).
- [x] Config isolation: there is no `--mcp-config`, `--system-prompt` or
      config-home variable, so every launch runs under its own `HOME`
      (`~/.cache/metascience/antigravity-sandbox/run-<uuid>/home`). Auth is
      in the OS keyring and survives it (measured). The forensic server is
      handed the REAL `HOME` back, or its receipts would be deleted with the
      sandbox.
- [x] System prompt as a custom agent's body (`--agent forensic`): rule
      files (`AGENTS.md`) are capped at 24 KB; a 156 KB agent body arrived
      with canaries at start, middle and end. `inheritCustomizations: false`
      keeps the operator's skills, rules and plugins out.
- [x] Built-in allowlist: `excludeDefaultComponents: true` plus `tools:
      [view_file, finish]` (+ `search_web`, `read_url_content` for the
      internet-on science agent). The model then reported 8 tools (the CLI
      adds `call_mcp_tool`, `list_resources`, `read_resource`,
      `manage_task`), no shell, no browser, no subagents. Permission rules
      deny `command(*)`, `unsandboxed(*)`, `write_file(*)`, `execute_url(*)`
      and (no-internet) `read_url(*)`; a `run_command` was refused by them.
- [x] `finish` must be listed: it carries `--json-schema` output, and
      without it no `structured_output` appears. agy validates the document
      itself (a bad `schema_version` was rejected and corrected in-turn), so
      there is no strict-dialect rewrite.
- [x] A turn that ends WITHOUT `finish` (measured: `status: SUCCESS`,
      `response: ""`) is mapped to `error_max_structured_output_retries`, so
      the analysts' and adjudicator's one corrective retry fires, and
      `core/prompts/antigravity_route.md` (appended to every launch) says
      the answer counts only through `finish`.
- [x] The schema-gate retry RESUMES the conversation (`--conversation
      <id>`, the run dir kept for it): a resumed turn kept its context
      (measured), and the first eval's tools agent had stopped after setup,
      which no fresh or tool-less retry can continue.
- [x] Stateful normalizer: `call_mcp_tool {ServerName, ToolName,
      Arguments}` -> `mcp__<server>__<tool>`; a wrong server name stays
      UNVALIDATED. Large MCP results arrive as `output: ""` and are read back
      from `brain/<conv>/.system_generated/steps/<n>/output.txt`
      (`agy_output_spilled`); a 53 KB `extract_xml` result reached the model
      complete.
- [x] Pre-spend liveness: the stdio handshake Codex uses. agy drops a server
      that fails to start without any event and exits 0 (measured).
- [x] Role fence: `METASCIENCE_MCP_STAGE` in the server env plus
      `enabledTools`; an off-list `grimmer_check` was refused.
- [x] Model and effort: a slug (`gemini-4-argon-high`) is sent alone (agy
      exits 1 on a slug plus a different `--effort`); a base name gets
      `--effort` clamped to what the model offers (no agy model has
      `xhigh`/`max`).
- [x] Usage guard: `agy -p /usage --output-format json` is free; only the
      quota groups the run's model draws on count (Gemini vs Claude-and-GPT;
      Argon has its own weekly bucket).
- [x] No spend cap, no turn cap, no cost figure: `supports_budget=False`,
      `max_turns_unsupported` stamped, cost 0.0 with `cost_reported: False`.
- [ ] One live gold-paper run read end to end (`metascience eval --paper
      apple_cider --backend antigravity`). NOT YET RUN: only single-tool
      smoke stages on gemini-3.8-flash-low have been measured.
- [ ] Image screening on antigravity (vision): `view_file` on a PNG is
      unmeasured, and the image package's evidence check has no agy branch.

## 12. Report path

- `render_report` keeps every structural guarantee: headline-first,
  severity-ordered findings, "what we could NOT check", figure-blindness
  limitation.
- Sort key becomes severity 1–9 descending, with a legacy string fallback for
  archived v1 runs. Level labels render as
  `Level 6 — results unreliable (retraction candidate)` (text from
  `severity9`).
- **`report_markdown` dies.** The narrative slot is the adjudicator's bounded
  `summary`; verdict/confidence come from the adjudicator's paper-level
  block; per-finding `plain` → `description`.
- The existing enrichment block (not_checked seeding, machine refusals,
  checkable census, completeness, statistics register, undelivered files,
  reconciliation) attaches to the ADJUDICATED object. Reconciliation now
  answers "did every finding from EITHER producer end adjudication with a
  disposition" via the explicit dismissed/merged lists — discarded findings
  are RETAINED with `adjudication.action: "discarded"`, never deleted
  ("ran and discarded" must stay distinguishable from "did not run").
- **Dual emission in Phase 1 (normative, corrected rule):** the image/text
  track row builders construct v2 records internally but a down-map converts
  to v1 at the injection point until Phase 4's parallel mode consumes v2
  natively. The live `two_stage` path validates the merged document against
  schema 1.0 and every consumer reads v1 keys until Phase 6 — a raw v2 row
  injected in Phase 1 would fail `--json-schema` or render wrongly for three
  phases.

## 13. run_meta and review-output file naming

- run_meta stage keys: `tool_agent`, `science_agent`, `adjudicator`
  (+ tracks). `stage1`/`stage2` result-dict ALIASES are kept for exactly ONE
  release for existing readers, then removed.
- Stage meta gains `internet` (bool), `n_web_calls`, and — science agent
  only — `n_scripts`; plus the §10 sandbox field.
- `parallel.write_parallel_outputs` emits, per run directory (labels
  `tool_agent`, `science_agent`, `adjudicator`):
  `prompt.{label}.md` (the user turn) and `system_prompt.{label}.md`,
  `toolcalls.{label}.json`, `messages.{label}.json`
  (`messages.{label}_unfiled.json` when an unfiled-results recovery ran),
  `receipts.{label}.jsonl` when the tool layer kept receipts,
  `adjudication.json` (RAW adjudicator output, pre-`apply()`),
  `analysis_code/` (persisted science-agent scripts),
  `sandbox_audit.json` (per-stage union, as today),
  `findings.v2.json` as the APPLIED v2 document (`schema_version: "2.0"`),
  `report.md` (plus `report.pdf`, best effort) and `run_meta.json`.
  (The design said `prompt.{label}.txt` and an applied `findings.json`; the
  code writes the names above.)

## 14. Phase-4 additions (from the verification passes; normative)

*Historical.* Item 1's `v2_pending` state was never implemented:
`webapp_index.py` reads v2 findings documents directly.

1. **Minimal scanner fallback:** `webapp_index.py` must read the v2 findings
   docs that A/B `parallel` runs will now produce — either map 2.0 → the v1
   index shape or record a named `v2_pending` state. It must never crash and
   never mis-rank the workbench for the two phases before the full index v2.
2. **One cheap live science-agent run** on a real CONSORT-bearing paper,
   output read per LESSONS ("read the OUTPUT"), before Phase 4 closes. No
   CONSORT fixture exists today, so the science agent is otherwise untested
   until Phase 7 — a miscalibration discovered there forces rework across
   Phases 3–4. The Phase-7 eval fixture is built FROM this run.

## 15. Test impact

New or changed suites (beyond per-tool tests already listed):

- `tests/test_flow.py` — the §7 checks, failure modes, guard paths.
- Registry snapshot regen + `test_registry_equivalence` `CASES` entry for
  `check_flow_arithmetic`; the role-rename commit regenerates the snapshot.
- `tests/test_tool_exposure.py` — three-way role agreement; science-prompt
  recommends-only-callable mirror; the science_error.md disjointness test.
- `tests/test_prompt_contract*` — embedded example JSON validates against the
  live producer subset (both agent prompts); rulebook who-binds preamble
  present; rubric text sourced from `severity9.rubric_markdown()`.
- `tests/test_llm_backend*` / argv pins — existing no-web byte pin unchanged;
  NEW pinned fixtures: Claude science agent (internet+code, INCLUDING MCP
  names) and Grok science agent; `normalize_event` mapping tests for the four
  new names.
- `tests/test_sandbox_*` — parameterized `_sandbox_audit`; web/code call by a
  no-web/no-code agent is a breach; `web_unbacked` + `code_unbacked`
  KNOWN-POSITIVE tests.
- `tests/test_parallel_pipeline.py` (NEW) — the §4 failure matrix, budget
  split + floor skip + `cross_check: "not_run"` stamp, mode alias +
  `mode_requested`, merge-before-annotators ordering, run_meta stage keys and
  one-release aliases, file-naming contract (§13).
- `webapp/test/smoke.mjs` / `tests/test_webapp_index.py` — the `v2_pending`
  fallback never crashes and never reads as a clean paper.
- Eval changes (fixture relabeling to 1–9 intervals, judge on severity9, the
  CONSORT-rich fixture) are Phase 7 and owned by the master plan's A8 —
  findings_v2.md §9 owns only the `deterministic.py` v2 validation slice.

**Versioning:** Phase 3 and Phase 4 each end with a MINOR bump + CHANGELOG
entry (a prompt or severity-semantics change makes reviews across the
boundary incomparable). Phase 7 carries the MAJOR (1.0.0, output schema
break).
