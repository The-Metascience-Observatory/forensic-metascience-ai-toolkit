/** Helpers the PDF-box, XML-box and thumbnail-preview projections share.
 *
 *  Each of those modules used to carry its own `finite`, its own crop
 *  mapping (`c0 + x / size * (c1 - c0)`) and its own B-side un-mirroring.
 *  One copy here, pinned by `test/geometry.test.mjs`, which also checks that
 *  the PDF and XML projections agree through `cropToParent`. */
import { mirrorBox } from "../affine.ts";

import type { Box, Crop, Size } from "./types.ts";

/** `v` is an array of exactly `n` finite numbers. */
export const finite = (v: unknown, n: number): v is number[] =>
  Array.isArray(v) && v.length === n && v.every((x) => typeof x === "number" && Number.isFinite(x));

/** A positive [width, height], or null. */
export const sizeOf = (v: unknown): Size | null =>
  finite(v, 2) && v.every((x) => x > 0) ? (v as Size) : null;

/** A box with positive extent; `nonNegative` also requires its origin at or
 *  past zero (the XML frame has no negative pixels). */
export const isRect = (v: unknown, { nonNegative = false } = {}): v is Box =>
  finite(v, 4) && v[2] > v[0] && v[3] > v[1] && (!nonNegative || (v[0] >= 0 && v[1] >= 0));

/** A point in a panel's pixel frame (`size` wide and high) mapped onto the
 *  parent figure, where the panel is the crop [r0, c0, r1, c1] (rows then
 *  columns) of that figure. Linear in each axis; no clipping. */
export function cropToParent([x, y]: readonly [number, number], size: Size, crop: Crop): [number, number] {
  const [r0, c0, r1, c1] = crop;
  return [c0 + (x / size[0]) * (c1 - c0), r0 + (y / size[1]) * (r1 - r0)];
}

/** The whole-figure crop for a panel that is the figure itself. */
export const wholeCrop = (figure: Size): Crop => [0, 0, figure[1], figure[0]];

/** The B-side box as printed. When the detector matched against a mirrored
 *  B (`flip`), its B coordinates are in that mirrored frame and nothing on
 *  disk un-flips them; clone regions and the A side are never mirrored. */
export function unmirror(region: Box, side: number, size: Size, flip: boolean, clone: boolean): Box {
  return !clone && side === 1 && flip ? mirrorBox(region, size[0]) : region;
}

/** The region records a match names on one side: a clone's `regions`
 *  (which live on side 0), else that side's inlier box. A record whose
 *  `bbox` is absent means "no measured region" and the caller decides what
 *  that absence licenses; it is never read as a box. */
export function matchRegions(ms: Record<string, unknown>, side: number, clone: boolean)
  : { bbox?: unknown; polygon?: unknown }[] {
  if (clone && Array.isArray(ms.regions)) {
    return ms.regions.map((r) => (r && typeof r === "object" ? r as { bbox?: unknown; polygon?: unknown } : {}));
  }
  return [{ bbox: side === 0 ? ms.inlier_box_a : ms.inlier_box_b }];
}
