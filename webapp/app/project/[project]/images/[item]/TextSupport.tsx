'use client';

import {useState} from 'react';
import {mediaUrl, type Item} from '@/app/images/lib';

type Box = {box:number[];text:string;confidence:number;rotation:number};
type Localization = {polygons?:number[][][];eligibility?:{applied:boolean;policy:string;reason?:string};provenance?:{engine?:string;model_sha256?:string;device?:string};status:string;reason:string;boxes?:Box[];size?:number[];mask_fraction?:number;engine?:string;engine_version?:string};
type Support = {status:string;reason:string;policy?:string;demote?:boolean;would_demote?:boolean;
  n_inliers?:number;text_inliers_both?:number;nontext_inliers?:number;inlier_floor?:number;
  uid_a?:string;uid_b?:string;a?:Localization;b?:Localization};

export function TextSupport({value,item,project}:{value:unknown;item:Item;project:string}) {
  const [showText,setShowText]=useState(false);
  if (!value || typeof value !== 'object') return <p className="muted">Text support: not measured.</p>;
  const s=value as Support;
  return <section aria-label="Text support">
    <h3>Text support</h3>
    <p><a href={`/project/${encodeURIComponent(project)}/images/text-regions?run=${encodeURIComponent(item.run_id)}`}>Audit all panels in this run</a></p>
    <label style={{display:'flex',alignItems:'center',gap:8}}>
      <input type="checkbox" role="switch" checked={showText} onChange={event=>setShowText(event.target.checked)}/>
      Show excluded text regions
    </label>
    <p>{s.demote ? 'Retained as text-label context.' : s.would_demote ?
      'Diagnostic only: the match appears to be supported by text labels. Classification unchanged.' :
      s.status==='measured' ? 'Text-only support was not established.' : 'Text support was not measured reliably.'}</p>
    <p className="muted">{s.reason}</p>
    {s.status==='measured' && s.n_inliers!=null && <p>{s.text_inliers_both} of {s.n_inliers} matching points lie in recognized text in both panels.
      {' '}{s.nontext_inliers} remain outside text in both panels{s.inlier_floor!=null && ` (required count: ${s.inlier_floor})`}.</p>}
    <div style={{display:'flex',flexWrap:'wrap',gap:12}}>
      {(['a','b'] as const).map(side=>{
        const loc=s[side],uid=side==='a'?s.uid_a:s.uid_b;
        const panel=item.panels.find(p=>p.uid===uid);
        if(!loc)return null;
        const [w,h]=loc.size || [];
        return <div key={side} style={{maxWidth:320}}>
          <b>Candidate {side.toUpperCase()}</b>
          <p className="muted">{loc.status}: {loc.reason}{loc.mask_fraction!=null && ` · ${(loc.mask_fraction*100).toFixed(1)}% text mask`}</p>
          {loc.eligibility && <p className="muted">{loc.eligibility.applied ? 'Text exclusion applied.' : 'Detected regions only — not applied.'} {loc.eligibility.reason}</p>}
          {panel?.image && w>0 && h>0 && <svg role="img" aria-label={`Recognized text boxes in candidate ${side.toUpperCase()}`} viewBox={`0 0 ${w} ${h}`} style={{width:300,maxWidth:'100%'}}>
            <image href={mediaUrl(project,panel.paper_dir,panel.image)} width={w} height={h}/>
            {showText && (loc.boxes || []).map((r,i)=><rect key={i} x={r.box[0]} y={r.box[1]} width={r.box[2]-r.box[0]} height={r.box[3]-r.box[1]} fill="none" stroke="#ffad32" strokeWidth={2} vectorEffect="non-scaling-stroke"><title>{r.text} ({r.confidence}%)</title></rect>)}
            {showText && (loc.polygons || []).map((polygon,i)=><polygon key={`polygon-${i}`} points={polygon.map(p=>p.join(',')).join(' ')} fill="rgba(255,173,50,.2)" stroke="#ffad32" strokeWidth={2} strokeDasharray={loc.eligibility?.applied ? undefined : '5 3'} vectorEffect="non-scaling-stroke"><title>{loc.eligibility?.applied ? 'Excluded text' : 'Detected text, not applied'}</title></polygon>)}
          </svg>}
          <p>{loc.polygons ? `${loc.polygons.length} detected text regions` : (loc.boxes || []).map(r=>r.text).join(' · ') || (loc.status==='measured' ? 'No confidently recognized text' : 'Not measured')}</p>
          <p className="muted">{loc.engine || loc.provenance?.engine} {loc.engine_version}</p>
          {loc.provenance?.device && <p className="muted">Localization backend: {loc.provenance.device}</p>}
        </div>;
      })}
    </div>
  </section>;
}
