import { rejectCrossOrigin } from "@/lib/mutation";
import { NextResponse } from "next/server";
import { workbench } from "@/lib/workbench";
export const dynamic="force-dynamic";
export async function POST(req:Request){
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
 try{return NextResponse.json({ok:true,viewed:await workbench("viewed",await req.json())});}
 catch(e){return NextResponse.json({error:String(e)},{status:400});}
}
