"use client";
import { useState } from "react";
import { mediaUrl } from "@/app/images/lib";
import type { ContentSupportData } from "@/app/images/lib";

export function ContentSupport({ data, project, dir }: { data?: ContentSupportData; project: string; dir: string }) {
  const [view, setView] = useState("original");
  if (!data) return null;
  const artifacts = data.artifacts || [];
  const pair = artifacts.filter(a => a.role === view);
  return <section aria-label="Content support diagnostics" style={{borderTop:"1px solid var(--line)",marginTop:12,paddingTop:10}}>
    <h3>Content support · {data.status}</h3>
    <p>{data.note || data.reason}</p>
    {data.reason && data.note && <p>{data.reason}</p>}
    {data.limitations?.map((s,i) => <p className="muted" key={i}>{s}</p>)}
    {data.saved_support && <p>Under saved transform: {data.saved_support.eligible_supporting_pairs} content-eligible correspondences / {data.saved_support.supporting_pairs} supporting correspondences / {data.saved_support.tentative_pairs} tentative pairs. Recomputed points; not the historical detector list.</p>}
    {data.independent_masked_fit && <p>Separate masked fit: {data.independent_masked_fit.status}; {data.independent_masked_fit.inliers ?? "unmeasured"} inliers / {data.independent_masked_fit.tentative_pairs} tentative pairs. This fit may describe a different match.</p>}
    {data.panels?.map((p,i) => <p key={i}>Candidate {"AB"[i]}: {p.mask ? <>{p.mask.eligible_px} eligible / {p.mask.total_px} pixels; {p.mask.excluded_px} excluded. Text detection: {p.mask.text.status}{p.mask.text.engine ? ` (${p.mask.text.engine})` : ""}. {p.mask.text.reason} {p.mask.note}</> : "Mask unavailable"} {p.segmentation?.reason}</p>)}
    {data.agreement && <p>Local agreement: {data.agreement.original_agree_px} original agreeing pixels / {data.agreement.eligible_overlap_px} eligible overlap pixels ({data.agreement.overlap_px} total overlap). Closing adds {data.agreement.closing_added_px} pixels for region visualization; they are not additional agreement.</p>}
    {!!pair.length && <>
      <label>Diagnostic view <select value={view} onChange={e => setView(e.target.value)}>
        <option value="original">Original images</option><option value="matched_points">Saved-transform supporting points</option>
        <option value="furniture">Likely furniture mask</option><option value="content_support">Content-eligible supporting points</option>
      </select></label>
      <p className="muted">Native image coordinates. {view === "furniture" ? "Orange tint marks provisionally masked pixels." : view === "original" ? "Unmodified candidate pixels." : "Orange points have descriptor neighborhoods overlapping the mask; green points pass the mask."} These markings are not a verdict.</p>
      <div style={{display:"flex",gap:12,alignItems:"flex-start"}}>{pair.map(a => <figure key={a.ref} style={{margin:0,width:"50%"}}>
        <figcaption>Candidate {a.side.toUpperCase()}</figcaption>
        <img src={mediaUrl(project,dir,a.ref)} alt={`${view} candidate ${a.side.toUpperCase()}`} style={{width:"100%",height:"auto"}} />
      </figure>)}</div>
    </>}
    {!!data.cell_pairs?.length && <details><summary>Localized comparisons ({data.cell_pairs.length})</summary>
      {data.cell_pairs.map((c,n) => <div key={n} style={{marginTop:12}}>
        <p>{c.eligible_supporting_pairs} content-eligible / {c.supporting_pairs} supporting correspondences. Positions are geometric, not scientific panel labels. Unsplit images use the whole parent.</p>
        <div style={{display:"flex",gap:12}}>{(["a","b"] as const).map((s,i) => {
          const cell = data.panels?.[i].segmentation?.cells[c[s]];
          const art = artifacts.find(a => a.side === s && a.cell === c[s]);
          return art && <figure key={s} style={{margin:0,maxWidth:"48%"}}><figcaption>{s.toUpperCase()} row {cell?.row}, column {cell?.column}</figcaption>
            <img src={mediaUrl(project,dir,art.ref)} alt={`Candidate ${s} cell ${c[s]}`} style={{maxWidth:"100%",height:"auto"}} /></figure>;
        })}</div>
      </div>)}
    </details>}
  </section>;
}
