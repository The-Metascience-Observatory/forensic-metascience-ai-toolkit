import type { Item, Panel } from '../app/images/lib.ts';
import { nativeSource, type XmlFigure } from './xmlFigures.ts';

import { matchDirection, type FlipDirection } from './flipArrow.ts';

export type ImageSize = [number, number];
export type XmlImageBox = {
  id: string; anchor: string; relpath: string; label: string; color: string;
  crop: number[] | null; size: ImageSize; region: number[];
  kind: 'match' | 'panel'; flipDirection?: FlipDirection;
  /** The item side (panel index) and, for a clone, the region index. */
  side: number; index: number;
};
const finite = (v: unknown, n: number): v is number[] =>
  Array.isArray(v) && v.length === n && v.every(x => typeof x === 'number' && Number.isFinite(x));
const sizeOf = (v: unknown): ImageSize | null =>
  finite(v, 2) && v.every(x => x > 0) ? v as ImageSize : null;
const rect = (v: unknown): v is number[] =>
  finite(v, 4) && v[0] >= 0 && v[1] >= 0 && v[2] > v[0] && v[3] > v[1];

/** A native image frame must match one graphic, not just its figure number.
 * In particular a PDF crop cannot inherit XML coordinates from a caption, and
 * a publisher rendition cannot inherit a PMC crop's coordinates by figure ID.
 */
function graphicFor(panel: Panel, figures: XmlFigure[]) {
  const source = panel.crop_box ? panel.parent_image : panel.image;
  const native = nativeSource(panel.uid);
  const matches = figures.flatMap(f => f.graphics.filter(g => {
    if (!g.relpath) return false;
    if (source && source === g.relpath) return true;
    if (!native) return false;
    const { folder, file } = native;
    if (g.relpath === `${folder}/${file}`) return true;
    // An archived object is associated explicitly with its original name by
    // the source service. Local alternates must still name that same file.
    return g.status === 'verified' && g.reference.split('/').pop() === file;
  }).map(g => ({ anchor: f.anchor, relpath: g.relpath! })));
  return matches.length === 1 ? matches[0] : null;
}

/** Recorded detector pixels -> native figure pixels. Browser scaling happens
 * once, through the SVG viewBox. crop is rows/columns; region is x/y.
 */
export function projectXmlImageBox(box: XmlImageBox, figureSize: ImageSize): number[] | null {
  if (!sizeOf(figureSize) || !sizeOf(box.size) || !rect(box.region)) return null;
  const [w, h] = figureSize;
  const crop = box.crop ?? [0, 0, h, w];
  if (!rect(crop)) return null;
  const [r0, c0, r1, c1] = crop;
  if (r1 > h || c1 > w) return null;
  const [x0, y0, x1, y1] = box.region;
  if (x1 > box.size[0] || y1 > box.size[1]) return null;
  return [c0 + x0 / box.size[0] * (c1 - c0), r0 + y0 / box.size[1] * (r1 - r0),
    c0 + x1 / box.size[0] * (c1 - c0), r0 + y1 / box.size[1] * (r1 - r0)];
}

export function imageXmlBoxes(item: Item, paperDir: string, figures: XmlFigure[],
                              sizes: (ImageSize | null)[] = []): XmlImageBox[] {
  const ms = item.measurements ?? {};
  const clone = item.detector_kind === 'intra_panel_clone';
  return item.panels.flatMap((panel, side) => {
    if (panel.paper_dir !== paperDir || (clone && side > 0)) return [];
    const graphic = graphicFor(panel, figures);
    if (!graphic) return [];
    const crop = panel.crop_box ?? null;
    if (crop && !rect(crop)) return [];
    // panel_px is the measured coordinate frame even when the display image
    // is a resized preview or higher-resolution rendition.
    const size = sizeOf(side === 0 ? ms.panel_px_a : ms.panel_px_b) || sizeOf(sizes[side]);
    const regions: unknown[] = clone && Array.isArray(ms.regions)
      ? ms.regions.map(r => r?.bbox) : [side === 0 ? ms.inlier_box_a : ms.inlier_box_b];
    const boxes: XmlImageBox[] = [];
    regions.forEach((region, i) => {
      if (!size || !rect(region) || region[2] > size[0] || region[3] > size[1]) return;
      const unmirrored = !clone && side === 1 && ms.flip === true
        ? [size[0] - region[2], region[1], size[0] - region[0], region[3]] : region;
      boxes.push({ ...graphic, id: `${item.id}:${side}:${i}`, side, index: i, label: clone ? `A${i + 1}` : 'AB'[side] || `${side + 1}`,
        flipDirection: matchDirection(ms, clone ? i : side, clone), color: '#00FFDD', crop, size, region: unmirrored, kind: 'match' });
    });
    // Hash/byte matches may have no localized region. Mark the known crop as
    // a panel locator, visibly distinct from a measured match rectangle.
    if (!boxes.length && crop && regions.every(r => r == null)) {
      const [r0, c0, r1, c1] = crop;
      boxes.push({ ...graphic, id: `${item.id}:${side}:panel`, side, index: 0, label: 'AB'[side] || `${side + 1}`,
        color: '#FFFF00', crop, size: [c1 - c0, r1 - r0], region: [0, 0, c1 - c0, r1 - r0], kind: 'panel' });
    }
    return boxes;
  });
}
