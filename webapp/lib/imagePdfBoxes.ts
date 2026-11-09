import { matchDirection, type FlipDirection } from "./flipArrow.ts";
import { cropToParent, finite, isRect, matchRegions, unmirror } from "./geometry/project.ts";
import type { Box, Crop, Size } from "./geometry/types.ts";
import { isPdfReference, paneDocument } from "./paneDocument.ts";
import type { Item, Panel, Placement } from "./types/images.ts";

export const DUPLICATION_COLORS = ["#00FFDD", "#FFFF00", "#39FF14"] as const;
export type ImagePdfBox = {
  page: number;
  tid: string;
  paperDir: string;
  documentPath: string;
  points: [number, number][];
  color: string;
  regionLabel?: string;
  flipDirection?: FlipDirection;
};

/** Detector pixels -> parent stream pixels -> unrotated PDF -> displayed PDF.
 * Only exact placements can locate a subregion; a parent/page-only location
 * cannot justify painting a precise match onto the source document.
 */
export function projectImageBox(
  panel: Panel,
  pl: Placement,
  size: [number, number],
  box: number[],
): [number, number][] | null {
  if (!finite(box, 4) || box[2] <= box[0] || box[3] <= box[1]) return null;
  return projectImagePolygon(panel, pl, size, [
    [box[0], box[1]],
    [box[2], box[1]],
    [box[2], box[3]],
    [box[0], box[3]],
  ]);
}

export function projectImagePolygon(
  panel: Panel,
  pl: Placement,
  size: [number, number],
  polygon: number[][],
): [number, number][] | null {
  if (
    !["crop_exact", "stream_exact"].includes(pl.bbox_kind || "") ||
    pl.geometry_gap ||
    !finite(pl.transform, 6) ||
    !finite(pl.parent_size, 2) ||
    !finite(size, 2) ||
    size.some((x) => x <= 0) ||
    pl.parent_size.some((x) => x <= 0) ||
    polygon.length < 3 ||
    polygon.some((p) => !finite(p, 2))
  )
    return null;
  if (pl.bbox_kind === "crop_exact" && !finite(panel.crop_box, 4)) return null;
  const [pw, ph] = pl.parent_size;
  const crop = (panel.crop_box ?? [0, 0, ph, pw]) as Crop; // row/column order
  if (!isRect(crop)) return null;
  const [a, b, c, d, e, f] = pl.transform;
  if (Math.abs(a * d - b * c) < 1e-10) return null;
  const rotation = (((pl.page_rotation || 0) % 360) + 360) % 360;
  if (![0, 90, 180, 270].includes(rotation) || (rotation && !finite(pl.page_size, 2))) return null;
  return polygon.map(([x, y]) => {
    // Panel pixels -> parent figure pixels -> the placement's unit square.
    const [px, py] = cropToParent([x, y], size as Size, crop);
    const u = px / pw,
      v = py / ph;
    const X = a * u + c * v + e,
      Y = b * u + d * v + f;
    const [w, h] = pl.page_size || [0, 0];
    return rotation === 90
      ? [h - Y, X]
      : rotation === 180
        ? [w - X, h - Y]
        : rotation === 270
          ? [Y, w - X]
          : [X, Y];
  });
}

/** Detector kinds whose match IS the whole panel: the same image placed twice
 *  (identical stream, same xref, or a near-identical perceptual hash). They
 *  carry no inlier box, so without this the summary figure drew nothing for
 *  them (Dan, 2026-10-22, Lab Invest 2019 Fig 5 C vs E). */
export const WHOLE_IMAGE_KINDS: ReadonlySet<string> = new Set([
  "near_duplicate_phash",
  "identical_stream",
  "same_xref_reused",
]);

/** `printed`: the measurements as printed (`affine.toPrinted`), used only to
 * decide the reflection arrows -- the boxes are projected from the STORED
 * measurements, which is what the placement matrix maps onto the page. */
export function imagePdfBoxes(
  item: Item,
  sizes: ([number, number] | null)[],
  printed?: Record<string, unknown>,
): ImagePdfBox[] {
  const result: ImagePdfBox[] = [];
  const ms = item.measurements ?? {};
  const reflected = !printed || printed.flip === true;
  const clone = item.detector_kind === "intra_panel_clone";
  item.panels.forEach((panel, side) => {
    const size = sizes[side];
    if (!size || (clone && side > 0)) return;
    const localized = side === 0 ? ms.inlier_box_a : ms.inlier_box_b;
    // A whole-image duplication has no measured region: its box is the whole
    // panel (its own crop of the figure, not the entire figure), on BOTH sides.
    const wholePanel =
      !clone && !finite(localized, 4) && WHOLE_IMAGE_KINDS.has(item.detector_kind ?? "");
    const regions = wholePanel
      ? [{ bbox: [0, 0, size[0], size[1]], polygon: undefined }]
      : matchRegions(ms, side, clone);
    for (const [regionIndex, record] of regions.entries()) {
      const region = record.bbox;
      if (!finite(region, 4)) continue;
      // The detector's B coordinates are mirrored when flip is true.
      const box = unmirror(region as Box, side, size, ms.flip === true, clone);
      panel.placements.forEach((pl, k) => {
        // Retained media paths replace the source filename; match by the
        // stable document ID before using that archived path.
        const paper = (item.papers || [item.paper]).find((p) => p?.dir === panel.paper_dir);
        const document = paneDocument(panel, paper);
        const sameDocument = pl.document_id && pl.document_id === panel.document?.id;
        const documentPath =
          sameDocument && document.kind === "pdf"
            ? document.path
            : pl.document_path || panel.document?.path;
        if (!isPdfReference(documentPath) || !Number.isInteger(pl.page) || pl.page < 1) return;
        const points =
          clone && Array.isArray(record.polygon)
            ? projectImagePolygon(panel, pl, size, record.polygon)
            : projectImageBox(panel, pl, size, box);
        if (points)
          result.push({
            page: pl.page,
            tid: `${item.id}:${side === 0 ? "a" : "b"}:${k}`,
            paperDir: panel.paper_dir,
            documentPath,
            points,
            flipDirection: reflected
              ? matchDirection(ms, clone ? regionIndex : side, clone)
              : undefined,
            regionLabel: clone ? (regionIndex === 0 ? "A" : "B") : undefined,
            color: DUPLICATION_COLORS[clone ? regionIndex % DUPLICATION_COLORS.length : 0],
          });
      });
    }
  });
  return result;
}
