"use client";
import { useEffect,useState } from "react";
import { ProjectTable } from "./ProjectTable";
import type { Paper } from "@/lib/store";
import type { SortState } from "@/lib/projectTableSort";
export function PapersPage({project}:{project:string}){
 const [papers,setPapers]=useState<Paper[]>([]),[total,setTotal]=useState(0),[offset,setOffset]=useState(0),[q,setQ]=useState(''),[error,setError]=useState('');
 const [sort,setSort]=useState<SortState|null>({key:'findings',dir:'desc'});
 useEffect(()=>{const controller=new AbortController();
 const load=()=>{if(document.hidden)return;const params=new URLSearchParams({method:'papers',project,offset:String(offset),q,sort:sort?.key || 'findings',direction:sort?.dir || 'desc'});
 fetch(`/api/workbench?${params}`,{signal:controller.signal}).then(async r=>{const b=await r.json();if(!r.ok)throw new Error(b.error);setPapers(b.papers);setTotal(b.pagination.total);setError('');}).catch(e=>{if(e.name!=='AbortError')setError(String(e));});};
 load();const timer=setInterval(load,30000);window.addEventListener('focus',load);return()=>{controller.abort();clearInterval(timer);window.removeEventListener('focus',load);};
 },[project,offset,q,sort]);
 return <div className="page"><a href="/">← projects</a><h1>{project}</h1>
 <p><a href={`/project/${encodeURIComponent(project)}/images`}>Image findings</a>{' · '}<a href={`/project/${encodeURIComponent(project)}/copypaste`}>Copy/paste findings</a>{' · '}<a href={`/project/${encodeURIComponent(project)}/stats`}>Statistics</a></p>
 <label>Search <input value={q} onChange={e=>{setQ(e.target.value);setOffset(0);}} placeholder="title, DOI, or folder (10.1007--s004010050748)" aria-label="Search papers by title, DOI, or folder name" style={{minWidth:280}} /></label>{' '}
 <button disabled={!offset} onClick={()=>setOffset(Math.max(0,offset-50))}>Previous 50</button> {total?offset+1:0}–{offset+papers.length} of {total}{' '}
 <button disabled={offset+50>=total} onClick={()=>setOffset(offset+50)}>Next 50</button>
 {error&&<p role="alert">{error}</p>}
 <ProjectTable project={project} papers={papers} onSortChange={s=>{setSort(s);setOffset(0);}}/>
 </div>;
}
