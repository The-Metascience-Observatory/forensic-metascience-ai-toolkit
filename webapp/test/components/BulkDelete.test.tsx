// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import { BulkDelete, toDelete } from "@/app/BulkDelete";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const plan = (project: string, extra: Record<string, unknown> = {}) => ({
  project, folders: [{ path: `/data/${project}`, files: 10, bytes: 2048, measured: true }],
  refused: [], also_removes: [], can_delete: true, ...extra,
});

test("a project inside another selected one is left to its parent's delete; refused ones are skipped", () => {
  expect(toDelete([plan("a", { also_removes: ["b"] }), plan("b"), plan("c", { can_delete: false })] as never))
    .toEqual(["a"]);
});

test("one confirmation, then one delete per project", async () => {
  const posts: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init: RequestInit) => {
    const body = JSON.parse(String(init.body));
    posts.push(body);
    if (body.action === "delete_plan") return new Response(JSON.stringify(plan(body.project)));
    return new Response(JSON.stringify({ id: "j", project: body.project, state: "counting" }));
  }));
  const onClose = vi.fn();
  render(<BulkDelete names={["p1", "p2"]} onClose={onClose} />);
  const yes = await screen.findByRole("button", { name: "Yes, delete 2" });
  expect(screen.getByText(/20 files, 4.0 KB in all/)).toBeTruthy();
  expect(posts.filter((p) => p.action === "delete")).toHaveLength(0);
  await userEvent.click(yes);
  await waitFor(() => expect(onClose).toHaveBeenCalledWith(true));
  expect(posts.filter((p) => p.action === "delete")).toEqual([
    { project: "p1", action: "delete", confirm: true },
    { project: "p2", action: "delete", confirm: true },
  ]);
});
