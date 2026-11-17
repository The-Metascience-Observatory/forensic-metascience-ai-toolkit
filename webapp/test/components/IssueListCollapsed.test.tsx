// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { IssueList } from "@/app/project/[project]/review/[slug]/IssueList";
import type { Issue } from "@/lib/types/review";

afterEach(cleanup);
const row = (id: string, group?: string): Issue => ({
  id, finding_id: id, priority: 1, title: `finding ${id}`, producer: "tool_expert", severity_9: 5,
  ...(group ? { group: { id: group, n: 2, tool: "grim", label: group } } : {}),
} as unknown as Issue);
const decisions = () => document.querySelectorAll(".finding-flags").length;

test("no finding is expanded until the reader clicks one", () => {
  const onFocus = vi.fn();
  render(<IssueList issues={[row("a"), row("b")]} at={0} review={null} onFocus={onFocus} onSave={() => {}} />);
  expect(decisions()).toBe(0);
  fireEvent.click(screen.getByText("finding a"));
  expect(onFocus).toHaveBeenCalledWith(0);
  expect(decisions()).toBe(1);
});

test("groups start closed, even the one holding the first finding", () => {
  render(<IssueList issues={[row("a", "g1"), row("b", "g1")]} at={0} review={null}
                    onFocus={() => {}} onSave={() => {}} grouped />);
  expect(screen.queryByText("finding a")).toBeNull();
  expect(document.querySelectorAll("[data-group-header]").length).toBe(1);
});

test("moving the focus (keys, a linked finding) expands that finding", () => {
  const { rerender } = render(<IssueList issues={[row("a"), row("b")]} at={0} review={null}
                                         onFocus={() => {}} onSave={() => {}} />);
  rerender(<IssueList issues={[row("a"), row("b")]} at={1} review={null} onFocus={() => {}} onSave={() => {}} />);
  expect(decisions()).toBe(1);
});

test("clicking an open card closes it; clicking its feedback does not", () => {
  render(<IssueList issues={[row("a"), row("b")]} at={0} review={null} onFocus={() => {}} onSave={() => {}} />);
  fireEvent.click(screen.getByText("finding a"));
  expect(decisions()).toBe(1);
  fireEvent.click(document.querySelector(".finding-flags input") as HTMLElement);
  expect(decisions()).toBe(1);
  fireEvent.click(screen.getByText("finding a"));
  expect(decisions()).toBe(0);
  fireEvent.click(screen.getByText("finding a"));
  expect(decisions()).toBe(1);
});
