/** Paint-time cleanup of locator rectangles. Does not change locators. */

export type PdfBox = {
  page?: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  tid?: string;
};

function usable(b: PdfBox, sx: number, sy: number, minPx: number): boolean {
  return (b.x1 - b.x0) * sx >= minPx && (b.y1 - b.y0) * sy >= minPx;
}

function sameLine(a: PdfBox, b: PdfBox): boolean {
  const line = Math.max(a.y1 - a.y0, b.y1 - b.y0, 1);
  const ac = (a.y0 + a.y1) / 2;
  const bc = (b.y0 + b.y1) / 2;
  return Math.abs(ac - bc) <= 0.4 * line;
}

function closeHoriz(a: PdfBox, b: PdfBox): boolean {
  const em = Math.max(a.y1 - a.y0, b.y1 - b.y0, 1);
  const gap = b.x0 >= a.x1 ? b.x0 - a.x1
    : a.x0 >= b.x1 ? a.x0 - b.x1
    : 0;
  return gap <= em;
}

function absorb(into: PdfBox, b: PdfBox) {
  into.x0 = Math.min(into.x0, b.x0);
  into.y0 = Math.min(into.y0, b.y0);
  into.x1 = Math.max(into.x1, b.x1);
  into.y1 = Math.max(into.y1, b.y1);
}

/**
 * Drop boxes that vanish on screen, then fuse collinear neighbours so one
 * quote-line is one strip. Different `tid`s stay separate (two highlights).
 */
export function mergePdfBoxes(
  boxes: PdfBox[],
  sx = 1,
  sy = 1,
  minPx = 3,
): PdfBox[] {
  const keep = boxes.filter((b) => usable(b, sx, sy, minPx));
  const groups = new Map<string, PdfBox[]>();
  for (const b of keep) {
    const key = `${b.page ?? ""}::${b.tid ?? ""}`;
    const g = groups.get(key);
    if (g) g.push(b);
    else groups.set(key, [b]);
  }
  const out: PdfBox[] = [];
  for (const g of groups.values()) {
    g.sort((a, b) => a.y0 - b.y0 || a.x0 - b.x0);
    const fused: PdfBox[] = [];
    for (const b of g) {
      const last = fused[fused.length - 1];
      if (last && sameLine(last, b) && closeHoriz(last, b)) {
        absorb(last, b);
      } else {
        fused.push({ ...b });
      }
    }
    out.push(...fused);
  }
  return out;
}
