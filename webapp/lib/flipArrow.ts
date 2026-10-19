/** Orientation markers, not a claim about which image was copied first.
 * Ordered corners preserve the panel's x axis through PDF/affine projection; 1 is horizontal and 2 is vertical. */
export type Point = [number, number];
export type FlipDirection = 1 | -1 | 2 | -2;
/** B's original orientation relative to A, drawn only for a REFLECTED match:
 * a pure rotation (e.g. a half-turn) gets no arrow, since the arrows mark flips.
 * Pair affine is in mirrored-B coordinates, while clone affine is already in
 * the original image frame. */
export function matchDirection(ms: Record<string, unknown>, side: number, clone = false): FlipDirection | undefined {
  if (side !== 0 && side !== 1) return undefined;
  const nested = ms.transform && typeof ms.transform === 'object' ? ms.transform as Record<string, unknown> : {};
  const flip = ms.flip === true || nested.flip === true;
  if (!flip) return undefined;
  const affine = ms.affine;
  let angle = typeof ms.rotation_deg === 'number' ? ms.rotation_deg : typeof nested.rotation_deg === 'number' ? nested.rotation_deg : 0;
  if (!Number.isFinite(angle)) angle = 0;
  let x = Math.cos(angle * Math.PI / 180), y = Math.sin(angle * Math.PI / 180);
  if (Array.isArray(affine) && affine.length === 2 && affine.every(r => Array.isArray(r) && r.length === 3 && r.every(v => typeof v === 'number' && Number.isFinite(v)))) {
    x = affine[0][0]; y = affine[1][0];
  } else if (clone) x = -x;
  if (!clone) x = -x;
  if (Math.hypot(x,y) < 1e-8) return undefined;
  // A horizontal mirror followed by a half-turn is a vertical reflection:
  // the x axes agree, so use the y axes to make that flip visible.
  if (Math.abs(Math.atan2(y,x)) < Math.PI / 180) return side === 0 ? 2 : -2;
  if (side === 0) return 1;
  return Math.abs(x) >= Math.abs(y) ? (x >= 0 ? 1 : -1) : (y >= 0 ? 2 : -2);
}
export function boxCorners([x0,y0,x1,y1]: number[]): Point[] {
  return [[x0,y0],[x1,y0],[x1,y1],[x0,y1]];
}
export function flipArrow(points: Point[], direction?: FlipDirection): Point[] {
  if (!direction || points.length < 2 || points.some(p => p.length !== 2 || !p.every(Number.isFinite))) return [];
  const [x,y] = points[0], [X,Y] = points[Math.abs(direction) === 2 ? 3 : 1] || points[1];
  const length = Math.hypot(X-x,Y-y);
  if (!length) return [];
  const ux = (X-x)/length*Math.sign(direction), uy = (Y-y)/length*Math.sign(direction);
  const cx = (x+X)/2, cy = (y+Y)/2;
  const h = length * .05;
  return [[cx+ux*h*1.5,cy+uy*h*1.5],
    [cx-ux*h-uy*h,cy-uy*h+ux*h],
    [cx-ux*h+uy*h,cy-uy*h-ux*h]];
}
export const FLIP_LABEL = 'Arrows mark a reflected (mirrored) match and show its orientation, not copying direction';
export function appendFlipArrow(svg: SVGElement, points: Point[], color: string, direction?: FlipDirection) {
  const arrow = flipArrow(points, direction);
  if (!arrow.length) return;
  const el = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
  el.setAttribute('points', arrow.map(p=>p.join(',')).join(' '));
  el.setAttribute('fill', color);
  el.setAttribute('stroke', '#111');
  el.setAttribute('stroke-width', '1');
  el.setAttribute('vector-effect', 'non-scaling-stroke');
  el.setAttribute('data-flip-arrow', String(direction));
  const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
  title.textContent = FLIP_LABEL; el.append(title); svg.append(el);
}
export function drawFlipArrow(ctx: CanvasRenderingContext2D, points: Point[], color: string, direction?: FlipDirection, scale = 1) {
  const arrow = flipArrow(points, direction);
  if (!arrow.length) return;
  ctx.save(); ctx.setLineDash([]); ctx.fillStyle = color; ctx.strokeStyle = '#111'; ctx.lineWidth = 1 / scale;
  ctx.beginPath(); arrow.forEach(([x,y],i)=>i ? ctx.lineTo(x,y) : ctx.moveTo(x,y));
  ctx.closePath(); ctx.fill(); ctx.stroke(); ctx.restore();
}
