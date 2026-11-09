// @vitest-environment jsdom
import { readFileSync } from "node:fs";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import { ProjectsTable } from "@/app/ProjectsTable";

// Imported image results must reach the landing page: every catalog project
// gets its image-review counts joined, and image projects the catalog does
// not list yet are appended rather than hidden (Yadong Huang's, 2026-09-30).
test("the home page joins image-review counts onto every listed project", () => {
  const home = readFileSync("app/page.tsx", "utf8");
  expect(home).toMatch(/<ProjectsTable\s+projects=\{withImageReviews\(listed,\s*counts\)\}/);
  expect(home).toMatch(/const listed\s*=\s*\[\.\.\.index\.projects,\s*\.\.\.imageOnlyProjects\(index\.projects,\s*counts\)\]/);
});

const fields = ["n_papers", "n_pdf", "n_xml", "n_image_run", "n_text_run", "n_human_reviewed"] as const;
const labels = ["Papers", "With PDF", "With XML", "Image track", "Text track", "Human reviewed"];
const rows = [2, 10, 0, null].map((value, i) => ({
  name: ["two", "ten", "zero", "unknown"][i],
  ...Object.fromEntries(fields.map((f) => [f, value])),
  n_not_fetched: 0, n_in_progress: 0,
})) as unknown as Parameters<typeof ProjectsTable>[0]["projects"];

test("all six numeric columns sort both ways; missing counts stay last", async () => {
  const user = userEvent.setup();
  render(<ProjectsTable projects={rows} />);
  const names = () => [...document.querySelectorAll("tbody tr td:first-child a")].map((a) => a.textContent);
  for (const label of labels) {
    const button = screen.getByRole("button", { name: new RegExp("^" + label + " ") });
    await user.click(button);
    expect(names()).toEqual(["ten", "two", "zero", "unknown"]);
    expect(document.querySelectorAll('th[aria-sort="descending"]').length).toBe(1);
    await user.click(button);
    expect(names()).toEqual(["zero", "two", "ten", "unknown"]);
    expect(document.querySelectorAll('th[aria-sort="ascending"]').length).toBe(1);
  }
  expect(screen.getByRole("link", { name: "two" }).getAttribute("href")).toBe("/project/two");
});
