// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

vi.mock("@/app/images/lib", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/app/images/lib")>()),
  mediaUrl: (_project: string, _dir: string, image: string) => image,
}));

import { TextSupport } from "@/app/project/[project]/images/[item]/TextSupport";

const loc = { status: "measured", reason: "text_localized",
  boxes: [{ box: [10, 20, 100, 40], text: "MDA-MB-231", confidence: 95, rotation: 0 }],
  size: [200, 200], mask_fraction: 0.045 };
const value = { status: "measured", reason: "text_label_only", policy: "diagnostic", would_demote: true,
  demote: false, n_inliers: 62, text_inliers_both: 61, nontext_inliers: 1, inlier_floor: 15,
  uid_a: "a", uid_b: "b", a: loc, b: loc };
const item = { panels: [
  { uid: "a", paper_dir: "paper", image: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg'/>" },
  { uid: "b", paper_dir: "paper", image: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg'/>" },
] } as unknown as Parameters<typeof TextSupport>[0]["item"];

test("diagnostic, context and abstention states, with native-coordinate overlays", async () => {
  const user = userEvent.setup();
  const { container, rerender } = render(<TextSupport value={value} item={item} project="test" />);
  const rects = () => container.querySelectorAll("svg rect").length;
  expect(container.textContent).toMatch(/Diagnostic only/);
  expect(container.textContent).toMatch(/61 of 62/);
  expect(rects()).toBe(0);
  await user.click(screen.getByRole("switch", { name: "Show excluded text regions" }));
  expect(rects()).toBe(2);
  await user.click(screen.getByRole("switch"));
  expect(rects()).toBe(0);
  await user.click(screen.getByRole("switch"));
  expect(container.querySelector("svg rect")!.getAttribute("x")).toBe("10");
  rerender(<TextSupport value={{ ...value, demote: true }} item={item} project="test" />);
  expect(container.textContent).toMatch(/Retained as text-label context/);
  rerender(<TextSupport value={{ status: "abstained", reason: "ocr_unavailable" }} item={item} project="test" />);
  expect(container.textContent).toMatch(/not measured reliably/);
  expect(container.querySelectorAll("svg").length).toBe(0);
  rerender(<TextSupport value={null} item={item} project="test" />);
  expect(container.textContent).toMatch(/not measured/);
});
