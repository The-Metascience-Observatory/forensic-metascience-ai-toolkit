import { jsonError } from "@/lib/err";
import { withReviewer } from "@/lib/auth";
import { rejectCrossOrigin } from "@/lib/mutation";
import { guard } from "@/lib/routeGuard";
import { NextResponse } from "next/server";
import { workbench } from "@/lib/workbench";
export const dynamic="force-dynamic";

// One decision on EVERY item matching the queue's current filter, resolved
// server-side. The per-page action covers the 50 loaded rows, which turned a
// 2,000-item skim into 40 rounds of select-all and persisted 58 of ~1,944
// decisions. `expected_total` is the reviewer's own count: if the queue moved
// underneath them the service refuses rather than labelling a different set.
//
// The save runs as a background JOB: POST answers at once with its id and
// GET ?job= reports progress. A 5,000-item save used to outlast the bridge's
// 60 s timer, and the queue then said "Nothing was saved" while the service
// kept saving.
export async function POST(req:Request){
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  const refused = guard(req);
  if (refused) return refused;
 try{
  const body = withReviewer(req, await req.json());
  if(!body?.project)return NextResponse.json({error:"project required"},{status:400});
  if(!body?.decision)return NextResponse.json({error:"decision required"},{status:400});
  return NextResponse.json({ok:true,job:await workbench("review_filter_start",{component:"image_forensics",...body})});
 }catch(e){return jsonError(e);}
}
export async function GET(req:Request){
 const job=new URL(req.url).searchParams.get("job");
 if(!job)return NextResponse.json({error:"job required"},{status:400});
 try{return NextResponse.json({ok:true,job:await workbench("job_status",{component:"image_forensics",job})});}
 catch(e){return jsonError(e, 404, {unknown:true});}
}
