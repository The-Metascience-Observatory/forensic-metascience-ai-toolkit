"use client";

import { createPortal } from "react-dom";
import { pdfImageRects } from "@/lib/summaryPdfGeometry";
import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { mediaUrl, type Item } from "@/app/images/lib";
import { drawFlipArrow } from "@/lib/flipArrow";
import { DUPLICATION_COLORS, type ImagePdfBox } from "@/lib/imagePdfBoxes";
import { projectXmlImageBox, type ImageSize } from "@/lib/imageXmlBoxes";
import type { XmlFigure } from "@/lib/xmlFigures";
import { isoDate, normalisePubpeerUrl } from "@/lib/websiteFinding";
import { pubpeerLink } from "@/lib/citation";

/** One PubPeer link per paper of the finding (its page when recorded, else
 *  a DOI search), labelled A/B on a cross-paper item. Same rule as the page. */
function pubpeerLinks(item: Item): { label: string; href: string; title: string }[] {
  const papers = item.papers || [item.paper];
  const dirs = [...new Set(item.panels.map(p => p.paper_dir).filter(Boolean))];
  return dirs.flatMap((dir, i) => {
    const paper = papers.find(p => p?.dir === dir);
    const link = pubpeerLink(paper?.doi || (dir.includes("--") ? dir.replace("--", "/") : null), paper?.pubpeer_url, paper?.title);
    if (!link) return [];
    return [{ href: link.href, label: dirs.length > 1 ? `PubPeer ${"AB"[i] || i + 1}` : "PubPeer",
      title: `${link.label}: ${paper?.title || dir}` }];
  });
}
import { adjoiningFigureRect, expandFigureBox, FIGURE_MARGIN_PT, brandMetrics, chooseLayout, grabCursor, grabSelection, isCrossPaper, nativeSides, nativeSummaryGroups, normaliseRect, referenceRuns, scaleRect, stageBounds, summaryGroups, wrapRuns,
  type Grab, type ImageSummaryGroup, type PdfSummaryGroup, type PixelRect, type ReferenceMeta, type Run, type SummaryGroup } from "@/lib/summaryFigure";

// Output resolution: the longer side of each figure crop, in pixels.
const TARGET_PX = 1600;
const MAX_CANVAS_PX = 12000;
const GAP = 24, PAD = 16;
// Header text scales with the crop so it stays legible when the PNG is shrunk.
const FONT = Math.round(TARGET_PX * 0.02), REF_FONT = Math.round(FONT * 0.8);
const LINE = 1.3, HEADER_GAP = Math.round(FONT * 0.4);
// White border round a native figure image, so an edge box and its label stay in frame.
const IMAGE_MARGIN_PX = 32;

type FigureBox = DrawnBox & { dashed?: boolean; limit: [number, number, number, number] };
type RenderedFigure = { canvas: HTMLCanvasElement; boxes: FigureBox[] };

function renderGroup(project: string, group: SummaryGroup): Promise<RenderedFigure> {
  return group.kind === "pdf" ? renderPdfGroup(project, group) : renderImageGroup(project, group);
}

async function renderPdfGroup(project: string, group: PdfSummaryGroup): Promise<RenderedFigure> {
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
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

/** The whole native figure, scaled so its longer side is TARGET_PX like a
 *  PDF crop, with each box projected into the image's own pixel frame. */
async function renderImageGroup(project: string, group: ImageSummaryGroup): Promise<RenderedFigure> {
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

type DrawnBox = Pick<ImagePdfBox, "points" | "color" | "flipDirection" | "regionLabel">;
function drawBox(ctx: CanvasRenderingContext2D, box: DrawnBox, scale: number, dashed = false) {
  const px = 1 / scale;
  ctx.beginPath();
  box.points.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
  ctx.closePath();
  if (dashed) ctx.setLineDash([12 * px, 8 * px]);
  ctx.strokeStyle = "#111"; ctx.lineWidth = 6 * px; ctx.stroke();
  ctx.strokeStyle = box.color; ctx.lineWidth = 3.5 * px; ctx.stroke();
  ctx.setLineDash([]);
  drawFlipArrow(ctx, box.points, box.color, box.flipDirection, scale);
  if (box.regionLabel && box.points.length) {
    const anchor = box.points.reduce((best, p) => p[1] < best[1] ? p : best);
    ctx.font = `bold ${22 * px}px sans-serif`;
    ctx.lineWidth = 4 * px; ctx.strokeStyle = "#111"; ctx.fillStyle = box.color;
    ctx.strokeText(box.regionLabel, anchor[0], anchor[1] - 6 * px);
    ctx.fillText(box.regionLabel, anchor[0], anchor[1] - 6 * px);
  }
}

function label(group: SummaryGroup): string {
  const sides = group.sides.map(s => "AB"[s]).join("+");
  const figure = group.figureLabels.join(", ") || "Figure";
  if (group.kind === "image") return `${sides} · ${figure}`;
  return `${sides} · ${figure} · p. ${group.page}${group.framed ? "" : " (whole page)"}`
    + (group.boxes.length ? "" : " · no box to draw");
}

/** Each paper's XML figure list, from the same `source` read the XML paper
 *  pane makes: it names the native image file each figure was rendered from. */
async function fetchFigures(project: string, item: Item, dirs: string[]): Promise<Record<string, XmlFigure[]>> {
  return Object.fromEntries(await Promise.all(dirs.map(async dir => {
    const query = new URLSearchParams({ method: "source", project, dir, run: item.run_id, component: "image_forensics" });
    const response = await fetch(`/api/workbench?${query}`);
    const source = await response.json().catch(() => ({}));
    if (!response.ok || source.error) throw new Error(`The figure list for ${dir} could not be loaded: ${source.error || response.statusText}`);
    return [dir, (source.article?.figures || []) as XmlFigure[]];
  })));
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

/** The papers' full references, fetched (and cached beside each paper) by
 *  the workbench. A paper the APIs cannot describe falls back to what the
 *  item already carries; it is never labelled by its DOI. */
async function fetchReferences(project: string, item: Item, dirs: string[]): Promise<Record<string, Run[]>> {
  const fallback = (dir: string) => {
    const paper = (item.papers || [item.paper]).find(p => p?.dir === dir) as ReferenceMeta | undefined;
    return referenceRuns(paper);
  };
  let fetched: Record<string, { metadata?: ReferenceMeta }> = {};
  try {
    const response = await fetch("/api/images/reference", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ project, dirs }) });
    if (response.ok) fetched = (await response.json()).references || {};
  } catch { /* fall back below */ }
  return Object.fromEntries(dirs.map(d => {
    const runs = referenceRuns(fetched[d]?.metadata);
    return [d, runs.length ? runs : fallback(d)];
  }));
}

