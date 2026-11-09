import { matchDirection, type FlipDirection } from './flipArrow.ts';
import { cropToParent, isRect, matchRegions, sizeOf, unmirror, wholeCrop } from './geometry/project.ts';
import type { Box, Crop, Size } from './geometry/types.ts';
import type { Item, Panel } from './types/images.ts';
import { nativeSource, panelSourcePaths, type XmlFigure } from './xmlFigures.ts';

export type ImageSize = Size;
export type XmlImageBox = {
  id: string; anchor: string; relpath: string; label: string; color: string;
  crop: number[] | null; size: ImageSize; region: number[];
  kind: 'match' | 'panel'; flipDirection?: FlipDirection;
  /** The item side (panel index) and, for a clone, the region index. */
  side: number; index: number;
};
const rect = (v: unknown): v is Box => isRect(v, { nonNegative: true });

/** A native image frame must match one graphic, not just its figure number.
 * In particular a PDF crop cannot inherit XML coordinates from a caption, and
 * a publisher rendition cannot inherit a PMC crop's coordinates by figure ID.
 */
function graphicFor(panel: Panel, figures: XmlFigure[]) {
  // Only the panel's OWN source (the figure a crop was cut from, else its
  // image) may match by path, which is narrower than `panelFigure`'s
  // either-path rule: a figure number is not an identity here.
  const source = panel.crop_box ? panel.parent_image : panel.image;
  const native = nativeSource(panel.uid);
  const nativePath = panelSourcePaths(panel).find(p => native && p === `${native.folder}/${native.file}`);
  const matches = figures.flatMap(f => f.graphics.filter(g => {
    if (!g.relpath) return false;
    if (source && source === g.relpath) return true;
    if (!native) return false;
    const { file } = native;
    if (nativePath && g.relpath === nativePath) return true;
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
  const crop = (box.crop ?? wholeCrop(figureSize)) as Crop;
  if (!rect(crop)) return null;
  const [, , r1, c1] = crop;
  if (r1 > h || c1 > w) return null;
  const [x0, y0, x1, y1] = box.region;
  if (x1 > box.size[0] || y1 > box.size[1]) return null;
  return [...cropToParent([x0, y0], box.size, crop), ...cropToParent([x1, y1], box.size, crop)];
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
    const regions: unknown[] = matchRegions(ms, side, clone).map(r => r.bbox);
    const boxes: XmlImageBox[] = [];
    regions.forEach((region, i) => {
      if (!size || !rect(region) || region[2] > size[0] || region[3] > size[1]) return;
      const unmirrored = unmirror(region, side, size, ms.flip === true, clone);
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
