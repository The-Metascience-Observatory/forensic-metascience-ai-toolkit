// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { usePaperReview } from "@/app/project/[project]/review/[slug]/usePaperReview";

// The paper page's hook against a controlled transport: a `?finding=` link
// whose finding sits past the first 100 (the list widens to reach it), the
// detail splice, serialised saves, the synced-event refetch and loading more.
const row = (id: string, extra: Record<string, unknown> = {}) =>
  ({ id, kind: "rng", title: id, run: "r1", detail_key: id, group: { id: `g-${id}` }, location_basis: "page", priority: 5, ...extra });
// 250 findings; the linked one, f_120, is past the first 100.
const all = Array.from({ length: 250 }, (_, n) => row(`f_${n}`));
afterEach(() => vi.unstubAllGlobals());

test("finding focus across pages, detail splice, serialised saves and synced refetch", async () => {
  const t = { paper: [] as URLSearchParams[], posts: [] as { url: string; body: Record<string, unknown>; at: number }[],
              firstPostDone: 0, review: { issues: {} as Record<string, unknown>, paper: {} as Record<string, unknown> } };
  const ok = (body: unknown) => ({ ok: true, json: async () => body });
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const u = new URL(String(url), "http://localhost");
    if (init?.method === "POST") {
      if (u.pathname === "/api/viewed") return ok({});
      const body = JSON.parse(String(init.body));
      t.posts.push({ url: u.pathname, body, at: performance.now() });
      if (t.posts.length === 1) { await new Promise((r) => setTimeout(r, 120)); t.firstPostDone = performance.now(); }
      const patch = body.patch;
      if (patch.issue_id) t.review = { ...t.review, issues: { ...t.review.issues, [patch.issue_id]: { decision: patch.decision } } };
      else t.review = { ...t.review, paper: { ...t.review.paper, status: patch.status } };
      return ok({ review: t.review });
    }
    if (u.pathname === "/api/paper") {
      t.paper.push(u.searchParams);
      const finding = u.searchParams.get("finding");
      let limit = Number(u.searchParams.get("limit"));
      const fi = finding ? all.findIndex((r) => r.id === finding) : -1;
      if (fi >= limit) limit = (Math.floor(fi / 100) + 1) * 100;
      return ok({ paper: { dir: "d" }, locators: { locators: [] },
        issues: { issues: all.slice(0, limit), review: t.review, latest_run: "r1",
                  pagination: { offset: 0, limit, total: all.length, next_offset: limit < all.length ? limit : null },
                  ...(finding ? { focus_index: fi } : {}) } });
    }
    const method = u.searchParams.get("method");
    if (method === "source") return ok({ article: { mode: "pdf" }, locators: { locators: [{ issue_id: "f_120", page: 7 }, { issue_id: "f_121", page: 8 }] } });
    if (method === "issue_detail") {
      const id = u.searchParams.get("finding")!;
      expect(u.searchParams.get("run")).toBe("r1");
      return ok({ issue: { ...row(id), group: null, location_basis: "DETAIL", priority: undefined, detail_loaded: true, notes: `detail ${id}` },
                  locators: { locators: [{ issue_id: id, page: 9 }] } });
    }
    throw new Error(`unexpected ${url}`);
  });
  window.localStorage.setItem("metascience.reviewer", "Tester");
  const { result, unmount } = renderHook(() =>
    usePaperReview({ project: "paper-project", slug: "s", dir: "d", run: null, focusFinding: "f_120" }));
  expect(result.current.data).toBeNull();

  // (1) The server widens the list to hold the finding (limit 200): adopt
  // it, ask once more WITH the finding so the two agree, then it is consumed.
  await waitFor(() => expect(t.paper.filter((p) => p.get("finding") === "f_120" && p.get("limit") === "200").length).toBe(1));
  await waitFor(() => expect(result.current.issues.length).toBe(200));
  await waitFor(() => expect(result.current.at).toBe(120));
  expect(t.paper[0].get("offset")).toBe("0");
  expect(t.paper[0].get("limit")).toBe("100");
  expect(t.paper[0].get("finding")).toBe("f_120");
  expect(t.paper[0].get("group")).toBe("1");
  await waitFor(() => expect(result.current.data?.article).toEqual({ mode: "pdf" }));

  // (2) The detail is spliced over the focused row; the list's group,
  // location basis and priority stay; its locators replace the summary's.
  await waitFor(() => expect(result.current.issues[120].notes).toBe("detail f_120"));
  expect(result.current.issues[120].group).toEqual({ id: "g-f_120" });
  expect(result.current.issues[120].location_basis).toBe("page");
  expect(result.current.issues[120].priority).toBe(5);
  expect(result.current.issues[121].notes).toBeUndefined();
  expect(result.current.data?.locators?.locators).toEqual([{ issue_id: "f_121", page: 8 }, { issue_id: "f_120", page: 9 }]);
  expect(result.current.detailError).toBe("");

  // (3) Saves are one POST each, in order, one at a time; each updates the review.
  act(() => {
    result.current.save({ issue_id: "f_120", decision: "confirmed" });
    result.current.save({ status: "complete" });
  });
  await waitFor(() => expect(t.posts.length).toBe(2));
  expect(t.posts[0].body).toEqual({ project: "paper-project", slug: "s", dir: "d", reviewer: "Tester", patch: { issue_id: "f_120", decision: "confirmed", run: "r1" } });
  expect(t.posts[1].body.patch).toEqual({ status: "complete", run: "r1" });
  expect(t.posts[1].at).toBeGreaterThanOrEqual(t.firstPostDone);
  await waitFor(() => expect(result.current.review?.paper.status).toBe("complete"));
  expect(result.current.review?.issues.f_120).toEqual({ decision: "confirmed" });

  // (4) The synced event refetches the paper (without the consumed finding).
  const reads = t.paper.length;
  act(() => { window.dispatchEvent(new Event("workbench-review-synced")); });
  await waitFor(() => expect(t.paper.length).toBe(reads + 1));
  expect(t.paper[reads].get("finding")).toBeNull();
  expect(t.paper[reads].get("limit")).toBe("200");
  await waitFor(() => expect(result.current.issues[120].notes).toBe("detail f_120"));

  // (5) Scrolling to the end loads the next 100; the rows on screen and the
  // focused one stay while it loads.
  expect(result.current.hasMore).toBe(true);
  act(() => { result.current.loadMore(); });
  expect(result.current.issues.length).toBe(200);
  await waitFor(() => expect(result.current.issues.length).toBe(250));
  expect(t.paper[t.paper.length - 1].get("limit")).toBe("300");
  expect(t.paper[t.paper.length - 1].get("finding")).toBeNull();
  expect(result.current.at).toBe(120);
  expect(result.current.hasMore).toBe(false);
  unmount();
}, 20_000);
