import { mediaUrl } from "@/app/images/lib";
import { DUPLICATION_COLORS } from "@/lib/imagePdfBoxes";
import { projectXmlImageBox, type ImageSize } from "@/lib/imageXmlBoxes";
import type { ImageSummaryGroup } from "@/lib/summaryGroups";
import { TARGET_PX, type FigureBox, type RenderedFigure } from "./RenderedFigure";

// White border round a native figure image, so an edge box and its label stay in frame.
const IMAGE_MARGIN_PX = 32;

/** The whole native figure, scaled so its longer side is TARGET_PX like a
 *  PDF crop, with each box projected into the image's own pixel frame. */
export async function renderImageGroup(project: string, group: ImageSummaryGroup): Promise<RenderedFigure> {
  const image = new Image();
  image.src = mediaUrl(project, group.paperDir, group.imagePath);
  try { await image.decode(); }
  catch { throw new Error(`The figure image ${group.imagePath} could not be loaded.`); }
  const size: ImageSize = [image.naturalWidth, image.naturalHeight];
  const scale = TARGET_PX / Math.max(...size);
  const out = document.createElement("canvas");
  out.width = Math.round(size[0] * scale) + 2 * IMAGE_MARGIN_PX;
  out.height = Math.round(size[1] * scale) + 2 * IMAGE_MARGIN_PX;
  const ctx = out.getContext("2d")!;
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, out.width, out.height);
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(image, IMAGE_MARGIN_PX, IMAGE_MARGIN_PX, size[0] * scale, size[1] * scale);
  const boxes: FigureBox[] = [];
  group.boxes.forEach(box => {
    const r = projectXmlImageBox(box, size);
    if (!r) return;
    // A match box gets the PDF figure's colours and region label; a panel
    // locator (match not localized) keeps its own colour, dashed as in the pane.
    const clone = group.clone && box.kind === "match";
    boxes.push({ points: ([[r[0], r[1]], [r[2], r[1]], [r[2], r[3]], [r[0], r[3]]] as [number, number][])
      .map(([x, y]) => [IMAGE_MARGIN_PX + x * scale, IMAGE_MARGIN_PX + y * scale]),
      limit: [IMAGE_MARGIN_PX, IMAGE_MARGIN_PX, out.width - IMAGE_MARGIN_PX, out.height - IMAGE_MARGIN_PX],
      dashed: box.kind === "panel",
      color: box.kind === "panel" ? box.color : DUPLICATION_COLORS[clone ? box.index % DUPLICATION_COLORS.length : 0],
      flipDirection: box.flipDirection, regionLabel: clone ? (box.index === 0 ? "A" : "B") : undefined });
  });
  return { canvas: out, boxes };
}
