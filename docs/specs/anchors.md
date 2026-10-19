# Persisted anchors — the location contract for every finding

**Status:** approved 2026-08-21.
**Source of truth:** THIS DOCUMENT. It was derived from the approved 2026-08 overhaul plan (a working file at `~/.claude/plans/`, since retired and reused for later planning — do not consult it)
(Part C §C1/§C7/§C8, reconciliation R4/R5). Where that plan's earlier sections
disagree with its reconciliation or verification passes, the corrected rule is
stated here and is normative.
**History:** built in overhaul phases 1–5 (2026-08); those phases are done.
The §6 backfill verb and the §8 `anchor_health` rollups were planned and are
not implemented.

An anchor is a CLAIM ABOUT A PLACE. A box drawn on the wrong number is a visual
accusation against an innocent cell. Everything below descends from that
sentence and from the existing `locators.py` doctrine: `none` is a successful
answer; never page 1.

---

## 1. The anchor record

Anchors live in each finding's `anchors[]` (findings-v2). Producers emit
minimal records (§5); the annotator (§6) enriches them **in place** into this
persisted shape:

```jsonc
{
  "anchor_id": "f_9c1e22ab34cd56ef:a:pdf",   // §2 id scheme
  "passage_id": "a",
  "passage_key": "f_9c1e22ab34cd56ef:a",     // EXPLICIT field — consumers never parse ids (§2)
  "surface": "pdf",                          // "pdf" | "xml" | "html" | "sheet"
  "kind": "pdf_text",                        // pdf_text | pdf_bbox | xml_text | html_text | sheet_cell
  "role": "said",                            // "said" | "against" | "source" | null
  "label": "Table 2",                        // human hint; may be ""
  "quote": "mean 3.53 (SD 1.20), n = 30",   // verbatim from the producer passage; null for pdf_bbox/sheet_cell
  "quote_folded_sha1": "…",                  // sha1 of fold(quote); idempotence + drift key (§6)

  // surface = "pdf" (kinds pdf_text, pdf_bbox):
  "file": "10.1000--j.pdf",                  // PAPER-RELATIVE path; SI PDFs supported, never assumed main
  "page": 4,                                 // 1-based
  "media_box": {"w": 595.3, "h": 841.9},     // page size in PDF points — viewers normalize with it
  "boxes": [{"x0":…, "y0":…, "x1":…, "y1":…, "page": 4}],  // PDF points, y-DOWN (PyMuPDF native)
  "region": {"x0":…, "y0":…, "x1":…, "y1":…, "page": 4},   // union bbox — the future tooltip/annotation rect

  // surface = "xml" or "html" (kinds xml_text, html_text):
  "section_index": 7,
  "section": "Results",
  "char_range": [1042, 1131],                // [start, end) into the section's PRE-FOLD extraction text (§4)

  // surface = "sheet" (kind sheet_cell):
  "sheet": "Table S3",
  "cells": [{"sheet": "Table S3", "row": 12, "col": 4}],

  "confidence": "exact",                     // §3 vocabulary — ladder unchanged from locators.py
  "method": "quote_verbatim",                // §3
  "status": "anchored",                      // §3 — pure function of confidence, persisted anyway
  "anchor_provenance": {                     // NORMATIVE NAME. Not `computed_by`: that key is the
    "pymupdf": "1.24.9",                     // finding-level evidence enum (plan R4); reusing it nested
    "pipeline": "0.10.0+abc1234",            // here breaks validation/codegen. Any draft using
    "at": "2026-08-21T14:02:11Z"             // computed_by inside an anchor is superseded.
  }
}
```

Field rules:

- Surface-specific keys appear only on their surface; absent keys mean
  "not this surface", never "unknown".
- `quote` is the producer's verbatim passage, byte-preserved. The annotator
  never edits it; it folds a COPY for matching (§4).
- `boxes[]` may be empty on a written record (that is `page_only` or
  `unanchored` — §3). `region` is present iff `boxes` is non-empty.
- `file` is present on every pdf-surface record, even unanchored ones, when
  the paper has a PDF; it names the document that was searched.
- The `html` surface exists for fetchpdf `_from_html` papers (an HTML article
  is the primary readable document). It uses the xml-style
  `section_index`/`section`/`char_range` fields, kind `html_text`, and the
  xml column of every table in §3. It is a first-class surface, not a
  degraded pdf.
