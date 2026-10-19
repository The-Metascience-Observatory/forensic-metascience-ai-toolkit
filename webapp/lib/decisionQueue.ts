/** Image decisions sent without blocking the reviewer.
 *
 * The page advances as soon as a decision key is pressed; the decision is
 * sent in the background with a client-generated `event_id`, so a retry after
 * a lost response is the SAME event (the service stores an event id once and
 * answers a repeat with the stored event) rather than a second decision.
 */
export type Ref = { id: string; run_id: string };
export type Navigation = { next_undecided: Ref | null; upcoming?: Ref[] };
export type DecisionBody = {
  project: string; run: string; item: string; decision: string; reviewer: string;
  note?: string; resolve?: boolean; event_id: string; extra?: Record<string, unknown>; carry_from?: string;
};
export type DecisionFailure = { body: DecisionBody; error: string };

export function newEventId(): string {
  return "rv_" + globalThis.crypto.randomUUID().replace(/-/g, "");
}

const refKey = (r: Ref) => `${r.run_id}\u0000${r.id}`;

/** Where a decision on `current` advances to.
 *
 * `undefined` means NOT YET KNOWN -- the caller waits for navigation rather
 * than saving without advancing, which is what a key pressed before the
 * neighbours loaded used to do. `null` means there is no undecided item
 * left. `hint` is the previous item's `upcoming` list, so a reviewer who
 * decides again before this item's navigation arrives still moves on;
 * `decided` holds items decided in this session whose rows may not yet say so.
 */
export function advanceTarget(current: Ref, nav: Navigation | null, hint: {from: Ref; upcoming: Ref[]} | null,
                              decided: Set<string>): Ref | null | undefined {
  const usable = (r: Ref) => !decided.has(refKey(r)) && refKey(r) !== refKey(current);
  if (nav) {
    const list = nav.upcoming && nav.upcoming.length ? nav.upcoming : nav.next_undecided ? [nav.next_undecided] : [];
    return list.find(usable) ?? (nav.upcoming && nav.upcoming.length >= 5 ? undefined : null);
  }
  if (hint && refKey(hint.from) === refKey(current)) return hint.upcoming.find(usable);
  return undefined;
}

export function decidedKey(r: Ref) { return refKey(r); }

type Fetcher = (url: string, init: RequestInit) => Promise<{ ok: boolean; status: number; json(): Promise<any> }>;

/** POST one decision, retrying a lost or failed response with the same id. */
export async function sendDecision(body: DecisionBody, fetcher: Fetcher = fetch as unknown as Fetcher,
                                   attempts = 3, pause = (n: number) => new Promise(r => setTimeout(r, 400 * n))) {
  let last: unknown;
  for (let n = 1; n <= attempts; n++) {
    try {
      const response = await fetcher("/api/images", {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
      });
      const value = await response.json();
      if (!response.ok || value.error) throw new Error(value.error || `HTTP ${response.status}`);
      return value.decision;
    } catch (error) {
      last = error;
      if (n < attempts) await pause(n);
    }
  }
  throw last instanceof Error ? last : new Error(String(last));
}

/** Decisions in flight and those that finally failed, for every page to show. */
export class DecisionOutbox {
  pending = new Map<string, DecisionBody>();
  failures: DecisionFailure[] = [];
  decided = new Set<string>();
  private listeners = new Set<() => void>();
  private send: (body: DecisionBody) => Promise<any>;
  constructor(send: (body: DecisionBody) => Promise<any> = body => sendDecision(body)) { this.send = send; }
  subscribe(listener: () => void) { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; }
  private notify() { this.listeners.forEach(l => l()); }
  submit(body: DecisionBody): Promise<any> {
    const ref = { id: body.item, run_id: body.run };
    this.pending.set(body.event_id, body); this.decided.add(refKey(ref));
    this.failures = this.failures.filter(f => !(f.body.item === body.item && f.body.run === body.run));
    this.notify();
    return this.send(body).then(decision => {
      this.pending.delete(body.event_id); this.notify(); return decision;
    }, error => {
      this.pending.delete(body.event_id); this.decided.delete(refKey(ref));
      this.failures = [...this.failures, { body, error: String(error instanceof Error ? error.message : error) }];
      this.notify(); throw error;
    });
  }
  dismiss(failure: DecisionFailure) { this.failures = this.failures.filter(f => f !== failure); this.notify(); }
}
