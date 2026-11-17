// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

vi.mock("next/link", () => ({ default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a> }));
import { PapersPage, MAX_ROWS } from "@/app/project/[project]/PapersPage";

function serve(total: number) {
  const offsets: number[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const p = new URL(url, "http://x").searchParams;
    const offset = Number(p.get("offset")), limit = Number(p.get("limit"));
    offsets.push(offset);
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
