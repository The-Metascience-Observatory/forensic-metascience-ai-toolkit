import { NextResponse } from "next/server";

import { NOT_SET_UP, hostedMode, identity, signedInEmail } from "@/lib/auth";

export const dynamic = "force-dynamic";

/** Who the server thinks is reviewing. Local mode has no identity: the
 *  header chip keeps its free-text name and every local user is an admin.
 *  Hosted: the directory entry, with the projects a reviewer is assigned. */
export async function GET(req: Request) {
  if (!hostedMode()) return NextResponse.json({ mode: "local", email: null, name: null, role: "admin", projects: [] });
  if (!signedInEmail(req)) return NextResponse.json({ error: "Sign in through Cloudflare Access" }, { status: 401 });
  const who = identity(req);
  if (!who) return NextResponse.json({ error: NOT_SET_UP }, { status: 403 });
  return NextResponse.json({ mode: "hosted", ...who });
}
