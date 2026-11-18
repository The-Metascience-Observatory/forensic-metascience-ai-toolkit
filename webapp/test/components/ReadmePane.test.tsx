// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { SWRConfig } from "swr";
import { afterEach, expect, test, vi } from "vitest";

import { ReadmePane } from "@/app/project/[project]/review/[slug]/ReadmePane";
import { RepoSummary } from "@/app/project/[project]/review/[slug]/RepoSummary";
import type { RepoView } from "@/lib/useRepo";

const NAME = "Journal-2024-PMC1-10.1--x-words";
const README = `# Reproducing data\n\n**Summary**\n\n- one\n\n<table><tr><td>cell</td></tr></table>\n\n<script>window.pwned = 1</script>\n<img src="x" onerror="window.pwned = 1">\n`;
const view = (over: Partial<NonNullable<RepoView["repo"]>> = {}, readme = README): RepoView => ({
  repo: { name: NAME, url: `https://github.com/Metascience-Observatory-Reproductions/${NAME}`, hasRemote: true, inOrg: true,
          readmeDirty: false, otherDirty: [], ahead: 0, visibility: "PRIVATE", ...over },
  readme, sha256: `sha-${readme.length}`, summary_md: "- one", triage_md: "", embargoed: false,
});

type Call = { url: string; body: Record<string, unknown> };
/** `/api/me` answers `role`; each write is recorded and answered by `reply`. */
function stubFetch(role: "admin" | "reviewer", reply: (c: Call) => RepoView | { error: string; status: number }) {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (String(url).startsWith("/api/me")) return Response.json({ mode: "hosted", email: "a@b", name: "A", role, projects: ["p"] });
    const call = { url: String(url), body: JSON.parse(String(init?.body || "{}")) };
    calls.push(call);
    const out = reply(call);
    return "error" in out ? Response.json({ error: out.error }, { status: out.status }) : Response.json(out);
  }));
  return calls;
}
afterEach(() => vi.unstubAllGlobals());

function Harness({ start }: { start: RepoView }) {
  const [info, setInfo] = useState(start);
  return (
    <SWRConfig value={{ provider: () => new Map() }}>
      <ReadmePane project="p" dir="10.1--x" info={info} onInfo={setInfo} onReload={() => {}} onClose={() => {}} />
    </SWRConfig>
  );
}
const button = (name: RegExp) => screen.getByRole("button", { name }) as HTMLButtonElement;

test("the README is rendered with its HTML table and without its script or event handler", () => {
  stubFetch("reviewer", () => view());
  render(<Harness start={view()} />);
  expect(document.querySelector(".readme-body table td")?.textContent).toBe("cell");
  expect(document.querySelector(".readme-body h1")?.textContent).toBe("Reproducing data");
  expect(document.querySelector(".readme-body script")).toBeNull();
  expect(document.querySelector(".readme-body [onerror]")).toBeNull();
  expect((window as unknown as { pwned?: number }).pwned).toBeUndefined();
});

test("edit, save, then commit and push: each step enables the next", async () => {
  const edited = README + "\nMore.\n";
  const calls = stubFetch("reviewer", (c) =>
    c.url === "/api/repo/readme" ? view({ readmeDirty: true }, String(c.body.content)) : view({}, edited));
  render(<Harness start={view()} />);
  expect(button(/^Save$/).disabled).toBe(true);
  expect(button(/Commit and push/).disabled).toBe(true);

  fireEvent.click(button(/^Edit markdown$/));
  fireEvent.change(screen.getByLabelText("README.md source"), { target: { value: edited } });
  expect(button(/^Save$/).disabled).toBe(false);
  expect(button(/Commit and push/).disabled).toBe(true); // not while the edit is unsaved
  fireEvent.click(button(/^Save$/));
  await waitFor(() => expect(button(/Commit and push/).disabled).toBe(false));
  expect(calls[0]).toEqual({ url: "/api/repo/readme", body: expect.objectContaining({ project: "p", dir: "10.1--x", content: edited, base_sha256: `sha-${README.length}` }) });
  expect(screen.getByRole("status").textContent).toMatch(/Not committed yet/);
  expect(button(/^Save$/).disabled).toBe(true);

  fireEvent.click(button(/Commit and push/));
  await waitFor(() => expect(screen.getByRole("status").textContent).toMatch(/pushed to GitHub/));
  expect(calls[1].url).toBe("/api/repo/push");
  expect(button(/Commit and push/).disabled).toBe(true);
});