- `anchor_provenance.error` (string) is added when annotation for this record
  crashed or its engine was unavailable (§6, §10) — the failure is named on
  the record, never a silent absence.

## 2. Id scheme (hash ids, never slugs; the collision fix)

- `anchor_id = "{finding_id}:{passage_id}:{surface}"`. `finding_id` is the v2
  **content-hash id** (`f_` + 16 hex). The human `slug` is display-only and
  NEVER appears in any anchor id — slugs repeat across runs and papers.
- `passage_id` assignment:
  - quote passages: the producer's `passages[].id` when present, else `"a"`,
    `"b"`, … in emission order (matches `locators.candidates_for_issue`);
  - image placements: `"pg{page}"` — **one passage per distinct placement
    page** (see collision fix below);
  - sheet artefacts: `"sheet{i}"` (artefact index).
- `passage_key = "{finding_id}:{passage_id}"`, written as an **explicit
  field**. Consumers (notably `webapp/lib/targets.ts:passageKey()`) read the
  field and fall back to legacy prefix-slicing only for anchor-less archived
  runs. Nothing new parses ids.
- **The collision fix.** Today's image targets are ids `{iid}:page:{n}` and
  `passageKey()` slices at the first colon, so the two placements of one
  duplicated panel — the exact pair a reviewer must blink between — collapse
  into one comparison group and the second highlight is unreachable. Under
  this contract each placement page is its own passage (`pg4`, `pg7`), so the
  groups are distinct by construction. The inverse rule holds for quotes: a
  single passage split across a page boundary is ONE passage — two anchors
  **sharing** `passage_id` (one comparison group, two rectangles).
- Uniqueness: `(finding_id, passage_id, surface)` identifies an anchor. When a
  multi-page quote yields a second pdf anchor for the same passage, the first
  anchor keeps the bare `anchor_id` and each subsequent one appends
  `":p{page}"` — the common single-page id stays stable across re-runs.
  *(Resolution of a plan ambiguity: the plan's id formula plus its multi-page
  rule would otherwise mint duplicate anchor_ids.)*

## 3. Vocabularies and the degradation contract

**confidence** (ladder unchanged from `locators.py`): `bbox | exact | page |
section | none`. "Never page 1": a page is only ever claimed by a positive
match, never defaulted.

**method**: `quote_verbatim | quote_word_align | numeric_tokens |
placement_bbox | placement_page | tool_cells | unlocated`.

**status**: `anchored | page_only | section_only | unanchored` — a pure
function of confidence, persisted so the index/DB never re-derive it:

| confidence | status | pdf meaning | xml/html meaning |
|---|---|---|---|
| `bbox` | `anchored` | recorded placement rectangle(s) | — |
| `exact` | `anchored` | quote found; `boxes[]` non-empty | `char_range` found in a section |
| `page` | `page_only` | page known, no boxes | — (xml has no pages) |
| `section` | `section_only` | — | section by numeric tokens only |
| `none` | `unanchored` | not found | not found |

**Degradation contract — "we will not invent a location."** Every applicable
surface gets a record for every passage, ALWAYS:

