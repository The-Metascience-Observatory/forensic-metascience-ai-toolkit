import fsp from "node:fs/promises";
import path from "node:path";
import {NextResponse} from "next/server";
import {workbench} from "@/lib/workbench";
export const dynamic="force-dynamic";
export async function GET(req:Request){
  try{
    const params=Object.fromEntries(new URL(req.url).searchParams);
    const result=await workbench("summary",{component:"image_forensics",...params});
    const body=await fsp.readFile(result.png);
    return new NextResponse(new Uint8Array(body),{headers:{
      "content-type":"image/png","content-length":String(body.byteLength),
      "content-disposition":`attachment; filename="${path.basename(result.png)}"`,
      "cache-control":"private, max-age=60"}});
  }catch(e){return NextResponse.json({error:String(e)},{status:400});}
}
