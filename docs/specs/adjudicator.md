# Adjudicator stage — contract

| | |
|---|---|
| **Status** | Approved 2026-08-21 |
| **Source of truth** | THIS DOCUMENT. Derived from the approved 2026-08 overhaul plan (sections A3, A4, B1, B2, B4, R2, R4 of a working file at `~/.claude/plans/`, since retired and reused for later planning — do not consult it); this spec states the corrected rules as normative. |
| **Implemented by** | Master Phase 4 (`adjudicate.py`, `modules/adjudicator/prompt.md`, `adjudication.schema.json`, `apply()`, parallel-mode wiring). Depends on Phase 1 (`severity9.py`, findings-v2 schema, finding_id hasher) and Phase 3 (registry `ADJUDICATOR` role, prompt assemblers, backend seams). Phase 7 relabels eval fixtures and performs cutover. |
| **New files** | `src/forensic_metascience_ai_toolkit/adjudicate.py`, `modules/adjudicator/prompt.md`, `src/forensic_metascience_ai_toolkit/schema/adjudication.schema.json`, `tests/test_adjudicate.py` |

## 1. Role

One LLM pass, after the merge of all five producer streams (tool-expert agent,
science-error agent, image track, text track, and the opt-in raw-data track
`raw_data_track`, quarantined and never headline -- `adjudicate._unscreened`)
and after the pre-adjudication
annotators, that: dedupes/merges findings across producers, triages
misapplications and innocent explanations, assigns the FINAL 1–9 severity per
finding, and emits the paper-level block (verdict, `paper_severity`, headline,
confidence, bounded `summary`). It **absorbs today's stage-2 editorial role**;
`report_markdown` dies — the adjudicator's `summary` is the report's narrative
slot, and `render_report` stays structural (B5).

The adjudicator is a referee, not a re-analyzer: it may spot-check with tools
(§3) but produces no new findings. Suspicion it cannot attach to an existing
finding goes into its rationale text, never into a minted row.

**Relation to the image prototypes.** Image-finding adjudication lives in the
separately distributed image package (`legacy_adjudication`), re-exported
lazily through `agent._IMAGE_REEXPORTS`. The adjudicator extends the contract
those prototypes share: verdicts joined
by explicit id, never by list position (the position-zip defense); a clear
requires a named benign category; parse failure / unknown verdict leaves the
finding standing; fail-open. What is NEW is a bounded ranking power — the
prototypes are downgrade-only (`_CLEARS={"explained"}`); the adjudicator may
also upgrade, with every bound enforced in `apply()` code (§5), which is what
makes the tool surface escalation-safe (R2).

The image innocuous-explanation pass **stays upstream** as a producer-side
filter; its verdict rides into the docket as `inputs.image_adjudication`. The
adjudicator does not re-litigate pixels.

## 2. Input: the docket

Built by `adjudicate.build_docket(merged_findings, paper_text="", tally="",
second_look=None, sources=None)` in `adjudicate.py`. Components, all mandatory (absent components
are named as absent in the docket text, never silently omitted):

1. **Per-finding compact rows** for every `problem` and `undecided` finding.
   Row fields: `finding_id` (the join key), `slug`, `producer`, `technique`,
   `computed_by`, `outcome`, `provisional_severity`, `impossible`,
   `tool_verdict.severity`, `quarantined` + `quarantine_reason`, `title`,
   `description`, `location`, load-bearing `reported`/`computed` scalars,
   truncated `quote`, `reproduction`, and (where present)
   `inputs.image_adjudication` verdict, `basis`, `n_web_sources`.
2. **Pass-row summarization**: `pass` findings are NEVER itemized — they enter
   as per-technique counts (`grim: 41 pass`), so a clean check is visible
   without spending docket rows on it.
