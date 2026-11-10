import { rejectCrossOrigin } from "@/lib/mutation";
import { guard } from "@/lib/routeGuard";
import { NextResponse } from "next/server";

import { errMsg } from "@/lib/err";
import { scanNow } from "@/lib/store";

export const dynamic = "force-dynamic";

/* GET (the whole legacy index, every project) was retired 2026-11-10: no
 * page read it, and it listed projects a reviewer may not see. */
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  const refused = await guard(req); if (refused) return refused;
  try {
    const index = await scanNow();
    return NextResponse.json({ ok: true, n_projects: index.n_projects,
                               n_papers: index.n_papers });
  } catch (e: unknown) {
    return NextResponse.json({ error: errMsg(e) }, { status: 500 });
  }
}
