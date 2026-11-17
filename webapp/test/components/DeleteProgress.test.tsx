// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

// A stable router, as Next's is: a fresh object per render would re-run the poll effect forever.
const router = { refresh: () => {} };
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => "/x" }));
vi.mock("@/lib/useMe", () => ({ useMe: () => ({ isAdmin: true }) }));

import { AUTO_DISMISS_MS, DeleteProgress } from "@/app/DeleteProgress";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); });

const job = (id: string, state: string) => ({ id, project: `proj-${id}`, state, total: 5, done: 5, elapsed: 1,
  started_at: 1, finished_at: 2, also_removes: [], error: state === "failed" ? "boom" : null });

test("a finished deletion clears itself after 2 s; a failed one stays", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ jobs: [job("a", "done"), job("b", "failed")] }))));
  render(<DeleteProgress />);
  await screen.findByText(/Deleted proj-a/);
  expect(AUTO_DISMISS_MS).toBe(2000);
  const t0 = Date.now();
  await waitFor(() => expect(screen.queryByText(/Deleted proj-a/)).toBeNull(), { timeout: AUTO_DISMISS_MS + 1500 });
  expect(Date.now() - t0).toBeGreaterThanOrEqual(AUTO_DISMISS_MS - 100);
  expect(screen.getByText(/Delete failed: proj-b/)).toBeTruthy();
});
