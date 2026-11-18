"use client";

import useSWR from "swr";

import { getJson } from "./getJson.ts";

/** `/api/repo` as the review page reads it (`lib/repoInfo.ts` on the server). */
export type RepoView = {
  repo: {
    name: string; url: string; hasRemote: boolean; inOrg: boolean;
    readmeDirty: boolean; otherDirty: string[]; ahead: number | null;
    visibility: "PRIVATE" | "PUBLIC" | "INTERNAL" | "unknown";
  } | null;
  readme: string | null;
  sha256: string | null;
  summary_md: string;
  triage_md: string;
  embargoed: boolean;
  /** The paper folder on the server; sent to admins only. */
  paper_path?: string;
};

/** The paper's reproduction repository. `set` replaces the cached view with
 *  the one a write returned, so the page never shows a stale state. */
export function useRepo(project: string, dir: string | null | undefined) {
  const key = dir ? `/api/repo?project=${encodeURIComponent(project)}&dir=${encodeURIComponent(dir)}` : null;
  const { data, error, mutate } = useSWR<RepoView>(key, (url: string) => getJson<RepoView>(url), {
    revalidateOnFocus: false, shouldRetryOnError: false,
  });
  return {
    info: data, error: error ? String(error.message || error) : null,
    set: (next: RepoView) => mutate(next, { revalidate: false }),
    reload: () => mutate(),
  };
}
