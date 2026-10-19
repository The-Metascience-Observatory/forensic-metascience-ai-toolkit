/** Group Findings, client side: the SERVER decides the groups
 *  (`finding_groups.group_issues`, applied before pagination) and tags each
 *  member with `group`; members of a group arrive contiguous. These helpers
 *  only walk that list, so there is one copy of the grouping rule. */

export const GROUP_KEY = "metascience.groupFindings";

export type GroupMeta = {
  id: string; family: string; tool: string; unit: string; n: number;
  severity_9?: number | null; provisional?: boolean;
};

type Item = { id?: string; group?: GroupMeta | null };

/** Stored preference; ON unless the reviewer turned it off. */
export function readGrouped(stored: string | null): boolean {
  return stored !== "0";
}

/** Index of the first finding of each entry (a group is one entry). */
export function entryStarts(items: Item[]): number[] {
  const out: number[] = [];
  items.forEach((it, i) => {
    const g = it.group?.id;
    if (i === 0 || !g || items[i - 1].group?.id !== g) out.push(i);
  });
  return out;
}

/** The entry `delta` steps from the one holding `at`, landing on its first finding. */
export function stepEntry(items: Item[], at: number, delta: number): number {
  if (!items.length) return 0;
  const starts = entryStarts(items);
  let k = 0;
  for (let j = 0; j < starts.length; j++) if (starts[j] <= at) k = j;
  const next = Math.min(starts.length - 1, Math.max(0, k + delta));
  return starts[next];
}

/** Is `i` the first finding of its group? */
export function isGroupStart(items: Item[], i: number): boolean {
  const g = items[i]?.group?.id;
  return !!g && items[i - 1]?.group?.id !== g;
}
