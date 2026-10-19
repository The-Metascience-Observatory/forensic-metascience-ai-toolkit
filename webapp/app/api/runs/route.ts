import { NextResponse } from "next/server";
import { workbench } from "@/lib/workbench";
export const dynamic="force-dynamic";
export async function GET(req:Request){
 try{return NextResponse.json(await workbench("runs",Object.fromEntries(new URL(req.url).searchParams)));}
 catch(e){return NextResponse.json({error:String(e)},{status:400});}
}
