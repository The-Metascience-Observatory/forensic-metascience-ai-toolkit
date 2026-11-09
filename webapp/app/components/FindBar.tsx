"use client";

import { useEffect } from "react";
import type { Ref } from "react";

export function FindBar({
  query, matchAt, matchN, placeholder, inputRef, onQuery, onPrev, onNext, onClose,
}: {
  query: string;
  matchAt: number;
  matchN: number;
  placeholder: string;
  inputRef: Ref<HTMLInputElement>;
  onQuery: (q: string) => void;
  onPrev: () => void;
  onNext: () => void;
  onClose: () => void;
}) {
  return (
    <form className="pdf-find" onSubmit={(e) => e.preventDefault()}>
      <input
        ref={inputRef}
        value={query}
        placeholder={placeholder}
        aria-label={placeholder}
        onChange={(e) => onQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            if (e.shiftKey) onPrev();
            else onNext();
          }
        }}
      />
      <span className="muted" style={{ fontSize: 12, minWidth: 52 }}>
        {query.trim() ? (matchN ? `${matchAt + 1} / ${matchN}` : "0 / 0") : ""}
      </span>
      <button type="button" onClick={onPrev} disabled={!matchN}
              title="Previous (Shift+Enter)">‹</button>
      <button type="button" onClick={onNext} disabled={!matchN}
              title="Next (Enter)">›</button>
      <button type="button" onClick={onClose} title="Close (Esc)">×</button>
    </form>
  );
}

export function useFindShortcut(
  openFind: () => void,
  closeFind: () => void,
  stepMatch: (delta: number) => void,
  isOpen: () => boolean,
) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const isFind = (e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "f";
      if (isFind) {
        e.preventDefault();
        e.stopPropagation();
        openFind();
        return;
      }
      if (!isOpen()) return;
      if (e.key === "Escape") {
        e.preventDefault();
        closeFind();
        return;
      }
      if (e.key === "F3" || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "g")) {
        e.preventDefault();
        stepMatch(e.shiftKey ? -1 : 1);
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [openFind, closeFind, stepMatch, isOpen]);
}
