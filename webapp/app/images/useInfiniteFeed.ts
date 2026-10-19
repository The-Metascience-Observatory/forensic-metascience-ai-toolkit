"use client";
import { useCallback, useEffect, useMemo, useState } from 'react';
import { RequestCache } from '@/lib/requestCache';
import { queuePages } from '@/lib/infiniteFeed';
import type { Feed, Filter } from './lib';

const cache = new RequestCache<Feed[]>(8);
// Facet counts and run options are separate, cheaper-to-skip requests: the
// counts cost up to ~0.5 s on a 67k-item queue and every decision changes
// them, and the run list (~31 KB) changes only when runs are imported. Rows
// no longer wait for either.
const facetCache = new RequestCache<Partial<Feed>>(8);
const runCache = new RequestCache<Pick<Feed, 'runs'>>(8);
const FACET_QUIET_MS = 1500;

function queryOf(project: string, run: string, filter: Record<string, unknown>, extra: Record<string, string>) {
  return new URLSearchParams({project, run, component:'image_forensics',
    ...Object.fromEntries(Object.entries(filter).map(([k,v]) => [k,Array.isArray(v) ? JSON.stringify(v) : String(v)])), ...extra});
}
async function getJson(url: string, signal: AbortSignal) {
  const response = await fetch(url, {signal});
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || response.statusText);
  return body;
}

export function useInfiniteFeed(project: string, run: string, filter: Filter, enabled: boolean) {
  const key = JSON.stringify([project, run, filter]);
  const runKey = JSON.stringify([project, run]);
  const [, render] = useState(0);
  const request = useCallback((mode: 'refresh' | 'more', rebuild = false, force = false) => {
    if (!enabled) return;
    void cache.load(key, signal => queuePages(cache.entry(key).data || [], mode, async offset => {
      const params = queryOf(project, run, JSON.parse(key)[2], {offset:String(offset), facets:'none',
        ...(rebuild && offset === 0 ? {rebuild:'1'} : {})});
      return (await getJson(`/api/images?${params}`, signal)).feed as Feed;
    }), force);
  }, [key, project, run, enabled]);
  const loadFacets = useCallback((force = false) => {
    if (!enabled) return;
    void facetCache.load(key, async signal =>
      (await getJson(`/api/images?${queryOf(project, run, JSON.parse(key)[2], {view:'facets'})}`, signal)).feed, force);
  }, [key, project, run, enabled]);
  const loadRuns = useCallback((force = false) => {
    if (!enabled) return;
    void runCache.load(runKey, async signal =>
      (await getJson(`/api/images?${queryOf(project, run, {}, {view:'runs'})}`, signal)).feed, force);
  }, [runKey, project, run, enabled]);
  useEffect(() => {
    if (!enabled) return;
    const unsubscribe = cache.subscribe(key, () => render(n => n + 1));
    const unsubscribeFacets = facetCache.subscribe(key, () => render(n => n + 1));
    const unsubscribeRuns = runCache.subscribe(runKey, () => render(n => n + 1));
    let quiet: ReturnType<typeof setTimeout> | undefined;
    // Counts follow a burst of decisions once it pauses, never each one.
    const facetsLater = () => { clearTimeout(quiet); quiet = setTimeout(() => loadFacets(true), FACET_QUIET_MS); };
    const refresh = () => { if (!document.hidden) { request('refresh'); loadFacets(); } };
    const reviewed = () => { request('refresh', false, true); facetsLater(); };
    request('refresh'); loadFacets(); loadRuns();
    const timer = setInterval(refresh, 30000);
    window.addEventListener('focus', refresh);
    window.addEventListener('workbench-review-synced', reviewed);
    window.addEventListener('workbench-review', reviewed);
    document.addEventListener('visibilitychange', refresh);
    return () => {
      unsubscribe(); unsubscribeFacets(); unsubscribeRuns(); clearInterval(timer); clearTimeout(quiet);
      window.removeEventListener('focus', refresh);
      window.removeEventListener('workbench-review-synced', reviewed);
      window.removeEventListener('workbench-review', reviewed);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, [enabled, key, runKey, request, loadFacets, loadRuns]);
  const entry = cache.entry(key);
  const pages = enabled ? entry.data : undefined;
  const facets = enabled ? facetCache.entry(key).data : undefined;
  const runs = enabled ? runCache.entry(runKey).data : undefined;
  const feed = useMemo(() => pages?.length ? {counts:{}, notes:[], ...runs, ...facets, ...(pages[0] as Partial<Feed>), items:pages.flatMap(page => page.items),
    pagination:pages[pages.length - 1].pagination} as Feed : null, [pages, facets, runs]);
  return {feed, error:entry.error || null, loading:!!entry.task, facetsLoading:!facets,
    loadMore:useCallback(() => request('more'), [request]),
    refresh:useCallback((rebuild = false) => { request('refresh', rebuild, rebuild); loadFacets(true); if (rebuild) loadRuns(true); }, [request, loadFacets, loadRuns])};
}
