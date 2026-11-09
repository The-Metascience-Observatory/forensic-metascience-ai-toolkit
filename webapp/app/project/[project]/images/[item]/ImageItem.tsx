"use client";


import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { type MissedDraft } from "./MissedDuplication";
import { imagePdfBoxes } from "@/lib/imagePdfBoxes";
import { describeTransform, orientationLabel, placementOrientation, toPrinted } from "@/lib/affine";
import {
  parseStoredZoom, ZOOM_FIT, ZOOM_KEY,
} from "@/lib/sourceView";
import { mediaUrl, queueHref } from "@/app/images/lib";
import { ItemLayout } from "./ItemLayout";
import { useItemData } from "./useItemData";
import { useItemKeys } from "./useItemKeys";
import { usePrefetchNeighbours } from "./usePrefetchNeighbours";

export function ImageItem({ project, projectName, itemId }: {
  project: string; projectName: string; itemId: string;
}) {
  const router = useRouter();
  const selection = useSearchParams().get("run") || "latest";
  const [note, setNote] = useState("");
  const data = useItemData({ project, selection, itemId, router, note });
  const { detail, item, nav, prev, next, nextUndecided, go, decide } = data;
  const [detailsOpen,setDetailsOpen]=useState(false);
  const [videoOpen,setVideoOpen]=useState(false);
  const [paperReady,setPaperReady]=useState(false);
  const [side, setSide] = useState<0 | 1>(0);
  const [focusTid, setFocusTid] = useState<string | null>(null);
  const [zoom, setZoom] = useState(ZOOM_FIT);
  const [pdfRefit, setPdfRefit] = useState(0);
  const [missed, setMissed] = useState<MissedDraft | null>(null);
  useEffect(() => {
    setZoom(parseStoredZoom(window.localStorage.getItem(ZOOM_KEY)));
  }, []);
  const applyZoom = useCallback((z: number) => {
    setZoom(z);
    window.localStorage.setItem(ZOOM_KEY, String(z));
  }, []);
  const refitPdf = useCallback(() => {
    applyZoom(ZOOM_FIT);
    setPdfRefit((i) => i + 1);
  }, [applyZoom]);

  const [selectedVideo,setSelectedVideo]=useState<string|null>(null);
  const imageSources = JSON.stringify(item?.panels.map(p => p.image ? mediaUrl(project,p.paper_dir,p.image) : null) || []);
  const [loadedImages,setLoadedImages] = useState<{key:string;images:(HTMLImageElement | null)[]}>({key:"",images:[]});
  // A panel image that fails to load was an empty grey box and nothing else
  // (Dan, 2026-09-14: every panel of a thesis, because no local root was
  // registered). The media route answers a JSON `error` saying why; ask it
  // and show that beside the comparator.
  const [mediaErrors,setMediaErrors] = useState<{key:string;errors:string[]}>({key:"",errors:[]});
  useEffect(() => {
    const sources: (string | null)[] = JSON.parse(imageSources);
    let active=true;
    setLoadedImages({key:imageSources,images:sources.map(()=>null)});
    setMediaErrors({key:imageSources,errors:[]});
    const images=sources.map((src,index)=>{
      if(!src)return null;
      const image=new Image();
      image.onload=()=>{if(active)setLoadedImages(old=>({key:imageSources,images:old.images.map((v,i)=>i===index?image:v)}));};
      image.onerror=()=>{
        if(!active)return;
        fetch(src).then(async r=>{
          const body=r.ok?null:await r.json().catch(()=>null);
          return body && typeof body.error==="string" ? `${body.error} [HTTP ${r.status}]` : `image did not load (HTTP ${r.status})`;
        }).catch(e=>`image did not load (${String(e)})`).then(msg=>{
          if(active)setMediaErrors(old=>({key:imageSources,errors:[...old.errors,`panel ${index+1}: ${msg}`]}));
        });
      };
      image.src=src;
      return image;
    });
    return()=>{active=false;images.forEach(image=>{if(image){image.onload=null;image.onerror=null;if(!image.complete)image.removeAttribute("src");}});};
  },[imageSources]);
  const panelErrors=mediaErrors.key===imageSources?mediaErrors.errors:[];
  const panelImages=loadedImages.key===imageSources?loadedImages.images:[];
  const panelSizes=useMemo(() => panelImages.map(image => image ? [image.naturalWidth,image.naturalHeight] as [number,number] : null),[loadedImages,imageSources]);
  // A PDF may store a stream upside down or mirrored and undo that in its
  // placement matrix; the detector's pixels and measurements are the STORED
  // ones. The comparator shows both panels as printed (`lib/affine`
  // placementOrientation / toPrinted), so it agrees with the PDF pane. Pairs
  // only: a clone's exhibit overlay is drawn in the stored frame.
  const printed=useMemo(()=>{
    const ms0=item?.measurements ?? {};
    const pair=!!item && item.detector_kind!=="intra_panel_clone" && item.panels.length===2;
    const reads=(item?.panels||[]).map((p,i)=>{const size=panelSizes[i];return pair&&size?placementOrientation(p.placements,size):{orientation:null,note:null};});
    const sizeB=panelSizes[1];
    const ms=pair&&sizeB&&panelSizes[0]?toPrinted(ms0,reads[0]?.orientation??null,reads[1]?.orientation??null,sizeB):ms0;
    const notes=reads.map((r,i)=>r.orientation?`${"AB"[i]} is stored ${orientationLabel(r.orientation)} relative to the page`:r.note?`${"AB"[i]}: ${r.note}`:null).filter(Boolean);
    return {reads,ms,notes,raw:ms===ms0?null:describeTransform(ms0)};
  },[item,panelSizes]);
  const printedImages=useMemo(()=>panelImages.map((image,i)=>{
    const o=printed.reads[i]?.orientation;
    if(!image||!o)return image;
    const c=document.createElement("canvas");c.width=o.width;c.height=o.height;
    const ctx=c.getContext("2d");if(!ctx)return image;
    ctx.setTransform(o.m[0],o.m[1],o.m[2],o.m[3],o.m[4],o.m[5]);ctx.drawImage(image,0,0);
    return c;
  }),[panelImages,printed]);
  const pdfMatches=useMemo(()=>item?imagePdfBoxes(item,panelSizes,printed.ms):[],[item,panelSizes,printed]);
  useEffect(()=>{
    setDetailsOpen(false);setVideoOpen(false);setSelectedVideo(null);
  },[item?.id,item?.run_id]);
  // The paper pane mounts one frame after the first item, so the comparison
  // paints first; later items keep it mounted.
  useEffect(()=>{
    if(!item||paperReady)return;
    const frame=requestAnimationFrame(()=>setPaperReady(true));
    return()=>cancelAnimationFrame(frame);
  },[item,paperReady]);
  usePrefetchNeighbours(project, selection, nav);
  useEffect(() => { setNote(item?.decision?.note || ""); setSide(0); setFocusTid(null); }, [item?.id, item?.run_id]);

  const jumpTo = useCallback((s: 0 | 1) => {
    if (!item) return;
    const p = item.panels[s];
    if (!p) return;
    const t = item.targets.find((x) => x.paper_dir === p.paper_dir && x.id.includes(`:${"ab"[s]}:`));
    setSide(s);
    setFocusTid(t ? t.id : null);
  }, [item]);

  useItemKeys({ go, next, prev, nextUndecided, jumpTo, decide, item, project, selection, router });

  if (detail.loading && !item) return <p className="muted" style={{ padding: 12 }}>loading…</p>;
  if(detail.error && !item)return <p role="alert">{detail.error} <button onClick={()=>detail.refresh()}>Retry</button></p>;
  if (!item) return <p style={{ padding: 12 }}>This item is not present in the selected run. <Link href={queueHref(project, selection)}>Back to the queue</Link>.</p>;

  return (
    <ItemLayout {...data} item={item}
                project={project} projectName={projectName} itemId={itemId} selection={selection} router={router}
                detailsOpen={detailsOpen} setDetailsOpen={setDetailsOpen}
                videoOpen={videoOpen} setVideoOpen={setVideoOpen}
                selectedVideo={selectedVideo} setSelectedVideo={setSelectedVideo}
                side={side} jumpTo={jumpTo} focusTid={focusTid}
                zoom={zoom} applyZoom={applyZoom} refitPdf={refitPdf} pdfRefit={pdfRefit} paperReady={paperReady}
                missed={missed} setMissed={setMissed} note={note} setNote={setNote}
                panelErrors={panelErrors} panelSizes={panelSizes} printed={printed} printedImages={printedImages} pdfMatches={pdfMatches} />
  );
}
