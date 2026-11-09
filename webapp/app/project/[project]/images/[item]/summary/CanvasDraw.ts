/** Pure canvas helpers for the summary figure: the duplication-box and
 *  drawn-box strokes, the credit band, and the pixel moves of the crop
 *  editor (lift, place, flatten). No React, no fetches. */
import { drawFlipArrow } from "@/lib/flipArrow";
import { expandFigureBox } from "@/lib/summaryGroups";
import { brandMetrics, stageBounds, type PixelRect } from "@/lib/cropEditor";
import type { DrawnBox, RenderedFigure } from "./RenderedFigure";

export function drawBox(ctx: CanvasRenderingContext2D, box: DrawnBox, scale: number, dashed = false) {
  const px = 1 / scale;
  ctx.beginPath();
  box.points.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
  ctx.closePath();
  if (dashed) ctx.setLineDash([12 * px, 8 * px]);
  ctx.strokeStyle = "#111"; ctx.lineWidth = 6 * px; ctx.stroke();
  ctx.strokeStyle = box.color; ctx.lineWidth = 3.5 * px; ctx.stroke();
  ctx.setLineDash([]);
  drawFlipArrow(ctx, box.points, box.color, box.flipDirection, scale);
  if (box.regionLabel && box.points.length) {
    const anchor = box.points.reduce((best, p) => p[1] < best[1] ? p : best);
    ctx.font = `bold ${22 * px}px sans-serif`;
    ctx.lineWidth = 4 * px; ctx.strokeStyle = "#111"; ctx.fillStyle = box.color;
    ctx.strokeText(box.regionLabel, anchor[0], anchor[1] - 6 * px);
    ctx.fillText(box.regionLabel, anchor[0], anchor[1] - 6 * px);
  }
}

/** Redraw annotations from clean pixels, so expanding a box leaves no old
 * outline behind and never stretches the scientific image. */
export function annotateFigure(figure: RenderedFigure, percent: number): HTMLCanvasElement {
  const out = blank(figure.canvas.width, figure.canvas.height);
  const ctx = out.getContext("2d")!;
  ctx.drawImage(figure.canvas, 0, 0);
  if (percent <= 0) return out; // 0 = boxes removed
  for (const box of figure.boxes) drawBox(ctx, { ...box,
    points: box.dashed ? box.points : expandFigureBox(box.points, percent, box.limit) }, 1, box.dashed);
  return out;
}

const INK = "#111", GLOBE_INK = "#444", DIM = "#555";
const SLAB = `"Roboto Slab", Georgia, "Times New Roman", serif`;

/** The site's globe mark (public/assets/globe.svg: a circle crossed by two
 * ellipses on a 16-unit box), stroked straight onto the canvas. */
export function drawGlobe(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number) {
  const k = r / 7.35;
  ctx.save();
  ctx.strokeStyle = GLOBE_INK; ctx.lineWidth = 0.9 * k; ctx.lineCap = "round";
  for (const [rx, ry] of [[7.35, 7.35], [3, 7.35], [7.35, 3]]) {
    ctx.beginPath(); ctx.ellipse(cx, cy, rx * k, ry * k, 0, 0, Math.PI * 2); ctx.stroke();
  }
  ctx.restore();
}

/** "found at [globe] The Metascience Observatory", right-aligned in a band
 * under the image -- a band, not an overlay, so it never covers a figure. */
export function drawBrand(ctx: CanvasRenderingContext2D, width: number, top: number) {
  const { font, band, pad } = brandMetrics(width);
  const r = font * 0.62, gap = font * 0.45, mid = top + band / 2;
  ctx.save();
  ctx.textBaseline = "middle";
  ctx.font = `bold ${font}px ${SLAB}`;
  const name = "The Metascience Observatory";
  let x = width - pad - ctx.measureText(name).width;
  ctx.fillStyle = INK; ctx.fillText(name, x, mid);
  x -= gap + r;
  drawGlobe(ctx, x, mid, r);
  x -= r + gap;
  ctx.font = `${Math.round(font * 0.85)}px ${SLAB}`;
  ctx.fillStyle = DIM;
  ctx.fillText("found at", x - ctx.measureText("found at").width, mid);
  ctx.restore();
}

export const blank = (w: number, h: number) => {
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(w)); c.height = Math.max(1, Math.round(h));
  const ctx = c.getContext("2d")!;
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, c.width, c.height);
  return c;
};

/** Lifted pixels (`canvas`) shown at x, y and scaled to w x h. */
export type Piece = { canvas: HTMLCanvasElement; x: number; y: number; w: number; h: number };
export const pieceRect = (p: Piece): PixelRect => ({ x0: p.x, y0: p.y, x1: p.x + p.w, y1: p.y + p.h });
/** A region lifted out of `base` (which now shows a white hole there) and
 * not yet put down. Nothing enters the history until it is placed. */
export type Floating = { base: HTMLCanvasElement; piece: Piece };

export function placePiece({ base, piece }: Floating): { canvas: HTMLCanvasElement; at: PixelRect } {
  const w = Math.max(1, Math.round(piece.w)), h = Math.max(1, Math.round(piece.h));
  const b = stageBounds(base.width, base.height, { x: piece.x, y: piece.y, w, h });
  const out = blank(b.x1 - b.x0, b.y1 - b.y0);
  const ctx = out.getContext("2d")!;
  ctx.drawImage(base, -b.x0, -b.y0);
  const x = Math.round(piece.x - b.x0), y = Math.round(piece.y - b.y0);
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(piece.canvas, x, y, w, h);
  return { canvas: out, at: { x0: x, y0: y, x1: x + w, y1: y + h } };
}

export function flatten(content: HTMLCanvasElement, brand: boolean): HTMLCanvasElement {
  const band = brand ? brandMetrics(content.width).band : 0;
  const out = blank(content.width, content.height + band);
  const ctx = out.getContext("2d")!;
  ctx.drawImage(content, 0, 0);
  if (brand) drawBrand(ctx, content.width, content.height);
  return out;
}

/** A drawn box: a neon outline over a dark keyline, the same look as the
 *  duplication boxes, at a width that scales with the image. */
export function strokeBox(ctx: CanvasRenderingContext2D, r: PixelRect, color: string, imageWidth: number) {
  const w = Math.max(3, imageWidth / 500);
  ctx.save();
  ctx.lineJoin = "miter";
  ctx.strokeStyle = "#111"; ctx.lineWidth = w * 1.7; ctx.strokeRect(r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0);
  ctx.strokeStyle = color; ctx.lineWidth = w; ctx.strokeRect(r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0);
  ctx.restore();
}
