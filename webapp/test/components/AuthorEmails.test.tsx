// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

// pdf.js is stubbed: one page whose text layer prints two addresses and whose
// mailto link annotation carries a third.
vi.mock("@/lib/pdfjs", () => ({
  loadPdfjs: async () => ({
    getDocument: () => ({ promise: Promise.resolve({
      numPages: 1,
      getPage: async () => ({
        getAnnotations: async () => [{ url: "mailto:third@example.org?subject=x" }],
        getTextContent: async () => ({ items: [
          { str: "Correspondence: first@example.org and second@example.org", hasEOL: true }] }),
        cleanup: () => {},
      }),
      destroy: () => {},
    }) }),
  }),
}));

import { AuthorEmails, joinEmails } from "@/app/project/[project]/images/[item]/AuthorEmails";

const item = { id: "i1", run_id: "r1", paper: { dir: "paper", pdf: "paper.pdf" }, papers: [], panels: [] } as unknown as
  Parameters<typeof AuthorEmails>[0]["item"];

test("autoStart reads the paper at once; copy all joins the addresses for PubPeer", async () => {
  // user-event installs its own clipboard stub; read what the button wrote through it.
  const user = userEvent.setup();
  render(<AuthorEmails project="p" item={item} autoStart />);
  await waitFor(() => expect(screen.getAllByRole("listitem").length).toBe(3));
  const texts = screen.getAllByRole("listitem").map((li) => li.textContent || "");
  expect(texts.join(" ")).toMatch(/first@example.org/);
  expect(texts.join(" ")).toMatch(/third@example.org/);
  await user.click(screen.getByRole("button", { name: /copy all 3/ }));
  const listed = texts.map((t) => t.replace(/copy.*$/, "").trim());
  expect(await navigator.clipboard.readText()).toBe(joinEmails(listed));
  expect(listed).toContain("third@example.org");
  expect(screen.getByRole("button", { name: /copied all/ })).toBeTruthy();
});

test("without autoStart nothing is read until the button is clicked", async () => {
  render(<AuthorEmails project="p" item={item} />);
  await new Promise((r) => setTimeout(r, 50));
  expect(screen.queryAllByRole("listitem").length).toBe(0);
  expect(screen.getByRole("button", { name: "Extract author emails" })).toBeTruthy();
});
