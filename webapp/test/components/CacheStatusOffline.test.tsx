// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

// The local service going away: reported at once, retried on the
// five-second cadence (not SWR's exponential backoff), recovered silently.
vi.mock("next/navigation", () => ({ usePathname: () => "/project/project/papers" }));

import { CacheStatus } from "@/app/CacheStatus";

afterEach(() => vi.unstubAllGlobals());

test("an unreachable service is reported and retried five seconds later", async () => {
  const w = { down: true, reads: 0 };
  vi.stubGlobal("fetch", async (url: string) => {
    // The header also asks who is signed in (/api/me); count status reads only.
    if (String(url).startsWith("/api/me")) return { ok: true, json: async () => ({ mode: "local", role: "admin", projects: [] }) };
    w.reads++;
    if (w.down) throw new TypeError("Failed to fetch");
    return { ok: true, json: async () => ({ ready: true, pending_writes: 0 }) };
  });
  const { unmount } = render(<CacheStatus />);
  const status = await screen.findByText(/Offline \/ sync needs attention/);
  expect(status.getAttribute("title")).toBe("Local service unavailable");
  const failedAt = performance.now();
  w.down = false;
  await screen.findByText(/Shared records cached/, {}, { timeout: 9000 });
  expect(performance.now() - failedAt).toBeLessThan(7000);
  expect(w.reads).toBe(2);
  unmount();
}, 15_000);
