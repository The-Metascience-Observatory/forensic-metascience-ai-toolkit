// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import { useColumnResize } from "@/app/useColumnResize";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

function TestComponent({
  storageKey = "test:col-width",
  def = 250,
  min = 100,
  max = 500,
}: {
  storageKey?: string;
  def?: number;
  min?: number;
  max?: number;
}) {
  const { width, isDragging, reset, setWidth, getHandleProps } = useColumnResize({
    storageKey,
    def,
    min,
    max,
    label: "Resize test column",
  });

  return (
    <div>
      <div data-testid="width">{width}</div>
      <div data-testid="dragging">{String(isDragging)}</div>
      <button data-testid="set-small" onClick={() => setWidth(50)}>
        Set small
      </button>
      <button data-testid="set-large" onClick={() => setWidth(999)}>
        Set large
      </button>
      <button data-testid="reset" onClick={reset}>
        Reset
      </button>
      <div {...getHandleProps()} data-testid="handle" />
    </div>
  );
}

test("useColumnResize clamps updates between min and max", async () => {
  const user = userEvent.setup();
  render(<TestComponent min={100} max={500} def={250} />);

  expect(screen.getByTestId("width").textContent).toBe("250");

  await user.click(screen.getByTestId("set-small"));
  expect(screen.getByTestId("width").textContent).toBe("100");

  await user.click(screen.getByTestId("set-large"));
  expect(screen.getByTestId("width").textContent).toBe("500");

  await user.click(screen.getByTestId("reset"));
  expect(screen.getByTestId("width").textContent).toBe("250");
});

test("useColumnResize ignores invalid or out-of-bounds localStorage values", () => {
  localStorage.setItem("test:col-width", "not-a-number");
  const { unmount } = render(<TestComponent />);
  expect(screen.getByTestId("width").textContent).toBe("250");
  unmount();

  localStorage.setItem("test:col-width", "50"); // below min (100)
  const { unmount: unmount2 } = render(<TestComponent />);
  expect(screen.getByTestId("width").textContent).toBe("250");
  unmount2();

  localStorage.setItem("test:col-width", "999"); // above max (500)
  const { unmount: unmount3 } = render(<TestComponent />);
  expect(screen.getByTestId("width").textContent).toBe("250");
  unmount3();

  localStorage.setItem("test:col-width", "320"); // valid
  render(<TestComponent />);
  expect(screen.getByTestId("width").textContent).toBe("320");
});

test("useColumnResize works smoothly even when localStorage throws", () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("Storage blocked");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("Storage blocked");
  });

  render(<TestComponent def={200} />);
  const handle = screen.getByTestId("handle");
  handle.setPointerCapture = () => {};
  handle.releasePointerCapture = () => {};

  expect(screen.getByTestId("width").textContent).toBe("200");
  fireEvent.pointerDown(handle, { clientX: 200, pointerId: 1 });
  fireEvent.pointerMove(handle, { clientX: 250, pointerId: 1 });
  fireEvent.pointerUp(handle, { clientX: 250, pointerId: 1 });

  expect(screen.getByTestId("width").textContent).toBe("250");
});
