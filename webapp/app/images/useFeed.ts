"use client";
import { useEffect, useState } from "react";
import { RequestCache } from "@/lib/requestCache";
import type { Feed, Item } from "./lib";
const feeds=new Map<string,Feed>();
const listeners=new Set<()=>void>();
const pending=new Map<string,Promise<Feed>>();
const keyOf=(p:string,r:string,c:string,options:Record<string,unknown>={})=>JSON.stringify([p,r,c,options]);
export function updateFeed(project:string,update:(f:Feed)=>Feed,run="latest",component="image_forensics"){
 for(const [key,feed] of feeds){const [p,r,c]=JSON.parse(key);if(p===project&&r===run&&c===component)feeds.set(key,update(feed));}
 listeners.forEach(f=>f());window.dispatchEvent(new Event("workbench-review"));
}
export function loadFeed(project:string,rebuild=false,run="latest",component="image_forensics",options:Record<string,unknown>={}):Promise<Feed>{
 const key=keyOf(project,run,component,options),old=pending.get(key);if(old)return old;
 const params=new URLSearchParams({project,run,component,...Object.fromEntries(Object.entries(options).map(([k,v])=>[k,Array.isArray(v)?JSON.stringify(v):String(v)])),...(rebuild?{rebuild:"1"}:{})});
 const task=fetch(`/api/images?${params}`).then(async r=>{const b=await r.json();if(!r.ok)throw new Error(b.error||r.statusText);feeds.set(key,b.feed);if(feeds.size>64)feeds.delete(feeds.keys().next().value!);listeners.forEach(f=>f());return b.feed;}).finally(()=>pending.delete(key));
 pending.set(key,task);return task;
}
export function useFeed(project:string,run="latest",component="image_forensics",options:Record<string,unknown>={},enabled=true){
 const key=keyOf(project,run,component,options);
 const [state,setState]=useState<{key:string;feed:Feed|null;error:string|null}>({key,feed:null,error:null});
 useEffect(()=>{if(!enabled)return;let active=true;
 const sync=()=>{if(active)setState({key,feed:feeds.get(key)||null,error:null});};
 const refresh=()=>{if(document.hidden)return;void loadFeed(project,false,run,component,JSON.parse(key)[3]).catch(e=>{if(active)setState({key,feed:feeds.get(key)||null,error:String(e)});});};
 listeners.add(sync);sync();refresh();const timer=setInterval(refresh,30000);window.addEventListener("focus",refresh);
 return()=>{active=false;listeners.delete(sync);clearInterval(timer);window.removeEventListener("focus",refresh);};
 },[project,run,component,key,enabled]);
 return state.key===key?state:{key,feed:null,error:null};
}
const items = new RequestCache<Item>(64);
export function useItem(project:string,run:string,component:string,item?:string,owner?:string,method="item"){
 const key=JSON.stringify([project,run,component,item,owner,method]);
 const [,render]=useState(0);
 useEffect(()=>{
  if(!item)return;
  const unsubscribe=items.subscribe(key,()=>render(n=>n+1));
  const refresh=(force=false)=>{
   if(document.hidden && items.entry(key).data)return;
   const p=new URLSearchParams({method,project,run,component,item,...(owner?{owner}:{})});
   void items.load(key,async signal=>{
    const r=await fetch(`/api/workbench?${p}`,{signal:AbortSignal.any([signal,AbortSignal.timeout(10000)])});const b=await r.json();
    if(!r.ok)throw new Error(b.error);return b;
   },force);
  };
  const changed=()=>refresh(true),focused=()=>refresh();
  refresh();
  window.addEventListener("workbench-review",changed);window.addEventListener("workbench-review-synced",changed);window.addEventListener("focus",focused);
  const timer=setInterval(focused,30000);
  return()=>{unsubscribe();clearInterval(timer);window.removeEventListener("workbench-review",changed);window.removeEventListener("workbench-review-synced",changed);window.removeEventListener("focus",focused);};
 },[key,project,run,component,item,owner,method]);
 const entry=items.entry(key);
 return {key,item:entry.data || null,error:entry.error || null,loading:!entry.data && !entry.error,refresh:()=>window.dispatchEvent(new Event("workbench-review"))};
}

// Decoded panel images kept alive for the items just ahead of the reviewer;
// dropping the Image object can cancel its download.
const warmImages:HTMLImageElement[]=[];
/** Load an item's compact record and then its panel images, so moving to it
 *  renders from cache. Resolves to the record (or undefined on failure). */
export async function prefetchItem(project:string,run:string,item:string,mediaUrl?:(dir:string,ref:string)=>string):Promise<Item|undefined>{
 const key=JSON.stringify([project,run,"image_forensics",item,undefined,"item_core"]);
 if(!items.entry(key).data){
  const p=new URLSearchParams({method:"item_core",project,run,component:"image_forensics",item});
  await items.load(key,async signal=>{
   const r=await fetch(`/api/workbench?${p}`,{signal:AbortSignal.any([signal,AbortSignal.timeout(10000)])});
   const value=await r.json();if(!r.ok)throw new Error(value.error);return value;
  });
 }
 const data=items.entry(key).data;
 if(data&&mediaUrl){
  for(const panel of data.panels||[]){
   if(!panel.image)continue;
   const image=new Image();image.decoding="async";image.src=mediaUrl(panel.paper_dir,panel.image);
   warmImages.push(image);if(warmImages.length>24)warmImages.shift();
  }
 }
 return data;
}
