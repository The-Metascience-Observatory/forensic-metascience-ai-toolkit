import { jsonError } from "@/lib/err";
import { rejectCrossOrigin } from "@/lib/mutation";
import { repoInfo, requireRepo } from "@/lib/repoInfo";
import { saveReadme } from "@/lib/reproRepo";
import { guard } from "@/lib/routeGuard";

export const dynamic = "force-dynamic";

/** Save an edited README into the reproduction repository's working tree.
 *  Nothing is committed or pushed here; that is `/api/repo/push`. */
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  const refused = await guard(req); if (refused) return refused;
  const body = await req.json().catch(() => ({})) as { project?: string; dir?: string; content?: string; base_sha256?: string };
  const scoped = await guard(req, { project: body.project }); if (scoped) return scoped;
  if (!body.project || !body.dir || typeof body.content !== "string" || !body.base_sha256) {
    return Response.json({ error: "project, dir, content and base_sha256 required" }, { status: 400 });
  }
  try {
    const { paperAbs, repoAbs } = await requireRepo(body.project, body.dir);
    await saveReadme(repoAbs, body.content, body.base_sha256);
    return Response.json(await repoInfo(paperAbs, repoAbs));
  } catch (e) { return jsonError(e, /changed on disk/.test(String(e)) ? 409 : 400); }
}
