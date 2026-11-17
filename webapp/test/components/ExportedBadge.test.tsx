// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ExportedBadge, itemDois, resetExportedCache } from "@/app/project/[project]/images/[item]/ExportedBadge";

type Item = Parameters<typeof ExportedBadge>[0]["item"];
const item = (dir: string, doi?: string) => ({
  id: "within:x", run_id: "r", paper: { dir, doi }, papers: [{ dir, doi }], panels: [{ paper_dir: dir }],
}) as unknown as Item;

afterEach(() => { cleanup(); resetExportedCache(); vi.unstubAllGlobals(); });
const serve = (exported: { doi: string; id: string }[]) =>
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ exported }))));

test("a paper on the website shows EXPORTED, matched by folder-name DOI", async () => {
  serve([{ doi: "10.3892/or.2013.2897", id: "yu-2014" }]);
  render(<ExportedBadge item={item("10.3892--or.2013.2897")} />);
  await waitFor(() => expect(screen.getByText("EXPORTED")).toBeTruthy());
  expect(screen.getByText("EXPORTED").getAttribute("title")).toMatch(/yu-2014/);
});

test("a paper not on the website shows no badge", async () => {
  serve([{ doi: "10.3892/or.2013.2897", id: "yu-2014" }]);
  const { container } = render(<ExportedBadge item={item("10.1000--other", "10.1000/Other")} />);
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(container.querySelector("[data-exported-badge]")).toBeNull();
});

test("the recorded DOI wins over the folder name and is lowercased", () => {
  expect(itemDois(item("folder", "10.1038/NM.2772"))).toEqual(["10.1038/nm.2772"]);
});
