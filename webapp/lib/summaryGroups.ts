/** Which figure regions a summary figure shows: the PDF groups (one per
 *  page and figure the matched panels sit on), the native-image groups, the
 *  figure rectangle a crop sits in, and the layout choice. Pure. Split out
 *  of `summaryFigure.ts` with the crop editor (`cropEditor.ts`) and the
 *  reference formatter (`citation.ts`). */
import { paneDocument } from "./paneDocument.ts";
import type { Item } from "./types/images.ts";
import { projectImagePolygon, type ImagePdfBox } from "./imagePdfBoxes.ts";
import { imageXmlBoxes, type ImageSize, type XmlImageBox } from "./imageXmlBoxes.ts";
import { canReadXml, type XmlFigure } from "./xmlFigures.ts";

/** One PDF region of a summary figure: the whole figure (every placement of
 * the finding's panels on that page) with the duplication boxes it holds.
 * Rectangles are displayed-PDF points, top-left origin, like `ImagePdfBox`. */
export type PdfSummaryGroup = {
  kind: "pdf";
  paperDir: string; documentPath: string; page: number;
  sides: number[]; figureLabels: string[];
  rect: [number, number, number, number];
  /** False when no exact placement framed the figure and the whole page stands in. */
  framed: boolean;
  /** Figure and match bounds without surrounding page text. */
  sourceRect?: [number, number, number, number];
  boxes: ImagePdfBox[];
};

/** A figure that was never printed on a PDF page -- a PMC or publisher
 * render of a paper with no PDF -- shown as its whole native image, with the
 * same boxes the XML paper pane draws (`imageXmlBoxes`, native pixels). */
export type ImageSummaryGroup = {
  kind: "image";
  paperDir: string; imagePath: string;
  sides: number[]; figureLabels: string[];
  boxes: XmlImageBox[];
  /** An intra-panel clone: its boxes are regions A and B of one panel. */
  clone: boolean;
};

export type SummaryGroup = PdfSummaryGroup | ImageSummaryGroup;

export const FIGURE_MARGIN_PT = 12;

type Rect = [number, number, number, number];
const union = (a: Rect | null, b: Rect): Rect =>
  a ? [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])] : b;
const bounds = (points: [number, number][]): Rect => [
  Math.min(...points.map(p => p[0])), Math.min(...points.map(p => p[1])),
  Math.max(...points.map(p => p[0])), Math.max(...points.map(p => p[1]))];

/** Include adjoining strips of a PDF image. Publishers sometimes split one
 * figure into full-width bands; a panel's parent is only one of those bands.
 * Require matching full edges and actual contact, never nearby page content. */
export function adjoiningFigureRect(seed: Rect, images: Rect[], tolerance = 0.5): Rect {
  let result = [...seed] as Rect;
  let changed = true;
  while (changed) {
    changed = false;
    for (const r of images) {
      if (r.some(v => !Number.isFinite(v)) || r[2] <= r[0] || r[3] <= r[1]) continue;
      const sameX = Math.abs(r[0] - result[0]) <= tolerance && Math.abs(r[2] - result[2]) <= tolerance;
      const sameY = Math.abs(r[1] - result[1]) <= tolerance && Math.abs(r[3] - result[3]) <= tolerance;
      const touchesY = Math.abs(r[1] - result[3]) <= tolerance || Math.abs(r[3] - result[1]) <= tolerance;
      const touchesX = Math.abs(r[0] - result[2]) <= tolerance || Math.abs(r[2] - result[0]) <= tolerance;
      if ((sameX && touchesY) || (sameY && touchesX)) {
        const next = union(result, r);
        if (next.some((v, i) => v !== result[i])) { result = next; changed = true; }
      }
    }
  }
  return result;
}

/** Display-only enlargement around the polygon's centre, clipped to the
 * source figure. This does not estimate or alter the detected match extent. */
export function expandFigureBox(points: [number, number][], percent: number, limit: Rect): [number, number][] {
  if (!points.length) return [];
  const cx = points.reduce((s, p) => s + p[0], 0) / points.length;
  const cy = points.reduce((s, p) => s + p[1], 0) / points.length;
  const k = Number.isFinite(percent) ? Math.max(1, Math.min(10, percent / 100)) : 1;
  if (k === 1) return points.map(p => [...p]);
  return points.map(([x, y]) => [Math.max(limit[0], Math.min(limit[2], cx + (x - cx) * k)),
    Math.max(limit[1], Math.min(limit[3], cy + (y - cy) * k))]);
}

/** The embedded image a panel was cropped from -- the printed figure -- on
 * its page. Null unless the placement is exact enough to paint boxes. */
export function figureRect(panel: Item["panels"][number], pl: Item["panels"][number]["placements"][number]): Rect | null {
  const size = pl.parent_size;
  if (!Array.isArray(size) || size.length !== 2) return null;
  const [w, h] = size;
  const points = projectImagePolygon({ ...panel, crop_box: null }, { ...pl, bbox_kind: "stream_exact" },
    [w, h], [[0, 0], [w, 0], [w, h], [0, h]]);
  return points ? bounds(points) : null;
}

/** Group the finding's PDF placements by document page. Both sides on one
 * page (a within-figure duplication, or two figures printed together) make
 * one crop that covers both, never two copies of the same page. */
