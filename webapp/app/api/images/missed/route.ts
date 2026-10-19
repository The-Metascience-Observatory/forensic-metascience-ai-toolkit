import { rejectCrossOrigin } from "@/lib/mutation";
import { NextResponse } from "next/server";
import { workbench } from "@/lib/workbench";
export const dynamic="force-dynamic";

// A duplication the detector did NOT flag: two boxes drawn on the paper's
// pages, a manipulation type and a note, kept as an immutable local event
// and exported as ground truth (`image-reviews-export --missed-out`).
export async function POST(req:Request){
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
 try{
  const body=await req.json();
  if(!body?.project)return NextResponse.json({error:"project required"},{status:400});
  return NextResponse.json({ok:true,missed:await workbench("image_missed_record",{...body,component:"image_forensics"})});
 }catch(e){return NextResponse.json({error:String(e)},{status:400});}
}
export async function GET(req:Request){
 const params=Object.fromEntries(new URL(req.url).searchParams);
 if(!params.project)return NextResponse.json({error:"project required"},{status:400});
 try{return NextResponse.json(await workbench("image_missed",{...params,component:"image_forensics"}));}
 catch(e){return NextResponse.json({error:String(e)},{status:400});}
}
