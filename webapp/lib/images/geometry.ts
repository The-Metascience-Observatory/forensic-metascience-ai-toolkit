/** Pane locators and crop polygons for the image item page. Pure; split out of `app/images/lib.ts`, which re-exports it. */
import type { PaneTarget, PaneLocator } from "@/lib/types/images";

export function buildPaneLocator(targets: PaneTarget[]): PaneLocator | null {
  if (!targets.length) return null;
  const first = targets[0];
  const method = first.method
    || (first.kind === "pdf_bbox" ? (first.boxes?.length ? "placement_bbox" : "placement_page") : undefined);
  return { page: first.page, confidence: first.confidence, method, targets };
}

/** The crop's outline in the parent image's pixel frame: the client twin of
 *  `evidence._parent_locator`, i.e. `crop_polygon(crop_box, (w, h),
 *  [w, 0, 0, h, 0, 0])`. `crop_box` is r0, c0, r1, c1 (rows then columns);
 *  null when the box is absent or does not fit inside the parent. */
export function cropPolygonPixels(cropBox: number[] | null | undefined,
                                  size: [number, number] | null | undefined): [number, number][] | null {
  if (!cropBox || cropBox.length !== 4 || !size || size.length !== 2) return null;
  const [r0, c0, r1, c1] = cropBox;
  const [w, h] = size;
  if (![r0, c0, r1, c1, w, h].every((v) => typeof v === "number" && Number.isFinite(v))) return null;
  if (!(w > 0 && h > 0 && 0 <= c0 && c0 < c1 && c1 <= w && 0 <= r0 && r0 < r1 && r1 <= h)) return null;
  return [[c0, r0], [c1, r0], [c1, r1], [c0, r1]];
}