async function compose(project: string, item: Item, groups: SummaryGroup[]): Promise<RenderedFigure & { unreferenced: number }> {
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

/** Redraw annotations from clean pixels, so expanding a box leaves no old
 * outline behind and never stretches the scientific image. */
function annotateFigure(figure: RenderedFigure, percent: number): HTMLCanvasElement {
  const out = blank(figure.canvas.width, figure.canvas.height);
  const ctx = out.getContext("2d")!;
  ctx.drawImage(figure.canvas, 0, 0);
  if (percent <= 0) return out; // 0 = boxes removed
  for (const box of figure.boxes) drawBox(ctx, { ...box,
    points: box.dashed ? box.points : expandFigureBox(box.points, percent, box.limit) }, 1, box.dashed);
  return out;
}

const INK = "#111", GLOBE_INK = "#444", DIM = "#555";
const SLAB = `"Roboto Slab", Georgia, "Times New Roman", serif`;

/** The site's globe mark (public/assets/globe.svg: a circle crossed by two
 * ellipses on a 16-unit box), stroked straight onto the canvas. */
function drawGlobe(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number) {
  const k = r / 7.35;
  ctx.save();
  ctx.strokeStyle = GLOBE_INK; ctx.lineWidth = 0.9 * k; ctx.lineCap = "round";
  for (const [rx, ry] of [[7.35, 7.35], [3, 7.35], [7.35, 3]]) {
    ctx.beginPath(); ctx.ellipse(cx, cy, rx * k, ry * k, 0, 0, Math.PI * 2); ctx.stroke();
  }
  ctx.restore();
}

/** "found at [globe] The Metascience Observatory", right-aligned in a band
 * under the image -- a band, not an overlay, so it never covers a figure. */
function drawBrand(ctx: CanvasRenderingContext2D, width: number, top: number) {
  const { font, band, pad } = brandMetrics(width);
  const r = font * 0.62, gap = font * 0.45, mid = top + band / 2;
  ctx.save();
  ctx.textBaseline = "middle";
  ctx.font = `bold ${font}px ${SLAB}`;
  const name = "The Metascience Observatory";
  let x = width - pad - ctx.measureText(name).width;
  ctx.fillStyle = INK; ctx.fillText(name, x, mid);
  x -= gap + r;
  drawGlobe(ctx, x, mid, r);
  x -= r + gap;
  ctx.font = `${Math.round(font * 0.85)}px ${SLAB}`;
  ctx.fillStyle = DIM;
  ctx.fillText("found at", x - ctx.measureText("found at").width, mid);
  ctx.restore();
}

const blank = (w: number, h: number) => {
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(w)); c.height = Math.max(1, Math.round(h));
  const ctx = c.getContext("2d")!;
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, c.width, c.height);
  return c;
};

/** Lifted pixels (`canvas`) shown at x, y and scaled to w x h. */
type Piece = { canvas: HTMLCanvasElement; x: number; y: number; w: number; h: number };
const pieceRect = (p: Piece): PixelRect => ({ x0: p.x, y0: p.y, x1: p.x + p.w, y1: p.y + p.h });
/** A region lifted out of `base` (which now shows a white hole there) and
 * not yet put down. Nothing enters the history until it is placed. */
type Floating = { base: HTMLCanvasElement; piece: Piece };

function placePiece({ base, piece }: Floating): { canvas: HTMLCanvasElement; at: PixelRect } {
  const w = Math.max(1, Math.round(piece.w)), h = Math.max(1, Math.round(piece.h));
  const b = stageBounds(base.width, base.height, { x: piece.x, y: piece.y, w, h });
  const out = blank(b.x1 - b.x0, b.y1 - b.y0);
  const ctx = out.getContext("2d")!;
  ctx.drawImage(base, -b.x0, -b.y0);
  const x = Math.round(piece.x - b.x0), y = Math.round(piece.y - b.y0);
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(piece.canvas, x, y, w, h);
  return { canvas: out, at: { x0: x, y0: y, x1: x + w, y1: y + h } };
}

function flatten(content: HTMLCanvasElement, brand: boolean): HTMLCanvasElement {
  const band = brand ? brandMetrics(content.width).band : 0;
  const out = blank(content.width, content.height + band);
  const ctx = out.getContext("2d")!;
  ctx.drawImage(content, 0, 0);
  if (brand) drawBrand(ctx, content.width, content.height);
  return out;
}

