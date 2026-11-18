"use client";


import type { RepoView } from "@/lib/useRepo";
import { Markdown } from "./Markdown";

/** What the repository's state adds up to, in the reader's words. */
export function repoNotes(repo: NonNullable<RepoView["repo"]>): string[] {
  const notes: string[] = [];
  if (!repo.hasRemote) notes.push("not on GitHub yet");
  else if (!repo.inOrg) notes.push("remote is outside the reproductions organisation");
  if (repo.readmeDirty) notes.push("README saved, not committed");
  if (repo.otherDirty.length) notes.push(`${repo.otherDirty.length} other uncommitted file${repo.otherDirty.length === 1 ? "" : "s"}`);
  if (repo.ahead) notes.push(`${repo.ahead} commit${repo.ahead === 1 ? "" : "s"} not pushed`);
  return notes;
}

export function VisibilityPill({ repo }: { repo: NonNullable<RepoView["repo"]> }) {
  if (!repo.hasRemote) return <span className="pill" data-visibility="local">Local only</span>;
  const v = repo.visibility;
  return (
    <span className={`pill${v === "PUBLIC" ? " pill-public" : ""}`} data-visibility={v}
          title={v === "unknown" ? "GitHub did not answer, so the visibility is not known" : undefined}>
      {v === "PUBLIC" ? "Public" : v === "PRIVATE" ? "Private" : v === "INTERNAL" ? "Internal" : "Visibility unknown"}
    </span>
  );
}

/** Above the findings list: the summary the reproduction repo's README opens
 *  with, or the triage note for a paper that has no repo (or no summary). */
export function RepoSummary({ info, readmeOpen, onReadme }: {
  info: RepoView | undefined; readmeOpen: boolean; onReadme: () => void;
}) {
  if (!info) return null;
  const { repo } = info;
  const fromReadme = !!info.summary_md;
  const text = info.summary_md || info.triage_md;
  if (!repo && !text) return null;
  const notes = repo ? repoNotes(repo) : [];
  return (
    <section className="repo-summary" data-repo-summary={fromReadme ? "readme" : text ? "triage" : "none"}>
      {repo && (
        <div className="repo-actions">
          <button className="repo-readme-button" onClick={onReadme} aria-pressed={readmeOpen} disabled={info.readme === null}
                  title={info.readme === null ? "This repository has no README.md" : "Read or edit the repository's README beside the findings"}>
            {readmeOpen ? "Hide README.md" : "View and edit README.md"}
          </button>
          <div className="repo-actions-row">
            {repo.url
              ? <a className="button-link" href={repo.url} target="_blank" rel="noreferrer" title={repo.name}>View Repo on GitHub</a>
              : <button disabled title="This repository has not been pushed to GitHub yet">View Repo on GitHub</button>}
            <VisibilityPill repo={repo} />
            {notes.length > 0 && <span className="repo-notes">{notes.join(" · ")}</span>}
          </div>
        </div>
      )}
      {/* Open on every paper; closing it lasts until the next paper. */}
      <details open>
        <summary>
          <strong>{fromReadme ? "Summary" : text ? "Triage note" : "Reproduction repo"}</strong>
          {!fromReadme && text && repo && <span className="muted"> (the README has no Summary section)</span>}
          {!repo && <span className="muted"> (no reproduction repo)</span>}
        </summary>
        {text && <Markdown>{text}</Markdown>}
      </details>
    </section>
  );
}
