"use client";
import { useEffect,useState } from 'react';
export default function Files(){
 const [roots,setRoots]=useState<any[]>([]),[message,setMessage]=useState(''),[failed,setFailed]=useState(false);
 const [project,setProject]=useState(''),[path,setPath]=useState(''),[dir,setDir]=useState(''),[sha,setSha]=useState('');
 const load=()=>fetch('/api/workbench?method=roots').then(r=>r.json()).then(b=>setRoots(b.roots||[]));
 useEffect(()=>{void load();},[]);
 async function save(method:string){try{const r=await fetch('/api/workbench',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({method,project,path,dir,sha256:sha})});const b=await r.json();if(!r.ok)throw new Error(b.error);setFailed(false);setMessage('Local mapping saved.');void load();}catch(e){setFailed(true);setMessage(String(e));}}
 return <div className="page"><h1>Local files</h1><p className="muted">These mappings apply only to this computer. Shared findings remain available when their evidence files are missing.</p>
 <ul>{roots.map(r=><li key={`${r.project}:${r.path}`}>{r.project}: {r.path} · {r.available?'available':'unavailable'}</li>)}</ul>
 <p><label>Shared project name <input value={project} onChange={e=>setProject(e.target.value)}/></label></p>
 <p><label>Absolute local folder or file <input style={{width:600}} value={path} onChange={e=>setPath(e.target.value)}/></label></p>
 <button onClick={()=>void save('register_root')}>Register project root</button>
 <p><label>Shared paper directory <input value={dir} onChange={e=>setDir(e.target.value)}/></label> <button onClick={()=>void save('map_paper')}>Map paper folder</button></p>
 <p><label>Recorded artifact SHA-256 <input style={{width:600}} value={sha} onChange={e=>setSha(e.target.value)}/></label> <button onClick={()=>void save('register_file')}>Verify and map file</button></p>
 <p role="status" style={failed?{color:"var(--sev-impossible)"}:undefined}>{message}</p></div>;
}
