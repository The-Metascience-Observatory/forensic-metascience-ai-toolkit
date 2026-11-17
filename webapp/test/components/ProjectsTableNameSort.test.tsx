// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test } from "vitest";

import { ProjectsTable } from "@/app/ProjectsTable";

afterEach(cleanup);
const rows = ["fca_screen_2026-09", "Berrio_depression", "batch10", "batch2"].map((name) => ({
  name, n_papers: 1, n_pdf_or_xml: 1, n_image_run: 0, n_text_run: 0, n_rng_papers: 0, n_human_reviewed: 0,
  n_not_fetched: 0, n_in_progress: 0,
})) as unknown as Parameters<typeof ProjectsTable>[0]["projects"];

test("the Project column sorts by name, A to Z first, then Z to A", async () => {
  const user = userEvent.setup();
  render(<ProjectsTable projects={rows} />);
  const names = () =>
    [...document.querySelectorAll('tbody tr td a[href^="/project/"]')].map((a) => a.textContent);
  const button = screen.getByRole("button", { name: /^Project / });
  await user.click(button);
  // Case-insensitive, and numbers in names compare as numbers (batch2 < batch10).
  expect(names()).toEqual(["batch2", "batch10", "Berrio_depression", "fca_screen_2026-09"]);
  expect(document.querySelectorAll('th[aria-sort="ascending"]').length).toBe(1);
  await user.click(button);
  expect(names()).toEqual(["fca_screen_2026-09", "Berrio_depression", "batch10", "batch2"]);
  expect(document.querySelectorAll('th[aria-sort="descending"]').length).toBe(1);
});
