// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { useInfiniteFeed } from "@/app/images/useInfiniteFeed";
import { DEFAULT_FILTER } from "@/lib/images/filters";

// The queue hook against a controlled transport: rows, facets and runs are
// separate requests; a failed next batch keeps the rows; a review retakes
// every loaded page in the new revision and the counts follow after the
// quiet period; "Sync records" is a POST before the reads.
const page = (offset: number, revision: string, total: number) => ({
  revision, project: "p", built_at: "now", seconds: 0, counts: { items: total }, notes: [],
  items: Array.from({ length: Math.min(50, total - offset) }, (_, n) => ({ id: String(offset + n), run_id: "r" })),
  pagination: { offset, limit: 50, total, next_offset: offset + 50 < total ? offset + 50 : null },
});
afterEach(() => vi.unstubAllGlobals());

test("paging, failed batch retry, revision retake, facet quiet period and sync", async () => {
  const t = { revision: "one", total: 120, failNext: false, calls: [] as string[], posts: 0 };
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    t.calls.push(String(url));
    if (init?.method === "POST") { t.posts++; return { ok: true, json: async () => ({}) }; }
    const params = new URL(String(url), "http://localhost").searchParams;
    if (params.get("view") === "facets") return { ok: true, json: async () => ({ feed: { judgment_counts: { issue: 3 } } }) };
    if (params.get("view") === "runs") return { ok: true, json: async () => ({ feed: { runs: [{ id: "r" }] } }) };
    const offset = Number(params.get("offset") || 0);
    if (offset > 0 && t.failNext) return { ok: false, statusText: "Service Unavailable", json: async () => ({ error: "queue page unavailable" }) };
    return { ok: true, json: async () => ({ feed: page(offset, t.revision, t.total) }) };
  });
  const facetReads = () => t.calls.filter((u) => u.includes("view=facets")).length;
  const { result, unmount } = renderHook(() => useInfiniteFeed("project-infinite", "latest", DEFAULT_FILTER, true));
  await waitFor(() => expect(result.current.feed?.items.length).toBe(50));
  await waitFor(() => expect(result.current.feed?.judgment_counts).toEqual({ issue: 3 }));
  await waitFor(() => expect(result.current.feed?.runs).toEqual([{ id: "r" }]));
  expect(result.current.facetsLoading).toBe(false);
  expect(t.calls.find((u) => u.includes("offset=0"))).toMatch(/facets=none/);

  // A failed next batch keeps the loaded rows and offers a retry.
  t.failNext = true;
  act(() => result.current.loadMore());
  await waitFor(() => expect(result.current.error).toMatch(/queue page unavailable/));
  expect(result.current.feed?.items.length).toBe(50);
  expect(result.current.loading).toBe(false);
  t.failNext = false;
  act(() => result.current.loadMore());
  await waitFor(() => expect(result.current.feed?.items.length).toBe(100));
  expect(result.current.error).toBeNull();
  expect(result.current.feed?.pagination?.next_offset).toBe(100);

  // A saved review bumped the revision: both pages are retaken in the new
  // snapshot, and the counts follow once the burst pauses, not at once.
  t.revision = "two"; t.total = 110;
  const facetsBefore = facetReads();
  act(() => window.dispatchEvent(new Event("workbench-review")));
  await waitFor(() => expect(result.current.feed?.revision).toBe("two"));
  expect(result.current.feed?.items.length).toBe(100);
  expect(result.current.feed?.pagination?.total).toBe(110);
  expect(facetReads()).toBe(facetsBefore);
  await waitFor(() => expect(facetReads()).toBe(facetsBefore + 1), { timeout: 4000 });

  // "Sync records" is a write first, then the rows, counts and runs again.
  const runReads = t.calls.filter((u) => u.includes("view=runs")).length;
  act(() => result.current.refresh(true));
  await waitFor(() => expect(t.posts).toBe(1));
  await waitFor(() => expect(result.current.loading).toBe(false));
  await waitFor(() => expect(t.calls.filter((u) => u.includes("view=runs")).length).toBe(runReads + 1));
  expect(t.calls.filter((u) => u.includes("/api/images/sync")).length).toBe(1);
  unmount();
}, 20_000);
