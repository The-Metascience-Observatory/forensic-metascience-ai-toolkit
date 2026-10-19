import { rejectCrossOrigin } from "@/lib/mutation";
import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

import { asRecord, errMsg } from "@/lib/err";
import { hostPath, loadSettings, saveSettings } from "@/lib/settings";
import { scanNow } from "@/lib/store";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(loadSettings());
}

export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
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
