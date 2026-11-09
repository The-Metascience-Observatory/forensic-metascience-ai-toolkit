import { mergeTextBoxes } from "@/lib/textHighlightBoxes";
import { SEV_FILL } from "@/lib/severity";
import { appendFlipArrow } from "@/lib/flipArrow";
import type { ImagePdfBox } from "@/lib/imagePdfBoxes";
import { boxesOf } from "@/lib/targets";
import type { Match, PageSlot } from "./textLayer";

/** What `PdfPane` is told to open: the finding's page, its boxes and the
 *  jump targets that carry their own boxes. */
export type PdfLocator = {
  page?: number | null;
  confidence?: string;
  method?: string;
  boxes?: { page?: number; x0: number; y0: number; x1: number; y1: number }[];
  targets?: { id: string; kind: string; confidence?: string;
              page?: number | null;
              boxes?: { page?: number; x0: number; y0: number; x1: number; y1: number }[] }[];
};

/** Find-in-PDF hits on the search overlays; scrolls the current one into view. */
export function paintHits(slots: PageSlot[], matches: Match[], current: number) {
  for (const slot of slots) slot.search.innerHTML = "";
  matches.forEach((m, i) => {
    const slot = slots[m.page - 1];
    if (!slot) return;
    for (const box of m.boxes) {
      const el = document.createElement("div");
      el.className = i === current ? "pdf-hit pdf-hit-current" : "pdf-hit";
      el.style.left = `${box.x0}px`;
      el.style.top = `${box.y0}px`;
      el.style.width = `${Math.max(1, box.x1 - box.x0)}px`;
      el.style.height = `${Math.max(1, box.y1 - box.y0)}px`;
      slot.search.appendChild(el);
    }
  });
  const cur = matches[current];
  if (!cur) return;
  const slot = slots[cur.page - 1];
  const el = slot?.search.querySelector(".pdf-hit-current");
  el?.scrollIntoView({ block: "center", inline: "nearest" });
}

/** The finding's boxes, the image duplication polygons and the sticky label
 *  on the page overlays (cleared first). Returns the page the focus is on, or
 *  null, so the caller can decide whether to scroll there. */
export function paintFindings(slots: PageSlot[], { locator, label, severity, focusTargetId, imageBoxes }: {
  locator: PdfLocator | null;
  label: string;
  severity?: string;
  focusTargetId?: string | null;
  imageBoxes: ImagePdfBox[];
}): number | null {
  for (const slot of slots) slot.overlay.innerHTML = "";
  const boxes = boxesOf(locator);
  const canBox = boxes.length > 0;
  const focusTid = focusTargetId || null;
  const focusTarget = (locator?.targets || []).find((t) => t.id === focusTid);
  // A focused page with no box (page-only locate) must not fall back to
  // boxes[0] — that is a different page.
  const focusBox = boxes.find((b) => focusTid && b.tid === focusTid)
    || (focusTid ? undefined : boxes[0]);
  const focusPage = (focusBox?.page
    || (typeof focusTarget?.page === "number" && focusTarget.page >= 1
      ? focusTarget.page : null)
    || (locator?.page && locator.page >= 1 ? locator.page : null)) ?? null;
  if (canBox) {
    for (let i = 0; i < slots.length; i++) {
      const n = i + 1;
      const slot = slots[i];
      const sx = slot.vw / slot.unscaledW;
      const sy = slot.vh / slot.unscaledH;
      const onPage = boxes.filter((b) => (b.page ?? locator?.page) === n);
      const merged = mergeTextBoxes(onPage, sx, sy);
      for (const box of merged) {
        const el = document.createElement("div");
        el.className = "pdf-finding";
        el.style.left = `${box.x0 * sx}px`;
        el.style.top = `${box.y0 * sy}px`;
        el.style.width = `${(box.x1 - box.x0) * sx}px`;
        el.style.height = `${(box.y1 - box.y0) * sy}px`;
        el.style.background = imageBoxes.some(b => b.tid === box.tid) ? "transparent" : SEV_FILL[severity || ""] || "rgba(61,143,209,0.25)";
        const focused = !!focusTid && box.tid === focusTid;
        if (focused && !imageBoxes.some(b => b.tid === box.tid)) {
          el.classList.add("pdf-finding-focus");
          el.dataset.focus = "1";
        }
        if (focusBox && box.tid === focusBox.tid && box.page === focusBox.page) {
          el.dataset.hit = "1";
        }
        slot.overlay.appendChild(el);
      }
    }
  }
  // SVG preserves rotated/skewed regions and keeps a 2.8px screen stroke.
  for (const box of imageBoxes) {
    const slot = slots[box.page - 1];
    if (!slot) continue;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.classList.add("pdf-duplication");
    svg.setAttribute("viewBox", `0 0 ${slot.unscaledW} ${slot.unscaledH}`);
    svg.setAttribute("preserveAspectRatio", "none");
    Object.assign(svg.style, { position: "absolute", inset: "0", width: "100%", height: "100%", overflow: "visible" });
    const polygon = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    polygon.setAttribute("points", box.points.map(p => p.join(",")).join(" "));
    polygon.setAttribute("fill", "none");
    polygon.setAttribute("stroke", box.color);
    polygon.setAttribute("stroke-width", "2.8");
    polygon.setAttribute("vector-effect", "non-scaling-stroke");
    svg.appendChild(polygon);
    appendFlipArrow(svg, box.points, box.color, box.flipDirection);
    if (box.regionLabel && box.points.length) {
      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      const anchor = box.points.reduce((best, point) => point[1] < best[1] ? point : best);
      text.setAttribute("x", String(anchor[0]));
      text.setAttribute("y", String(anchor[1] - 4));
      text.setAttribute("fill", box.color);
      text.setAttribute("stroke", "#111");
      text.setAttribute("stroke-width", "2");
      text.setAttribute("paint-order", "stroke");
      text.setAttribute("font-size", "12");
      text.setAttribute("font-weight", "bold");
      text.textContent = box.regionLabel;
      svg.appendChild(text);
    }
    slot.overlay.appendChild(svg);
  }
  if (focusPage && label) {
    const slot = slots[focusPage - 1];
    if (slot) {
      const sticky = document.createElement("div");
      sticky.textContent = label;
      sticky.style.position = "absolute";
      sticky.style.right = "-2px";
      sticky.style.top = "8px";
      sticky.style.transform = "translateX(100%)";
      sticky.style.background = "var(--accent)";
      sticky.style.color = "var(--on-accent)";
      sticky.style.fontSize = "11px";
      sticky.style.padding = "3px 6px";
      sticky.style.borderRadius = "0 4px 4px 0";
      sticky.style.whiteSpace = "nowrap";
      slot.overlay.appendChild(sticky);
    }
  }
  return focusPage;
}
