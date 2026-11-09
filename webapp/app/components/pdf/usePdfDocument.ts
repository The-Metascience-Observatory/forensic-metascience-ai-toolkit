import { loadPdfjs } from "@/lib/pdfjs";
import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";

import type { PDFDocumentProxy } from "pdfjs-dist";
import { boxesOf } from "@/lib/targets";
import { pageText, type PageSlot } from "./textLayer";
import type { PdfLocator } from "./paintHits";

/** Opens `url` through pdf.js and fills `host` with one placeholder per page,
 *  rasterising only the pages in view (an IntersectionObserver, 600px about
 *  the scroll root; a page that leaves is cleared) nearest the locator's page
 *  first, then indexes every page's text into `pages` for find. `zoom` and
 *  `refitNonce` re-render every page at the host's current width; why the
 *  re-fit is a gesture and not a ResizeObserver is on the `refitNonce` prop
 *  in `PdfPane`. */
export function usePdfDocument({ url, zoom, refitNonce, locator, host: hostRef, pages: pagesRef,
  findOpenRef, findInput, matchAtRef, runSearch, closeFind }: {
  url: string;
  zoom: number;
  refitNonce: number;
  locator: PdfLocator | null;
  host: RefObject<HTMLDivElement | null>;
  pages: RefObject<PageSlot[]>;
  findOpenRef: RefObject<boolean>;
  findInput: RefObject<HTMLInputElement | null>;
  matchAtRef: RefObject<number>;
  runSearch: (q: string, at?: number) => void;
  closeFind: () => void;
}) {
  const [err, setErr] = useState<string | null>(null);
  const [nPages, setNPages] = useState(0);
  const [pdfDocument, setDocument] = useState<PDFDocumentProxy | null>(null);
  const latestLocator = useRef(locator);
  latestLocator.current = locator;
  const [textReady, setTextReady] = useState(false);
  const [ready, setReady] = useState(false);

  // Document lifetime is independent of zoom, pane width and finding selection.
  useEffect(() => {
    let gone = false;
    let task: import("pdfjs-dist").PDFDocumentLoadingTask | undefined;
    setDocument(null); setErr(null); setReady(false);
    void loadPdfjs().then(async (pdfjs) => {
      if (gone) return;
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
    const hostEl = hostRef.current;
    pagesRef.current = [];
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
      const pdfjs = await loadPdfjs();
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
      pagesRef.current = slots;
      const loc = latestLocator.current;
      firstPage = Math.max(0, Math.min(pdf.numPages - 1, (loc?.page || boxesOf(loc)[0]?.page || 1) - 1));
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
      hostEl.innerHTML = ""; pagesRef.current = [];
    };
  }, [pdfDocument, zoom, refitNonce, closeFind, runSearch, hostRef, pagesRef, findOpenRef, findInput, matchAtRef]);

  return { err, nPages, ready, textReady };
}
