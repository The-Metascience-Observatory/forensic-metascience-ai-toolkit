/** One canvas from the summary groups: each group rendered (PDF or native
 *  image), laid out side by side or stacked, under its reference and label. */
import type { Item } from "@/app/images/lib";
import { chooseLayout, isCrossPaper, type SummaryGroup } from "@/lib/summaryGroups";
import { wrapRuns, type Run } from "@/lib/citation";
import { renderPdfGroup } from "./PdfGroupRenderer";
import { renderImageGroup } from "./ImageGroupRenderer";
import { fetchReferences } from "./useFigureData";
import { TARGET_PX, type FigureBox, type RenderedFigure } from "./RenderedFigure";

const GAP = 24, PAD = 16;
// Header text scales with the crop so it stays legible when the PNG is shrunk.
const FONT = Math.round(TARGET_PX * 0.02), REF_FONT = Math.round(FONT * 0.8);
const LINE = 1.3, HEADER_GAP = Math.round(FONT * 0.4);

function renderGroup(project: string, group: SummaryGroup): Promise<RenderedFigure> {
  return group.kind === "pdf" ? renderPdfGroup(project, group) : renderImageGroup(project, group);
}

function label(group: SummaryGroup): string {
  const sides = group.sides.map(s => "AB"[s]).join("+");
  const figure = group.figureLabels.join(", ") || "Figure";
  if (group.kind === "image") return `${sides} · ${figure}`;
  return `${sides} · ${figure} · p. ${group.page}${group.framed ? "" : " (whole page)"}`
    + (group.boxes.length ? "" : " · no box to draw");
}

const refFont = (italic: boolean) => `${italic ? "italic " : ""}${REF_FONT}px sans-serif`;
function measureRef(ctx: CanvasRenderingContext2D, text: string, italic: boolean): number {
  ctx.font = refFont(italic);
  return ctx.measureText(text).width;
}

type Header = { ref: Run[][]; label: string; height: number };
function header(ctx: CanvasRenderingContext2D, reference: Run[], group: SummaryGroup, width: number): Header {
  const ref = wrapRuns(reference, width, (t, italic) => measureRef(ctx, t, italic));
  return { ref, label: label(group), height: Math.round(ref.length * REF_FONT * LINE + FONT * LINE + HEADER_GAP) };
}

export async function compose(project: string, item: Item, groups: SummaryGroup[]): Promise<RenderedFigure & { unreferenced: number }> {
  const dirs = [...new Set(groups.map(g => g.paperDir))];
  const [rendered, references] = await Promise.all([
    Promise.all(groups.map(g => renderGroup(project, g))),
    isCrossPaper(item) ? fetchReferences(project, item, dirs) : Promise.resolve({} as Record<string, Run[]>)]);
  const crops = rendered.map(r => r.canvas);
  const boxes: FigureBox[] = [];
  const unreferenced = isCrossPaper(item) ? dirs.filter(d => !references[d]?.length).length : 0;
  const out = document.createElement("canvas");
  const ctx = out.getContext("2d")!;
  const headerFor = (i: number, width: number) => header(ctx, references[groups[i].paperDir] || [], groups[i], width);
  const estimate = Math.max(...crops.map((c, i) => headerFor(i, c.width).height));
  const layout = chooseLayout(crops.map(c => [c.width, c.height]), estimate);
  // Equal heights side by side, equal widths stacked.
  const common = layout === "horizontal" ? Math.max(...crops.map(c => c.height)) : Math.max(...crops.map(c => c.width));
  const sized = crops.map(c => layout === "horizontal"
    ? [c.width * common / c.height, common] : [common, c.height * common / c.width]);
  const headers = sized.map(([w], i) => headerFor(i, w));
  const band = Math.max(...headers.map(h => h.height));
  out.width = Math.round(layout === "horizontal"
    ? sized.reduce((s, [w]) => s + w, 0) + GAP * (crops.length - 1) + PAD * 2 : common + PAD * 2);
  out.height = Math.round(layout === "horizontal"
    ? common + band + PAD * 2
    : sized.reduce((s, [, h], i) => s + h + headers[i].height, 0) + GAP * (crops.length - 1) + PAD * 2);
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, out.width, out.height);
  ctx.textBaseline = "top";
  let x = PAD, y = PAD;
  crops.forEach((crop, i) => {
    const [w, h] = sized[i];
    const head = headers[i];
    // Side by side, the images share a top edge; each header sits above its own.
    const top = layout === "horizontal" ? y + band - head.height : y;
    ctx.fillStyle = "#111";
    head.ref.forEach((line, k) => {
      let at = x;
      for (const run of line) {
        const advance = measureRef(ctx, run.text, !!run.italic); // also sets the font
        ctx.fillText(run.text, at, top + k * REF_FONT * LINE);
        at += advance;
      }
    });
    ctx.font = `bold ${FONT}px sans-serif`;
    ctx.fillText(head.label, x, top + head.ref.length * REF_FONT * LINE, w);
    const imageTop = top + head.height;
    ctx.drawImage(crop, x, imageTop, w, h);
    const sx = w / crop.width, sy = h / crop.height;
    boxes.push(...rendered[i].boxes.map(box => ({ ...box,
      points: box.points.map(([bx, by]) => [x + bx * sx, imageTop + by * sy] as [number, number]),
      limit: [x + box.limit[0] * sx, imageTop + box.limit[1] * sy,
        x + box.limit[2] * sx, imageTop + box.limit[3] * sy] as [number, number, number, number] })));

    ctx.strokeStyle = "#999"; ctx.lineWidth = 1; ctx.strokeRect(x + .5, imageTop + .5, w - 1, h - 1);
    if (layout === "horizontal") x += w + GAP; else y = imageTop + h + GAP;
    crop.width = 0; crop.height = 0;
  });
  return { canvas: out, boxes, unreferenced };
}
