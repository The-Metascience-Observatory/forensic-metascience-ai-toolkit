import { guard } from "@/lib/routeGuard";
import {NextResponse} from 'next/server';
import {workbench} from '@/lib/workbench';
export const dynamic='force-dynamic';
export async function GET(request:Request) {
  const params=Object.fromEntries(new URL(request.url).searchParams);
  const refused = await guard(request, { project: params.project }); if (refused) return refused;
  try {return NextResponse.json(await workbench('text_regions',{...params,component:'image_forensics'}));}
  catch(error) {return NextResponse.json({error:String(error)},{status:400});}
}
