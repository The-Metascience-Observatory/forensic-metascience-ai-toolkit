import type { Box } from "./affine.ts";
import { mirrorBox } from "./affine.ts";

/** Boxes in the displayed panel's native pixel frame, as in the comparator.
 * No geometry is inferred for a perceptual match that recorded no region. */
export function previewBoxes(measurements: Record<string, unknown>, side: number,
  size: [number, number], clone = false): Box[] {
  const [w, h] = size;
  if (!(w > 0 && h > 0)) return [];
  const regions = clone
    ? (side === 0 && Array.isArray(measurements.regions)
      ? measurements.regions.map(r => r?.bbox) : [])
    : side < 2 ? [measurements[side === 0 ? "inlier_box_a" : "inlier_box_b"]] : [];
  return regions.flatMap(raw => {
    if (!Array.isArray(raw) || raw.length !== 4 || !raw.every(v => typeof v === "number" && Number.isFinite(v))) return [];
    const box = raw as Box;
    if (box[2] <= box[0] || box[3] <= box[1]) return [];
    const shown = !clone && side === 1 && measurements.flip === true ? mirrorBox(box, w) : box;
    const clipped: Box = [Math.max(0, shown[0]), Math.max(0, shown[1]), Math.min(w, shown[2]), Math.min(h, shown[3])];
    return clipped[2] > clipped[0] && clipped[3] > clipped[1] ? [clipped] : [];
  });
}
