// @vitest-environment jsdom
import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

// An image page reads local image status and never writes to shared storage.
vi.mock("next/navigation", () => ({ usePathname: () => "/project/project/images/item" }));

import { CacheStatus } from "@/app/CacheStatus";

afterEach(() => vi.unstubAllGlobals());

test("local image status and focus never synchronize shared storage", async () => {
  const w = { imageReads: 0, sharedWrites: 0 };
  vi.stubGlobal("fetch", async (url: string, options?: RequestInit) => {
    if (options?.method === "POST") w.sharedWrites++;
    if (String(url).includes("method=image_status")) w.imageReads++;
    return { ok: true, json: async () => ({ ready: true, local: true, pending_writes: 0 }) };
  });
  const { unmount } = render(<CacheStatus />);
  await screen.findByText(/Saved on this computer/);
  const before = w.imageReads;
  act(() => { window.dispatchEvent(new Event("focus")); });
  await waitFor(() => expect(w.imageReads).toBeGreaterThan(before));
  expect(w.sharedWrites).toBe(0);
  unmount();
});
