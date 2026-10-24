/** Shared types and helpers for the image review system. */

export type Subfigure = { status: string; raw?: string | null; normalized?: string | null };
export type Placement = { page: number; bbox: number[] | null; figure_label?: string | null;
  document_path?: string; document_id?: string; bbox_kind?: string;
  transform?: number[]; parent_size?: number[]; page_size?: number[]; page_rotation?: number; subfigure?: Subfigure; geometry_gap?: string;
  /** Set when the geometry came from `panels/panel_identity.json` rather than the live PDF. */
  identity_source?: string; occurrence_id?: string | null };

export type Rendition = { rendition_id?: string | null; source?: string | null; file?: string | null;
  width?: number | null; height?: number | null; provenance?: string | null; passthrough?: boolean | null;
  link?: string | null; framing?: string | null; n_inliers?: number | null; detail?: string };

/** `state` is "current", "stale:<why>" or "absent" ("absent" means the ledger
 *  verb has not run, which is not "the PDF is the only copy"). */
export type FigureSources = { state: string;
  best_pixels?: { rendition_id?: string | null; source?: string | null; file?: string | null;
                  width?: number | null; height?: number | null } | string | null;
  best_pixels_reason?: string | null; links?: Record<string, number>; renditions?: Rendition[] };

/** One text line per rendition, best-pixels one marked; the state note when the
 *  ledger is not current. Pure, so the item page's rendering is testable. */
export function renditionLines(fs: FigureSources | undefined): { note: string | null; lines: string[] } {
  if (!fs) return { note: null, lines: [] };
  const state = fs.state || "absent";
  const note = state === "current" ? null
    : state.startsWith("absent") ? "Ledger absent: run metascience image-figure-sources"
    : state.startsWith("stale") ? `Ledger stale: ${state.replace(/^stale:?\s*/, "") || "inputs changed"}`
    : `Ledger ${state}`;
  const bestId = typeof fs.best_pixels === "string" ? fs.best_pixels : fs.best_pixels?.rendition_id ?? null;
  const lines = (fs.renditions || []).map((r) => {
    const size = r.width != null && r.height != null ? `${r.width}x${r.height}` : "size unknown";
    const best = bestId != null && r.rendition_id === bestId;
    return `${r.source || "unknown source"} ${size} · ${r.link || "link unmeasured"}`
      + (r.framing ? ` · ${r.framing}` : "") + (best ? " · best pixels" : "");
  });
  return { note, lines };
}

/** The identity sidecar's state for this panel's document: present only when
 *  a sidecar file exists (`usable` / `stale` / `no_record` / `unreadable`). */
export type IdentitySidecar = { status: string; reason?: string | null; path?: string };

export type Panel = {
  uid: string;
  crop_box?: number[] | null;
  paper_dir: string;
  paper_path?: string;
  image: string | null;
  placements: Placement[];
  figure_label: string | null;
  caption_key: string | null;
  caption: string | null;
  caption_source?: string | null;
  image_unavailable_reason?: string | null;
  image_recovery?: { method: string; run_id: string };
  document?: { id: string; path: string; role: string; status: string };
  subfigure?: Subfigure;
  caption_warnings?: string[];
  caption_locator?: { path?: string; page?: number };
  identity_gaps?: string[];
  identity_sidecar?: IdentitySidecar;
  /** The figure source ledger's view of this panel's figure (image_review `_figure_sources_for`). */
  figure_sources?: FigureSources;
  /** The parent figure's PNG (relative to the paper), for a crop or a native
   *  publisher/SI figure with no PDF placement. Set by `evidence.enrich_panel`. */
  parent_image?: string | null;
  panel_readings?: { page: number | null; subfigure_raw: string | null; status: string; context_text: string }[];
};

export type PaneTarget = { id: string; kind: string; label: string; page: number;
  boxes: { page: number; x0: number; y0: number; x1: number; y1: number; tid?: string }[];
  confidence: string; method?: string; paper_dir?: string; document_path?: string };

