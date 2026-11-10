import { jsonError } from "@/lib/err";
import { identity, withReviewer } from "@/lib/auth";
import { rejectCrossOrigin } from "@/lib/mutation";
import { ADMIN_WORKBENCH_METHODS, UNSCOPED_WORKBENCH_READS, guard } from "@/lib/routeGuard";
import { NextResponse } from "next/server";
import { workbench, workbenchTimed, serverTiming } from "@/lib/workbench";
export const dynamic = "force-dynamic";
const READ = new Set([
  "status",
  "image_status",
  "item_core",
  "item_details",
  "image_navigation",
  "image_carried",
  "projects",
  "papers",
  "findings",
  "runs",
  "feed",
  "item",
  "item_diagnostics",
  "paper",
  "source",
  "issue_detail",
  "roots",
  "video_status",
]);
const WRITE = new Set([
  "sync",
  "review",
  "register_root",
  "map_paper",
  "register_file",
  "video_generate",
]);
export async function GET(req: Request) {
  const params = Object.fromEntries(new URL(req.url).searchParams),
    method = params.method || "status";
  if (!READ.has(method)) return NextResponse.json({ error: "Unknown method" }, { status: 400 });
  delete params.method;
  // Every read but the admin-only cross-project ones is about one project;
  // image_status may omit it (the header's status line).
  const unscoped = UNSCOPED_WORKBENCH_READS.has(method) || (method === "image_status" && !params.project);
  const refused = await guard(req, unscoped ? { workbenchMethod: method } : { workbenchMethod: method, project: params.project });
  if (refused) return refused;
  try {
    const { value, timings } = await workbenchTimed(method, params, { signal: req.signal });
    // image_status lists every project's counts, and the status errors can
    // name server paths or the database: a reviewer sees neither.
    const who = identity(req);
    if (who && who.role !== "admin" && value && typeof value === "object") {
      const v = value as Record<string, unknown>;
      if (method === "image_status") delete v.projects;
      if (method === "status" || method === "image_status") {
        for (const k of ["error", "file_monitor_error", "warmup_error", "import_error"]) if (v[k]) v[k] = "Sync needs attention (details for admins)";
        if (Array.isArray(v.pending_errors) && v.pending_errors.length) v.pending_errors = ["Some decisions are waiting to sync"];
      }
    }
    return NextResponse.json(value, { headers: { "Server-Timing": serverTiming(timings) } });
  } catch (e) {
    return jsonError(e);
  }
}
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req);
  if (rejected) return rejected;
  const refused = await guard(req);
  if (refused) return refused;
  // The local API may touch local files; cross-origin browser requests cannot register roots.
  try {
    const { method, ...params } = withReviewer(req, await req.json());
    if (!WRITE.has(method)) return NextResponse.json({ error: "Unknown method" }, { status: 400 });
    // Catalog writes are admin-only and may name a project that is not a
    // source yet (registering its folder is how it becomes one).
    const adminOnly = await guard(req, ADMIN_WORKBENCH_METHODS.has(method)
      ? { workbenchMethod: method } : { workbenchMethod: method, project: params.project });
    if (adminOnly) return adminOnly;
    return NextResponse.json(await workbench(method, params));
  } catch (e) {
    return jsonError(e);
  }
}
