import { guard } from "@/lib/routeGuard";
import { jsonError } from "@/lib/err";
import { NextResponse } from "next/server";
import { workbench } from "@/lib/workbench";
export const dynamic="force-dynamic";
export async function GET(req: Request) {
 const start=performance.now();
 const params=Object.fromEntries(new URL(req.url).searchParams);
 const refused = await guard(req, { project: params.project }); if (refused) return refused;
 try { const body=await workbench("paper",params);
 return NextResponse.json(body,{headers:{"Server-Timing":`catalog;dur=${(performance.now()-start).toFixed(1)}`}}); }
 catch(e) {return jsonError(e);}
}
