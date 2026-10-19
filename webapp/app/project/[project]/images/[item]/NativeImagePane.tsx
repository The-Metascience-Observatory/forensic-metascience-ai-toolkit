"use client";
import { FlipArrow } from "@/app/images/FlipArrow";
import { matchDirection } from "@/lib/flipArrow";
import type { Item } from "@/app/images/lib";
import { useState } from "react";

import { cropPolygonPixels, mediaUrl, nativePaneSentence, type Panel } from "@/app/images/lib";

/** A panel with no PDF placement, shown on the image it actually came from.
 *
 *  A publisher render, a DOCX supplement member or an SI image was never
 *  printed on a page of the main PDF, so the pane used to open that PDF
 *  beside it and let the reader infer a location that does not exist. This
 *  pane shows the parent image (or the panel itself when it IS the parent)
 *  and, for a crop, outlines the crop in the parent's own pixel frame -- the
 *  client twin of `evidence._parent_locator`.
 */
export function NativeImagePane({ project, panel, documentPath, reason, item }: {
  project: string; panel: Panel; documentPath: string | null; reason?: string; item?: Item;
}) {
  const [size, setSize] = useState<[number, number] | null>(null);
  const rel = panel.parent_image || panel.image;
  const src = rel ? mediaUrl(project, panel.paper_dir, rel) : null;
  const isCrop = !!panel.parent_image && !!panel.crop_box;
  const poly = isCrop ? cropPolygonPixels(panel.crop_box, size) : null;
  const side = item?.panels.findIndex(p => p.uid === panel.uid && p.paper_dir === panel.paper_dir) ?? -1;
  const direction = item?.detector_kind === "intra_panel_clone" ? undefined : matchDirection(item?.measurements || {}, side);
  const sentence = reason || nativePaneSentence(documentPath);
  return (
    <div style={{ height: "100%", overflow: "auto", padding: 10, boxSizing: "border-box" }}>
      <p className="muted" role="status" style={{ margin: "0 0 8px", fontSize: 12 }}>{sentence}</p>
      {src ? (
        <div style={{ position: "relative", display: "inline-block", maxWidth: "100%" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt={`native image for ${panel.uid}`}
               style={{ maxWidth: "100%", height: "auto", display: "block" }}
               onLoad={(e) => setSize([e.currentTarget.naturalWidth, e.currentTarget.naturalHeight])} />
          {poly && size && (
            <svg viewBox={`0 0 ${size[0]} ${size[1]}`} preserveAspectRatio="none"
                 style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
              <polygon points={poly.map(([x, y]) => `${x},${y}`).join(" ")}
                       fill="none" stroke="red" strokeWidth={Math.max(2, size[0] / 500)} />
            <FlipArrow points={poly} direction={direction} color="red" />
            </svg>
          )}
          {isCrop && size && !poly && (
            <p className="muted" style={{ fontSize: 11 }}>crop box {JSON.stringify(panel.crop_box)} does not fit inside the parent image ({size[0]}×{size[1]} px); no outline drawn.</p>
          )}
        </div>
      ) : (
        <p className="muted" style={{ fontSize: 12 }}>No native image is available for this panel{panel.image_unavailable_reason ? `: ${panel.image_unavailable_reason}` : "."}</p>
      )}
    </div>
  );
}
