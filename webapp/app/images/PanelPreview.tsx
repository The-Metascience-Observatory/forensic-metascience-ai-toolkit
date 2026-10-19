"use client";

import { useState } from "react";
import { FlipArrow } from "./FlipArrow";
import { boxCorners, matchDirection } from "@/lib/flipArrow";
import { previewBoxes } from "@/lib/imagePreview";
import { DUPLICATION_COLORS } from "@/lib/imagePdfBoxes";

/** SVG shares the image's exact rectangle and native coordinate system. */
export function PanelPreview({src, label, measurements, side, clone, pending, maxHeight}: {
  src: string; label: string; measurements: Record<string, unknown>;
  side: number; clone: boolean; pending: boolean; maxHeight: number;
}) {
  const [size, setSize] = useState<[number, number] | null>(null);
  const [failed, setFailed] = useState(false);
  const boxes = size ? previewBoxes(measurements, side, size, clone) : [];
  return <figure style={{margin:0, minWidth:0, flex:"1 1 0", textAlign:"center"}}>
    {failed ? <p className="muted">Panel image unavailable</p> :
      <div style={{position:"relative", width:"100%", aspectRatio:size ? `${size[0]} / ${size[1]}` : "1", maxHeight, lineHeight:0}}>
        <img src={src} alt={label} onLoad={e => setSize([e.currentTarget.naturalWidth, e.currentTarget.naturalHeight])}
          onError={() => setFailed(true)}
          style={{position:"absolute", inset:0, display:"block", width:"100%", height:"100%", objectFit:"contain", background:"var(--media-bg)"}} />
        {size && boxes.length > 0 && <svg aria-label="Matching regions" viewBox={`0 0 ${size[0]} ${size[1]}`}
          style={{position:"absolute", inset:0, width:"100%", height:"100%", overflow:"hidden"}}>
          {boxes.map(([x0,y0,x1,y1],i) => <g key={i}>
            <rect x={x0} y={y0} width={x1-x0} height={y1-y0} fill="none" stroke="#111"
              strokeWidth={6} vectorEffect="non-scaling-stroke" />
            <rect data-preview-box x={x0} y={y0} width={x1-x0} height={y1-y0} fill="none"
              stroke={DUPLICATION_COLORS[0]} strokeWidth={3} vectorEffect="non-scaling-stroke" />
          <FlipArrow points={boxCorners([x0,y0,x1,y1])} direction={matchDirection(measurements, clone ? i : side, clone)} color={DUPLICATION_COLORS[0]} />
          </g>)}
        </svg>}
      </div>}
    <figcaption className="muted" style={{fontSize:11, marginTop:4, overflowWrap:"anywhere"}}>
      {label}
      {size && !pending && !boxes.length && <div>No saved region coordinates</div>}
    </figcaption>
  </figure>;
}
