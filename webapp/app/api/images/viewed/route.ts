import { rejectCrossOrigin } from "@/lib/mutation";
import { NextResponse } from "next/server";
import { workbench } from "@/lib/workbench";
export const dynamic="force-dynamic";
// Opening an image item's detail page. A view, never a decision.
export async function POST(req:Request){
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
 try {return NextResponse.json({ok:true,viewed:await workbench("image_viewed",{component:"image_forensics",...await req.json()})});}
 catch(e){return NextResponse.json({error:String(e)},{status:400});}
}