const toBlob = (canvas: HTMLCanvasElement) => new Promise<Blob>((resolve, reject) =>
  canvas.toBlob(b => b ? resolve(b) : reject(new Error("PNG encoding failed")), "image/png"));

function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

type WebsiteResult = { id: string; website: string; files: string[]; page: string; embargoOverridden?: string };

/** "Add to website": the PubPeer link and comment for this finding, sent
 *  with the current summary figure to the Observatory website checkout. */
function AddToWebsite({ project, item, exportBlob, onClose }: {
  project: string; item: Item; exportBlob: () => Promise<Blob>; onClose: () => void;
}) {
  const dirs = [...new Set(item.panels.map(p => p.paper_dir).filter(Boolean))];
  const [dir, setDir] = useState(dirs[0] || "");
  const [url, setUrl] = useState("");
  const [summary, setSummary] = useState("");
  const [date, setDate] = useState(isoDate());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<WebsiteResult | null>(null);
  // Set when the server refuses because the corpus is under a selection embargo;
  // the override is then offered, for this one finding, as "submit anyway".
  const [embargo, setEmbargo] = useState<string | null>(null);
  const urlOk = !!normalisePubpeerUrl(url);
  const labels = [...new Set(item.panels.map(p => p.figure_label).filter(Boolean))].join(" and ");

  async function submit(override = false) {
    setBusy(true); setError(null);
    try {
      const form = new FormData();
      form.set("project", project); form.set("dir", dir);
      form.set("pubpeerUrl", url); form.set("summary", summary); form.set("submitted", date);
      form.set("alt", `Annotated ${labels || "figure"} with the matching regions outlined.`);
      form.set("image", await exportBlob(), "summary.png");
      if (override) form.set("embargoOverride", "submit-anyway");
      const response = await fetch("/api/images/website", { method: "POST", body: form });
      const body = await response.json().catch(() => ({}));
      if (response.status === 403 && body.code === "embargo") { setEmbargo(String(body.marker || "")); return; }
      if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
      setDone(body as WebsiteResult);
    } catch (e) { setError(String(e instanceof Error ? e.message : e)); }
    finally { setBusy(false); }
  }

  const box = { border: "1px solid var(--line)", borderRadius: 6, padding: 10, display: "flex", flexDirection: "column" as const, gap: 6 };
  if (done) return (
    <div style={box}>
      <span>Added to the website as <b>{done.id}</b>: wrote {done.files.map(f => <code key={f} style={{ marginRight: 6 }}>{f}</code>)}
        in <code>{done.website}</code>. Nothing is public until the website is committed and deployed.</span>
      {done.embargoOverridden && <span role="status">The selection embargo was overridden for this finding; recorded in <code>EMBARGO_OVERRIDES.jsonl</code> beside <code>{done.embargoOverridden}</code>.</span>}
      <span className="muted">It will appear at <code>{done.page}</code>.</span>
      <div><button type="button" onClick={onClose}>ok</button></div>
    </div>
  );
  return (
    <div style={box}>
      <b>Add to website</b>
      <span className="muted">The figure as shown now (with any crop and edits, and the logo if ticked) goes to the image-findings page with this comment.</span>
      {dirs.length > 1 && (
        <label style={{ display: "flex", gap: 6, alignItems: "center" }}>paper the comment is on
          <select value={dir} onChange={e => setDir(e.target.value)}>
            {dirs.map((d, i) => <option key={d} value={d}>{"AB"[i] || i + 1} · {d}</option>)}
          </select>
        </label>
      )}
      <label style={{ display: "flex", gap: 6, alignItems: "center" }}>PubPeer URL
        <input type="url" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://pubpeer.com/publications/…"
               style={{ flex: 1, minWidth: 260 }} />
      </label>
      {url && !urlOk && <span style={{ color: "var(--sev-impossible)" }}>Not a PubPeer publication link.</span>}
      <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>Comment text
        <textarea value={summary} onChange={e => setSummary(e.target.value)} rows={4}
                  placeholder="The comment as posted on PubPeer" style={{ width: "100%", lineHeight: 1.4 }} />
      </label>
      <label style={{ display: "flex", gap: 6, alignItems: "center" }}>submitted
        <input type="date" value={date} onChange={e => setDate(e.target.value)} />
      </label>
      {error && <span role="alert" style={{ color: "var(--sev-impossible)" }}>{error}</span>}
      {embargo !== null && (
        <div role="alert" style={{ border: "2px solid var(--sev-impossible)", borderRadius: 6, padding: 8, display: "flex", flexDirection: "column", gap: 6 }}>
          <b>This corpus is under a selection embargo.</b>
          <span><code>{embargo}</code> marks it as selected for a possible False Claims Act action, where publishing our own
            findings can spoil the claim. Override only if you have decided to publish this finding. It applies to this
            one finding, the marker is left in place, and the override is written to <code>EMBARGO_OVERRIDES.jsonl</code> beside it.</span>
          <div>
            <button type="button" onClick={() => submit(true)}
                    disabled={busy || !urlOk || !summary.trim() || !dir || !date}>
              {busy ? "adding…" : "submit anyway"}</button>
          </div>
        </div>
      )}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" onClick={() => submit(false)} disabled={busy || !urlOk || !summary.trim() || !dir || !date}>
          {busy ? "adding…" : "add to website"}</button>
        <button type="button" onClick={onClose} disabled={busy}>cancel</button>
      </div>
    </div>
  );
}

