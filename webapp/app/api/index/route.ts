import { rejectCrossOrigin } from "@/lib/mutation";
import { NextResponse } from "next/server";

import { errMsg } from "@/lib/err";
import { IndexMissing, loadIndex, scanNow } from "@/lib/store";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json(loadIndex());
  } catch (e) {
    if (e instanceof IndexMissing) {
      return NextResponse.json({ error: e.message }, { status: 404 });
    }
    return NextResponse.json({ error: errMsg(e) }, { status: 500 });
  }
}

export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  try {
    const index = await scanNow();
    return NextResponse.json({ ok: true, n_projects: index.n_projects,
                               n_papers: index.n_papers });
  } catch (e: unknown) {
    return NextResponse.json({ error: errMsg(e) }, { status: 500 });
  }
}
