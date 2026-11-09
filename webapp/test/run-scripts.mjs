#!/usr/bin/env node
// Runs plain test scripts (Playwright component tests, live-server checks)
// one after another and reports each as passed, SKIPPED or failed. A script
// that cannot measure (missing opt-in fixture, no server) prints a line
// starting with "SKIPPED" and exits 0; it is counted as skipped, never as a
// pass. Usage: node test/run-scripts.mjs test/a.mjs test/b.mjs ...
import { spawnSync } from "node:child_process";

const files = process.argv.slice(2);
if (!files.length) { console.error("no scripts given"); process.exit(2); }
const results = [];
for (const file of files) {
  const run = spawnSync(process.execPath, [file], { encoding: "utf8", stdio: ["inherit", "pipe", "pipe"] });
  const out = (run.stdout || "") + (run.stderr || "");
  process.stdout.write(out);
  const skipped = /^SKIPPED\b/m.test(out);
  results.push({ file, status: run.status === 0 ? (skipped ? "skipped" : "passed") : "failed" });
}
const counts = { passed: 0, skipped: 0, failed: 0 };
for (const r of results) { counts[r.status]++; console.log(`${r.status.padEnd(7)} ${r.file}`); }
console.log(`${counts.passed} passed, ${counts.skipped} skipped, ${counts.failed} failed`);
process.exit(counts.failed ? 1 : 0);
