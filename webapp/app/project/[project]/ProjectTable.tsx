"use client";

import { useMemo, useState } from "react";

import { citationLine, displayFirstAuthor } from "@/app/Citation";
import { sev9Color, sev9Label } from "@/lib/constants.gen";
import { sev9Of } from "@/lib/projectTableSort";
import type { Paper } from "@/lib/store";
import {
  compactRunAt,
  cycleSort,
  defaultSort,
  nonImageFindings,
  paperRunAt,
  pipelineVersionOf,
  sortPapers,
  viewedLabel,
  viewedTitle,
  viewState,
  type SortKey,
  type SortState,
} from "@/lib/projectTableSort";

function pubpeerHref(url: string | null | undefined): string | null {
  if (typeof url !== "string") return null;
  return url.startsWith("https://pubpeer.com/") ? url : null;
}

function PubPeerCell({ paper }: { paper: Paper }) {
  const pp = paper.pubpeer;
  if (pp == null || !pp.has_entry) return "—";
  const label = pp.is_image_integrity
    ? (pp.figures?.length ? pp.figures.slice(0, 3).join(", ") : "image")
    : (pp.n_comments ? `${pp.n_comments} comments` : "comments");
  const href = pubpeerHref(pp.url);
  const title = [
    pp.n_comments ? `${pp.n_comments} PubPeer comment${pp.n_comments === 1 ? "" : "s"}` : "PubPeer",
    pp.figures?.length ? pp.figures.join(", ") : "",
  ].filter(Boolean).join(" — ");
  if (!href) return <span title={title || undefined}>{label}</span>;
  return (
    <a href={href} target="_blank" rel="noreferrer" title={title}>
      {label}
    </a>
  );
}

function sortMark(sort: SortState | null, key: SortKey): string {
  if (sort?.key !== key) return "";
  return sort.dir === "desc" ? " ▾" : " ▴";
}

function ariaSort(sort: SortState | null, key: SortKey): "ascending" | "descending" | "none" {
  if (sort?.key !== key) return "none";
  return sort.dir === "asc" ? "ascending" : "descending";
}

