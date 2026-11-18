// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, test, vi } from "vitest";

import { DraftPane } from "@/app/project/[project]/review/[slug]/DraftPane";
import type { Draft, DraftKind, DraftsView } from "@/lib/useDrafts";

const EMAIL: Draft = {
  name: "email-20261117-100000.json", kind: "email", created_at: "2026-11-17T10:00:00Z", who: "Dan", model: "opus",
  paper: { title: "A trial", doi: "10.1002/acn3.51800" },
  to: [
    { name: "Ana Rivera", role: "handling editor", email: "ed@uni.es", source_url: "https://uni.es/ed", verified: true, check: "address found on the source page", selected: true },
    { name: "Made up", role: "editor-in-chief", email: "guess@j.org", source_url: "https://j.org", verified: false, check: "address NOT found on the source page", selected: false },
  ],
  cc: [{ email: "yan@uni.edu", selected: true, corresponding: true }],
  subject: "Figure 5", body: "Dear Editors,\n\nFigure 5 matches.", repo_url: "https://github.com/O/R",
  repo_visibility: "PRIVATE", contacts_note: "journal contacts looked up now (1 found)", sent: null,
};
const PUBPEER: Draft = { ...EMAIL, name: "pubpeer-20261117-110000.json", kind: "pubpeer", to: [], subject: "", body: "Figure 5 values equal R draws.", repo_url: "", repo_visibility: "" };
const view = (drafts: Draft[], jobs: Partial<DraftsView["jobs"]> = {}): DraftsView => ({ jobs: { email: null, pubpeer: null, ...jobs }, drafts });

type Call = { url: string; body: Record<string, unknown> };
function stubFetch(reply: (c: Call) => unknown) {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const call = { url: String(url), body: JSON.parse(String(init?.body || "{}")) };
    calls.push(call);
    return Response.json(reply(call));
  }));
  return calls;
}
afterEach(() => vi.unstubAllGlobals());

function Harness({ start, kind = "email" }: { start: DraftsView; kind?: DraftKind }) {
  const [v, setV] = useState(start);
  return <DraftPane project="p" dir="10.1--x" kind={kind} view={v} exclude={["f_fp"]} onView={setV} onClose={() => {}} />;
}

test("opening the pane with no draft starts one, with the ruled-out findings named", async () => {
  const running = view([], { email: { kind: "email", state: "starting", steps: [
    { name: "authors", status: "pending", detail: "" }, { name: "contacts", status: "pending", detail: "" },
    { name: "draft", status: "pending", detail: "" }] } });
  const calls = stubFetch(() => running);
  render(<Harness start={view([])} />);
  await waitFor(() => expect(calls.length).toBe(1));
  expect(calls[0]).toMatchObject({ url: "/api/drafts", body: { project: "p", dir: "10.1--x", kind: "email", exclude: ["f_fp"] } });
  await screen.findByText(/Journal editors' addresses/);
  expect(screen.getByText(/takes a few minutes/)).toBeTruthy();
});

test("a failed job says why and is not restarted on its own", async () => {
  const calls = stubFetch(() => ({}));
  render(<Harness start={view([], { email: { kind: "email", state: "error", error: "claude exited 1", steps: [] } })} />);
  expect(screen.getByText("claude exited 1")).toBeTruthy();
  await new Promise((r) => setTimeout(r, 20));
  expect(calls.length).toBe(0);
});

test("unverified addresses start unticked; the mail links follow the ticks", () => {
  stubFetch(() => ({}));
  render(<Harness start={view([EMAIL])} />);
  const boxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
  expect(boxes.slice(0, 2).map((b) => b.checked)).toEqual([true, false]);
  expect(screen.getByText("unverified").getAttribute("title")).toMatch(/NOT found/);
  const gmail = () => new URL((screen.getByText("Open in Gmail") as HTMLAnchorElement).href);
  expect(gmail().searchParams.get("to")).toBe("ed@uni.es");
  expect(gmail().searchParams.get("cc")).toBe("yan@uni.edu");
  fireEvent.click(boxes[1]);
  expect(gmail().searchParams.get("to")).toBe("ed@uni.es,guess@j.org");
  expect((screen.getByText("Open in mail app") as HTMLAnchorElement).href).toMatch(/^mailto:ed%40uni\.es,guess%40j\.org\?cc=yan%40uni\.edu&subject=Figure%205/);
  expect(screen.getByText(/repository is private/)).toBeTruthy();
});

test("edits are saved and the draft can be marked sent", async () => {
  const calls = stubFetch((c) => ({ ...EMAIL, ...(c.body.sent ? { sent: { at: "2026-11-17T12:00:00Z", by: "Dan" } } : {}), body: String(c.body.body) }));
  render(<Harness start={view([EMAIL])} />);
  const save = screen.getByRole("button", { name: "Save" }) as HTMLButtonElement;
  expect(save.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Email body"), { target: { value: "Shorter." } });
  fireEvent.change(screen.getByLabelText("Add an address"), { target: { value: "new@uni.edu" } });
  fireEvent.click(screen.getByRole("button", { name: "Add" }));
  expect(save.disabled).toBe(false);
  fireEvent.click(save);
  await waitFor(() => expect(calls.length).toBe(1));
  expect(calls[0]).toMatchObject({ url: "/api/drafts/save", body: { name: EMAIL.name, body: "Shorter." } });
  expect((calls[0].body.cc as { email: string }[]).map((r) => r.email)).toEqual(["yan@uni.edu", "new@uni.edu"]);
  fireEvent.click(screen.getByRole("checkbox", { name: /Sent/ }));
  await waitFor(() => expect(calls.length).toBe(2));
  expect(calls[1].body.sent).toBe(true);
  await screen.findByText(/by Dan on 2026-11-17/);
});

test("a PubPeer draft has no recipients to send to, only the authors to notify", () => {
  stubFetch(() => ({}));
  render(<Harness kind="pubpeer" start={view([EMAIL, PUBPEER])} />);
  expect(screen.queryByText(/To: journal/)).toBeNull();
  expect(screen.queryByText("Open in Gmail")).toBeNull();
  expect(screen.getByText(/notify authors/)).toBeTruthy();
  expect((screen.getByLabelText("PubPeer comment") as HTMLTextAreaElement).value).toBe(PUBPEER.body);
  expect((screen.getByText("Open on PubPeer") as HTMLAnchorElement).href).toBe("https://pubpeer.com/search?q=10.1002%2Facn3.51800");
  expect(screen.getByRole("button", { name: "Copy comment" })).toBeTruthy();
});
