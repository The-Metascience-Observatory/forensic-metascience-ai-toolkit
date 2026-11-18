// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { createRef } from "react";
import { afterEach, expect, test } from "vitest";

import { SidePane } from "@/app/project/[project]/review/[slug]/SidePane";

afterEach(() => window.localStorage.clear());

test("a side pane takes its stored width, resizes from the keyboard and remembers it", () => {
  window.localStorage.setItem("metascience.review.pane.email", "25");
  const row = createRef<HTMLDivElement>();
  render(<div ref={row}><SidePane id="email" label="Resize the email pane" rowRef={row}>body</SidePane></div>);
  const pane = document.querySelector<HTMLElement>("[data-side-pane=email]")!;
  expect(pane.style.flexBasis).toBe("25%");
  const gutter = screen.getByRole("separator", { name: "Resize the email pane" });
  fireEvent.keyDown(gutter, { key: "ArrowRight" });
  expect(pane.style.flexBasis).toBe("27%");
  expect(window.localStorage.getItem("metascience.review.pane.email")).toBe("27");
  for (let i = 0; i < 40; i++) fireEvent.keyDown(gutter, { key: "ArrowLeft" });
  expect(pane.style.flexBasis).toBe("12%");
});

test("a closed pane is hidden and has no gutter; a bad stored width falls back to the default", () => {
  window.localStorage.setItem("metascience.review.pane.readme", "900");
  const row = createRef<HTMLDivElement>();
  const { rerender } = render(<div ref={row}><SidePane id="readme" label="Resize" rowRef={row} hidden>body</SidePane></div>);
  expect(document.querySelector<HTMLElement>("[data-side-pane=readme]")!.hidden).toBe(true);
  expect(screen.queryByRole("separator")).toBeNull();
  rerender(<div ref={row}><SidePane id="readme" label="Resize" rowRef={row}>body</SidePane></div>);
  expect(document.querySelector<HTMLElement>("[data-side-pane=readme]")!.style.flexBasis).toBe("40%");
  expect(screen.getByRole("separator")).toBeTruthy();
});
