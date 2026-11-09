export function errMsg(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}

export function asRecord(body: unknown): Record<string, unknown> | null {
  if (body === null || typeof body !== "object" || Array.isArray(body)) {
    return null;
  }
  return body as Record<string, unknown>;
}

/** True when the failure is the local workbench service itself (it timed
 *  out, exited or was restarting), as `lib/workbench.ts` phrases it, rather
 *  than a request the service refused. */
export function isServiceFailure(e: unknown): boolean {
  return /workbench (request )?(timed out|exited|restart|unavailable|closed)|service (exited|unavailable)/i
    .test(errMsg(e));
}

/** The error body every API route returns from its catch: `{error}` with the
 *  message alone (not the "Error: " prefix `String(e)` adds), 502 when the
 *  local service failed, else the given status (400: a refused or malformed
 *  request, which is what the service's own ValueErrors are). */
export function jsonError(e: unknown, status = 400, extra: Record<string, unknown> = {}): Response {
  return Response.json({ error: errMsg(e), ...extra }, { status: isServiceFailure(e) ? 502 : status });
}
