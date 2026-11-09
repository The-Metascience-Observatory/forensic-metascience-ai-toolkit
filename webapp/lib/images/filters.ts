/** The queue filter: its defaults, the figure-span and match-region vocabularies, and restoring a saved filter. Pure; split out of `app/images/lib.ts`, which re-exports it. */
import { queueSortFirst, queueSortOf } from "@/lib/images/sort";
import type { Item, FigureSpan, Filter, QueueSort } from "@/lib/types/images";

/** Values and dropdown wording, in the order the control lists them. */
export const FIGURE_SPANS: [FigureSpan, string][] = [
  ["different_figures", "different figures"],
  ["same_figure", "same figure"],
  ["different_papers", "different papers"],
  ["unknown", "figure unknown"],
];

/** Show issue and unresolved judgments at every confidence level by default,
 * and candidates with no saved AI judgment. Complete-profile runs have AI
 * screening disabled, so every candidate is `missing`; leaving it out emptied
 * the queue and every facet, including the kind and image-type filters
 * (jasti_s_rao, 2026-09-25: 493,899 unscreened items, 0 shown). */
export const DEFAULT_FILTER: Filter = {
  text_context: "exclude",
  verdict: "all",
  kind: "all",
  image_type: "all",
  transformation: "all",
  coverage: "all",
  figure_span: "all",
  lookalike: "all",
  match_region: "all",
  region_max_percent: 80,
  q: "",
  sort: "triage",
  direction: "asc",
  undecided: false,
  judgments: ["issue", "unresolved", "missing"],
  spot_check: "",
  evidence: "all",
};

/** Restore only filters the queue can display and edit; retired controls must
 * never survive as invisible restrictions in saved browser preferences. */
export function restoreFilter(value: unknown): Filter {
  if (!value || typeof value !== "object" || Array.isArray(value)) return { ...DEFAULT_FILTER };
  const saved = value as Record<string, unknown>;
  const verdict = ["unexplained", "standing", "all", "unscreened", "cleared"].includes(
    String(saved.verdict),
  )
    ? (saved.verdict as Filter["verdict"])
    : DEFAULT_FILTER.verdict;
  const judgments = Array.isArray(saved.judgments)
    ? saved.judgments.filter(
        (v): v is string =>
          typeof v === "string" &&
          ["issue", "unresolved", "innocuous", "automatic_clearance", "missing", "legacy"].includes(
            v,
          ),
      )
    : DEFAULT_FILTER.judgments;
  const sort = queueSortOf({ sort: saved.sort as QueueSort });
  const direction =
    saved.direction === "asc" || saved.direction === "desc"
      ? saved.direction
      : queueSortFirst(sort);
  return {
    verdict,
    kind: typeof saved.kind === "string" && saved.kind ? saved.kind : "all",
    image_type: typeof saved.image_type === "string" && saved.image_type ? saved.image_type : "all",
    // Restored explicitly. A filter absent from this function is dropped on
    // reload and the control springs back to "all" with the queue already
    // filtered -- measured on `image_type` when it was added (2026-09-14).
    lookalike: saved.lookalike === "yes" || saved.lookalike === "no" ? saved.lookalike : "all",
    match_region: MATCH_REGIONS.some(([value]) => value === saved.match_region)
      ? (saved.match_region as Filter["match_region"])
      : "all",
    transformation: [
      "any_suspicious",
      "translation",
      "rotation",
      "resizing",
      "reflection",
      "combined",
      "unknown",
    ].includes(String(saved.transformation))
      ? (saved.transformation as Filter["transformation"])
      : "all",
    coverage: ["incomplete", "unknown"].includes(String(saved.coverage))
      ? (saved.coverage as Filter["coverage"])
      : "all",
    figure_span: FIGURE_SPANS.some(([value]) => value === saved.figure_span)
      ? (saved.figure_span as FigureSpan)
      : "all",
    text_context:
      saved.text_context === "include" || saved.text_context === "only"
        ? saved.text_context
        : "exclude",
    region_max_percent: maxRegionPercent(saved.region_max_percent),
    q: typeof saved.q === "string" ? saved.q : "",
    sort,
    direction,
    spot_check: typeof saved.spot_check === "string" ? saved.spot_check.slice(0, 40) : "",
    evidence:
      saved.evidence === "available" || saved.evidence === "missing" || saved.evidence === "unknown"
        ? saved.evidence
        : "all",
    undecided: saved.undecided === true,
    judgments,
  };
}

/** Queue and item page share one restore path so a retired key cannot
 *  silently restrict j/k on the item while the queue ignores it. */
export function readFilter(key: string): Filter {
  if (typeof window === "undefined") return { ...DEFAULT_FILTER };
  try {
    const raw = window.localStorage.getItem(key);
    if (raw) return restoreFilter(JSON.parse(raw));
  } catch {
    /* a stale or blocked store is the default */
  }
  return { ...DEFAULT_FILTER };
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
  if (
    !c ||
    ![c.a, c.b].every((v) => typeof v === "number" && Number.isFinite(v) && v > 0 && v <= 1)
  )
    return "unknown";
  const cutoff = maxRegionPercent(maxPercent) / 100;
  const count = Number(c.a <= cutoff) + Number(c.b <= cutoff);
  return ["large_both", "partial_one", "partial_both"][count];
}

export function matchRegionLabel(it: Item): string {
  if (matchRegionKind(it) === "unknown") return "Match boxes not measured";
  const c = it.region_coverage!;
  return `Match boxes: A ${(100 * c.a).toFixed(1)}% · B ${(100 * c.b).toFixed(1)}%`;
}
