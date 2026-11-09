export const REVIEW_QUEUED_MESSAGE = "Decision saved locally; synchronizing with database…";

export function reviewSyncCompleted(previousPending: number, currentPending: number) {
  return previousPending > currentPending;
}

export type ReviewSyncState = {
  synced_at?: string;
  ready?: boolean;
  error?: string;
  file_monitor_error?: string;
  warmup_error?: string;
  pending_writes?: number;
  pending_errors?: string[];
};

/** One status response, with the save generation its request was made under
 *  (`ReviewSyncTracker.saves` at that moment). */
export type ReviewSyncReading = { state: ReviewSyncState; generation: number };

/** Status polling cadence (docs/workbench_storage.md, "Queues and production
 *  review"): 30 s normally, 5 s while writes are pending or the local service
 *  is unreachable. Shaped as SWR's `refreshInterval(data)` callback. */
export const REVIEW_SYNC_IDLE_MS = 30000;
export const REVIEW_SYNC_PENDING_MS = 5000;
export function reviewSyncInterval(reading?: ReviewSyncReading, failed = false): number {
  if (failed) return REVIEW_SYNC_PENDING_MS;
  return (reading?.state.pending_writes ?? 0) > 0 ? REVIEW_SYNC_PENDING_MS : REVIEW_SYNC_IDLE_MS;
}

/** Decides, from successive status readings, when a saved decision has
 *  reached the database -- the moment the item and queue views must refresh
 *  their judgments. Only local status is polled; a save wakes the database
 *  worker separately. A reading acknowledges a save when the pending count
 *  dropped, or when a save was announced and the service reports none
 *  pending. A response requested before the latest save cannot acknowledge
 *  that save, so each reading carries the generation it was requested under. */
export class ReviewSyncTracker {
  /** Saves announced so far (`workbench-review` events). */
  saves = 0;
  private previousPending = 0;
  private observedSaves = 0;
  saved() {
    this.saves++;
  }
  observe(reading: ReviewSyncReading): boolean {
    if (reading.generation !== this.saves || typeof reading.state.pending_writes !== "number") return false;
    const pending = Number(reading.state.pending_writes || 0);
    const completed =
      reviewSyncCompleted(this.previousPending, pending) ||
      (reading.generation > this.observedSaves && pending === 0);
    this.previousPending = pending;
    if (pending === 0) this.observedSaves = reading.generation;
    return completed;
  }
}
