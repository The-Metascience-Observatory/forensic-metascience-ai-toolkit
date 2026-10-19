"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { PDFDocumentProxy } from "pdfjs-dist";
import { mergePdfBoxes } from "@/lib/pdfBoxes";
import { SEV_FILL } from "@/lib/severity";
import { appendFlipArrow } from "@/lib/flipArrow";
import type { ImagePdfBox } from "@/lib/imagePdfBoxes";
import { pdfBoxes } from "@/lib/targets";
import { FindBar, useFindShortcut } from "./FindBar";

type Box = { x0: number; y0: number; x1: number; y1: number };

type TextRun = {
  str: string;
  start: number;
  end: number;
  box: Box;
};

type PageSlot = {
  wrap: HTMLDivElement;
  overlay: HTMLDivElement;
  search: HTMLDivElement;
  unscaledW: number;
  unscaledH: number;
  vw: number;
  vh: number;
  haystack: string;
  runs: TextRun[];
  textLayer: { cancel: () => void } | null;
};

type Match = { page: number; boxes: Box[] };

function isTextItem(item: unknown): item is { str: string; transform: number[];
  width: number; height: number; hasEOL?: boolean } {
  return !!item && typeof item === "object" && "str" in item
    && typeof (item as { str: unknown }).str === "string";
}

function itemBox(
  item: { transform: number[]; width: number; height: number },
  viewport: { convertToViewportRectangle: (r: number[]) => number[] },
): Box {
  const x = item.transform[4];
  const y = item.transform[5];
  const h = item.height || Math.hypot(item.transform[2], item.transform[3]) || 8;
  const w = item.width || 0;
  const rect = viewport.convertToViewportRectangle([x, y, x + w, y + h]);
  const x0 = Math.min(rect[0], rect[2]);
  const y0 = Math.min(rect[1], rect[3]);
  const x1 = Math.max(rect[0], rect[2]);
  const y1 = Math.max(rect[1], rect[3]);
  return { x0, y0, x1, y1 };
}

function pageText(
  items: unknown[],
  viewport: { convertToViewportRectangle: (r: number[]) => number[] },
): { haystack: string; runs: TextRun[] } {
  let haystack = "";
  const runs: TextRun[] = [];
  let prev = "";
  let prevEOL = false;
  for (const raw of items) {
    if (!isTextItem(raw)) continue;
    const str = raw.str;
    if (prev && !prevEOL && str && !/\s$/.test(prev) && !/^\s/.test(str)) {
      haystack += " ";
    }
    if (str) {
      const start = haystack.length;
      haystack += str;
      runs.push({ str, start, end: haystack.length, box: itemBox(raw, viewport) });
    }
    prev = str || prev;
    prevEOL = !!raw.hasEOL;
    if (raw.hasEOL) haystack += "\n";
  }
  return { haystack, runs };
}

function findMatches(slots: PageSlot[], query: string): Match[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const out: Match[] = [];
  for (let i = 0; i < slots.length; i++) {
    const page = i + 1;
    const lower = slots[i].haystack.toLowerCase();
    let from = 0;
    while (from <= lower.length - q.length) {
      const at = lower.indexOf(q, from);
      if (at < 0) break;
      const end = at + q.length;
      const boxes: Box[] = [];
      for (const run of slots[i].runs) {
        if (run.end <= at || run.start >= end) continue;
        boxes.push(run.box);
      }
      if (boxes.length) out.push({ page, boxes });
      from = at + 1;
    }
  }
  return out;
}

