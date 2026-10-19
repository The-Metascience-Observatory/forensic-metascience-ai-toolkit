# findings_v2 — the unified findings data contract

- **Status:** approved 2026-08-21.
- **Source of truth:** THIS DOCUMENT. It was derived from the approved 2026-08 overhaul plan (a working file at `~/.claude/plans/`, since retired and reused for later planning — do not consult it)
  (Parts A, B §B4/B5, C §C1/C5, reconciliation R1–R6). Where that plan's later
  sections or verification passes corrected an earlier sketch, THIS document states
  the corrected rule and the corrected rule is normative. The v0 sketch in the plan
  is superseded.
- **Implemented by master phases:** 1 (schema, hasher, severity9, annotators, dual
  emission), 4 (parallel pipeline consumes v2 natively), 5 (converter), 5N (DB
  mirror + aliases), 7 (eval + cutover). Phases 2/6 consume it (anchors, webapp).
  These phases are complete; phase references below are historical.
- **Sibling specs:** `adjudicator.md` (docket + apply()), `anchors.md` (enrichment),
  `pipeline.md` (agents, `--tools` incl. the MCP surface for the science agent),
  `webapp_db.md` (DDL, db-push). This file owns the RECORD; those own the flows.

## 0. Two axes, one enum untouched

The tool-layer 5-enum (`impossible|highly_suspicious|suspicious|indeterminate|
consistent`, `tools/severity.py`) is an **epistemic verdict about a number** and
survives untouched in every ToolSpec, guard, and test. The 1–9 severity
(`severity9.py`) is a **correction-outcome ranking**: what a journal
would have to do if the finding were confirmed. A finding carries both — the enum
inside `tool_verdict`, the ranking in `provisional_severity`/`severity` — and the
webapp sorts on severity while metascience stats count on `technique` ×
`impossible`/`tool_verdict`. Neither axis is derivable from the other.

## 1. The finding record

Writer vocabulary: **model** (producer LLM output), **code** (deterministic
producer: image/text track builders, screen runner), **annotator** (pipeline
annotator chain), **adjudicator** (via `adjudicate.apply()`), **converter**
(`migrate_v2.py`, deleted in 1.100.0 after its last run; documents it wrote
still carry the `legacy` block below). A field whose writer is not *model* is ABSENT from the
producer-facing subset schema (§4) — enforced by omission, never by prose.

