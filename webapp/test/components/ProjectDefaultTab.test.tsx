import { afterEach, expect, test, vi } from "vitest";

// The project page's server component: which tab it opens on.
const replies: Record<string, unknown> = {};
vi.mock("@/lib/workbench", () => ({ workbench: vi.fn(async (method: string) => replies[method]) }));
const redirect = vi.fn((url: string) => { throw new Error(`redirect:${url}`); });
vi.mock("next/navigation", () => ({ redirect: (url: string) => redirect(url) }));
vi.mock("@/app/project/[project]/PapersPage", () => ({ PapersPage: () => null }));
import Page from "@/app/project/[project]/page";

afterEach(() => { redirect.mockClear(); });
const open = (view?: string) => Page({ params: Promise.resolve({ project: "fca%20v2" }),
                                       searchParams: Promise.resolve(view ? { view } : {}) });
const set = (nonImage: number | null, images: number) => {
  replies.papers = { papers: nonImage === undefined ? [] : [{ n_non_image_findings: nonImage }] };
  replies.feed = { pagination: { total: images } };
};

test("only image findings: opens on the Image findings tab", async () => {
  set(0, 12);
  await expect(open()).rejects.toThrow("redirect:/project/fca%20v2/images");
});

test("no analysis yet (null) counts as no non-image findings", async () => {
  set(null, 3);
  await expect(open()).rejects.toThrow("redirect:/project/fca%20v2/images");
});

test("any non-image finding, or no image findings: stays on Non-image findings", async () => {
  set(4, 12);
  await expect(open()).resolves.toBeTruthy();
  set(0, 0);
  await expect(open()).resolves.toBeTruthy();
  expect(redirect).not.toHaveBeenCalled();
});

test("the tab's own link (?view=findings) is never redirected", async () => {
  set(0, 12);
  await expect(open("findings")).resolves.toBeTruthy();
  expect(redirect).not.toHaveBeenCalled();
});
