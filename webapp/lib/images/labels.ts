/** Wording: decision choices, saved-judgment and verdict labels, number formatting, rendition lines. Pure; split out of `app/images/lib.ts`, which re-exports it. */
import type { FigureSources, Item } from "@/lib/types/images";

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

export function judgmentDecision(it: Item): string {
  return it.screening?.decision || (it.cleared ? "automatic_clearance" : it.adjudication?.verdict ? "legacy" : "missing");
}

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
