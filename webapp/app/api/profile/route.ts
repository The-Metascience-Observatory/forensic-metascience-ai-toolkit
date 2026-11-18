import { identity } from "@/lib/auth";
import { jsonError } from "@/lib/err";
import { rejectCrossOrigin } from "@/lib/mutation";
import { currentUser, readProfile, saveProfile } from "@/lib/profiles";
import { guard } from "@/lib/routeGuard";
import { loadSettings } from "@/lib/settings";

export const dynamic = "force-dynamic";

/** The signed-in user's own preferences (the email footer). Each user reads
 *  and writes only their own: the key comes from the sign-in when hosted. */
export async function GET(req: Request) {
  const refused = await guard(req); if (refused) return refused;
  const reviewer = new URL(req.url).searchParams.get("reviewer") || "";
  const who = currentUser(identity(req), reviewer, loadSettings().reviewers);
  return Response.json({ name: who.name, ...readProfile(who.key) }, { headers: { "cache-control": "no-store" } });
}

export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  const refused = await guard(req); if (refused) return refused;
  const body = await req.json().catch(() => ({})) as { reviewer?: string; email_footer?: unknown };
  const who = currentUser(identity(req), String(body.reviewer || ""), loadSettings().reviewers);
  if (!who.key) return Response.json({ error: "Set your name in the header first" }, { status: 400 });
  if (typeof body.email_footer !== "string") return Response.json({ error: "email_footer required" }, { status: 400 });
  try {
    return Response.json({ name: who.name, ...saveProfile(who.key, { email_footer: body.email_footer }) });
  } catch (e) { return jsonError(e); }
}
