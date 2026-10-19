/** Bounded data cache with shared in-flight requests and subscriber cancellation. */
export class RequestCache<T> {
  entries = new Map<string, {data?: T; error?: string; listeners: Set<() => void>; controller?: AbortController; task?: Promise<void>}>();
  private limit: number;
  constructor(limit = 64) { this.limit = limit; }
  entry(key: string) {
    let entry = this.entries.get(key);
    if (!entry) {
      entry = {listeners: new Set()}; this.entries.set(key, entry);
      for (const [k, old] of this.entries) {
        if (this.entries.size <= this.limit) break;
        if (!old.listeners.size && k !== key) { old.controller?.abort(); this.entries.delete(k); }
      }
    }
    return entry;
  }
  subscribe(key: string, notify: () => void) {
    const entry = this.entry(key); entry.listeners.add(notify);
    return () => { entry.listeners.delete(notify); queueMicrotask(() => {
      if (!entry.listeners.size) { entry.controller?.abort(); entry.controller = undefined; entry.task = undefined; }
    }); };
  }
  load(key: string, fetcher: (signal: AbortSignal) => Promise<T>, force = false): Promise<void> {
    const entry = this.entry(key);
    if (entry.task && !force) return entry.task;
    entry.controller?.abort();
    const controller = new AbortController(); entry.controller = controller; entry.error = undefined;
    const task = fetcher(controller.signal).then(data => {
      if (controller.signal.aborted || entry.controller !== controller) return;
      entry.data = data; entry.error = undefined;
    }).catch(error => {
      if (!controller.signal.aborted && entry.controller === controller) entry.error = String(error);
    }).finally(() => {
      if (entry.controller !== controller) return;
      entry.controller = undefined; entry.task = undefined;
      entry.listeners.forEach(notify => notify());
    });
    entry.task = task; entry.listeners.forEach(notify => notify()); return task;
  }
}
