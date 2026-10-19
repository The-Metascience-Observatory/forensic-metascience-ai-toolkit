import { NextResponse } from "next/server";
import { workbench } from "@/lib/workbench";
export const dynamic="force-dynamic";
export async function GET(req:Request){
 try{const p=Object.fromEntries(new URL(req.url).searchParams);return NextResponse.json(await workbench("sheet",{...p,highlights:JSON.parse(p.highlights || "[]")}));}
 catch(e){return NextResponse.json({error:String(e)},{status:400});}
}
