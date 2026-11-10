import { guard } from "@/lib/routeGuard";
import { jsonError } from "@/lib/err";
import { NextResponse } from "next/server";
import { workbench } from "@/lib/workbench";
export const dynamic = "force-dynamic";
export async function GET(req: Request) {
  const p = Object.fromEntries(new URL(req.url).searchParams);
  const refused = await guard(req, { project: p.project }); if (refused) return refused;
  try {
    return NextResponse.json(
      await workbench("sheet", { ...p, highlights: JSON.parse(p.highlights || "[]") }),
    );
  } catch (e) {
    return jsonError(e);
  }
}
