/** Queue order: the sort keys, cycling a column header, the paper column and the next undecided item. Pure; split out of `app/images/lib.ts`, which re-exports it. */
import type { Decision, Item, Filter, QueueSort } from "@/lib/types/images";

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

export function paperColumn(it: Item): string {
  if (it.kind === "cross" && it.papers?.length) {
    const dirs = it.papers.map((p) => p.dir).filter(Boolean);
    if (dirs.length) return dirs.join(" ~ ");
  }
  return it.paper?.dir || "";
}
