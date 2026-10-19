"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { boxCorners, drawFlipArrow, matchDirection } from "@/lib/flipArrow";
import { DUPLICATION_COLORS } from "@/lib/imagePdfBoxes";

import {
  type Box, type M, type View, fromAffine, fromBoxes, invert, mirrorBox, quadThrough,
  toOriginalB, viewModes,
} from "@/lib/affine";

/**
 * The comparator: both panels on one canvas, B drawn through the recovered
 * transform into A's frame, so a mirrored or rotated pair lines up on screen
 * without a rendered video -- the animator refused exactly those pairs.
 *
 * Views: side-by-side (the two crops AS PRINTED, with the inlier boxes),
 * blink (A and B-in-A's-frame alternating; hold SPACE to see B), overlay
 * (opacity slider), and video (the rendered animation, when the pipeline
 * wrote one). For a clone (one panel, two regions) the exhibit overlay is
 * shown and the two boxed regions are cut out and blinked against each other.
 *
 * Side-by-side keeps both images as printed. By default, corresponding
 * regions use the same thick neon outline. The transform-box toggle restores
 * the original red/green outlines plus the other panel's mapped dashed box.
 *
 * Sizing (Dan, 2026-09-08: "too zoomed in, I have to scroll"): the default
 * FITS the whole comparison into the box the page gives it -- width AND
 * height, two columns in side-by-side -- and the zoom control scales from
 * there (`-` / `=` / `0`). Zoom above fit scrolls inside the box; the page
 * never grows. The video view is sized to the same box.
 *
 * The transform comes from the detector's affine when it carries one
 * (`measurements.affine`, 2x3, mapping A -> B); otherwise from the two
 * inlier boxes as a similarity (scale from box sizes, translation from box
 * corners) -- and that fallback is SAID in the caption, because a guessed
 * alignment must not read as a measured one. When the detector matched
 * against a MIRRORED B (`flip`), its affine and `inlier_box_b` are in that
 * mirrored frame; `lib/affine.toOriginalB` / `mirrorBox` put them back on
 * the panel as printed before anything is drawn.
 */

const ZOOM_STEPS = [0.25, 0.35, 0.5, 0.7, 1, 1.4, 2, 2.8, 4];
const TOOLBAR_PX = 34;
const RED = "#e11";
const GREEN = "#1c1";


