import { rejectCrossOrigin } from "@/lib/mutation";
import { NextResponse } from "next/server";
import path from "node:path";
import fsp from "node:fs/promises";

import { errMsg } from "@/lib/err";
import { pyJson } from "@/lib/python";
import { badProject } from "@/lib/paths";
import { loadSettings } from "@/lib/settings";

export const dynamic = "force-dynamic";

function statsPath(project: string): string {
  const settings = loadSettings();
  return path.join(settings.papers_root, project, "corpus_stats.json");
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const project = url.searchParams.get("project") || "";
  if (!project || badProject(project)) {
    return NextResponse.json({ error: "project required" }, { status: 400 });
  }
  try {
    const body = await fsp.readFile(statsPath(project), "utf8");
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
  const url = new URL(req.url);
  const project = url.searchParams.get("project") || "";
  if (!project || badProject(project)) {
    return NextResponse.json({ error: "project required" }, { status: 400 });
  }
  try {
    const settings = loadSettings();
    const root = path.join(settings.papers_root, project);
    await pyJson(["corpus-stats", root, "--stdout"]);
    const body = await fsp.readFile(statsPath(project), "utf8");
    return NextResponse.json(JSON.parse(body));
  } catch (e) {
    return NextResponse.json({ error: errMsg(e) }, { status: 500 });
  }
}
