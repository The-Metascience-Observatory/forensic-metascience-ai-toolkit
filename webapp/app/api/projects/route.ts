import { rejectCrossOrigin } from "@/lib/mutation";
import { NextResponse } from "next/server";

import { asRecord, errMsg } from "@/lib/err";
import { loadSettings } from "@/lib/settings";
import { workbench } from "@/lib/workbench";

export const dynamic = "force-dynamic";

/** Background deletion jobs, polled by the progress bar on every page. */
export async function GET() {
  try { return NextResponse.json(await workbench("project_delete_jobs")); }
  catch (e) { return NextResponse.json({ error: errMsg(e) }, { status: 400 }); }
}

/** Landing-page housekeeping on THIS machine: mark a project done, or delete
 * its local folder(s) and hide it here. Shared database records are untouched.
 * The configured papers root is always protected: a project registered at the
 * collection folder itself must never take every other project with it. */
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  let body: Record<string, unknown> | null = null;
  try { body = asRecord(await req.json()); } catch { /* handled below */ }
  if (!body || typeof body.project !== "string" || !body.project) {
    return NextResponse.json({ error: "project is required" }, { status: 400 });
  }
  const project = body.project;
  const protectedPaths = [loadSettings().papers_root];
  try {
    switch (body.action) {
      case "done":
      case "undone":
        return NextResponse.json(await workbench("project_done", { project, done: body.action === "done" }));
      case "delete_plan":
        return NextResponse.json(await workbench("project_delete_plan", { project, protected: protectedPaths }));
      case "delete":
        // Starts a background job; progress comes from GET.
        return NextResponse.json(await workbench("project_delete", {
          project, confirm: body.confirm === true, protected: protectedPaths }));
      default:
        return NextResponse.json({ error: "Unknown action" }, { status: 400 });
    }
  } catch (e) {
    return NextResponse.json({ error: errMsg(e) }, { status: 400 });
  }
}