export function summaryGroups(item: Item, boxes: ImagePdfBox[]): PdfSummaryGroup[] {
  const groups = new Map<string, PdfSummaryGroup & { figure: Rect | null; pageSize: number[] | null }>();
  const clone = item.detector_kind === "intra_panel_clone";
  item.panels.forEach((panel, side) => {
    if (clone && side > 0) return;
    const paper = (item.papers || [item.paper]).find(p => p?.dir === panel.paper_dir);
    const document = paneDocument(panel, paper);
    if (document.kind !== "pdf") return;
    panel.placements.forEach(pl => {
      if (!Number.isInteger(pl.page) || pl.page < 1) return;
      const sameDocument = !pl.document_path || pl.document_path === document.path
        || (pl.document_id && pl.document_id === panel.document?.id);
      if (!sameDocument) return;
      const key = `${panel.paper_dir}\n${document.path}\n${pl.page}`;
      const group = groups.get(key) || { kind: "pdf" as const, paperDir: panel.paper_dir, documentPath: document.path, page: pl.page,
        sides: [], figureLabels: [], rect: [0, 0, 0, 0], framed: false, boxes: [], figure: null, pageSize: null };
      if (!group.sides.includes(side)) group.sides.push(side);
      const label = panel.figure_label || pl.figure_label;
      if (label && !group.figureLabels.includes(label)) group.figureLabels.push(label);
      const rect = figureRect(panel, pl);
      if (rect) group.figure = union(group.figure, rect);
      if (Array.isArray(pl.page_size) && pl.page_size.length === 2) group.pageSize = pl.page_size;
      groups.set(key, group);
    });
  });
  return [...groups.values()].map(({ figure, pageSize, ...group }) => {
    const onPage = boxes.filter(b => b.paperDir === group.paperDir && b.page === group.page
      && (b.documentPath === group.documentPath || group.sides.some(s => item.panels[s]?.placements
        .some(pl => pl.document_path === b.documentPath))));
    // A box always stays in frame, even one reaching past the parent image.
    let rect = figure;
    for (const box of onPage) rect = union(rect, bounds(box.points));
    const sourceRect = rect ? [...rect] as Rect : undefined;
    if (rect) {
      rect = [rect[0] - FIGURE_MARGIN_PT, rect[1] - FIGURE_MARGIN_PT, rect[2] + FIGURE_MARGIN_PT, rect[3] + FIGURE_MARGIN_PT];
      if (pageSize) rect = [Math.max(0, rect[0]), Math.max(0, rect[1]),
        Math.min(pageSize[0], rect[2]), Math.min(pageSize[1], rect[3])];
    }
    return { ...group, sides: group.sides.sort(), boxes: onPage, framed: !!figure, sourceRect, rect: rect || [0, 0, 0, 0] };
  });
}

/** The sides no PDF group covers whose figure the XML paper pane can show
 * instead: the same test the item page uses to open that pane (an XML-readable
 * source, and no PDF for the paper). Their figure is resolved by
 * `nativeSummaryGroups` once the paper's XML figure list is fetched. */
export function nativeSides(item: Item, pdfGroups: PdfSummaryGroup[]): number[] {
  const clone = item.detector_kind === "intra_panel_clone";
  const covered = new Set(pdfGroups.flatMap(g => g.sides));
  return item.panels.flatMap((panel, side) => {
    if ((clone && side > 0) || covered.has(side)) return [];
    const paper = (item.papers || [item.paper]).find(p => p?.dir === panel.paper_dir);
    return canReadXml(panel) && !paper?.pdf ? [side] : [];
  });
}

/** One group per native figure image holding any of `sides`' boxes. Both
 * sides in one image (a within-figure duplication) make one figure, as on a
 * PDF page. A side whose figure cannot be linked uniquely contributes nothing:
 * a box is only ever drawn on the image whose pixel frame it was measured in. */
export function nativeSummaryGroups(item: Item, sides: number[], figures: Record<string, XmlFigure[]>,
                                    sizes: (ImageSize | null)[] = []): ImageSummaryGroup[] {
  const groups = new Map<string, ImageSummaryGroup>();
  for (const dir of new Set(sides.map(s => item.panels[s]?.paper_dir).filter(Boolean))) {
    for (const box of imageXmlBoxes(item, dir, figures[dir] || [], sizes)) {
      if (!sides.includes(box.side)) continue;
      const key = `${dir}\n${box.relpath}`;
      const group = groups.get(key)
        || { kind: "image" as const, paperDir: dir, imagePath: box.relpath, sides: [], figureLabels: [], boxes: [],
          clone: item.detector_kind === "intra_panel_clone" };
      if (!group.sides.includes(box.side)) group.sides.push(box.side);
      const label = item.panels[box.side]?.figure_label || figures[dir]?.find(f => f.anchor === box.anchor)?.label;
      if (label && !group.figureLabels.includes(label)) group.figureLabels.push(label);
      group.boxes.push(box);
      groups.set(key, group);
    }
  }
  return [...groups.values()].map(g => ({ ...g, sides: g.sides.sort() }));
}

/** A finding whose panels come from more than one paper. Only these carry
 * reference lines: within one paper the reader already knows the source. */
export function isCrossPaper(item: Item): boolean {
  return new Set(item.panels.map(p => p.paper_dir).filter(Boolean)).size > 1;
}

/** Side by side (equal heights) or stacked (equal widths), whichever total
 * aspect ratio is nearer square. `extra` is the per-figure caption band. */
export function chooseLayout(sizes: [number, number][], extra = 0): "horizontal" | "vertical" {
  if (sizes.length < 2) return "horizontal";
  const H = Math.max(...sizes.map(s => s[1]));
  const horizontalW = sizes.reduce((sum, [w, h]) => sum + w * H / h, 0);
  const W = Math.max(...sizes.map(s => s[0]));
  const verticalH = sizes.reduce((sum, [w, h]) => sum + h * W / w + extra, 0);
  const off = (r: number) => Math.abs(Math.log(r));
  return off(horizontalW / (H + extra)) <= off(W / verticalH) ? "horizontal" : "vertical";
}
