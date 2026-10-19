"use client";

import { useEffect, useState, type MouseEvent } from "react";

import { displayName, legacyToNine, sev9Color, sev9Label } from "@/lib/constants.gen";
import { SEV_COLOR } from "@/lib/severity";
import { highlightJumps, passageKey, STEPPER_AT, type Target } from "@/lib/targets";

/** How the tool tag was established (`review_issues.finding_tool`). Only the
 *  first two mean a recorded tool run backs the row; a technique label is the
 *  analyst naming a tool it did not (recordably) call, and is drawn dashed. */
const TOOL_SOURCE_TITLE: Record<string, string> = {
  tool_verdict: "Triggered by this tool: its validated verdict is joined to the finding.",
  tool_call: "Triggered by this tool: the recorded call behind the finding.",
  technique: "Labelled with this tool's technique, but no recorded call of it backs the finding.",
  model_judgement: "No tool backs this finding: the analyst's own reading.",
  component: "Found by this detector.",
  not_recorded: "Not recorded in this cached summary yet; it fills in on the next sync.",
};

function ToolBadge({ tool, source }: { tool?: string | null; source?: string }) {
  if (!source) return null;
  const backed = source === "tool_verdict" || source === "tool_call" || source === "component";
  return (
    <span className="pill" data-tool-badge={source}
          title={TOOL_SOURCE_TITLE[source] || undefined}
          style={{
            fontFamily: backed || source === "technique" ? "monospace" : undefined,
            borderStyle: source === "technique" ? "dashed" : undefined,
            color: backed ? undefined : "var(--muted)",
          }}>
      {source === "not_recorded" ? "tool not recorded" : displayName(tool)}
    </span>
  );
}

function CopyQuote({ text }: { text: string }) {
  const [ok, setOk] = useState(false);
  async function copy(e: MouseEvent) {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    setOk(true);
    window.setTimeout(() => setOk(false), 1200);
  }
  return (
    <button type="button" onClick={copy} style={{ fontSize: 11, marginTop: 6 }}
            title="Copy this quote for a PubPeer comment">
      {ok ? "Copied" : "Copy quote"}
    </button>
  );
}

const NUMERIC_COLS = [
  [
    ["correct_minor", "Correct — minor issue"],
    ["correct_significant", "Correct — significant issue"],
  ],
  [
    ["false_positive", "False positive"],
  ],
] as const;

const IMAGE_COLS = [
  [
    ["true_issue", "True issue"],
    ["unsure", "Unsure"],
  ],
  [
    ["false_positive", "False positive"],
    ["false_positive_same_condition", "FP — same condition"],
    ["false_positive_other", "FP — other"],
    ["false_positive_chart", "FP — chart / label"],
    ["false_positive_overlay", "FP — channel overlay"],
    ["false_positive_supplement", "FP — own supplement"],
    ["false_positive_magnification", "FP — magnification"],
    ["false_positive_scale_bar", "False positive: scale bar"],
    ["false_positive_channels", "False positive: different channels"],
    ["false_positive_logo", "False positive: logo"],
  ],
] as const;

const HIDE_KEY = "metascience.hideBelowSev";

function sevNine(iss: any): number | null {
  if (typeof iss.severity_9 === "number") return iss.severity_9;
  return legacyToNine(iss.severity);
}

/** Live workbench `paper()` sends `{kind:'database', status, detail}`.
 *  The nested `database.state` shape is the older disk-era payload. */
export interface IssueSource {
  kind?: string;
  status?: string;
  detail?: string | null;
  execution_id?: string | null;
  database?: {
    state: "hit" | "miss" | "unavailable" | null;
    detail: string | null;
    runs?: { label: string; corpus: string | null; name: string | null;
            matched_by: "dir" | "doi" | null; analysed_at: string | null;
            pipeline_version: string | null; verdict: string | null;
            paper_severity: number | null; n_findings: number }[];
  } | null;
}

function emptyMessage(source?: IssueSource | null): string {
  if (source?.detail) return source.detail;
  const db = source?.database;
  if (source?.kind === "database" && !db?.state) {
    return "No reviewable issues in the synchronized catalog for this selection.";
  }
  const lead = "No reviewable issues on disk";
  if (!db || !db.state) {
    return `${lead}, and the findings database was not consulted.`;
  }
  if (db.state === "unavailable") {
    return `${lead}, and the findings database could not be reached` +
      ` (${db.detail || "no detail"}). Findings pushed from another machine` +
      " may exist there.";
  }
  if (db.state === "miss") {
    return `${lead}, and the findings database has no run for this paper.`;
  }
  return `${lead}; the findings database has a run but every row is` +
    " image/text-track or non-problem.";
}