test("a save over a README that changed on disk says so and offers a reload", async () => {
  stubFetch("reviewer", () => ({ error: "The README changed on disk since you opened it. Reload it, then make your edit again.", status: 409 }));
  render(<Harness start={view()} />);
  fireEvent.click(button(/^Edit markdown$/));
  fireEvent.change(screen.getByLabelText("README.md source"), { target: { value: "mine" } });
  fireEvent.click(button(/^Save$/));
  await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/changed on disk/));
  expect(button(/Reload the README/)).toBeTruthy();
  expect((screen.getByLabelText("README.md source") as HTMLTextAreaElement).value).toBe("mine"); // the edit is kept
});

test("a reviewer has no 'Make repo public'; for an admin it is one click, with no dialog", async () => {
  stubFetch("reviewer", () => view());
  const first = render(<Harness start={view()} />);
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(screen.queryByRole("button", { name: /Make repo public/ })).toBeNull();
  first.unmount();

  const calls = stubFetch("admin", () => view({ visibility: "PUBLIC" }));
  render(<Harness start={view()} />);
  fireEvent.click(await screen.findByRole("button", { name: /Make repo public/ }));
  expect(screen.queryByRole("dialog")).toBeNull();
  await waitFor(() => expect(document.querySelector(".readme-bar [data-visibility]")?.textContent).toBe("Public"));
  expect(calls).toEqual([{ url: "/api/repo/publish", body: expect.objectContaining({ project: "p", dir: "10.1--x", confirm: NAME }) }]);
  expect(screen.queryByRole("button", { name: /Make repo public/ })).toBeNull(); // already public
});

test("'Make repo public' waits for a clean, pushed tree; a public repo is pushed to by admins only", async () => {
  stubFetch("admin", () => view());
  const a = render(<Harness start={view({ ahead: 1 })} />);
  expect((await screen.findByRole("button", { name: /Make repo public/ }) as HTMLButtonElement).disabled).toBe(true);
  a.unmount();
  stubFetch("reviewer", () => view());
  render(<Harness start={view({ visibility: "PUBLIC", readmeDirty: true })} />);
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(button(/Commit and push/).disabled).toBe(true);
  expect(button(/Commit and push/).title).toMatch(/only an admin/);
});

test("the summary block: README bullets, else the triage note, else nothing", () => {
  const open = vi.fn();
  const a = render(<RepoSummary info={view({ readmeDirty: true })} readmeOpen={false} onReadme={open} />);
  expect(document.querySelector("[data-repo-summary]")?.getAttribute("data-repo-summary")).toBe("readme");
  expect(document.querySelector(".repo-summary li")?.textContent).toBe("one");
  expect(document.querySelector(".repo-summary")?.textContent).toMatch(/Private.*README saved, not committed/);
  const github = screen.getByRole("link", { name: "View Repo on GitHub" }) as HTMLAnchorElement;
  expect(github.href).toBe(`https://github.com/Metascience-Observatory-Reproductions/${NAME}`);
  expect(github.nextElementSibling?.textContent).toBe("Private");
  expect(screen.queryByRole("link", { name: NAME })).toBeNull();
  fireEvent.click(button(/^View and edit README.md$/));
  expect(open).toHaveBeenCalledOnce();
  a.unmount();

  const b = render(<RepoSummary info={{ repo: null, readme: null, sha256: null, summary_md: "", triage_md: "Category: C\n\n- matched", embargoed: false }}
                                readmeOpen={false} onReadme={open} />);
  expect(document.querySelector("[data-repo-summary]")?.getAttribute("data-repo-summary")).toBe("triage");
  expect(document.querySelector(".repo-summary")?.textContent).toMatch(/Triage note[\s\S]*no reproduction repo[\s\S]*Category: C/);
  expect(screen.queryByRole("button", { name: /README/ })).toBeNull();
  b.unmount();

  render(<RepoSummary info={{ repo: null, readme: null, sha256: null, summary_md: "", triage_md: "", embargoed: false }} readmeOpen={false} onReadme={open} />);
  expect(document.querySelector("[data-repo-summary]")).toBeNull();
});
