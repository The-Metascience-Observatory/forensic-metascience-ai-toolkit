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
  return Response.json({ error: publicMessage(errMsg(e)), ...extra }, { status: isServiceFailure(e) ? 502 : status });
}

/** Absolute paths on the server, as OS errors and the service's stderr tail
 *  spell them. Windows drive paths and the usual POSIX roots. */
const SERVER_PATH = /(?:[A-Za-z]:\\|\/(?:home|Users|root|media|mnt|tmp|var|opt|srv|usr|etc|data)\/)[^\s'"`,;:)\]]*/g;

/** The message as a hosted reviewer may read it: the file's name survives
 *  (it says which file), the folders above it do not. Local mode is the
 *  operator's own machine and keeps the whole path. */
export function publicMessage(message: string, env: Record<string, string | undefined> = process.env): string {
  if (!(env.METASCIENCE_ACCESS_TEAM || "").trim() && !(env.METASCIENCE_ACCESS_AUD || "").trim()) return message;
  const cut = message.length > 600 ? message.slice(0, 600) + "…" : message;
  return cut.replace(SERVER_PATH, (m) => "…/" + (m.split(/[\\/]/).filter(Boolean).pop() || ""));
}
