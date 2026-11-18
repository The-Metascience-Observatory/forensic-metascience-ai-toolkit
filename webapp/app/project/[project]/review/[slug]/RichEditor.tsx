"use client";

import type { Editor } from "@tiptap/core";
import { EditorContent, useEditor } from "@tiptap/react";
import DOMPurify from "dompurify";
import { useMemo, useRef } from "react";

import { RawHtml, parseMarkdown, respell, richExtensions } from "@/lib/richExtensions";
import { mergeRichEdit } from "@/lib/richMerge";

/** A raw HTML block on screen: rendered (sanitized) and not editable here. */
const RawHtmlView = RawHtml.extend({
  addNodeView() {
    return ({ node }) => {
      const dom = document.createElement("div");
      const source = String(node.attrs.source || "").trim();
      dom.contentEditable = "false";
      if (/^<!--[\s\S]*-->$/.test(source)) {
        dom.className = "raw-html raw-html-comment";
        dom.textContent = source;
        dom.title = "A comment in the markdown source. Not shown on GitHub; kept as it is.";
      } else {
        dom.className = "raw-html";
        dom.innerHTML = DOMPurify.sanitize(source);
        dom.title = "HTML block: shown as it will render. Edit it in Markdown mode.";
      }
      return { dom };
    };
  },
});

type Tool = { label: string; title: string; active?: (e: Editor) => boolean; run: (e: Editor) => void; show?: (e: Editor) => boolean };

const inTable = (e: Editor) => e.isActive("table");
const TOOLS: (Tool | "|")[] = [
  { label: "B", title: "Bold (Ctrl+B)", active: (e) => e.isActive("bold"), run: (e) => e.chain().focus().toggleBold().run() },
  { label: "I", title: "Italic (Ctrl+I)", active: (e) => e.isActive("italic"), run: (e) => e.chain().focus().toggleItalic().run() },
  { label: "</>", title: "Inline code (Ctrl+E)", active: (e) => e.isActive("code"), run: (e) => e.chain().focus().toggleCode().run() },
  { label: "Link", title: "Add, change or remove a link", active: (e) => e.isActive("link"), run: (e) => {
    const now = String(e.getAttributes("link").href || "");
    const href = window.prompt("Link address (leave empty to remove the link)", now);
    if (href === null) return;
    if (!href.trim()) e.chain().focus().extendMarkRange("link").unsetLink().run();
    else e.chain().focus().extendMarkRange("link").setLink({ href: href.trim() }).run();
  } },
  "|",
  { label: "H2", title: "Section heading", active: (e) => e.isActive("heading", { level: 2 }), run: (e) => e.chain().focus().toggleHeading({ level: 2 }).run() },
  { label: "H3", title: "Sub-heading", active: (e) => e.isActive("heading", { level: 3 }), run: (e) => e.chain().focus().toggleHeading({ level: 3 }).run() },
  { label: "• List", title: "Bulleted list", active: (e) => e.isActive("bulletList"), run: (e) => e.chain().focus().toggleBulletList().run() },
  { label: "1. List", title: "Numbered list", active: (e) => e.isActive("orderedList"), run: (e) => e.chain().focus().toggleOrderedList().run() },
  { label: "Quote", title: "Block quote", active: (e) => e.isActive("blockquote"), run: (e) => e.chain().focus().toggleBlockquote().run() },
  { label: "Code block", title: "Code block", active: (e) => e.isActive("codeBlock"), run: (e) => e.chain().focus().toggleCodeBlock().run() },
  "|",
  { label: "+ Row", title: "Add a table row below", show: inTable, run: (e) => e.chain().focus().addRowAfter().run() },
  { label: "− Row", title: "Delete this table row", show: inTable, run: (e) => e.chain().focus().deleteRow().run() },
  { label: "+ Column", title: "Add a table column to the right", show: inTable, run: (e) => e.chain().focus().addColumnAfter().run() },
  { label: "− Column", title: "Delete this table column", show: inTable, run: (e) => e.chain().focus().deleteColumn().run() },
  { label: "Undo", title: "Undo (Ctrl+Z)", run: (e) => e.chain().focus().undo().run() },
  { label: "Redo", title: "Redo (Ctrl+Shift+Z)", run: (e) => e.chain().focus().redo().run() },
];

/** Rich-text editing of a markdown file. `value` is read once, when the
 *  editor opens; every edit reports the file's new text through `onChange`,
 *  with every block the edit did not touch left exactly as it was in `value`
 *  (`lib/richMerge.ts`). */
export default function RichEditor({ value, onChange }: { value: string; onChange: (markdown: string) => void }) {
  const original = useRef(value);
  const report = useRef(onChange);
  report.current = onChange;
  const cache = useRef(new Map<string, string>());
  const extensions = useMemo(() => richExtensions(RawHtmlView), []);
  const editor = useEditor({
    extensions,
    // Filled in `onCreate`: the document is built by `parseMarkdown`, the
    // same way the merge reads each block.
    content: "",
    immediatelyRender: false,
    shouldRerenderOnTransaction: true,
    editorProps: { attributes: { class: "md", "aria-label": "README, rich text", spellcheck: "true" } },
    onCreate: ({ editor: e }) => {
      // Not an edit: no update is reported and there is nothing to undo.
      e.chain().setMeta("addToHistory", false).setContent(parseMarkdown(e.markdown!, original.current), { emitUpdate: false }).run();
    },
    onUpdate: ({ editor: e }) => {
      const canon = (src: string) => {
        let out = cache.current.get(src);
        if (out === undefined) { out = respell(e.markdown!, src); cache.current.set(src, out); }
        return out;
      };
      report.current(mergeRichEdit(original.current, e.getMarkdown(), canon));
    },
  });
  if (!editor) return <div className="readme-body muted">Loading the editor…</div>;
  return (
    <div className="rich-editor" data-rich-editor>
      <div className="rich-tools" role="toolbar" aria-label="Formatting">
        {TOOLS.map((tool, i) => tool === "|"
          ? <span key={i} className="rich-sep" aria-hidden />
          : (tool.show && !tool.show(editor)) ? null : (
            <button key={tool.label} type="button" title={tool.title}
                    className={tool.active?.(editor) ? "primary" : undefined} aria-pressed={tool.active ? tool.active(editor) : undefined}
                    onMouseDown={(ev) => ev.preventDefault()} onClick={() => tool.run(editor)}>
              {tool.label}
            </button>
          ))}
      </div>
      <div className="readme-body"><EditorContent editor={editor} /></div>
    </div>
  );
}
