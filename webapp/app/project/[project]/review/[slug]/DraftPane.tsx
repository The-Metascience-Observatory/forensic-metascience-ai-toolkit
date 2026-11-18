"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { readReviewer } from "@/app/ReviewerChip";
import { MAILTO_SAFE_LENGTH, emailHtml, gmailUrl, mailtoUrl, pubpeerSearchUrl, ticked, type Recipient } from "@/lib/draftLinks";
import { errorMessage, postJson } from "@/lib/getJson";
import { jobBusy, type Draft, type DraftJob, type DraftKind, type DraftsView } from "@/lib/useDrafts";
import { CopyButton } from "./CopyButton";

const TITLE: Record<DraftKind, string> = { email: "Email to the journal and authors", pubpeer: "PubPeer comment" };
const STEP: Record<string, string> = {
  authors: "Author addresses from the paper",
  contacts: "Journal editors' addresses (web search)",
  draft: "Drafting",
};
const MARK: Record<string, string> = { pending: "·", running: "…", done: "✓", warning: "!", error: "✕" };

/** The newest draft of a kind, its job, and the start of a new one. Opening
 *  the pane with no draft and no job starts one: the button that opened it
 *  is the request. Nothing here sends or posts. */
export function DraftPane({ project, dir, kind, view, exclude, onView, onClose }: {
  project: string; dir: string; kind: DraftKind; view: DraftsView | undefined;
  /** Findings the reviewer ruled out, kept out of the draft. */
  exclude: string[];
  onView: (next: DraftsView) => void; onClose: () => void;
}) {
  const job = view?.jobs[kind] ?? null;
  const drafts = useMemo(() => (view?.drafts || []).filter((d) => d.kind === kind), [view, kind]);
  // A pick from the earlier drafts holds until another job finishes; then
  // the new draft is the one shown.
  const finished = job?.state === "done" ? job.result ?? null : null;
  const [pick, setPick] = useState<{ name: string; after: string | null } | null>(null);
  const shown = (pick && pick.after === finished ? drafts.find((d) => d.name === pick.name) : null) ?? drafts[0] ?? null;
  const [err, setErr] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const start = async () => {
    setStarting(true); setErr(null);
    try {
      onView(await postJson<DraftsView>("/api/drafts", { project, dir, kind, exclude, reviewer: readReviewer() }));
      setPick(null);
    } catch (e) { setErr(errorMessage(e)); }
    finally { setStarting(false); }
  };

  // The button that opened an empty pane asked for a draft.
  const autoStarted = useRef(false);
  useEffect(() => {
    if (!view || autoStarted.current || drafts.length || jobBusy(job) || job?.state === "error") return;
    autoStarted.current = true;
    void Promise.resolve().then(start);
    // `start` is recreated each render; the ref above runs it once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, drafts.length, job]);

  const running = jobBusy(job) || starting;
  return (
    <div className="readme-pane draft-pane" data-draft-pane={kind}>
      <header className="readme-bar">
        <strong className="draft-title">{TITLE[kind]}</strong>
        {drafts.length > 1 && (
          <select aria-label="Earlier drafts" value={shown?.name ?? ""} onChange={(e) => setPick({ name: e.target.value, after: finished })}>
            {drafts.map((d, i) => (
              <option key={d.name} value={d.name}>
                {i === 0 ? "Latest" : "Earlier"}: {d.created_at.replace("T", " ").slice(0, 16)}{d.sent ? " (sent)" : ""}
              </option>
            ))}
          </select>
        )}
        <button disabled={running} onClick={start}
                title="Make a new draft from the paper, its findings, triage note and repository README">
          {running ? "Drafting…" : drafts.length ? "Draft again" : "Draft"}
        </button>
        <span style={{ flex: 1 }} />
        <button onClick={onClose} aria-label={`Close the ${TITLE[kind]}`} title="Close and show the paper">✕</button>
      </header>
      {err && <p className="readme-msg" role="alert" style={{ color: "var(--sev-impossible)" }}>{err}</p>}
      {job && (running || job.state === "error") && <JobProgress job={job} />}
      <div className="readme-body">
        {shown ? <DraftEditor key={shown.name + (shown.edited?.at ?? "")} project={project} dir={dir} draft={shown}
                              onSaved={(d) => view && onView({ ...view, drafts: view.drafts.map((x) => (x.name === d.name ? d : x)) })} />
          : !running && <p className="muted">No draft yet.</p>}
      </div>
    </div>
  );
}

function JobProgress({ job }: { job: DraftJob }) {
  return (
    <div className="draft-job" role="status" aria-live="polite">
      <ol>
        {job.steps.map((s) => (
          <li key={s.name} className={`draft-step draft-step-${s.status}`}>
            <span aria-hidden>{MARK[s.status] || "·"}</span> {STEP[s.name] || s.name}
            {s.detail && <span className="muted">: {s.detail}</span>}
          </li>
        ))}
      </ol>
      {job.state === "error" && <p style={{ color: "var(--sev-impossible)", margin: "4px 0 0" }}>{job.error || "The job failed."}</p>}
      {job.state !== "error" && <p className="muted" style={{ margin: "4px 0 0" }}>This takes a few minutes. You can keep reviewing; the draft appears here.</p>}
    </div>
  );
}

function DraftEditor({ project, dir, draft, onSaved }: {
  project: string; dir: string; draft: Draft; onSaved: (d: Draft) => void;
}) {
  const [to, setTo] = useState<Recipient[]>(draft.to.map((c) => ({ email: c.email, selected: c.selected })));
  const [cc, setCc] = useState<Recipient[]>(draft.cc.map((c) => ({ email: c.email, selected: c.selected })));
  const [subject, setSubject] = useState(draft.subject);
  const [body, setBody] = useState(draft.body);
  const [added, setAdded] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const email = draft.kind === "email";
  const dirty = subject !== draft.subject || body !== draft.body
    || JSON.stringify(to) !== JSON.stringify(draft.to.map((c) => ({ email: c.email, selected: c.selected })))
    || JSON.stringify(cc) !== JSON.stringify(draft.cc.map((c) => ({ email: c.email, selected: c.selected })));

  const post = async (extra: Record<string, unknown>) => {
    setBusy(true); setErr(null);
    try {
      onSaved(await postJson<Draft>("/api/drafts/save", {
        project, dir, name: draft.name, reviewer: readReviewer(), to, cc, subject, body, ...extra,
      }));
    } catch (e) { setErr(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const toList = ticked(to), ccList = ticked(cc);
  const mailto = mailtoUrl(toList, ccList, subject, body);
  const toggle = (rows: Recipient[], set: (r: Recipient[]) => void, i: number) =>
    set(rows.map((r, j) => (j === i ? { ...r, selected: !r.selected } : r)));
  const addCc = () => {
    const a = added.trim().toLowerCase();
    if (!/^[^\s@,]+@[^\s@,]+\.[a-z]{2,}$/i.test(a)) { setErr(`Not an email address: ${a}`); return; }
    if (!cc.some((r) => r.email === a)) setCc([...cc, { email: a, selected: true }]);
    setAdded(""); setErr(null);
  };

  return (
    <div className="draft-editor">
      {draft.repo_url && draft.repo_visibility !== "PUBLIC" && (
        <p className="draft-note">
          The draft links the reproduction repository, which is {draft.repo_visibility === "PRIVATE" ? "still private" : "not public"}:
          recipients cannot open the link until it is. Make it public from the README pane (Make repo public…) before you send.
        </p>
      )}
      {email && (
        <fieldset className="draft-recipients">
          <legend>To: journal ({toList.length} of {to.length})</legend>
          {!draft.to.length && <p className="muted">No editor address was found. {draft.contacts_note}</p>}
          {draft.to.map((c, i) => (
            <label key={c.email} className="draft-recipient">
              <input type="checkbox" checked={to[i]?.selected ?? false} onChange={() => toggle(to, setTo, i)} />
              <span className="mono">{c.email}</span>
              <span className="muted">{c.name}{c.role ? `, ${c.role}` : ""}</span>
              <span className={`pill ${c.verified ? "pill-verified" : "pill-unverified"}`} title={c.check}>
                {c.verified ? "verified" : "unverified"}
              </span>
              {c.source_url && <a href={c.source_url} target="_blank" rel="noreferrer" title="The page the address was read from">source</a>}
            </label>
          ))}
          {draft.to.length > 0 && draft.contacts_note && <p className="muted draft-small">{draft.contacts_note}</p>}
          {toList.length > 0 && (
            <CopyButton text={toList.join(", ")} label={`Copy editor emails (${toList.length})`} done="Copied"
                        title="Copy the ticked journal addresses, comma-separated" />
          )}
        </fieldset>
      )}
      <fieldset className="draft-recipients">
        <legend>{email ? `Cc: authors (${ccList.length} of ${cc.length})` : "Author addresses, for PubPeer's \"notify authors\" field"}</legend>
        {!cc.length && <p className="muted">No author address was found in the paper.</p>}
        {cc.map((r, i) => (
          <label key={r.email} className="draft-recipient">
            <input type="checkbox" checked={r.selected} onChange={() => toggle(cc, setCc, i)} />
            <span className="mono">{r.email}</span>
            {draft.cc.find((c) => c.email === r.email)?.corresponding && <span className="muted">corresponding</span>}
          </label>
        ))}
        <span className="draft-add">
          <input value={added} onChange={(e) => setAdded(e.target.value)} placeholder="add an address"
                 aria-label="Add an address" onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addCc(); } }} />
          <button type="button" onClick={addCc} disabled={!added.trim()}>Add</button>
        </span>
        {ccList.length > 0 && <CopyButton text={ccList.join(", ")} label={email ? "Copy Cc" : "Copy addresses"} done="Copied" />}
      </fieldset>
      {email && (
        <label className="draft-field">
          Subject
          <input value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Subject" />
        </label>
      )}
      <label className="draft-field">
        {email ? "Body" : "Comment"}
        <textarea className="readme-edit draft-body" value={body} onChange={(e) => setBody(e.target.value)}
                  aria-label={email ? "Email body" : "PubPeer comment"} spellCheck />
      </label>
      <p className="muted draft-small">{body.trim().split(/\s+/).filter(Boolean).length} words · drafted by {draft.model}
        {draft.who ? ` for ${draft.who}` : ""} on {draft.created_at.slice(0, 10)}
        {draft.edited ? ` · edited by ${draft.edited.by}` : ""}</p>
      {err && <p role="alert" style={{ color: "var(--sev-impossible)" }}>{err}</p>}
      <div className="draft-actions">
        <button className={dirty ? "primary" : undefined} disabled={!dirty || busy} onClick={() => post({})}>
          {busy ? "Saving…" : "Save"}
        </button>
        {email ? (
          <>
            <a className="button-link" href={gmailUrl(toList, ccList, subject, body)} target="_blank" rel="noreferrer"
               title="Open Gmail's compose window with this email filled in. You send it.">Open in Gmail</a>
            <a className="button-link" href={mailto}
               title={mailto.length > MAILTO_SAFE_LENGTH ? "This email is long: some mail programs cut it. Copy the body if it arrives short." : "Open your mail program with this email filled in. You send it."}>
              Open in mail app
            </a>
            <CopyFormatted html={emailHtml(body, draft.citation, draft.footer)} text={body} />
            <CopyButton text={subject} label="Copy subject" />
            <CopyButton text={body} label="Copy body" />
          </>
        ) : (
          <>
            <CopyButton text={body} label="Copy comment" />
            {draft.paper.doi && (
              <a className="button-link" href={pubpeerSearchUrl(draft.paper.doi)} target="_blank" rel="noreferrer"
                 title="Open the article on PubPeer. You paste and post the comment.">Open on PubPeer</a>
            )}
          </>
        )}
        <label className="draft-sent" title={email ? "Record that you sent this email" : "Record that you posted this comment"}>
          <input type="checkbox" checked={!!draft.sent} disabled={busy}
                 onChange={(e) => post({ sent: e.target.checked })} />
          {email ? "Sent" : "Posted"}
          {draft.sent && <span className="muted"> by {draft.sent.by} on {draft.sent.at.slice(0, 10)}</span>}
        </label>
      </div>
    </div>
  );
}

/** Copies the body as formatted HTML (with a plain-text twin), so a paste
 *  into Gmail keeps the linked title, italic journal, bold volume and code
 *  block. A "mailto:" or Gmail link can only carry plain text. */
function CopyFormatted({ html, text }: { html: string; text: string }) {
  const [ok, setOk] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.write([new ClipboardItem({
        "text/html": new Blob([html], { type: "text/html" }),
        "text/plain": new Blob([text], { type: "text/plain" }),
      })]);
    } catch {
      // No async clipboard (plain http, an older browser): select a rendered
      // copy and copy that, which keeps its formatting.
      const div = document.createElement("div");
      div.innerHTML = html;
      Object.assign(div.style, { position: "fixed", left: "-9999px" });
      document.body.appendChild(div);
      const range = document.createRange();
      range.selectNodeContents(div);
      const sel = window.getSelection();
      sel?.removeAllRanges(); sel?.addRange(range);
      document.execCommand("copy");
      sel?.removeAllRanges(); div.remove();
    }
    setOk(true);
    window.setTimeout(() => setOk(false), 1200);
  };
  return (
    <button type="button" onClick={copy} className="primary"
            title="Copy the body with its formatting (linked title, italic journal, bold volume) to paste into Gmail or your mail program">
      {ok ? "Copied" : "Copy formatted email"}
    </button>
  );
}