/** What `PdfPane` is told to open. `method` is what makes a page-only image
 *  placement read "Figure on p. N" rather than the numeric-token sentence:
 *  `_targets` emits it, and a feed cached before it did gets it inferred
 *  from the target kind. */
export type PaneLocator = { page: number; confidence: string; method?: string; targets: PaneTarget[] };

export function buildPaneLocator(targets: PaneTarget[]): PaneLocator | null {
  if (!targets.length) return null;
  const first = targets[0];
  const method = first.method
    || (first.kind === "pdf_bbox" ? (first.boxes?.length ? "placement_bbox" : "placement_page") : undefined);
  return { page: first.page, confidence: first.confidence, method, targets };
}

export type PaneDocument =
  | { kind: "pdf"; path: string; substituted: boolean }
  | { kind: "native"; path: string | null; reason: string }
  | { kind: "none"; reason: string };

/** Browser media references are archive identifiers or paper-relative paths,
 * never producer workspace paths. Keep the server containment checks as well. */
export function isPdfReference(path: string | null | undefined): path is string {
  if (!path) return false;
  const normalized = path.replaceAll("\\", "/");
  if (normalized.startsWith("/") || /^[a-z][a-z0-9+.-]*:/i.test(normalized)
      || normalized.split("/").some(part => part === ".." || part === ".")) return false;
  if (normalized.startsWith("__runs/")) return /^__runs\/[^/]+\/[^/]+$/.test(normalized);
  return normalized.toLowerCase().endsWith(".pdf");
}

/** Which document the right-hand pane shows for a panel.
 *
 *  The paper's main PDF is substituted ONLY when the panel's own document
 *  is the main article (or its role is unknown) and the recorded path is
 *  not itself a PDF. A publisher render, a DOCX supplement member or an
 *  SI image has no page in that PDF: substituting it painted the main
 *  article beside a panel that was never printed there, so those render
 *  on their native image instead. */
export function paneDocument(panel: Panel | undefined, paper: PaperHead | undefined): PaneDocument {
  const doc = panel?.document;
  const path = doc?.path ?? null;
  const role = doc?.role ?? "unknown";
  if (panel?.paper_dir && paper?.dir && panel.paper_dir !== paper.dir) {
    return { kind: "none", reason: "The selected source belongs to a different paper." };
  }
  // A sealed paper head is the canonical main document for this exact run.
  // Historical cross-panel metadata may still name an expired workspace PDF.
  if (role === "main" && isPdfReference(paper?.pdf) && paper.pdf.startsWith("__runs/")
      && !path?.startsWith("__runs/")) {
    return { kind: "pdf", path: paper.pdf, substituted: true };
  }
  if (isPdfReference(path)) return { kind: "pdf", path, substituted: false };
  if (role === "main" || role === "unknown") {
    if (isPdfReference(paper?.pdf)) return { kind: "pdf", path: paper!.pdf!, substituted: true };
    if (panel?.parent_image || panel?.image) {
      return { kind: "native", path, reason: `No PDF location: no PDF on disk for ${paper?.dir || "this paper"}` };
    }
    return { kind: "none", reason: `No PDF on disk for ${paper?.dir || "this paper"}.` };
  }
  return { kind: "native", path, reason: nativePaneSentence(path) };
}

export function nativePaneSentence(path: string | null): string {
  return `No PDF location: this panel comes from ${path || "an unresolved document"}; shown on its native image.`;
}

/** The crop's outline in the parent image's pixel frame: the client twin of
 *  `evidence._parent_locator`, i.e. `crop_polygon(crop_box, (w, h),
 *  [w, 0, 0, h, 0, 0])`. `crop_box` is r0, c0, r1, c1 (rows then columns);
 *  null when the box is absent or does not fit inside the parent. */
