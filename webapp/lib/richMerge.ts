import remarkGfm from "remark-gfm";
import remarkParse from "remark-parse";
import { unified } from "unified";

/** Keeping a rich-text edit of a markdown file to the blocks that changed.
 *
 * A rich-text editor holds a document, not the file's text: writing that
 * document back out re-spells the whole file (list markers, table padding,
 * escapes, wrapped lines), so one changed word would rewrite the README and
 * bury the edit in the diff. Here the file is cut into its top-level blocks
 * (paragraph, heading, list, table, HTML block ...). A block the editor still
 * writes the way it wrote it before any edit is emitted from the ORIGINAL
 * text, byte for byte, with the original spacing around it; only a block that
 * is new or changed takes the editor's spelling. */

const parser = unified().use(remarkParse).use(remarkGfm);

export interface Block {
  /** The block's source text. */
  src: string;
  /** The text between the previous block (or the file's start) and this one. */
  before: string;
  /** A link reference definition (`[1]: https://...`): text the editor
   *  resolves into the links that use it and then has no node for. */
  definition: boolean;
}

/** The file's top-level blocks, and the text after the last one. */
export function splitBlocks(md: string): { blocks: Block[]; tail: string } {
  const tree = parser.parse(md);
  const blocks: Block[] = [];
  let at = 0;
  for (const node of tree.children) {
    const start = node.position?.start.offset, end = node.position?.end.offset;
    if (start == null || end == null || end <= start) continue;
    blocks.push({ before: md.slice(at, start), src: md.slice(start, end), definition: node.type === "definition" });
    at = end;
  }
  return { blocks, tail: md.slice(at) };
}

const norm = (s: string) => s.replace(/\r\n?/g, "\n").trim();

/** For each item of `b`, the index in `a` it pairs with in a longest common
 *  subsequence, else -1. */
function align(a: string[], b: string[]): number[] {
  const n = a.length, m = b.length;
  const len = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      len[i][j] = a[i] === b[j] ? len[i + 1][j + 1] + 1 : Math.max(len[i + 1][j], len[i][j + 1]);
    }
  }
  const pair = new Array<number>(m).fill(-1);
  for (let i = 0, j = 0; i < n && j < m;) {
    if (a[i] === b[j]) { pair[j] = i; i++; j++; }
    else if (len[i + 1][j] >= len[i][j + 1]) i++;
    else j++;
  }
  return pair;
}

/** `canon(src)` is how the editor writes one block it was given as `src`
 *  (parse, then serialize). `""` means the editor cannot hold the block at
 *  all (a link reference definition): such a block is never taken as deleted. */
export type Canon = (src: string) => string;

/** The file after a rich-text edit: `edited` is the editor's markdown for
 *  the whole document, `original` the text the editor was opened on. */
export function mergeRichEdit(original: string, edited: string, canon: Canon): string {
  const o = splitBlocks(original.replace(/\r\n?/g, "\n"));
  const e = splitBlocks(edited.replace(/\r\n?/g, "\n"));
  // A block is written alone, but with the file's link definitions in reach,
  // so that `[text][1]` comes out as the link it is in the whole document.
  const defs = o.blocks.filter((b) => b.definition).map((b) => b.src).join("\n");
  const oCanon = o.blocks.map((b) => (b.definition ? "" : norm(canon(defs ? `${b.src}\n\n${defs}` : b.src))));
  // Blocks the editor cannot hold ride with the block before them.
  const held = o.blocks.map((_, i) => i).filter((i) => oCanon[i] !== "");
  const pair = align(held.map((i) => oCanon[i]), e.blocks.map((b) => norm(b.src))).map((k) => (k < 0 ? -1 : held[k]));

  let out = "";
  let prev = -2;            // the original index of the block just emitted; -2 at the start, -1 after a new block
  const emitted = new Set<number>();
  const emitOriginal = (i: number) => {
    const follows = prev === i - 1 || (prev === -2 && i === 0);
    out += (follows ? o.blocks[i].before : out ? "\n\n" : "") + o.blocks[i].src;
    emitted.add(i); prev = i;
    // ... and the unholdable blocks straight after it, with their own spacing.
    for (let k = i + 1; k < o.blocks.length && oCanon[k] === ""; k++) {
      out += o.blocks[k].before + o.blocks[k].src; emitted.add(k); prev = k;
    }
  };
  // Unholdable blocks at the very top of the file stay there.
  for (let k = 0; k < o.blocks.length && oCanon[k] === ""; k++) {
    out += o.blocks[k].before + o.blocks[k].src; emitted.add(k); prev = k;
  }
  e.blocks.forEach((block, j) => {
    if (pair[j] >= 0) emitOriginal(pair[j]);
    else { out += (out ? "\n\n" : "") + norm(block.src); prev = -1; }
  });
  // An unholdable block whose neighbour was edited away is kept at the end.
  o.blocks.forEach((b, k) => {
    if (oCanon[k] === "" && !emitted.has(k)) { out += (out ? "\n\n" : "") + b.src; prev = -1; }
  });
  if (!out.trim()) return "";
  return out + (prev === o.blocks.length - 1 ? o.tail : "\n");
}
