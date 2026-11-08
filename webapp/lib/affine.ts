/**
 * The comparator's geometry, kept pure so `test/smoke.mjs` can pin it.
 *
 * A 2x3 affine is stored as [a, b, c, d, e, f] with
 *   x' = a x + c y + e ;  y' = b x + d y + f
 * (the canvas `transform()` argument order). The detector records its
 * affine as rows [[a, b, tx], [c, d, ty]] mapping A -> B, and `fromAffine`
 * converts.
 *
 * FLIP (2026-09-08, from the match-control session): when `flip` is true
 * the detector mirrored B left-right BEFORE matching, so the recorded
 * affine maps A into the MIRRORED B and `inlier_box_b` is in that mirrored
 * frame too. Nothing on disk un-flips them. `toOriginalB` composes the
 * mirror back on, so a quad or a warp lands on the panel as printed.
 */

export type Box = [number, number, number, number];
export type M = [number, number, number, number, number, number];
export type View = "side" | "blink" | "overlay" | "video";

export function invert(m: M): M | null {
  const [a, b, c, d, e, f] = m;
  const det = a * d - b * c;
  if (!det) return null;
  const ia = d / det, ib = -b / det, ic = -c / det, id = a / det;
  return [ia, ib, ic, id, -(ia * e + ic * f), -(ib * e + id * f)];
}

export function fromAffine(rows: unknown): M | null {
  if (!Array.isArray(rows) || rows.length !== 2) return null;
  const r0 = rows[0], r1 = rows[1];
  if (!Array.isArray(r0) || !Array.isArray(r1) || r0.length < 3 || r1.length < 3) return null;
  const m: M = [Number(r0[0]), Number(r1[0]), Number(r0[1]), Number(r1[1]), Number(r0[2]), Number(r1[2])];
  return m.every((v) => Number.isFinite(v)) ? m : null;
}

/** A similarity that maps box A onto box B with no rotation: a GUESS,
 *  and the caller labels it as one. */
export function fromBoxes(ba: Box, bb: Box): M {
  const sx = (bb[2] - bb[0]) / Math.max(1, ba[2] - ba[0]);
  const sy = (bb[3] - bb[1]) / Math.max(1, ba[3] - ba[1]);
  const s = (sx + sy) / 2;
  return [s, 0, 0, s, bb[0] - ba[0] * s, bb[1] - ba[1] * s];
}

/** `outer ∘ inner`: apply `inner` first, then `outer`. */
export function compose(outer: M, inner: M): M {
  const [oa, ob, oc, od, oe, of] = outer;
  const [ia, ib, ic, id, ie, iff] = inner;
  return [
    oa * ia + oc * ib, ob * ia + od * ib,
    oa * ic + oc * id, ob * ic + od * id,
    oa * ie + oc * iff + oe, ob * ie + od * iff + of,
  ];
}

/** Left-right mirror of a frame `width` px wide: x -> width - x. */
export function mirrorX(width: number): M {
  return [-1, 0, 0, 1, width, 0];
}

export function mirrorBox(b: Box, width: number): Box {
  return [width - b[2], b[1], width - b[0], b[3]];
}

/** The detector's A -> B affine re-expressed against B AS PRINTED. Identity
 *  when the match needed no flip. */
export function toOriginalB(m: M, flip: boolean, widthB: number): M {
  return flip ? compose(mirrorX(widthB), m) : m;
}

export function apply(m: M, x: number, y: number): [number, number] {
  return [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]];
}

/** The four corners of `box`, in order, mapped through `m`. */
export function quadThrough(box: Box, m: M): [number, number][] {
  const pts: [number, number][] = [[box[0], box[1]], [box[2], box[1]], [box[2], box[3]], [box[0], box[3]]];
  return pts.map(([x, y]) => apply(m, x, y));
}

/** True when every edge of the quad is horizontal or vertical. */
export function isAxisAligned(quad: [number, number][], tol = 1e-6): boolean {
  return quad.every((p, i) => {
    const q = quad[(i + 1) % quad.length];
    return Math.abs(p[0] - q[0]) < tol || Math.abs(p[1] - q[1]) < tol;
  });
}

