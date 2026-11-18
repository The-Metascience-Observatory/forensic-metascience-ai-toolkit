import { identity } from "@/lib/auth";
import { jsonError } from "@/lib/err";
import { rejectCrossOrigin } from "@/lib/mutation";
import { saveDraft, type DraftEdit } from "@/lib/paperDrafts";
import { guard } from "@/lib/routeGuard";
import { paperAbsDir } from "@/lib/store";

export const dynamic = "force-dynamic";

/** Save a reviewer's edits to one draft (recipients, subject, body), or mark
 *  it sent / posted. Nothing is sent from here. */
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  const refused = await guard(req); if (refused) return refused;
  const body = await req.json().catch(() => ({})) as DraftEdit & {
    project?: string; dir?: string; name?: string; reviewer?: string;
  };
  const scoped = await guard(req, { project: body.project }); if (scoped) return scoped;
  if (!body.project || !body.dir || !body.name) {
    return Response.json({ error: "project, dir and name required" }, { status: 400 });
  }
  try {
    const paperAbs = await paperAbsDir(body.project, body.dir);
    const who = identity(req)?.name || String(body.reviewer || "");
    const { to, cc, subject, body: text, sent } = body;
    return Response.json(await saveDraft(paperAbs, body.name, { to, cc, subject, body: text, sent }, who));
  } catch (e) { return jsonError(e); }
}
