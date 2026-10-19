import { paneDocument, type Item } from "../app/images/lib.ts";
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

export type ReferenceMeta = {
  authors_list?: { given?: string | null; family?: string | null; full?: string | null }[] | null;
  authors?: string | null; title?: string | null; journal?: string | null;
  volume?: string | number | null; issue?: string | number | null; pages?: string | null;
  year?: string | number | null;
};

const MAX_AUTHORS = 20;
const initials = (given: string) => given.split(/\s+/).filter(Boolean)
  .map(t => t.split("-").map(p => p.replace(/\.$/, "")).filter(Boolean).map(p => `${p[0].toUpperCase()}.`).join("-"))
  .join(" ");
const trimStop = (s: string) => s.trim().replace(/[.\s]+$/, "");

/** A run of reference text; the journal name is the italic one. */
export type Run = { text: string; italic?: boolean };

/** One reference line: `Chetty, C., Dontula, R., & Lakka, S. S. (2011).
 * Title. *Journal*, 417(2), 874-879.` No DOI -- the figure is for readers,
 * and the DOI is on every other surface. Missing pieces are omitted, never
 * printed as "None"; returns [] when there is nothing but a DOI to say. */
export function referenceRuns(meta: ReferenceMeta | null | undefined): Run[] {
  if (!meta) return [];
  let names = (meta.authors_list || []).map(a => {
    const family = (a.family || "").trim(), given = (a.given || "").trim();
    return family ? (given ? `${family}, ${initials(given)}` : family) : (a.full || "").trim();
  }).filter(Boolean);
  if (!names.length && meta.authors) {
    names = meta.authors.split(";").map(n => n.trim()).filter(Boolean).map(n => {
      const parts = n.split(/\s+/);
      return parts.length > 1 ? `${parts[parts.length - 1]}, ${initials(parts.slice(0, -1).join(" "))}` : n;
    });
  }
  const authors = names.length > MAX_AUTHORS
    ? `${names.slice(0, MAX_AUTHORS - 1).join(", ")}, ... ${names[names.length - 1]}`
    : names.length > 1 ? `${names.slice(0, -1).join(", ")}, & ${names[names.length - 1]}` : names[0] || "";
  const year = meta.year == null || meta.year === "" ? "" : String(meta.year);
  const title = trimStop(meta.title || "");
  const journal = trimStop(meta.journal || "");
  const volume = String(meta.volume ?? "").trim(), issue = String(meta.issue ?? "").trim();
  const rest = [volume ? `${volume}${issue ? `(${issue})` : ""}` : issue ? `(${issue})` : "",
    (meta.pages || "").trim().replace(/-/g, "–")].filter(Boolean).join(", ");
  if (!title && !journal && !rest) return [];
  const lead = [authors && `${trimStop(authors)}.`, year && `(${year}).`, title && `${title}.`].filter(Boolean).join(" ");
  const runs: Run[] = [];
  if (lead) runs.push({ text: journal || rest ? `${lead} ` : lead });
  if (journal) runs.push({ text: journal, italic: true });
  if (journal || rest) runs.push({ text: `${journal && rest ? ", " : ""}${rest}.` });
  return runs;
}

export function formatReference(meta: ReferenceMeta | null | undefined): string {
  return referenceRuns(meta).map(r => r.text).join("");
}

/** Greedy word wrap of styled runs against a width measure (canvas
 * `measureText` in the page, a character count in tests). A word may change
 * style midway ("*Cancer*,"); a single overlong word keeps its line. Each
 * line comes back as runs with adjacent same-style pieces merged. */
export function wrapRuns(runs: Run[], width: number, measure: (s: string, italic: boolean) => number): Run[][] {
  const words: Run[][] = [];
  let word: Run[] = [];
  for (const run of runs) for (const piece of run.text.split(/(\s+)/)) {
    if (!piece) continue;
    if (/^\s+$/.test(piece)) { if (word.length) words.push(word); word = []; }
    else word.push({ text: piece, italic: !!run.italic });
  }
  if (word.length) words.push(word);
  const push = (line: Run[], piece: Run) => {
    const last = line[line.length - 1];
    if (last && !!last.italic === !!piece.italic) last.text += piece.text; else line.push({ ...piece });
  };
  const size = (line: Run[]) => line.reduce((s, r) => s + measure(r.text, !!r.italic), 0);
  const lines: Run[][] = [];
  let line: Run[] = [];
  for (const w of words) {
    const next = line.map(r => ({ ...r }));
    if (next.length) push(next, { text: " ", italic: !!next[next.length - 1].italic && !!w[0].italic });
    w.forEach(r => push(next, r));
    if (line.length && size(next) > width) {
      lines.push(line); line = [];
      w.forEach(r => push(line, r));
    } else line = next;
  }
  if (line.length) lines.push(line);
  return lines;
}

export function wrapText(text: string, width: number, measure: (s: string) => number): string[] {
  return wrapRuns([{ text }], width, s => measure(s)).map(l => l.map(r => r.text).join(""));
}

/** An axis-aligned rectangle in image pixels, corners in any order. */
export type PixelRect = { x0: number; y0: number; x1: number; y1: number };

