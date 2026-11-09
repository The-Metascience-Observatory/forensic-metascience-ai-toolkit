"use client";

import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { brandMetrics, grabCursor, grabSelection, normaliseRect, scaleRect, stageBounds, type Grab, type PixelRect } from "@/lib/cropEditor";
import { blank, drawBrand, pieceRect, placePiece, strokeBox, type Floating } from "./CanvasDraw";

export const MIN_SELECTION_PX = 8;
/** Bright neon outline colours for drawn boxes: name for the tooltip, hex for the stroke. */
export const NEON = [
  ["cyan", "#00FFFF"], ["magenta", "#FF00FF"], ["lime", "#39FF14"], ["yellow", "#FFFF00"],
  ["orange", "#FF6700"], ["hot pink", "#FF1493"], ["electric blue", "#1F8FFF"], ["neon red", "#FF073A"],
] as const;

type Drag = { kind: "select"; x: number; y: number } | { kind: "move"; dx: number; dy: number }
  | { kind: "box"; x: number; y: number }
  | { kind: "scale"; grab: Exclude<Grab, null | "inside">; start: PixelRect; x: number; y: number };
/** How close (in screen pixels) the pointer must be to grab a selection edge. */
const GRAB_PX = 16;
/** Drawn handle size and outline width, in screen pixels. */
const HANDLE_PX = 14, OUTLINE_PX = 1.5;

/** The crop editor over the generated figure: its version history, the
 *  selection, a lifted (floating) piece, the box tool, and the pointer
 *  handlers and drawing that work them. `shown` is the dialog's visibility;
 *  with content to show, the dialog (and its canvas) is mounted. */
export function useCropEditor(shown: boolean) {
  // Every committed version of the image, oldest first; [0] is as generated.
  const [history, setHistory] = useState<HTMLCanvasElement[]>([]);
  const [floating, setFloating] = useState<Floating | null>(null);
  const [selection, setSelection] = useState<PixelRect | null>(null);
  // The "found at the Metascience Observatory" logo, bottom right. Off by default
  // (Dan, 2026-10-22); the checkbox turns it on for a figure that wants it.
  const [brand, setBrand] = useState(false);
  const [copied, setCopied] = useState(false);
  // The box tool: null = select/move; a colour = drag draws an outline in it.
  const [boxColor, setBoxColor] = useState<string | null>(null);
  const [boxDraft, setBoxDraft] = useState<PixelRect | null>(null);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const origin = useRef({ x: 0, y: 0 }); // image -> display-canvas offset of the last draw
  const drag = useRef<Drag | null>(null);
  const content = history[history.length - 1] || null;
  const open = shown && !!content;

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
  const hint = boxColor ? "drag on the image to draw a box in the chosen colour; Esc or 'select' returns to selecting"
    : floating ? "drag the piece to move it, its handles to resize it; click outside it or press Enter to place, Esc to put it back"
    : usable(sel) ? "drag inside the selection to move it, or its handles to resize it (corners keep the proportions)"
    : "drag on the image to select a region";

  return { open, content, history, setHistory, floating, setFloating, selection, setSelection, brand, setBrand,
    copied, setCopied, boxColor, setBoxColor, canvasRef, push, settle, selected, usable, lift, erase, crop, undo,
    onPointerDown, onPointerMove, onPointerUp, sel, edited, scaleTo, pct, hint };
}

export type CropEditor = ReturnType<typeof useCropEditor>;
