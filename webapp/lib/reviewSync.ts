export const REVIEW_QUEUED_MESSAGE = "Decision saved locally; synchronizing with database…";

export function reviewSyncCompleted(previousPending: number, currentPending: number) {
  return previousPending > currentPending;
}

export type ReviewSyncState = {synced_at?:string;ready?:boolean;error?:string;file_monitor_error?:string;warmup_error?:string;pending_writes?:number;pending_errors?:string[]};

// Only local status is polled. A save wakes the database worker separately.
export function watchReviewSync(options: {
  read: () => Promise<ReviewSyncState>;
  update: (state: ReviewSyncState) => void;
  completed: () => void;
  visible: () => boolean;
}) {
  let stopped = false, running = false, requested = false;
  let previousPending = 0, saves = 0, observedSaves = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const schedule = (delay: number) => {
    clearTimeout(timer);
    if (!stopped) timer = setTimeout(() => void read(), delay);
  };
  async function read() {
    if (stopped) return;
    if (running) { requested = true; return; }
    clearTimeout(timer);
    if (!options.visible()) { schedule(30000); return; }
    running = true;
    const generation = saves;
    let delay = 30000;
    try {
      const state = await options.read();
      if (stopped) return;
      options.update(state);
      // A response started before the latest save cannot acknowledge that save.
      if (generation === saves && typeof state.pending_writes === "number") {
        const pending = Number(state.pending_writes || 0);
        const completed = reviewSyncCompleted(previousPending, pending) ||
          (generation > observedSaves && pending === 0);
        previousPending = pending;
        if (pending === 0) { observedSaves = generation; }
        if (completed) options.completed();
        if (pending > 0) delay = 5000;
      }
    } catch {
      delay = 5000;
      if (!stopped) options.update({error: "Local service unavailable"});
    } finally {
      running = false;
      if (!stopped) {
        if (requested) { requested = false; schedule(0); }
        else schedule(delay);
      }
    }
  }
  void read();
  return {
    saved() { saves++; void read(); },
    refresh() { void read(); },
    stop() { stopped = true; clearTimeout(timer); },
  };
}
