"use client";

import { useEffect, useState } from "react";
import { useItem } from "./useFeed";
import { PanelPreview } from "./PanelPreview";
import { type Item, mediaUrl } from "./lib";

/** Dan, 2026-09-08: hovering a thumbnail shows a MUCH larger version beside
 *  the cursor, so a row can be judged without opening it. Fixed-position,
 *  pointer-events off (so it never steals the hover it depends on), placed
 *  on whichever side of the cursor has room, clamped to the viewport. */
export function HoverPreview({ project, it, x, y }: { project: string; it: Item; x: number; y: number }) {
  // Queue summaries intentionally omit geometry. Fetch only the hovered
  // item's exact run, using the same bounded detail cache as the item page.
  const detail = useItem(project, it.run_id, "image_forensics", it.id);
  const shown = detail.item || it;
  const panels = shown.panels.map((panel, side) => ({panel, side})).filter(({panel}) => panel.image);
  const [point, setPoint] = useState({ x, y });
  useEffect(() => {
    let frame = 0;
    const move = (e: MouseEvent) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setPoint({ x: e.clientX, y: e.clientY }));
    };
    window.addEventListener("mousemove", move);
    return () => { cancelAnimationFrame(frame); window.removeEventListener("mousemove", move); };
  }, []);
  x = point.x; y = point.y;
  if (!panels.length) return null;
  const vw = typeof window === "undefined" ? 1600 : window.innerWidth;
  const vh = typeof window === "undefined" ? 1000 : window.innerHeight;
  const w = Math.min(Math.round(vw * 0.62), 1100);
  const h = Math.round(vh * 0.82);
  const left = x + 28 + w <= vw ? x + 28 : Math.max(8, x - 28 - w);
  const top = Math.max(8, Math.min(y - Math.round(h * 0.35), vh - h - 8));
  return (
    <div role="tooltip" aria-label="Image comparison preview" style={{ position: "fixed", left, top, width: w, maxHeight: h, zIndex: 50, pointerEvents: "none",
                  background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 6,
                  boxShadow: "0 8px 30px rgba(0,0,0,0.35)", padding: 8, overflow: "hidden" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "flex-start", justifyContent: "center" }}>
        {panels.map(({panel, side}) => (
          <PanelPreview key={`${panel.uid}:${panel.image}`} src={mediaUrl(project, panel.paper_dir, panel.image!)}
            label={`${"AB"[side] || side + 1} · ${panel.figure_label || panel.paper_dir}`}
            measurements={shown.measurements || {}} side={side}
            clone={shown.detector_kind === "intra_panel_clone"} pending={detail.loading || !!detail.error} maxHeight={h - 100} />
        ))}
      </div>
      <div className="muted" style={{fontSize:11, marginTop:4}}>
        {detail.loading ? "Loading match regions…" : detail.error ? "Match regions unavailable" : "Outlines mark the recorded matching regions."}
      </div>
      <div className="mono" style={{ fontSize: 11, marginTop: 4, overflow: "hidden", textOverflow: "ellipsis",
                                     whiteSpace: "nowrap" }}>
        {it.id} · {it.figure_labels.join(" / ") || "unlabelled"} · {it.detector_kind}
      </div>
    </div>
  );
}