export function cropPolygonPixels(cropBox: number[] | null | undefined,
                                  size: [number, number] | null | undefined): [number, number][] | null {
  if (!cropBox || cropBox.length !== 4 || !size || size.length !== 2) return null;
  const [r0, c0, r1, c1] = cropBox;
  const [w, h] = size;
  if (![r0, c0, r1, c1, w, h].every((v) => typeof v === "number" && Number.isFinite(v))) return null;
  if (!(w > 0 && h > 0 && 0 <= c0 && c0 < c1 && c1 <= w && 0 <= r0 && r0 < r1 && r1 <= h)) return null;
  return [[c0, r0], [c1, r0], [c1, r1], [c0, r1]];
}

export type PaperHead = {
  pubpeer_url?: string | null;
  dir: string; path?: string; doi?: string | null; title?: string | null;
  journal?: string | null; year?: number | string | null; pdf?: string | null;
  authors?: string | null; volume?: string | null; issue?: string | null; pages?: string | null;
};

export type Decision = {
  decision: string; reviewer?: string; at?: string; note?: string; pending?: boolean;
};

export type ContentSupportData = {
  status: string; note?: string; reason?: string; limitations?: string[];
  saved_support?: {tentative_pairs:number; supporting_pairs:number; eligible_supporting_pairs:number};
  independent_masked_fit?: {status:string; inliers:number|null; tentative_pairs:number};
  agreement?: {original_agree_px:number; eligible_overlap_px:number; overlap_px:number; closing_added_px:number};
  panels?: {mask?: {eligible_px:number; total_px:number; excluded_px:number; note:string; text:{status:string; engine?:string; reason?:string}};
    segmentation?: {reason:string; cells:{row:number;column:number;box:number[]}[]}}[];
  cell_pairs?: {a:number;b:number;supporting_pairs:number;eligible_supporting_pairs:number}[];
  artifacts?: {role:string;side:string;sha256:string;ref:string;cell?:number}[];
};

export type Item = {
  requested_item_id?: string;
  /** Whether the archived panel pixels resolve on this computer (queue rows). */
  evidence?: "available" | "missing" | "unknown";
  /** Publication year from the queue's indexed column (null when unknown). */
  year?: number | null;
  text_label_context?: boolean;
  review_conflict?: boolean;
  record_revision?: string;
  content_support?: ContentSupportData;
  reviews?: {conflict?:boolean;reviewers?:any[];history?:any[]};
  screening_attempts?: unknown[];
  run_status?: string;
  coverage_status?: string;
  region_measurements?: Record<string, unknown>;
  legacy_decision_context?: unknown;
  prior_decisions?: unknown[];

  id: string;
  run_id: string; execution_id: string; provenance?: {version?:string}; publication_status?:string; evidence_source?:string;
  kind: "within" | "cross";
  source_id: string;
  paper: PaperHead;
  papers: PaperHead[];
  group_index: number | null;
  detector_kind: string;
  sentence: string;
  figure_labels: string[];
  spans_figures: boolean;
  /** `match_regions.figure_span`, computed by the service for every queue row. */
  figure_span?: FigureSpan;
  direction?: { later?: string; basis?: string } | null;
  captions: Record<string, { caption: string; source?: string; paper?: string }>;
  panels: Panel[];
  targets: PaneTarget[];
  /** Compact queue rows omit geometry; details load it for the selected run.
   * Missing measurements must never imply a measured empty region. */
  measurements?: Record<string, unknown> | null;
  /** Match-box area divided by each compared panel's area; absent is unmeasured. */
  region_coverage?: {a: number; b: number} | null;
  adjudication: { verdict?: string; category?: string; explanation?: string; confidence?: string } | null;
  screening_status?: string; scientific_disposition?: string | null; eligibility_detail?: string;
  screening?: { decision: string; confidence: string; validated: boolean; policy: string;
    explanation?: string; evidence_quote?: string; validation_errors?: string[];
    panel_readings?: {uid:string;page:number|null;subfigure_raw:string|null;status:string;context_text:string}[] };
  cleared: boolean;
  rank: { score: number; reasons: string[]; verdict?: string | null; category?: string | null;
          lookalike?: boolean };
  exhibit: string | null;
  video: string | null;
  video_revision?: string | null;
  video_generation?: import("@/app/project/[project]/images/[item]/VideoGeneration").VideoJob;
  exhibit_gate?: string | null;
  decision: Decision | null;
};