/** One group's header: tool, place, count, worst severity. Click to open. */
function GroupHeader({ group, open, onOpen }: {
  group: any; open: boolean; onOpen: () => void;
}) {
  return (
    <div data-group-header={group.id} onClick={onOpen}
         style={{
           display: "flex", gap: 6, alignItems: "baseline", cursor: "pointer",
           border: "1px solid var(--line)", borderRadius: 4, padding: "6px 8px",
           marginBottom: open ? 4 : 8, background: "var(--panel)",
           borderLeft: `3px solid ${typeof group.severity_9 === "number"
             ? sev9Color(group.severity_9) : "var(--line)"}`,
         }}>
      <span className="muted" style={{ fontSize: 11 }}>{open ? "▾" : "▸"}</span>
      <strong style={{ flex: 1, fontSize: 13 }}>
        {group.n} {group.tool === group.family && group.tool !== undefined
          ? `${displayName(group.family)}-family` : displayName(group.tool)} findings · {group.unit}
      </strong>
      <span className="pill" style={{ fontFamily: "monospace" }}>{displayName(group.tool)}</span>
      {typeof group.severity_9 === "number" && (
        <span className="pill" style={{ color: sev9Color(group.severity_9) }}
              title="the worst severity in this group">
          {sev9Label(group.severity_9)}{group.provisional ? "*" : ""}
        </span>
      )}
    </div>
  );
}

/** One place at a time, for a finding with more places than buttons fit. */
function Stepper({ jumps, focusKey, onJump }: {
  jumps: { label: string; target: Target }[];
  focusKey: string | null;
  onJump?: (t: Target) => void;
}) {
  const k = Math.max(0, jumps.findIndex((j) => passageKey(j.target) === focusKey));
  const go = (d: number) => onJump?.(jumps[(k + d + jumps.length) % jumps.length].target);
  const t = jumps[k]?.target;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8, fontSize: 11 }}
         onClick={(e) => e.stopPropagation()} data-cell-stepper>
      <button type="button" onClick={() => go(-1)} style={{ fontSize: 11 }}>‹</button>
      <span>{k + 1} of {jumps.length}</span>
      <button type="button" onClick={() => go(1)} style={{ fontSize: 11 }}>›</button>
      {t?.label && <span className="muted mono">{t.label}</span>}
    </div>
  );
}