/** The caption fragment for the recorded transform, from the detector's
 *  measurements: "rotation −8.7°, scale 0.951", "mirrored", ... `null` when
 *  the measurements record none of the three, "translation only" when they
 *  record them all as nothing. */
export function describeTransform(ms: Record<string, unknown>): string | null {
  const rot = typeof ms.rotation_deg === "number" ? ms.rotation_deg : null;
  const scale = typeof ms.scale === "number" ? ms.scale : null;
  const flip = ms.flip === true;
  if (rot === null && scale === null && !("flip" in ms)) return null;
  const parts: string[] = [];
  if (flip) parts.push("mirrored");
  if (rot !== null && Math.abs(rot) >= 0.05) parts.push(`rotation ${rot < 0 ? "−" : ""}${Math.abs(rot)}°`);
  if (scale !== null && Math.abs(scale - 1) >= 0.005) parts.push(`scale ${scale}`);
  return parts.length ? parts.join(", ") : "translation only";
}

/** The comparator's views, in toolbar order; `video` only when one is rendered. */
export function viewModes(hasVideo: boolean): View[] {
  const base: View[] = ["side", "blink", "overlay"];
  return hasVideo ? [...base, "video"] : base;
}

/**
 * PAGE ORIENTATION (2026-11-08, Dan: 10.1101/2022.11.28.22282811 IMGDUP-2
 * showed A upside down beside an upright B, while the PDF pane showed the two
 * identical). The detector compares an embedded stream's STORED pixels, and a
 * PDF may store a stream upside down or mirrored and undo that in the
 * placement matrix (there `[52.2, 0, 0, -46.9, ...]`). The measured "mirrored,
 * rotation −179.9°" was then the producer's storage, not the authors' copy.
 *
 * `placementOrientation` reads the placement matrix (and the page's own
 * rotation) into a signed-permutation map from stored pixels to pixels as
 * printed; only right-angle orientations are handled, anything else (or
 * placements that disagree) leaves the panel as stored and says why.
 * `toPrinted` re-expresses a pair's measurements in that frame, keeping the
 * detector's convention (under `flip`, affine and `inlier_box_b` are in the
 * mirrored-B frame). Nothing here touches stored findings.
 */
export type Orientation = { m: M; width: number; height: number };
type PlacementLike = { transform?: number[]; page_rotation?: number };

export function placementOrientation(placements: PlacementLike[] | undefined, size: [number, number]):
    { orientation: Orientation | null; note: string | null } {
  const signs: string[] = [];
  let lin: [number, number, number, number] | null = null;   // X = p x + q y ; Y = r x + s y
  for (const pl of placements || []) {
    const t = pl.transform;
    if (!Array.isArray(t) || t.length !== 6 || !t.every((v) => Number.isFinite(v))) continue;
    // PyMuPDF: page X = a u + c v + e, Y = b u + d v + f (u, v in the unit image square, y down).
    let [p, q, r, s] = [t[0], t[2], t[1], t[3]];
    const rot = (((pl.page_rotation || 0) % 360) + 360) % 360;
    // The displayed page: 90 -> (h - Y, X), 180 -> (w - X, h - Y), 270 -> (Y, w - X).
    if (rot === 90) [p, q, r, s] = [-r, -s, p, q];
    else if (rot === 180) [p, q, r, s] = [-p, -q, -r, -s];
    else if (rot === 270) [p, q, r, s] = [r, s, -p, -q];
    else if (rot !== 0) return { orientation: null, note: "page rotation is not a right angle; panels shown as stored" };
    const big = Math.max(Math.abs(p), Math.abs(q), Math.abs(r), Math.abs(s));
    if (!big) continue;
    const tol = big * 1e-3;
    let cand: [number, number, number, number];
    if (Math.abs(q) < tol && Math.abs(r) < tol) cand = [Math.sign(p), 0, 0, Math.sign(s)];
    else if (Math.abs(p) < tol && Math.abs(s) < tol) cand = [0, Math.sign(q), Math.sign(r), 0];
    else return { orientation: null, note: "placed at an angle; panels shown as stored" };
    signs.push(cand.join(","));
    lin = cand;
  }
  if (!lin) return { orientation: null, note: null };
  if (new Set(signs).size > 1) return { orientation: null, note: "placements drawn in different orientations; panels shown as stored" };
  const [p, q, r, s] = lin;
  if (p === 1 && s === 1) return { orientation: null, note: null };   // stored as printed
  const [w, h] = size;
  const tx = (p < 0 ? w : 0) + (q < 0 ? h : 0);
  const ty = (r < 0 ? w : 0) + (s < 0 ? h : 0);
  const swapped = p === 0;
  return { orientation: { m: [p, r, q, s, tx, ty], width: swapped ? h : w, height: swapped ? w : h }, note: null };
}

