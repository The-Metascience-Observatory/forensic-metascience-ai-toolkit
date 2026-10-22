import { citationParts, doiLink, pubpeerLink } from "@/lib/citation";
import type { Item, PaperHead } from "@/app/images/lib";

/** Authors as recorded; `metadata.json` separates them with semicolons. */
function authorLine(authors: string | null | undefined): string {
  return (authors || "").split(";").map((a) => a.trim()).filter(Boolean).join(", ");
}

function PubPeerButton({ paper }: { paper: PaperHead }) {
  const link = pubpeerLink(
    paper.doi || (paper.dir?.includes("--") ? paper.dir.replace("--", "/") : null),
    paper.pubpeer_url, paper.title);
  if (!link) return <span className="muted"> · no DOI or title to search PubPeer with</span>;
  return (
    <> · <a href={link.href} target="_blank" rel="noreferrer"
            title={link.label === "PubPeer page" ? "Open this paper's PubPeer discussion" : "Search PubPeer for this paper"}>
      {link.label} →</a></>
  );
}

function Reference({ paper }: { paper: PaperHead }) {
  const { journal, loc, year } = citationParts(paper);
  const authors = authorLine(paper.authors);
  const pages = (paper.pages || "").trim();
  const doi = doiLink(paper.doi
    || (paper.dir?.includes("--") ? paper.dir.replace("--", "/") : null));
  const source = [loc, pages].filter(Boolean).join(loc && pages ? ":" : "");
  return (
    <span>
      {authors && <>{authors}. </>}
      {paper.title ? <b>{paper.title.replace(/\.\s*$/, "")}.</b> : <span className="muted">title not recorded.</span>}
      {journal && <> <span className="journal-title">{journal}</span></>}
      {source && <> {source}</>}
      {year && <> ({year})</>}
      {(journal || source || year) && "."}
      {doi && <> <a href={doi.href} target="_blank" rel="noreferrer">{doi.label}</a></>}
    </span>
  );
}

/** Full references for the two papers of a cross-paper finding, in panel
 *  order, so the reader never has to work out which paper A and B are. */
export function PaperReferences({ item }: { item: Item }) {
  if (item.kind !== "cross") return null;
  const papers = item.panels.map((p) =>
    item.papers.find((x) => x.dir === p.paper_dir) || { dir: p.paper_dir });
  return (
    <section aria-label="Papers" style={{ margin: "8px 0", overflowWrap: "anywhere" }}>
      {papers.map((paper, i) => (
        <p key={i} style={{ margin: "0 0 6px" }}>
          <b>{"AB"[i]}</b> · <Reference paper={paper} /><PubPeerButton paper={paper} />
        </p>
      ))}
    </section>
  );
}

/** First author only, "et al." when there are more. `metadata.json` separates
 *  authors with semicolons; a record with no separator is one author. */
function firstAuthorEtAl(authors: string | null | undefined): string {
  const list = (authors || "").split(";").map((a) => a.trim()).filter(Boolean);
  if (!list.length) return "";
  return list.length > 1 ? `${list[0]} et al.` : list[0];
}

/** The shown paper's reference, in the left pane under the item buttons
 *  (Dan, 2026-10-22): first author et al., the title as the link to its DOI,
 *  journal in italics, volume in bold. The reference is for orientation, so
 *  it never claims more than the record holds: a missing field is omitted. */
export function PaperReference({ paper }: { paper: PaperHead | undefined }) {
  if (!paper) return null;
  const { journal, year } = citationParts(paper);
  const volume = String(paper.volume ?? "").trim();
  const issue = String(paper.issue ?? "").trim();
  const pages = (paper.pages || "").trim();
  const authors = firstAuthorEtAl(paper.authors);
  const doi = doiLink(paper.doi
    || (paper.dir?.includes("--") ? paper.dir.replace("--", "/") : null));
  const title = (paper.title || "").replace(/\.\s*$/, "");
  const titleNode = !title
    ? <span className="muted">title not recorded</span>
    : doi
      ? <a href={doi.href} target="_blank" rel="noreferrer">{title}</a>
      : <>{title}</>;
  return (
    <section aria-label="Paper reference" style={{ margin: "8px 0", overflowWrap: "anywhere" }}>
      <p style={{ margin: 0 }}>
        {authors && <>{authors} </>}
        {year && <>({year}). </>}
        {titleNode}.
        {journal && <> <span className="journal-title">{journal}</span></>}
        {volume && <> <b>{volume}</b></>}
        {issue && <>({issue})</>}
        {pages && <>{volume || issue ? ":" : " "}{pages}</>}
        {(journal || volume || issue || pages) && "."}
        <PubPeerButton paper={paper} />
      </p>
    </section>
  );
}