export type SpotCheck = { seed: string; per_kind: number;
  strata: Record<string, { population: number; sampled: number; right: number; wrong: number }> };

export type Feed = {
  revision?: string;
  spot_check?: SpotCheck;
  evidence_counts?: { value: string; count: number }[];
  pagination?: {offset:number;limit:number;total:number;next_offset:number|null};
  kinds?: { value: string; count: number }[];
  adjudicator_outputs?: { value: string; count: number }[];
  image_types?: { value: string; count: number }[];
  /** How many of the run's items the unaligned control demoted as lookalikes. */
  lookalike_counts?: { value: string; count: number }[];
  /** Items per figure span, GIVEN the other filters. */
  figure_span_counts?: { value: string; count: number }[];
  match_region_counts?: { value: string; count: number }[];
  /** Totals for the kind select's own "all" and "cross" options, on the same
   *  base as every other facet: the items passing all OTHER filters. `counts`
   *  stays whole-run, because it feeds the run summary line. */
  facet_totals?: { kind?: number; kind_cross?: number };
  empty_reason?: string | null;
  project: string; built_at: string; seconds: number;
  counts: Record<string, number>; items: Item[]; notes: string[];
  judgment_counts?: Record<string, number>;
  selection?: string; runs?: import("@/app/RunSelector").RunOption[]; coverage?: {runs:number;states:Record<string,number>};
  latest_info?: import("@/app/RunSelector").LatestInfo;
  refresh_needed?: boolean; refresh_error?: string;
  screening_progress?: { candidates: number; awaiting_review: number };
};

export const DECISIONS: [string, string, string][] = [
  ["false_positive", "5", "False positive"],
  ["true_issue", "1", "True issue"],
  ["unsure", "2", "Unsure"],
  ["false_positive_same_condition", "3", "FP — same condition"],
  ["false_positive_other", "4", "FP — other"],
  // Reason-specific false positives (2026-09-14): one click that names the
  // CLASS, so the negatives benchmark can count each detector rule's
  // remaining misses. All of them are rejections to every reader.
  ["false_positive_chart", "6", "FP — chart / label"],
  ["false_positive_overlay", "7", "FP — channel overlay"],
  ["false_positive_supplement", "8", "FP — own supplement"],
  ["false_positive_magnification", "9", "FP — magnification"],
  ["false_positive_scale_bar", "0", "False positive: scale bar"],
  // Digits are all taken; "c" for channels is free on the item page.
  ["false_positive_channels", "c", "False positive: different channels"],
  ["false_positive_logo", "l", "False positive: logo"],
];

export function mediaUrl(project: string, dir: string, rel: string, component = "image_forensics"): string {
  return `/api/media?component=${encodeURIComponent(component)}&project=${encodeURIComponent(project)}`
    + `&dir=${encodeURIComponent(dir)}&f=${encodeURIComponent(rel)}`;
}

export function itemHref(project: string, id: string, run = "latest"): string {
  return `/project/${encodeURIComponent(project)}/images/${encodeURIComponent(id)}?run=${encodeURIComponent(run)}`;
}

/** The next item in queue order with no decision, wrapping to the first.
 *  Used by `n` and by a successful feedback click. Absence of a decision is
 *  the only test: a pending local save still counts as decided. */
export function nextUndecidedIn<T extends { id: string; decision?: Decision | null }>(
  items: T[], currentId: string,
): T | null {
  const pos = items.findIndex((i) => i.id === currentId);
  const later = items.slice(Math.max(0, pos + 1)).find((i) => !i.decision);
  if (later) return later;
  return items.find((i) => !i.decision && i.id !== currentId) || null;
}

export function queueHref(project: string, run = "latest"): string {
  return `/project/${encodeURIComponent(project)}/images?run=${encodeURIComponent(run)}`;
}

