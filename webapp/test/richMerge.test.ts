// @vitest-environment jsdom
import { Editor } from "@tiptap/core";
import { expect, test } from "vitest";

import { parseMarkdown, respell, richExtensions } from "@/lib/richExtensions";
import { mergeRichEdit, splitBlocks } from "@/lib/richMerge";

// A README in the repo agents' style: `-` bullets, `*emphasis*`, a padded
// pipe table, an HTML table with merged cells, the kit markers, a wrapped
// paragraph and a last line that must stay last.
const README = `# Reproducing data in "A paper" with a random number generator

**Summary**

- The 45 cells of *Table 4* are reproduced by \`numpy.random.seed(0)\`.
- Each column is 15 consecutive draws,
  wrapped onto a second line.

## Published vs generated values

| cell | published | generated |
|:-----|----------:|----------:|
| a    |     1.250 |    1.2504 |

<table>
<tr><th rowspan="2">panel</th><th colspan="2">volume (mL)</th></tr>
<tr><th>published</th><th>generated</th></tr>
<tr><td>CVVH</td><td>20.5379</td><td>20.5379</td></tr>
</table>

1. First check.
2. Second check, with H<sub>2</sub>O and a [link](https://example.org/a_b).

<!-- rngdetect-kit:start -->
## Generator details

\`\`\`python
u = rng.random_sample(15)   # 5 * 3
\`\`\`
<!-- rngdetect-kit:end -->

**Funding stated** in the paper: none.
`;

function open(md: string) {
  const editor = new Editor({ element: null, extensions: richExtensions() });
  editor.commands.setContent(parseMarkdown(editor.markdown!, md));
  const canon = (src: string) => respell(editor.markdown!, src);
  return { editor, merged: () => mergeRichEdit(md, editor.getMarkdown(), canon) };
}

test("opening a README in rich text and changing nothing leaves the file byte for byte", () => {
  const { editor, merged } = open(README);
  // The editor's own spelling of the file is NOT the file (that is the point).
  expect(editor.getMarkdown()).not.toBe(README);
  expect(merged()).toBe(README);
});

test("an edit rewrites its own block and nothing else", () => {
  const { editor, merged } = open(README);
  // Type at the end of the "First check." list item.
  let at = -1;
  editor.state.doc.descendants((node, pos) => { if (node.isText && node.text === "First check.") at = pos + node.nodeSize; });
  editor.chain().insertContentAt(at, " Added.").run();
  const out = merged();
  expect(out).toContain("1. First check. Added.\n2. Second check, with H<sub>2</sub>O and a [link](https://example.org/a_b).");
  const before = splitBlocks(README).blocks.map((b) => b.src), after = splitBlocks(out).blocks.map((b) => b.src);
  expect(after.length).toBe(before.length);
  expect(after.filter((b, i) => b !== before[i]).length).toBe(1);
  // The HTML table (merged cells), the kit markers and the last line are untouched.
  expect(out).toContain('<tr><th rowspan="2">panel</th><th colspan="2">volume (mL)</th></tr>');
  expect(out).toContain("<!-- rngdetect-kit:start -->\n## Generator details");
  expect(out.endsWith("**Funding stated** in the paper: none.\n")).toBe(true);
});

test("wrapped lines and entities survive an edit of their block", () => {
  // Written back with its wrap, the second line would start a heading.
  const md = "- Columns \"Measurement\n  #5\" are reproduced &mdash; 24 of 24 cells.\n";
  const { editor, merged } = open(md);
  expect(merged()).toBe(md);
  editor.chain().insertContentAt(editor.state.doc.content.size - 3, " Checked.").run();
  expect(merged()).toBe("- Columns \"Measurement #5\" are reproduced — 24 of 24 cells. Checked.\n");
});

test("a new paragraph and a deleted block land where they were made", () => {
  const { editor, merged } = open(README);
  editor.chain().insertContentAt(editor.state.doc.content.size, { type: "paragraph", content: [{ type: "text", text: "A closing note." }] }).run();
  expect(merged()).toBe(README.trimEnd() + "\n\nA closing note.\n");

  const second = open(README);
  let from = -1, to = -1;
  second.editor.state.doc.forEach((node, pos) => { if (node.type.name === "orderedList") { from = pos; to = pos + node.nodeSize; } });
  second.editor.chain().deleteRange({ from, to }).run();
  const out = second.merged();
  expect(out).not.toContain("First check.");
  expect(out).toContain("</table>\n\n<!-- rngdetect-kit:start -->");
  expect(splitBlocks(out).blocks.length).toBe(splitBlocks(README).blocks.length - 1);
});

test("a block the editor cannot hold (a link definition) is never taken as deleted", () => {
  const md = "Intro with a [ref][1].\n\n[1]: https://example.org\n\nLast paragraph.\n";
  const { editor, merged } = open(md);
  expect(merged()).toBe(md);
  editor.chain().insertContentAt(editor.state.doc.content.size, { type: "paragraph", content: [{ type: "text", text: "More." }] }).run();
  expect(merged()).toContain("[1]: https://example.org");
});

test("the merge itself: unchanged blocks keep the original text and spacing", () => {
  const canon = (s: string) => s.replace(/^\* /gm, "- ").replace(/[ \t]+$/gm, "");
  const original = "# T\n\n\n* a\n* b\n\npara  \n";
  expect(mergeRichEdit(original, "# T\n\n- a\n- b\n\npara\n", canon)).toBe(original);
  expect(mergeRichEdit(original, "# T\n\n- a\n- b\n- c\n\npara\n", canon)).toBe("# T\n\n- a\n- b\n- c\n\npara  \n");
  expect(mergeRichEdit(original, "", canon)).toBe("");
});
