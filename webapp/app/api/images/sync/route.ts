import { jsonError } from "@/lib/err";
import { rejectCrossOrigin } from "@/lib/mutation";
import { guard } from "@/lib/routeGuard";
import { workbench } from "@/lib/workbench";

export const dynamic = "force-dynamic";

/** Pull changed shared records for a component now. A write, so a POST: it
 *  used to ride on `GET /api/images?rebuild=1`, where a prefetch or a
 *  bookmark could trigger a sync without an origin check. */
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req);
  if (rejected) return rejected;
  const refused = await guard(req); if (refused) return refused;
  try {
    const body = await req.json().catch(() => ({}));
    const component = typeof body?.component === "string" && body.component ? body.component : "image_forensics";
    return Response.json(await workbench("sync", { component }));
  } catch (e) {
    return jsonError(e);
  }
}