export function paperHref(project: string, dir: string, run: string = "latest"): string {
  return `/project/${encodeURIComponent(project)}/review/${encodeURIComponent(dir.split("/").pop() || dir)}?dir=${encodeURIComponent(dir)}&run=${encodeURIComponent(run)}`;
}

export type FigureSpan = "different_figures" | "same_figure" | "different_papers" | "unknown";
/** Values and dropdown wording, in the order the control lists them. */
export const FIGURE_SPANS: [FigureSpan, string][] = [["different_figures", "different figures"],
  ["same_figure", "same figure"], ["different_papers", "different papers"], ["unknown", "figure unknown"]];

export type Filter = { text_context?: "exclude" | "include" | "only"; verdict: "unexplained" | "standing" | "all" | "unscreened" | "cleared"; kind: string;
                       /** The typer's class for the item: Blots, Graphs, Microscopy, Body Imaging,
                        *  Flow Cytometry, or `mixed` / `untyped`. "all" disables the filter. */
                       image_type?: string;
                       /** A LOOKALIKE is a group the unaligned control MEASURED and
                        *  failed: the two panels agree about as well unaligned as
                        *  aligned, so the agreement is not specific to the transform --
                        *  generic resemblance rather than shared pixels. Also set for a
                        *  single channel matched to a merge containing it across two
                        *  figures. It never changes the score, only the order, and a
                        *  group whose control was never measured is NOT one: absence of
                        *  a measurement is not a failed measurement. "all" disables. */
                       lookalike?: "all" | "yes" | "no";
                       match_region?: "all" | "partial_both" | "partial_one" | "large_both" | "unknown";
                       region_max_percent?: number;
                       transformation?: "all" | "any_suspicious" | "translation" | "rotation" | "resizing" | "reflection" | "combined" | "unknown";
                       coverage?: "all" | "incomplete" | "unknown";
                       /** Whether the item's placements name two different figures of one
                        *  paper (`different_figures`), one figure (`same_figure`), another
                        *  paper (`different_papers`), or cannot say because a label is
                        *  missing (`unknown`). "all" disables the filter. */
                       figure_span?: "all" | FigureSpan;
                       /** Case-insensitive substring of the paper folder shown in the Paper column. */
                       q?: string;
                       /** Queue order. Default is the triage rule (`triage_rank.sort_key`:
                        *  cleared and measured lookalikes last, then verdict tier, score,
                        *  inliers); `score` is the bare rank score. `paper` is the folder
                        *  column; `decision` groups by human decision, undecided last. */
                       sort?: QueueSort;
                       direction?: "asc" | "desc";
                       /** Spot-check mode: a seeded, stratified sample of the detector's own
                        *  context demotions (e.g. chart_furniture), per kind. Empty = off. */
                       spot_check?: string;
                       /** Whether the item's archived panel pixels resolve on this computer. */
                       evidence?: "all" | "available" | "missing" | "unknown";
                       undecided: boolean; adjudicator?: string; judgments?: string[] };

/** Show issue and unresolved judgments at every confidence level by default,
 * and candidates with no saved AI judgment. Complete-profile runs have AI
 * screening disabled, so every candidate is `missing`; leaving it out emptied
 * the queue and every facet, including the kind and image-type filters
 * (jasti_s_rao, 2026-09-25: 493,899 unscreened items, 0 shown). */
export const DEFAULT_FILTER: Filter = { text_context: "exclude", verdict: "all", kind: "all", image_type: "all",
  transformation: "all", coverage: "all", figure_span: "all", lookalike: "all", match_region: "all", region_max_percent: 80, q: "",
  sort: "triage", direction: "asc", undecided: false, judgments: ["issue", "unresolved", "missing"], spot_check: "", evidence: "all" };

export function paperColumn(it: Item): string {
  if (it.kind === "cross" && it.papers?.length) {
    const dirs = it.papers.map((p) => p.dir).filter(Boolean);
    if (dirs.length) return dirs.join(" ~ ");
  }
  return it.paper?.dir || "";
}

