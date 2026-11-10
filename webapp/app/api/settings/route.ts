import { identity } from "@/lib/auth";
import { rejectCrossOrigin } from "@/lib/mutation";
import { guard } from "@/lib/routeGuard";
import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

import { asRecord, errMsg } from "@/lib/err";
import { hostPath, loadSettings, saveSettings } from "@/lib/settings";
import { scanNow } from "@/lib/store";

export const dynamic = "force-dynamic";

/** Hosted mode: a reviewer sees the names only. The rest (absolute paths,
 *  `python_bin`, the directory's emails) describes the server. */
export async function GET(req: Request) {
  const refused = await guard(req); if (refused) return refused;
  const settings = loadSettings();
  const who = identity(req);
  if (who && who.role !== "admin") return NextResponse.json({ known_reviewers: settings.known_reviewers });
  return NextResponse.json(settings);
}

export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  const refused = await guard(req); if (refused) return refused;
  let raw: unknown;
  try {
    raw = await req.json();
  } catch {
    return NextResponse.json({ error: "bad JSON" }, { status: 400 });
  }
  const body = asRecord(raw);
  if (!body) {
    return NextResponse.json({ error: "bad JSON" }, { status: 400 });
  }
  const current = loadSettings();
  const papersRoot = path.resolve(hostPath(String(body.papers_root || current.papers_root)));
  let st: fs.Stats;
  try {
    st = fs.statSync(papersRoot);
  } catch {
    return NextResponse.json(
      { error: `not a directory: ${papersRoot}` },
      { status: 400 },
    );
  }
  if (!st.isDirectory()) {
    return NextResponse.json(
      { error: `not a directory: ${papersRoot}` },
      { status: 400 },
    );
  }
  const known = Array.isArray(body.known_reviewers)
    ? body.known_reviewers.filter((x): x is string => typeof x === "string")
    : current.known_reviewers;

  const next = saveSettings({
    papers_root: papersRoot,
    known_reviewers: known,
  });
  if (body.scan) {
    try {
      const index = await scanNow();
      return NextResponse.json({ ok: true, settings: next, index:
        { n_projects: index.n_projects, n_papers: index.n_papers } });
    } catch (e: unknown) {
      return NextResponse.json(
        { error: errMsg(e) }, { status: 500 });
    }
  }
  return NextResponse.json({ ok: true, settings: next });
}
