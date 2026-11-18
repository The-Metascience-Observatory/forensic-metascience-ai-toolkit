import path from "node:path";

import { identity } from "@/lib/auth";
import { jsonError } from "@/lib/err";
import { rejectCrossOrigin } from "@/lib/mutation";
import {
  KINDS, detachedPython, isKind, listDrafts, paperXmlAddresses, readJob, startJob,
} from "@/lib/paperDrafts";
import { pythonBin, pythonEnv, repoRoot } from "@/lib/python";
import { paperRepo, repoInfo } from "@/lib/repoInfo";
import { guard } from "@/lib/routeGuard";
import { paperAbsDir, projectFolders } from "@/lib/store";

export const dynamic = "force-dynamic";

async function state(paperAbs: string) {
  const [email, pubpeer] = await Promise.all(KINDS.map((k) => readJob(paperAbs, k)));
  return { jobs: { email, pubpeer }, drafts: await listDrafts(paperAbs) };
}

/** The paper's drafts and the progress of any job making one. */
export async function GET(req: Request) {
  const url = new URL(req.url);
  const project = url.searchParams.get("project") || "";
  const dir = url.searchParams.get("dir") || "";
  const refused = await guard(req, { project }); if (refused) return refused;
  if (!project || !dir) return Response.json({ error: "project and dir required" }, { status: 400 });
  try {
    return Response.json(await state(await paperAbsDir(project, dir)), { headers: { "cache-control": "no-store" } });
  } catch (e) { return jsonError(e); }
}

/** Start drafting an email (to the journal, authors in copy) or a PubPeer
 *  comment. Returns at once; the page polls GET. Nothing is ever sent. */
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  const refused = await guard(req); if (refused) return refused;
  const body = await req.json().catch(() => ({})) as {
    project?: string; dir?: string; kind?: string; exclude?: unknown; reviewer?: string;
  };
  const scoped = await guard(req, { project: body.project }); if (scoped) return scoped;
  if (!body.project || !body.dir || !isKind(body.kind)) {
    return Response.json({ error: "project, dir and kind (email or pubpeer) required" }, { status: 400 });
  }
  try {
    const { paperAbs, repoAbs } = await paperRepo(body.project, body.dir);
    const [authors, info] = await Promise.all([
      paperXmlAddresses(paperAbs).catch(() => [] as string[]),
      repoInfo(paperAbs, repoAbs).catch(() => null),
    ]);
    // The journal-contact cache is shared by the project's papers.
    const roots = await projectFolders(body.project).catch(() => [] as string[]);
    const contactsDir = roots.find((r) => !path.relative(r, paperAbs).startsWith("..")) ?? path.dirname(paperAbs);
    await startJob(paperAbs, {
      kind: body.kind,
      authors,
      who: identity(req)?.name || String(body.reviewer || ""),
      repoUrl: info?.repo?.url || "",
      repoVisibility: info?.repo?.visibility || "",
      contactsDir,
      exclude: Array.isArray(body.exclude) ? body.exclude.map(String) : [],
    }, detachedPython(pythonBin(), repoRoot(), pythonEnv()));
    return Response.json(await state(paperAbs));
  } catch (e) { return jsonError(e, /already being drafted/.test(String(e)) ? 409 : 400); }
}