- A quote not found in the PDF still writes a pdf-surface anchor with
  `status: "unanchored"`, `method: "unlocated"`. **Unanchored records are
  written, never omitted** — absence is a statement (LESSONS #1: a missing
  record is NO measurement; an unanchored record is a measurement of "not
  there").
- Degradation only ever moves DOWN the table. No tier may promote a weaker
  match to a stronger vocabulary value (a wrong box is a visual accusation).
- A surface the paper does not have gets no record (no PDF → no pdf anchors);
  "the paper has no PDF" and "the PDF was searched and the quote is absent"
  must stay distinguishable (the Elsevier-no-PDF lesson).

## 4. The four-tier XML→PDF bridge

The robustness requirement: findings computed from XML/HTML must still land on
the PDF page. Tiers are tried in order; each names its `method`:

1. **Folded probe** (`quote_verbatim`) — today's machinery: fold the quote
   (`quotes.normalise` + `fold_rendering`), probe the first 8 folded words
   against per-page folded text, then `page.search_for` for boxes
   (`locators.quote_boxes`). Hit with boxes → `exact`/`anchored`.
2. **Word alignment** (`quote_word_align`, NEW) — when tier 1 finds no boxes
   (typography differs between the XML serialization and the PDF text layer):
   `page.get_text("words")`, fold each word, align the folded quote's token
   sequence against the page's folded word sequence, tolerating soft hyphens,
   ligatures, and line-break hyphenation (a token may match the concatenation
   of two adjacent page words). Union the matched word rects into `boxes[]`.
   **Thresholds, normative: ≥ 90% of the quote's tokens matched AND ≥ 8
   tokens matched; below either, degrade** — never emit tier-2 boxes from a
   partial alignment.
3. **Numeric tokens** (`numeric_tokens`) — the existing ≥2-token,
   ≥60%-majority page score (`locators.locate`). Page only, no boxes →
   `page`/`page_only`.
4. **Explicit unanchored** (`unlocated`) — the written statement of absence.

Bridge rules:

- **Multi-page quotes** (tier 1 or 2 matching across a page break) become two
  anchors sharing `passage_id` (§2), each with its own `page`/`boxes`.
- XML/HTML `char_range` is computed with an **offset-preserving fold** variant
  in `quotes.py` (§7): matching happens in folded space, offsets are mapped
  back so `char_range` indexes the section's **pre-fold** extraction text —
  the same string `extract_xml_text_with_tables` emits (table placeholders
  included, per the never-inline-tables invariant).
- Tier order is fixed. Tier 2 runs only on pages tier 1's probe or tier 3's
  scoring nominated (bounded work → the §6 time budget holds).

## 5. Producer input requirements (imposed on Parts A/B; plan R5)

Producers emit **minimal** anchor precursors; the annotator does the locating.
The producer-facing `--json-schema` subset enforces these by shape:

- **Text/numeric findings, BOTH agents** (tool_expert and science_error):
  mandatory verbatim `passages[]` — each one contiguous span, **≥ 8 words or
  ≥ 40 characters**, containing the load-bearing numbers, **no ellipses**.
  Optional `id`, `role` (`said|against|source`), `label` per passage.
- **Image findings**: `placements` carried **verbatim** from
  `panels/panel_index.json` — never re-typed by a model. The annotator also
  joins panel uids to `panel_index.json` itself; the historical
  dict-vs-list `placements` polymorphism is normalized ONCE here (v2 anchors
  are always derived through one code path), not defended in three viewers.
- **Tortured-phrase findings**: the matched phrase itself as the passage
  quote — this upgrades the text track from structurally unlocatable to
  anchorable.
- **Sheet findings**: cell refs (`artefacts[]` with sheet kind + `cells[]`),
  as `locators._sheet_targets` reads today.
- Minimal producer record kinds: `quote | page_bbox | table_cell`. The
  annotator enriches in place; `anchor_problem` (string on the finding) is
  the named-absence escape hatch — a producer that cannot supply a passage
  says why, and the finding still flows (it will carry unanchored records).

## 6. When annotation runs

- `anchors.annotate_findings(paper_dir, findings)` runs **ONCE,
  post-adjudication**, in the pipeline finalizer (Part B's post-adjudication
  annotator chain) — final findings only; discarded findings are annotated
  too (they are retained, and a reviewer auditing a discard needs the place).
- **It never fails the run.** Every exception is caught; affected records are
  written unanchored with `anchor_provenance.error` naming the failure. A
  paid analysis is never lost to a highlighting step.
- **Budget: ~1–3 s per paper.** One `fitz.open` per PDF document, pages
  folded once, both shared across all findings (the `locators_for_paper`
  pattern); tier 2 bounded per §4.
- **Idempotent.** Re-running over an already-annotated document is a byte-level
  no-op: a record whose `quote_folded_sha1` and `anchor_provenance.pipeline`
  match the existing anchor is skipped (preserving `at`); `--force`
  recomputes. Re-annotation **replaces** a finding's `anchors[]` wholesale —
  never appends beside stale records.
- Backfill CLI verb **`metascience anchor-findings <paper_dir>`**
  (`--force`, `--dry-run`): **not implemented** (checked 1.77.0). The only
  caller of `annotate_findings` is the pipeline finalizer in `parallel.py`;
  migrated `findings.v2.json` documents keep their minimal anchors and are
  served by the legacy fallback (§9).

## 7. Module design

- **New `src/metascience_agent/anchors.py`.** NOT `anchoring.py` — that name
  is taken by evidence-provenance; both modules' docstrings MUST
  cross-reference the other ("locations" vs "evidentiary basis").
- **`locators.py` stays the compute engine and the legacy view-time
  fallback.** Promote to public names: `_fold`→`fold`, `_locate`→`locate`,
  `_quote_boxes`→`quote_boxes` (underscore aliases retained — tests and
  `bundle.py` re-exports keep working). `anchors.py` calls these; it does not
  duplicate them.
- `quotes.py` gains the offset-preserving fold: fold plus a
  folded-offset→original-offset map (or equivalent span-mapping API), used
  for `char_range` (§4). `fold_rendering`/`normalise` semantics are
  unchanged — the variant adds offsets, it does not change folding.
- `anchors.py` public surface (minimum): `annotate_findings(paper_dir,
  findings)`, `anchor_passage(...)` (one passage → records across surfaces),
  `word_align_boxes(page, folded_tokens)` (tier 2), `status_for(confidence)`,
  and `summarize(finding)` → `anchor_summary`.

## 8. `anchor_summary` (finding level)

```jsonc
"anchor_summary": {"pdf": "anchored", "xml": "anchored",
                   "primary_anchor_id": "f_9c1e22ab34cd56ef:a:pdf", "page": 4}
```

- One key per surface the paper HAS (`pdf`, `xml`, `html`, `sheet`), value =
  the **best** status among that surface's records (order: `anchored` >
  `page_only` > `section_only` > `unanchored`). A surface key absent means
  the surface does not exist for this paper.
