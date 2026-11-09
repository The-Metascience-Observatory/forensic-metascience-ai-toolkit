"use client";

import type { useRouter } from "next/navigation";
import { useEffect } from "react";
import { DECISIONS, type Item, queueHref } from "@/app/images/lib";
import type { Decide, Neighbor } from "./useItemData";

/** The item page's keyboard map: j/k next/prev, n next undecided, a/B the
 *  shown side, 1–9 decide, Esc back to the queue (README "Keyboard"). */
export function useItemKeys({ go, next, prev, nextUndecided, jumpTo, decide, item, project, selection, router }: {
  go: (it: Neighbor | null) => void;
  next: Neighbor | null; prev: Neighbor | null; nextUndecided: Neighbor | null;
  jumpTo: (s: 0 | 1) => void;
  decide: Decide;
  item: Item | null;
  project: string; selection: string; router: ReturnType<typeof useRouter>;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.defaultPrevented) return;
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === "j") go(next);
      else if (e.key === "k") go(prev);
      else if (e.key === "n") go(nextUndecided);
      else if (e.key === "a") jumpTo(0);
      else if (e.key === "b" && e.shiftKey === false && !item?.panels[1]) { /* comparator uses b */ }
      else if (e.key === "B" || (e.key === "b" && item?.panels[1] && e.altKey)) jumpTo(1);
      else if (DECISIONS.some((x) => x[1] === e.key)) {
        const d = DECISIONS.find((x) => x[1] === e.key);
        if (d) decide(d[0]);
      } else if (e.key === "Escape") router.push(queueHref(project, selection));
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, next, prev, nextUndecided, jumpTo, decide, item, project, router]);
}
