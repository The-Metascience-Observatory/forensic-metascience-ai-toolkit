import { citationParts, doiLink } from "@/lib/citation";
import type { Item, PaperHead } from "@/app/images/lib";

/** Authors as recorded; `metadata.json` separates them with semicolons. */
function authorLine(authors: string | null | undefined): string {
  return (authors || "").split(";").map((a) => a.trim()).filter(Boolean).join(", ");
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
          <b>{"AB"[i]}</b> · <Reference paper={paper} />
        </p>
      ))}
    </section>
  );
}
