"use client";

import { useState, type MouseEvent } from "react";

/** Copies `text` to the clipboard, with the execCommand fallback for a page
 *  served over plain http (the local app), and confirms for 1.2 s. */
export function CopyButton({ text, label = "Copy", done = "Copied", title }: {
  text: string; label?: string; done?: string; title?: string;
}) {
  const [ok, setOk] = useState(false);
  async function copy(e: MouseEvent) {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    setOk(true);
    window.setTimeout(() => setOk(false), 1200);
  }
  return (
    <button type="button" onClick={copy} style={{ fontSize: 11, marginTop: 6 }} title={title}>
      {ok ? done : label}
    </button>
  );
}
