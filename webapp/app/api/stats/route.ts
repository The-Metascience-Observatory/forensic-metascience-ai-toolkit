import { rejectCrossOrigin } from "@/lib/mutation";
import { guard } from "@/lib/routeGuard";
import { NextResponse } from "next/server";
import path from "node:path";
import fsp from "node:fs/promises";

import { errMsg } from "@/lib/err";
import { pyJson } from "@/lib/python";
import { badProject } from "@/lib/paths";
import { projectRoot } from "@/lib/store";

export const dynamic = "force-dynamic";

/** `corpus_stats.json` beside the project's (first) registered folder. */
async function statsPath(project: string): Promise<string | null> {
  const root = await projectRoot(project);
  return root ? path.join(root, "corpus_stats.json") : null;
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const project = url.searchParams.get("project") || "";
  if (!project || badProject(project)) {
    return NextResponse.json({ error: "project required" }, { status: 400 });
  }
  const refused = await guard(req, { project }); if (refused) return refused;
  try {
    const file = await statsPath(project);
    if (!file) throw new Error("no folder");
    const body = await fsp.readFile(file, "utf8");
    return NextResponse.json(JSON.parse(body));
  } catch {
    return NextResponse.json(
      { error: "no corpus_stats.json for this project -- POST here to compute it" },
      { status: 404 });
  }
}

/** Recompute. The CLI writes corpus_stats.json beside the corpus. */
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  const refused = await guard(req); if (refused) return refused;
  const url = new URL(req.url);
  const project = url.searchParams.get("project") || "";
  if (!project || badProject(project)) {
    return NextResponse.json({ error: "project required" }, { status: 400 });
  }
  const scoped = await guard(req, { project }); if (scoped) return scoped;
  try {
    const root = await projectRoot(project);
    if (!root) return NextResponse.json({ error: "this project has no folder on this machine" }, { status: 404 });
    await pyJson(["corpus-stats", root, "--stdout"]);
    const body = await fsp.readFile(path.join(root, "corpus_stats.json"), "utf8");
    return NextResponse.json(JSON.parse(body));
  } catch (e) {
    return NextResponse.json({ error: errMsg(e) }, { status: 500 });
  }
}
