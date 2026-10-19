"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ComponentPropsWithoutRef,
  KeyboardEvent as ReactKeyboardEvent,
  PointerEvent as ReactPointerEvent,
  RefObject,
} from "react";

/** One draggable gutter, in the shape `Reviewer` and `SourcePane` already use.
 *
 * Those two grew the same forty lines twice, once per axis; this is that code
 * with the axis as a parameter, so the image item page can have BOTH dividers
 * without a third and fourth copy.
 *
 * Storage is SESSION-scoped on purpose. Pane sizes here are a reading posture
 * for the run of a queue -- the reviewer widens the PDF for a paper with dense
 * figure captions and wants that to hold for the next ninety items -- not a
 * standing preference like the theme or the reviewer's name, which are the
 * things in `localStorage`. It survives the full page loads this app navigates
 * with (`window.location.href`), because `sessionStorage` is per TAB, not per
 * document.
 */

export type SplitAxis = "x" | "y";

function readPct(key: string, def: number, min: number, max: number): number {
  if (typeof window === "undefined") return def;
  try {
    const n = Number(window.sessionStorage.getItem(key));
    if (Number.isFinite(n) && n >= min && n <= max) return n;
  } catch { /* storage blocked: the default is a fine answer */ }
  return def;
}

function storePct(key: string, pct: number): void {
  try { window.sessionStorage.setItem(key, String(pct)); } catch { /* fine */ }
}

export type SplitPane = {
  /** Size of the FIRST pane, as a percentage of the container. */
  pct: number;
  dragging: boolean;
  /** Bumped once each time a drag or key nudge COMMITS.
   *
   *  Canvas and PDF panes here re-fit off their measured box, and measuring
   *  during the drag is the flash loop `PdfPane.refitNonce` documents: the
   *  re-render changes the scrollbar, the scrollbar changes the width, round
   *  again. A settled gesture is a safe moment to re-fit; a moving one is not.
   */
  settled: number;
  /** Put this on the element the percentage is measured against. */
  containerRef: RefObject<HTMLDivElement>;
  /** Spread onto an empty `<div>` sitting between the two panes. */
  separatorProps: ComponentPropsWithoutRef<"div">;
};

export function useSplitPane({ storageKey, axis, def, min, max, label }: {
  storageKey: string;
  axis: SplitAxis;
  def: number;
  min: number;
  max: number;
  label: string;
}): SplitPane {
  const [pct, setPct] = useState(def);
  const [dragging, setDragging] = useState(false);
  const [settled, setSettled] = useState(0);
  const pctRef = useRef(def);
  const containerRef = useRef<HTMLDivElement>(null);

  // Read after mount, never during render: the server has no sessionStorage,
  // and a first paint that disagreed with it would be a hydration mismatch.
  useEffect(() => {
    const n = readPct(storageKey, def, min, max);
    pctRef.current = n;
    setPct(n);
  }, [storageKey, def, min, max]);

  const apply = useCallback((next: number) => {
    const v = Math.min(max, Math.max(min, next));
    pctRef.current = v;
    setPct(v);
  }, [min, max]);

  const onPointerDown = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    // preventDefault stops the drag selecting text -- and, as a side effect,
    // stops the mousedown focusing the gutter, which would leave the arrow
    // keys documented but unreachable after a drag. Focus it back explicitly.
    e.preventDefault();
    e.currentTarget.focus();
    setDragging(true);
    e.currentTarget.setPointerCapture(e.pointerId);
  }, []);

  const onPointerMove = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    if (e.buttons === 0 || !containerRef.current) return;
    const r = containerRef.current.getBoundingClientRect();
    if (axis === "x") {
      if (r.width <= 0) return;
      apply(((e.clientX - r.left) / r.width) * 100);
    } else {
      if (r.height <= 0) return;
      apply(((e.clientY - r.top) / r.height) * 100);
    }
  }, [apply, axis]);

  const onPointerUp = useCallback(() => {
    setDragging(false);
    setSettled((n) => n + 1);
    storePct(storageKey, pctRef.current);
  }, [storageKey]);

  const onKeyDown = useCallback((e: ReactKeyboardEvent<HTMLDivElement>) => {
    const less = axis === "x" ? "ArrowLeft" : "ArrowUp";
    const more = axis === "x" ? "ArrowRight" : "ArrowDown";
    if (e.key !== less && e.key !== more) return;
    e.preventDefault();
    // The page binds j/k/n/1-4 on `window`; a focused gutter must not leak.
    e.stopPropagation();
    apply(pctRef.current + (e.key === more ? 2 : -2));
    setSettled((n) => n + 1);
    storePct(storageKey, pctRef.current);
  }, [apply, axis, storageKey]);

  const separatorProps: ComponentPropsWithoutRef<"div"> = {
    className: `split-gutter${axis === "y" ? " split-gutter-row" : ""}${dragging ? " dragging" : ""}`,
    role: "separator",
    "aria-orientation": axis === "x" ? "vertical" : "horizontal",
    "aria-label": label,
    "aria-valuemin": min,
    "aria-valuemax": max,
    "aria-valuenow": Math.round(pct),
    tabIndex: 0,
    onPointerDown,
    onPointerMove,
    onPointerUp,
    onPointerCancel: onPointerUp,
    onKeyDown,
  };

  return { pct, dragging, settled, containerRef, separatorProps };
}
