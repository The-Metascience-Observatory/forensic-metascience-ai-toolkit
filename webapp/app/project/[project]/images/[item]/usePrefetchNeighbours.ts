"use client";

import { useEffect } from "react";
import { prefetchItem } from "@/app/images/useFeed";
import type { Ref } from "@/lib/decisionQueue";
import { mediaUrl } from "@/app/images/lib";
import type { Navigation } from "./useItemData";

/** Once the item's queue position is known, load the records and panel
 *  images of the items the reviewer is likely to open next. */
export function usePrefetchNeighbours(project: string, selection: string, nav: Navigation | null) {
  useEffect(() => {
    if (!nav) return;
    // Warm what the reviewer most likely opens next: the next undecided
    // item (where a decision advances) and the plain next one (j).
    const warm=(ref:Ref|null)=>{if(ref)void prefetchItem(project,selection,ref.id,(dir,f)=>mediaUrl(project,dir,f));};
    const upcoming:Ref[]=nav.upcoming||[];
    warm(nav.next_undecided);warm(upcoming[1]||null);warm(nav.next);
  }, [nav, project, selection]);
}
