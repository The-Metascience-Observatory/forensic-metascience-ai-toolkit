/** The one JSON transport behind the client hooks.
 *
 * A successful response is its parsed body; anything else is thrown as an
 * `Error` carrying the service's `error` field when it sent one, otherwise
 * the HTTP status text. Callers pass an `AbortSignal` for timeouts.
 */
type ErrorBody = { error?: unknown };

function describe(body: unknown, response: Response): string {
  const error = (body as ErrorBody | null)?.error;
  if (typeof error === "string" && error) return error;
  return response.statusText || `HTTP ${response.status}`;
}

async function parse<T>(response: Response): Promise<T> {
  const body: unknown = await response.json().catch((error: unknown) => {
    if (response.ok) throw error;
    return {};
  });
  if (!response.ok) throw new Error(describe(body, response));
  return body as T;
}

export async function getJson<T = unknown>(url: string, signal?: AbortSignal): Promise<T> {
  return parse<T>(await fetch(url, { signal }));
}

export async function postJson<T = unknown>(url: string, payload: unknown, signal?: AbortSignal): Promise<T> {
  return parse<T>(
    await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    }),
  );
}

/** The text a hook shows for a failed request. */
export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