- `primary_anchor_id`: the first jumpable anchor (confidence `bbox`/`exact`)
  in document order, else the best non-`none` anchor, else `null`. `page` is
  the primary's page (`null` when non-pdf or unknown).
- Consumers: the DB mirrors `anchor_summary` as jsonb without unpacking
  `anchors[]`. (A webapp_index v2 `anchor_health {anchored, page_only,
  unanchored}` rollup was planned and is not implemented.)

## 9. The view-time path

- **Persisted-first**: `paper-view` (CLI → `/api/paper`) translates persisted
  anchors to workbench `Target` records **purely** — no PyMuPDF open, no PDF
  read. Translation: `id`←`anchor_id`, `passage_key` passed through verbatim,
  `kind`/`page`/`boxes`/`section_index`/`cells`/`confidence`/`method` copied.
  This is the WSL win: paper-open stops paying the 9P per-file penalty.
  The translation lives in `locators.locators_for_paper`, which marks each
  locator `located_by: "persisted_anchors"` or `"computed"`. The `paper-view`
  CLI verb still exists, but the workbench no longer spawns it: `/api/paper`
  and finding detail go through the workbench's persistent service
  (`workbench/service.py`, see `docs/workbench_storage.md`), whose
  `issue_detail` hands the finding's persisted `anchors` to the same
  `locators_for_paper`.
- **Legacy fallback**: runs whose findings carry no enriched anchors fall
  through to today's `locators.locators_for_paper` compute, unchanged. The
  fallback is reported (the view says which path served it), never silent.
- `webapp/lib/targets.ts`: `Target` gains `passage_key?: string`;
  `passageKey()` returns the field when present, legacy-slices otherwise.
  `comparisonGroups`/`pickTarget`/`coveringSurface` are unchanged — the fix
  is in the key, by design, not in the grouping logic.

## 10. HtmlArticlePane: the concatenated-haystack fix

`highlight()` today searches each text node independently, so a quote crossing
any element boundary (`<italic>`, `<sup>`, a `<sec>` seam) never matches — the
common case for scientific prose. Normative replacement:

- Walk text nodes once (TreeWalker), build ONE concatenated haystack plus a
  node/offset map; search the haystack (case-folded, and
  whitespace/typography-folded consistently with §4's fold so annotation-time
  hits reproduce at view time); split each match back into per-node DOM
  `Range`s and wrap each range in a `<mark>`.
- Both consumers — quote highlighting (`xml-hit`, with `data-target-id` from
  the anchor) and FindBar search (`html-hit`) — use the same machinery.
- The existing 8-word probe fallback and `clearMarks`/`normalize()` contract
  survive unchanged.

## 10a. Table cells (1.83.0)

A finding about specific table cells (the harness GRIM sweep's rows,
`grim_harness.finding_rows`) carries producer `table_cell` anchors:
`{table, table_key, table_num, source, row_label, row, col, raw, value, page}`.
`row`/`col` are the reader's own address: `data[row - 1][col] == raw`, and
`table_key` is the table's position (`T1`, `T2`, ...) in
`prepass.paper_tables(paper_dir, include_supplements=True)`.

