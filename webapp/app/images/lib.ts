/** Shared types and helpers for the image review system. */
// The record types live in lib/types/images.ts and the pane-document
// rules in lib/paneDocument.ts (lib/ must not import app/); both are
// re-exported here so existing importers keep working.
export type { Subfigure, Placement, Rendition, FigureSources, IdentitySidecar, Panel, PaneTarget, PaneLocator, PaneDocument, PaperHead, Decision, ContentSupportData, Item, SpotCheck, Feed, FigureSpan, Filter, QueueSort } from "@/lib/types/images";
export { isPdfReference, nativePaneSentence, paneDocument } from "@/lib/paneDocument";
import type { FigureSources, PaneTarget, PaneLocator, Decision, Item, FigureSpan, Filter, QueueSort } from "@/lib/types/images";


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

export function buildPaneLocator(targets: PaneTarget[]): PaneLocator | null {
  if (!targets.length) return null;
  const first = targets[0];
  const method = first.method
    || (first.kind === "pdf_bbox" ? (first.boxes?.length ? "placement_bbox" : "placement_page") : undefined);
  return { page: first.page, confidence: first.confidence, method, targets };
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

/** Values and dropdown wording, in the order the control lists them. */
export const FIGURE_SPANS: [FigureSpan, string][] = [["different_figures", "different figures"],
  ["same_figure", "same figure"], ["different_papers", "different papers"], ["unknown", "figure unknown"]];

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