export type QueueSort = "triage" | "score" | "paper" | "decision" | "year";
export const QUEUE_SORTS: [QueueSort, string][] = [
  ["triage", "Triage (cleared and lookalikes last)"], ["score", "Rank score"],
  ["paper", "Paper"], ["year", "Year"], ["decision", "Decision"],
];

export function queueSortOf(f: Pick<Filter, "sort" | "direction">): QueueSort {
  return QUEUE_SORTS.some(([key]) => key === f.sort) ? f.sort as QueueSort : "triage";
}

export function queueDirectionOf(f: Pick<Filter, "sort" | "direction">): "asc" | "desc" {
  if (f.direction === "asc" || f.direction === "desc") return f.direction;
  return queueSortFirst(queueSortOf(f));
}

/** First click A→Z (paper), true issue first (decision) or high→low (score);
 *  second reverses; third restores the base order (triage, unless a queue
 *  without triage ranks passes its own).
 *  Score and year start high to low (newest paper first); triage starts at
 *  the most promising; paper and decision A to Z. */
export function queueSortFirst(key: QueueSort): "asc" | "desc" {
  return key === "score" || key === "year" ? "desc" : "asc";
}

export function cycleQueueSort(filter: Pick<Filter, "sort" | "direction">, key: QueueSort,
                               base: QueueSort = "triage"): Pick<Filter, "sort" | "direction"> {
  const first: "asc" | "desc" = queueSortFirst(key);
  if (queueSortOf(filter) !== key) return { sort: key, direction: first };
  if (queueDirectionOf(filter) === first) return { sort: key, direction: first === "asc" ? "desc" : "asc" };
  return { sort: base, direction: queueSortFirst(base) };
}

export function queueSortMark(filter: Pick<Filter, "sort" | "direction">, key: QueueSort): string {
  if (queueSortOf(filter) !== key) return "";
  return queueDirectionOf(filter) === "desc" ? " ▾" : " ▴";
}

export function queueAriaSort(filter: Pick<Filter, "sort" | "direction">, key: QueueSort): "ascending" | "descending" | "none" {
  if (queueSortOf(filter) !== key) return "none";
  return queueDirectionOf(filter) === "asc" ? "ascending" : "descending";
}

export function judgmentDecision(it: Item): string {
  return it.screening?.decision || (it.cleared ? "automatic_clearance" : it.adjudication?.verdict ? "legacy" : "missing");
}

export const MATCH_REGIONS = [
  ["partial_both", "Partial in both images"],
  ["partial_one", "Partial in one image"],
  ["large_both", "Large in both images"],
  ["unknown", "Not measured / unavailable"],
] as const;

export function maxRegionPercent(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) && n >= 1 && n <= 99 ? n : 80;
}

export function matchRegionKind(it: Item, maxPercent = 80): string {
  const c = it.region_coverage;
  if (!c || ![c.a, c.b].every(v => typeof v === "number" && Number.isFinite(v) && v > 0 && v <= 1)) return "unknown";
  const cutoff = maxRegionPercent(maxPercent) / 100;
  const count = Number(c.a <= cutoff) + Number(c.b <= cutoff);
  return ["large_both", "partial_one", "partial_both"][count];
}

export function matchRegionLabel(it: Item): string {
  if (matchRegionKind(it) === "unknown") return "Match boxes not measured";
  const c = it.region_coverage!;
  return `Match boxes: A ${(100 * c.a).toFixed(1)}% · B ${(100 * c.b).toFixed(1)}%`;
}

/** Restore only filters the queue can display and edit; retired controls must
 * never survive as invisible restrictions in saved browser preferences. */