const MIN_SELECTION_PX = 8;
/** Bright neon outline colours for drawn boxes: name for the tooltip, hex for the stroke. */
const NEON = [
  ["cyan", "#00FFFF"], ["magenta", "#FF00FF"], ["lime", "#39FF14"], ["yellow", "#FFFF00"],
  ["orange", "#FF6700"], ["hot pink", "#FF1493"], ["electric blue", "#1F8FFF"], ["neon red", "#FF073A"],
] as const;

/** A drawn box: a neon outline over a dark keyline, the same look as the
 *  duplication boxes, at a width that scales with the image. */
function strokeBox(ctx: CanvasRenderingContext2D, r: PixelRect, color: string, imageWidth: number) {
  const w = Math.max(3, imageWidth / 500);
  ctx.save();
  ctx.lineJoin = "miter";
  ctx.strokeStyle = "#111"; ctx.lineWidth = w * 1.7; ctx.strokeRect(r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0);
  ctx.strokeStyle = color; ctx.lineWidth = w; ctx.strokeRect(r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0);
  ctx.restore();
}

type Drag = { kind: "select"; x: number; y: number } | { kind: "move"; dx: number; dy: number }
  | { kind: "box"; x: number; y: number }
  | { kind: "scale"; grab: Exclude<Grab, null | "inside">; start: PixelRect; x: number; y: number };
/** How close (in screen pixels) the pointer must be to grab a selection edge. */
const GRAB_PX = 16;
/** Drawn handle size and outline width, in screen pixels. */
const HANDLE_PX = 14, OUTLINE_PX = 1.5;

