import { NextResponse } from "next/server";

import { projectsPayload, validateSources } from "@/lib/adminData";
import { errMsg } from "@/lib/err";
import { rejectCrossOrigin } from "@/lib/mutation";
import { invalidateSources, sourceView } from "@/lib/projectSources";
import { guard } from "@/lib/routeGuard";
import { saveProjectSources } from "@/lib/settings";

export const dynamic = "force-dynamic";

/** Configured sources, the projects they yield (folders, papers, members),
 *  and the catalog names no source covers. */
export async function GET(req: Request) {
  const refused = await guard(req);
  if (refused) return refused;
  try {
    return NextResponse.json(await projectsPayload());
  } catch (e) {
    return NextResponse.json({ error: errMsg(e) }, { status: 502 });
  }
}

/** Replace the sources. New folders are registered with the service on the
 *  next read, which this triggers. */
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req);
  if (rejected) return rejected;
  const refused = await guard(req);
  if (refused) return refused;
  let body: { sources?: unknown };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "bad JSON" }, { status: 400 });
  }
  const checked = validateSources(body?.sources);
  if ("error" in checked) return NextResponse.json({ error: checked.error }, { status: 400 });
  saveProjectSources(checked.sources);
  invalidateSources();
  try {
    await sourceView();
    return NextResponse.json({ ok: true, ...(await projectsPayload()) });
  } catch (e) {
    return NextResponse.json({ ok: true, warning: errMsg(e) });
  }
}
