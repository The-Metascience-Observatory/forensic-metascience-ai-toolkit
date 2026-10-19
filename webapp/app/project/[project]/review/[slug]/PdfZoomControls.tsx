"use client";

import type { CSSProperties, ReactNode } from "react";

import { canZoomIn, canZoomOut, zoomLabel } from "@/lib/sourceView";

/** − / current% (fit) / + overlay used by both the paper PDF pane and the
 *  image-item PDF pane. Extra buttons (download, folder) are children. */
export function PdfZoomControls({ zoom, onZoomOut, onZoomIn, onFit, style, children }: {
  zoom: number;
  onZoomOut: () => void;
  onZoomIn: () => void;
  onFit: () => void;
  style?: CSSProperties;
  children?: ReactNode;
}) {
  return (
    <div className="pdf-zoom" role="group" aria-label="Zoom" style={style}>
      <button
        type="button"
        onClick={onZoomOut}
        disabled={!canZoomOut(zoom)}
        title="Zoom out"
        aria-label="Zoom out"
      >
        &minus;
      </button>
      <button
        type="button"
        onClick={onFit}
        title="Fit the page to the pane width"
        style={{ minWidth: 46 }}
      >
        {zoomLabel(zoom)}
      </button>
      <button
        type="button"
        onClick={onZoomIn}
        disabled={!canZoomIn(zoom)}
        title="Zoom in"
        aria-label="Zoom in"
      >
        +
      </button>
      {children}
    </div>
  );
}
