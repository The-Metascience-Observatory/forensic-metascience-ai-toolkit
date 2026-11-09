/** Pure text-layer helpers for `PdfPane`: what pdf.js's text items become
 *  (one haystack per page with the runs that place each match) and the find
 *  over it. No DOM here beyond the slot elements the types name. */

export type Box = { x0: number; y0: number; x1: number; y1: number };

export type TextRun = {
  str: string;
  start: number;
  end: number;
  box: Box;
};

export type PageSlot = {
  wrap: HTMLDivElement;
  overlay: HTMLDivElement;
  search: HTMLDivElement;
  unscaledW: number;
  unscaledH: number;
  vw: number;
  vh: number;
  haystack: string;
  runs: TextRun[];
  textLayer: { cancel: () => void } | null;
};

export type Match = { page: number; boxes: Box[] };

function isTextItem(item: unknown): item is { str: string; transform: number[];
  width: number; height: number; hasEOL?: boolean } {
  return !!item && typeof item === "object" && "str" in item
    && typeof (item as { str: unknown }).str === "string";
}

function itemBox(
  item: { transform: number[]; width: number; height: number },
  viewport: { convertToViewportRectangle: (r: number[]) => number[] },
): Box {
  const x = item.transform[4];
  const y = item.transform[5];
  const h = item.height || Math.hypot(item.transform[2], item.transform[3]) || 8;
  const w = item.width || 0;
  const rect = viewport.convertToViewportRectangle([x, y, x + w, y + h]);
  const x0 = Math.min(rect[0], rect[2]);
  const y0 = Math.min(rect[1], rect[3]);
  const x1 = Math.max(rect[0], rect[2]);
  const y1 = Math.max(rect[1], rect[3]);
  return { x0, y0, x1, y1 };
}

export function pageText(
  items: unknown[],
  viewport: { convertToViewportRectangle: (r: number[]) => number[] },
): { haystack: string; runs: TextRun[] } {
  let haystack = "";
  const runs: TextRun[] = [];
  let prev = "";
  let prevEOL = false;
  for (const raw of items) {
    if (!isTextItem(raw)) continue;
    const str = raw.str;
    if (prev && !prevEOL && str && !/\s$/.test(prev) && !/^\s/.test(str)) {
      haystack += " ";
    }
    if (str) {
      const start = haystack.length;
      haystack += str;
      runs.push({ str, start, end: haystack.length, box: itemBox(raw, viewport) });
    }
    prev = str || prev;
    prevEOL = !!raw.hasEOL;
    if (raw.hasEOL) haystack += "\n";
  }
  return { haystack, runs };
}

export function findMatches(slots: PageSlot[], query: string): Match[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const out: Match[] = [];
  for (let i = 0; i < slots.length; i++) {
    const page = i + 1;
    const lower = slots[i].haystack.toLowerCase();
    let from = 0;
    while (from <= lower.length - q.length) {
      const at = lower.indexOf(q, from);
      if (at < 0) break;
      const end = at + q.length;
      const boxes: Box[] = [];
      for (const run of slots[i].runs) {
        if (run.end <= at || run.start >= end) continue;
        boxes.push(run.box);
      }
      if (boxes.length) out.push({ page, boxes });
      from = at + 1;
    }
  }
  return out;
}
