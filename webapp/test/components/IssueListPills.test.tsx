// @vitest-environment jsdom
import { render } from "@testing-library/react";
import { expect, test } from "vitest";

import { IssueList } from "@/app/project/[project]/review/[slug]/IssueList";
import type { Issue } from "@/lib/types/review";

const row = (id: string, producer: string): Issue => ({
  id, finding_id: id, priority: 1, title: `finding ${id}`, producer,
  quarantined: true, tool: producer, tool_source: "component", severity_9: 5,
} as unknown as Issue);

// Every seeded-RNG row has the same detector and is quarantined, so those two
// pills repeat on every finding; other detectors keep them.
test("RNG findings carry no detector or quarantined pill; other detectors do", () => {
  render(<IssueList issues={[row("a", "rng_track"), row("b", "image_track")]}
                    at={0} review={null} onFocus={() => {}} onSave={() => {}} />);
  expect(document.querySelectorAll("[data-quarantined]").length).toBe(1);
  expect(document.querySelectorAll("[data-tool-badge]").length).toBe(1);
  expect(document.body.textContent).not.toMatch(/Seeded-RNG detector/);
});
