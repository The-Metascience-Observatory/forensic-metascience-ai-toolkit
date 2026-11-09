import { isRect, matchRegions, unmirror } from "./geometry/project.ts";
import type { Box, Size } from "./geometry/types.ts";

/** Boxes in the displayed panel's native pixel frame, as in the comparator.
 * No geometry is inferred for a perceptual match that recorded no region;
 * a clone's regions live on side 0 only; a third panel has none. */
export function previewBoxes(measurements: Record<string, unknown>, side: number,
  size: Size, clone = false): Box[] {
  const [w, h] = size;
  if (!(w > 0 && h > 0) || side >= 2 || (clone && side > 0)) return [];
  const regions = clone && !Array.isArray(measurements.regions) ? []
    : matchRegions(measurements, side, clone).map((r) => r.bbox);
  return regions.flatMap((raw) => {
    if (!isRect(raw)) return [];
    const shown = unmirror(raw, side, size, measurements.flip === true, clone);
    const clipped: Box = [Math.max(0, shown[0]), Math.max(0, shown[1]), Math.min(w, shown[2]), Math.min(h, shown[3])];
    return clipped[2] > clipped[0] && clipped[3] > clipped[1] ? [clipped] : [];
  });
}
