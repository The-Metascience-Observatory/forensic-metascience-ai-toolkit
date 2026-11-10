import { jsonError } from "@/lib/err";
import { withReviewer } from "@/lib/auth";
import { rejectCrossOrigin } from "@/lib/mutation";
import { guard } from "@/lib/routeGuard";
import { NextResponse } from "next/server";
import { workbench, workbenchTimed, serverTiming } from "@/lib/workbench";
export const dynamic = "force-dynamic";
export async function GET(req: Request) {
  const params = Object.fromEntries(new URL(req.url).searchParams);
  const scoped = await guard(req, { project: params.project });
  if (scoped) return scoped;
  try {
    if (params.format === "csv") {
      const quote = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
      const columns = [
        "run_id",
        "id",
        "publication_status",
        "detector_kind",
        "sentence",
        "decision",
        "reviewer",
      ];
      let offset = 0,
        done = false,
        header = false;
      const stream = new ReadableStream({
        async pull(controller) {
          try {
            if (!header) {
              controller.enqueue(new TextEncoder().encode(columns.join(",") + "\n"));
              header = true;
            }
            if (done) {
              controller.close();
              return;
            }
            const feed = await workbench("feed", {
              component: "image_forensics",
              ...params,
              verdict: "all",
              offset,
              limit: 100,
              facets: "none",
            });
            const text = feed.items
              .map((i: any) =>
                [
                  i.run_id,
                  i.id,
                  i.publication_status,
                  i.detector_kind,
                  i.sentence,
                  i.decision?.decision,
                  i.decision?.reviewer,
                ]
                  .map(quote)
                  .join(","),
              )
              .join("\n");
            controller.enqueue(new TextEncoder().encode(text + "\n"));
            done = feed.pagination.next_offset == null;
            offset = feed.pagination.next_offset || 0;
          } catch (e) {
            controller.error(e);
          }
        },
      });
      return new NextResponse(stream, {
        headers: {
          "content-type": "text/csv; charset=utf-8",
          "content-disposition": 'attachment; filename="findings.csv"',
        },
      });
    }
    // The queue's facet counts and run options are separate requests (see
    // useInfiniteFeed); rows come with facets=none.
    const view = params.view;
    delete params.view;
    if (view === "facets" || view === "runs") {
      const { value: feed, timings } = await workbenchTimed(
        view === "facets" ? "feed_facets" : "image_run_options",
        { component: "image_forensics", ...params, undecided: params.undecided === "true" },
        { signal: req.signal },
      );
      return NextResponse.json(
        { project: params.project, feed },
        { headers: { "Server-Timing": serverTiming(timings) } },
      );
    }
    const { value: feed, timings } = await workbenchTimed(
      "feed",
      { component: "image_forensics", ...params, undecided: params.undecided === "true" },
      { signal: req.signal },
    );
    return NextResponse.json(
      { project: params.project, feed },
      { headers: { "Server-Timing": serverTiming(timings) } },
    );
  } catch (e) {
    return jsonError(e);
  }
}
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req);
  if (rejected) return rejected;
  const refused = await guard(req);
  if (refused) return refused;
  try {
    const body = withReviewer(req, await req.json());
    const scoped = await guard(req, { project: body?.project });
    if (scoped) return scoped;
    return NextResponse.json({
      ok: true,
      decision: await workbench("review", { component: "image_forensics", ...body }),
    });
  } catch (e) {
    return jsonError(e);
  }
}
