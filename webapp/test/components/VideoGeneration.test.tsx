// @vitest-environment jsdom
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import { useVideoGeneration, VideoGeneration }
  from "@/app/project/[project]/images/[item]/VideoGeneration";

// A controlled transport standing in for the workbench: POST starts a job
// (or fails, or times out), GET reports its phase.
type Mode = "failure" | "success" | "timeout" | "unsupported";
const t = { mode: "failure" as Mode, phase: "idle", failReads: 0, calls: [] as { url: string; body?: string }[] };
const json = (status: number, body: unknown) => ({ ok: status < 400, status, json: async () => body });
const transport = async (url: string, options: RequestInit = {}) => {
  t.calls.push({ url: String(url), body: options.body as string | undefined });
  if (options.method === "POST") {
    if (t.mode === "failure") return json(400, { error: "Panel source unavailable" });
    if (t.mode === "timeout") { t.phase = "ready"; t.failReads = 1; return json(504, { error: "Error: Workbench request timed out" }); }
    t.phase = "running"; setTimeout(() => { t.phase = "ready"; }, 100);
    return json(200, { status: "queued", can_generate: true });
  }
  if (t.failReads > 0) { t.failReads--; throw new TypeError("Network interrupted"); }
  return json(200, t.mode === "unsupported"
    ? { status: "idle", can_generate: false, reason: "No usable recorded transformation is available." }
    : { status: t.phase, can_generate: true,
        video: t.phase === "ready" ? "__videos/job/hash.mp4" : null,
        thumbnail: t.phase === "ready" ? "__videos/job/titlehash.png" : null });
};
afterEach(() => vi.unstubAllGlobals());

type Item = Parameters<typeof useVideoGeneration>[1];
function Harness({ item }: { item: Item }) {
  const state = useVideoGeneration("project", item);
  return <VideoGeneration state={state} />;
}
const base = { id: "within:p:IMGDUP-1", run_id: "r_old", record_revision: "one", paper: { dir: "paper" } } as unknown as NonNullable<Item>;

test("exact run, source failure, retry, queued-to-ready, navigation and unsupported state", async () => {
  vi.stubGlobal("fetch", transport);
  const user = userEvent.setup();
  // Embedded idle status avoids a second item/status fetch.
  const { rerender } = render(<Harness item={{ ...base, id: "embedded-status", record_revision: "embedded",
    video_generation: { status: "idle", can_generate: true } } as Item} />);
  await screen.findByRole("button", { name: "Generate video" });
  expect(t.calls.length).toBe(0);

  rerender(<Harness item={base} />);
  await user.click(await screen.findByRole("button", { name: "Generate video" }));
  await screen.findByRole("button", { name: "Retry video" });
  expect(screen.getByRole("status").textContent).toMatch(/Panel source unavailable/);
  const sent = JSON.parse(t.calls.find((c) => c.body)!.body!);
  expect(sent.run).toBe("r_old");
  expect(sent.item).toBe("within:p:IMGDUP-1");

  t.mode = "success";
  await user.click(screen.getByRole("button", { name: "Retry video" }));
  await screen.findByRole("button", { name: /Queued|Generating/ });
  await screen.findByText("Saved on this computer", {}, { timeout: 8000 });
  const thumbnail = await screen.findByRole("link", { name: "Download thumbnail" });
  const params = new URL(thumbnail.getAttribute("href")!, "http://localhost").searchParams;
  expect(params.get("f")).toBe("__videos/job/titlehash.png");
  expect(params.get("dir")).toBe("paper");
  expect(params.get("project")).toBe("project");
  expect(params.get("download")).toBe("1");
  expect(thumbnail.hasAttribute("download")).toBe(true);

  // Media availability changes without changing the scientific record. A
  // refreshed failure must replace local ready state and expose regeneration.
  rerender(<Harness item={{ ...base, video_generation: { status: "failed", can_generate: true,
    revision: "missing-file", error: "Saved video is unavailable or changed" } } as Item} />);
  await screen.findByRole("button", { name: "Retry video" });
  expect(screen.queryByText("Saved on this computer")).toBeNull();
  await user.click(screen.getByRole("button", { name: "Retry video" }));
  await screen.findByText("Saved on this computer", {}, { timeout: 8000 });

  // A late response from an older job snapshot cannot overwrite newer props.
  let finishOldRead: ((v: unknown) => void) | undefined;
  vi.stubGlobal("fetch", () => new Promise((resolve) => { finishOldRead = resolve; }));
  rerender(<Harness item={{ ...base, video_generation: { status: "queued", can_generate: true, revision: "queued-snapshot" } } as Item} />);
  await waitFor(() => expect(finishOldRead).toBeDefined(), { timeout: 8000 });
  rerender(<Harness item={{ ...base, video_generation: { status: "failed", can_generate: true, revision: "new-failure", error: "Newer failure" } } as Item} />);
  await screen.findByRole("button", { name: "Retry video" });
  await act(async () => {
    finishOldRead!(json(200, { status: "ready", can_generate: true, video: "stale.mp4" }));
    await new Promise((r) => setTimeout(r, 50));
  });
  vi.stubGlobal("fetch", transport);
  expect(screen.queryByText("Saved on this computer")).toBeNull();
  expect(screen.getByRole("status").textContent).toMatch(/Newer failure/);

  // A timed-out POST may already have completed. Recover through GET, even
  // when the first reconciliation request also fails, without another POST.
  t.mode = "timeout"; t.phase = "idle";
  rerender(<Harness item={{ ...base, id: "timeout-item", record_revision: "timeout" } as Item} />);
  await user.click(await screen.findByRole("button", { name: "Generate video" }));
  await screen.findByText("Connection interrupted; checking video status…");
  await screen.findByRole("link", { name: "Download thumbnail" }, { timeout: 8000 });
  expect(t.calls.filter((c) => c.body && JSON.parse(c.body).item === "timeout-item").length).toBe(1);
  expect(screen.getAllByText("Saved on this computer").length).toBe(1);

  // Initial status failures must also recover rather than remaining blank.
  t.failReads = 1;
  rerender(<Harness item={{ ...base, id: "initial-read-failure", record_revision: "read-failure" } as Item} />);
  await screen.findByText("Connection interrupted; checking video status…");
  await screen.findByRole("link", { name: "Download thumbnail" }, { timeout: 8000 });

  t.mode = "unsupported";
  rerender(<Harness item={{ ...base, id: "another", record_revision: "two" } as Item} />);
  await screen.findByText("No usable recorded transformation is available.");
  expect((screen.getByRole("button", { name: "Generate video" }) as HTMLButtonElement).disabled).toBe(true);
}, 60_000);
