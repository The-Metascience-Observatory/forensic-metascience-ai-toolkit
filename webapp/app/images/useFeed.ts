"use client";
import { useEffect } from "react";
import useSWR, { mutate as mutateGlobal, unstable_serialize, type Cache } from "swr";
import { errorMessage, getJson } from "@/lib/getJson";
import type { Feed, Item } from "./lib";

// Records are cached and polled by SWR, keyed by the request they answer.
// Every mounted hook on a key shares one request; an interval and window
// focus revalidate while the page is visible; the `workbench-review` and
// `workbench-review-synced` events are the explicit "a decision changed,
// refetch now" triggers that let one component invalidate another.
const REFRESH_MS = 30000;
const ITEM_TIMEOUT_MS = 10000;
const POLLING = { refreshInterval: REFRESH_MS, revalidateOnFocus: true, refreshWhenHidden: false } as const;

type FeedOptions = Record<string, unknown>;
type FeedKey = ["feed", string, string, string, FeedOptions];
type ItemKey = ["item", string, string, string, string, string | null, string];

const feedKey = (project: string, run: string, component: string, options: FeedOptions): FeedKey => [
  "feed", project, run, component, options,
];
const itemKey = (
  project: string, run: string, component: string, item: string, owner: string | null, method: string,
): ItemKey => ["item", project, run, component, item, owner, method];

async function fetchFeed([, project, run, component, options]: FeedKey): Promise<Feed> {
  const params = new URLSearchParams({
    project,
    run,
    component,
    ...Object.fromEntries(
      Object.entries(options).map(([k, v]) => [k, Array.isArray(v) ? JSON.stringify(v) : String(v)]),
    ),
  });
  return (await getJson<{ feed: Feed }>(`/api/images?${params}`)).feed;
}

function fetchItem([, project, run, component, item, owner, method]: ItemKey): Promise<Item> {
  const params = new URLSearchParams({ method, project, run, component, item, ...(owner ? { owner } : {}) });
  return getJson<Item>(`/api/workbench?${params}`, AbortSignal.timeout(ITEM_TIMEOUT_MS));
}

/** Apply a saved decision to every cached feed of this project, run and
 *  component (whatever its paging or filter options), then announce it. */
export function updateFeed(
  project: string,
  update: (f: Feed) => Feed,
  run = "latest",
  component = "image_forensics",
) {
  void mutateGlobal<Feed>(
    (key) =>
      Array.isArray(key) && key[0] === "feed" && key[1] === project && key[2] === run && key[3] === component,
    (feed) => (feed ? update(feed) : feed),
    { revalidate: false },
  );
  window.dispatchEvent(new Event("workbench-review"));
}

export function useFeed(
  project: string,
  run = "latest",
  component = "image_forensics",
  options: FeedOptions = {},
  enabled = true,
) {
  const key = feedKey(project, run, component, options);
  const { data, error } = useSWR<Feed>(enabled ? key : null, fetchFeed, POLLING);
  return { key: unstable_serialize(key), feed: data ?? null, error: error ? errorMessage(error) : null };
}

export function useItem(
  project: string,
  run: string,
  component: string,
  item?: string,
  owner?: string,
  method = "item",
) {
  const key = item ? itemKey(project, run, component, item, owner ?? null, method) : null;
  const serialized = key ? unstable_serialize(key) : "";
  const { data, error, mutate } = useSWR<Item>(key, fetchItem, POLLING);
  useEffect(() => {
    if (!serialized) return;
    const changed = () => void mutate();
    window.addEventListener("workbench-review", changed);
    window.addEventListener("workbench-review-synced", changed);
    return () => {
      window.removeEventListener("workbench-review", changed);
      window.removeEventListener("workbench-review-synced", changed);
    };
  }, [serialized, mutate]);
  return {
    key: serialized,
    item: data ?? null,
    error: error ? errorMessage(error) : null,
    loading: !data && !error,
    refresh: () => window.dispatchEvent(new Event("workbench-review")),
  };
}

// Decoded panel images kept alive for the items just ahead of the reviewer;
// dropping the Image object can cancel its download.
const warmImages: HTMLImageElement[] = [];
/** Load an item's compact record into the SWR cache and then its panel
 *  images, so moving to it renders from cache. `cache` (the SWR cache from
 *  `useSWRConfig`) lets an already-loaded record skip the request. Resolves
 *  to the record (or undefined on failure). */
export async function prefetchItem(
  project: string,
  run: string,
  item: string,
  mediaUrl?: (dir: string, ref: string) => string,
  cache?: Cache<Item>,
): Promise<Item | undefined> {
  const key = itemKey(project, run, "image_forensics", item, null, "item_core");
  const cached = cache?.get(unstable_serialize(key))?.data;
  const data = cached ?? (await mutateGlobal<Item>(key, fetchItem(key), { revalidate: false }).catch(() => undefined));
  if (data && mediaUrl) {
    for (const panel of data.panels || []) {
      if (!panel.image) continue;
      const image = new Image();
      image.decoding = "async";
      image.src = mediaUrl(panel.paper_dir, panel.image);
      warmImages.push(image);
      if (warmImages.length > 24) warmImages.shift();
    }
  }
  return data;
}
