import { NextResponse } from "next/server";
import { workbench } from "@/lib/workbench";
export const dynamic="force-dynamic";
export async function GET(req: Request) {
 const start=performance.now();
 try { const body=await workbench("paper",Object.fromEntries(new URL(req.url).searchParams));
 return NextResponse.json(body,{headers:{"Server-Timing":`catalog;dur=${(performance.now()-start).toFixed(1)}`}}); }
 catch(e) {return NextResponse.json({error:String(e)},{status:400});}
}
