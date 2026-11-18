import path from "node:path";

import { identity } from "@/lib/auth";
import { jsonError } from "@/lib/err";
import { rejectCrossOrigin } from "@/lib/mutation";
import { repoInfo, requireRepo } from "@/lib/repoInfo";
import { makePublic } from "@/lib/reproRepo";
import { guard } from "@/lib/routeGuard";
import { projectFolders } from "@/lib/store";

export const dynamic = "force-dynamic";

/** Make the paper's GitHub reproduction repository public. Admin only
 *  (`lib/routeGuard.ts`), and only with the repository's name typed out. */
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  const refused = await guard(req); if (refused) return refused;
  const body = await req.json().catch(() => ({})) as { project?: string; dir?: string; confirm?: string; reviewer?: string };
  const scoped = await guard(req, { project: body.project }); if (scoped) return scoped;
  if (!body.project || !body.dir) return Response.json({ error: "project and dir required" }, { status: 400 });
  try {
    const { paperAbs, repoAbs } = await requireRepo(body.project, body.dir);
    // The log sits at the project's root, beside its paper folders.
    const roots = await projectFolders(body.project).catch(() => [] as string[]);
    const logDir = roots.find((r) => !path.relative(r, paperAbs).startsWith("..")) ?? path.dirname(paperAbs);
    const who = identity(req)?.name || String(body.reviewer || "");
    const done = await makePublic(repoAbs, String(body.confirm || ""), who, logDir);
    return Response.json({ ...done, ...(await repoInfo(paperAbs, repoAbs)) });
  } catch (e) { return jsonError(e); }
}
