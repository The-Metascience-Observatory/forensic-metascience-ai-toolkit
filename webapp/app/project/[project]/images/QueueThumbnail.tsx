"use client";

import Link from "next/link";
import { FlipArrow } from "@/app/images/FlipArrow";
import { previewBoxes } from "@/lib/imagePreview";
import { boxCorners, matchDirection } from "@/lib/flipArrow";
import { useEffect, useRef, useState } from "react";
import { itemHref, mediaUrl } from "@/app/images/lib";
import type { Item } from "@/lib/types/images";

/** The row under the pointer and where it is, for the hover preview. */
export type HoverTarget = { it: Item; x: number; y: number };

function thumb(project: string, it: Item): string | null {
  // Archived exhibits may still contain the old explanatory text bands.
  const panel = it.panels.find(p => p.image);
  const rel = panel?.image || it.exhibit;
  const dir = panel?.image ? panel.paper_dir : it.paper.dir;
  return rel ? mediaUrl(project, dir, rel) + "&variant=thumbnail" : null;
}

function QueueThumbnail({src, root, item}: {src: string; item: Item; root: React.RefObject<HTMLDivElement | null>}) {
  const image = useRef<HTMLImageElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const observer = new IntersectionObserver(entries => {
      if (entries.some(e => e.isIntersecting)) { setVisible(true); observer.disconnect(); }
    }, {root: root.current, rootMargin: `${root.current?.clientHeight || 800}px 0px`});
    if (image.current) observer.observe(image.current);
    return () => observer.disconnect();
  }, [root]);
  const side = item.panels.findIndex(p => p.image);
  const ms = item.measurements ?? {};
  const size = side === 0 ? ms.panel_px_a : side === 1 ? ms.panel_px_b : null;
  const clone = item.detector_kind === 'intra_panel_clone';
  const boxes = Array.isArray(size) && size.length === 2 ? previewBoxes(ms, side, size as [number,number], clone) : [];
  return <div style={{position:'relative',width:130,height:60}}><img ref={image} src={visible ? src : undefined} alt="" decoding="async" width={130} height={60}
    style={{width:130,height:60,display:"block",objectFit:"contain",background:"var(--media-bg)"}} />
    {visible && Array.isArray(size) && boxes.length > 0 && <svg viewBox={`0 0 ${size[0]} ${size[1]}`} aria-label="Matching regions"
      style={{position:'absolute',inset:0,width:'100%',height:'100%',pointerEvents:'none'}}>
      {boxes.map((box,i)=><g key={i}>
        <rect x={box[0]} y={box[1]} width={box[2]-box[0]} height={box[3]-box[1]} fill="none" stroke="#00FFDD" strokeWidth={2} vectorEffect="non-scaling-stroke" />
        <FlipArrow points={boxCorners(box)} direction={matchDirection(ms,clone ? i : side,clone)} color="#00FFDD" />
      </g>)}
    </svg>}
  </div>;
}

/** The thumbnail cell of a queue row: the lazily loaded thumbnail linking to
 *  the item, and the hover wiring that opens the preview over the row. */
export function QueueThumbnailCell({ project, selection, it, root, style, onHover }: {
  project: string; selection: string; it: Item; root: React.RefObject<HTMLDivElement | null>;
  style: React.CSSProperties; onHover: (hover: HoverTarget | null) => void;
}) {
  const t = thumb(project, it);
  return (
    <td style={style}
        onMouseEnter={(e) => onHover({ it, x: e.clientX, y: e.clientY })}
        onMouseLeave={() => onHover(null)}>
      {t ? (
        <Link prefetch={false} href={itemHref(project, it.id, selection)}>
          <QueueThumbnail key={t} src={t} item={it} root={root} />
        </Link>
      ) : <span className="muted">no image</span>}
    </td>
  );
}
