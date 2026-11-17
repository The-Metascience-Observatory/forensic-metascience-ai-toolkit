// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));
let pathname = "/";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));
import { ProjectTabs } from "@/app/project/[project]/ProjectTabs";
import { ProjectCrumb } from "@/app/ProjectCrumb";

afterEach(() => vi.unstubAllGlobals());

function feed(reply: Response) {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => { calls.push(url); return reply; }));
  return calls;
}

test("the image tab is a link when the project has image findings", async () => {
  const calls = feed(new Response(JSON.stringify({ feed: { pagination: { total: 3 } } }), { status: 200 }));
  render(<ProjectTabs project="p 1" active="findings" />);
  const link = await screen.findByRole("link", { name: "Image findings" });
  expect(link.getAttribute("href")).toBe("/project/p%201/images");
  const findings = screen.getByRole("link", { name: "Non-image findings" });
  expect(findings.getAttribute("aria-current")).toBe("page");
  // An explicit choice: the project page never redirects it to the image tab.
  expect(findings.getAttribute("href")).toBe("/project/p%201?view=findings");
  expect(calls[0]).toContain("verdict=all");
});

test("the image tab is greyed out and not a link when there are none", async () => {
  feed(new Response(JSON.stringify({ feed: { pagination: { total: 0 } } }), { status: 200 }));
  render(<ProjectTabs project="p" active="findings" />);
  await waitFor(() => expect(document.querySelector("[data-tab-disabled]")?.getAttribute("title")).toMatch(/no image findings/));
  expect(screen.queryByRole("link", { name: "Image findings" })).toBeNull();
});

test("a service error (no image results registered) also greys it out", async () => {
  feed(new Response(JSON.stringify({ error: "LookupError: No local folder" }), { status: 500 }));
  render(<ProjectTabs project="p" active="findings" />);
  await waitFor(() => expect(document.querySelector("[data-tab-disabled]")?.getAttribute("title")).toMatch(/no image findings/));
});

test("the top bar names the project only on project pages", () => {
  pathname = "/";
  const { container, rerender } = render(<ProjectCrumb />);
  expect(container.textContent).toBe("");
  pathname = "/project/rng_europepmc_screen/review/x";
  rerender(<ProjectCrumb />);
  expect(screen.getByRole("link", { name: "rng_europepmc_screen project" }).getAttribute("href")).toBe("/project/rng_europepmc_screen");
});
