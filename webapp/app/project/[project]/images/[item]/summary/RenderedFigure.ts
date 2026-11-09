/** The rendered pieces of a summary figure and the resolution they share:
 *  one canvas per summary group (`PdfGroupRenderer`, `ImageGroupRenderer`)
 *  with its duplication boxes in that canvas's pixels, composed by
 *  `ComposeFigure` and annotated by `CanvasDraw`. */
import type { ImagePdfBox } from "@/lib/imagePdfBoxes";

// Output resolution: the longer side of each figure crop, in pixels.
export const TARGET_PX = 1600;
export const MAX_CANVAS_PX = 12000;

export type DrawnBox = Pick<ImagePdfBox, "points" | "color" | "flipDirection" | "regionLabel">;
export type FigureBox = DrawnBox & { dashed?: boolean; limit: [number, number, number, number] };
export type RenderedFigure = { canvas: HTMLCanvasElement; boxes: FigureBox[] };
