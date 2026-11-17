// @vitest-environment jsdom
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import { ProjectsTable } from "@/app/ProjectsTable";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const rows = ["live", "old_a", "old_b"].map((name) => ({
  name, archived: name !== "live", n_papers: 1, n_pdf_or_xml: 1, n_image_run: 0, n_text_run: 0,
  n_rng_papers: 0, n_human_reviewed: 0, n_not_fetched: 0, n_in_progress: 0,
})) as unknown as Parameters<typeof ProjectsTable>[0]["projects"];

function transport() {
  const posts: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body || "{}"));
    posts.push(body);
    if (body.action === "delete_plan") {
      return new Response(JSON.stringify({ project: body.project, can_delete: true, refused: [], also_removes: [],
        folders: [{ path: `/d/${body.project}`, files: 1, bytes: 10, measured: true }] }));
    }
    return new Response(JSON.stringify({ ok: true }));
  }));
  return posts;
}

async function openArchived() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: /Archived \(2\)/ }));
  const section = document.querySelector("[data-archived-projects]") as HTMLElement;
  await user.click(within(section).getByRole("checkbox", { name: "Select all projects in this table" }));
  return { user, section };
}

test("archived projects can be selected together and unarchived", async () => {
  const posts = transport();
  render(<ProjectsTable projects={rows} />);
  const { user, section } = await openArchived();
  // The active table's own selection bar is not involved.
  expect(screen.queryByRole("button", { name: "Archive selected" })).toBeNull();
  expect(within(section).getByText("2 selected")).toBeTruthy();
  await user.click(within(section).getByRole("button", { name: "Unarchive selected" }));
  await waitFor(() => expect(posts.filter((p) => p.action === "unarchive").map((p) => p.project)).toEqual(["old_a", "old_b"]));
  // Both rows moved back to the active table; the Archived section is gone.
  await waitFor(() => expect(document.querySelector("[data-archived-projects]")).toBeNull());
});

test("delete selected opens one confirmation for the archived selection, in that section", async () => {
  transport();
  render(<ProjectsTable projects={rows} />);
  const { user, section } = await openArchived();
  await user.click(within(section).getByRole("button", { name: "Delete selected…" }));
  const dialog = await within(section).findByRole("dialog", { name: "Delete 2 projects" });
  expect(await within(dialog).findByRole("button", { name: "Yes, delete 2" })).toBeTruthy();
  expect(within(dialog).getByText("old_a")).toBeTruthy();
});
