import { rejectCrossOrigin } from "@/lib/mutation";
import { NextResponse } from "next/server";
import { workbench, workbenchTimed, serverTiming } from "@/lib/workbench";
export const dynamic = "force-dynamic";
const READ = new Set(["status", "image_status", "item_core", "item_details", "image_navigation", "image_carried", "projects", "papers", "findings", "runs", "feed", "item", "item_diagnostics", "paper", "source", "issue_detail", "roots", "video_status"]);
const WRITE = new Set(["sync", "review", "register_root", "map_paper", "register_file", "video_generate"]);
export async function GET(req: Request) {
  const params = Object.fromEntries(new URL(req.url).searchParams), method = params.method || "status";
  if (!READ.has(method)) return NextResponse.json({error:"Unknown method"},{status:400});
  delete params.method;
  try { const {value,timings}=await workbenchTimed(method, params, {signal:req.signal}); return NextResponse.json(value,{headers:{"Server-Timing":serverTiming(timings)}}); }
  catch(e) { return NextResponse.json({error:String(e)},{status:400}); }
}
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  // The local API may touch local files; cross-origin browser requests cannot register roots.
  try {
    const {method,...params}=await req.json();
    if(!WRITE.has(method)) return NextResponse.json({error:"Unknown method"},{status:400});
    return NextResponse.json(await workbench(method,params));
  } catch(e) { return NextResponse.json({error:String(e)},{status:400}); }
}
