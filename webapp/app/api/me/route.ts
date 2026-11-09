import { NextResponse } from "next/server";

import { hostedMode, identity } from "@/lib/auth";

export const dynamic = "force-dynamic";

/** Who the server thinks is reviewing. Local mode has no identity: the
 *  header chip keeps its free-text name and every local user is an admin. */
export async function GET(req: Request) {
  if (!hostedMode()) return NextResponse.json({ mode: "local", email: null, name: null, role: "admin" });
  const who = identity(req);
  if (!who) return NextResponse.json({ error: "Sign in through Cloudflare Access" }, { status: 401 });
  return NextResponse.json({ mode: "hosted", ...who });
}
