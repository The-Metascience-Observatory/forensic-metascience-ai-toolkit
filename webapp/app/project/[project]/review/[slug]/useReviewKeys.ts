import { useCallback, useEffect } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { NavRef } from "@/lib/nav";
import { stepEntry, type GroupMeta } from "@/lib/findingGroups";

/** The paper page's arrow keys: up/down between findings, left/right between
 *  papers. Typing fields and the split gutter keep their own keys. */
export function useReviewKeys({ issues, grouped, setAt, goPaper, data }: {
  issues: { id?: string; group?: GroupMeta | null }[];
  grouped: boolean | null;
  setAt: Dispatch<SetStateAction<number>>;
  goPaper: (next: NavRef | null | "caught-up") => void;
  data: { nav?: { next?: NavRef | null; prev?: NavRef | null } | null } | null;
}) {
  // Grouped, the arrows step between ENTRIES (a group is one); its findings
  // are reached by opening it. Ungrouped, finding by finding as before.
  const move = useCallback((delta: number) => {
    setAt((i) => grouped ? stepEntry(issues, i, delta)
      : Math.min(issues.length - 1, Math.max(0, i + delta)));
  }, [issues, grouped, setAt]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
      if (el?.closest?.(".split-gutter")) return;
      if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
      if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
      if (e.key === "ArrowRight") {
        e.preventDefault();
        goPaper(data?.nav?.next ?? "caught-up");
      }
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        goPaper(data?.nav?.prev ?? null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move, goPaper, data]);
}