export function SummaryFigureButton({ project, item, boxes, sizes, autoStart }: { project: string; item: Item; boxes: ImagePdfBox[];
  /** The panels' decoded sizes: the measured frame when the item does not record one. */
  sizes?: (ImageSize | null)[];
  /** The click that loaded this (lazily imported) module, replayed once. */
  autoStart?: "generate" | "website" }) {
  const [busy, setBusy] = useState(false);
  const [meta, setMeta] = useState<{ name: string; note: string | null } | null>(null);
  // Every committed version of the image, oldest first; [0] is as generated.
  const [history, setHistory] = useState<HTMLCanvasElement[]>([]);
  const [floating, setFloating] = useState<Floating | null>(null);
  const [selection, setSelection] = useState<PixelRect | null>(null);
  // The "found at the Metascience Observatory" logo, bottom right. Off by default
  // (Dan, 2026-10-22); the checkbox turns it on for a figure that wants it.
  const [brand, setBrand] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [website, setWebsite] = useState(false);
  const [resizing, setResizing] = useState(false);
  // The box tool: null = select/move; a colour = drag draws an outline in it.
  const [boxColor, setBoxColor] = useState<string | null>(null);
  const [boxDraft, setBoxDraft] = useState<PixelRect | null>(null);

  const generated = useRef<RenderedFigure | null>(null);
  const boxScales = useRef(new WeakMap<HTMLCanvasElement, number>());
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const origin = useRef({ x: 0, y: 0 }); // image -> display-canvas offset of the last draw
  const drag = useRef<Drag | null>(null);
  // The toolbar wraps on a narrow window; the image gets the height it leaves.
  const toolbarRef = useRef<HTMLDivElement>(null);
  const [toolbarH, setToolbarH] = useState(40);
  const content = history[history.length - 1] || null;
  // The dialog can be closed and reopened: the figure and its edits stay
  // until the item changes or a new one is generated.
  const [shown, setShown] = useState(false);
  const open = shown && !!meta && !!content;

  const discard = useCallback(() => {
    generated.current = null;
    setShown(false); setMeta(null); setHistory([]); setFloating(null); setSelection(null);
    setCopied(false); setWebsite(false); setResizing(false);
  }, []);
  useEffect(() => { discard(); setError(null); }, [item.id, item.run_id, discard]);
  /** Hide the dialog, keeping the edits; a lifted piece is placed where it is. */
  const close = useCallback(() => {
    if (floating) { const { canvas } = placePiece(floating); setHistory(h => [...h, canvas]); setFloating(null); }
    setSelection(null); setWebsite(false); setResizing(false); setShown(false);
  }, [floating]);

  const push = useCallback((next: HTMLCanvasElement) => { setHistory(h => [...h, next]); setCopied(false); }, []);
  /** The image with any lifted region put down where it now sits. */
  const settle = useCallback((): HTMLCanvasElement | null => {
    if (!floating) return content;
    const { canvas, at } = placePiece(floating);
    push(canvas); setFloating(null); setSelection(at);
    return canvas;
  }, [floating, content, push]);

  const selected = () => content && selection && !floating ? normaliseRect(selection, content.width, content.height) : null;
  const usable = (r: PixelRect | null): r is PixelRect => !!r && Math.min(r.x1 - r.x0, r.y1 - r.y0) >= MIN_SELECTION_PX;

  const lift = useCallback((r: PixelRect) => {
    if (!content) return null;
    const piece = blank(r.x1 - r.x0, r.y1 - r.y0);
    piece.getContext("2d")!.drawImage(content, r.x0, r.y0, piece.width, piece.height, 0, 0, piece.width, piece.height);
    const base = blank(content.width, content.height);
    const ctx = base.getContext("2d")!;
    ctx.drawImage(content, 0, 0);
    ctx.fillStyle = "#fff"; ctx.fillRect(r.x0, r.y0, piece.width, piece.height);
    const f = { base, piece: { canvas: piece, x: r.x0, y: r.y0, w: piece.width, h: piece.height } };
    setFloating(f); setSelection(null);
    return f;
  }, [content]);

  /** Commit a drawn box onto the image as one edit. */
  const drawBoxEdit = useCallback((r: PixelRect, color: string) => {
    if (!content) return;
    const out = blank(content.width, content.height);
    const ctx = out.getContext("2d")!;
    ctx.drawImage(content, 0, 0);
    strokeBox(ctx, r, color, content.width);
    push(out);
  }, [content, push]);

  const erase = useCallback((r: PixelRect) => {
    if (!content) return;
    const out = blank(content.width, content.height);
    const ctx = out.getContext("2d")!;
    ctx.drawImage(content, 0, 0);
    ctx.fillStyle = "#fff"; ctx.fillRect(r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0);
    push(out); setSelection(null);
  }, [content, push]);

  const crop = useCallback((r: PixelRect) => {
    if (!content) return null;
    const out = blank(r.x1 - r.x0, r.y1 - r.y0);
    out.getContext("2d")!.drawImage(content, r.x0, r.y0, out.width, out.height, 0, 0, out.width, out.height);
    push(out); setSelection(null);
    return out;
  }, [content, push]);

  const undo = useCallback(() => {
    if (floating) { setFloating(null); return; }
    setSelection(null); setHistory(h => h.length > 1 ? h.slice(0, -1) : h); setCopied(false);
  }, [floating]);

  // Draw: the image (grown to hold a moved piece), the piece, the selection, the credit band.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !content) return;
    const base = floating?.base || content;
    const p = floating?.piece;
    const b = stageBounds(base.width, base.height, p && { x: p.x, y: p.y, w: p.w, h: p.h });
    const w = b.x1 - b.x0, h = b.y1 - b.y0;
    const band = brand ? brandMetrics(w).band : 0;
    if (canvas.width !== w || canvas.height !== h + band) { canvas.width = w; canvas.height = h + band; }
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, canvas.width, canvas.height);
    origin.current = { x: -b.x0, y: -b.y0 };
    ctx.drawImage(base, -b.x0, -b.y0);
    // Handles and outlines keep a fixed size on screen however far the
    // (often 3000 px) image is scaled down to fit the dialog.
    const k = canvas.width / Math.max(1, canvas.getBoundingClientRect().width || canvas.width);
    const line = Math.max(1, OUTLINE_PX * k);
    const outline = (x: number, y: number, rw: number, rh: number) => {
      ctx.save(); ctx.lineWidth = line;
      ctx.setLineDash([]); ctx.strokeStyle = "#000"; ctx.strokeRect(x, y, rw, rh);
      ctx.setLineDash([line * 4, line * 3]); ctx.strokeStyle = "#fff"; ctx.strokeRect(x, y, rw, rh);
      ctx.restore();
    };
    // Resize handles at the corners and edge midpoints.
    const handles = (r: PixelRect) => {
      const hs = HANDLE_PX * k, mx = (r.x0 + r.x1) / 2, my = (r.y0 + r.y1) / 2;
      ctx.save(); ctx.fillStyle = "#fff"; ctx.strokeStyle = "#000"; ctx.lineWidth = line;
      for (const x of [r.x0, mx, r.x1]) for (const y of [r.y0, my, r.y1]) {
        if (x === mx && y === my) continue;
        ctx.fillRect(x - hs / 2, y - hs / 2, hs, hs); ctx.strokeRect(x - hs / 2, y - hs / 2, hs, hs);
      }
      ctx.restore();
    };
    if (p) {
      const r = { x0: p.x - b.x0, y0: p.y - b.y0, x1: p.x - b.x0 + p.w, y1: p.y - b.y0 + p.h };
      ctx.save(); ctx.imageSmoothingQuality = "high";
      ctx.drawImage(p.canvas, r.x0, r.y0, p.w, p.h); ctx.restore();
      outline(r.x0, r.y0, p.w, p.h);
      handles(r);
    }
    const sel = !floating && selection && normaliseRect(selection, base.width, base.height);
    if (sel) {
      ctx.save(); ctx.fillStyle = "rgba(0,0,0,.35)";
      ctx.beginPath(); ctx.rect(0, 0, w, h); ctx.rect(sel.x0, sel.y0, sel.x1 - sel.x0, sel.y1 - sel.y0);
      ctx.fill("evenodd"); ctx.restore();
      outline(sel.x0, sel.y0, sel.x1 - sel.x0, sel.y1 - sel.y0);
      handles(sel);
    }
    if (boxDraft && boxColor) strokeBox(ctx, boxDraft, boxColor, base.width);
    if (brand) drawBrand(ctx, w, h);
  }, [content, floating, selection, brand, open, boxDraft, boxColor]); // `open`: the canvas remounts on reopen

  const point = (e: ReactPointerEvent) => {
    const c = canvasRef.current!, r = c.getBoundingClientRect();
    return { x: (e.clientX - r.left) * c.width / r.width - origin.current.x,
             y: (e.clientY - r.top) * c.height / r.height - origin.current.y };
  };
  const tolerance = () => {
    const c = canvasRef.current!;
    return GRAB_PX * c.width / Math.max(1, c.getBoundingClientRect().width);
  };

  /** What a press at `p` would grab: the lifted piece if there is one, else
   *  the selection. Either way, the middle moves the content and the
   *  handles resize it. */
  const grabAt = (p: { x: number; y: number }): { rect: PixelRect; grab: Grab } | null => {
    if (floating) { const rect = pieceRect(floating.piece); return { rect, grab: grabSelection(rect, p, tolerance()) }; }
    const sel = selected();
    return usable(sel) ? { rect: sel, grab: grabSelection(sel, p, tolerance()) } : null;
  };

  function onPointerDown(e: ReactPointerEvent) {
    if (e.button || !content) return;
    e.preventDefault();
    try { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); } catch { /* capture is a convenience */ }
    const p = point(e);
    if (boxColor) {
      if (floating) settle();
      setSelection(null);
      drag.current = { kind: "box", x: p.x, y: p.y };
      setBoxDraft({ x0: p.x, y0: p.y, x1: p.x, y1: p.y });
      return;
    }
    const hit = grabAt(p);
    if (hit?.grab) {
      if (!floating) lift(hit.rect);
      const { rect, grab } = hit;
      drag.current = grab === "inside" ? { kind: "move", dx: p.x - rect.x0, dy: p.y - rect.y0 }
        : { kind: "scale", grab, start: rect, x: p.x, y: p.y };
      return;
    }
    if (floating) settle();
    drag.current = { kind: "select", x: p.x, y: p.y };
    setSelection({ x0: p.x, y0: p.y, x1: p.x, y1: p.y });
  }
  function onPointerMove(e: ReactPointerEvent) {
    const d = drag.current;
    const p = point(e);
    if (!d) {
      // Hover: show what a press here would do.
      const cursor = boxColor ? "crosshair" : grabCursor(grabAt(p)?.grab ?? null);
      if (canvasRef.current && canvasRef.current.style.cursor !== cursor) canvasRef.current.style.cursor = cursor;
      return;
    }
    if (d.kind === "scale") {
      const r = scaleRect(d.start, d.grab, p.x - d.x, p.y - d.y);
      setFloating(f => f && { ...f, piece: { ...f.piece, x: r.x0, y: r.y0, w: r.x1 - r.x0, h: r.y1 - r.y0 } });
    } else if (d.kind === "box") setBoxDraft({ x0: d.x, y0: d.y, x1: p.x, y1: p.y });
    else if (d.kind === "move") setFloating(f => f && { ...f, piece: { ...f.piece, x: Math.round(p.x - d.dx), y: Math.round(p.y - d.dy) } });
    else setSelection({ x0: d.x, y0: d.y, x1: p.x, y1: p.y });
  }
  function onPointerUp() {
    const d = drag.current; drag.current = null;
    if (d?.kind === "box") {
      const r = boxDraft && content && normaliseRect(boxDraft, content.width, content.height);
      setBoxDraft(null);
      if (r && boxColor && Math.min(r.x1 - r.x0, r.y1 - r.y0) >= MIN_SELECTION_PX) drawBoxEdit(r, boxColor);
      return;
    }
    if (d?.kind === "select") {
      const sel = selected();
      setSelection(usable(sel) ? sel : null);
    }
  }

  async function exportBlob(): Promise<Blob> {
    const current = settle();
    if (!current) throw new Error("nothing to export");
    const flat = flatten(current, brand);
    try { return await toBlob(flat); } finally { flat.width = 0; flat.height = 0; }
  }
  async function download(suffix = "") {
    if (!meta) return;
    try { saveBlob(await exportBlob(), `${meta.name}${suffix}.png`); }
    catch (e) { setError(`Download failed: ${String(e)}`); }
  }
  async function copy() {
    try { await navigator.clipboard.write([new ClipboardItem({ "image/png": exportBlob() })]); setCopied(true); }
    catch (e) { setError(`Copy failed: ${String(e)}`); }
  }
  async function cropAndDownload() {
    const sel = selected();
    if (!usable(sel) || !meta) return;
    const out = crop(sel);
    if (!out) return;
    try { const flat = flatten(out, brand); saveBlob(await toBlob(flat), `${meta.name}_crop.png`); flat.width = 0; }
    catch (e) { setError(`Crop failed: ${String(e)}`); }
  }

  // While open, the page's shortcuts (Esc = back to queue, j/k = navigate)
  // must not act behind the dialog. Esc puts back a lifted region, then
  // clears a selection, then closes; Enter places; Delete blanks; Ctrl+Z undoes.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) {
        e.stopPropagation(); // typing stays in the form, away from the page's shortcuts
        if (e.key === "Escape") setWebsite(false);
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); undo(); return; }
      if (e.ctrlKey || e.metaKey) return;
      e.preventDefault();
      if (e.key === "Escape") {
        if (boxColor) setBoxColor(null); else if (floating) setFloating(null); else if (selection) setSelection(null); else close();
      }
      else if (e.key === "Enter" && floating) settle();
      else if (e.key === "Delete" || e.key === "Backspace") { const s = selected(); if (usable(s)) erase(s); }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  });

  useEffect(() => {
    const el = toolbarRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setToolbarH(el.getBoundingClientRect().height));
    ro.observe(el);
    return () => ro.disconnect();
  }, [open]);

  const pdfGroups = summaryGroups(item, boxes);
  const pending = nativeSides(item, pdfGroups);
  const available = pdfGroups.length > 0 || pending.length > 0;

  async function generate(force = false): Promise<boolean> {
    if (!force && content && meta) { setShown(true); return true; } // reopen, edits kept
    setBusy(true); setError(null); setCopied(false);
    try {
      if (!available) throw new Error("No PDF placement or figure image for either panel -- nothing to screenshot.");
      const dirs = [...new Set(pending.map(s => item.panels[s].paper_dir))];
      const native = pending.length ? nativeSummaryGroups(item, pending, await fetchFigures(project, item, dirs), sizes) : [];
      if (pending.length && !native.length && !pdfGroups.length)
        throw new Error("This paper has no PDF, and neither panel could be linked to one of its figure images.");
      const groups: SummaryGroup[] = [...pdfGroups, ...native].sort((a, b) => a.sides[0] - b.sides[0]);
      const figure = await compose(project, item, groups);
      const { unreferenced } = figure;
      const missing = groups.filter(g => !g.boxes.length).length;
      const unlinked = pending.filter(s => !native.some(g => g.sides.includes(s))).map(s => "AB"[s]);
      const notes = [missing ? `${missing} of ${groups.length} figure(s) have no exact placement, so no box is drawn there.` : "",
        unlinked.length ? `Panel ${unlinked.join(" and ")} has no PDF and could not be linked to a figure image, so it is not shown.` : "",
        unreferenced ? `No reference could be found for ${unreferenced} paper(s).` : ""].filter(Boolean);
      discard();
      generated.current = figure;
      const canvas = annotateFigure(figure, 100);
      boxScales.current.set(canvas, 100);
      setHistory([canvas]);
      setMeta({ name: `summary_figure_${item.id.replace(/[^\w.-]+/g, "_")}`, note: notes.join(" ") || null });
      setShown(true);
      return true;
    } catch (e) { setError(String(e instanceof Error ? e.message : e)); return false; }
    finally { setBusy(false); }
  }

  const boxPercent = content ? boxScales.current.get(content) : undefined;
  const canExpand = boxPercent !== undefined && !floating && !!generated.current?.boxes.some(b => !b.dashed);
  const changeBoxSize = (percent: number) => {
    if (!canExpand || !generated.current) return;
    const next = percent <= 0 ? 0 : Math.max(100, Math.min(1000, percent));
    const canvas = annotateFigure(generated.current, next);
    boxScales.current.set(canvas, next);
    push(canvas); setSelection(null);
  };
  const sel = selected();
  const edited = history.length > 1 || !!floating;
  /** Scale the lifted picture to `pct` percent of its original size,
   *  proportions locked, anchored at its top-left corner. */
  const scaleTo = (pct: number) => setFloating(f => {
    if (!f) return f;
    const k = Math.min(1000, Math.max(5, pct)) / 100;
    return { ...f, piece: { ...f.piece, w: Math.max(8, f.piece.canvas.width * k), h: Math.max(8, f.piece.canvas.height * k) } };
  });
  const pct = floating ? Math.round(100 * floating.piece.w / floating.piece.canvas.width) : 100;
  const openResize = () => {
    if (!floating) { const s = selected(); if (!usable(s)) return; lift(s); }
    setResizing(true);
  };
  const hint = boxColor ? "drag on the image to draw a box in the chosen colour; Esc or 'select' returns to selecting"
    : floating ? "drag the piece to move it, its handles to resize it; click outside it or press Enter to place, Esc to put it back"
    : usable(sel) ? "drag inside the selection to move it, or its handles to resize it (corners keep the proportions)"
    : "drag on the image to select a region";

  const started = useRef(false);
  useEffect(() => {
    if (!autoStart || started.current) return;
    started.current = true;
    void generate().then(ok => { if (ok && autoStart === "website") setWebsite(true); });
  // eslint-disable-next-line react-hooks/exhaustive-deps -- once, on the mount the click caused
  }, []);

  return (
    <>
      <button type="button" onClick={() => generate()} disabled={busy || !available}
              title={!available ? "No PDF placement or figure image for this finding"
                : content ? "Reopen the summary figure with its edits"
                : pdfGroups.length ? "Render the whole figure(s) from the PDF with the duplication boxes drawn on"
                : "Render the whole figure image(s) with the duplication boxes drawn on"}>
        {busy ? "generating…" : content ? `open summary figure${history.length > 1 ? " (edited)" : ""}` : "generate summary figure"}
      </button>
      <button type="button" onClick={async () => { if (await generate()) setWebsite(true); }} disabled={busy || !available}
              title="Generate the summary figure and put it, with its PubPeer comment, on the Observatory website's image-findings page">
        add to website
      </button>
      {error && !open && <span role="alert" style={{ color: "var(--sev-impossible)" }}>{error}</span>}
      {open && meta && createPortal(
        <div role="dialog" aria-modal="true" aria-label="Summary figure" onClick={close}
             style={{ position: "fixed", inset: 0, zIndex: 50, background: "rgba(0,0,0,.6)",
                      display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
          <div onClick={e => e.stopPropagation()}
               style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 6, padding: 12,
                        maxWidth: "100%", maxHeight: "100%", overflow: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
            <div ref={toolbarRef} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <b>Summary figure{edited ? " (edited)" : ""}</b>
              <span className="muted">{hint}</span>
              {meta.note && <span className="muted">{meta.note}</span>}
              {error && <span role="alert" style={{ color: "var(--sev-impossible)" }}>{error}</span>}
              <span style={{ flex: 1 }} />
              <span style={{ display: "inline-flex", gap: 3, alignItems: "center" }} title="Draw a box: pick a colour, then drag on the image">
                <button type="button" onClick={() => setBoxColor(null)} aria-pressed={!boxColor}
                        style={{ fontWeight: boxColor ? undefined : "bold" }}>select</button>
                {NEON.map(([name, hex]) => (
                  <button key={hex} type="button" onClick={() => { setBoxColor(hex); setSelection(null); }}
                          aria-label={`draw ${name} box`} aria-pressed={boxColor === hex} title={`draw a ${name} box`}
                          style={{ width: 22, height: 22, padding: 0, background: hex, border: boxColor === hex ? "3px solid #111" : "1px solid #555",
                                   borderRadius: 4, cursor: "pointer" }} />
                ))}
              </span>
              <button type="button" onClick={openResize} disabled={!floating && !usable(sel)}
                      title="Scale the selected picture by a percentage, proportions locked">resize</button>
              {floating && <button type="button" onClick={() => { settle(); setResizing(false); }} title="Put the piece down here (Enter)">place</button>}
              <button type="button" onClick={() => { if (usable(sel)) erase(sel); }} disabled={!usable(sel)}
                      title="Blank the selection to white (Delete)">blank</button>
              <button type="button" onClick={() => { if (usable(sel)) crop(sel); }} disabled={!usable(sel)}
                      title="Crop to the selection">crop</button>
              <button type="button" onClick={cropAndDownload} disabled={!usable(sel)}
                      title="Crop to the selection, keep the crop here, and download it">crop &amp; download</button>
              <button type="button" onClick={undo} disabled={!edited} title="Undo the last edit (Ctrl+Z)">undo</button>
              <button type="button" disabled={!edited} title="Back to the image as generated, discarding every edit"
                      onClick={() => { setFloating(null); setSelection(null); setResizing(false); setHistory(h => h.slice(0, 1)); }}>reset</button>
              <button type="button" disabled={busy} title="Render the figure again from the PDF (discards edits)"
                      onClick={() => void generate(true)}>regenerate</button>
              <label title="Credit line in the bottom-right corner" style={{ display: "flex", gap: 4, alignItems: "center" }}>
                <input type="checkbox" checked={brand} onChange={e => setBrand(e.target.checked)} /> logo
              </label>
              <button type="button" onClick={() => download()}>download PNG</button>
              <button type="button" onClick={copy}>{copied ? "copied" : "copy"}</button>
              {pubpeerLinks(item).map(l => (
                <a key={l.href} href={l.href} target="_blank" rel="noopener noreferrer" title={l.title}>{l.label} ↗</a>
              ))}
              <button type="button" onClick={() => setWebsite(w => !w)} aria-expanded={website}
                      title="Put this figure and its PubPeer comment on the Observatory website's image-findings page">add to website</button>
              <button type="button" onClick={close}>close</button>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <b>Match boxes</b>
              <button type="button" onClick={() => changeBoxSize(boxPercent === 0 ? 100 : (boxPercent ?? 100) + 25)} disabled={!canExpand || (boxPercent ?? 100) >= 1000}>expand boxes +25%</button>
              <button type="button" onClick={() => changeBoxSize((boxPercent ?? 100) - 25)} disabled={!canExpand || boxPercent === 100 || boxPercent === 0}>shrink boxes −25%</button>
              <button type="button" onClick={() => changeBoxSize(0)} disabled={!canExpand || boxPercent === 0}
                      title="Remove the match boxes from the figure (original boxes brings them back)">remove boxes</button>
              <span>{boxPercent === 0 ? "boxes removed" : boxPercent !== undefined ? `${boxPercent}%` : "custom edits"}</span>
              <button type="button" onClick={() => changeBoxSize(100)} disabled={!canExpand || boxPercent === 100}>original boxes</button>
              <span className="muted">{boxPercent === undefined || floating
                ? "Reset image edits to adjust the match boxes."
                : "Adjust outlines before cropping. Larger boxes are a visual guide; check their extent against the images."}</span>
            </div>
            {resizing && floating && (
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", border: "1px solid var(--line)", borderRadius: 6, padding: 8 }}>
                <b>Resize</b>
                <span className="muted">the selected picture, proportions locked; then place it</span>
                <button type="button" onClick={() => scaleTo(pct - 10)}>−10%</button>
                <input type="number" min={5} max={1000} step={5} value={pct} style={{ width: 70 }}
                       onChange={e => { const v = Number(e.target.value); if (Number.isFinite(v) && v > 0) scaleTo(v); }} />
                <span>%</span>
                <button type="button" onClick={() => scaleTo(pct + 10)}>+10%</button>
                <button type="button" onClick={() => scaleTo(50)}>½</button>
                <button type="button" onClick={() => scaleTo(200)}>2×</button>
                <button type="button" onClick={() => scaleTo(100)}>100%</button>
                <span style={{ flex: 1 }} />
                <button type="button" onClick={() => { settle(); setResizing(false); }}>place</button>
                <button type="button" onClick={() => { setFloating(null); setResizing(false); }}>cancel</button>
              </div>
            )}
            {website && <AddToWebsite project={project} item={item} exportBlob={exportBlob} onClose={() => setWebsite(false)} />}
            </div>
            <div style={{ alignSelf: "center", minHeight: 0, lineHeight: 0, overflow: "hidden", touchAction: "none" }}>
              <canvas ref={canvasRef} role="img" aria-label="Summary figure: the source figure(s) with duplication boxes"
                      onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
                      style={{ display: "block", maxWidth: "100%", maxHeight: `calc(100vh - ${Math.ceil(toolbarH) + 84}px)`, width: "auto", height: "auto",
                               userSelect: "none" }} />
            </div>
          </div>
        </div>, document.body
      )}
    </>
  );
}
