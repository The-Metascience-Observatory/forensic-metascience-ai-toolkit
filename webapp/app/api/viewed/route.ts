import { jsonError } from "@/lib/err";
import { withReviewer } from "@/lib/auth";
import { rejectCrossOrigin } from "@/lib/mutation";
import { guard } from "@/lib/routeGuard";
import { NextResponse } from "next/server";
import { workbench } from "@/lib/workbench";
export const dynamic="force-dynamic";
export async function POST(req:Request){
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  const refused = await guard(req);
  if (refused) return refused;
 try{
  const body = withReviewer(req, await req.json(), "viewer");
  const scoped = await guard(req, { project: body?.project }); if (scoped) return scoped;
  return NextResponse.json({ok:true,viewed:await workbench("viewed", body)});
 }
 catch(e){return jsonError(e);}
}
