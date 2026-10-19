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
