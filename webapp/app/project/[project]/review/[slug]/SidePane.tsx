"use client";

import { useCallback, useRef, useState, type ReactNode, type RefObject } from "react";

/** A pane between the findings and the paper (README, email draft, PubPeer
 *  draft): its own column with a drag gutter on its right edge. The width is
 *  a percentage of the row the panes share; the paper takes what is left.
 *  Each pane's width is a standing preference, kept in `localStorage`. */
const MIN = 12, MAX = 70;
const keyFor = (id: string) => `metascience.review.pane.${id}`;

function readWidth(id: string, def: number): number {
  if (typeof window === "undefined") return def;
  try {
    const n = Number(window.localStorage.getItem(keyFor(id)));
    if (Number.isFinite(n) && n >= MIN && n <= MAX) return n;
  } catch { /* storage blocked: the default */ }
  return def;
}

export function SidePane({ id, label, rowRef, hidden = false, def = 40, children }: {
  id: string;
  /** Names the gutter for assistive technology ("Resize the README pane"). */
  label: string;
  /** The row the percentage is of. */
  rowRef: RefObject<HTMLElement | null>;
  hidden?: boolean;
  def?: number;
  children: ReactNode;
}) {
  // A side pane opens on a click, never in server-rendered HTML, so the
  // stored width can be read on the first render.
  const [pct, setPct] = useState(() => readWidth(id, def));
  const [dragging, setDragging] = useState(false);
  const pctRef = useRef(pct);
  const start = useRef<{ x: number; pct: number } | null>(null);

  const apply = useCallback((n: number) => {
    const v = Math.min(MAX, Math.max(MIN, n));
    pctRef.current = v;
    setPct(v);
  }, []);
  const commit = useCallback(() => {
    try { window.localStorage.setItem(keyFor(id), String(pctRef.current)); } catch { /* fine */ }
  }, [id]);

  return (
    <>
      <section className="side-pane" data-side-pane={id} hidden={hidden} style={{ flexBasis: `${pct}%` }}>
        {children}
      </section>
      {!hidden && (
        <div
          className={`split-gutter${dragging ? " dragging" : ""}`}
          role="separator" aria-orientation="vertical" aria-label={label}
          aria-valuemin={MIN} aria-valuemax={MAX} aria-valuenow={Math.round(pct)} tabIndex={0}
          onPointerDown={(e) => {
            e.preventDefault();
            e.currentTarget.focus();
            e.currentTarget.setPointerCapture(e.pointerId);
            start.current = { x: e.clientX, pct: pctRef.current };
            setDragging(true);
          }}
          onPointerMove={(e) => {
            const row = rowRef.current?.getBoundingClientRect();
            if (e.buttons === 0 || !start.current || !row || row.width <= 0) return;
            apply(start.current.pct + ((e.clientX - start.current.x) / row.width) * 100);
          }}
          onPointerUp={() => { start.current = null; setDragging(false); commit(); }}
          onPointerCancel={() => { start.current = null; setDragging(false); commit(); }}
          onKeyDown={(e) => {
            if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
            e.preventDefault();
            // The page binds j/k and the arrows on `window`; a focused gutter must not leak.
            e.stopPropagation();
            apply(pctRef.current + (e.key === "ArrowRight" ? 2 : -2));
            commit();
          }}
        />
      )}
    </>
  );
}