export function IssueList({ issues, at, review, onFocus, onSave, locById, onJump,
  focusTargetId, preferredSurface, source, grouped, onGrouped }: {
  issues: any[];
  at: number;
  review: any;
  onFocus: (i: number) => void;
  onSave: (patch: Record<string, unknown>) => void;
  locById?: Map<string, { targets?: Target[] }>;
  onJump?: (t: Target) => void;
  focusTargetId?: string | null;
  preferredSurface?: "pdf" | "xml" | "sheet" | null;
  source?: IssueSource | null;
  /** Group Findings (server-side groups; see lib/findingGroups.ts). */
  grouped?: boolean;
  onGrouped?: (on: boolean) => void;
}) {
  const [hideBelow, setHideBelow] = useState(0);
  const [opened, setOpened] = useState<Set<string>>(new Set());
  useEffect(() => {
    try {
      const n = Number(window.localStorage.getItem(HIDE_KEY));
      if (Number.isFinite(n) && n >= 0 && n <= 9) setHideBelow(n);
    } catch { /* storage may be unavailable */ }
  }, []);
  const setHide = (n: number) => {
    setHideBelow(n);
    try { window.localStorage.setItem(HIDE_KEY, String(n)); } catch { /* ok */ }
  };
  if (!issues.length) {
    return (
      <p className="muted">
        {emptyMessage(source)} That is not a clean paper — nothing was
        recorded to review.
      </p>
    );
  }
  // A row hides only when its severity is KNOWN and below the bar; a row
  // with no ladder value never hides (absence is not "low"), and the row
  // the keyboard is on always shows so arrow-walking cannot vanish.
  const entries = issues.map((iss, i) => ({ iss, i }));
  const isHidden = (iss: any, i: number) => {
    if (!hideBelow || i === at) return false;
    const n = sevNine(iss);
    return typeof n === "number" && n < hideBelow;
  };
  // A group is open when the reader opened it or is on one of its findings.
  const atGroup = issues[at]?.group?.id as string | undefined;
  const isOpen = (gid: string) => gid === atGroup || opened.has(gid);
  const toggleGroup = (gid: string, firstIndex: number) => {
    if (isOpen(gid) && gid !== atGroup) {
      setOpened((s) => { const n = new Set(s); n.delete(gid); return n; });
    } else {
      setOpened((s) => new Set(s).add(gid));
      onFocus(firstIndex);
    }
  };
  const visible = entries.filter(({ iss, i }) => !isHidden(iss, i));
  const nHidden = entries.length - visible.length;
  const headed = new Set<string>();
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 8,
                    marginBottom: 8, fontSize: 11 }}
           className="muted">
        <label>
          Hide below{" "}
          <select value={hideBelow}
                  onChange={(e) => setHide(Number(e.target.value))}
                  style={{ fontSize: 11 }}>
            <option value={0}>off</option>
            {[2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>S{n}</option>
            ))}
          </select>
        </label>
        {onGrouped && (
          <label title="One row per tool and table (or page range); open a group to review its findings one by one">
            <input type="checkbox" checked={!!grouped}
                   onChange={(e) => onGrouped(e.target.checked)}
                   data-group-toggle />{" "}
            Group findings
          </label>
        )}
        {nHidden > 0 && (
          <span>
            {nHidden} finding{nHidden === 1 ? "" : "s"} below S{hideBelow} hidden
            {" — "}
            <button type="button" style={{ fontSize: 11 }}
                    onClick={() => setHide(0)}>show all</button>
          </span>
        )}
      </div>
      {visible.map(({ iss, i }) => {
        const gid = iss.group?.id as string | undefined;
        // At the group's first VISIBLE finding: "Hide below" may hide its first.
        const firstShown = !!gid && !headed.has(gid);
        if (gid) headed.add(gid);
        const header = gid && firstShown ? (
          <GroupHeader key={`h-${gid}`} group={iss.group} open={isOpen(gid)}
                       onOpen={() => toggleGroup(gid, i)} />
        ) : null;
        if (gid && !isOpen(gid)) return header;
        const saved = review?.issues?.[iss.id] || {};
        const focused = i === at;
        const decisionCols = iss.kind === "image" ? IMAGE_COLS : NUMERIC_COLS;
        const jumps = focused && onJump
          ? highlightJumps(locById?.get(iss.id)?.targets, preferredSurface)
          : [];
        // The FOCUSED TARGET's passage. Derived from the id alone it was the
        // finding id for every persisted anchor (`<fid>:<passage>:<surface>`),
        // so no button ever showed as current.
        const focusTarget = focusTargetId
          ? (locById?.get(iss.id)?.targets || []).find((t) => t.id === focusTargetId)
          : undefined;
        const focusKey = focusTarget ? passageKey(focusTarget)
          : focusTargetId ? passageKey({ id: focusTargetId }) : null;
        return (
          <div key={iss.id} style={gid ? { marginLeft: 12 } : undefined}>
          {header}
          <article
            onClick={() => onFocus(i)}
            style={{
              border: `1px solid ${focused ? "var(--accent)" : "var(--line)"}`,
              borderLeft: `3px solid ${
                typeof iss.severity_9 === "number"
                  ? sev9Color(iss.severity_9)
                  : SEV_COLOR[iss.severity] || "var(--line)"}`,
              borderRadius: 4, padding: 8, marginBottom: 8,
              background: focused ? "var(--focus)" : "transparent",
              cursor: "pointer",
              opacity: iss.adjudication_action === "discarded" ? 0.65 : 1,
            }}
          >
            <div style={{ display: "flex", gap: 6, alignItems: "baseline" }}>
              <span className="muted" style={{ fontSize: 11 }}>{iss.priority}.</span>
              <strong style={{ flex: 1, fontSize: 13 }}>{iss.title}</strong>
              <ToolBadge tool={iss.tool} source={iss.tool_source} />
              {iss.adjudication_action === "discarded" && (
                <span className="pill" title={iss.adjudication_rationale || undefined}
                      style={{ color: "var(--muted)" }}>discarded</span>
              )}
              {typeof iss.severity_9 === "number" ? (
                <span className="pill"
                      title={iss.severity_is_provisional
                        ? "provisional — the adjudicator did not rank this row"
                        : undefined}
                      style={{ color: sev9Color(iss.severity_9) }}>
                  {sev9Label(iss.severity_9)}
                  {iss.severity_is_provisional ? "*" : ""}
                </span>
              ) : legacyToNine(iss.severity) !== null ? (
                <span className="pill"
                      title="mapped from a legacy 5-level run — not an assigned 1–9"
                      style={{ color: SEV_COLOR[iss.severity] || "var(--muted)" }}>
                  {sev9Label(legacyToNine(iss.severity) as number)} (legacy)
                </span>
              ) : (
                <span className="pill" style={{
                  color: SEV_COLOR[iss.severity] || "var(--muted)",
                }}>{(iss.severity || iss.kind || "").replace(/_/g, " ")}</span>
              )}
            </div>
            {iss.kind === "image" && iss.location && (
              <p style={{ margin: "8px 0 0", fontSize: 14, fontWeight: 600 }}>
                {iss.location}
              </p>
            )}
            {focused && iss.kind === "image" && Array.isArray(iss.extras?.pages)
              && iss.extras.pages.length > 0 && onJump && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}
                   onClick={(e) => e.stopPropagation()}>
                {iss.extras.pages.map((p: number) => {
                  const loc = locById?.get(iss.id);
                  const t = (loc?.targets || []).find(
                    (x: Target) => x.page === p && x.kind === "pdf_bbox",
                  );
                  if (!t) {
                    return (
                      <span key={p} className="pill" style={{ fontSize: 11 }}>
                        p. {p}
                      </span>
                    );
                  }
                  return (
                    <button key={p} type="button"
                            className={t.id === focusTargetId ? "primary" : undefined}
                            onClick={() => onJump(t)}
                            style={{ fontSize: 11 }}>
                      Open p. {p}
                    </button>
                  );
                })}
              </div>
            )}
            {iss.plain && (
              <p style={{ margin: "6px 0 0", fontSize: 13 }}>{iss.plain}</p>
            )}
            {Array.isArray(iss.artefacts) && iss.artefacts[0] && (
              <p className="muted" style={{ fontSize: 11, margin: "4px 0 0" }}>
                <span className="pill">{iss.artefacts[0].kind || "file"}</span>
                {" "}
                <span className="mono">{iss.artefacts[0].basename}</span>
                {iss.artefacts[0].sheet ? ` · ${iss.artefacts[0].sheet}` : ""}
                {iss.artefacts[0].found === false
                  ? " · file not in this folder"
                  : ""}
                {iss.artefacts[0].confidence === "file"
                  ? " · cells not recorded"
                  : ""}
                {iss.artefacts[0].confidence === "cells"
                  && Array.isArray(iss.artefacts[0].cells)
                  ? ` · ${iss.artefacts[0].cells.length} cell(s)`
                  : ""}
              </p>
            )}
            {iss.quote && focused && (
              <div onClick={(e) => e.stopPropagation()}>
                <blockquote style={{
                  margin: "6px 0 0", padding: "4px 8px",
                  borderLeft: "2px solid var(--line)", color: "var(--muted)",
                  fontSize: 12,
                }}>“{iss.quote}”</blockquote>
                <CopyQuote text={iss.quote} />
              </div>
            )}
            {jumps.length > STEPPER_AT && (
              <Stepper jumps={jumps} focusKey={focusKey} onJump={onJump} />
            )}
            {jumps.length >= 2 && jumps.length <= STEPPER_AT && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}
                   onClick={(e) => e.stopPropagation()}>
                {jumps.map((j) => (
                  <button key={j.target.id} type="button"
                          className={passageKey(j.target) === focusKey ? "primary" : undefined}
                          onClick={() => onJump?.(j.target)}
                          style={{ fontSize: 11 }}>
                    {j.label}
                  </button>
                ))}
              </div>
            )}
            {focused && (
              <div className="finding-flags" onClick={(e) => e.stopPropagation()}>
                {decisionCols.map((col, ci) => (
                  <div className="finding-flags-col" key={ci}>
                    {col.map(([key, label]) => (
                      <label key={key}>
                        <input
                          type="checkbox"
                          checked={saved.decision === key}
                          onChange={(e) => onSave({
                            issue_id: iss.id,
                            decision: e.target.checked ? key : null,
                          })}
                        />
                        {label}
                      </label>
                    ))}
                  </div>
                ))}
                <div className="finding-flags-col">
                  <label>
                    <input type="checkbox"
                      checked={!!saved.submitted_to_pubpeer}
                      onChange={(e) => onSave({
                        issue_id: iss.id,
                        submitted_to_pubpeer: e.target.checked,
                      })} />
                    submitted to PubPeer
                  </label>
                  {saved.pubpeer_url && (
                    <a href={saved.pubpeer_url} target="_blank" rel="noreferrer"
                       style={{ fontSize: 11 }}>
                      View on PubPeer
                    </a>
                  )}
                  <label>
                    <input type="checkbox"
                      checked={!!saved.submitted_to_editor}
                      onChange={(e) => onSave({
                        issue_id: iss.id,
                        submitted_to_editor: e.target.checked,
                      })} />
                    submitted to editor
                  </label>
                </div>
              </div>
            )}
            {focused && saved.decision === "correct" && (
              <p className="muted" style={{ fontSize: 11, margin: "4px 0 0" }}>
                labelled Correct before the minor/significant split — pick one
              </p>
            )}
          </article>
          </div>
        );
      })}
    </div>
  );
}