export function restoreFilter(value: unknown): Filter {
  if (!value || typeof value !== "object" || Array.isArray(value)) return { ...DEFAULT_FILTER };
  const saved = value as Record<string, unknown>;
  const verdict = ["unexplained", "standing", "all", "unscreened", "cleared"].includes(String(saved.verdict))
    ? saved.verdict as Filter["verdict"] : DEFAULT_FILTER.verdict;
  const judgments = Array.isArray(saved.judgments)
    ? saved.judgments.filter((v): v is string => typeof v === "string" &&
        ["issue", "unresolved", "innocuous", "automatic_clearance", "missing", "legacy"].includes(v))
    : DEFAULT_FILTER.judgments;
  const sort = queueSortOf({ sort: saved.sort as QueueSort });
  const direction = saved.direction === "asc" || saved.direction === "desc"
    ? saved.direction : queueSortFirst(sort);
  return { verdict, kind: typeof saved.kind === "string" && saved.kind ? saved.kind : "all",
    image_type: typeof saved.image_type === "string" && saved.image_type ? saved.image_type : "all",
    // Restored explicitly. A filter absent from this function is dropped on
    // reload and the control springs back to "all" with the queue already
    // filtered -- measured on `image_type` when it was added (2026-09-14).
    lookalike: saved.lookalike === "yes" || saved.lookalike === "no" ? saved.lookalike : "all",
    match_region: MATCH_REGIONS.some(([value]) => value === saved.match_region)
      ? saved.match_region as Filter["match_region"] : "all",
    transformation: ["any_suspicious", "translation", "rotation", "resizing", "reflection", "combined", "unknown"].includes(String(saved.transformation))
      ? saved.transformation as Filter["transformation"] : "all",
    coverage: ["incomplete", "unknown"].includes(String(saved.coverage)) ? saved.coverage as Filter["coverage"] : "all",
    figure_span: FIGURE_SPANS.some(([value]) => value === saved.figure_span) ? saved.figure_span as FigureSpan : "all",
    text_context: saved.text_context === "include" || saved.text_context === "only" ? saved.text_context : "exclude",
    region_max_percent: maxRegionPercent(saved.region_max_percent),
    q: typeof saved.q === "string" ? saved.q : "",
    sort, direction,
    spot_check: typeof saved.spot_check === "string" ? saved.spot_check.slice(0, 40) : "",
    evidence: saved.evidence === "available" || saved.evidence === "missing" || saved.evidence === "unknown" ? saved.evidence : "all",
    undecided: saved.undecided === true, judgments };
}

/** Queue and item page share one restore path so a retired key cannot
 *  silently restrict j/k on the item while the queue ignores it. */
export function readFilter(key: string): Filter {
  if (typeof window === "undefined") return { ...DEFAULT_FILTER };
  try {
    const raw = window.localStorage.getItem(key);
    if (raw) return restoreFilter(JSON.parse(raw));
  } catch { /* a stale or blocked store is the default */ }
  return { ...DEFAULT_FILTER };
}

// The queue's filters run only in the service (SQL in `local_images.filters`,
// `match_regions` in Python) and are tested there. There is deliberately no
// client-side copy: a copy tested on its own can pass while production
// filters with something else.

export function verdictLabel(it: Item): string {
  if (judgmentDecision(it) === "automatic_clearance") return "Automatically cleared — AI not needed";
  if (judgmentDecision(it) === "missing") return "No saved AI judgment";
  if (it.screening?.decision) return `Saved AI judgment: ${it.screening.decision} · ${it.screening.confidence || "confidence unavailable"}`;
  if (it.cleared) return "cleared";
  const v = it.adjudication?.verdict;
  if (!v) return "not adjudicated";
  const c = it.adjudication?.category;
  return c && c !== "none" ? `${v} · ${c}` : v;
}

export function fmt(v: unknown, digits = 2): string {
  if (v == null) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(digits);
  if (typeof v === "boolean") return v ? "yes" : "no";
  return String(v);
}

export function evidenceLabel(source?: string): string {
  return source === "producer" ? "preserved by the producer"
    : source === "captured_at_import" ? "captured at import; original bytes unverified"
    : source === "partial_log" || source === "partial_report" ? "partial historical record; original media unavailable"
    : "historical provenance unknown";
}
