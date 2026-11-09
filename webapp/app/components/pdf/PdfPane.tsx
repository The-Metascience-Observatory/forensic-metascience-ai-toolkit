"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { ImagePdfBox } from "@/lib/imagePdfBoxes";
import { boxesOf } from "@/lib/targets";
import { FindBar, useFindShortcut } from "@/app/components/FindBar";
import { findMatches, type Match, type PageSlot } from "./textLayer";
import { paintFindings, paintHits, type PdfLocator } from "./paintHits";
import { usePdfDocument } from "./usePdfDocument";

export type DrawnRegion = { page: number; bbox: [number, number, number, number] };

export function PdfPane({ url, locator, label, severity, focusTargetId,
  zoom = 1, refitNonce = 0, imageBoxes = [], onDrawRegion = null }: {
  url: string;
  imageBoxes?: ImagePdfBox[];
  /** While set, dragging on a page draws a box and reports it in PDF points
   *  (top-left origin, the same coordinates as `imageBoxes`). */
  onDrawRegion?: ((region: DrawnRegion) => void) | null;
  locator: PdfLocator | null;
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

  const { err, nPages, ready, textReady } = usePdfDocument({
    url, zoom, refitNonce, locator, host, pages,
    findOpenRef, findInput, matchAtRef, runSearch, closeFind,
  });

  useEffect(() => {
    if (!ready) return;
    const focusPage = paintFindings(pages.current, { locator, label, severity, focusTargetId, imageBoxes });
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
        {locator && locator.confidence === "none" && boxesOf(locator).length === 0 && (
          <p className="muted" style={{ fontSize: 12 }}>
            Location unknown — no page jump, no highlight. We will not invent one.
          </p>
        )}
        {locator && locator.confidence === "page" && boxesOf(locator).length === 0 && (
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
