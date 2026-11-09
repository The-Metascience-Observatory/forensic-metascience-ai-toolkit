"use client";

import { useCallback, useEffect } from "react";
import type { useRouter } from "next/navigation";
import type { Feed, Item } from "@/lib/types/images";
import { itemHref } from "@/app/images/lib";

/** Keyboard navigation over the loaded rows: ArrowDown/ArrowUp move the
 *  cursor (and load the next page when it runs off the end), Enter opens the
 *  item. `arrowTargetRef` holds the row an arrow press is waiting on past the loaded
 *  rows; the queue clears it when the filter changes. */
export function useQueueKeyboard({ rows, cursor, setCursor, feed, nextOffset, loadMore, project, selection, router, scrollHostRef, arrowTargetRef }: {
  rows: Item[]; cursor: number; setCursor: React.Dispatch<React.SetStateAction<number>>; feed: Feed | null;
  nextOffset: number | null | undefined; loadMore: () => void; project: string; selection: string;
  router: ReturnType<typeof useRouter>; scrollHostRef: React.RefObject<HTMLDivElement | null>;
  arrowTargetRef: React.RefObject<number | null>;
}) {
  const selectRow = useCallback((index: number) => {
    setCursor(index);
    const row=scrollHostRef.current?.querySelector<HTMLElement>(`[data-row-index="${index}"]`);
    row?.focus({preventScroll:true});
    row?.scrollIntoView({block:"nearest"});
  }, [setCursor, scrollHostRef]);
  useEffect(() => {
    if (arrowTargetRef.current != null && arrowTargetRef.current < rows.length) {
      selectRow(arrowTargetRef.current); arrowTargetRef.current=null;
    }
    if (feed && cursor >= rows.length) setCursor(Math.max(0,rows.length-1));
  }, [rows.length, feed, cursor, selectRow, setCursor, arrowTargetRef]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.defaultPrevented) return;
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if ((e.target as HTMLElement | null)?.isContentEditable) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (!rows.length) return;
        const index=cursor + (e.key === "ArrowDown" ? 1 : -1);
        if (index >= rows.length && nextOffset != null) { arrowTargetRef.current=index; loadMore(); }
        else selectRow(Math.max(0,Math.min(rows.length-1,index)));
      }
      else if (e.key === "Enter" && rows[cursor] && tag !== "BUTTON" && tag !== "A") {
        e.preventDefault();
        router.push(itemHref(project, rows[cursor].id, selection));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [rows, cursor, project, router, selection, nextOffset, loadMore, selectRow, arrowTargetRef]);
}
