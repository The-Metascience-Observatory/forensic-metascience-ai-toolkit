import { identity, requireAdmin } from "@/lib/auth";
import { jsonError } from "@/lib/err";
import { rejectCrossOrigin } from "@/lib/mutation";
import { repoInfo, requireRepo } from "@/lib/repoInfo";
import { commitAndPush, repoState, visibility } from "@/lib/reproRepo";
import { guard } from "@/lib/routeGuard";

export const dynamic = "force-dynamic";

/** Commit the saved README and push it to GitHub. A reviewer may do this
 *  while the repository is private; once it is public a push publishes, so
 *  only an admin may (and an unknown visibility is treated as public). */
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  const refused = await guard(req); if (refused) return refused;
  const body = await req.json().catch(() => ({})) as { project?: string; dir?: string; reviewer?: string };
  const scoped = await guard(req, { project: body.project }); if (scoped) return scoped;
  if (!body.project || !body.dir) return Response.json({ error: "project and dir required" }, { status: 400 });
  try {
    const { paperAbs, repoAbs } = await requireRepo(body.project, body.dir);
    const state = await repoState(repoAbs);
    if ((await visibility(state.name, undefined, true)) !== "PRIVATE") {
      const adminOnly = requireAdmin(req); if (adminOnly) return adminOnly;
    }
    const who = identity(req)?.name || String(body.reviewer || "");
    const done = await commitAndPush(repoAbs, who);
    return Response.json({ ...done, ...(await repoInfo(paperAbs, repoAbs)) });
  } catch (e) { return jsonError(e); }
}
