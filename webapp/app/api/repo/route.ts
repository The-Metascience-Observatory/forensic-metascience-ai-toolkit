import { jsonError } from "@/lib/err";
import { paperRepo, repoInfo } from "@/lib/repoInfo";
import { guard } from "@/lib/routeGuard";

export const dynamic = "force-dynamic";

/** The paper's reproduction repository as the review page shows it: its
 *  state, its README and the README's summary (or the triage note). */
export async function GET(req: Request) {
  const url = new URL(req.url);
  const project = url.searchParams.get("project") || "";
  const dir = url.searchParams.get("dir") || "";
  const refused = await guard(req, { project }); if (refused) return refused;
  if (!project || !dir) return Response.json({ error: "project and dir required" }, { status: 400 });
  try {
    const { paperAbs, repoAbs } = await paperRepo(project, dir);
    return Response.json(await repoInfo(paperAbs, repoAbs), { headers: { "cache-control": "no-store" } });
  } catch (e) { return jsonError(e); }
}
