"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { readReviewer } from "@/app/ReviewerChip";
import { errorMessage, postJson } from "@/lib/getJson";
import { useMe } from "@/lib/useMe";
import type { RepoView } from "@/lib/useRepo";
import { Markdown } from "./Markdown";
import { VisibilityPill, repoNotes } from "./RepoSummary";

type Busy = null | "save" | "push" | "publish";
/** Reading it as GitHub shows it, or editing it one of two ways. */
type Mode = "view" | "rich" | "markdown";

// The rich-text editor is large and only needed once someone edits.
const RichEditor = dynamic(() => import("./RichEditor"), {
  ssr: false, loading: () => <div className="readme-body muted">Loading the editor…</div>,
});

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
  const [mode, setMode] = useState<Mode>("view");
  /** Bumped when the text is replaced from outside the rich-text editor
   *  (typed in Markdown mode, reloaded), so that editor reopens on it. */
  const [richKey, setRichKey] = useState(0);
  const [busy, setBusy] = useState<Busy>(null);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const dirty = draft !== base.text;

  // The file changed under us (a save, a reload, another paper): take the
  // new text unless there is an unsaved edit to protect.
  useEffect(() => {
    if (info.sha256 === base.sha256 || dirty) return;
    setBase({ text: info.readme ?? "", sha256: info.sha256 });
    setDraft(info.readme ?? "");
    setRichKey((k) => k + 1);
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
  // One click, no dialog (Dan, 2026-11-17); the server still checks the name.
  // No message afterwards: the badge turns to "Public".
  const publish = () => call("publish", "/api/repo/publish", { confirm: repo?.name }, "");
  const reload = () => { setDraft(base.text); setRichKey((k) => k + 1); setErr(null); onReload(); };
  const close = () => {
    if (dirty && !window.confirm("Close the README and lose your unsaved edit?")) return;
    setDraft(base.text); setRichKey((k) => k + 1); onClose();
  };
  const notes = repoNotes(repo);

  return (
    <div className="readme-pane" data-readme-pane>
      <header className="readme-bar">
        <div className="seg" role="group" aria-label="README view">
          <button className={mode === "view" ? "primary" : undefined} aria-pressed={mode === "view"} onClick={() => setMode("view")}
                  title="The README as GitHub shows it">
            {dirty ? "Preview" : "View"}
          </button>
          <button className={mode === "rich" ? "primary" : undefined} aria-pressed={mode === "rich"} onClick={() => setMode("rich")}
                  title="Edit the formatted text. Only the paragraphs you change are rewritten in the file.">
            Edit rich text
          </button>
          <button className={mode === "markdown" ? "primary" : undefined} aria-pressed={mode === "markdown"} onClick={() => setMode("markdown")}
                  title="Edit the markdown source">
            Edit markdown
          </button>
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
          <button disabled={!clean || busy !== null} onClick={publish}
                  title={clean ? "Make the GitHub repository visible to everyone" : "Save, commit and push everything first"}>
            {busy === "publish" ? "Making public…" : "Make repo public"}
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
      {mode === "markdown" && (
        <textarea className="readme-edit" value={draft} spellCheck aria-label="README.md source"
                  onChange={(e) => { setDraft(e.target.value); setRichKey((k) => k + 1); setDone(null); }} />
      )}
      {mode === "rich" && <RichEditor key={richKey} value={draft} onChange={(md) => { setDraft(md); setDone(null); }} />}
      {mode === "view" && <div className="readme-body"><Markdown>{draft}</Markdown></div>}

    </div>
  );
}
