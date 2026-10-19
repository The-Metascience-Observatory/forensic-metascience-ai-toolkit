/** Local clients may omit Origin; browser mutations must be same-origin. */
export function rejectCrossOrigin(req: Request): Response | null {
  const origin = req.headers.get("origin");
  if ((origin && origin !== new URL(req.url).origin) || req.headers.get("sec-fetch-site") === "cross-site") {
    return Response.json({ error: "Cross-origin request refused" }, { status: 403 });
  }
  return null;
}
