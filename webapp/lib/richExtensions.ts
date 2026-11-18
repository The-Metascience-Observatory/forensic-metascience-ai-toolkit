import { Mark, Node, type AnyExtension } from "@tiptap/core";
import { TableKit } from "@tiptap/extension-table";
import { Markdown } from "@tiptap/markdown";
import StarterKit from "@tiptap/starter-kit";

/** A raw HTML block of the markdown file (an HTML table with merged cells, a
 *  `<!-- marker -->` comment): held verbatim, shown but not editable in
 *  rich-text mode, and written back exactly as it was. Editing one is what
 *  Markdown mode is for; turning it into editor nodes would lose whatever
 *  the editor has no node for (rowspan, comments). */
export const RawHtml = Node.create({
  name: "rawHtml",
  group: "block",
  atom: true,
  selectable: true,
  draggable: false,
  addAttributes() {
    return { source: { default: "" } };
  },
  parseHTML() {
    return [{ tag: "div[data-raw-html]", getAttrs: (el) => ({ source: (el as HTMLElement).getAttribute("data-source") || "" }) }];
  },
  renderHTML({ node }) {
    return ["div", { "data-raw-html": "", "data-source": node.attrs.source }];
  },
  markdownTokenName: "html",
  parseMarkdown: (token, helpers) => {
    // Inline HTML (`<sub>`, `<br>`) stays with the default handling.
    if (!token.block) return [];
    const source = String(token.raw || token.text || "").replace(/\s+$/, "");
    return source ? helpers.createNode("rawHtml", { source }) : [];
  },
  renderMarkdown: (node) => String(node.attrs?.source || ""),
});

/** `<sub>` and `<sup>`, the only inline HTML the READMEs use: marks that are
 *  written back as the same tags. (Without them the tags are dropped from any
 *  paragraph that is edited: "H<sub>2</sub>O" would come back as "H2O".) */
const inlineTag = (name: string, tag: "sub" | "sup") => Mark.create({
  name,
  excludes: tag === "sub" ? "superscript" : "subscript",
  parseHTML() { return [{ tag }]; },
  renderHTML() { return [tag, 0]; },
  renderMarkdown: (node, h) => `<${tag}>${h.renderChildren(node)}</${tag}>`,
});
export const Subscript = inlineTag("subscript", "sub");
export const Superscript = inlineTag("superscript", "sup");

/** The editor's schema and markdown rules. `rawHtmlView` adds the on-screen
 *  rendering of a raw HTML block (the browser side). */
export function richExtensions(rawHtml: AnyExtension = RawHtml): AnyExtension[] {
  return [
    StarterKit.configure({ link: { openOnClick: false, autolink: false }, underline: false, strike: false }),
    TableKit.configure({ table: { resizable: false } }),
    rawHtml, Subscript, Superscript,
    Markdown.configure({ markedOptions: { gfm: true } }),
  ];
}

type Json = { type?: string; text?: string; content?: Json[]; [key: string]: unknown };
type Manager = { parse: (markdown: string) => Json; serialize: (doc: Json) => string };

let entityBox: HTMLTextAreaElement | null = null;
function decodeEntities(text: string): string {
  if (!/&[#\w]+;/.test(text) || typeof document === "undefined") return text;
  entityBox ??= document.createElement("textarea");
  entityBox.innerHTML = text;
  return entityBox.value;
}

/** Text as the reader sees it: a line wrapped in the source is one line of
 *  prose (written back with the wrap, a continuation line that starts with
 *  `#` or `1.` would become a heading or a list), and `&mdash;` is a dash
 *  (the editor would otherwise write the entity back as literal text). */
function tidy(node: Json, inCode = false): Json {
  const code = inCode || node.type === "codeBlock";
  if (typeof node.text === "string" && !code) {
    const marks = (node.marks as { type?: string }[] | undefined) || [];
    if (marks.some((m) => m.type === "code")) return node;
    return { ...node, text: decodeEntities(node.text.replace(/[ \t]*\n[ \t]*/g, " ")) };
  }
  return node.content ? { ...node, content: node.content.map((child) => tidy(child, code)) } : node;
}

/** The editor document for a markdown text. */
export const parseMarkdown = (manager: Manager, markdown: string): Json => tidy(manager.parse(markdown));
/** How the editor writes a markdown text it was given: the merge's `canon`. */
export const respell = (manager: Manager, markdown: string): string => manager.serialize(parseMarkdown(manager, markdown));
