import "server-only";

import fsp from "node:fs/promises";
import path from "node:path";

import { readmeSummary, triageNote } from "./readmeSummary.ts";
import {
  TRIAGE_NOTE, embargoMarker, findRepo, readReadme, repoState, visibility,
  type RepoState, type Run, type Visibility,
} from "./reproRepo.ts";
import { paperAbsDir } from "./store.ts";

/** What the review page shows about a paper's reproduction repository. */
export interface RepoInfo {
  repo: (RepoState & { visibility: Visibility }) | null;
  /** The README's text, and the hash a save must name. */
  readme: string | null;
  sha256: string | null;
  /** The README's Summary bullets (markdown), `""` when it has none. */
  summary_md: string;
  /** The triage note, shown when there is no summary. */
  triage_md: string;
  /** An EMBARGO.json covers this paper folder. */
  embargoed: boolean;
}

export async function paperRepo(project: string, dir: string): Promise<{ paperAbs: string; repoAbs: string | null }> {
  const paperAbs = await paperAbsDir(project, dir);
  return { paperAbs, repoAbs: await findRepo(paperAbs) };
}

/** As `paperRepo`, for a write: the paper must have a repository. */
export async function requireRepo(project: string, dir: string): Promise<{ paperAbs: string; repoAbs: string }> {
  const found = await paperRepo(project, dir);
  if (!found.repoAbs) throw new Error("This paper has no reproduction repository");
  return { paperAbs: found.paperAbs, repoAbs: found.repoAbs };
}

export async function repoInfo(paperAbs: string, repoAbs: string | null, run?: Run): Promise<RepoInfo> {
  const triage = await fsp.readFile(path.join(paperAbs, TRIAGE_NOTE), "utf8").catch(() => "");
  const info: RepoInfo = {
    repo: null, readme: null, sha256: null, summary_md: "",
    triage_md: triageNote(triage), embargoed: !!embargoMarker(paperAbs),
  };
  if (!repoAbs) return info;
  const [state, readme] = await Promise.all([repoState(repoAbs, run), readReadme(repoAbs)]);
  const vis: Visibility = state.inOrg ? await visibility(state.name, run) : "unknown";
  info.repo = { ...state, visibility: vis };
  if (readme) {
    info.readme = readme.text;
    info.sha256 = readme.sha256;
    info.summary_md = readmeSummary(readme.text);
  }
  return info;
}
