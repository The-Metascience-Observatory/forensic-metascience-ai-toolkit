# AGENTS.md

> **Read `LESSONS.md` before measuring anything or wiring anything up.**
> It records the recurring errors this project keeps repeating -- absence read as
> evidence, wrong denominators, code built and never consumed, guards that
> silently stop guarding, stale numbers in prompts, reading source instead of
> output -- each as a numbered rule with one real example (`LESSONS #4`).


This repo is the **Forensic Metascience AI Toolkit** (formerly the Agent for Forensic
Metascience; GitHub `delton137/forensic-metascience-ai-toolkit`; pip distribution
`forensic-metascience-ai-toolkit`). The import package is still `metascience_agent` and
the CLI is still `metascience`.

Guidance for working in this repo. See [README.md](README.md) for user-facing usage
and [docs/README.md](docs/README.md) for an index of the specs and design notes
(current contracts in `docs/specs/`, finished work in `docs/archive/`).
**This file is the one copy of the project guidance.** `CLAUDE.md` is a
one-line `@AGENTS.md` import so Claude Code loads it too; edit here, never
there. Backend behavior comes from the code, not the assistant reading this
file.

## What this is

An AI agent that analyzes scientific papers for statistical inconsistencies and
data-integrity anomalies. `llm_backend.py` dispatches the configured Claude Code,
Codex, Grok or Antigravity (`agy`; per-run `HOME`, see `docs/specs/pipeline.md`
§11c) backend, or `openrouter` (our own agent loop, `openrouter_loop.py`,
which speaks Claude's stream-json and needs `OPENROUTER_API_KEY`); do not substitute backend names into package names or
CLI syntax. On the CLI `--backend` is REQUIRED for `analyze`/`run`/`batch` (a
pipeline file's `backend:` also counts; `METASCIENCE_LLM_CLI` does not;
`image_detect`/`raw_data_only` call no model and need none):
`cli._require_backend`, `PipelineConfig.uses_llm`. The stdio MCP server exposes **62 of 64 registered tools** (the two
withheld are the CLI-only `analyze_paper_images` and `detect_tortured_phrases`, see
below; the two `r_*_ground_truth` tools shell to R and ARE exposed; the rest
are pure Python). Registry roles
gate access: 58 tools are callable by the TOOL_AGENT, 17 by the SCIENCE_AGENT,
42 by the ADJUDICATOR; 55 have a CLI command, 2 are CLI-only by design and are
**not** listed on the MCP server. Analysis (v1.0.0, `mode="parallel"`; see
`docs/specs/pipeline.md`; the current module/scheduler shape is
`docs/specs/modules.md`) runs **two analysts concurrently** — the *tools
agent* (numbers/tables/supplements, no internet, no code; formerly the "tool
expert", stored producer `tool_expert`) and the *scientific proofreading
agent* (methodology/contradictions/CONSORT flow, internet on, sandboxed
`run_python_script`; formerly the "science-error analyst", stored producer
`science_error`) — then an **adjudicator** merges, verifies and assigns
each finding's final 1–9 severity into a findings-v2 document.
`mode="two_stage"` is a deprecated ALIAS for the same pipeline, and the only
other accepted value. **The serial sweep→editorial pipeline was DELETED in
v1.27.0** (~11,800 lines, after the measurement under §Testing & eval showed
parallel ≥ legacy on all three fixtures). Everything that READS its output
still works -- `bundle.py`, `webapp_index.py`, `migrate_v2.py`, `runs.py` and
the archive verbs -- because deleting a writer is not deleting a reader.

## Environment (read this first)

- **Use the interpreter the `metascience` console script points at** — the
  one with `claude-agent-sdk`, `mcp` AND `statcheck` installed; the system
  `python3` has none of them. It is MACHINE-SPECIFIC (a dedicated venv such
  as `~/.venvs/metascience-agent/bin/python` on one machine, a conda install
  on another), so never assume a literal path from this file:
  `metascience python` prints the interpreter the CLI itself runs under
  (`sys.executable`), and `tests/test_docs_accuracy.py` pins that this file
  stays path-neutral.
  ```bash
  PY=$(metascience python)
  $PY -c "import statcheck; print('ok')"
  metascience preflight      # names every dependency; prints READY or does not
  ```
  **Never derive the interpreter from the console script's shebang.** On a
  machine where `metascience` is a `#!/bin/sh` shim that `exec`s the real
  script, `$(head -1 $(which metascience) | tr -d '#!')` is `/bin/sh`, and
  Python fed to it runs as shell: on 2026-10-18 `$PY - <<'EOF'` with
  `import json` on line 1 ran ImageMagick's `import`, which grabbed the
  screen into a 48 MB file named `json` in the repo root.
  A missing `statcheck` does NOT fail loudly — the tool returns
  `success: false` and an empty result, which reads as "this paper has no NHST
  statistics". That mistake was made here once and briefly produced the
  conclusion that a 95-paper corpus contained zero test statistics. Run
  `preflight` first.
- **Tests: `metascience-test -q`** (console script from `[project.scripts]`,
  wraps `src/metascience_agent/test_runner.py`). Use **`metascience-test --stack -q`**
  for final local verification: all three Python test roots, TypeScript, web unit tests,
  isolated browser checks, and lint run concurrently, with separate logs and a
  combined exit status. Live server/database checks and paid evals remain explicit.
  Python uses pytest-xdist with a machine-local calibrated worker count (all
  available CPUs before calibration), `--dist loadfile` (a
  whole file stays on one worker, which is what this suite's module-scoped
  fixtures need) — and self-installs pytest-xdist into whatever interpreter
  is running it if it isn't already present, so it works the same on a fresh
  Mac/Linux/Windows checkout without a separate setup step. If the install
  can't complete (offline, read-only env), it degrades to a serial run rather
  than failing — parallelism is a speed optimization, not a requirement.
  Run `metascience-test --stack --tune --worker-counts 6,12,16,20` to
  compare full-stack elapsed times (choose counts within the machine's available
  CPUs). Two alternating rounds select the fastest median; a failed run leaves
  the previous calibration unchanged. Calibration stays in the operating system's
  local cache, outside Dropbox. `-n` or `METASCIENCE_TEST_WORKERS` overrides it.
  Numerical/OpenCV thread pools default to one thread per worker so parallel
  processes do not each claim every core; explicit thread environment settings win.
  Bare `pytest -q` / `python -m pytest -q` is also parallel when
  pytest-xdist is installed — `tests/conftest.py` applies the same
  calibrated worker / `--dist loadfile` default after plugins load.
  `[tool.pytest.ini_options].addopts` deliberately does NOT hardcode
  `-n`/`--dist`, because those flags are only valid once pytest-xdist is
  installed and `addopts` is parsed before any plugin/conftest.py can fix
  that up — hardcoding them here is what made bare `pytest` hard-crash with
  "unrecognized arguments: -n" the one time it was tried.
  `metascience-test -p no:xdist` (or bare `pytest -p no:xdist -k <name>`) to
  debug a single test serially with clean, non-interleaved output. Outside
  the venv a globally-installed pytest/hydra plugin can break collection; the
  workaround is
  `PYTHONPATH=src:copy_paste_detector/src python3 -m pytest tests/ -q`
  (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` turns xdist off; pass `-p xdist` as
  well if you need that workaround *and* parallelism). That PYTHONPATH is
  how tests import both packages outside the venv. The raw-data detector
  lives in `copy_paste_detector/`; an editable install (`pip install -e .`)
  adds both source roots to its `.pth`. The image analysis package is a
  separate repository (see Architecture); install it editable from its own
  checkout AFTER the toolkit, and add its `src` to `PYTHONPATH` in a worktree
  run that needs it.
- PDF rendering tries `wkhtmltopdf`, the WeasyPrint Python library, then
  `pandoc` with an available PDF engine. It is optional and best-effort;
  a failed render is recorded in `run_meta.pdf_error`.

## Architecture / where things live

- `agent.py` + `parallel.py` — the pipeline. `analyze_paper(mode="parallel")`
  (in `agent.py`, the one entry point; `two_stage` is a deprecated alias
  and anything else raises; `single_stage` was removed in v1.19.0)
  dispatches to `parallel.analyze_paper_parallel`: two `_run_stage`-driven
  analysts run concurrently under a budget split (tool 0.40·B, science
  0.25·B, adjudicator the rest with a $0.20 floor), their findings merge
  with the image/text track rows, pre-adjudication annotators run (quote
  verification, tool-verdict ledger join, provisional clamps — evidence-
  CHANNEL caps only; since v1.14.0 there is NO ceiling on the 1–9 ladder,
  every role may write any rung), then
  `adjudicate.build_docket`/`apply()` assign final severities with
  code-enforced clamps, and `write_parallel_outputs` writes the
  `forensic_review*/` layout (per-agent prompt/toolcalls/messages files,
  `adjudication.json`, `analysis_code/`, `findings.v2.json`). `agent.py`
  keeps the `_run_stage` adapter, annotators, source resolution and numeric
  orchestration. `runtime.py` owns subprocess execution, stream parsing,
  retries, cancellation and transcripts; the adapter supplies statistical
  preflight and forensic MCP configuration. The image package's screening
  stages use the same runtime with its own image preflight (the default when
  no `preflight=` is passed). Shared serialization and track contracts also have one canonical owner. The serial body was deleted in v1.27.0; shared
  helpers are still live despite their module name. Per-role tool lists come from `registry.stage_tools`
  (`STAGE1_TOOLS`/`STAGE2_TOOLS` are the legacy aliases). Structured output
  is enforced with the CLI's `--json-schema`.
- `pipeline_config.py` + `pipelines/*.yaml` — **pipelines** choose the modules
  a run uses (`tools_agent`, `scientific_proofreading_agent`, `image_analysis`,
  `text_forensics`, `adjudicator`) and the tools agent's
  toolset; `--pipeline` on `analyze`/`batch`, `metascience pipeline
  list|validate|show|tools`. `full` is byte-identical to the flag default
  (pinned). Display names are new; the STORED producers `tool_expert` /
  `science_error` are not (`finding_id` hashes them). A restricted toolset is
  enforced by the allowlist, the MCP server (`METASCIENCE_MCP_TOOLS`,
  fail-closed), `check_table` and the harness prepass. A partial pipeline
  never stands as the paper's review (`run_kind` `partial_review`, history
  component `partial_review`, its own review directory, batch skip per
  digest). Phase 1 of the modular refactor; see
  [docs/specs/pipeline_config.md](docs/specs/pipeline_config.md).
- `modules/` + `core/` — **modules** (Phase 2): each module is a folder,
  `modules/<name>/MODULE.md` (its definition, as frontmatter) + `module.py`.
  `core/scheduler.py` starts each producer when the modules it `needs` have
  finished, and results merge in canonical order (`ModuleDef.order`); the
  adjudicator is the finaliser. An agent module or the adjudicator may run on
  its own `backend:`. The always-on correctness passes stay in `parallel.py`.
  The opt-in `raw_data` module (2026-10-15; pipelines `raw_data_only`,
  `full_raw_data`) runs the copy-paste detector over the paper's
  spreadsheets as producer `raw_data_track`: quarantined, one row per
  (file, kind), never the headline.
  See [docs/specs/modules.md](docs/specs/modules.md).
- **Tool layer, names and backends (Phases 3b-5, 2026-10-13).**
  - `metascience tool list|describe|run` (`tool_cli.py`) runs ANY registered
    tool through `ToolSpec.call` -- the MCP gates -- and serves only what the
    MCP server would under the same env. Reproductions are generated as
    `metascience tool run <tool> --json '<args>'`, replaying the ledger call
    behind a finding (`findings_v2.backing_call`); the analysts no longer get a
    CLI map and do not write commands (`core/prompts/reproduction.md`).
  - `receipts.py`: the MCP server (and `tool run`) receipts every answer to
    `~/.cache/metascience/receipts/<run_slug>/<role>.jsonl`; the review dir
    gets `receipts.<label>.jsonl` and `run_meta.tool_receipts` names ledger
    calls without a receipt, receipts without a call, and calls whose result
    the transport changed (Claude Code swaps a large MCP result for a
    "saved to a file" notice).
  - `tool_access: mcp | mcp_brief | skill` per agent module
    (docs/specs/tool_access.md). `skill` is fenced by the PreToolUse hook
    `skill_guard.py`, NOT by Claude's permission pattern, which measured
    letting `... && echo PWNED` run.
  - `--backend openrouter`: our agent loop (`openrouter_loop.py`), Claude
    stream-json dialect, MCP client, needs `OPENROUTER_API_KEY`.
  - `image_detect` pipeline: detection without AI review; candidates filed
    unscreened (`ai_screening.status: not_run`), never headline (in code),
    never published.
  - `names.py`: the ONE alias table from stored identifiers (producers, stage
    labels, channel keys) to display names, derived from MODULE.md; used by
    the report, the viewer, the webapp (`constants.gen.ts`) and the CLI.
- `tool_specs/` — **each tool's definition, one folder per family** (Phase 3a):
  `tool_specs/<family>/spec.py` holds the `ToolSpec`s (typed params, guards,
  roles, CLI name) and `TOOL.md` holds each tool's MCP description (exactly as
  sent) and integrity card. Moved verbatim out of `registry.py`, which keeps
  the machinery (`Param`, `ToolSpec.call`, the gates) and loads the specs in
  `tool_specs.ORDER`. The pure functions stay in `tools/*.py`; a folder is
  named for the module it defines (`tool_specs/grim/` -> `tools/grim.py`).
- `tools/*.py` — pure functions, one technique each. **Every result dict carries
  a `severity`** from `tools/severity.py` (enum, lowercase:
  `impossible|highly_suspicious|suspicious|indeterminate|consistent`). Guards
  return `{"error": ..., "severity": "indeterminate"}` rather than raising.
- `tools_mcp.py` — wraps each tool function with `@tool("name", "desc", {arg:
  type})` returning `{"content":[{"type":"text","text": json.dumps(result)}]}`,
  and lists them in `ALL_TOOLS`. `mcp_server.py` iterates `ALL_TOOLS` and wraps
  handler crashes in a structured error — no per-tool change needed there.
- **Prompts** — the text lives with its owners: each agent's text is
  `modules/<name>/prompt.md` (`tool_expert.md` is
  `modules/tools_agent/prompt.md`, `science_error.md`
  `modules/scientific_proofreading_agent/prompt.md`, `adjudication.md`
  `modules/adjudicator/prompt.md`) and the shared text (`rulebook.md`,
  `rulebook_roles.md`, `reproduction.md`, `grok_mcp_route.md`) is
  `core/prompts/`. They are assembled by `core/prompts/__init__.py`
  (`metascience_agent.core.prompts`), the single source of truth for what
  is sent; the JSON schemas are `src/metascience_agent/schema/`. The old
  `metascience_agent/prompts/` package was retired on 2026-10-18.
  `prompts.PROMPT_FILES` maps the old names to the files; a scanner of
  prompt text reads `prompts.prompt_files()`, never a glob of one folder.
  What is actually SENT (parallel pipeline):
  - `tool_expert_system_prompt()` = `tool_expert.md` (with each `TOOL.md`'s
    guidance block spliced in at `{{TOOL_GUIDANCE}}`) + the severity ladder
    from `severity9` + `rulebook.md` + `rulebook_roles.md` +
    `r_crosscheck_note()` + `reproduction.md`, then a toolset note when a
    pipeline restricts the tools and `grok_mcp_route.md` under Grok. No
    tool→CLI-verb map is sent any more (`registry.cli_syntax_reference` still
    exists, for people).
  - `science_error_system_prompt()` = `science_error.md` + ladder +
    `rulebook.md` + `rulebook_roles.md` + `reproduction.md` (+ the Grok route).
  - `adjudication_system_prompt()` = `adjudication.md` + ladder +
    `rulebook.md` + `rulebook_roles.md` + `r_crosscheck_note()`.
  - `_provenance`'s default `prompt_blob` is the parallel trio (tool_expert +
    science_error + adjudication) since v1.26.1 -- `cli.py`'s version verb
    calls it bare, and it used to fingerprint prompts the live pipeline does
    not send.
  - Per-tool prose reaches the model only as each `ToolSpec.description`, i.e.
    the MCP tool definition.

  **`docs/tool_reference.md` is NOT sent to any model.** It is a human reference, and
  the exclusion is deliberate: it duplicated the MCP definitions (~3,885 tokens)
  on every turn. A test used to assert the opposite and passed vacuously for
  months, so guidance written there — including an inverted `decimals` warning —
  was maintained for an audience of nobody. Guidance the model needs goes in the
  `description` or in the two stage prompts.

  Schemas: producer-specific variants of `src/metascience_agent/schema/findings.v2.schema.json`
  and `schema/adjudication.schema.json`, enforced via `--json-schema`.
  The v1 `findings.schema.json` and `report.schema.json` were deleted, as were
  the retired divergent master prompts; do not reintroduce either.
- `cli.py` — Typer app; each tool has a command. Use `print_severity()` /
  `bail_on_error()` / `_severity_color()` helpers; drive color only from the
  `severity` field.
- `extraction/pdf.py` — `extract_text_with_tables` (docling, served from the
  content-hash `.extraction_cache/`); output is capped and supports
  `first_page`/`last_page`.
- `extraction/jats.py` — `extract_xml_text_with_tables` (stdlib
  `ElementTree`, no new dependency) reads publisher XML: JATS `<article>`,
  `<pmc-articleset>`, and Elsevier `full-text-retrieval-response` (CALS
  `<tgroup>` tables, which carry NO `<table-wrap>` at all). **This is the
  primary source when a paper ships an `.xml`** — see the invariant below.
  Also exports `find_xml` and `paper_text(paper_dir)`, the one loader every
  consumer of the old `body.md`/`abstract.md` should use.
- `extraction/supplements_read.py` — `extract_supplement` reads a supplement in
  ANY format and returns the SAME table shape as `jats.py`: `.pdf` (via
  `extraction/pdf.py`), `.docx` (python-docx), `.xlsx` (openpyxl), `.csv`/`.tsv`,
  `.html` (via `extraction/html.py`, `require_article=False`), `.epub` (a zip of
  XHTML, stdlib `zipfile` — no new dependency), `.xml` (via `jats`, `tables="full"`),
  `.txt`/`.md` (text only, no column guessing), and images (via the OCR seam).
  Only `.doc`, `.xls`, `.zip` and `.tex` refuse by format. **Four refusal states,
  and they are different facts**: `ocr_unavailable` (no engine on THIS machine),
  `no_text_layer` (the PDF's pages are pictures), `unreadable_format`, and a read
  file with an empty `tables` list. Conflating the first with the last writes a
  claim about the authors out of a missing package.
- `extraction/ocr.py` — the OCR SEAM, not an engine. Three adapters
  (pytesseract, RapidOCR, PyMuPDF-via-Tesseract) behind one `OcrWord`. **No
  engine is vendored, and which ones are present is MACHINE-SPECIFIC** — ask
  `engine_status()` or `metascience preflight` on the machine you are on rather
  than assuming either way. This file previously asserted that none was
  installed; that was true when written and had stopped being true, which is
  how a run gets planned around a capability the machine actually has (or
  lacks). What IS implemented and tested is the layout reconstruction above the seam
  (word boxes → lines → column cuts → grid → `cells`), on synthetic boxes, so it
  is engine-independent. A column break needs support from 60% of multi-word
  lines, which is what stops a spanning caption shredding the grid.
- `report_render.py` — markdown → HTML → PDF (best-effort).
- **Image analysis is a separate, private package** (since 2026-10-16):
  `metascience_observatory_image_analysis`, its own repository, checked out
  beside this one as `../metascience-observatory-image-analysis` and installed
  editable after the toolkit; it DEPENDS ON this toolkit, never the reverse.
  The toolkit runs without it. Host code reaches it ONLY through
  `image_plugin.py` (`load`, `available`, `ImagePluginUnavailable`), pinned by
  `tests/test_runs_without_image_plugin.py`. The host keeps NO aliases of the
  package's modules (deleted 2026-10-18, v1.85.0): import the package's own
  paths, and load its storage-backed review modules (`local_images`,
  `local_image_import`, `local_image_service`) through
  `workbench.image_review_host.load`, which binds the host's bases first. The
  one exception is `extraction/figures.py`, which IS the package's module when
  it is installed and supplies the OCR provenance names when it is not. Without the
  package: the image module's channel reads `refused` with "the figures were
  NOT examined" (history component `unavailable`), `extract_figures` and
  `analyze_paper_images` stay registered and refuse by name, the `image-*`
  verbs and `--device` options are absent, workbench image routes raise
  `ImagePluginUnavailable`, and docling runs in-process on the CPU
  (`extraction/document_compute.py`; the GPU broker is the image package's).
  Host-side adapters: `modules/image_analysis` (detect + AI screening, one
  module since 2026-10-18),
  `workbench/image_mixins.py`, `workbench/image_review_host.py`,
  `integration.py` (hooks both sides read). The general modules the
  2026-09-11 extraction had put inside the image package (runtime, LLM
  backends, extraction, archive, history, findings_v2, quotes) live HERE; the
  package keeps reverse aliases. Detector, gate, screening contracts, GPU
  execution, image review and the image invariants are documented in that
  repository's CLAUDE.md, with `eval/gate`, `eval/bench`,
  `eval/ground_truth/image`, `eval/rollout` and the image docs.
  `METASCIENCE_BLOCK_IMAGE_PLUGIN=1` runs this suite as a plugin-less install;
  tests that exercise the package take the `image_package` fixture.
- `workbench/` + `webapp/` — the **review workbench**: Next.js calls one
  managed persistent Python JSON-lines service through `webapp/lib/workbench.ts`.
  Normal project/paper/finding/image/copy-paste/history reads use a private local
  SQLite cache; they do not spawn a CLI process, recursively scan folders, or
  contact the findings database after the relevant records are cached. `webapp_index.py` and
  `webapp/data/index.json` remain explicit import/compatibility tools, not the
  normal navigation authority. See [docs/workbench_storage.md](docs/workbench_storage.md).
  - Interactive queue reads use indexed project/run scopes and durable SQLite
    revisions for records, reviews, and local mappings; status/detail/file-cache
    writes do not rebuild queue projections. Each read worker has its own SQLite
    connection. Validated media references have a bounded revision-keyed cache.
    Queue PNG thumbnails fit within 260×120 and live in a disposable 1 GiB local
    cache; full images remain available in hover/detail views. Review uses
    `cd webapp && npm run build && npm start` on port 3101 (`.next-review`);
    development uses `npm run dev` on port 3100 (`.next-dev`), or the next free
    port if 3100 is taken. `webapp/scripts/serve.mjs` puts each build directory in
    the OS cache (keyed by checkout path, beside a `node_modules` link and a
    generated tsconfig), never in the synced checkout: Dropbox once synced a Mac
    `.next-dev` into Linux and every page failed. Stop a production
    server before rebuilding its directory; separate QA builds use
    `METASCIENCE_NEXT_DIST` and an explicit `PORT`.
    The image queue loads pages incrementally and preserves loaded rows on
    request failure. Bulk False positive applies only to selected loaded rows,
    saves each decision against its actual run, and retains failed selections
    for retry. Preserve the generic `false_positive` decision alongside legacy
    reason-specific decisions in readers, evaluation, and publication rules.
  - **The local Postgres findings database owns records; files own media.**
    Every database is on this machine: the remote Neon database was retired
    2026-10-16 (quota-blocked; its contents were already in the local Postgres),
    and `db_push.resolve_db_url` REFUSES a URL naming any other host. There is
    one URL, `METASCIENCE_DB_URL` (env or repo `.env`); the `NEON_DB_URL` alias
    and the `METASCIENCE_DB_PROFILE(S)` switcher are gone. Store findings,
    retained candidate details, runs, review events, publication state, and
    lightweight artifact references in it. Do not upload PDFs, images, videos, spreadsheets,
    extracted article bodies, or generated exhibits. Stable corpus/paper/run/item
    identities must survive different directory layouts; never merge by DOI.
  - `workbench/catalog.py` owns private SQLite/WAL storage in the operating
    system's local application-data directory, outside Dropbox/network shares.
    Multiple roots and explicit paper/file mappings support files outside Dropbox.
    Archived evidence must match its recorded SHA-256. Missing or changed files
    affect local availability, never the scientific status of shared findings.
    A contemporary source without an archived hash is separately labeled.
  - `workbench/service.py` separates cached interactive reads, foreground detail
    connections/workers, source conversion, local monitoring, and background sync.
    Summary pages default to 50 rows (maximum 100); filter and sort before
    serialization, fetch selected details separately, and show findings before
    PDF/XML preparation. Failed, partial, empty, and explicitly selected historical
    runs must not fall back to a different run. Comprehensive/component deduplication
    uses explicit provenance, not similar titles.
  - `workbench/remote.py` synchronizes compact summaries through a transactional,
    commit-ordered journal. Bootstrap publication and cursor advancement are atomic;
    changed/deleted records invalidate fetched details. Poll at 30 seconds while
    active and five minutes while idle, and refresh on focus. Decisions first
    commit to a durable local outbox with immutable event IDs; show pending sync
    until acknowledgment and pull. Preserve all reviewers' events and disagreements.
  - `history_publication.sync` projects saved database judgments independently of
    local file-stat stamps. Old imports cannot undo a later publication revocation;
    conflicting reviewers cannot silently republish it. `history_publication.refresh`
    is a separate legacy local-file projection. Browsing and new workbench decisions
    must not trigger corpus-wide archive uploads or local evidence rebuilding.
  - `workbench/monitor.py` uses nonrecursive watches on known paths and periodic
    reconciliation. Source-file modifications are revalidated locally, independently
    of the database. Watcher failure is visible and retains periodic reconciliation.
  - `python -m metascience_agent.workbench.service --migrate` applies migrations
    004/005/006; `--sync --index webapp/data/index.json` bootstraps the local cache.
    Here `python` means the interpreter discovered from the console script above.
    The `db` extra supplies psycopg and watchfiles.
    `workbench.importer` imports existing archives/reports without rerunning analysis,
    and reports digest/U+0000/unscoped-review conflicts.
  - Queue default order is `triage` (`image_queue.triage` = the image package's
    `image_forensics.triage_rank.sort_value`, loaded via `image_plugin`,
    backfilled once at worker start); navigation is keyset-based and returns the
    next undecided items to prefetch; a decision key advances immediately and the
    save retries with the same client `event_id`. Bulk decisions are polled jobs
    in 250-row transactions; "nothing saved" is shown only when the service says
    zero were. Local events also record missed duplications (`image_missed`,
    exported as ground truth by `image-reviews-export --missed-out`), spot-check
    verdicts on automatic demotions (`extra.demotion_check`) and decisions carried
    from an earlier run whose evidence is provably identical (`extra.carried_from`;
    item id alone is not proof). Media under `__runs/` is served immutable; WAL
    files are checkpointed when the service is idle. The bridge decodes stdout as
    a UTF-8 stream (a multibyte character split across 64 KB chunks used to become
    U+FFFD) and a restart rejects waiting requests at once.
  - Image review still operates on an **item**, not a paper. `triage_rank` (in the
    image package) remains the shared ranking rule. The image package's legacy
    `image_review.build_items` / `image-review-write` support file workflows; the normal web routes use the cache and review outbox.
    Keep media streaming, HTTP byte ranges, conditional requests, hash validation,
    and path-containment checks. Video seeking depends on range support.
  - `bundle.py` remains the self-contained offline report (`viewer.html`, opened
    from `file://`), distinct from the workbench. Do not invoke its full-media
    rendering during corpus navigation. Legacy aggregate statistics still use
    explicitly generated `corpus_stats.json`; finding drill-down uses cached pages.
  - **Retention exceptions recorded September 10, 2026:** superseded prototype
    image payloads were retired in the shared database (then Neon), with original local archives retained.
    The user then explicitly reset **all Masliah image results** in the database and on
    disk, preserving original sources, protected source snapshots, and non-image
    analyses. The UI must say “awaiting a new analysis,” not “clean.” No replacement
    Masliah image run was started. `workbench/image_cleanup.py` and migration 006
    preserve run-identity tombstones and prevent reimport under cleared IDs; local
    tombstones live in `.analysis_runs/retired_runs.json`. Future analysis uses new
    run IDs. Do not restore retired payloads during backfill or generalize these
    explicit resets into automatic deletion of innocuous/unresolved candidates.
    Audit manifests and measured space savings are documented in the storage guide.
- `evaluation/` — the eval harness (`harness.py`, `judge.py`,
  `deterministic.py`); fixtures in `benchmarks/paper_reviews/fixtures/*.yaml`; `metascience eval`.
- `scaffold/` — Greg's paper scaffold: a structured extraction of studies,
  variables and values, plus (since v1.72.0) a deterministic checks/premises
  layer (`checks.py`, `premises.py`, `premise_reading.py`, `adjudication*.py`).
  **Not wired into the analysis pipeline**; run it with
  `python -m metascience_agent.scaffold`. The paid premise reading is opt-in
  (`--read-premises`, capped by `MAX_CANDIDATES_PER_PAPER`). Paid table readings
  persist in `~/.cache/metascience/readings` (`METASCIENCE_READING_CACHE`, `off`
  for test-retest); the suite gives each test its own empty store.
- `batch.py` — async worker-pool batch runner behind `metascience batch` (concurrency,
  per-paper timeout, `batch_costs.jsonl` / `failed.jsonl`, log slimming).
- `preflight.py` — `fatal_checks()` / `optional_checks()` / `assert_ready()`.
  `assert_ready` is called at the top of the host `_run_stage`, just before the usage
  guard, and `metascience preflight` renders the same two functions so the
  command and the gate cannot drift. See the invariant below.
- `usage_guard.py` — pre-call check on the Claude Code 5-hour session limit
  *and* the weekly quota, awaited at the top of `_run_stage` (so every
  analyst, adjudicator and JSON-repair call is covered by one hook) and again
  explicitly in `batch.py`. Probes `claude -p "/usage"` (or, under
  `--backend codex`, `codex app-server`'s `account/rateLimits/read`, the
  same two windows; under `--backend antigravity`, the free `agy -p /usage`,
  counting only the quota groups the run's model draws on; grok has no probe
  and is `UNSUPPORTED`), pauses
  at/over `METASCIENCE_USAGE_THRESHOLD` (default 90%), and **stops**
  (raises `WeeklyLimitReached`) at/over `METASCIENCE_USAGE_WEEK_THRESHOLD`
  (default 97%). Extra usage credits are not in the weekly %; override with
  `--ignore-weekly-limit` / `METASCIENCE_USAGE_IGNORE_WEEKLY=1` (session
  pause still runs) or `--no-usage-guard` / `METASCIENCE_USAGE_GUARD=0`
  (disable entirely). Async on purpose: a blocking sleep would stop the
  event loop from draining in-flight stage subprocesses. See the invariant
  below.

## Read the OUTPUT, not only the code (standing rule)

**Before calling any result here correct, spend a pass looking only at what the tool
printed — recompute it, eyeball the rendered table, ask whether the claim is plausible
for this kind of paper.** This is not optional polish; it is the rule that catches the
defect class this project exists to prevent.

Greg, 2026-08-12, on why: an engineer reading the implementation sees code that is doing
exactly what it says. A scientist reading the *numbers* sees the problem in seconds.
Nearly every false accusation found in this repo was of the second kind.

- **Recompute the arithmetic behind a flag.** `sweep_duplication` called an honest JAMA
  cohort paper `highly_suspicious` at p=4.8e-09 over "13 identical (mean, SD) pairs" —
  0.26/0.44, 0.06/0.24, 0.10/0.30. One line of `sqrt(m(1-m))` reproduces all of them:
  binary proportions beside their own SDs. The code was fine. The numbers were not.
- **Open the artefact.** Build the bundle, count the rows, compare against the source.
  That is how `get_table`'s cell window turned out to be delivering 61% of every large
  table while reporting `data_is_complete: true`.
- **Apply domain sense.** Tables 1/2/3 of a cohort paper are subsets of each other;
  affect means above 1 cannot be proportions; a "P value" column is not a percentage
  column. Faster and more reliable than tracing the dispatch table.
- **Question the premise.** "Fix X" frequently means X is mis-scoped — measure the
  reported scope before fixing it. Queue items have repeatedly differed from their
  descriptions.
- **Sanity-check every number before reporting it**, including your own measurements and
  any subagent's. Check the denominator first. Agent reports in this repo have been
  confidently wrong in both directions.

## Correctness invariants (have regression tests — do NOT regress)

- **GRIM** tolerance scales with n (round-back logic in `tools/grim.py`), not a
  fixed `0.5/10^d`. `grim_test(3.53, 30)` is consistent.
- **GRIMMER** enumerates (sum S, sum-of-squares Q) with the parity constraint
  `Q ≡ S (mod 2)`; the old vacuous `consistent` check was wrong (its own test
  expectation `grimmer(4.0,1.0,10)=consistent` was wrong — that combo is
  impossible).
- **CSF** emits a one-sided `similarity_p`; **high baseline p-values are the
  red flag, never reassurance** (rulebook rule 1). Both stouffer/fisher branches
  must agree on direction.
- **check_sd_range** uses the sample-SD bound `(range/2)·√(n/(n−1))`. It, with
  `flag_round_n`, `reconstruct_2x2` and `required_n`, was once sequestered as
  CLI-only for safety (it can return `impossible` against a range nobody
  stated); all four are now stage-reachable with the premise made an explicit
  parameter, which is the better fix. The only CLI-only tools are
  `analyze_paper_images` and `detect_tortured_phrases`, for an unrelated
  reason: the deterministic image and text tracks call them in child
  subprocesses concurrent with the analysts, and their quarantined findings
  reach the adjudicator by injection (an analyst mid-run must not launch a CV
  pipeline, and a free deterministic screen must not cost paid analyst turns).
  `registry.py:CLI_ONLY` is the register of record, each entry with its
  reason. Do not advertise those two in any prompt — the agent cannot call
  them.
- **Never label duplication `impossible`** — it's improbable, not a math
  violation (rulebook rules 3, 9, 11). Cap at `highly_suspicious`.
- **GRIM-U** uses the *normal approximation* (not the exact permutation
  distribution — they give different p's); it reproduces the paper's tables
  byte-exact. `impossible` only below the U=0 floor under all conventions; a
  granularity miss is at most `suspicious` (`tools/grimu.py`; exact-permutation
  DP is gated to n1·n2 ≤ 5000). Applies to Mann-Whitney/Wilcoxon p-values ONLY —
  and that guard is IN CODE now like GRIM/DEBIT's: `grimu_check` takes
  `test_type` and refuses anything that is not mann_whitney/wilcoxon
  (`canonical_test_type`; verified 2026-08-22 against a claim here that the
  port was "remaining work" — it had already shipped, with tests in
  `test_misapplication_guards.py`).
- **A complex-survey paper's p-values cannot be recomputed as a simple random
  sample.** `survey_design.declares_complex_survey` reads the Methods (14
  markers: the design phrase, `WTMEC*`/`SDMVPSU`, `svyglm`, `PROC SURVEY*`, R's
  survey package, Taylor-series/jackknife/BRR); bare "weight", "stratified" and
  "survey" are deliberately absent. Both analyst prompts then quote the paper's
  own sentence, and every affected tool takes `sampling`. TWO TIERS, because
  the checks are not equally damaged: `check_estimate_ci` becomes ONE-SIDED
  (its interval and p come from one fit, so df is the only free parameter and p
  is monotone decreasing in df — the z recovery is the INFIMUM, so a printed p
  above it means nothing and a printed p below it still stands), while
  `REFUSED_UNDER_SURVEY` — the recompute-from-printed-means family — returns
  `indeterminate`, because weighting moves the point estimate too and neither
  direction is informative. Counting checks on printed integers are untouched.
  MEASURED 2026-08-22: six of twenty severity-bearing tool findings on
  `10.1186--s12889-025-24026-y` were this one error. The guard is in the TOOLS,
  not `ToolSpec.call`, because `cli.py` calls them directly.
- **Misapplication guards are enforced IN CODE, not just in prompts.**
  `grim_test` and `debit_test` take a `data_type`; non-integer data (GRIM) and
  non-binary data (DEBIT) return `indeterminate`, never a finding. A tool
  pointed at the wrong data must REFUSE, not accuse. Guard paths (n<2, mean
  outside [0,1], inapplicable type) must return `indeterminate` — only real
  evaluations may return `impossible`. See `tests/test_misapplication_guards.py`.
- **Rulebook rule 4 is enforced in code**: `grim_test` takes `bound_source`
  (`stated`|`logically_necessary`|`assumed`); an out-of-range result resting on
  an `assumed` bound is capped at `suspicious`. Granularity failure and range
  violation are reported as distinct `failure_mode`s, not fused into one flag.
- **Thresholded p-values are bounds, not values.** `recalc_within_subjects_t`
  auto-detects `"p<.05"`, treats the recovered r as a lower bound, and returns
  `indeterminate` unless the whole attainable interval is outside [-1,1].
  An exact-p `|r|>1` caps at `highly_suspicious` — reporting convention, not
  fabrication, is the usual cause. See `tests/test_false_positive_guards.py`.
- **DEBIT tests both SD conventions.** A row consistent under the population SD
  `√(p(1−p))` is `suspicious`, never `impossible` (that convention is legitimate;
  treating it as fraud caused 66 false accusations in a 450-case grid vs
  `scrutiny`). `impossible` requires failing every defensible reading.
- **SPRITE distinguishes four outcomes**: `found` / `no_solution_proven` /
  `grim_fail` / `search_exhausted`. **Only `no_solution_proven` is evidence** —
  it comes from the analytic integer/parity constraint `Q ≡ S (mod 2)`, not from
  a search giving up. Matching is on the SD ROUNDED to its reported precision
  (what `rsprite2` does), not an exact variance match.
- **A budget-truncated run must announce itself.** `_stage_meta` records
  `error_subtype` + `truncated_by_budget` per stage; `analysis_runs` then
  files the run as `incomplete` (not `completed`), `webapp_index` carries the
  flag, and the viewer prints "STAGE TRUNCATED BY BUDGET". A truncated stage
  must never read as a complete review. `report.md` says so too: since
  v1.78.2 `report_v2._truncated_stages_banner` prints a PARTIAL COVERAGE
  banner beside the partial-pipeline one, naming each stage with
  `truncated_by_budget` or `truncated_by_timeout` (the serial pipeline's
  limitation went with it in v1.27.0 and was missing until then). See
  `tests/test_report_v2.py::TestTruncatedStageBanner`.
- **The version is declared in exactly one place, and the report says what
  produced it.** `version.py` holds `__version__`; `pyproject.toml` reads it via
  `[tool.hatch.version]`, and `tests/test_version.py` fails if a literal
  `version = "..."` reappears there — the number was declared in both files
  independently and never bumped, so `0.1.0` identified nothing. Bump rules live
  in `CHANGELOG.md`, and the MINOR rule is the load-bearing one: a new tool, a
  changed severity cap, or a prompt edit that changes interpretation all bump
  MINOR, because two reviews across that boundary are not comparable.
  `pipeline_version()` returns the COMPOSITE (release + git sha + dirty flag) —
  the release number moves monthly while the code moves daily, so it does not
  identify a run on its own, which is the same reason `_provenance` also records
  `prompt_sha256`/`registry_sha256`. `git_dirty` has THREE states and the third
  is the point: `"unknown"` when the probe could not run, never `False`.
  `analysed_at` is taken ONCE per run in `parallel.py` and reused for the run id
  and `run_meta`; taken twice, report.md and run_meta.json disagree about when
  the same run happened (the serial pipeline's `_run_stamp` once did exactly
  that). The stamp reaches the PDF through the
  MARKDOWN, not only `markdown_to_html`'s `meta_line`: the pandoc fallback engine
  renders the raw markdown and never sees that template. `resolve_run_stamp` is
  shared with `bundle._run_facts` so both surfaces answer "when was this run" the
  same way, and a legacy run's `run_meta.json` mtime is offered ONLY with
  `analysed_at_source: "file_mtime"` and a sentence on the page saying it is a
  file date — a file date presented as a run date is the substitution this
  toolkit exists to catch, and mtime diverges the moment the directory is synced.
- **The report is rendered from the schema, not from model prose**
  (`report_v2.render_report_v2`; the v1 `report_render.render_report` was
  deleted in v1.27.0). Headline-first, severity-ordered findings,
  "what we could NOT check", and the figure-blindness limitation are structural
  guarantees, not prompt requests.
- **The preflight gate fails CLOSED, and the asymmetry with the usage guard is
  deliberate.** `preflight.assert_ready()` runs at the top of `_run_stage`
  (before `usage_guard()`, since a free local check should precede a network
  probe) and RAISES `PreflightError` when a dependency whose absence makes the
  output *wrong* is missing — the selected backend CLI, `statcheck`, `claude_agent_sdk`,
  `python-docx`, `openpyxl`, the registry. The usage guard fails open because
  its worst case is wasted spend; this fails closed because its worst case is a
  paid run that checked nothing and still reads as a clean paper. Non-fatal
  items (R, `wkhtmltopdf`/`pandoc`, PyMuPDF) are reported and never block —
  they degrade a run without making it wrong. Overridable with
  `METASCIENCE_SKIP_PREFLIGHT=1`; results are cached per process, so the 2–3
  `_run_stage` calls per paper cost one check. `batch.py` re-raises
  `PreflightError` WITHOUT writing it to `failed.jsonl` — it is an environment
  fault affecting every paper, and retrying cannot install a library. The gate
  must stay out of `metascience batch --dry-run` and `benchmark`, which spend
  nothing. See `tests/test_preflight.py`.
- **The usage guard fails OPEN, and is checked before the spend, not after.**
  A `/usage` probe that times out, crashes, can't find `claude`, or returns
  unparseable text must let the run continue — the guard exists to avoid wasting
  spend and must never itself stop a batch. The weekly STOP is the named
  exception (`WeeklyLimitReached`); extra usage credits are not in that
  gauge, so `--ignore-weekly-limit` / `METASCIENCE_USAGE_IGNORE_WEEKLY=1`
  skips it. It also has to run *before* `create_subprocess_exec` (hitting the
  session limit mid-stage doesn't stall, it returns an error result, so the
  paper is charged for a sweep with no findings) and *outside* both the
  `wall_seconds` clock and the stage timeout, so a pause isn't billed to
  either. See `tests/test_usage_guard.py`.

- **An R cross-check that cannot run must SAY SO, and preflight must not call
  it healthy.** `preflight` probed only `shutil.which("Rscript")` and printed
  the detail `"present"`; the wrappers' failure branch read
  `result["error"] or result["stderr"]`, but R writes "ERROR: <pkg> package not
  installed" to STDOUT and `quietly = TRUE` leaves stderr empty, so `r_grim`
  returned `{"error": "", ...}` on every call. The prompts require a
  cross-check before any GRIM `impossible` is published, so a missing
  `scrutiny` silently capped every GRIM finding in a corpus at `suspicious`.
  `_r_unavailable()` now names three distinct states — `package_missing`,
  `r_absent`, `r_error` — and preflight probes the packages. An unavailable
  engine is never a disagreement.
- **A threshold p-value passed as an exact one cannot be allowed to accuse.**
  `recalc_within_subjects_t` handles a declared threshold correctly, but the
  MODEL stripped the `<` from "p<0.05" and the same rows went from
  `indeterminate` (interval `[-80.22, 1.013]`) to `highly_suspicious`
  (`[-90.59, -70.90]`), producing a headline finding against a real paper that
  had to be retracted. When the p equals a conventional alpha and is not
  declared a threshold, the finding must survive BOTH readings or it is not
  reported — see `_CONVENTIONAL_ALPHAS` in `tools/ttest.py`.
- **Duplication counts groups, pairs and rows separately, and says which.**
  "75 duplicated row pair(s)" was a count of merged match-signature GROUPS
  across two worksheets on a two-shared-columns criterion; a reader divided it
  by 193 rows to get "39% of rows". `n_row_pair_groups` / `n_row_pairs` /
  `n_rows_implicated` are now distinct keys. Budget truncation UNDER-counts and
  the caveat says so.
- **A column that is an exact linear function of two OTHERS is not independent
  evidence** (`_linearly_derived`, `copy_paste_detector/screening.py`). `QALY-SG` was
  exactly `0.125*(SG-V2) + 0.125*(SG-V7)` across 193 rows, so a chance tie on
  the inputs forced a tie in the output and one coincidence scored as three
  matches. The test must be an EXACT linear fit over an over-determined design:
  a mere functional dependency is near-vacuous on low-cardinality data and
  capped 15 columns on the first attempt, and a 3-parameter fit through <= 3
  distinct points is exact by construction, so binary columns are excluded.
  Row-pair evidence still has NO chance model — the remaining known gap.
- **A stage CLI's stdout is a regular file we tail, never a pipe**
  (`runtime._FileLineReader`). `claude -p` exits 0 having DROPPED whatever
  it had not written when its pipe was full; 7 of 57 stages of a 20-worker
  batch lost their `result` event that way (2026-10-18). When a stream still
  ends without one, the CLI-accepted StructuredOutput call in the transcript
  is the document (parse path `structured_output_tool_use`, cost UNKNOWN,
  `result_event: false`), and a stage with no document is `is_error: true`.
  See `tests/test_lost_result_event.py`.
- **A stage that errored but still produced a full report is PARTIAL, not
  FAILED.** `result["is_error"]` is set when any configured stage errored
  (it was `stage1 or stage2` in the deleted serial pipeline, when a sweep that
  exhausted its structured-output retries filed a complete, paid-for report
  -- $6.02, verdict, four findings -- into `failed.jsonl`). `batch.py`
  reports `partial`, writes to `partial.jsonl`, still records the cost row, and
  withholds only the move to `done/`.
- **A merged table cell is placed ONCE, at its anchor** (`_expand` in
  `extraction/jats.py`). Header rows and the column-0 row-label region repeat
  their text across the cells they cover; **every other body cell is
  anchor-only**, with empty continuations recorded in `spans`. Repeating a body
  value would turn one `3.7 (0.30)` with `colspan=4` into four identical
  (mean, SD) pairs — and `detect_duplication` escalates at three, so the PARSER
  alone would manufacture a `highly_suspicious` finding against an innocent
  paper. 355 such cells existed in the original paper corpus (removed from the repo 2026-08-09). The same rule is
  enforced in `supplements_read.py`, where python-docx repeats a merged cell by
  default (compare `cell._tc` by identity, never by `id()` — the proxies are
  transient and ids get reused).
- **Ragged rows are right-padded, never truncated, and flagged only when the
  SOURCE row was short.** Testing "row contains blanks" instead flags a third of
  all tables (160 vs 3 on this corpus) and makes `alignment_uncertain`
  worthless. A shifted column label hands GRIM/GRIMMER a triple the paper never
  reported, so the flag has to stay rare enough to be believed.
- **`extract_xml` output must NOT be routed through `parse_table` on the main
  path.** `parse_table` drops any cell `parse_cell` cannot reduce to a scalar
  (`tools/tableparse.py`, the `value is None and sd is None` skip), which silently discards every `estimate (CI)` cell —
  57 usable cells instead of 173 on a real clinical Table 1, and those are the
  highest-yield check on clinical papers. Each table already carries `cells`;
  send those to `parse_cells_typed`. `parse_table` is for `cross_check`
  reconciliation.
- **Elsevier XML has no `<table-wrap>` at all.** Four corpus files are
  `full-text-retrieval-response` with CALS `<tgroup>` tables, and **two of them
  are the only papers with no PDF**. A `table-wrap`-only parser turns those from
  "crashes loudly" into "reviewed, zero tables found" — a silent coverage hole
  that reads as a clean paper, which is worse than the crash.
- **An OCR'd numeral is neither `printed_table` nor `measured_raster`.** It has
  its own channel, `ocr_table`/`ocr_text` (`extraction/figures.py`,
  `registry.TRANSCRIBED_PROVENANCE`), at reliability tier 2. `printed_table`
  asserts both that the authors printed the number and that we know WHICH number
  — OCR delivers only the first, and a misread digit yields `impossible` against
  arithmetic that was fine. `measured_raster` states the wrong REASON: "a value
  read off a figure has no last printed digit" is false of an OCR'd numeral,
  which has exactly one. The error shapes differ too — a measured value's error
  is continuous with a computable sigma, an OCR error is discrete (48.90 or
  43.90, nothing between), so the `uncertainty` machinery is the wrong
  instrument. The exact-arithmetic gate refuses both channels with DIFFERENT
  sentences, and the OCR one names the promotion path: a human who confirms the
  cell against the image re-stamps it `printed_table`. That is the only route
  from an image to an `impossible` verdict, and it is deliberately manual.
  `dispatch.check_table` and `registry.ToolSpec.call` share one
  `UNVERIFIED_PROVENANCE` set — the table path is the one a scanned supplement
  actually travels, and it used to hold its own literal copy.
- **PDF extraction is docling-only** (`extraction/docling_tables.py`) — the
  pdfplumber ruled/inferred grid machinery (`grid_strategy`) is retired with
  it. Measured against XML ground truth, docling reads 92.0% precision /
  95.9% recall on numeric cells vs pdfplumber's 88.3/60.7, and pdfplumber
  rendered inline operators as glyph references (`t(28)(cid:1)(cid:5)3.33` —
  statcheck finds 0 statistics where docling's text yields 26). The measured
  numbers, and why routing/union ensembles were rejected, live in
  `extraction/docling_tables.py`'s module docstring. ONE exception, per file:
  when an out-of-band Mistral OCR extraction already exists for a PDF AND
  `prepass._text_layer_lies` finds that PDF's text layer corrupt (font-encoding
  damage, `glyphs.scan`), its tables are read from the page-image extraction
  instead, stamped `extractor: "mistral"` (`extraction/mistral_tables.py`; reads
  only, never calls the API, fails closed to the text layer).
- **The viewer's left pane does not assume a PDF** (`bundle.source_documents`).
  One record per document with a `kind` (pdf/image/html/epub/office/xml/text/
  unsupported) and a `locate` mode (`lines`/`dom`/`none`) stating the
  click-to-locate contract per document; `none` REFUSES IN WORDS rather than
  showing a pane that silently does nothing. PDF records keep their
  `render_all_pdfs` ids because `pdf_pages[].doc` joins to them, and document 0
  keeps the ids `bodytext`/`bodyrender`/`pg{n}` that `applyJump`, `goSource` and
  every evidence link address. Third-party HTML goes through `_safe_html`, an
  ALLOWLIST — the bundle is opened from `file://` and is offline by contract.
- **Table content is never inlined into `text`** — only a
  `[Table 2: caption — N rows x M cols]` placeholder. Some publishers nest
  `<table-wrap>` INSIDE a `<p>`, so paragraph flattening must skip table markup;
  otherwise the model can transcribe numbers from prose that has already lost
  the column alignment, which is the failure the whole module exists to remove.
- **A channel that did not run is not a channel that found nothing, and
  "it ran" is not "we kept the answer".** Every consumer of a corpus --
  `webapp_index.py`, the workbench, and anything that publishes — reports each
  check as a TRI-STATE at minimum: `ran` / `ran_result_discarded` / `refused` /
  `did_not_run` / `unknown`. MEASURED on `cerebrolysin_papers` 2026-08-17: of
  421 papers, **370 ran the image detector and 369 retained no result**
  (`panels/panel_index.json` is written by `analyze_paper_images` itself, so it
  proves the run happened); 142 have an empty `figmap/`; and **44 were never
  fetched** — a landing page and no PDF. Reporting any of those as "did not
  run" is false, and as "ran" it invites the reader to conclude the panels were
  examined and cleared. An early version of `looks_like_paper` required
  evidence that something WORKED and so hid all 44 unfetched papers, reporting
  373 harvested papers where the truth was 421 of which 44 were never obtained
  — our failure rendered as an absence of findings, by the tool whose job is
  making coverage visible. See `tests/test_webapp_index.py`.

### Comparing against R ground truth

`rsprite2` **infers decimal precision from the literal you pass** — `mean=4.0`
reads as 0 decimals. Any Python-vs-R comparison MUST pin `m_prec`/`sd_prec`
explicitly or it silently compares different questions (this produced a false
"repo is broken" finding once already).

## Adding a new tool (wiring checklist)

1. `tools/<name>.py` — pure function returning a dict with `severity`; guard bad
   inputs with structured errors.
2. Export in `tools/__init__.py`.
3. **Add a `ToolSpec` to the tool's family folder, `tool_specs/<family>/spec.py`
   (a new family: a new folder with `spec.py` + `TOOL.md`, listed in
   `tool_specs.FAMILIES`), its MCP description and integrity card to the
   `TOOL.md` beside it, and its name to `tool_specs.ORDER` (registry order,
   which the role allowlists follow). `registry.py` loads them; the MCP
   wrappers (`ALL_TOOLS` in `tools_mcp.py`) and EVERY role allowlist
   (TOOL_AGENT / SCIENCE_AGENT / ADJUDICATOR via `registry.stage_tools`;
   `STAGE1_TOOLS`/`STAGE2_TOOLS` in `agent.py`) are DERIVED from it — there is
   nothing to edit in either file.**
   Steps 3 and 4 used to say to hand-edit both; following that today produces a
   duplicate wrapper and a stage list that disagrees with the registry, which is
   the exact class of defect the registry exists to make unrepresentable.
   `stages=frozenset()` is legal and means CLI-only — but it must be a decision,
   and `registry.py:CLI_ONLY` is where its reason is recorded
   (`tests/test_tool_exposure.py` reads that dict; it used to hold its own copy).
4. **Nothing to do on the live pipeline** — step 3 already did it.
   `findings.v2.schema.json` ships a placeholder enum that
   `prompts.findings_schema_v2()` replaces at load time with every
   `registry.SPECS` name (its docstring: "wiring-checklist step 4 stops
   existing for v2"), and a misplaced placeholder raises rather than silently
   skipping injection. The hand-maintained v1 enum is gone with
   `findings.schema.json` (v1.27.0), so there is only one place to look. The
   schema is enforced by `--json-schema`, so an unlisted technique is a hard
   rejection, not a soft one.
5. **No CLI command is required.** `metascience tool run <name> --json ...`
   serves every registered tool through `ToolSpec.call`, and reproductions are
   generated in that form. A hand-written verb in `cli.py` (registry `cli=`)
   is optional, for people; it calls `tools/*.py` directly and skips the
   registry gates, so it must never be what a reproduction runs. A tool whose
   result should be replayable as a reproduction also needs its name in
   `deterministic.reproducible_tools()` (readers, the dispatcher, tracks, R
   wrappers and `run_python_script` are deliberately not).
6. Guidance the MODEL needs goes in the `description` block of the family's
   `TOOL.md` (that IS the MCP tool definition, and it IS sent; its first
   sentence is also the `mcp_brief` summary, so make it stand alone). The
   tools agent's procedure bullet for the tool goes in the same `TOOL.md` as
   a numbered `<!-- guidance:NN -->` block (assembled into `tool_expert.md` at
   `{{TOOL_GUIDANCE}}` in number order; renumber to insert). If it changes
   interpretation, also `rulebook.md` (or `science_error.md` for that
   analyst's beat). `docs/tool_reference.md` is documentation for humans
   and is **not** sent to any model -- writing guidance only there reaches
   nobody.
7. Tests in `tests/test_<name>.py`.
8. Regenerate `tests/data/registry_snapshot.json` — the golden snapshot pins
   every tool's schema, description hash, stages and CLI name, so a new tool
   fails 4 tests until it is added deliberately. Add a `CASES` entry in
   `tests/test_registry_equivalence.py` too (an empty list, with a comment
   naming the test file that covers it, is correct for tools needing a real
   file on disk).

`mcp_server.py` needs no change (it reads `ALL_TOOLS`).

**Extraction tools are the exception to steps 1, 2 and 4**: they live in
`extraction/`, not `tools/`, return extraction data rather than a `severity`,
and are absent from the `technique` enum (which lists forensic techniques —
`extract_pdf` is not in it either).

## Worktrees (standing rule)

Concurrent sessions should each work in their own `git worktree` (outside
Dropbox, e.g. on the data disk) and integrate through `main`. **Never use
`git stash` in a worktree**: the stash stack is shared by every worktree of the
repository, and on 2026-10-01 two agents' stashes were popped into each other's
trees. Commit work in progress instead. Some `tests/fixtures/papers/` files show as
modified in a fresh worktree (raw files in LFS-tracked paths); never stage
them -- add explicit paths, never `git add -A`. A fresh worktree can also hold Git LFS pointer stubs under
`tests/fixtures/papers/` and `eval/ground_truth/papers` (about 33 corpus tests then fail).
`git lfs checkout tests/fixtures/papers eval/ground_truth/papers` fills them from the
local LFS store without a download. The editable install points at the
Dropbox checkout, so in a worktree put that worktree's two source roots on
`PYTHONPATH` (and the image checkout's `src` when testing against it);
otherwise tests import the other tree's code.

## Pushing (standing rule)

**Push after every change, BEFORE running the full suite.** Then push again
only if the suite finds something that needed fixing.

**Push with `git push-both`** (`scripts/push_both.sh`). There are two repos:
- `full-history` (`The-Metascience-Observatory/forensic-metascience-ai-toolkit-full-history`)
  gets every commit. `main` tracks it, so a plain `git push` goes there.
- `origin` (`The-Metascience-Observatory/forensic-metascience-ai-toolkit`) is the
  public repo, and its history is not ours. The script adds ONE commit there
  per push, holding main's exact tree and named after the newest `Release`
  commit. Never `git push origin main`, which is always refused, and never
  force it, which would replace the public history with the full one.

Dan asked for this and he is right. Full-suite duration depends on the machine
and concurrent work; holding every finished change for it leaves work unpushed
and invisible -- which is how a branch drifts and how two people end up editing
the same thing. Frequent small pushes are cheaper to review and cheaper
to revert than one large one.

The order matters. Run the module tests that cover what you touched, push, then
start the full suite. That way the common case (suite green) costs one push, and
the rare case (suite red) costs two -- rather than every change waiting on the
slowest possible check.

WHAT THIS DOES NOT LICENSE. Pushing before the full suite is not pushing
untested code:

  - run the tests for every module you changed first, and read the result
  - a change whose own tests fail does not get pushed, ever
  - if the suite then goes red, fix and push again promptly -- a known-broken
    guard sitting in a shared repo is worse than a slow push
  - a cross-cutting guard can live in a module your diff never touches
    (`test_verdict_vocabulary` caught a retired-word collision this way, after
    584 targeted tests passed), so "my module tests pass" is evidence, not proof

## Testing & eval

- Unit suite: the September 10, 2026 workbench integration run passed **10,440
  tests**, with 173 skipped and one expected failure. This is a dated result, not
  a fixed suite size; use `python -m pytest tests --collect-only -q` for the current
  inventory. The default suite does not run the paid scientific pipeline. Run
  after any tool/prompt/schema change.
  `tests/test_tool_exposure.py` additionally pins that every validated tool is
  reachable from the MCP server, the CLI, and the per-stage allowlists in
  `agent.py` -- all three must agree, and a tool registered in only two of them
  is unusable by the agent while every other test still passes.
- Workbench verification: run `tests/test_workbench_*.py`, plus the relevant
  history/publication tests, with the project interpreter. PostgreSQL tests require
  `METASCIENCE_TEST_POSTGRES=1` and create/drop disposable schemas; they are not offline.
  Run TypeScript checks, `webapp/test/workbench.mjs`, and rendered browser checks
  when changing the bridge/UI. Use a separate `METASCIENCE_NEXT_DIST` when another
  dev server is active; do not overwrite its build directory. Validate actual rows,
  counts, reset/revocation messages, and media ranges, not only source code.
  Server-dependent image screening status, infinite queue, bulk review, and
  performance browser scenarios are explicit live checks, excluded from the
  default test stack. Their scripts document the server URL environment variable;
  use a controlled transport or disposable review data for tests that write.
- Live eval (`metascience eval` / `tests/test_eval.py`, gated on `RUN_EVAL=1`)
  runs the real pipeline on 4 fixtures (3 human-gold papers +
  `cerebrolysin_flow`, a regression fixture labeled from a validated
  parallel run) and costs money. After changing prompts or a tool the agent
  relies on, run `metascience eval --paper apple_cider` and confirm the
  baseline-uniformity finding is covered with severity in [3,5] and the
  verdict is `does_not_reconcile`.
  - **THE GATE'S RECORDED FAILURE WAS STALE, AND THE COMMAND COULD NOT RUN.**
    This entry used to cite a v1.0.0 run failing at recall 0.182 and block the
    legacy-body delete on it. The archived apple_cider scorecard
    (`benchmarks/paper_reviews/runs/apple_cider/scorecard.json`, v1.2.0, later the same day)
    records **recall 0.636, zero false positives, verdict
    `does_not_reconcile` matching expected, deterministic checks all passed,
    and severity calibration 1-of-1 in interval** — the 0.182 was superseded
    within hours and never updated here. Separately, re-running the command on
    2026-08-22 produced NO measurement at all: the `--budget-usd` default was
    $3.00, the parallel split gives the tool agent 0.40 of it, and that
    fixture's tool stage is measured at $2.81, so the stage was
    BUDGET-TRUNCATED before emitting findings. The default is now $8.00 and
    `tests/test_eval_cli.py` pins it against the measurement.
  - **MEASURED AT v1.11.1, 2026-08-22 ($6.63):** verdict `does_not_reconcile`
    matching expected, deterministic checks passed, severity calibration 1-of-1
    in interval, **zero false positives** — so both criteria named above PASS —
    but **recall_weighted 0.455, down from 0.636 at v1.2.0**, on 39 findings
    against that run's 21. It covers the critical gold finding
    (`baseline_uniformity`) and both minors, and MISSES ALL THREE MAJORS
    (`data_availability`, `effect_size_implausible`, `sprite_boundary_stacking`).
    Nearly twice the output, zero false positives, less of what matters: a
    dilution signal, not a precision problem.
  - **Historical eval context, not an active deletion gate:** the v1.11.1
    recall drop prompted broader evaluation at the time. The serial body was
    subsequently removed in v1.27.0; do not treat this old measurement as an
    instruction to block or reintroduce that retired implementation.
  - Re-running overwrites `benchmarks/paper_reviews/runs/<paper>/` in place, so the previous run
    survives only in git history. Both figures are recorded here for that
    reason: a comparison you can only recover by archaeology is one nobody
    makes.
  - **`judge_notes` came back EMPTY on the v1.11.1 run** (`judge_parse_path:
    "json_schema"`, so nothing errored — the judge simply returned `""`). That
    field is the diagnostic explaining every miss, and the v1.2.0 run's was a
    detailed paragraph naming exactly which tools never ran. Silently empty is
    the wrong failure mode for the field that would tell you why recall fell.
- **`metascience eval --skip-analysis` is not free either.** It skips the
  paid analysis pipeline, not the LLM judge. It now refuses outright when a selected
  fixture has no `benchmarks/paper_reviews/runs/<paper>/forensic_review/report.md`, because the
  harness reads the flag as "reuse the run IF one exists" and would otherwise
  run the full paid pipeline — silently, on the one invocation passed to prevent
  exactly that. The CLI and harness `--model` defaults are pinned equal
  (`sonnet`) by `tests/test_eval_cli.py`, and so are their `--budget-usd`
  defaults — two places declare each, and the budget one had no pin until it
  drifted low enough to break the documented command.

## Conventions

- Severity strings are lowercase everywhere; the schema/enum is the contract.
- Prompt text lives in `modules/<name>/prompt.md`, `core/prompts/` and each
  tool family's `TOOL.md`; edit those, never hardcode prompt text in Python.
- Reports must have no leaked model preamble (structured `report_markdown`
  output enforces this; `evaluation/deterministic.py` checks it).

## Publication embargo marker

`history_publication.{sync,refresh}` refuse a corpus carrying `EMBARGO.json` at
its root, and so does the webapp's website-publication route: nothing derived
from it may reach PubPeer, the public site build or `public_findings`. A marker
file (survives any database state), a hard raise (a silent filter is
indistinguishable from a guard that is not running), and an unreadable marker
still refuses. The corpus builder that writes these markers lives outside this
repository.

`-m fetchpdf_grey.cli` is a **silent no-op** (no `__main__` guard: prints nothing,
exits 0, fetches nothing). The package entry point is `-m fetchpdf_grey`.

