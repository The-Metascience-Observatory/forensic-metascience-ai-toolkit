"use client";

import { useEffect, useRef, useState } from "react";
import { readReviewer } from "@/app/ReviewerChip";
import type { Feed, Filter, Item } from "@/lib/types/images";

// Why a whole filter's worth of candidates is a false positive. Recorded on
// the event as `bulk_reason` beside the generic `false_positive` decision --
// the decision vocabulary stays as it is, and the reason is what makes the
// labels usable as a regression fixture instead of a count.
export const BULK_REASONS = [
  ["chart_or_graph", "Charts, graphs or graphics"],
  ["channel_overlay", "Colour-channel overlay or merge"],
  ["caption_disclosed_zoom", "Overview/detail disclosed in the caption"],
  ["other", "Other (see note)"],
] as const;

/** How much of a bulk save is KNOWN to have happened when it did not finish. */
class BulkOutcome extends Error {
  constructor(readonly kind: "refused" | "partial" | "unknown", message: string, readonly saved = 0) { super(message); }
}

/** Row selection and the bulk False-positive save: one background job for
 *  the selection (or for everything the filter matches), polled for progress.
 *  Rows whose save failed stay selected so a retry is the same click. */
export function useBulkReview({ project, selection, filter, filterKey, feed, rows, load }: {
  project: string; selection: string; filter: Filter; filterKey: string; feed: Feed | null; rows: Item[]; load: () => void;
}) {
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const [bulkMessage, setBulkMessage] = useState("");
  const [bulkReason, setBulkReason] = useState<string>(BULK_REASONS[0][0]);
  const selectAll = useRef<HTMLInputElement>(null);
  const rowKey = (it: Item) => JSON.stringify([it.run_id, it.id]);
  const selectedRows = rows.filter(it => checked.has(rowKey(it)));
  const allChecked = rows.length > 0 && selectedRows.length === rows.length;
  useEffect(() => {
    if (selectAll.current) selectAll.current.indeterminate = selectedRows.length > 0 && !allChecked;
  }, [selectedRows.length, allChecked]);
  useEffect(() => { setChecked(new Set()); setBulkMessage(""); }, [filterKey, filter]);
  function toggleAll() {
    setChecked(allChecked ? new Set() : new Set(rows.map(rowKey)));
  }
  // ONE request for the whole selection. It used to be one request per row:
  // measured at ~630 ms each, so 1,944 selected rows took twenty minutes, and
  // each request re-refreshed the service projection and bumped the revision
  // the reviewer's own queue was paging through.
  //
  // The save is a background job, polled for progress. What a failure means
  // depends on what is KNOWN: a refusal the service answered before saving
  // ("saved 0") is nothing saved; a lost connection or an unknown job is an
  // unknown outcome, and the queue is reloaded to show what was saved.
  async function runBulk(payload: Record<string, unknown>, label: string) {
    const response = await fetch("/api/images/bulk", {
      method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(payload),
    }).catch(error => { throw new BulkOutcome("unknown", String(error)); });
    const started = await response.json().catch(() => ({}));
    if (!response.ok || started.error || !started.job) throw new BulkOutcome(response.ok ? "unknown" : "refused", started.error || response.statusText);
    let misses = 0;
    for (;;) {
      await new Promise(resolve => setTimeout(resolve, 400));
      let job;
      try {
        const poll = await fetch(`/api/images/bulk?job=${encodeURIComponent(started.job.id)}`);
        const body = await poll.json();
        if (!poll.ok || body.error) throw new Error(body.error || poll.statusText);
        job = body.job; misses = 0;
      } catch (error) {
        if (++misses >= 5) throw new BulkOutcome("unknown", String(error));
        continue;
      }
      const p = job.progress || {};
      if (job.state === "running") {
        setBulkMessage(p.to_save != null ? `${label}: ${(p.processed || 0).toLocaleString()} of ${p.to_save.toLocaleString()} processed, ${(p.saved || 0).toLocaleString()} saved…` : `${label}: preparing…`);
        continue;
      }
      if (job.state === "done") return job.result;
      throw new BulkOutcome((p.saved || 0) > 0 ? "partial" : "refused", job.error, p.saved || 0);
    }
  }
  function outcomeMessage(error: unknown, unchanged: string) {
    if (error instanceof BulkOutcome) {
      if (error.kind === "refused") return `Nothing was saved${unchanged}. ${error.message}`;
      if (error.kind === "partial") return `${error.saved.toLocaleString()} decisions were saved before the job stopped; the reloaded queue shows which. ${error.message}`;
    }
    return `The outcome is unknown: some decisions may have been saved; the reloaded queue shows what was. ${error instanceof Error ? error.message : String(error)}`;
  }
  async function markFalsePositive() {
    if (savingRef.current || !selectedRows.length) return;
    const reviewer = readReviewer().trim();
    if (!reviewer) { setBulkMessage("Set your name in the header before recording a decision."); return; }
    savingRef.current = true; setSaving(true);
    const targets = [...selectedRows];
    setBulkMessage(`Saving ${targets.length.toLocaleString()}…`);
    try {
      const result = await runBulk({project, decision: "false_positive", reviewer,
          items: targets.map(it => ({run: it.run_id, id: it.id}))}, "Saving");
      const failed = new Set<string>((result.failed || []).map((f: {id: string; run?: string}) => f.run ? rowKey({run_id: f.run, id: f.id} as Item) : f.id));
      // Only the rows that failed stay selected, so a retry is the same click.
      setChecked(new Set(targets.filter(it => failed.has(rowKey(it)) || failed.has(it.id)).map(rowKey)));
      setBulkMessage(`${result.saved} of ${targets.length} saved locally as False positive; `
        + "database sync runs in the background."
        + (failed.size ? ` ${failed.size} failed and remain selected. ${result.failed[0].error}` : ""));
    } catch (error) {
      setBulkMessage(outcomeMessage(error, "; the selection is unchanged"));
    }
    savingRef.current = false; setSaving(false);
    window.dispatchEvent(new Event("workbench-review"));
    load();
  }
  async function markFilterFalsePositive() {
    if (savingRef.current) return;
    const reviewer = readReviewer().trim();
    if (!reviewer) { setBulkMessage("Set your name in the header before recording a decision."); return; }
    const total = feed?.pagination?.total;
    if (!total) { setBulkMessage("Nothing matches the current filter."); return; }
    const label = BULK_REASONS.find(([value]) => value === bulkReason)?.[1] || bulkReason;
    if (!window.confirm(`Mark all ${total.toLocaleString()} items matching the current filter `
        + `as False positive (${label})? Items that already carry a decision are left alone.`)) return;
    savingRef.current = true; setSaving(true);
    setBulkMessage(`Saving ${total.toLocaleString()} decisions…`);
    try {
      const r = await runBulk({project, run: selection, component: "image_forensics", ...filter,
          decision: "false_positive", reason: bulkReason, note: label,
          reviewer, expected_total: total}, "Saving");
      setBulkMessage(`${r.saved} of ${r.matched} saved as False positive (${label}).`
        + (r.skipped_already_decided ? ` ${r.skipped_already_decided} already had a decision and were left alone.` : "")
        + (r.failed?.length ? ` ${r.failed.length} failed: ${r.failed[0].error}` : "")
        + " Database sync runs in the background.");
      setChecked(new Set());
    } catch (error) { setBulkMessage(outcomeMessage(error, "")); }
    savingRef.current = false; setSaving(false);
    window.dispatchEvent(new Event("workbench-review"));
    load();
  }
  return { checked, setChecked, rowKey, selectedRows, allChecked, selectAll, toggleAll,
    saving, bulkMessage, bulkReason, setBulkReason, markFalsePositive, markFilterFalsePositive };
}
