"use client";

import useSWR from "swr";

import { getJson } from "./getJson.ts";
import type { Draft, DraftJob, DraftKind } from "./paperDrafts.ts";

export type { Draft, DraftJob, DraftKind };

/** `/api/drafts` as the review page reads it. */
export type DraftsView = {
  jobs: Record<DraftKind, DraftJob | null>;
  drafts: Draft[];
};

export const jobBusy = (job: DraftJob | null | undefined) => job?.state === "starting" || job?.state === "running";

/** The paper's drafts. Polls every 3 s while a job is making one. */
export function useDrafts(project: string, dir: string | null | undefined) {
  const key = dir ? `/api/drafts?project=${encodeURIComponent(project)}&dir=${encodeURIComponent(dir)}` : null;
  const { data, error, mutate } = useSWR<DraftsView>(key, (url: string) => getJson<DraftsView>(url), {
    revalidateOnFocus: false, shouldRetryOnError: false,
    refreshInterval: (d) => (d && (jobBusy(d.jobs.email) || jobBusy(d.jobs.pubpeer)) ? 3000 : 0),
  });
  return {
    view: data, error: error ? String(error.message || error) : null,
    set: (next: DraftsView) => mutate(next, { revalidate: false }),
    reload: () => mutate(),
  };
}