function paintHits(slots: PageSlot[], matches: Match[], current: number) {
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

export type DrawnRegion = { page: number; bbox: [number, number, number, number] };

export function PdfPane({ url, locator, label, severity, focusTargetId,
  zoom = 1, refitNonce = 0, imageBoxes = [], onDrawRegion = null }: {
  url: string;
  imageBoxes?: ImagePdfBox[];
  /** While set, dragging on a page draws a box and reports it in PDF points
   *  (top-left origin, the same coordinates as `imageBoxes`). */
  onDrawRegion?: ((region: DrawnRegion) => void) | null;
  locator: {
    page?: number | null;
    confidence?: string;
    method?: string;
    boxes?: { page?: number; x0: number; y0: number; x1: number; y1: number }[];
    targets?: { id: string; kind: string; confidence?: string;
                page?: number | null;
                boxes?: { page?: number; x0: number; y0: number; x1: number; y1: number }[] }[];
  } | null;
  label: string;
  severity?: string;
  focusTargetId?: string | null;
  /** 1 = fit the pane width, which is what this pane always used to do. */
  zoom?: number;
  /**
   * Bump to re-render at the pane's CURRENT width. Driven only by the fit
   * button, i.e. by a human.
   *
   * A ResizeObserver used to do this automatically and it flashed on every
   * paper: the observed host sits inside `.pdf-scroll`, each render starts
   * `host.innerHTML = ""`, so the scrollbar vanished, the host widened, the
   * observer fired, the pages came back, the scrollbar returned, the host
   * narrowed, and round again. The width never drifted -- it alternated
   * between two values, so an "is it different from last time" guard could
   * not see it. Anything re-rendering off measured layout can close that
   * loop; a gesture cannot.
   */
  refitNonce?: number;
}) {
  const host = useRef<HTMLDivElement>(null);
  const findInput = useRef<HTMLInputElement>(null);
  const pages = useRef<PageSlot[]>([]);
  const matchesRef = useRef<Match[]>([]);
  const matchAtRef = useRef(0);
  const findOpenRef = useRef(false);
  const [err, setErr] = useState<string | null>(null);
  const [nPages, setNPages] = useState(0);
  const [pdfDocument, setDocument] = useState<PDFDocumentProxy | null>(null);
  const latestLocator = useRef(locator);
  latestLocator.current = locator;
  const [textReady, setTextReady] = useState(false);
  const [ready, setReady] = useState(false);
  const [findOpen, setFindOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [matchAt, setMatchAt] = useState(0);
  const [matchN, setMatchN] = useState(0);

  const runSearch = useCallback((q: string, at = 0) => {
    const matches = findMatches(pages.current, q);
    const nextAt = matches.length ? ((at % matches.length) + matches.length) % matches.length : 0;
    matchesRef.current = matches;
    matchAtRef.current = nextAt;
    setMatchN(matches.length);
    setMatchAt(nextAt);
    paintHits(pages.current, matches, nextAt);
  }, []);

  const stepMatch = useCallback((delta: number) => {
    const matches = matchesRef.current;
    if (!matches.length) return;
    const next = (matchAtRef.current + delta + matches.length) % matches.length;
    matchAtRef.current = next;
    setMatchAt(next);
    paintHits(pages.current, matches, next);
  }, []);

  const openFind = useCallback(() => {
    findOpenRef.current = true;
    setFindOpen(true);
    queueMicrotask(() => {
      findInput.current?.focus();
      findInput.current?.select();
    });
  }, []);

  const closeFind = useCallback(() => {
    findOpenRef.current = false;
    setFindOpen(false);
    setQuery("");
    matchesRef.current = [];
    matchAtRef.current = 0;
    setMatchN(0);
    setMatchAt(0);
    paintHits(pages.current, [], 0);
  }, []);

  // Document lifetime is independent of zoom, pane width and finding selection.
  useEffect(() => {
    let gone = false;
    let task: import("pdfjs-dist").PDFDocumentLoadingTask | undefined;
    setDocument(null); setErr(null); setReady(false);
    void import("pdfjs-dist").then(async (pdfjs) => {
      if (gone) return;
      pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
      task = pdfjs.getDocument({ url, withCredentials: false });
      const doc = await task.promise;
      if (!gone) setDocument(doc);
    }).catch(async (e) => {
      if (gone) return;
      // pdf.js wraps every failed fetch as "Missing PDF <url>"; the media
      // route answers a JSON `error` that says WHY (an unregistered root, a
      // hash mismatch, a file outside the paper folder). Show that.
      let msg = String(e);
      try {
        const r = await fetch(url, { headers: { Range: "bytes=0-0" } });
        if (!r.ok) {
          const body = await r.json().catch(() => null);
          if (body && typeof body.error === "string") msg = `${body.error} [HTTP ${r.status}]`;
        }
      } catch { /* keep pdf.js's message */ }
      if (!gone) setErr(msg);
    });
    return () => { gone = true; if (task) void task.destroy().catch(() => {}); };
  }, [url]);

  useEffect(() => {
    let gone = false;
    let observer: IntersectionObserver | null = null;
    const renders = new Map<number, { cancel: () => void }>();
    const desired = new Set<number>();
    const rendered = new Set<number>();
    const canvases = new Map<number, HTMLCanvasElement>();
    const textDivs = new Map<number, HTMLDivElement>();
    const hostEl = host.current;
    pages.current = [];
    setReady(false); setTextReady(false); setNPages(0); closeFind();
    if (!pdfDocument || !hostEl) return;
    const pdf = pdfDocument;
    const slots: PageSlot[] = [];
    let pumping = false;
    let firstPage = 0;
    let resolveFirstPaint: () => void = () => {};
    const firstPaint = new Promise<void>(resolve => { resolveFirstPaint=resolve; });
    const clearPage = (n: number) => {
      renders.get(n)?.cancel();
      slots[n]?.textLayer?.cancel();
      const cv = canvases.get(n);
      if (cv) { delete cv.dataset.rendered; cv.width = 0; cv.height = 0; }
      const div = textDivs.get(n);
      if (div) div.innerHTML = "";
      rendered.delete(n);
    };
    void (async () => {
      const pdfjs = await import("pdfjs-dist");
      if (gone) return;
      hostEl.innerHTML = "";
      setNPages(pdf.numPages);
      const width = hostEl.clientWidth || 800;
      const dpr = window.devicePixelRatio || 1;
      // Stable placeholders establish scroll geometry without rendering canvases.
      for (let n = 0; n < pdf.numPages; n++) {
        const page = await pdf.getPage(n + 1);
        if (gone) return;
        const unscaled = page.getViewport({ scale: 1 });
        const scale = width / unscaled.width * zoom;
        const viewport = page.getViewport({ scale });
        const wrap = document.createElement("div");
        wrap.dataset.page = String(n + 1);
        Object.assign(wrap.style, { position: "relative", margin: "0 0 12px",
          width: `${viewport.width}px`, height: `${viewport.height}px` });
        wrap.style.setProperty("--scale-factor", String(scale));
        const cv = document.createElement("canvas");
        cv.width = 0; cv.height = 0;
        cv.style.width = `${viewport.width}px`; cv.style.height = `${viewport.height}px`;
        const overlay = document.createElement("div"); overlay.className = "pdf-overlay";
        const search = document.createElement("div"); search.className = "pdf-overlay pdf-search-overlay";
        const textDiv = document.createElement("div"); textDiv.className = "textLayer pdf-text-layer";
        wrap.append(cv, overlay, search, textDiv); hostEl.appendChild(wrap);
        canvases.set(n, cv); textDivs.set(n, textDiv);
        slots.push({ wrap, overlay, search, unscaledW: unscaled.width, unscaledH: unscaled.height,
          vw: viewport.width, vh: viewport.height, haystack: "", runs: [], textLayer: null });
      }
      pages.current = slots;
      const loc = latestLocator.current;
      firstPage = Math.max(0, Math.min(pdf.numPages - 1, (loc?.page || pdfBoxes(loc)[0]?.page || 1) - 1));
      const pump = async () => {
        if (pumping || gone) return;
        pumping = true;
        try {
          while (!gone) {
            const n = [...desired].filter((i) => !rendered.has(i)).sort((a, b) => Math.abs(a - firstPage) - Math.abs(b - firstPage))[0];
            if (n === undefined) break;
            const slot = slots[n], cv = canvases.get(n)!;
            const page = await pdf.getPage(n + 1);
            if (gone) return;
            const viewport = page.getViewport({ scale: slot.vw / slot.unscaledW });
            delete cv.dataset.rendered;
            cv.width = Math.round(slot.vw * dpr); cv.height = Math.round(slot.vh * dpr);
            const task = page.render({ canvasContext: cv.getContext("2d")!, viewport,
              transform: dpr === 1 ? undefined : [dpr, 0, 0, dpr, 0, 0] });
            renders.set(n, task);
            try {
              await task.promise;
              if (gone || !desired.has(n)) { clearPage(n); continue; }
              cv.dataset.rendered = "true";
              resolveFirstPaint();
              const content = await page.getTextContent();
              if (gone || !desired.has(n)) { clearPage(n); continue; }
              const layer = new pdfjs.TextLayer({ textContentSource: content, container: textDivs.get(n)!, viewport });
              slot.textLayer = layer;
              await layer.render();
              rendered.add(n);
            } catch (e) {
              if (!gone && desired.has(n) && !["RenderingCancelledException", "AbortException"].includes((e as Error).name)) {
                setErr(String(e)); desired.delete(n);
              }
            } finally { renders.delete(n); }
          }
        } finally { pumping = false; }
      };
      desired.add(firstPage);
      void pump();
      setReady(true);
      observer = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          const n = Number((entry.target as HTMLElement).dataset.page) - 1;
          if (entry.isIntersecting) desired.add(n);
          else { desired.delete(n); clearPage(n); }
        }
        void pump();
      }, { root: hostEl.closest(".pdf-scroll"), rootMargin: "600px" });
      slots.forEach((slot) => observer!.observe(slot.wrap));
      // Visible evidence takes priority over whole-document search indexing.
      await firstPaint;
      if (gone) return;
      // Whole-document search does not require whole-document rasterization.
      for (let n = 0; n < pdf.numPages && !gone; n++) {
        const page = await pdf.getPage(n + 1);
        const content = await page.getTextContent();
        if (gone) return;
        const viewport = page.getViewport({ scale: slots[n].vw / slots[n].unscaledW });
        Object.assign(slots[n], pageText(content.items, viewport));
        if (findOpenRef.current) runSearch(findInput.current?.value || "", matchAtRef.current);
        await new Promise((resolve) => setTimeout(resolve, 0));
      }
      if (!gone) setTextReady(true);
    })().catch((e) => { if (!gone) setErr(String(e)); });
    return () => {
      gone = true; resolveFirstPaint(); observer?.disconnect();
      renders.forEach((task) => task.cancel());
      slots.forEach((slot) => slot.textLayer?.cancel());
      canvases.forEach((cv) => { cv.width = 0; cv.height = 0; });
      hostEl.innerHTML = ""; pages.current = [];
    };
  }, [pdfDocument, zoom, refitNonce, closeFind, runSearch]);

  useEffect(() => {
    if (!ready) return;
    const slots = pages.current;
    for (const slot of slots) slot.overlay.innerHTML = "";
    const boxes = pdfBoxes(locator);
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
        const merged = mergePdfBoxes(onPage, sx, sy);
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
    if (!findOpenRef.current && host.current) {
      const hit = host.current.querySelector("[data-focus='1']")
        || host.current.querySelector("[data-hit='1']");
      if (hit) {
        hit.scrollIntoView({ block: "center", inline: "nearest" });
      } else if (focusPage) {
        const el = host.current.querySelector(`[data-page="${focusPage}"]`);
        if (el) el.scrollIntoView({ block: "start" });
      }
    }
  }, [ready, locator, label, severity, focusTargetId, imageBoxes]);

  // Box drawing for "record a missed duplication". Screen pixels inside a
  // page map to PDF points by that page's own display scale.
  useEffect(() => {
    const el = host.current;
    if (!el || !onDrawRegion) return;
    el.style.cursor = "crosshair";
    let start: { wrap: HTMLElement; n: number; x: number; y: number } | null = null;
    let band: HTMLDivElement | null = null;
    const local = (wrap: HTMLElement, e: PointerEvent) => {
      const r = wrap.getBoundingClientRect();
      return { x: Math.max(0, Math.min(r.width, e.clientX - r.left)), y: Math.max(0, Math.min(r.height, e.clientY - r.top)) };
    };
    const down = (e: PointerEvent) => {
      const wrap = (e.target as HTMLElement | null)?.closest<HTMLElement>("[data-page]");
      if (!wrap || e.button !== 0) return;
      e.preventDefault();
      const at = local(wrap, e);
      start = { wrap, n: Number(wrap.dataset.page), ...at };
      band = document.createElement("div");
      Object.assign(band.style, { position: "absolute", border: "2px dashed var(--accent)", background: "rgba(61,143,209,.12)",
        left: `${at.x}px`, top: `${at.y}px`, width: "0px", height: "0px", pointerEvents: "none", zIndex: "5" });
      wrap.appendChild(band);
      el.setPointerCapture?.(e.pointerId);
    };
    const move = (e: PointerEvent) => {
      if (!start || !band) return;
      const at = local(start.wrap, e);
      Object.assign(band.style, { left: `${Math.min(at.x, start.x)}px`, top: `${Math.min(at.y, start.y)}px`,
        width: `${Math.abs(at.x - start.x)}px`, height: `${Math.abs(at.y - start.y)}px` });
    };
    const up = (e: PointerEvent) => {
      if (!start) return;
      const at = local(start.wrap, e), slot = pages.current[start.n - 1];
      band?.remove(); band = null;
      const s = start; start = null;
      if (!slot || Math.abs(at.x - s.x) < 4 || Math.abs(at.y - s.y) < 4) return;
      const kx = slot.unscaledW / slot.vw, ky = slot.unscaledH / slot.vh;
      onDrawRegion({ page: s.n, bbox: [Math.min(at.x, s.x) * kx, Math.min(at.y, s.y) * ky, Math.max(at.x, s.x) * kx, Math.max(at.y, s.y) * ky] });
    };
    el.addEventListener("pointerdown", down); el.addEventListener("pointermove", move); el.addEventListener("pointerup", up);
    return () => {
      el.style.cursor = ""; band?.remove();
      el.removeEventListener("pointerdown", down); el.removeEventListener("pointermove", move); el.removeEventListener("pointerup", up);
    };
  }, [onDrawRegion]);

  const isOpen = useCallback(() => findOpenRef.current, []);
  useFindShortcut(openFind, closeFind, stepMatch, isOpen);

  return (
    <div className="pdf-pane">
      {findOpen && (
        <FindBar
          query={query}
          matchAt={matchAt}
          matchN={matchN}
          placeholder="Find in PDF"
          inputRef={findInput}
          onQuery={(q) => { setQuery(q); runSearch(q, 0); }}
          onPrev={() => stepMatch(-1)}
          onNext={() => stepMatch(1)}
          onClose={closeFind}
        />
      )}
      {findOpen && !textReady && <p className="muted" style={{ margin: 4 }}>Indexing PDF text; search results are still loading…</p>}
      <div className="pdf-scroll">
        {err && (
          <p style={{ color: "var(--sev-impossible)" }}>
            Could not render the PDF ({err}).
          </p>
        )}
        {locator && locator.confidence === "none" && pdfBoxes(locator).length === 0 && (
          <p className="muted" style={{ fontSize: 12 }}>
            Location unknown — no page jump, no highlight. We will not invent one.
          </p>
        )}
        {locator && locator.confidence === "page" && pdfBoxes(locator).length === 0 && (
          <p className="muted" style={{ fontSize: 12 }}>
            {locator.method === "placement_page"
              ? `Figure on p. ${locator.page} — we know the page, not a box to paint.`
              : `Page ${locator.page} from numeric tokens — no text box, because the match is not exact enough to mark a cell.`}
          </p>
        )}
        <div ref={host} />
        {nPages > 0 && (
          <p className="muted" style={{ fontSize: 11 }}>{nPages} pages</p>
        )}
      </div>
    </div>
  );
}
