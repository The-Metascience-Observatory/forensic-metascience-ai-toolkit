import { rejectCrossOrigin } from "@/lib/mutation";
import { NextResponse } from "next/server";

import { asRecord, errMsg } from "@/lib/err";
import { pyJson, pyModuleJson } from "@/lib/python";
import { findPaper, findProject, paperAbsDir, scanNow } from "@/lib/store";

export const dynamic = "force-dynamic";

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
  const project = String(body.project || "");
  const slug = body.slug ? String(body.slug) : "";
  const dir = body.dir ? String(body.dir) : "";
  const slugs = Array.isArray(body.slugs)
    ? body.slugs.filter((s): s is string => typeof s === "string").slice(0, 40)
    : [];
  const force = body.force === true;
  if (!project) {
    return NextResponse.json({ error: "project required" }, { status: 400 });
  }
  const core = (m: unknown) => {
    if (!m || typeof m !== "object") return false;
    const rec = m as Record<string, unknown>;
    const title = String(rec.title || "").trim();
    const author = String(rec.authors || rec.first_author || "").trim();
    return Boolean(title && author);
  };
  try {
    if (slug || slugs.length) {
      const wanted = slug ? [slug] : slugs;
      let updated = 0;
      let last: unknown = null;
      for (const one of wanted) {
        const paper = findPaper(project, one, dir || null);
        if (!paper) continue;
        const abs = await paperAbsDir(project, paper.dir);
        const args = ["fetch-metadata", abs];
        if (force) args.push("--force");
        last = await pyJson(args);
        if (core(last)) {
          await pyModuleJson("forensic_metascience_ai_toolkit.webapp_index", [abs]);
          updated += 1;
        }
      }

      return NextResponse.json({ ok: true, metadata: last, updated });
    }
    const row = findProject(project);
    if (!row) {
      return NextResponse.json({ error: "unknown project" }, { status: 404 });
    }
    const args = ["fetch-metadata", "--project-dir", row.root];
    if (force) args.push("--force");
    if (body.limit) args.push("--limit", String(body.limit));
    const summary = await pyJson(args);
    const index = await scanNow();
    return NextResponse.json({
      ok: true, summary, n_papers: index.n_papers,
    });
  } catch (e: unknown) {
    return NextResponse.json({ error: errMsg(e) }, { status: 500 });
  }
}
