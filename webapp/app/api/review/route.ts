import { jsonError } from "@/lib/err";
import { withReviewer } from "@/lib/auth";
import { rejectCrossOrigin } from "@/lib/mutation";
import { guard } from "@/lib/routeGuard";
import { NextResponse } from "next/server";
import { workbench } from "@/lib/workbench";
export const dynamic = "force-dynamic";
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req);
  if (rejected) return rejected;
  const refused = guard(req);
  if (refused) return refused;
  try {
    const body = withReviewer(req, await req.json()),
      p = body.patch || {};
    const result = await workbench("review", {
      project: body.project,
      run: p.run || body.run,
      item: p.issue_id || "__paper__",
      ...("decision" in p ? { decision: p.decision } : {}),
      reviewer: body.reviewer,
      ...("note" in p ? { note: p.note } : {}),
      extra:
        p.paper ||
        Object.fromEntries(
          Object.entries(p).filter(
            ([k]) => !["issue_id", "run", "decision", "note", "event_id"].includes(k),
          ),
        ),
      event_id: p.event_id,
    });
    const paper = await workbench("paper", {
      project: body.project,
      slug: body.slug,
      dir: body.dir,
      run: p.run || body.run,
    });
    return NextResponse.json({ ok: true, review: paper.issues.review, pending: result.pending });
  } catch (e) {
    return jsonError(e);
  }
}
