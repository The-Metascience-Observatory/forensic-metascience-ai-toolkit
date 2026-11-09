"use client";

import { useEffect, useState } from "react";
import { DEFAULT_FILTER, readFilter } from "@/lib/images/filters";
import type { Filter } from "@/lib/types/images";

// v4: the default now includes unscreened candidates; a saved v3 default hid them.
const FILTER_KEY = "metascience.images.filter.v4";

/** The queue's filter: React state restored from `localStorage` per project
 *  and run selection, and written back on every change. `onRestore` runs when
 *  the key changes (a new project or run), before the saved filter is read, so
 *  the queue can reset its cursor and scroll position. `filterLoaded` names
 *  the key whose saved filter is in state; the feed waits for it. */
export function useQueueFilters(project: string, selection: string, onRestore: () => void): {
  filter: Filter; filterKey: string; filterLoaded: string | null; updateFilter: (next: Partial<Filter>) => void;
} {
  const filterKey = `${FILTER_KEY}.${project}.${selection}`;
  const [filter, setFilter] = useState<Filter>(DEFAULT_FILTER);
  const [filterLoaded,setFilterLoaded]=useState<string | null>(null);
  useEffect(() => {
    onRestore();
    setFilter(readFilter(filterKey)); setFilterLoaded(filterKey);
  }, [filterKey, onRestore]);

  function updateFilter(next: Partial<Filter>) {
    const f = { ...filter, ...next };
    setFilter(f);
    try { window.localStorage.setItem(filterKey, JSON.stringify(f)); } catch { /* fine */ }
  }

  return { filter, filterKey, filterLoaded, updateFilter };
}