| Field | Type | Writer | Req | Rule |
|---|---|---|---|---|
| `finding_id` | `f_`+16 hex | annotator | yes | Content hash, §5. DB natural key with `run_id`. |
| `finding_id_hasher` | string | annotator | yes | Hasher version that minted `finding_id` (§5). |
| `slug` | string | model/code | yes | Old human id (`table2_bdi_grim`). Display only; never a join key. |
| `producer` | enum §1.1 | code | yes | Stamped by the harness per agent/track, never model-chosen. |
| `technique` | string §1.2 | model/code | yes | Registry tool name or fixed non-tool value. Equality-joins to the toolcall ledger. |
| `title` | string 8–90 | model/code | yes | §8. Adjudicator may rewrite; original kept in `adjudication.title_was`. |
| `description` | string 20–700 | model/code | yes | §8. Plain English. Rewrites preserved in `description_was`. |
| `location` | string | model/code | yes | Reader's terms: "Table 2, BDI row". |
| `outcome` | `problem\|pass\|undecided` | model/code | yes | Replaces v1 `consistent` bool. `pass` = ran and found nothing; `undecided` = refusal/indeterminate. |
| `provisional_severity` | int 1–9, null | model/code, clamped by annotator | on `problem` | Producer's estimate; pipeline clamps under the evidence-channel caps (§7); no ceiling. Null unless `outcome=problem`. |
| `severity` | int 1–9, null | adjudicator | — | Final. Null unless `outcome=problem` and `adjudication.action≠discarded`. When the adjudicator did not run, annotator copies provisional here and sets `severity_is_provisional`. |
| `severity_is_provisional` | bool | annotator | yes | True whenever `severity` was not adjudicator-assigned. Always true for `fast_screen` and converted legacy rows. |
| `impossible` | bool | annotator | yes | Derivation rule §1.5. Neither model nor adjudicator can set it. Default false. |
| `tool_verdict` | object, null | annotator | — | §1.4. Joined from the validated toolcall ledger, never trusted from prose. |
| `cross_check` | string | annotator | — | On ANY adjudicator-skip/fail path, every `impossible: true` row is stamped `"not_run"` (pipeline.md §3, adjudicator.md §8): rendered as a report limitation and barred from headline use. Absent otherwise. |
| `computed_by` | enum §1.3 | annotator (ledger-derived), code for tracks | yes | Evidence-weight dimension (R4). |
| `quarantined` | bool | code/annotator | yes | Default false. Quarantined rows stay `problem`, cap at `QUARANTINE_CAP=3`, never headline. |
| `quarantine_reason` | string | code | if quarantined | Detector's own words; a bare cap with no reason is forbidden. |
| `quote` | string | model | see §3 | ONE contiguous verbatim span with the load-bearing numbers (v1 semantics). |
| `quote_verified` | enum | annotator | — | `verbatim\|elided\|stitched\|unverified\|absent` — v1 semantics unchanged. |
| `quote_source`, `quote_problem` | string | annotator | — | v1 semantics unchanged. |
| `source` | object | annotator | — | v1 `source_quote*` block, unchanged: the passage the CHECKED numbers came from, per the validated call. |
| `inputs` | object | model/code | — | Tool arguments. Scalars here feed the hash (§5). |
| `reported`, `computed` | object | model/code | — | v1 semantics: printed vs derived, derivations named. |
| `consequence` | object | model + annotator | — | v1 shape (`flips_significance`, `claims_affected`, `basis: computed\|asserted`, `explanation`). |
| `notes` | string | model | — | Innocent explanations belong here, not omitted. |
| `artefacts` | array | annotator | — | Paper-relative POSIX paths, v1 semantics. |
| `web_sources` | array | model | if `basis=web_lookup` | `[{url, title, quote, accessed}]`. Legal only with `producer: science_error` (and future web-enabled producers). A row citing web_sources with zero ledger web calls is flagged `web_unbacked` by the annotator. |
| `basis` | `tool\|web_lookup\|model_knowledge` | model | — | Science-agent factual findings. `model_knowledge` caps provisional at 3 (§7). |
| `reproduction` | string | model/code | yes* | Exact `metascience …` command; *or absent when `reproduction_kind=no_command_applies`. |
| `reproduction_kind` | `command\|script\|no_command_applies` | annotator | yes | `script` (R4) points at a persisted `analysis_code/` file. |
| `reproduction_valid`, `reproduction_problem` | bool/null, string | annotator | — | v1 semantics unchanged. |
| `anchors` | array | model/code, enriched in place by annotator | see §3 | Producers emit minimal records (§3); Part C's `anchors.annotate_findings` enriches post-adjudication (R5). |
| `anchor_summary` | object | annotator | — | One status key per surface the paper HAS (`pdf`, `xml`, `html`, `sheet`) + `primary_anchor_id`, `page` — anchors.md §8. |
| `anchor_problem` | string | model/code | — | Named-absence escape hatch: why the producer could not supply an anchorable passage (anchors.md §5). Absence is a statement, never a silent gap. |
| `adjudication` | object | adjudicator | — | §1.6. Absent = adjudicator never saw the row (distinct from `kept`). |
| `legacy` | object | converter | — | §1.7. Present only on converted rows. |

Dropped v1 keys and their heirs: `id`→`slug`, `consistent`→`outcome`,
`explanation`→`description`, `severity_before_quarantine`→
`tool_verdict.quarantined_raw`, `severity_source`→ the structural
provisional/final split (a divergence is now two fields, not a sidecar).

### 1.1 `producer` enum

`tool_expert | science_error | image_track | text_track | raw_data_track |
fast_screen | legacy_sweep | legacy_editorial`

`raw_data_track` (added 1.76) is the opt-in `raw_data` module's copy-paste
detector over a paper's spreadsheets: quarantined, one row per (file, kind),
and never the headline (`adjudicate._unscreened`).

`image_track` rows appear only when the separately distributed image analysis
package is installed (reached through `image_plugin.py`, since 1.77). Without
it a configured image module records `execution_status: "unavailable"` and its
channel reads `refused` with a limitation saying the figures were not examined
-- never an empty result that reads as clean.

`fast_screen` is in the enum FROM DAY ONE (Phase 1) so the screen agent's arrival
(Phase 9) is not a schema break. Its structural constraints:
`severity_is_provisional=true` always and `impossible=false` always (screen
runner AND a DB CHECK), provisional ≤ 4 and `computed_by=model_reading`
(app-layer rules in the screen runner — deliberately NOT CHECK constraints,
per webapp_db.md §2/§6), excluded
by default from accusation-grade fire-rate stats (a screen is a funnel, not
evidence — the Table-1 screening lesson).

### 1.2 `technique` namespace

Generated at schema-assembly time = **registry-derived exact tool names**
(every `registry.SPECS` name; ends the `grim` vs `grim_check` drift; fire-rate
joins to `toolcalls.*.json` become equality joins) **plus fixed non-tool
values**: `not_computational`, `no_tool_exists`, `tool_existed_unused`,
`legacy_unattributed`, `factual_claim`, `internal_contradiction`.
`check_flow_arithmetic` enters via the registry derivation when the flow tool
lands (Phase 3), not as a hand-added literal. v1's `manual` is retired: the
converter maps it per the 2026-08-13 split, new rows may never use it.

### 1.3 `computed_by`