/** Corners ordered, rounded and clamped to a `w` x `h` image; null when
 * nothing of it is left. */
export function normaliseRect(r: PixelRect, w: number, h: number): PixelRect | null {
  const x0 = Math.max(0, Math.round(Math.min(r.x0, r.x1))), x1 = Math.min(w, Math.round(Math.max(r.x0, r.x1)));
  const y0 = Math.max(0, Math.round(Math.min(r.y0, r.y1))), y1 = Math.min(h, Math.round(Math.max(r.y0, r.y1)));
  return x1 > x0 && y1 > y0 ? { x0, y0, x1, y1 } : null;
}

/** The area an edit occupies: the image, grown to hold a piece moved past
 * its edges. Image coordinates, so x0/y0 are <= 0. */
export function stageBounds(w: number, h: number, piece?: { x: number; y: number; w: number; h: number } | null): PixelRect {
  if (!piece) return { x0: 0, y0: 0, x1: w, y1: h };
  return { x0: Math.min(0, piece.x), y0: Math.min(0, piece.y),
    x1: Math.max(w, piece.x + piece.w), y1: Math.max(h, piece.y + piece.h) };
}

/** The credit line's type size and band height for an image `width` wide:
 * about the reference lines' size on a typical figure, never illegible on a
 * small crop or shouting on a wide one. */
export function brandMetrics(width: number): { font: number; band: number; pad: number } {
  const font = Math.round(Math.min(56, Math.max(18, width * 0.014)));
  return { font, band: Math.round(font * 2.4), pad: Math.round(font * 0.9) };
}

/** Which edges of a selection a pointer grabs: any of l/r/t/b (two at a
 * corner), "inside" to move the whole box, or null. `tol` is the grab
 * distance in image pixels. Edges win over the interior near the border. */
export type Grab = { l?: boolean; r?: boolean; t?: boolean; b?: boolean } | "inside" | null;
export function grabSelection(sel: PixelRect, p: { x: number; y: number }, tol: number): Grab {
  const ct = tol * 1.5; // corners are the natural place to resize from: a bigger target
  if (p.x < sel.x0 - ct || p.x > sel.x1 + ct || p.y < sel.y0 - ct || p.y > sel.y1 + ct) return null;
  // Inside a small box the grab band shrinks, so its middle can still be moved.
  const near = (v: number, edge: number, outward: 1 | -1, t: number, span: number) =>
    (v - edge) * outward >= 0 ? Math.abs(v - edge) <= t : Math.abs(v - edge) <= Math.min(t, span / 4);
  const w = sel.x1 - sel.x0, h = sel.y1 - sel.y0;
  const cl = near(p.x, sel.x0, -1, ct, w), cr = !cl && near(p.x, sel.x1, 1, ct, w);
  const cu = near(p.y, sel.y0, -1, ct, h), cd = !cu && near(p.y, sel.y1, 1, ct, h);
  if ((cl || cr) && (cu || cd)) return { l: cl, r: cr, t: cu, b: cd };
  const l = near(p.x, sel.x0, -1, tol, w), r = !l && near(p.x, sel.x1, 1, tol, w);
  const t = near(p.y, sel.y0, -1, tol, h), b = !t && near(p.y, sel.y1, 1, tol, h);
  const inX = p.x >= sel.x0 - tol && p.x <= sel.x1 + tol, inY = p.y >= sel.y0 - tol && p.y <= sel.y1 + tol;
  if ((l || r) && inY) return { l, r, t: false, b: false };
  if ((t || b) && inX) return { l: false, r: false, t, b };
  return p.x > sel.x0 && p.x < sel.x1 && p.y > sel.y0 && p.y < sel.y1 ? "inside" : null;
}

/** The CSS cursor for a grab. */
export function grabCursor(g: Grab): string {
  if (!g) return "crosshair";
  if (g === "inside") return "move";
  const ns = g.t ? "n" : g.b ? "s" : "", ew = g.l ? "w" : g.r ? "e" : "";
  return `${ns}${ew}-resize`;
}

/** `start` resized by dragging the grabbed edges by (dx, dy), the opposite
 * edges held still. A corner keeps the aspect ratio (whichever axis moved
 * further sets the scale); an edge handle stretches its one axis. Never
 * flips and never shrinks below `min` pixels a side. */
export function scaleRect(start: PixelRect, g: Exclude<Grab, null | "inside">, dx: number, dy: number, min = 8): PixelRect {
  const w0 = start.x1 - start.x0, h0 = start.y1 - start.y0;
  let w = g.l ? w0 - dx : g.r ? w0 + dx : w0;
  let h = g.t ? h0 - dy : g.b ? h0 + dy : h0;
  if ((g.l || g.r) && (g.t || g.b)) {
    const sx = w / w0, sy = h / h0;
    const s = Math.max(Math.abs(sx - 1) >= Math.abs(sy - 1) ? sx : sy, min / Math.min(w0, h0));
    w = w0 * s; h = h0 * s;
  }
  w = Math.max(min, w); h = Math.max(min, h);
  const x0 = g.l ? start.x1 - w : start.x0, y0 = g.t ? start.y1 - h : start.y0;
  return { x0, y0, x1: x0 + w, y1: y0 + h };
}