export function Comparator({ imgA, imgB: suppliedImgB, srcA, srcB, boxA, boxB, affine, flip = false, transformNote = null,
  labelA, labelB, exhibit, regions, video = null, videoActions, fitNonce = 0, measurements }: {
  measurements?: Record<string, unknown>;
  srcA: string | null; srcB: string | null;
  imgA: HTMLImageElement | null; imgB: HTMLImageElement | null;
  boxA?: Box | null; boxB?: Box | null;
  affine?: unknown;
  /** the detector matched B mirrored left-right: its affine and box are in that frame */
  flip?: boolean;
  /** `describeTransform(measurements)`: "rotation −8.7°, scale 0.951" or null */
  transformNote?: string | null;
  labelA: string; labelB: string;
  /** clone items: the overlay PNG and the two regions (source, copy) in A's frame */
  exhibit?: string | null; regions?: { role: string; bbox: Box; polygon?: number[][] }[] | null;
  /** the rendered animation's media URL, when the pipeline wrote one */
  video?: string | null;
  videoActions?: ReactNode;
  /**
   * Bump to re-fit at the host's CURRENT box. The fit is measured from the
   * parent, and nothing here watches that parent -- a `resize` on the window
   * is the only signal, so a pane the reviewer resized with a divider would
   * keep drawing to the old box. Gesture-driven for the same reason
   * `PdfPane.refitNonce` is: this canvas sits in a scrolling host, so growing
   * it can add the scrollbar that shrinks the host that shrinks the canvas.
   */
  fitNonce?: number;
}) {
  const [mode, setMode] = useState<View | "gif">("side");
  const [showB, setShowB] = useState(false);
  const [hold, setHold] = useState(false);
  const [alpha, setAlpha] = useState(0.5);
  const [hz, setHz] = useState(2);
  const [transformBoxes, setTransformBoxes] = useState(false);
  const boxColor = DUPLICATION_COLORS[0];
  const [zoom, setZoom] = useState(1);          // 1 = fit the box
  const [scaleUsed, setScaleUsed] = useState(1); // px per image px, after fit x zoom
  const [paneH, setPaneH] = useState(0);         // the video's box, measured like the canvas's
  const [videoSecs, setVideoSecs] = useState<number | null>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const canvasB = useRef<HTMLCanvasElement>(null);
  const outer = useRef<HTMLDivElement>(null);
  const toolbar = useRef<HTMLDivElement>(null);
  const isClone = !srcB && !!regions && regions.length >= 2;
  const imgB = isClone ? imgA : suppliedImgB;
  const orientation = useMemo(() => measurements || {flip, affine}, [measurements, flip, affine]);
  const twoCols = mode === "side" && !isClone;
  const [gifUrl, setGifUrl] = useState<string | null>(null);
  const [gifBusy, setGifBusy] = useState(false);
  const [gifError, setGifError] = useState<string | null>(null);
  const gifGeneration = useRef(0);
  const gifSourceKey = JSON.stringify([srcA, srcB, affine, boxA, boxB, regions, flip]);
  const views: (View | "gif")[] = [...viewModes(!!video), ...(gifUrl ? ["gif" as const] : [])];
  useEffect(() => () => { if (gifUrl) URL.revokeObjectURL(gifUrl); }, [gifUrl]);
  useEffect(() => {
    gifGeneration.current++;
    setGifUrl(null); setGifError(null); setGifBusy(false);
    return () => { gifGeneration.current++; };
  }, [imgA, imgB, gifSourceKey]);

  // A view that no longer exists (the item changed under us) falls back to side.
  useEffect(() => { if (!views.includes(mode)) setMode("side"); }, [views, mode]);

  useEffect(() => { setVideoSecs(null); }, [video]);

  /** A -> B as printed. Under `flip` the detector's numbers are in the
   *  mirrored-B frame, so the mirror is composed back on (needs B's width,
   *  hence the wait for `imgB`). `boxBShown` is B's inlier box in the same
   *  as-printed frame. */
  const transform = useMemo<{ m: M | null; guessed: boolean; boxBShown: Box | null }>(() => {
    if (isClone && regions) {
      const measured = fromAffine(affine);
      if (measured) return { m: measured, guessed: false, boxBShown: null };
      const s = regions.find((r) => ["source", "A"].includes(r.role))?.bbox, c = regions.find((r) => ["copy", "B"].includes(r.role))?.bbox;
      if (s && c) return { m: fromBoxes(s, c), guessed: false, boxBShown: null };  // a copy-move is a pure translation
      return { m: null, guessed: true, boxBShown: null };
    }
    const wB = imgB?.width ?? null;
    const unflip = (m: M | null): M | null => (m && flip && wB !== null ? toOriginalB(m, true, wB) : m);
    const boxBShown = boxB ? (flip && wB !== null ? mirrorBox(boxB, wB) : boxB) : null;
    const m = fromAffine(affine);
    if (m) return { m: unflip(m), guessed: false, boxBShown };
    if (boxA && boxB) return { m: unflip(fromBoxes(boxA, boxB)), guessed: true, boxBShown };
    return { m: null, guessed: true, boxBShown };
  }, [affine, boxA, boxB, isClone, regions, flip, imgB]);

  useEffect(() => {
    if (mode !== "blink" || hold) return;
    const t = setInterval(() => setShowB((v) => !v), 1000 / Math.max(0.5, hz));
    return () => clearInterval(t);
  }, [mode, hz, hold]);

  const zoomStep = useCallback((dir: 1 | -1) => {
    setZoom((z) => {
      const i = ZOOM_STEPS.findIndex((v) => Math.abs(v - z) < 1e-6);
      const j = i < 0 ? ZOOM_STEPS.indexOf(1) + dir : i + dir;
      return ZOOM_STEPS[Math.max(0, Math.min(ZOOM_STEPS.length - 1, j))];
    });
  }, []);

  useEffect(() => {
    function down(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === " ") { e.preventDefault(); setHold(true); setShowB(true); }
      if (e.key === "s") setMode("side");
      if (e.key === "b") setMode("blink");
      if (e.key === "o") setMode("overlay");
      if (e.key === "v" && video) setMode("video");
      if (e.key === "-" || e.key === "_") zoomStep(-1);
      if (e.key === "=" || e.key === "+") zoomStep(1);
      if (e.key === "0") setZoom(1);
    }
    function up(e: KeyboardEvent) { if (e.key === " ") { setHold(false); } }
    window.addEventListener("keydown", down); window.addEventListener("keyup", up);
    return () => { window.removeEventListener("keydown", down); window.removeEventListener("keyup", up); };
  }, [zoomStep, video]);

  /** The box the page gives the comparator: its parent's client box, minus
   *  the toolbar and padding. Measured from the DOM, so the parent must have
   *  a height of its own (the page gives it a fixed share). */
  const hostBox = useCallback((): { W: number; H: number } => {
    const host = outer.current?.parentElement;
    const W = Math.max(200, (host?.clientWidth || 800) - 20);
    // the toolbar wraps to two lines when the status sentence is long, so measure it
    const tb = toolbar.current?.offsetHeight || TOOLBAR_PX;
    const H = Math.max(120, (host?.clientHeight || 420) - tb - 30);
    return { W, H };
  }, []);

  /** px per image px that fits A's frame (and B beside it, in side mode)
   *  into the host box. */
  const fitScale = useCallback((): number => {
    if (!imgA) return 1;
    const { W, H } = hostBox();
    const frameW = twoCols && imgB ? imgA.width + imgB.width * (imgA.height / Math.max(1, imgB.height)) : imgA.width;
    // side by side: B is shown at A's height, so the pair's width is A plus B rescaled to that height
    const gap = twoCols ? 8 : 0;
    return Math.min((W - gap) / frameW, H / imgA.height);
    // fitNonce is not read above: it is the caller saying the host box moved.
  }, [imgA, imgB, twoCols, hostBox, fitNonce]);

  useEffect(() => {
    if (mode !== "video" && mode !== "gif") return;
    const on = () => setPaneH(hostBox().H);
    on();
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, [mode, hostBox, fitNonce]);

  const draw = useCallback((exportFrame?: { canvas: HTMLCanvasElement; showB: boolean }) => {
    const cv = exportFrame?.canvas || canvas.current;
    const drawingMode = exportFrame ? "blink" : mode;
    const drawingB = exportFrame ? exportFrame.showB : showB;
    if (!cv || !imgA || drawingMode === "video" || drawingMode === "gif") return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    const frameW = imgA.width;
    const frameH = imgA.height;
    const scale = exportFrame ? Math.min(1, 1024 / Math.max(frameW, frameH)) : fitScale() * zoom;
    if (!exportFrame) setScaleUsed((s) => (Math.abs(s - scale) < 1e-4 ? s : scale));
    cv.width = Math.max(1, Math.round(frameW * scale));
    cv.height = Math.max(1, Math.round(frameH * scale));
    cv.style.width = `${cv.width}px`;
    cv.style.height = `${cv.height}px`;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.scale(scale, scale);
    const m = transform.m;
    const inv = m ? invert(m) : null;
    const boxBShown = transform.boxBShown;
    const drawBInA = (a: number) => {
      if (!imgB) return;
      ctx.save();
      ctx.globalAlpha = a;
      if (isClone && regions) {
        const box = regions.find(r => ["A", "source"].includes(r.role))?.bbox;
        if (box) { ctx.beginPath(); ctx.rect(box[0], box[1], box[2]-box[0], box[3]-box[1]); ctx.clip(); }
      }
      if (inv) {
        // B pasted into A's frame: for a clone this is the COPY region
        // shifted back over the SOURCE region's spot.
        ctx.transform(inv[0], inv[1], inv[2], inv[3], inv[4], inv[5]);
        ctx.drawImage(imgB, 0, 0);
      } else {
        ctx.drawImage(imgB, 0, 0, imgA.width, imgA.height);
      }
      ctx.restore();
    };
    if (drawingMode === "blink") {
      if (drawingB && imgB) { if (isClone) ctx.drawImage(imgA, 0, 0); else { ctx.fillStyle = "#000"; ctx.fillRect(0, 0, frameW, frameH); } drawBInA(1); }
      else ctx.drawImage(imgA, 0, 0);
    } else if (drawingMode === "overlay") {
      ctx.drawImage(imgA, 0, 0);
      drawBInA(alpha);
    } else {
      ctx.drawImage(imgA, 0, 0);
    }
    // Keep outlines a fixed screen thickness at every image scale.
    const colorA = transformBoxes ? RED : boxColor;
    const colorB = transformBoxes ? GREEN : boxColor;
    const solid = (c: CanvasRenderingContext2D, px: number, b: Box | null | undefined, color: string, direction = isClone ? undefined : matchDirection(orientation, 0)) => {
      if (!b) return;
      c.save();
      c.lineWidth = (transformBoxes ? 2 : 8) / px; c.strokeStyle = color; c.setLineDash([]);
      c.strokeRect(b[0], b[1], b[2] - b[0], b[3] - b[1]);
      c.restore();
      drawFlipArrow(c, boxCorners(b), color, direction, px);
    };
    const mapped = (c: CanvasRenderingContext2D, px: number, b: Box | null | undefined, mm: M | null, color: string, direction = matchDirection(orientation, 1, isClone)) => {
      if (!b || !mm) return;
      const q = quadThrough(b, mm);
      c.save();
      c.lineWidth = (transformBoxes ? 2 : 8) / px; c.strokeStyle = color;
      c.setLineDash(transformBoxes ? [7 / px, 5 / px] : []);
      c.beginPath();
      q.forEach(([X, Y], i) => { if (i === 0) c.moveTo(X, Y); else c.lineTo(X, Y); });
      c.closePath(); c.stroke();
      c.restore();
      drawFlipArrow(c, q, color, direction, px);
    };
    if (isClone && regions) {
      for (const [index, region] of regions.entries()) {
        const color = index === 0 ? RED : GREEN;
        const polygon = region.polygon;
        if (polygon && polygon.length >= 3 && polygon.every(p => p.length === 2 && p.every(Number.isFinite))) {
          ctx.save(); ctx.strokeStyle = color; ctx.lineWidth = 3 / scale; ctx.setLineDash([]);
          ctx.beginPath(); polygon.forEach(([x,y], i) => i ? ctx.lineTo(x,y) : ctx.moveTo(x,y));
          ctx.closePath(); ctx.stroke(); ctx.restore();
        } else solid(ctx, scale, region.bbox, color, undefined);
        drawFlipArrow(ctx, boxCorners(region.bbox), color, matchDirection(orientation, index, true), scale);
        ctx.save(); ctx.fillStyle = color; ctx.font = `bold ${18 / scale}px sans-serif`;
        ctx.fillText(index === 0 ? "A" : "B", region.bbox[0], Math.max(18 / scale, region.bbox[1] - 5 / scale));
        ctx.restore();
      }
    } else if (drawingMode === "side") {
      solid(ctx, scale, boxA || null, colorA);
      if (transformBoxes) mapped(ctx, scale, boxBShown, inv, GREEN);
    } else if (drawingMode === "overlay") {
      solid(ctx, scale, boxA || null, colorA);
      mapped(ctx, scale, boxBShown, inv, colorB);
    } else if (drawingB) {
      mapped(ctx, scale, boxBShown, inv, colorB);
    } else {
      solid(ctx, scale, boxA || null, colorA);
    }
    // B's own canvas (side by side): B AS PRINTED at A's displayed height,
    // its own box solid green, A's box through the affine dashed red.
    const cvB = canvasB.current;
    if (!exportFrame && cvB && imgB && twoCols) {
      const sB = (imgA.height * scale) / Math.max(1, imgB.height);
      cvB.width = Math.max(1, Math.round(imgB.width * sB));
      cvB.height = Math.max(1, Math.round(imgA.height * scale));
      cvB.style.width = `${cvB.width}px`;
      cvB.style.height = `${cvB.height}px`;
      const cb = cvB.getContext("2d");
      if (cb) {
        cb.setTransform(1, 0, 0, 1, 0, 0);
        cb.clearRect(0, 0, cvB.width, cvB.height);
        cb.scale(sB, sB);
        cb.drawImage(imgB, 0, 0);
        solid(cb, sB, boxBShown, colorB, matchDirection(orientation, 1, isClone));
        if (transformBoxes) mapped(cb, sB, boxA || null, m, RED, matchDirection(orientation, 0, isClone));
      }
    }
  }, [imgA, imgB, mode, showB, alpha, transform, isClone, regions, fitScale, zoom, boxA, twoCols, transformBoxes, boxColor, orientation]);

  useEffect(() => { draw(); }, [draw]);
  useEffect(() => {
    const on = () => draw();
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, [draw]);

  const generateGif = async () => {
    if (gifBusy || !imgA || !imgB) return;
    const generation = ++gifGeneration.current;
    setGifBusy(true); setGifError(null);
    try {
      const { GIFEncoder, quantize, applyPalette } = await import("gifenc");
      if (generation !== gifGeneration.current) return;
      const output = GIFEncoder();
      const frame = document.createElement("canvas");
      for (const showB of [false, true]) {
        draw({ canvas: frame, showB });
        const context = frame.getContext("2d");
        if (!context) throw new Error("The browser could not render the GIF.");
        const { data } = context.getImageData(0, 0, frame.width, frame.height);
        const palette = quantize(data, 256);
        output.writeFrame(applyPalette(data, palette), frame.width, frame.height,
          { palette, delay: 1000 / hz, repeat: 0 });
        // Yield between frames so navigation and the progress label remain responsive.
        await new Promise(resolve => setTimeout(resolve, 0));
        if (generation !== gifGeneration.current) return;
      }
      output.finish();
      const bytes = new Uint8Array(output.bytes());
      setGifUrl(URL.createObjectURL(new Blob([bytes], { type: "image/gif" })));
      setMode("gif");
    } catch (error) {
      if (generation === gifGeneration.current)
        setGifError(error instanceof Error ? error.message : "GIF generation failed.");
    } finally {
      if (generation === gifGeneration.current) setGifBusy(false);
    }
  };

  const status = (() => {
    if (mode === "gif") return "";
    if (mode === "video") {
      return "rendered animation: title card, side by side, warp, blink — the warp is in the video by design; the side view above never transforms a pixel";
    }
    const parts: string[] = [];
    if (matchDirection(orientation, 0, isClone)) parts.push("arrows mark a reflection");
    if (isClone) parts.push("regions A/B; copying direction is unknown");
    if (mode !== "side" || transformBoxes) {
      if (!transform.m) parts.push("no alignment available; B is stretched onto A");
      else if (transform.guessed) parts.push("alignment GUESSED from the inlier boxes (no affine recorded)");
      else if (transformNote) parts.push(transformNote);
    } else if (!isClone && transformNote && transformNote !== "translation only") {
      // Side mode draws no warp, and arrows mark only reflections, so name the
      // recorded transform (e.g. a half-turn) here.
      parts.push(`B: ${transformNote}`);
    }
    if (mode === "blink") parts.push(`showing ${showB ? labelB : labelA}`);
    return parts.join(" · ");
  })();

  return (
    <div ref={outer}>
      <div ref={toolbar} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12, marginBottom: 6, flexWrap: "wrap",
                    minHeight: TOOLBAR_PX - 6 }}>
        {views.map((m) => (
          <button key={m} type="button" onClick={() => setMode(m)}
                  className={m === "video" ? "primary" : undefined}
                  style={{ fontWeight: mode === m ? 700 : 400,
                           outline: mode === m ? "2px solid var(--accent)" : undefined,
                           outlineOffset: mode === m ? 1 : undefined }}
                  title={m === "side" ? "s" : m === "blink" ? "b — hold SPACE to see B" : m === "overlay" ? "o"
                         : m === "gif" ? "View the generated blink GIF" : "v — the rendered animation for this match"}>
            {m === "video" ? `▶ View video${videoSecs !== null ? ` · ${videoSecs} s` : ""}` : m === "gif" ? "View GIF" : m}
          </button>
        ))}
        {videoActions || (!video && <span className="muted">no video rendered</span>)}
        <button type="button" onClick={generateGif} disabled={gifBusy || !imgA || !imgB}
                title="Generate a looping GIF using the blink alignment and speed">
          {gifBusy ? "Generating GIF…" : "Generate GIF"}
        </button>
        {gifUrl && <a className="btn" href={gifUrl} download="blink-comparison.gif">Download GIF</a>}
        {gifError && <span role="alert">{gifError}</span>}
        {mode !== "video" && mode !== "gif" && (
          <span style={{ display: "inline-flex", gap: 2, alignItems: "center", marginLeft: 6 }}>
            <button type="button" onClick={() => zoomStep(-1)} title="zoom out (-)">−</button>
            <button type="button" onClick={() => zoomStep(1)} title="zoom in (=)">+</button>
            <span className="muted" style={{ marginLeft: 4 }}>{Math.round(zoom * 100)}%</span>
          </span>
        )}
        {mode !== "video" && mode !== "gif" && (
          <>
            <button type="button" aria-pressed={transformBoxes}
                    onClick={() => setTransformBoxes((v) => !v)}
                    title="Show red/green matched boxes and dashed transformed boxes"
                    style={{ fontWeight: transformBoxes ? 700 : 400 }}>
              Show transform boxes
            </button>

          </>
        )}
        {mode === "blink" && (
          <label>Hz <input type="range" min={0.5} max={6} step={0.5} value={hz}
                           onChange={(e) => setHz(Number(e.target.value))} /> {hz}</label>
        )}
        {mode === "overlay" && (
          <label>B opacity <input type="range" min={0} max={1} step={0.05} value={alpha}
                                  onChange={(e) => setAlpha(Number(e.target.value))} /> {alpha.toFixed(2)}</label>
        )}
        <span className="muted">{status}</span>
      </div>
      {mode === "gif" && gifUrl ? (
        <img src={gifUrl} alt="Generated blink comparison" style={{ display: "block", width: "100%",
          maxHeight: paneH || undefined, objectFit: "contain", background: "var(--media-bg)" }} />
      ) : mode === "video" && video ? (
        <video key={video} src={video} controls autoPlay
               onLoadedMetadata={e => { if (Number.isFinite(e.currentTarget.duration)) setVideoSecs(Math.round(e.currentTarget.duration)); }}
               style={{ display: "block", width: "100%", maxHeight: paneH || undefined, objectFit: "contain",
                        background: "var(--media-bg)" }} />
      ) : twoCols ? (
        <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
          <figure style={{ margin: 0, flex: "0 0 auto" }}>
            <figcaption style={{ color: "#000", fontSize: 18, fontWeight: 700, marginBottom: 4 }}>
              {labelA}
            </figcaption>
            <canvas ref={canvas} style={{ display: "block", background: "var(--media-bg)" }} />
          </figure>
          <figure style={{ margin: 0, flex: "0 0 auto" }}>
            <figcaption style={{ color: "#000", fontSize: 18, fontWeight: 700, marginBottom: 4 }}>
              {labelB}
            </figcaption>
            {srcB ? <canvas ref={canvasB} style={{ display: "block", background: "var(--media-bg)" }} />
                  : <span className="muted">no image for B</span>}
          </figure>
        </div>
      ) : (
        <div>
          <canvas ref={canvas} style={{ display: "block", background: "var(--media-bg)" }} />
          {isClone && exhibit && mode === "side" && transformBoxes && (
            <figure style={{ margin: "8px 0 0" }}>
              <img src={exhibit} alt="" style={{ display: "block", width: imgA ? Math.round(imgA.width * scaleUsed) : undefined,
                                                background: "var(--media-bg)" }} />
              <figcaption className="muted" style={{ fontSize: 11 }}>
                detector overlay — red = A, green = B; copying direction unknown
              </figcaption>
            </figure>
          )}
        </div>
      )}
    </div>
  );
}
