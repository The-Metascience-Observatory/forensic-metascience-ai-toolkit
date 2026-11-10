import { NextResponse } from "next/server";

import { catalogProjects, validateUsers } from "@/lib/adminData";
import { signedInEmail } from "@/lib/auth";
import { errMsg } from "@/lib/err";
import { rejectCrossOrigin } from "@/lib/mutation";
import { sourceView } from "@/lib/projectSources";
import { guard } from "@/lib/routeGuard";
import { loadSettings, saveDirectory } from "@/lib/settings";

export const dynamic = "force-dynamic";

/** The user directory and the project names it can assign. */
export async function GET(req: Request) {
  const refused = await guard(req);
  if (refused) return refused;
  try {
    const view = await sourceView();
    const names = view ? [...view.projects.keys()] : (await catalogProjects()).map((p) => p.name);
    return NextResponse.json({
      users: loadSettings().reviewers,
      projects: names.sort(),
      me: signedInEmail(req),
    });
  } catch (e) {
    return NextResponse.json({ error: errMsg(e) }, { status: 502 });
  }
}

/** Replace the directory. Takes effect on the next request (the proxy reads
 *  the settings file each time). */
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req);
  if (rejected) return rejected;
  const refused = await guard(req);
  if (refused) return refused;
  let body: { users?: unknown };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "bad JSON" }, { status: 400 });
  }
  const checked = validateUsers(body?.users, signedInEmail(req));
  if ("error" in checked) return NextResponse.json({ error: checked.error }, { status: 400 });
  return NextResponse.json({ ok: true, users: saveDirectory(checked.users) });
}
