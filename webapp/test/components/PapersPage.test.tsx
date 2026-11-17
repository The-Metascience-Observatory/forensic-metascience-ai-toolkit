// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

vi.mock("next/link", () => ({ default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a> }));
import { PapersPage, MAX_ROWS, REFRESH_CHUNK } from "@/app/project/[project]/PapersPage";

type Seen = { offset: number; limit: number; q: string; sort: string };

function serve(total: number, seen: Seen[] = [], hold?: (p: URLSearchParams) => Promise<void> | undefined) {
  const offsets: number[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.startsWith("/api/images")) return new Response(JSON.stringify({ feed: { pagination: { total: 0 } } }), { status: 200 });
    const p = new URL(url, "http://x").searchParams;
    const offset = Number(p.get("offset")), limit = Number(p.get("limit"));
    offsets.push(offset);
    seen.push({ offset, limit, q: p.get("q") || "", sort: `${p.get("sort")}:${p.get("direction")}` });
    await hold?.(p);
    const papers = Array.from({ length: Math.max(0, Math.min(limit, total - offset)) }, (_, i) => ({
      paper_id: `p${offset + i}`, dir: `d${offset + i}`, title: `Paper ${offset + i}`, review: {}, runs: [], sources: {}, findings: [],
    }));
    return new Response(JSON.stringify({ papers, pagination: { total } }), { status: 200 });
  }));
  return offsets;
}

afterEach(() => vi.unstubAllGlobals());

const count = () => document.querySelector("[data-papers-count]")?.textContent;

test("loads 50, then appends 50 more, and stops at the total", async () => {
  const user = userEvent.setup();
  const offsets = serve(120);
  render(<PapersPage project="rng_europepmc_screen" />);
  await waitFor(() => expect(count()).toBe("50 of 120"));
  // The project name is in the top bar only; the page repeats no title.
  expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
  await user.click(screen.getByRole("button", { name: "Load 50 more" }));
  await waitFor(() => expect(count()).toBe("100 of 120"));
  await user.click(screen.getByRole("button", { name: "Load 20 more" }));
  await waitFor(() => expect(count()).toBe("120 of 120"));
  expect(screen.queryByRole("button", { name: /Load/ })).toBeNull();
  expect(offsets).toEqual([0, 50, 100]);
});

test(`infinite scroll stops at ${MAX_ROWS} papers and says so`, async () => {
  const user = userEvent.setup();
  serve(5000);
  render(<PapersPage project="big" />);
  await waitFor(() => expect(count()).toBe("50 of 5000"));
  for (let n = 100; n <= MAX_ROWS; n += 50) {
    await user.click(screen.getByRole("button", { name: "Load 50 more" }));
    await waitFor(() => expect(count()).toBe(`${n} of 5000`));
  }
  expect(screen.queryByRole("button", { name: /Load/ })).toBeNull();
  expect(document.querySelector("[data-papers-cap]")?.textContent).toMatch(/first 1,000 of 5,000/);
});

test("search waits for typing to pause and sends one request", async () => {
  const user = userEvent.setup();
  const seen: Seen[] = [];
  serve(120, seen);
  render(<PapersPage project="p" />);
  await waitFor(() => expect(count()).toBe("50 of 120"));
  await user.type(screen.getByRole("textbox", { name: /Search papers/ }), "elife");
  await waitFor(() => expect(seen.some((s) => s.q === "elife")).toBe(true));
  await new Promise((r) => setTimeout(r, 400));
  expect(seen.map((s) => s.q)).toEqual(["", "elife"]);
});

test("rows stay on screen while a new sort loads, then are replaced", async () => {
  const user = userEvent.setup();
  let release: () => void = () => {};
  const gate = new Promise<void>((r) => { release = r; });
  serve(120, [], (p) => (p.get("sort") === "title" ? gate : undefined));
  render(<PapersPage project="p" />);
  await waitFor(() => expect(count()).toBe("50 of 120"));
  await user.click(screen.getByRole("button", { name: /^Title/ }));
  await new Promise((r) => setTimeout(r, 50));
  expect(count()).toBe("50 of 120");
  expect(document.querySelector("[aria-busy=true]")).not.toBeNull();
  release();
  await waitFor(() => expect(document.querySelector("[aria-busy=true]")).toBeNull());
  expect(count()).toBe("50 of 120");
});

test(`the refresh re-reads loaded rows ${REFRESH_CHUNK} at a time`, async () => {
  const user = userEvent.setup();
  const seen: Seen[] = [];
  serve(120, seen);
  render(<PapersPage project="p" />);
  await waitFor(() => expect(count()).toBe("50 of 120"));
  await user.click(screen.getByRole("button", { name: "Load 50 more" }));
  await user.click(await screen.findByRole("button", { name: "Load 20 more" }));
  await waitFor(() => expect(count()).toBe("120 of 120"));
  seen.length = 0;
  window.dispatchEvent(new Event("focus"));
  await waitFor(() => expect(seen).toHaveLength(2));
  expect(seen.map((s) => [s.offset, s.limit])).toEqual([[0, 100], [100, 100]]);
  await waitFor(() => expect(count()).toBe("120 of 120"));
});
