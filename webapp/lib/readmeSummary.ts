/** The paper-level summary a reproduction repo's README opens with.
 *
 * The repo agents write it two ways (2026-11: 258 repos `**Summary**`, 46
 * `## Summary`), so both are read. Pure text in, markdown out. */

// A bold lead may carry text on its own line; a heading must be "Summary" alone
// ("## Summary of generators" is some other section).
const SUMMARY_LEAD = /^\s*(?:(?:\*\*Summary\*\*:?|\*\*Summary[.:]\*\*)\s*(.*)|#{2,3}\s+Summary:?\s*)$/i;
const HEADING = /^#{1,6}\s/;

/** The markdown under the README's Summary lead, up to the next heading;
 *  `""` when the README has no Summary. */
export function readmeSummary(md: string): string {
  const lines = String(md || "").replace(/\r\n?/g, "\n").split("\n");
  const start = lines.findIndex((line) => SUMMARY_LEAD.test(line));
  if (start < 0) return "";
  const out: string[] = [];
  const sameLine = (SUMMARY_LEAD.exec(lines[start])?.[1] || "").trim();
  if (sameLine) out.push(sameLine);
  for (const line of lines.slice(start + 1)) {
    if (HEADING.test(line) || line.startsWith("<!--")) break;
    out.push(line);
  }
  return out.join("\n").trim();
}

/** A triage note (`rng_triage.md`) without its `# Triage: <title>` line: the
 *  page already shows the paper's title. */
export function triageNote(md: string): string {
  const lines = String(md || "").replace(/\r\n?/g, "\n").split("\n");
  const first = lines.findIndex((line) => line.trim());
  if (first >= 0 && /^#\s/.test(lines[first])) lines.splice(0, first + 1);
  return lines.join("\n").trim();
}
