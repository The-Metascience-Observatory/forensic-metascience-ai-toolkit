import { rejectCrossOrigin } from "@/lib/mutation";
import { NextResponse } from "next/server";

import { errMsg } from "@/lib/err";
import { revealLocation } from "@/lib/reveal";
import { workbench } from "@/lib/workbench";

export const dynamic = "force-dynamic";

/** Open the paper's directory in the OS file browser (selecting the file
 *  where the platform can). The workbench runs on the reviewer's own
 *  machine, so "reveal" is a local convenience -- but the path still goes
 *  through /api/media's registered-root and archived-hash validation. */
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  let body: { component?: string; project?: string; dir?: string; f?: string };
  try {
    body = await req.json();
    if (!body || typeof body !== "object" || Array.isArray(body)) throw new Error("bad JSON");
  } catch {
    return NextResponse.json({ error: "bad JSON" }, { status: 400 });
  }
  const project = String(body.project || "");
  const dir = String(body.dir || "");
  const f = body.f ? String(body.f) : null;
  if (!project || !dir) {
    return NextResponse.json({ error: "project and dir required" }, { status: 400 });
  }
  try {
    const target = await workbench("reveal_target", {project, dir, f, component:body.component});
    const launch = await revealLocation(process.platform, target.directory, target.file);
    return NextResponse.json({ok: true, opened: target.file || target.directory,
      ...launch, note: target.note});
  } catch (e: unknown) {
    return NextResponse.json({ error: errMsg(e) }, { status: 400 });
  }
}
