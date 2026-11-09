/** Run picker records, as the workbench `runs`/`paper` reads return them.
 *  Types only; the component is `app/RunSelector.tsx`. */

export type RunOption = {
  id: string; label: string; n_items?: number; states?: Record<string, number>;
  provenance?: unknown; configuration?: unknown; requested_components?: string[]; status?: string;
  execution_id?: string | null; component?: string;
  /** Number of per-paper records folded into this execution. */
  n_runs?: number;
  /** A run made by a non-default pipeline: "tools only · provisional". */
  pipeline?: { name?: string | null; complete_review?: boolean; label: string } | null;
};

/** What the "latest" selection actually resolved to, from the server. The
 *  selector prints the newest run's OWN date and how many sweeps the per-paper
 *  view mixes, because the header's `built_at` is when the projection was
 *  rebuilt, not when the results were produced -- a stale run rebuilt this
 *  morning reads as fresh. (2026-09-14: two newer sweeps sat on disk unsynced
 *  and the viewer showed the previous one as current, with nothing on screen
 *  saying so.) */
export type LatestInfo = {
  newest_run_at?: string | null;
  /** Distinct detector stamps (code fingerprint + flags) among the runs shown.
   *  1 means one coherent run; 2+ means the per-paper view is mixing runs made
   *  under different code or flags, which is the stale-data signal. */
  configurations_in_view?: number;
  papers_in_view?: number;
  newest_run?: { run_uid: string; execution_uid?: string | null } | null;
  configuration?: Record<string, unknown>;
};
