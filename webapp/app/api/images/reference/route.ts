import { rejectCrossOrigin } from "@/lib/mutation";
import { NextResponse } from "next/server";

import { errMsg } from "@/lib/err";
import { pyJson } from "@/lib/python";
import { workbench } from "@/lib/workbench";

export const dynamic = "force-dynamic";

/** Bibliographic metadata for the papers of an image finding, for the
 *  summary figure's reference lines. The paper folder is resolved the same
 *  way "show in folder" resolves it (registered roots, no DOI search), and
 *  `fetch-metadata` answers from `metadata.json` when it is already complete,
 *  asking the DOI APIs only when it is not. POST because a first fetch writes
 *  that cache file. One failed paper is named, never fatal to the others. */
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  let body: { project?: unknown; dirs?: unknown };
  try { body = await req.json(); } catch { return NextResponse.json({ error: "bad JSON" }, { status: 400 }); }
  const project = typeof body?.project === "string" ? body.project : "";
  const dirs = Array.isArray(body?.dirs)
    ? [...new Set(body.dirs.filter((d): d is string => typeof d === "string" && !!d))].slice(0, 4) : [];
  if (!project || !dirs.length) return NextResponse.json({ error: "project and dirs required" }, { status: 400 });
  const entries = await Promise.all(dirs.map(async (dir) => {
    try {
      const target = await workbench("reveal_target", { project, dir, component: "image_forensics" });
      const metadata = await pyJson(["fetch-metadata", String(target.directory)], { timeoutMs: 90_000 });
      return [dir, { metadata }] as const;
    } catch (e: unknown) {
      return [dir, { error: errMsg(e) }] as const;
    }
  }));
  return NextResponse.json({ references: Object.fromEntries(entries) });
}