`registry_tool | agent_code | model_reading | deterministic_track` (R4).
Annotator-derived from the ledger where possible. `agent_code` is legal ONLY
with `producer: science_error` (deterministic validation check), ranks below
`registry_tool` in evidence weight, caps provisional at 4, and can never yield
`impossible` (§1.5). A `computed` number citing a script with no matching
`run_python_script` call in the ledger is flagged `code_unbacked`
(known-positive test required). Per the Phase-0 resolution (pipeline.md §10),
science-agent code runs ONLY through the sandboxed MCP tool
`run_python_script` — never a backend shell.

### 1.4 `tool_verdict`

```jsonc
{ "severity": "impossible",        // the 5-enum, verbatim from the validated call
  "tool": "grim_check",            // registry name of the call joined to
  "validated": true,               // passed the registry validation gate
  "quarantined_raw": null }        // 5-enum a quarantined detector WOULD have
                                   // returned (v1 severity_before_quarantine)
```
Written only by the annotator's tool-verdict reconciliation join. Null when no
tool call backs the row (`not_computational`, factual claims). Per-tool
impossible/fire stats count on THIS field, never on prose.

### 1.5 `impossible` derivation rule

`impossible: true` **iff** a **validated** call of a tool whose registry
`evidence` class is `absolute` returned `impossible` AND survived
reconciliation. Structural corollaries: unreachable from `agent_code`,
`model_reading`, quarantined rows, `fast_screen`, and any probabilistic or
descriptive tool. The converter sets it only when the legacy technique maps to
an absolute tool AND the archived severity was `impossible` (conservative).
This is Dan's "code can't mint impossible" guardrail made structural — it is
what makes per-tool impossible-fire counts trustworthy for metascience.

### 1.6 `adjudication` (per-finding)

