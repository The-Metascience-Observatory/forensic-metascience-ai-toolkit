import { loadPdfjs } from "@/lib/pdfjs";
import { pdfImageRects } from "@/lib/summaryPdfGeometry";
import { mediaUrl } from "@/app/images/lib";
import { adjoiningFigureRect, FIGURE_MARGIN_PT, type PdfSummaryGroup } from "@/lib/summaryGroups";
import { MAX_CANVAS_PX, TARGET_PX, type RenderedFigure } from "./RenderedFigure";

/** One PDF summary group rendered by pdf.js: the figure's page cropped to
 *  the figure (grown to the images it adjoins) at TARGET_PX, with the
 *  duplication boxes projected into the crop's pixels. */
export async function renderPdfGroup(project: string, group: PdfSummaryGroup): Promise<RenderedFigure> {
  const pdfjs = await loadPdfjs();
  const pdf = await pdfjs.getDocument({ url: mediaUrl(project, group.paperDir, group.documentPath), withCredentials: false }).promise;
  try {
    const page = await pdf.getPage(group.page);
    const base = page.getViewport({ scale: 1 });
    const frame = group.sourceRect || group.rect;
    let [x0, y0, x1, y1] = frame[2] > frame[0] && frame[3] > frame[1]
      ? frame : [0, 0, base.width, base.height];
    if (group.framed) {
      const images = pdfImageRects(await page.getOperatorList(), pdfjs.OPS, base);
      // Grow each image inside the saved frame independently (a page may
      // hold multiple figures). Add white margin outside the page crop below.
      for (const image of images) {
        if (image[0] < frame[0] - 0.5 || image[1] < frame[1] - 0.5
            || image[2] > frame[2] + 0.5 || image[3] > frame[3] + 0.5) continue;
        const r = adjoiningFigureRect(image, images);
        x0 = Math.min(x0, r[0]); y0 = Math.min(y0, r[1]);
        x1 = Math.max(x1, r[2]); y1 = Math.max(y1, r[3]);
      }
      x0 = Math.max(0, x0); y0 = Math.max(0, y0);
      x1 = Math.min(base.width, x1); y1 = Math.min(base.height, y1);
    }
    const scale = Math.min(TARGET_PX / Math.max(x1 - x0, y1 - y0),
      MAX_CANVAS_PX / Math.max(base.width, base.height));
    const viewport = page.getViewport({ scale });
    const full = document.createElement("canvas");
    full.width = Math.ceil(viewport.width); full.height = Math.ceil(viewport.height);
    await page.render({ canvasContext: full.getContext("2d")!, viewport }).promise;
    const out = document.createElement("canvas");
    const margin = group.framed ? Math.round(FIGURE_MARGIN_PT * scale) : 0;
    const width = Math.round((x1 - x0) * scale), height = Math.round((y1 - y0) * scale);
    out.width = width + 2 * margin; out.height = height + 2 * margin;
    const ctx = out.getContext("2d")!;
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, out.width, out.height);
    ctx.drawImage(full, x0 * scale, y0 * scale, width, height, margin, margin, width, height);
    full.width = 0; full.height = 0;
    return { canvas: out, boxes: group.boxes.map(box => ({ ...box,
      points: box.points.map(([x, y]) => [margin + (x - x0) * scale, margin + (y - y0) * scale]),
      limit: [margin, margin, margin + width, margin + height] })) };
  } finally { void pdf.destroy(); }
}
