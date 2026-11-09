// @vitest-environment jsdom
import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

// Render the actual status and item hooks against a controlled transport.
// One scenario per file: the hooks keep window listeners and timers whose
// teardown would otherwise bleed into the next test.
vi.mock("next/navigation", () => ({ usePathname: () => "/project/project/papers" }));

import { CacheStatus, ReviewJudgments } from "@/app/CacheStatus";
import { useItem } from "@/app/images/useFeed";

afterEach(() => vi.unstubAllGlobals());

test("delayed and immediate acknowledgment refresh the item; unmount stops polling", async () => {
  const w = { pending: 0, statusReads: 0, syncEvents: 0, hasDecision: false, notified: 0, acknowledged: 0 };
  vi.stubGlobal("fetch", async (url: string) => {
    if (String(url).includes("method=status")) {
      w.statusReads++;
      return { ok: true, json: async () => ({ ready: true, pending_writes: w.pending }) };
    }
    return { ok: true, json: async () => ({ reviews: { reviewers: w.hasDecision
      ? [{ reviewer: "Test", decision: "confirmed", pending: !!w.pending }] : [] } }) };
  });
  window.addEventListener("workbench-review-synced", () => { w.syncEvents++; w.notified = performance.now(); });
  function Harness() {
    const { item } = useItem("project", "run", "image", "item");
    return <><CacheStatus /><ReviewJudgments reviews={item?.reviews} /></>;
  }
  const { unmount } = render(<Harness />);
  await waitFor(() => expect(w.statusReads).toBeGreaterThan(0));
  act(() => { w.hasDecision = true; w.pending = 1; window.dispatchEvent(new Event("workbench-review")); });
  await waitFor(() => expect(document.body.textContent).toMatch(/pending sync/));
  w.pending = 0; w.acknowledged = performance.now();
  // Pending reviews poll on the five-second interval; allow scheduling overhead.
  await waitFor(() => { expect(w.syncEvents).toBe(1); expect(document.body.textContent).not.toMatch(/pending sync/); },
                { timeout: 9000 });
  expect(w.notified - w.acknowledged).toBeLessThan(6500);
  act(() => { window.dispatchEvent(new Event("workbench-review")); });
  await waitFor(() => expect(w.syncEvents).toBe(2));
  unmount();
  const reads = w.statusReads;
  await new Promise((r) => setTimeout(r, 600));
  expect(w.statusReads).toBe(reads);
}, 30_000);
