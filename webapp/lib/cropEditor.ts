/** The summary figure's crop editor: selection rectangles in image pixels,
 *  the stage bounds a floating piece may move in, the brand band's metrics
 *  and the grab/scale rules for the handles. Pure; `SummaryFigure.tsx` draws
 *  with them. */

/** An axis-aligned rectangle in image pixels, corners in any order. */
export type PixelRect = { x0: number; y0: number; x1: number; y1: number };

/** Corners ordered, rounded and clamped to a `w` x `h` image; null when
 * nothing of it is left. */
export function normaliseRect(r: PixelRect, w: number, h: number): PixelRect | null {
  const x0 = Math.max(0, Math.round(Math.min(r.x0, r.x1))), x1 = Math.min(w, Math.round(Math.max(r.x0, r.x1)));
  const y0 = Math.max(0, Math.round(Math.min(r.y0, r.y1))), y1 = Math.min(h, Math.round(Math.max(r.y0, r.y1)));
  return x1 > x0 && y1 > y0 ? { x0, y0, x1, y1 } : null;
}

/** The area an edit occupies: the image, grown to hold a piece moved past
 * its edges. Image coordinates, so x0/y0 are <= 0. */
export function stageBounds(w: number, h: number, piece?: { x: number; y: number; w: number; h: number } | null): PixelRect {
  if (!piece) return { x0: 0, y0: 0, x1: w, y1: h };
  return { x0: Math.min(0, piece.x), y0: Math.min(0, piece.y),
    x1: Math.max(w, piece.x + piece.w), y1: Math.max(h, piece.y + piece.h) };
}

/** The credit line's type size and band height for an image `width` wide:
 * about the reference lines' size on a typical figure, never illegible on a
 * small crop or shouting on a wide one. */
export function brandMetrics(width: number): { font: number; band: number; pad: number } {
  const font = Math.round(Math.min(56, Math.max(18, width * 0.014)));
  return { font, band: Math.round(font * 2.4), pad: Math.round(font * 0.9) };
}

/** Which edges of a selection a pointer grabs: any of l/r/t/b (two at a
 * corner), "inside" to move the whole box, or null. `tol` is the grab
 * distance in image pixels. Edges win over the interior near the border. */
export type Grab = { l?: boolean; r?: boolean; t?: boolean; b?: boolean } | "inside" | null;
export function grabSelection(sel: PixelRect, p: { x: number; y: number }, tol: number): Grab {
  const ct = tol * 1.5; // corners are the natural place to resize from: a bigger target
  if (p.x < sel.x0 - ct || p.x > sel.x1 + ct || p.y < sel.y0 - ct || p.y > sel.y1 + ct) return null;
  // Inside a small box the grab band shrinks, so its middle can still be moved.
  const near = (v: number, edge: number, outward: 1 | -1, t: number, span: number) =>
    (v - edge) * outward >= 0 ? Math.abs(v - edge) <= t : Math.abs(v - edge) <= Math.min(t, span / 4);
  const w = sel.x1 - sel.x0, h = sel.y1 - sel.y0;
  const cl = near(p.x, sel.x0, -1, ct, w), cr = !cl && near(p.x, sel.x1, 1, ct, w);
  const cu = near(p.y, sel.y0, -1, ct, h), cd = !cu && near(p.y, sel.y1, 1, ct, h);
  if ((cl || cr) && (cu || cd)) return { l: cl, r: cr, t: cu, b: cd };
  const l = near(p.x, sel.x0, -1, tol, w), r = !l && near(p.x, sel.x1, 1, tol, w);
  const t = near(p.y, sel.y0, -1, tol, h), b = !t && near(p.y, sel.y1, 1, tol, h);
  const inX = p.x >= sel.x0 - tol && p.x <= sel.x1 + tol, inY = p.y >= sel.y0 - tol && p.y <= sel.y1 + tol;
  if ((l || r) && inY) return { l, r, t: false, b: false };
  if ((t || b) && inX) return { l: false, r: false, t, b };
  return p.x > sel.x0 && p.x < sel.x1 && p.y > sel.y0 && p.y < sel.y1 ? "inside" : null;
}

/** The CSS cursor for a grab. */
export function grabCursor(g: Grab): string {
  if (!g) return "crosshair";
  if (g === "inside") return "move";
  const ns = g.t ? "n" : g.b ? "s" : "", ew = g.l ? "w" : g.r ? "e" : "";
  return `${ns}${ew}-resize`;
}

/** `start` resized by dragging the grabbed edges by (dx, dy), the opposite
 * edges held still. A corner keeps the aspect ratio (whichever axis moved
 * further sets the scale); an edge handle stretches its one axis. Never
 * flips and never shrinks below `min` pixels a side. */
export function scaleRect(start: PixelRect, g: Exclude<Grab, null | "inside">, dx: number, dy: number, min = 8): PixelRect {
  const w0 = start.x1 - start.x0, h0 = start.y1 - start.y0;
  let w = g.l ? w0 - dx : g.r ? w0 + dx : w0;
  let h = g.t ? h0 - dy : g.b ? h0 + dy : h0;
  if ((g.l || g.r) && (g.t || g.b)) {
    const sx = w / w0, sy = h / h0;
    const s = Math.max(Math.abs(sx - 1) >= Math.abs(sy - 1) ? sx : sy, min / Math.min(w0, h0));
    w = w0 * s; h = h0 * s;
  }
  w = Math.max(min, w); h = Math.max(min, h);
  const x0 = g.l ? start.x1 - w : start.x0, y0 = g.t ? start.y1 - h : start.y0;
  return { x0, y0, x1: x0 + w, y1: y0 + h };
}