function boundsThrough(box: Box, m: M): Box {
  const q = quadThrough(box, m);
  const xs = q.map((p) => p[0]), ys = q.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

const round = (v: number, k: number) => Math.round(v * 10 ** k) / 10 ** k;
const isBox = (b: unknown): b is Box => Array.isArray(b) && b.length === 4 && b.every((v) => Number.isFinite(v));

/** A pair's measurements with A and B as printed. `sizeB` is B's STORED size. */
export function toPrinted(ms: Record<string, unknown>, oa: Orientation | null, ob: Orientation | null,
    sizeB: [number, number]): Record<string, unknown> {
  if (!oa && !ob) return ms;
  const I: M = [1, 0, 0, 1, 0, 0];
  const mA = oa ? oa.m : I, mB = ob ? ob.m : I;
  const wB2 = ob ? ob.width : sizeB[0];
  const flip = ms.flip === true;
  const out: Record<string, unknown> = { ...ms, page_oriented: true };
  if (isBox(ms.inlier_box_a)) out.inlier_box_a = boundsThrough(ms.inlier_box_a, mA).map((v) => round(v, 1));
  let boxB: Box | null = isBox(ms.inlier_box_b) ? (flip ? mirrorBox(ms.inlier_box_b, sizeB[0]) : ms.inlier_box_b) : null;
  if (boxB) boxB = boundsThrough(boxB, mB);
  const stored = fromAffine(ms.affine);
  const invA = invert(mA);
  let newFlip: boolean;
  if (stored && invA) {
    const printed = compose(mB, compose(toOriginalB(stored, flip, sizeB[0]), invA));
    newFlip = printed[0] * printed[3] - printed[1] * printed[2] < 0;
    const kept = newFlip ? compose(mirrorX(wB2), printed) : printed;
    out.affine = [[kept[0], kept[2], kept[4]], [kept[1], kept[3], kept[5]]].map((row) => row.map((v) => round(v, 6)));
    out.rotation_deg = round(Math.atan2(kept[1], kept[0]) * 180 / Math.PI, 1);
    out.scale = round(Math.sqrt(Math.abs(printed[0] * printed[3] - printed[1] * printed[2])), 3);
  } else {
    const det = (m: M) => m[0] * m[3] - m[1] * m[2];
    newFlip = flip !== (det(mA) * det(mB) < 0);
  }
  if (boxB) out.inlier_box_b = (newFlip ? mirrorBox(boxB, wB2) : boxB).map((v) => round(v, 1));
  out.flip = newFlip;
  return out;
}

/** Words for an orientation: what the PDF does to the stored pixels when it prints them. */
export function orientationLabel(o: Orientation): string {
  const [p, r, q, s] = o.m;
  if (p === -1 && s === 1) return "mirrored left-right";
  if (p === 1 && s === -1) return "flipped top-bottom";
  if (p === -1 && s === -1) return "turned 180°";
  if (q === 1 && r === -1) return "turned 90° anticlockwise";
  if (q === -1 && r === 1) return "turned 90° clockwise";
  return "transposed";
}
