export type Target = {
  id: string;
  passage_key?: string | null;
  kind: string;
  label?: string;
  quote?: string | null;
  file?: string | null;
  page?: number | null;
  boxes?: { page?: number; x0: number; y0: number; x1: number; y1: number }[];
  section_index?: number | null;
  sheet?: string | null;
  cells?: { sheet?: string; row?: number; col?: number }[];
  confidence?: string;
  method?: string;
  /** Table cells (`xml_cell` / `pdf_cell`): the XML table number and the
   *  reader's own (row, col), which the XML pane prints as data-row/data-col. */
  table_num?: number | null;
  row?: number | null;
  col?: number | null;
  raw?: string | null;
};

export function jumpable(t: Target): boolean {
  if (t.kind === "pdf_text") {
    return t.confidence === "exact" && Array.isArray(t.boxes) && t.boxes.length > 0;
  }
  if (t.kind === "pdf_bbox") {
    if (t.confidence === "bbox" && Array.isArray(t.boxes) && t.boxes.length > 0) {
      return true;
    }
    // Known page, no rectangle: still a jump (scroll to the page).
    return t.confidence === "page" && typeof t.page === "number" && t.page >= 1;
  }
  if (t.kind === "xml_text") {
    return t.confidence === "exact" && !!t.quote;
  }
  if (t.kind === "pdf_cell") {
    if (t.confidence === "exact" && Array.isArray(t.boxes) && t.boxes.length > 0) return true;
    // The cell's page is known but no box was safe to draw: scroll there.
    return t.confidence === "page" && typeof t.page === "number" && t.page >= 1;
  }
  if (t.kind === "xml_cell") {
    return t.confidence === "exact" && t.table_num != null
      && typeof t.row === "number" && typeof t.col === "number";
  }
  if (t.kind === "sheet_cell") {
    return Array.isArray(t.cells) && t.cells.length > 0;
  }
  return false;
}

export function surfaceOf(t: Target): "pdf" | "xml" | "sheet" | null {
  if (t.kind === "pdf_text" || t.kind === "pdf_bbox" || t.kind === "pdf_cell") return "pdf";
  if (t.kind === "xml_text" || t.kind === "xml_cell") return "xml";
  if (t.kind === "sheet_cell") return "sheet";
  return null;
}

/** Same quote in PDF and XML is one highlight, not two places to compare.
 * Persisted anchors carry `passage_key` explicitly (docs/specs/anchors.md §2):
 * two placements of one duplicated panel get pg{n} keys — distinct groups.
 * Prefix-slicing is the legacy fallback for anchor-less archived runs only. */
export function passageKey(t: { id: string; passage_key?: string | null }): string {
  if (t.passage_key) return t.passage_key;
  const colon = t.id.indexOf(":");
  return colon >= 0 ? t.id.slice(0, colon) : t.id;
}

export function comparisonGroups(targets: Target[] | undefined): Target[][] {
  const order: string[] = [];
  const byKey = new Map<string, Target[]>();
  for (const t of targets || []) {
    if (!jumpable(t)) continue;
    const k = passageKey(t);
    if (!byKey.has(k)) {
      order.push(k);
      byKey.set(k, []);
    }
    byKey.get(k)!.push(t);
  }
  return order.map((k) => byKey.get(k)!);
}

export function pickTarget(
  group: Target[],
  preferredSurface?: "pdf" | "xml" | "sheet" | null,
): Target | undefined {
  if (!group.length) return undefined;
  if (preferredSurface) {
    const match = group.find((t) => surfaceOf(t) === preferredSurface);
    if (match) return match;
  }
  return group[0];
}

/** Surface that can show the most comparison groups. PDF wins a tie. */
export function coveringSurface(
  targets: Target[] | undefined,
): "pdf" | "xml" | "sheet" | null {
  const groups = comparisonGroups(targets);
  if (!groups.length) return null;
  const surfaces = ["pdf", "xml", "sheet"] as const;
  let best: (typeof surfaces)[number] | null = null;
  let bestN = -1;
  for (const s of surfaces) {
    const n = groups.filter((g) => g.some((t) => surfaceOf(t) === s)).length;
    if (n > bestN) {
      bestN = n;
      best = s;
    }
  }
  return best;
}

export function primaryJumpTarget(
  targets: Target[] | undefined,
  preferredSurface?: "pdf" | "xml" | "sheet" | null,
): Target | undefined {
  const surface = preferredSurface ?? coveringSurface(targets);
  return pickTarget(comparisonGroups(targets)[0] || [], surface);
}

export function highlightJumps(
  targets: Target[] | undefined,
  preferredSurface?: "pdf" | "xml" | "sheet" | null,
): { label: string; target: Target }[] {
  const groups = comparisonGroups(targets);
  if (groups.length < 2) return [];
  const surface = preferredSurface ?? coveringSurface(targets);
  const out: { label: string; target: Target }[] = [];
  groups.forEach((group, i) => {
    const target = pickTarget(group, surface);
    if (target) out.push({ label: `Highlight ${i + 1}`, target });
  });
  return out;
}

export function pdfBoxes(locator: {
  targets?: Target[];
  boxes?: Target["boxes"];
  page?: number | null;
  confidence?: string;
} | null): { page?: number; x0: number; y0: number; x1: number; y1: number; tid?: string }[] {
  if (!locator) return [];
  const fromTargets = (locator.targets || [])
    .filter((t) => jumpable(t)
      && (t.kind === "pdf_text" || t.kind === "pdf_bbox" || t.kind === "pdf_cell"))
    .flatMap((t) => (t.boxes || []).map((b) => ({ ...b, tid: t.id })));
  if (fromTargets.length) return fromTargets;
  if ((locator.confidence === "exact" || locator.confidence === "bbox")
      && Array.isArray(locator.boxes)) {
    return locator.boxes.map((b) => ({ ...b }));
  }
  return [];
}

/** The table cells a finding names, for the XML pane to mark. */
export function xmlCells(targets: Target[] | undefined):
    { id: string; tableNum: number; row: number; col: number }[] {
  return (targets || [])
    .filter((t) => t.kind === "xml_cell" && jumpable(t))
    .map((t) => ({ id: t.id, tableNum: t.table_num as number,
                   row: t.row as number, col: t.col as number }));
}

/** Above this many places, step through them rather than show a button each. */
export const STEPPER_AT = 8;