3. **Row cap = 120** (`DOCKET_ROW_CAP = 120`), with a **named remainder**: the
   docket states how many rows were withheld, broken down by producer and
   technique. Rows are ranked into the cap by `provisional_severity` desc,
   then `impossible`, then producer interleave (so one noisy producer cannot
   evict another's rows entirely). Over-cap rows resolve by the silence rule
   (§5.7) and are counted in the doc-level `adjudication` summary as
   `n_not_adjudicated` — a capped docket must announce itself (the
   budget-truncation invariant, applied to rows).
4. **Paper text budget**: the first `PAPER_TEXT_BUDGET_CHARS = 40_000`
   characters of `paper_text(paper_dir)` (the `extraction/jats.py` loader —
   XML-primary invariant respected). Truncation is announced in the docket
   ("text truncated at 40,000 of N chars").
5. **`Read` access** to the paper directory (read-only), including image
   exhibits under `panels/` and supplements — for verifying `evidence_quote`s,
   opening a disputed table, or eyeballing an exhibit beyond the text budget.
6. **`second_look` worklist**: the pre-adjudication annotators' list of items
   flagged for re-examination, passed verbatim.
7. **`checks_tally`**: the merged tally block (`agent.py:checks_tally`) so
   "what was checked" is data handed in, not inference from the rows.

## 3. Tool access

Registry role **`ADJUDICATOR`** (replaces `STAGE2`; deprecated alias kept
through migration):

- **The former stage-2 set, plus `check_flow_arithmetic`** (R2; the current
  list is `registry.stage_tools(ADJUDICATOR)`, 42 tools at 1.77.0). The
  formerly stage2-only tools (`check_proportion_from_normal`,
  `r_grim_ground_truth`) become adjudicator-only — the rulebook's
  cross-check-before-`impossible` duty is now this stage's job by name.
- **Plus `Read`. No web, no code** (no WebSearch/WebFetch/Bash/Write, and
  `run_python_script` is not in the ADJUDICATOR role — pipeline.md §6/§10).
- Rationale (R2, corrected over Part A's Read-only draft): `apply()`'s clamps
  make tools **escalation-safe** — nothing a tool returns can raise a severity
  past the caps in §4 — while the R ground-truth cross-check has to live
  somewhere with tools.
- Enforcement (pipeline.md §9): the adjudicator is a no-web, no-code stage
  and keeps **today's byte-pinned no-web argv shape** — `--tools Read`,
  `--allowedTools` = the `ADJUDICATOR` role's `mcp__forensic_metascience__*`
  names, `--disallowedTools` as today, under `--permission-mode
  bypassPermissions` (where `allowedTools` auto-approves). The B4
  MCP-names-in-`--tools` correction applies to the SCIENCE agent's newly
  built argv, not here: the plan pins today's no-web argv byte-identical.
  Argv is byte-pinned by fixture. Grok backend: deny-complement from
  `registry.SPECS` as today; `search_tool`/`use_tool` never land in a deny
  list.
- A web or code call by the adjudicator is a **named surface breach** in
  `sandbox_audit.json` (`_sandbox_audit` parameterized by the stage's actual
  denied list, per B4). Stage meta records `internet: false`, `n_web_calls`.

## 4. Severity constants consumed (owned by `severity9.py`, R1)

The adjudicator imports, never redeclares: `FIVE_TO_NINE`
({suspicious: 3, highly_suspicious: 4, impossible: 5}), `QUARANTINE_CAP = 3`,
`ACCUSATORY_MIN = 3`, and `rubric_markdown()` (embedded into
`modules/adjudicator/prompt.md` at assembly time — no separate ladder file to drift).

**There is no ceiling (v1.14.0).** `PIPELINE_MAX`, `ADJUDICATOR_MAX_*`, the
manipulation 8-gate and the analysts' evidence-class `PROVISIONAL_CAP` were
removed; the adjudicator may write any rung 1–9, and the prompt carries no
composition rules. What still binds is movement (the +2 rule below) and the
producer-side evidence-CHANNEL caps in `findings_v2.md` §7.

## 5. `apply()` — every bound in code

`adjudicate.apply(merged_findings, adjudicator_output) -> (findings, summary)`.
Deterministic, pure, no LLM. Joined on **`finding_id`**, never position. Rules,
each with the exact numbers, each individually tested (§9):

1. **Unknown-id drop.** A verdict whose `finding_id` matches no merged finding
   is dropped and counted (`n_unknown_ids` in the doc-level summary). It never
   attaches to a neighbor.
2. **Discard retains.** `action: "discarded"` sets
   `adjudication.action = "discarded"` and `severity = null`; the finding row
   is **RETAINED in findings.json, never deleted** — "ran and discarded" must
   stay distinguishable from "did not run" (LESSONS #1; tri-state doctrine).
   Discarding never alters any channel state; for fire-rate stats the row
   splits out of `fires` into `n_discarded_by_adjudicator`, while its
   channel still counts in denominators — **"ran" for denominator purposes is
   state ∈ {`ran`, `ran_result_discarded`}** (corrected rule; a channel that
   demonstrably ran and retained nothing STILL RAN).
3. **Merge validation.** `action: "merged"` requires a `merged_into` pointing
   at a finding that exists in the output and is itself
   kept/downgraded/upgraded (never discarded, never merged — no chains, no
   cycles, no dangling targets). Invalid merges degrade both rows to `kept`
   (provisional) and are counted. `apply()` writes the inverse `merged_from`
   list on the target; a merged row keeps its own record with
   `adjudication.action = "merged"`.
4. **Clamps**, applied in order after the action:
   - `severity` must be an integer 1–9 from the model; anything else → the
     silence rule for that row.
   - Quarantined rows clamp to `QUARANTINE_CAP = 3`.
   - **Upgrade limit: `severity ≤ provisional_severity + 2`**, and upgrades
     are legal only with category `merged_pattern`, `consequence_reassessed`
     or `manipulation`; an upgrade with any other category reverts to the
     provisional. **Merged pattern findings are EXEMPT from the +2 limit**
     (a pervasiveness merge may express a level no single row could).
   - No ceiling: 8 and 9 are ordinary rungs, reached by the same +2 rule
     (9 from a provisional ≥ 7, or from anywhere via `merged_pattern`).
     The final `min(sev, 9)` only guards a malformed number.
   - Every clamp records `severity_from` (the model's number) in the
     finding's `adjudication` object — a clamp is visible, never silent.
5. **Evidence-quote verification.** A clear (`discarded`, or a downgrade with
   category `innocent_explanation`) must carry an `evidence_quote`; `apply()`
   verifies it appears in the paper text (typography-folded match via
   `quotes.py`, same fold as the locator path). A quote that cannot be located
   **demotes the action to `kept`** (provisional severity stands) with a named
   demotion reason — a fabricated supporting sentence must not clear a
   finding. This guard ships with a known-positive test (§9).
6. **Read-only fields.** `impossible` and `tool_verdict` are pipeline-derived
   and untouchable: any adjudicator output for them is ignored (and counted).
   `impossible` is true iff a validated call of an `evidence: absolute` tool
   returned `impossible` and survived reconciliation — neither model nor
   adjudicator can set OR clear it (A1). Likewise the adjudicator cannot
   change `outcome`, `producer`, `technique`, `computed_by`, or `quarantined`.
7. **Silence = kept-provisional.** A merged finding with no verdict row
   (including all over-cap rows) ships `adjudication.action = "kept"`,
   `severity = provisional_severity`, `severity_is_provisional = true`.
8. **Fail-open.** Total adjudicator failure (transport, parse after the
   3-tier fallback, schema rejection) applies rule 7 to every finding and
   writes a doc-level `adjudication.failure` record. Findings are never lost;
   the run is PARTIAL, not FAILED (the errored-but-produced invariant).
9. **Rewrites preserve originals.** Optional `title`/`description` rewrites
   are accepted only within the schema caps (title 8–90 chars, description
   20–700); `apply()` stores the originals as
   `adjudication.title_was`/`description_was`.

## 6. Output schema (`adjudication.schema.json`, enforced via `--json-schema`)

Raw output is written verbatim to `<review_dir>/adjudication.json` (R6);
`findings.json` is the *applied* v2 document.

```jsonc
{
  "verdicts": [                       // one per adjudicated finding
    {
      "finding_id": "f_9c1e22ab34cd56ef",   // required; the join key
      "action": "kept|merged|downgraded|upgraded|discarded",  // required
      "severity": 4,                  // required unless discarded (then null)
      "category":                     // required; the normative starting enum:
        "duplicate|misapplication|innocent_explanation|chance_expected|
         merged_pattern|consequence_reassessed|manipulation|
         insufficient_evidence|none",
      "rationale": "…",               // required, 1–2 sentences
      "evidence_quote": "…",          // required for innocent_explanation
                                      // clears/discards; verified per §5.5
      "merged_into": "f_…",           // required iff action == merged
      "title": "…", "description": "…"   // optional rewrites, schema-capped
    }
  ],
  "paper": {                          // required
    "verdict": "reconciles|unresolved|does_not_reconcile",  // existing enum
    "paper_severity": 5,              // 1–9 (no ceiling since v1.14.0); clamped in apply()
    "headline_finding_id": "f_…",     // must be a kept/upgraded/downgraded
                                      // problem row, never discarded/merged;
                                      // else apply() falls back to
                                      // issue_sort_key order and counts it
    "confidence": "low|medium|high",  // existing enum
    "summary": "…"                    // bounded narrative, 200–2000 chars;
                                      // replaces report_markdown
  }
}
```

Applied per-finding object (findings-v2 `adjudication`): `{action, rationale,
category, merged_into, merged_from[], severity_from, title_was,
description_was}`. Doc-level `adjudication` summary: `{ran, verdict,
paper_severity, headline_finding_id, confidence, summary, n_kept, n_merged,
n_discarded, n_downgraded, n_upgraded, n_not_adjudicated, n_unknown_ids,
failure}`.

Category and action vocabularies live in the schema; extending either is a
schema change (MINOR bump — interpretation changes across it).

## 7. Prompt: `modules/adjudicator/prompt.md` (assembled by `adjudication_system_prompt()`)

Eight sections, in this order (Part A contract; the embedded example JSON is
validated against the live schema by a test so it cannot rot):

1. **Mission** — single referee over the five producer streams of §1 (the
   prompt's own wording still says four; `raw_data_track` arrived in 1.76);
   absorbs the editorial role; produces no new findings.
2. **Inputs** — docket format, pass-count semantics, the named remainder,
   paper-text budget, `Read` discipline, `second_look`, `checks_tally`.
3. **Severity rubric** — `rubric_markdown()` embedded at assembly time; the
   two axes (evidence verdict vs 1–9 consequence); the governing question:
   *"If this one finding were confirmed, and it were the only problem in the
   paper, what would the journal have to do about it?"*
4. **Actions and categories** — the five actions, category meanings, the
   `evidence_quote` requirement for clears (with the warning that an
   unlocatable quote demotes the clear).
5. **Dedup and merge discipline** — cross-producer duplicates (the same
   defect found by both agents is ONE finding), no merge chains, merged
   pattern findings carry the pervasiveness severity.
6. **Tool spot-checks** — when to re-run a tool; `r_grim_ground_truth` before
   any GRIM `impossible` headlines; a cross-check that cannot run must say so
   (the `_r_unavailable` invariant); a tool result never raises a
   severity by itself.
7. **Paper-level block** — verdict rubric (arithmetic claim, not honesty),
   `paper_severity`, headline choice, confidence, the bounded `summary`.
8. **Output discipline** — JSON only, join on `finding_id`, embedded example
   validated by test, silence semantics stated (unaddressed = kept
   provisional).

Rulebook stays the one shared file with the "who each rule binds" preamble
(B3); severity intro rewritten for the two axes.

## 8. Cost, budget, and the `cross_check: "not_run"` stamp

- Budget split (Claude backend only; the other backends have no spend cap): tool agent
  0.40·B, science agent 0.25·B, **adjudicator gets the remainder**, with
  `MIN_ADJUDICATOR_BUDGET_USD = 0.20` as a floor. Below the floor:
  **skip adjudication** and ship a findings-only result (merged, all
  provisional, `severity_is_provisional: true` throughout) with the doc-level
  `adjudication.ran = false` and a named reason.
- **On ANY adjudicator-skip or adjudicator-fail path, every finding carrying
  `impossible: true` is stamped `cross_check: "not_run"`**, rendered as a
  report limitation and **barred from headline use** — the R ground-truth
  surface is adjudicator-only under the new roles, and an unrun cross-check
  must never read as a passed one (the `_r_unavailable` invariant, inverted).
- The stage runs through `_run_stage` machinery: preflight (fails closed) then
  usage guard (fails open) at the top, both outside the wall clock; run_meta
  stage `adjudicator` records cost/tokens/parse path, `internet: false`,
  `n_web_calls`. A budget-truncated adjudicator call records `error_subtype` +
  `truncated_by_budget` and the report carries the PARTIAL COVERAGE
  limitation.

## 9. Failure modes (exhaustive; every path leaves findings shipped)

| Failure | Behavior |
|---|---|
| Budget below floor | Skip; provisional findings; `adjudication.ran=false`; `cross_check:"not_run"` stamp on impossible rows |
| Transport/parse/schema total failure | Fail-open (§5.8); PARTIAL not FAILED; failure record; stamp applies |
| Partial verdict coverage | Silence rule per missing row; counts in summary |
| Unknown `finding_id`s | Dropped + counted; never positional |
| Invalid merge target | Both rows degrade to kept; counted |
| Unlocatable `evidence_quote` on a clear | Demoted to kept; named reason |
| Severity over +2 / ineligible upgrade / quarantined | Clamped; `severity_from` recorded |
| Web/code call attempted | Named surface breach in sandbox_audit; run continues |
| Headline id invalid | Fallback to `issue_sort_key`; counted |
| Docket over cap | Named remainder; over-cap rows kept-provisional |

## 10. Required tests (`tests/test_adjudicate.py`; known-positives per LESSONS #4 — a guard that never fires is indistinguishable from a broken one)

Each of these must FIRE on a fixture built to trip it, not merely pass on
clean input:

1. Fabricated `evidence_quote` (absent from paper text) → clear demoted to
   `kept`; the same quote present → clear accepted (both directions).
2. Unknown-id verdict → dropped, `n_unknown_ids` incremented, neighbor rows
   unaffected under shuffled verdict order (position-zip defense).
3. Discarded finding retained in findings.json with `severity: null`; absent
   from `fires`, present in `n_discarded_by_adjudicator`; channel states
   untouched.
4. Upgrade clamps: 3→6 non-exempt clamped to 5; merged-pattern 4→7 and
   3→9 accepted; manipulation 5→8 clamped to 7; consequence_reassessed 7→9
   accepted; ineligible-category 4→9 reverts to 4; quarantined row >3
   clamped to 3; `severity_from` recorded on every clamp.
5. Merge chain / dangling / into-discarded target → both rows kept, counted;
   valid merge writes `merged_from` inverse.
6. Silence and over-cap rows → kept-provisional with
   `severity_is_provisional: true`.
7. Fail-open: crashed transport ships all findings provisional + failure
   record; result is PARTIAL, not FAILED.
8. `impossible`/`tool_verdict`/`outcome` flip attempts ignored and counted.
9. Skip/fail paths stamp `cross_check: "not_run"` on `impossible` rows;
   `adjudicate.apply()` never picks such a row as headline, and
   `evaluation/deterministic.py` (`check_findings_v2`) rejects it on a
   non-provisional row.
10. Docket builder: 121 problem rows → 120 itemized + named remainder by
    producer/technique; pass rows never itemized; text truncation announced.
11. Prompt-contract: embedded example JSON validates against the live schema;
    `test_tool_exposure` three-way agreement includes the `ADJUDICATOR` role;
    pinned argv fixture carries the `ADJUDICATOR` role's MCP tool names in
    `--allowedTools` (today's no-web argv shape, byte-pinned — §3).

## Addendum — skip-vs-silence pin (resolves critic open #8)

Per-row `adjudication` present ⟺ `apply()` executed. The silence rule
(§5.7, `action: "kept"`) applies ONLY to rows apply() ran over but the model
did not mention. On the skip-entirely paths (budget floor, zero-findings
skip, crash before apply) the PIPELINE annotator — not apply() — copies
provisional→severity, sets `severity_is_provisional: true`, writes NO
per-row adjudication object, records doc-level `adjudication.ran: false`
(+ skipped_reason/failure), and stamps `cross_check: "not_run"` on
`impossible` rows. See findings_v2.md §10 for the three-case table.
