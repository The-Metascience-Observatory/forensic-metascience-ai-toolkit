import assert from "node:assert/strict";
import { test } from "vitest";

import { readmeSummary, triageNote } from "../lib/readmeSummary.ts";

const BOLD = `# Reproducing data in "A paper" with a random number generator

**Summary**

- First bullet.
- Second bullet with \`code\`.

## Paper

Not part of the summary.
`;

test("the Summary bullets are read from both README layouts", () => {
  assert.equal(readmeSummary(BOLD), "- First bullet.\n- Second bullet with `code`.");
  assert.equal(readmeSummary(BOLD.replace("**Summary**", "## Summary")), "- First bullet.\n- Second bullet with `code`.");
  assert.equal(readmeSummary(BOLD.replace("**Summary**", "**Summary:**").replace(/\n/g, "\r\n")), "- First bullet.\n- Second bullet with `code`.");
});

test("a README without a Summary gives nothing, and a later section is never borrowed", () => {
  assert.equal(readmeSummary("# Title\n\n**Paper.** Text.\n\n## Finding\n\n- a\n"), "");
  assert.equal(readmeSummary(""), "");
  // The Summary is the last thing before the kit marker: stop there.
  assert.equal(readmeSummary("**Summary**\n- a\n<!-- rngdetect-kit:start -->\n## Generator details\n"), "- a");
  // "Summary of ..." as a heading of something else is not the Summary.
  assert.equal(readmeSummary("## Summary of generators\n- a\n"), "");
});

test("the triage note drops its title line and keeps the rest", () => {
  assert.equal(triageNote("# Triage: A paper\n\nCategory: C\nDecision: repo\n\n- **What matched:** x\n"),
    "Category: C\nDecision: repo\n\n- **What matched:** x");
  assert.equal(triageNote("Category: A\n"), "Category: A");
  assert.equal(triageNote(""), "");
});
