"use client";

import { useEffect, useState } from "react";

import { readReviewer } from "@/app/ReviewerChip";
import { errorMessage, postJson } from "@/lib/getJson";
import { useMe } from "@/lib/useMe";
import type { RepoView } from "@/lib/useRepo";
import { Markdown } from "./Markdown";
import { VisibilityPill, repoNotes } from "./RepoSummary";

type Busy = null | "save" | "push" | "publish";

/** The reproduction repo's README beside the findings: rendered, editable,
 *  and from here committed, pushed and (by an admin) made public.
 *
 *  Save only writes the file. "Commit and push" is a separate step, and
 *  "Make repo public" another, each refused by the server unless the one
 *  before it is done. */
export function ReadmePane({ project, dir, info, onInfo, onReload, onClose }: {
  project: string; dir: string; info: RepoView;
  onInfo: (next: RepoView) => void; onReload: () => void; onClose: () => void;
}) {
  const { isAdmin } = useMe();
  // `base` is the README as this pane last took it from the server; a save
  // names its hash, so a save over someone else's newer text is refused.
  const [base, setBase] = useState({ text: info.readme ?? "", sha256: info.sha256 });
  const [draft, setDraft] = useState(base.text);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<Busy>(null);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [typed, setTyped] = useState("");
  const dirty = draft !== base.text;

  // The file changed under us (a save, a reload, another paper): take the
  // new text unless there is an unsaved edit to protect.
  useEffect(() => {
    if (info.sha256 === base.sha256 || dirty) return;
    setBase({ text: info.readme ?? "", sha256: info.sha256 });
    setDraft(info.readme ?? "");
  }, [info.sha256, info.readme, base.sha256, dirty]);

  const repo = info.repo;
  if (!repo) return null;
  const isPrivate = repo.visibility === "PRIVATE";
  const toPush = repo.readmeDirty || !!repo.ahead;
  const mayPush = isPrivate || isAdmin;
  const clean = !dirty && !repo.readmeDirty && !repo.otherDirty.length && !repo.ahead;

  const call = async (what: Exclude<Busy, null>, url: string, body: Record<string, unknown>, ok: string) => {
    setBusy(what); setErr(null); setDone(null);
    try {
      const next = await postJson<RepoView>(url, { project, dir, reviewer: readReviewer(), ...body });
      if (what === "save") { setBase({ text: next.readme ?? "", sha256: next.sha256 }); setDraft(next.readme ?? ""); }
      onInfo(next);
      setDone(ok);
      return true;
    } catch (e) { setErr(errorMessage(e)); return false; }
    finally { setBusy(null); }
  };
  const save = () => call("save", "/api/repo/readme", { content: draft, base_sha256: base.sha256 }, "Saved to the repository folder. Not committed yet.");
  const push = () => call("push", "/api/repo/push", {}, "Committed and pushed to GitHub.");
  const publish = async () => {
    if (await call("publish", "/api/repo/publish", { confirm: typed }, "The repository is now public.")) {
      setConfirming(false); setTyped("");
    }
  };
  const reload = () => { setDraft(base.text); setErr(null); onReload(); };
  const close = () => {
    if (dirty && !window.confirm("Close the README and lose your unsaved edit?")) return;
    setDraft(base.text); onClose();
  };
  const notes = repoNotes(repo);

  return (
    <div className="readme-pane" data-readme-pane>
      <header className="readme-bar">
        <div className="seg" role="group" aria-label="README view">
          <button className={!editing ? "primary" : undefined} aria-pressed={!editing} onClick={() => setEditing(false)}>
            {dirty ? "Preview" : "Rendered"}
          </button>
          <button className={editing ? "primary" : undefined} aria-pressed={editing} onClick={() => setEditing(true)}>Edit</button>
        </div>
        <button className={dirty ? "primary" : undefined} disabled={!dirty || busy !== null} onClick={save}
                title="Write README.md in the repository folder. Does not commit or push.">
          {busy === "save" ? "Saving…" : "Save"}
        </button>
        <button disabled={dirty || !toPush || !mayPush || busy !== null || !repo.inOrg} onClick={push}
                title={dirty ? "Save your edit first"
                  : !repo.inOrg ? "This repository has no remote in the reproductions organisation"
                  : !mayPush ? "The repository is public, so only an admin may push to it"
                  : !toPush ? "Nothing to commit or push"
                  : isPrivate ? "Commit README.md and push it to the private GitHub repository"
                  : "Commit README.md and push it. The repository is public, so this publishes the edit."}>
          {busy === "push" ? "Pushing…" : "Commit and push"}
        </button>
        {isAdmin && isPrivate && (
          <button disabled={!clean || busy !== null} onClick={() => { setConfirming(true); setErr(null); setDone(null); }}
                  title={clean ? "Make the GitHub repository visible to everyone" : "Save, commit and push everything first"}>
            Make repo public…
          </button>
        )}
        <span className="readme-state">
          <VisibilityPill repo={repo} />
          {dirty && <span className="repo-notes">unsaved edit</span>}
          {!dirty && notes.length > 0 && <span className="repo-notes">{notes.join(" · ")}</span>}
        </span>
        <button onClick={close} aria-label="Close the README" title="Close the README and show the paper">✕</button>
      </header>
      {err && (
        <p className="readme-msg" role="alert" style={{ color: "var(--sev-impossible)" }}>
          {err}{" "}
          {/changed on disk/.test(err) && <button onClick={reload}>Reload the README</button>}
        </p>
      )}
      {done && !err && <p className="readme-msg muted" role="status">{done}</p>}
      {editing
        ? <textarea className="readme-edit" value={draft} spellCheck onChange={(e) => { setDraft(e.target.value); setDone(null); }}
                    aria-label="README.md source" />
        : <div className="readme-body"><Markdown>{draft}</Markdown></div>}

      {confirming && (
        <div className="readme-confirm" role="dialog" aria-modal="true" aria-label="Make repository public"
             onClick={(e) => { if (e.target === e.currentTarget && busy === null) setConfirming(false); }}>
          <div className="readme-confirm-box">
            <h3>Make this repository public?</h3>
            <p>
              <a href={repo.url} target="_blank" rel="noreferrer">{repo.name}</a> and its whole commit history will be
              visible to everyone on GitHub. GitHub can make it private again, but copies made in the meantime stay out.
            </p>
            {info.embargoed && (
              <p style={{ color: "var(--sev-highly)" }}>
                An EMBARGO.json covers this paper&apos;s folder: the corpus is marked as not to be published from.
              </p>
            )}
            <label>
              Type the repository&apos;s name to confirm:
              <input value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus spellCheck={false}
                     placeholder={repo.name} aria-label="Repository name" />
            </label>
            {err && <p role="alert" style={{ color: "var(--sev-impossible)" }}>{err}</p>}
            <div className="readme-confirm-actions">
              <button onClick={() => setConfirming(false)} disabled={busy !== null}>Cancel</button>
              <button className="primary" disabled={typed.trim() !== repo.name || busy !== null} onClick={publish}>
                {busy === "publish" ? "Making public…" : "Make public"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