```jsonc
{ "action": "kept|merged|downgraded|upgraded|discarded",
  "rationale": "…", "category": "…",       // category enum owned by adjudicator.md
  "merged_into": "f_…", "merged_from": ["f_…"],
  "severity_from": 4,                       // provisional it moved from
  "title_was": "…", "description_was": "…" }  // originals, when rewritten
```
Rules (enforced in `adjudicate.apply()`, constants from `severity9.py`):
join on `finding_id` (the position-zip defense); unknown ids dropped;
**discarded rows are RETAINED** with `severity: null` — "ran and discarded"
must stay distinguishable from "did not run" (LESSONS #1); merge chains
validated; an innocent-explanation clear whose `evidence_quote` is not
locatable in the paper demotes to `kept`; silence = kept-with-provisional;
total adjudicator failure fails OPEN (findings ship provisional + doc-level
`adjudication.failure` — never lost). Severity bounds: §7.

### 1.7 `legacy` block

`{from_schema, original_id, original_severity, source_file, migrated_at}`.
Converter contract (Phase 5): severity via `FIVE_TO_NINE`, provisional=final,
`severity_is_provisional: true`; producer `legacy_sweep` for stage-1 rows,
`legacy_editorial` + technique `legacy_unattributed` for report.json rows with
no stage-1 twin; descriptions from deterministic templates flagged legacy —
never fabricate fluent prose for old findings; `review.json` is NEVER rewritten
(verdicts join via `legacy.original_id`, which stores the PREFIXED review key
exactly as written, e.g. `image:IMGDUP-3`); output `findings.v2.json` beside,
never over, v1; idempotent via `source_sha256`.

## 2. Document level (`schema_version: "2.0"`)

| Key | Writer | Rule |
|---|---|---|
| `schema_version` | pipeline | const `"2.0"`. |
| `paper_id`, `paper_title` | pipeline | as v1. |
| `run_id` | pipeline | `r_<hash>`, minted once per run; screens mint their own. Joins to run_meta and the DB `runs.run_uid`. |
| `paper_metadata` | pipeline | PROJECTION of `metadata.json` (schema 1.1): v1 keys + `journal_normalized`, `authors_list [{given, family, full}]`, `year`, `metadata_status`. Pipeline-written; the model never invents metadata. |
| `findings` | mixed | array of §1 records. |
| `channels` | pipeline | Per producer/track channel: `{state, detail}`, state ∈ `ran \| ran_result_discarded \| refused \| did_not_run \| unknown`. **Normative corrected rule:** for every denominator, "ran" means state ∈ {`ran`, `ran_result_discarded`} — a channel that demonstrably ran and retained nothing STILL RAN (counting only `ran` drops ~369 of the 370 measured image-channel papers and inflates that fire rate by orders of magnitude). `refused`/`did_not_run`/`unknown` are always printed separately, never folded into "did not fire". |
| `adjudication` | pipeline | Doc summary: `{ran, verdict, paper_severity, headline_finding_id, confidence, summary, n_kept, n_merged, n_discarded, n_downgraded, n_upgraded, n_not_adjudicated, n_unknown_ids, failure}` (the last three per adjudicator.md §5/§6). `summary` is the adjudicator's bounded narrative — it replaces `report_markdown`. `headline_finding_id` must reference a non-quarantined, non-discarded row. |
| `coverage`, `anatomy`, `unchecked`, `statistics_register`, `figures` | model/pipeline | Survive from v1 unchanged in shape; **producer-optional** (the science agent is not schema-forced to emit `anatomy`; the merged document carries the union). |
| `checks_tally` | pipeline | Survives: the merged denominator block (`agent.checks_tally` — severity histogram + the passes `check_table` collapses + convention-rescue counts) handed to the adjudicator so the verdict has a denominator. |
| `provenance` | pipeline/converter | `{pipeline_version, git_sha, prompt_sha256, registry_sha256, analysed_at, analysed_at_source, backend, model}`. `analysed_at_source: "file_mtime"` is mandatory when the converter backdated from mtime — a file date is never presented as a run date. |

## 3. Anchors slot — minimum producer contract (R5)

Producers emit MINIMAL anchor records; `anchors.annotate_findings` (spec:
`anchors.md`) enriches them **in place** post-adjudication into the persisted
schema. Producer kinds:

- `{"kind": "quote", "quote": "…", "label": "Table 2", "role": "said|against|source"}`
  — mandatory for every text/numeric `problem` finding from BOTH agents: one
  contiguous verbatim span, ≥8 words or ≥40 chars, containing the load-bearing
  numbers, no ellipses. Satisfies Part C's `passages[]` requirement; the
  top-level `quote`/`quote_verified` remain the verification channel.
- `{"kind": "page_bbox", "file": "…", "page": 1, "bbox": [x0,y0,x1,y1]}` —
  image findings: placements VERBATIM from `panels/panel_index.json`, never
  re-derived.
- `{"kind": "table_cell", "table": "…", "cells": ["B4","C4"], "sheet": "…"}` —
  sheet/supplement findings.

Tortured-phrase findings carry the matched phrase as a quote anchor (upgrades
them from unlocatable to anchored). A finding with no anchorable evidence sets
`anchor_problem` — named absence, not omission.

## 4. Producer-facing subset schema rule

Each producer's `--json-schema` is a SUBSET of this contract. Excluded by
omission (the schema physically lacks them; `additionalProperties: false`
rejects attempts): `finding_id`, `finding_id_hasher`, `severity`,
`severity_is_provisional`, `impossible`, `tool_verdict`, `computed_by`,
`adjudication`, `legacy`, `anchor_summary`, `cross_check`, and every
annotator-written field (`quote_verified`, `quote_source`, `quote_problem`,
`source`, `artefacts`, `reproduction_kind`, `reproduction_valid`,
`reproduction_problem`). `anchor_problem` IS producer-writable — the
named-absence escape hatch for a producer that cannot supply a passage
(anchors.md §5). Per-producer narrowing: only the science agent's
subset contains `web_sources`/`basis`; track builders (code, not schema-bound)
must still emit only subset-legal keys plus `quarantined`/`quarantine_reason`.
A generated test asserts subset ⊂ full schema and that no excluded field is
reachable from any producer schema.

## 5. `finding_id` hashing

- **Inputs** (in order): `paper_id`, `producer`, `technique`, `anchor_key`,
  and the finding's **input scalars** — the scalar-valued entries of `inputs`,
  as sorted `(key, value)` pairs (arrays/objects excluded).
- **`anchor_key`** (resolution of a plan gap, normative): from the FIRST
  producer anchor by precedence quote → table_cell → page_bbox:
  quote → `fold_rendering(quote)` (typography-folded text — stable across
  PDF/XML surfaces and across anchor ENRICHMENT, which must never move an id);
  table_cell → `"{sheet|table}:{sorted cells}"`; page_bbox →
  `"{file}:{page}"` (page, never bbox — coordinates jitter across PyMuPDF
  versions); no anchors → `fold_rendering(location)`.
- **Canonicalization**: keys sorted; numbers rendered as shortest round-trip
  repr with integral floats as ints (`3.530` → `3.53`, `4.0` → `4`); strings
  NFC-normalized, whitespace collapsed; fields joined with `\x1f`, records
  with `\x1e`; UTF-8; `finding_id = "f_" + sha256(payload).hexdigest()[:16]`.
- **Hasher versioning**: `severity9`-adjacent constant
  `FINDING_ID_HASHER_VERSION` (initially `"1"`), recorded per finding as
  `finding_id_hasher`. Any change to inputs or canonicalization bumps it.
  Existing ids are NEVER recomputed in place.
- **Alias mechanism for drift: DEFERRED** (Dan, 2026-08-21 — superseded by the
  MULTI-REPORT model, webapp_db.md §15): every run's report is reviewed
  INDEPENDENTLY, so verdicts are RUN-SCOPED and never carry across runs —
  alias-matching is not needed for correctness. Cross-run context is a plain
  equality join (identical evidence → identical `finding_id` across runs);
  the GUI shows another run's verdict as a context chip, never inherits it.
  `db-push` still PRINTS the orphaned-reviews report (file-import path).
  **Normative corrected rule: `reviews` is literally append-only** — no row
  is ever edited or re-pointed; the current verdict is the latest row per
  (RUN, issue, reviewer). File-mode legacy joins use `legacy.original_id`
  against review.json keys, scoped to the run the workbench displayed.

## 6. Example rows (one per producer; elided with `…`)

```jsonc
// tool_expert — GRIM, validated absolute tool, adjudicated
{ "finding_id": "f_9c1e22ab34cd56ef", "finding_id_hasher": "1",
  "slug": "table2_bdi_mean_grim", "producer": "tool_expert",
  "technique": "grim_check", "computed_by": "registry_tool",
  "title": "Table 2: BDI-II mean 23.47 is impossible for n=28",
  "description": "Table 2 reports mean 23.47 (SD 9.1) for the BDI-II in the intervention arm (n=28). No set of 28 integer scores can produce a mean of 23.47 at two decimals; the nearest attainable values are 23.46 and 23.50. A transcription slip in the mean or the n would explain it.",
  "location": "Table 2, BDI-II row", "outcome": "problem",
  "provisional_severity": 3, "severity": 3, "severity_is_provisional": false,
  "impossible": true, "quarantined": false,
  "tool_verdict": {"severity": "impossible", "tool": "grim_check",
                   "validated": true, "quarantined_raw": null},
  "quote": "BDI-II scores in the intervention group (M = 23.47, SD = 9.1, n = 28)…",
  "inputs": {"mean": 23.47, "n": 28, "decimals": 2, "data_type": "integer",
             "bound_source": "stated"},
  "anchors": [{"kind": "quote", "quote": "BDI-II scores…", "label": "Table 2"}],
  "reproduction": "metascience tool run grim_check --json '{\"bound_source\":\"stated\",\"data_type\":\"integer\",\"decimals\":2,\"mean\":23.47,\"n\":28}'",
  "adjudication": {"action": "kept", "category": "…",
                   "rationale": "Cross-checked against r_grim; no bound ambiguity."} }

// science_error — web-verified factual claim (no registry tool)
{ "finding_id": "f_77aa01bc9932de10", "finding_id_hasher": "1",
  "slug": "gfap_antibody_species", "producer": "science_error",
  "technique": "factual_claim", "computed_by": "model_reading",
  "basis": "web_lookup",
  "web_sources": [{"url": "https://…", "title": "Anti-GFAP ab7260 datasheet",
                   "quote": "Rabbit polyclonal to GFAP", "accessed": "2026-08-21"}],
  "title": "Methods: ab7260 described as a mouse monoclonal; it is rabbit polyclonal",
  "description": "…", "location": "Methods, Immunohistochemistry",
  "outcome": "problem", "provisional_severity": 4, "severity": 4,
  "severity_is_provisional": false, "impossible": false, "quarantined": false,
  "tool_verdict": null,
  "quote": "…mouse monoclonal anti-GFAP (Abcam ab7260, 1:500)…",
  "anchors": [{"kind": "quote", "quote": "…"}],
  "reproduction_kind": "no_command_applies",
  "adjudication": {"action": "kept", "rationale": "…"} }

// image_track — deterministic, pre-adjudicated upstream (inputs.image_adjudication)
{ "finding_id": "f_31f00c2ab8d94477", "finding_id_hasher": "1",
  "slug": "fig3_panel_dup", "producer": "image_track",
  "technique": "image_duplication", "computed_by": "deterministic_track",
  "title": "Figure 3: panels B and D share a duplicated region across treatment groups",
  "description": "…", "location": "Figure 3, panels B/D",
  "outcome": "problem", "provisional_severity": 4, "severity": 4,
  "severity_is_provisional": false, "impossible": false,   // duplication is NEVER impossible
  "quarantined": false,
  "tool_verdict": {"severity": "highly_suspicious", "tool": "analyze_paper_images",
                   "validated": true, "quarantined_raw": null},
  "inputs": {"image_adjudication": {"verdict": "unexplained", "…": "…"}},
  "anchors": [{"kind": "page_bbox", "file": "paper.pdf", "page": 6,
               "bbox": [72.0, 401.5, 291.2, 540.0]}],
  "reproduction": "metascience image-analysis paper.pdf --paper-dir …",
  "adjudication": {"action": "kept", "rationale": "…"} }  // ranked by the adjudicator (severity_is_provisional: false requires it)

// text_track — quarantined detector: capped, reasoned, never headline
{ "finding_id": "f_ab8812c4e07731fa", "finding_id_hasher": "1",
  "slug": "tortured_phrase_counterfeit", "producer": "text_track",
  "technique": "tortured_phrases", "computed_by": "deterministic_track",
  "title": "Discussion uses 'counterfeit consciousness' for 'artificial intelligence'",
  "description": "…", "location": "Discussion, para 4",
  "outcome": "problem", "provisional_severity": 2, "severity": 2,
  "severity_is_provisional": true,          // adjudicator declined to re-rank a quarantined row
  "impossible": false, "quarantined": true,
  "quarantine_reason": "Dictionary is a 51-row seed; per-phrase precision unmeasured.",
  "tool_verdict": {"severity": "indeterminate", "tool": "detect_tortured_phrases",
                   "validated": true, "quarantined_raw": "suspicious"},
  "anchors": [{"kind": "quote", "quote": "…counterfeit consciousness…"}],
  "reproduction": "metascience tool run detect_tortured_phrases --json …",
  "adjudication": {"action": "kept"} }  // silence rule: kept-with-provisional (adjudicator.md §5.7)
```

## 7. `severity9.py` (one severity source of truth — R1)

Module contents, consumed by prompts (`rubric_markdown()` at assembly time),
report_render, the adjudicator's `apply()`, and the Part C codegen
(`as_json()` → `gen-webapp-constants` → **both**
`webapp/lib/constants.gen.ts` and `docs/severity_ladder.json`, byte-compared
in `tests/test_webapp_constants.py`). `tools/severity.py` stays the tool-layer
5-enum world.

**Each `Level` carries both audiences' fields** rather than the ladder being
forked into an agent copy and a website copy: `finding_rubric` + `boundaries`
are what reach the prompts, `label`/`correction_outcome`/`web_summary`/`colors`
are what reach the public ladder page. A second hand-written copy for the
website would be the `tool_reference.md` failure (prose maintained for an
audience of nobody).

**The correction outcome is the LABEL, not the TEST** (introduced at ladder
version 2; the current version is `severity9.LADDER_VERSION`, `"3"` at 1.77.0).
Rungs 2/3/4 were previously discriminated by journal notice names — erratum
vs. correction vs. corrigendum — which are publisher-dependent and so an
unstable thing for a classifier to reason from. Every `boundaries` entry now
keys on the paper: 2→3 does a reported result change; 3→4 must something be
re-run rather than re-reported; 4→5 does an abstract-level claim change; 5→6
can the surviving results still be bounded; 6→7 is the outcome settled; 7→8 is
there positive evidence of intent; 8→9 does it span multiple papers or cause
external harm. Two rungs were repaired by this: **3/4** was near-vacuous, and
**6** keyed on investigation status, which the pipeline cannot know — it now
records unbounded scope and is assignable. Levels 1–2 are one reporting band
(`ACCUSATORY_MIN = 3` already treats them as one); 2 is the default when
unsure.

**The ladder** (summary; canonical: `docs/severity_ladder.json`, generated
from `severity9.py`. Slugs/labels are the
canonical rendering — e.g. `S7 · fatal error`, "Level 6 — results unreliable
(retraction candidate)"):

| n | slug | label | correction outcome |
|---|---|---|---|
| 1 | `trivial` | Trivial error | no formal correction |
| 2 | `minor` | Minor error | erratum if needed |
| 3 | `notable` | Notable error | localized correction/clarification |
| 4 | `local_flaw` | Localized methodological flaw or omission | public correction (corrigendum) |
| 5 | `conclusions_affected` | Major error affecting conclusions | corrigendum or partial retraction |
| 6 | `unreliable` | Severe error — results unreliable | expression of concern; retraction candidate |
| 7 | `fatal_error` | Fatal error invalidating main findings | retraction (honest error) |
| 8 | `misconduct` | Serious misconduct | retraction (misconduct) |
| 9 | `extreme_misconduct` | Malicious or extreme misconduct | retraction, sanctions |

**Maps.** `FIVE_TO_NINE = {"suspicious": 3, "highly_suspicious": 4,
"impossible": 5}` (one value, stated once — the legacy webapp badge derives
from it). `OUTCOME_FROM_FIVE = {"consistent": "pass", "indeterminate":
"undecided", else: "problem"}`; legacy pass/undecided rows get null severity.

**Caps and constants** (every clamp in the pipeline and `apply()` imports
these; no literal severities elsewhere):

- **No ceiling and no evidence-class cap (v1.14.0).** `PROVISIONAL_CAP`,
  `ADJUDICATOR_MAX_DEFAULT`, `ADJUDICATOR_MAX_MANIPULATION` and
  `PIPELINE_MAX` are removed; any role may write any rung 1–9. The caps
  below key on the evidence CHANNEL a number arrived through, never on the
  technique's class or on the level itself.
- `AGENT_CODE_CAP = 4` (R4: agent-code evidence is probabilistic-class).
- `MODEL_KNOWLEDGE_CAP = 3` (a memory-based factual claim without a recorded
  lookup; cap value resolved here — the plan says "capped" without a number).
- `FAST_SCREEN_CAP = 4` (locked decision; app-layer rule in the screen runner
  and db-push — deliberately NOT a DB CHECK; the DB CHECK covers only
  never-`impossible` + `severity_is_provisional`, webapp_db.md §2/§6).
- `QUARANTINE_CAP = 3`; quarantined rows never headline.
- `MODEL_READING_CAP = 3` — a tool technique whose row cites no call
  asserted arithmetic it never performed.
- `ACCUSATORY_MIN = 3` — at/above it a `problem` finding is accusation-grade:
  it must carry a verified quote or a validated `tool_verdict`, it enters
  accusation-grade fire-rate stats, and draft tooling treats it as publishable
  criticism. Levels 1–2 are record-keeping, not accusations.
- **Upgrade rule (normative):** adjudicator upgrades are limited to +2 over
  provisional and only via `merged_pattern`, `consequence_reassessed` or
  `manipulation` — **merged pattern findings are exempt from the +2 limit**
  (a pervasiveness merge may express a level no single row could).

**Rubric** (`rubric_markdown()`, embedded into agent + adjudicator prompts):
the per-finding question is *"If this one finding were confirmed, and it were
the only problem in the paper, what would the journal have to do about it?"*
The rubric carries no composition rules (removed v1.14.0): the nine rungs,
their boundary tests and that one question are the whole instruction.

## 8. Title and description rules

Schema-enforced lengths: `title` 8–90 chars, `description` 20–700 chars
(hard `--json-schema` bounds, not prose requests). Style, checked by
`evaluation/deterministic.py` where mechanical:

- Title: one clause, place + discrepancy, numbers as printed
  ("Table 2: BDI-II mean 23.47 is impossible for n=28"). No filler
  ("Possible issue with…"), no technique jargon without its plain reading,
  no trailing period.
- Description: plain English, 1–4 sentences: what the paper prints (verbatim
  values), what the check computed or expected, why it matters, and the
  leading innocent explanation when one exists. No markdown, no model
  preamble, no first person.
- **Inconsistency, never intent**: "fabricated", "fraud", "manipulated" and
  kin are banned from producer titles/descriptions at every level; even
  adjudicator prose keeps severity language within the assigned rung's
  correction outcome (a level-3 finding is not described in retraction
  vocabulary). Level 8–9 labels name the CATEGORY the evidence was gated
  through, not an accusation of a person.
- Converted legacy descriptions come from deterministic templates and are
  flagged by the `legacy` block — fluent prose is never synthesized for a
  finding the model of record did not write.

## 9. Validation invariants (deterministic.py + tests)

`evaluation/deterministic.py:check_findings_v2` owns the mechanical slice of
these; the rest are enforced in `adjudicate.apply()`, the annotators and tests.

1. `severity` non-null ⇔ `outcome=problem` ∧ `adjudication.action≠discarded`.
2. `impossible=true` ⇒ `tool_verdict.validated=true` ∧ tool's registry
   evidence class is `absolute` ∧ `tool_verdict.severity="impossible"`.
3. `quarantined=true` ⇒ `quarantine_reason` present ∧ effective severity ≤ 3
   ∧ not the headline finding.
4. `producer=fast_screen` ⇒ `severity_is_provisional` ∧ ¬`impossible` ∧
   provisional ≤ 4.
5. `computed_by=agent_code` ⇒ `producer=science_error`.
6. `web_sources` present ⇒ ≥1 ledger web call (`web_unbacked` otherwise);
   `reproduction_kind=script` ⇒ matching `analysis_code/` file and
   `run_python_script` ledger call (pipeline.md §10).
7. Discarded findings retained; every producer finding ends adjudication with
   a disposition (reconciliation is total).
8. Title/description length bounds; five-state channel keys valid; denominator
   consumers count `ran_result_discarded` as ran (golden stats fixture).
9. All guards above ship with KNOWN-POSITIVE tests (LESSONS #4: a guard that
   cannot fire reads as though it had passed).

## 10. Adjudicator-skip semantics (normative pin — resolves critic open #8)

Per-row `adjudication` object present **⟺ `adjudicate.apply()` executed over
that row's docket**. Three distinct cases, three distinct shapes:

| Case | Who writes | Row state |
|---|---|---|
| apply() ran, row addressed | apply() | `adjudication {action …}`, final `severity`, `severity_is_provisional: false` |
| apply() ran, row unmentioned (silence rule) | apply() | `adjudication {action: "kept", rationale: "not addressed by the adjudicator"}`, `severity = provisional`, `severity_is_provisional: true` |
| adjudicator never ran (budget floor, zero-findings skip, crash before apply) | the PIPELINE annotator | **no per-row `adjudication` object at all**; `severity = provisional`, `severity_is_provisional: true`; doc-level `adjudication.ran: false` (+ `skipped_reason` or `failure`); `impossible` rows stamped `cross_check: "not_run"` |

So an absent `adjudication` object always means "the adjudicator never saw
this run", never "it saw the row and said nothing" — the ran-vs-didn't
distinction the whole repo is built on, applied to its own reviewing stage.

## 11. Metadata enrichment (A5 — owned here; resolves critic open #3)

- **`src/forensic_metascience_ai_toolkit/journal_names.py`** (new): `normalize(journal:
  str) -> str` — abbreviation expansion → variant standardization →
  HTML-entity fix, single-string port of the website repo's
  `data_ingestor.py` logic; data vendored to
  `src/forensic_metascience_ai_toolkit/data/journal_name_mappings.json` with an
  attribution header; refresh verb `metascience refresh-journal-mappings`
  (**not implemented** at 1.77.0; `journal_names.normalize` exists).
  Unknown journal → passthrough (`journal_normalized == journal`, NEVER
  null when journal is known — "not in the mapping" must not read as "no
  journal").
- **`paper_metadata.py` → SCHEMA_VERSION "1.1"**: adds `journal_normalized`,
  `authors_list [{given, family, full}]` (Crossref structured authors
  preserved), `metadata_status ∈ ok|partial|failed|offline`,
  `needs_enrichment(meta) -> bool`, **and the abbreviated-name port from the
  website repo's `expand_author_names.py`**: detect initials-only given
  names, refetch by title, update ONLY when the name gets more complete
  ('J. Smith' rows fragment by-author stats). 1.0 files stay readable and
  upgrade in place on next fetch; offline discipline unchanged.
- **Backfill**: `metascience metadata-enrich <corpus-root> [--force]` —
  refetches only when `needs_enrichment` is true (small gaps are not a
  refetch). **Not implemented** at 1.77.0: `paper_metadata.needs_enrichment`
  exists, the verb does not.
- The findings document's `paper_metadata` block (§2) is a pipeline-written
  PROJECTION of `metadata.json`; producers emit no bibliographic fields.

## 12. Legacy converter details (A7 — beyond §1's field mapping; resolves critic open #5)

> The converter (`migrate_v2.py`, `metascience migrate-v2`) was deleted in
> 1.100.0, after converting the last archived serial-pipeline runs. This section
> records what the documents it wrote contain; nothing reads the v1 layout now.

- Orphan track outputs (`image_duplication_findings.json` — masliah holds
  544 — and standalone `text_forensics.json`) convert to **track-only v2
  docs** (`runs.kind = image_track|text_track`), with `channels` states
  derived by the SAME file-evidence rules `webapp_index.py` implements
  (tests/test_webapp_index.py is the contract — an ad-hoc derivation risks
  the ran-vs-did_not_run substitution).
- Unconvertible runs: write `findings.v2.skipped.json {reason, source_file,
  attempted_at}` beside the source — a named skip, never a silent one.
- Corpus roll-up: `migration_report.json {n_converted, n_skipped,
  n_review_orphans, by_reason}`; the review-orphan check verifies every
  review.json decision key joins to some converted row.
- Version rule (locked decision): `pipeline_version` from run_meta when
  present, else **`"0.0.1"`**; `analysed_at` from run_meta else file mtime
  WITH `analysed_at_source: "file_mtime"` (a file date presented as a run
  date is the substitution this toolkit exists to catch).
- Idempotent via `source_sha256`; `--dry-run` prints the report and writes
  nothing; v1 files and review.json are NEVER rewritten.

## 13. Eval changes (A8 — owned here; resolves critic open #6)

(Historical plan; implemented. Where it names a function that was built
differently, the code is described as it stands.)

- Fixture format: `severity_expected` becomes an INTEGER INTERVAL on the 1–9
  ladder (e.g. `[3, 5]`); optional `allow_undecided: true` (an
  `outcome: undecided` row also scores in-interval). `verdict_expected`
  unchanged.
- Gold papers relabeled with cited level slugs: apple_cider
  `baseline_uniformity` → `[3, 5]`; `data_availability` → `[3, 4]`;
  `effect_size_implausible` → `[2, 3]` + allow_undecided;
  `sprite_boundary_stacking` → `[2, 5]` + allow_undecided; airforce
  `grim_failures` → `[4, 6]` (the merged-pattern composition case).
- `judge.py`: interval logic becomes direct integer comparison via
  severity9; `severity_of` reads final `severity` (falls back to
  `provisional_severity` when `severity_is_provisional`); matching accepts
  `slug` OR `finding_id`; `severity_bias` is now linear.
- `evaluation/deterministic.py`: `check_findings_v2` validates v2 per §9's
  invariants, and the adjudication check is inline there rather than a
  separate `check_adjudication` (the `ran` flag must be recorded; an
  adjudicated problem row with no severity fails); a paper with findings whose
  adjudicator silently didn't run FAILS the deterministic block.
- A NEW CONSORT-rich fixture exercises the science agent (none exists —
  built from the Phase-4 live run per pipeline.md).
