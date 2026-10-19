'use client';
import {useEffect,useRef,useState} from 'react';
import {mediaUrl} from '@/app/images/lib';

type Consumer={consumer:string;stage?:string;size?:number[];status:string;policy:string;applied:boolean;reflected:boolean;chrome_mask_applied:boolean;remaining_features?:number;excluded_features?:number};
type Usage=Consumer & {excluded_feature_footprints?:number[][];footprint?:unknown;reason?:string;sample_type?:string;excluded_samples?:number;remaining_samples?:number;mask_bits?:string;mask_fraction?:number;analysis_size?:number[];to_analysis?:number[][]};
type Panel={timing?:unknown;coordinates?:unknown;consumers?:Consumer[];uid:string;paper:string;run:string;image?:string;localization?:string;status:string;policy:string;rollout?:{scientific_acceptance?:string};crop_box?:number[];pixel_source?:unknown;provenance?:unknown};
type Localization={status:string;reason?:string;size?:number[];analysis_size?:number[];to_analysis?:number[][];polygons?:number[][][];mask_fraction?:number;mask_bits?:string;pixel_sha256?:string;provenance?:{device?:string;execution?:{runtime?:{hardware?:{name?:string}}}}};
type PageData={panels:Panel[];total:number;reason?:string;pagination?:{next_offset:number|null}};
function RasterMask({record,effective=false}:{record:Localization;effective?:boolean}) {
  const canvas=useRef<HTMLCanvasElement>(null);
  const [error,setError]=useState('');
  useEffect(()=>{
    let cancelled=false;
    setError('');
    async function draw() {
      if(!record.mask_bits || !record.size)return;
      const [w,h]=record.size;
      if(!Number.isInteger(w) || !Number.isInteger(h) || w<1 || h<1 || w*h>200_000_000)throw Error('Invalid saved mask dimensions');
      const compressed=Uint8Array.from(atob(record.mask_bits),c=>c.charCodeAt(0));
      const stream=new Blob([compressed]).stream().pipeThrough(new DecompressionStream('deflate'));
      const bytes=new Uint8Array(await new Response(stream).arrayBuffer());
      if(bytes.length!==Math.ceil(w*h/8))throw Error('Saved mask dimensions do not match');
      if(cancelled || !canvas.current)return;
      const context=canvas.current.getContext('2d');if(!context)return;
      const pixels=context.createImageData(w,h);
      for(let i=0;i<w*h;i++)if(bytes[i>>3] & (128>>(i&7)))pixels.data.set(effective ? [0,140,220,100] : [255,173,50,115],i*4);
      const scratch=document.createElement('canvas');scratch.width=w;scratch.height=h;
      scratch.getContext('2d')!.putImageData(pixels,0,0);
      context.setTransform(1,0,0,1,0,0);
      context.clearRect(0,0,canvas.current.width,canvas.current.height);
      const m=record.to_analysis || [[1,0,0],[0,1,0]];
      if(m.length!==2 || m.some(row=>row.length!==3 || row.some(v=>!Number.isFinite(v))))throw Error('Invalid sampling coordinate mapping');
      context.setTransform(m[0][0],m[1][0],m[0][1],m[1][1],m[0][2],m[1][2]);
      context.imageSmoothingEnabled=false;context.drawImage(scratch,0,0);
    }
    void draw().catch(e=>{if(!cancelled)setError(String(e));});
    return ()=>{cancelled=true;};
  },[record,effective]);
  return <>{error && <p role="alert">{error}</p>}<canvas ref={canvas} width={(record.analysis_size || record.size)?.[0]} height={(record.analysis_size || record.size)?.[1]} aria-label={effective ? 'Effective sampling exclusions' : 'Exact retained text mask'} style={{position:'absolute',inset:0,width:'100%',height:'100%',pointerEvents:'none'}}/></>;
}
export function AuditPanel({panel,project}:{panel:Panel;project:string}) {
  const [show,setShow]=useState(false),[detail,setDetail]=useState<Localization|null>(null),[error,setError]=useState('');
  const [consumer,setConsumer]=useState(''),[usage,setUsage]=useState<Usage|null>(null);
  useEffect(()=>{
    if(!show)return;
    const abort=new AbortController();
    const query=new URLSearchParams({project,run:panel.run,paper:panel.paper,uid:panel.uid});
    if(consumer)query.set('consumer',consumer);
    void fetch('/api/images/text-regions?'+query,{signal:abort.signal}).then(async r=>{
      const data=await r.json();if(!r.ok)throw Error(data.error);return data;
    }).then(data=>{setDetail(data.localization || {status:data.status,reason:data.reason});setUsage(data.usage || null);setError('');}).catch(e=>{if(!abort.signal.aborted)setError(String(e));});
    return ()=>abort.abort();
  },[show,consumer,panel,project]);
  const url=panel.image ? mediaUrl(project,panel.paper,panel.image) : null;
  return <article style={{padding:16,border:'1px solid #ccc',borderRadius:6,maxWidth:680}}>
    <h3>{panel.paper} · {panel.uid}</h3>
    <p>{panel.status} · Select a detector ledger to inspect whether exclusions were applied.</p>
    <p>Saved text policy: {panel.policy}. Scientific acceptance: {panel.rollout?.scientific_acceptance || 'not recorded for this run'}.</p>
    <label><input type="checkbox" role="switch" checked={show} onChange={e=>setShow(e.target.checked)}/> Show excluded text regions</label>
    <label style={{display:'block',marginTop:8}}>Overlay <select value={consumer} onChange={e=>{setConsumer(e.target.value);setUsage(null);}}>
      <option value="">Detected text</option>
      {(panel.consumers || []).map((c,i)=><option key={i} value={String(i)}>{c.consumer}{c.stage ? ` · ${c.stage}` : ''}{c.size ? ` · ${c.size.join('×')}` : ''}{c.reflected ? ' (reflected features)' : ''}{c.chrome_mask_applied ? ' (chrome excluded)' : ''}</option>)}
    </select></label>
    {usage && <p>{usage.status === 'incomplete' ? 'Analysis incomplete' : usage.applied ? 'Exclusion applied' : 'Diagnostic only, not applied'} · {usage.excluded_samples!=null ? `${usage.excluded_samples} grid centers excluded · ${usage.remaining_samples} remain` : usage.excluded_features!=null ? `${usage.excluded_features} features excluded · ${usage.remaining_features} remain` : 'Effective sampling counts not recorded'}. {usage.reason}</p>}
    {consumer && show && !usage && !error && <p>Loading consumer ledger…</p>}
    {error && <p role="alert">{error}</p>}
    {url ? <div style={{position:'relative',marginTop:12,lineHeight:0}}>
      {/* The thumbnail uses the existing bounded media cache. Full analysis pixels
          and the exact saved mask are requested only for visual inspection. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={show ? url : url+'&variant=thumbnail'} alt={`Analysis pixels for ${panel.uid}`} loading="lazy" style={{width:'100%',height:'auto'}}/>
      {show && detail?.mask_bits && <RasterMask record={detail}/>}
      {show && usage?.mask_bits && <RasterMask record={usage} effective/>}
      {show && detail?.size && <svg aria-label="Detected text polygons" viewBox={`0 0 ${detail.size[0]} ${detail.size[1]}`} style={{position:'absolute',inset:0,width:'100%',height:'100%',pointerEvents:'none'}}>
        {(detail.polygons || []).map((polygon,i)=><polygon key={i} points={polygon.map(p=>p.join(',')).join(' ')} fill="none" stroke="#e48c00" strokeWidth={2} strokeDasharray={usage?.applied ? undefined : '5 3'} vectorEffect="non-scaling-stroke"/>)}
        {(usage?.excluded_feature_footprints || []).map(([x,y,r],i)=><rect key={`feature-${i}`} x={x-r} y={y-r} width={2*r+1} height={2*r+1} fill="rgba(0,140,220,.08)" stroke="#008cdc" strokeWidth={1} vectorEffect="non-scaling-stroke"><title>Descriptor neighborhood excluded from matching</title></rect>)}
      </svg>}
    </div> : <p>Analysis pixels were not retained in this run.</p>}
    {show && !detail && !error && <p>Loading retained regions…</p>}
    {detail && <p>{detail.status}: {detail.reason}{detail.mask_fraction!=null && ` · ${(100*detail.mask_fraction).toFixed(2)}% localized text`}</p>}
    {detail?.provenance?.device && <p>Localization backend: {detail.provenance.device}{detail.provenance.execution?.runtime?.hardware?.name && ` · ${detail.provenance.execution.runtime.hardware.name}`}</p>}
    <details><summary>Provenance and source mapping</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify({run:panel.run,policy:panel.policy,timing:panel.timing,consumer:usage?.consumer,stage:usage?.stage,footprint:usage?.footprint,sampling_size:usage?.size,sampling_to_analysis:usage?.to_analysis,analysis_size:usage?.analysis_size,pixel_sha256:detail?.pixel_sha256,size:detail?.size,crop_box:panel.crop_box,coordinates:panel.coordinates,pixel_source:panel.pixel_source,provenance:detail?.provenance || panel.provenance},null,2)}</pre></details>
  </article>;
}
export function TextRegionAudit({project,initialRun}:{project:string;initialRun:string}) {
  const [draft,setDraft]=useState(initialRun),[run,setRun]=useState(initialRun),[offset,setOffset]=useState(0),[data,setData]=useState<PageData|null>(null),[error,setError]=useState('');
  useEffect(()=>{
    setData(null);setError('');if(!run)return;
    const abort=new AbortController();
    void fetch('/api/images/text-regions?'+new URLSearchParams({project,run,offset:String(offset),limit:'25'}),{signal:abort.signal}).then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.error);return d;}).then(setData).catch(e=>{if(!abort.signal.aborted)setError(String(e));});
    return ()=>abort.abort();
  },[project,run,offset]);
  return <main style={{padding:24}}><h1>Text-region audit</h1>
    <p>All retained panels in the selected run, including panels without findings. Applied exclusions and scientific acceptance status come from this run. Showing an overlay does not change analysis or review decisions.</p>
    <form onSubmit={e=>{e.preventDefault();setOffset(0);setRun(draft.trim());}}><label>Exact run ID <input value={draft} onChange={e=>setDraft(e.target.value)} required/></label> <button type="submit">Load run</button></form>
    {error && <p role="alert">{error}</p>}{run && !error && !data && <p>Loading panel audit…</p>}
    {data && <><p>{data.total} retained panels. {data.reason}</p><div style={{display:'flex',flexWrap:'wrap',alignItems:'start',gap:16}}>{data.panels.map(panel=><AuditPanel key={`${run}/${panel.paper}/${panel.uid}`} panel={panel} project={project}/>)}</div>
      <nav aria-label="Audit pages"><button disabled={!offset} onClick={()=>setOffset(Math.max(0,offset-25))}>Previous</button> <button disabled={data.pagination?.next_offset==null} onClick={()=>setOffset(data.pagination!.next_offset!)}>Next</button></nav></>}
  </main>;
}


export function FindingRegionAudit({project,run,panels}:{project:string;run:string;panels:{uid:string;paper_dir:string}[]}) {
  const [open,setOpen]=useState(false);
  return <details onToggle={event=>setOpen(event.currentTarget.open)}>
    <summary>Audit retained text exclusions for this finding</summary>
    <p><a href={`/project/${encodeURIComponent(project)}/images/text-regions?run=${encodeURIComponent(run)}`}>Audit every panel in this exact run</a></p>
    {open && panels.map(panel=><FindingPanel key={`${run}/${panel.paper_dir}/${panel.uid}`} project={project} run={run} uid={panel.uid} paper={panel.paper_dir}/>)}
  </details>;
}
function FindingPanel({project,run,uid,paper}:{project:string;run:string;uid:string;paper:string}) {
  const [panel,setPanel]=useState<Panel|null>(null),[error,setError]=useState('');
  useEffect(()=>{
    const abort=new AbortController();
    const query=new URLSearchParams({project,run,paper,uid,summary_only:'true'});
    void fetch('/api/images/text-regions?'+query,{signal:abort.signal}).then(async response=>{
      const data=await response.json();if(!response.ok)throw Error(data.error);return data;
    }).then(data=>setPanel(data.panel)).catch(e=>{if(!abort.signal.aborted)setError(String(e));});
    return ()=>abort.abort();
  },[project,run,paper,uid]);
  if(error)return <p role="status">Retained text-region audit unavailable for {uid}: {error}</p>;
  return panel ? <AuditPanel panel={panel} project={project}/> : <p>Loading retained panel metadata…</p>;
}
