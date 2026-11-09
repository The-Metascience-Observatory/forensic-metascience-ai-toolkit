"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import useSWR, { unstable_serialize, useSWRConfig } from "swr";
import { errorMessage, getJson, postJson } from "@/lib/getJson";
import { queuePages } from "@/lib/infiniteFeed";
import type { Feed, Filter } from "./lib";

// Three SWR keys per queue view. The rows are ONE key holding every loaded
// page, so `queuePages` can keep them in a single repository revision and
// retake the snapshot when a review bumped it (lib/infiniteFeed.ts). Facet
// counts and run options are separate, cheaper-to-skip requests: the counts
// cost up to ~0.5 s on a 67k-item queue and every decision changes them, and
// the run list (~31 KB) changes only when runs are imported. Rows never wait
// for either.
const COMPONENT = "image_forensics";
const REFRESH_MS = 30000;
const FACET_QUIET_MS = 1500;
const POLLING = { refreshInterval: REFRESH_MS, revalidateOnFocus: true, refreshWhenHidden: false } as const;

type QueueKey = ["queue", string, string, Filter];
type FacetKey = ["facets", string, string, Filter];
type RunKey = ["runs", string, string];

function queryOf(project: string, run: string, filter: Partial<Filter>, extra: Record<string, string>) {
  return new URLSearchParams({
    project,
    run,
    component: COMPONENT,
    ...Object.fromEntries(
      Object.entries(filter).map(([k, v]) => [k, Array.isArray(v) ? JSON.stringify(v) : String(v)]),
    ),
    ...extra,
  });
}
const pageFetcher = (project: string, run: string, filter: Filter) => async (offset: number) =>
  (await getJson<{ feed: Feed }>(`/api/images?${queryOf(project, run, filter, { offset: String(offset), facets: "none" })}`)).feed;
const fetchFacets = async ([, project, run, filter]: FacetKey) =>
  (await getJson<{ feed: Partial<Feed> }>(`/api/images?${queryOf(project, run, filter, { view: "facets" })}`)).feed;
const fetchRuns = async ([, project, run]: RunKey) =>
  (await getJson<{ feed: Pick<Feed, "runs"> }>(`/api/images?${queryOf(project, run, {}, { view: "runs" })}`)).feed;

export function useInfiniteFeed(project: string, run: string, filter: Filter, enabled: boolean) {
  const { cache } = useSWRConfig();
  const fetchPage = useMemo(() => pageFetcher(project, run, filter), [project, run, filter]);
  // A "more" or "sync" request in flight, and the error of the last one: a
  // failed next batch keeps the loaded rows (the cache is untouched) and the
  // queue offers "Retry loading".
  const [more, setMore] = useState<{ loading: boolean; error: string | null }>({ loading: false, error: null });
  const inFlight = useRef(false);

  const queueKey: QueueKey | null = enabled ? ["queue", project, run, filter] : null;
  const queue = useSWR<Feed[], Error>(
    queueKey,
    // Revalidation (interval, focus, mount, a review event) refreshes every
    // loaded page together, in one revision, from whatever is cached now.
    async (key: QueueKey) => {
      const current = (cache.get(unstable_serialize(key))?.data as Feed[] | undefined) ?? [];
      return queuePages(current, "refresh", fetchPage);
    },
    { ...POLLING, onSuccess: () => setMore((m) => (m.error ? { ...m, error: null } : m)) },
  );
  const facets = useSWR<Partial<Feed>, Error>(enabled ? (["facets", project, run, filter] as FacetKey) : null, fetchFacets, POLLING);
  const runs = useSWR<Pick<Feed, "runs">, Error>(enabled ? (["runs", project, run] as RunKey) : null, fetchRuns, {
    revalidateOnFocus: false,
  });

  const { mutate: mutateQueue } = queue;
  const { mutate: mutateFacets } = facets;
  const { mutate: mutateRuns } = runs;
  const extend = useCallback(
    async (mode: "more" | "sync") => {
      if (!enabled || inFlight.current) return;
      inFlight.current = true;
      setMore({ loading: true, error: null });
      try {
        await mutateQueue(
          async (current = []) => {
            // "Sync records" pulls changed shared records first. A write, so
            // its own POST (it used to ride on the GET as `rebuild=1`), then
            // the read.
            if (mode === "sync") await postJson("/api/images/sync", { component: COMPONENT });
            return queuePages(current, mode === "more" ? "more" : "refresh", fetchPage);
          },
          { revalidate: false },
        );
        setMore({ loading: false, error: null });
      } catch (error) {
        setMore({ loading: false, error: errorMessage(error) });
      } finally {
        inFlight.current = false;
      }
    },
    [enabled, mutateQueue, fetchPage],
  );

  useEffect(() => {
    if (!enabled) return;
    let quiet: ReturnType<typeof setTimeout> | undefined;
    const reviewed = () => {
      void mutateQueue();
      // Counts follow a burst of decisions once it pauses, never each one.
      clearTimeout(quiet);
      quiet = setTimeout(() => void mutateFacets(), FACET_QUIET_MS);
    };
    window.addEventListener("workbench-review-synced", reviewed);
    window.addEventListener("workbench-review", reviewed);
    return () => {
      clearTimeout(quiet);
      window.removeEventListener("workbench-review-synced", reviewed);
      window.removeEventListener("workbench-review", reviewed);
    };
  }, [enabled, mutateQueue, mutateFacets]);

  const pages = queue.data;
  const feed = useMemo(
    () =>
      pages?.length
        ? ({
            counts: {},
            notes: [],
            ...runs.data,
            ...facets.data,
            ...(pages[0] as Partial<Feed>),
            items: pages.flatMap((page) => page.items),
            pagination: pages[pages.length - 1].pagination,
          } as Feed)
        : null,
    [pages, facets.data, runs.data],
  );
  const loadMore = useCallback(() => void extend("more"), [extend]);
  const refresh = useCallback(
    (rebuild = false) => {
      if (rebuild) {
        void extend("sync");
        void mutateRuns();
      } else void mutateQueue();
      void mutateFacets();
    },
    [extend, mutateQueue, mutateFacets, mutateRuns],
  );
  return {
    feed,
    error: more.error ?? (queue.error ? errorMessage(queue.error) : null),
    loading: queue.isValidating || more.loading,
    facetsLoading: !facets.data,
    loadMore,
    refresh,
  };
}