export function ProjectTable({ project, papers, onSortChange }: {
  onSortChange?: (sort:SortState|null)=>void;
  project: string;
  papers: Paper[];
}) {
  const [sort, setSort] = useState<SortState | null>(() => onSortChange ? {key:"findings",dir:"desc"} : defaultSort(papers));
  const rows = useMemo(() => onSortChange ? papers : sortPapers(papers, sort), [papers, sort, onSortChange]);

  function onSort(key: SortKey) {
    const next=cycleSort(sort,key); setSort(next); onSortChange?.(next);
  }

  return (
    <table className="grid">
      <thead>
        <tr>
          <th className="title-col" aria-sort={ariaSort(sort, "title")}>
            <button type="button" className="sort-th"
                    onClick={() => onSort("title")}
                    title="Sort by title">
              Title{sortMark(sort, "title")}
            </button>
          </th>
          <th aria-sort={ariaSort(sort, "author")}>
            <button type="button" className="sort-th"
                    onClick={() => onSort("author")}
                    title="Sort by first author">
              First author{sortMark(sort, "author")}
            </button>
          </th>
          <th aria-sort={ariaSort(sort, "journal")}>
            <button type="button" className="sort-th"
                    onClick={() => onSort("journal")}
                    title="Sort by journal">
              Journal{sortMark(sort, "journal")}
            </button>
          </th>
          <th aria-sort={ariaSort(sort, "year")}>
            <button type="button" className="sort-th"
                    onClick={() => onSort("year")}
                    title="Sort by year">
              Year{sortMark(sort, "year")}
            </button>
          </th>
          <th aria-sort={ariaSort(sort, "folder")}>
            <button type="button" className="sort-th"
                    onClick={() => onSort("folder")}
                    title="Sort by folder">
              Folder{sortMark(sort, "folder")}
            </button>
          </th>
          <th aria-sort={ariaSort(sort, "run")}>
            <button type="button" className="sort-th"
                    onClick={() => onSort("run")}
                    title="Sort by latest agent run">
              Run{sortMark(sort, "run")}
            </button>
          </th>
          <th aria-sort={ariaSort(sort, "version")}>
            <button type="button" className="sort-th"
                    onClick={() => onSort("version")}
                    title="Sort by the pipeline version that produced the run">
              Version{sortMark(sort, "version")}
            </button>
          </th>
          <th>PDF</th>
          <th>XML</th>
          <th aria-sort={ariaSort(sort, "verdict")}>
            <button type="button" className="sort-th"
                    onClick={() => onSort("verdict")}
                    title="Sort by verdict">
              Verdict{sortMark(sort, "verdict")}
            </button>
          </th>
          <th aria-sort={ariaSort(sort, "sev9")}>
            <button type="button" className="sort-th"
                    onClick={() => onSort("sev9")}
                    title="Sort by the 1-9 severity ladder the adjudicator assigned">
              S1–9{sortMark(sort, "sev9")}
            </button>
          </th>
          <th className="stack stack-wide" aria-sort={ariaSort(sort, "findings")}>
            <button type="button" className="sort-th"
                    onClick={() => onSort("findings")}
                    title="Sort by the count of findings the image track did not produce">
              Non-image<br/>findings{sortMark(sort, "findings")}
            </button>
          </th>
          <th className="stack" aria-sort={ariaSort(sort, "image")}>
            <button type="button" className="sort-th"
                    onClick={() => onSort("image")}
                    title="Sort by image-finding count">
              Image<br/>findings{sortMark(sort, "image")}
            </button>
          </th>
          <th>PubPeer</th>
          <th className="stack" aria-sort={ariaSort(sort, "viewed")}>
            <button type="button" className="sort-th"
                    onClick={() => onSort("viewed")}
                    title="Sort by whether anyone has opened this paper's review page (un-opened first)">
              Viewed?{sortMark(sort, "viewed")}
            </button>
          </th>
          <th className="review-status">Review</th>
          <th className="review-go"><span className="sr-only">Open review</span></th>
        </tr>
      </thead>
      <tbody>
        {rows.map((p) => {
          const href = `/project/${encodeURIComponent(project)}/review/${encodeURIComponent(p.paper_id)}?dir=${encodeURIComponent(p.dir)}`;
          const status = p.review.paper_status || (p.review.reviewed ? "in_progress" : "unreviewed");
          const cite = citationLine(p);
          const first = displayFirstAuthor(p.first_author || p.authors);
          const folder = p.dir || p.paper_id;
          const view = viewState(p);
          const version = pipelineVersionOf(p);
          const nonImage = nonImageFindings(p);
          const rawWhen = paperRunAt(p);
          const when = compactRunAt(rawWhen);
          const whenTitle = rawWhen
            ? (p.analysed_at_source === "file_mtime"
                ? `file date ${rawWhen}`
                : rawWhen)
            : undefined;
          return (
            <tr key={p.dir}>
              <td className="title-col" title={p.title || folder}>
                <a href={href}>{p.title || folder}</a>
              </td>
              <td style={{ whiteSpace: "normal" }}
                  title={p.authors || undefined}>
                {first || "—"}
              </td>
              <td style={{ whiteSpace: "normal", maxWidth: 220 }}
                  title={cite}>
                {p.journal
                  ? <span className="journal-title">{p.journal}</span>
                  : "—"}
                {(p.volume || p.issue) && (
                  <span className="muted">{" "}
                    {p.volume}{p.issue ? `(${p.issue})` : ""}
                  </span>
                )}
              </td>
              <td>{p.year ?? "—"}</td>
              <td className="mono" style={{ fontSize: 11 }} title={folder}>
                {folder}
              </td>
              <td className="mono" title={whenTitle} style={{ fontSize: 12 }}>
                {when || "—"}
              </td>
              <td className="mono" style={{ fontSize: 11 }}
                  title={version
                    ? `pipeline version ${version} produced this run`
                    : "the run recorded no pipeline version"}>
                {version || "—"}
              </td>
              <td>
                {p.sources.pdf_suspect_stub ? (
                  <span
                    style={{ color: "#b45309", fontWeight: 600 }}
                    title={`the PDF here is ${p.sources.main_pdf_pages ?? "?"} page(s) beside a full-text XML — a publisher preview stub, not the paper; image checks were figure-blind`}
                  >
                    stub?
                  </span>
                ) : p.sources.pdf ? "yes" : "—"}
              </td>
              <td>{p.sources.xml ? "yes" : "—"}</td>
              <td>{p.verdict?.replace(/_/g, " ") ?? "—"}</td>
              <td>
                {(() => {
                  const n = sev9Of(p);
                  if (n == null) return "—";
                  return (
                    <span title={sev9Label(n)}
                          style={{ background: sev9Color(n), color: "white",
                                   borderRadius: 3, padding: "0 6px" }}>
                      S{n}
                    </span>
                  );
                })()}
              </td>
              <td title={nonImage == null
                ? (p.n_findings == null
                    ? "no analysed run"
                    : "this index predates the non-image count — re-run "
                      + "`metascience webapp-index` to fill it in")
                : `${nonImage} finding(s) not produced by the image track`
                  + (p.n_findings != null && p.n_findings !== nonImage
                      ? ` (${p.n_findings} in total)`
                      : "")}>
                {nonImage == null ? "—" : nonImage}
              </td>
              <td style={p.n_image_findings
                ? { fontWeight: 700, color: "var(--sev-suspicious)" }
                : undefined}
                  title={p.n_image_findings == null
                    ? (p.image_status || "image track result not kept (did not run, refused, or discarded)")
                    : (p.n_image_findings === 0
                        ? "completed image run; no currently published image findings"
                        : `${p.n_image_findings} group(s) the adjudicator left `
                          + "unexplained (or never judged)")
                      + ((p.n_image_undecided || 0) > 0
                        ? ` · ${p.n_image_undecided} undecided (insufficient evidence — still standing, not cleared)`
                        : "")}>
                {p.n_image_findings == null ? "—" : p.n_image_findings}
                {(p.n_image_findings != null && (p.n_image_undecided || 0) > 0) && (
                  <span className="muted" style={{ fontWeight: 400, fontSize: 11 }}>
                    {" "}+{p.n_image_undecided}?
                  </span>
                )}
              </td>
              <td>
                <PubPeerCell paper={p} />
              </td>
              <td title={viewedTitle(view)}
                  className={view.code === "seen" ? undefined : "muted"}>
                {viewedLabel(view)}
              </td>
              <td className="review-status" title={p.review.reviewed_by
                ? `reviewed by ${p.review.reviewed_by} on ${p.review.reviewed_at}`
                : ""}>
                {status}
                {status === "complete" && p.review.reviewed_by && (
                  <span className="muted"> · {p.review.reviewed_by}</span>
                )}
                {p.review.submitted_to_pubpeer && (
                  p.review.pubpeer_url
                    ? <>{" · "}<a href={p.review.pubpeer_url} target="_blank"
                                  rel="noreferrer"
                                  title={p.review.pubpeer_note || "submitted to PubPeer"}>
                        PubPeer
                      </a></>
                    : <span className="muted" title={p.review.pubpeer_note || undefined}>
                        {" · "}submitted
                      </span>
                )}
              </td>
              <td className="review-go">
                <a className="review-go-link" href={href}
                   aria-label={`Review ${p.title || p.paper_id}`}
                   title="Review this paper">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none"
                       stroke="currentColor" strokeWidth="2.5"
                       strokeLinecap="round" strokeLinejoin="round"
                       aria-hidden="true">
                    <path d="M5 12h14M13 6l6 6-6 6" />
                  </svg>
                </a>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