`annotate_findings` turns each into (passage id `cell-<table_key>-r<row>c<col>`,
so a cell's PDF and XML records pair as one comparison group):

- **`xml_cell`** (surface `xml`) when the paper has XML and the table is the
  article's: `table_num`, `row`, `col`, `raw`, confidence `exact`. The XML pane
  (`xml_html._table_html`) prints the same address as
  `figure[data-table-num] td[data-row][data-col]`, so the cell is marked, not a
  passage around it.
- **`pdf_cell`** (surface `pdf`) against the main PDF: a box ONLY when the row
  label occurs exactly once on the page and the cell's printed text occurs in
  that label's line band exactly as often as the extracted row prints it (the
  k-th equal value gets the k-th box). Otherwise the page alone
  (`cell_page`), or `unlocated`. Never a guessed box: the k-th-match rule is
  what stops a value repeated across columns (Shaaban's "66.7 ... 66.7")
  boxing the wrong column.

Every enriched record keeps the producer's fields as `cell`, so a forced
re-annotation (anchors are replaced wholesale) rebuilds it. A failed pass
keeps the cell as an unanchored `xml_cell`. A supplement table gets no
`pdf_cell` (the main PDF is the wrong document). In the list, a finding with
more than `STEPPER_AT` (8) places shows one place at a time (‹ k of N ›)
instead of a button per place. A sealed run's locators are its persisted
anchors only (`locators.persisted_locators`); its files are never re-searched.

## 11. PyMuPDF version discipline

- `anchor_provenance.pymupdf` records the exact version that computed boxes.
- Tests assert **rectangle overlap** (IoU / containment with tolerance),
  **never byte-equal coordinates** — PyMuPDF text extraction drifts across
  releases and a coordinate-exact test would break on every upgrade while a
  genuinely wrong box could still pass it at the old pin.
- A viewer or re-verifier running under a different PyMuPDF treats a
  no-longer-matching quote as a **re-annotation trigger** (a re-run of the
  annotator; the planned `anchor-findings --force` verb does not exist), never an error and never a reason to move a box heuristically.
- PyMuPDF absent/blocked at annotation time: pdf-surface records are written
  unanchored with `anchor_provenance.error: "pymupdf_unavailable"`;
  xml/html/sheet surfaces still annotate. Engine-missing and quote-absent
  remain different facts (the four-refusal-states doctrine).

## 12. Required tests

`tests/test_anchors.py`, on synthetic fitz-built PDFs (no corpus dependency):

1. **Typography-mangled known-positive** (LESSONS #4): a quote whose PDF
   rendering differs by ligature (`efficacy` → `ef fi cacy`), soft hyphen, and
   line-break hyphenation MUST anchor via tier 2 with boxes — and the test
   MUST FAIL when the word-alignment fallback is removed (a guard that cannot
   fail reads as though it passed).
2. **Absent quote** → pdf record written with `status:"unanchored"`,
   `method:"unlocated"` — and **never page 1**.
3. **Threshold degradation**: an alignment at 89% tokens, or at 7 matched
   tokens, emits NO boxes (degrades to tier 3/4).
4. **Multi-page quote** → two anchors sharing `passage_id`, distinct pages,
   distinct `anchor_id`s per §2.
5. **Idempotence**: annotate twice, byte-compare the documents.
6. **PyMuPDF-blocked degradation**: with `fitz` import blocked, annotation
   completes, pdf records carry the named error, the call does not raise.
7. **Offset fold round-trip**: `char_range` sliced from the pre-fold section
   text re-folds to the matched quote.
8. **Never-fails-the-run**: an injected exception inside annotation yields a
   completed document with named errors, not a raised pipeline failure.
9. **Image passage split**: two placements on different pages → `pg{n}`
   passages, two distinct `passage_key`s.

`webapp/test/smoke.mjs` extensions: the passage_key collision regression (two
image placement pages form TWO comparison groups), anchor→target translation
shape (persisted-first path serves jumpable targets with no PDF open), and a
cross-element quote painting through the concatenated haystack.

Every rate or count these tests print obeys the standing rule: name the
denominator, and read the OUTPUT — open one annotated paper and check the
painted boxes against the page before calling the module done.
