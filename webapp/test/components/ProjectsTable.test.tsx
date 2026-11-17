// @vitest-environment jsdom
import { readFileSync } from "node:fs";

import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import { ProjectsTable } from "@/app/ProjectsTable";

// Imported image results must reach the landing page: every catalog project
// gets its image-review counts joined, and image projects the catalog does
// not list yet are appended rather than hidden (Yadong Huang's, 2026-09-30).
test("the home page joins image-review counts onto every listed project", () => {
  const home = readFileSync("app/page.tsx", "utf8");
  expect(home).toMatch(/<ProjectsTable\s+projects=\{withImageReviews\(listed,\s*counts\)\}/);
  expect(home).toMatch(
    /const catalog\s*=\s*\[\.\.\.index\.projects,\s*\.\.\.imageOnlyProjects\(index\.projects,\s*counts\)\]/,
  );
  // Then only the configured sources and, for a reviewer, their projects.
  expect(home).toMatch(
    /const listed\s*=\s*\[\.\.\.catalog,[^\n]*\]\s*\n\s*\.filter\(p => visible\(p\.name\)\)/,
  );
});

const fields = [
  "n_papers",
  "n_pdf_or_xml",
  "n_image_run",
  "n_text_run", "n_rng_papers",
  "n_human_reviewed",
] as const;
const labels = ["Papers", "With PDF/XML", "Image track", "Text track", "RNG track", "Human reviewed"];
const rows = [2, 10, 0, null].map((value, i) => ({
  name: ["two", "ten", "zero", "unknown"][i],
  ...Object.fromEntries(fields.map((f) => [f, value])),
  n_not_fetched: 0,
  n_in_progress: 0,
})) as unknown as Parameters<typeof ProjectsTable>[0]["projects"];

test("all six numeric columns sort both ways; missing counts stay last", async () => {
  const user = userEvent.setup();
  render(<ProjectsTable projects={rows} />);
  const names = () =>
    [...document.querySelectorAll('tbody tr td a[href^="/project/"]')].map((a) => a.textContent);
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

test("archived projects sit in a closed Archived section, out of the active table", async () => {
  const user = userEvent.setup();
  const list = rows.map((r, i) => ({ ...r, archived: i === 1 }));
  render(<ProjectsTable projects={list} />);
  const linked = () =>
    [...document.querySelectorAll('tbody tr td a[href^="/project/"]')].map((a) => a.textContent);
  expect(linked()).not.toContain("ten");
  const toggle = screen.getByRole("button", { name: /Archived \(1\)/ });
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  await user.click(toggle);
  expect(linked()).toContain("ten");
  expect(screen.getByRole("button", { name: "Unarchive" })).toBeTruthy();
});

test("a reviewer gets no selection boxes or archive buttons", () => {
  render(<ProjectsTable projects={rows} canManage={false} />);
  expect(document.querySelectorAll('input[type="checkbox"]').length).toBe(0);
  expect(screen.queryByRole("button", { name: "Archive" })).toBeNull();
});

test("the project column is resizable via keyboard, double-click reset, and persists in localStorage", async () => {
  localStorage.clear();
  const user = userEvent.setup();
  const { unmount } = render(<ProjectsTable projects={rows} />);

  // Initial render: default width 260px
  const handle = screen.getByRole("separator", { name: "Resize Project column" });
  expect(handle).toBeTruthy();
  expect(handle.getAttribute("aria-valuenow")).toBe("260");
  expect(handle.getAttribute("aria-valuemin")).toBe("120");
  expect(handle.getAttribute("aria-valuemax")).toBe("800");

  const th = document.querySelector("th.project-col") as HTMLElement;
  expect(th.style.width).toBe("260px");
  expect(th.style.maxWidth).toBe("260px");

  const tds = document.querySelectorAll("td.project-col");
  expect(tds.length).toBe(rows.length);
  tds.forEach((td) => {
    expect((td as HTMLElement).style.width).toBe("260px");
  });

  // Keyboard navigation: ArrowRight increases width by 10px
  handle.focus();
  await user.keyboard("{ArrowRight}");
  expect(handle.getAttribute("aria-valuenow")).toBe("270");
  expect(th.style.width).toBe("270px");
  expect(localStorage.getItem("metascience:project-col-width")).toBe("270");

  // ArrowLeft decreases width by 10px
  await user.keyboard("{ArrowLeft}");
  expect(handle.getAttribute("aria-valuenow")).toBe("260");
  expect(th.style.width).toBe("260px");
  expect(localStorage.getItem("metascience:project-col-width")).toBe("260");

  // Shift + ArrowRight increases by 20px
  await user.keyboard("{Shift>}{ArrowRight}{/Shift}");
  expect(handle.getAttribute("aria-valuenow")).toBe("280");
  expect(th.style.width).toBe("280px");

  // Home sets to min (120px)
  await user.keyboard("{Home}");
  expect(handle.getAttribute("aria-valuenow")).toBe("120");
  expect(th.style.width).toBe("120px");
  expect(localStorage.getItem("metascience:project-col-width")).toBe("120");

  // End sets to max (800px)
  await user.keyboard("{End}");
  expect(handle.getAttribute("aria-valuenow")).toBe("800");
  expect(th.style.width).toBe("800px");
  expect(localStorage.getItem("metascience:project-col-width")).toBe("800");

  // Double click resets to default (260px)
  await user.dblClick(handle);
  expect(handle.getAttribute("aria-valuenow")).toBe("260");
  expect(th.style.width).toBe("260px");
  expect(localStorage.getItem("metascience:project-col-width")).toBe("260");

  // Fresh mount after setting localStorage loads stored width
  unmount();
  localStorage.setItem("metascience:project-col-width", "350");
  render(<ProjectsTable projects={rows} />);
  expect(
    screen.getByRole("separator", { name: "Resize Project column" }).getAttribute("aria-valuenow"),
  ).toBe("350");
});

test("pointer drag resizes the project column and updates localStorage", () => {
  localStorage.clear();
  render(<ProjectsTable projects={rows} />);
  const handle = screen.getByRole("separator", { name: "Resize Project column" });
  const th = document.querySelector("th.project-col") as HTMLElement;

  handle.setPointerCapture = () => {};
  handle.releasePointerCapture = () => {};

  fireEvent.pointerDown(handle, { clientX: 260, pointerId: 1 });
  expect(handle.classList.contains("dragging")).toBe(true);

  fireEvent.pointerMove(handle, { clientX: 320, pointerId: 1 });
  expect(handle.getAttribute("aria-valuenow")).toBe("320");
  expect(th.style.width).toBe("320px");

  fireEvent.pointerUp(handle, { clientX: 320, pointerId: 1 });
  expect(handle.classList.contains("dragging")).toBe(false);
  expect(localStorage.getItem("metascience:project-col-width")).toBe("320");
});

test("project cell contains link with tooltip title for long names", () => {
  render(<ProjectsTable projects={rows} />);
  const link = screen.getByRole("link", { name: "two" });
  expect(link.getAttribute("title")).toBe("two");
  expect(link.classList.contains("project-name-link")).toBe(true);
});
