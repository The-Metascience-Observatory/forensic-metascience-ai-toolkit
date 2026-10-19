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
