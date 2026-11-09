// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { usePaperReview } from "@/app/project/[project]/review/[slug]/usePaperReview";

// The paper page's hook against a controlled transport: a `?finding=` link
// whose finding sits on another page, the detail splice, serialised saves
// and the synced-event refetch.
const row = (id: string, extra: Record<string, unknown> = {}) =>
  ({ id, kind: "rng", title: id, run: "r1", detail_key: id, group: { id: `g-${id}` }, location_basis: "page", priority: 5, ...extra });
const pages: Record<number, ReturnType<typeof row>[]> = { 0: [row("f_0"), row("f_1")], 1: [row("f_a"), row("f_b")] };
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
      const offset = finding ? 1 : Number(u.searchParams.get("offset"));
      return ok({ paper: { dir: "d" }, locators: { locators: [] },
        issues: { issues: pages[offset], review: t.review, latest_run: "r1", pagination: { offset, total: 4, next_offset: offset ? null : 1 },
                  ...(finding ? { focus_index: 0 } : {}) } });
    }
    const method = u.searchParams.get("method");
    if (method === "source") return ok({ article: { mode: "pdf" }, locators: { locators: [{ issue_id: "f_a", page: 7 }, { issue_id: "f_b", page: 8 }] } });
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
    usePaperReview({ project: "paper-project", slug: "s", dir: "d", run: null, focusFinding: "f_a" }));
  expect(result.current.data).toBeNull();

  // (1) The server answers the finding's page (offset 1): adopt it, ask once
  // more WITH the finding so the offsets agree, then the focus is consumed.
  await waitFor(() => expect(result.current.offset).toBe(1));
  await waitFor(() => expect(t.paper.filter((p) => p.get("finding") === "f_a" && p.get("offset") === "1").length).toBe(1));
  await waitFor(() => expect(result.current.issues.map((i) => i.id)).toEqual(["f_a", "f_b"]));
  expect(result.current.at).toBe(0);
  expect(t.paper[0].get("offset")).toBe("0");
  expect(t.paper[0].get("finding")).toBe("f_a");
  expect(t.paper[0].get("group")).toBe("1");
  await waitFor(() => expect(result.current.data?.article).toEqual({ mode: "pdf" }));

  // (2) The detail is spliced over the focused row; the list's group,
  // location basis and priority stay; its locators replace the summary's.
  await waitFor(() => expect(result.current.issues[0].notes).toBe("detail f_a"));
  expect(result.current.issues[0].group).toEqual({ id: "g-f_a" });
  expect(result.current.issues[0].location_basis).toBe("page");
  expect(result.current.issues[0].priority).toBe(5);
  expect(result.current.issues[1].notes).toBeUndefined();
  expect(result.current.data?.locators?.locators).toEqual([{ issue_id: "f_b", page: 8 }, { issue_id: "f_a", page: 9 }]);
  expect(result.current.detailError).toBe("");

  // (3) Saves are one POST each, in order, one at a time; each updates the review.
  act(() => {
    result.current.save({ issue_id: "f_a", decision: "confirmed" });
    result.current.save({ status: "complete" });
  });
  await waitFor(() => expect(t.posts.length).toBe(2));
  expect(t.posts[0].body).toEqual({ project: "paper-project", slug: "s", dir: "d", reviewer: "Tester", patch: { issue_id: "f_a", decision: "confirmed", run: "r1" } });
  expect(t.posts[1].body.patch).toEqual({ status: "complete", run: "r1" });
  expect(t.posts[1].at).toBeGreaterThanOrEqual(t.firstPostDone);
  await waitFor(() => expect(result.current.review?.paper.status).toBe("complete"));
  expect(result.current.review?.issues.f_a).toEqual({ decision: "confirmed" });

  // (4) The synced event refetches the paper (without the consumed finding).
  const reads = t.paper.length;
  act(() => { window.dispatchEvent(new Event("workbench-review-synced")); });
  await waitFor(() => expect(t.paper.length).toBe(reads + 1));
  expect(t.paper[reads].get("finding")).toBeNull();
  expect(t.paper[reads].get("offset")).toBe("1");
  await waitFor(() => expect(result.current.issues[0].notes).toBe("detail f_a"));

  // Later paging is the reader's own: no `finding`, first row focused.
  act(() => { result.current.setOffset(0); });
  await waitFor(() => expect(result.current.issues.map((i) => i.id)).toEqual(["f_0", "f_1"]));
  const page0 = t.paper.filter((p) => p.get("offset") === "0");
  expect(page0.length).toBeGreaterThanOrEqual(2);
  expect(page0[page0.length - 1].get("finding")).toBeNull();
  expect(t.paper.filter((p) => p.get("finding")).length).toBe(2);
  expect(result.current.at).toBe(0);
  unmount();
}, 20_000);
