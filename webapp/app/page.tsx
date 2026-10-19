import { ProjectsTable, type ImageReviewCount } from "./ProjectsTable";
import { workbench } from "@/lib/workbench";
import { loadSettings } from "@/lib/settings";
import { RefreshCountsButton } from "./RefreshCountsButton";
import { RootForm } from "./RootForm";

export const dynamic = "force-dynamic";

/** Join local image-review counts by project. `null` counts mean the image
 * worker could not answer: NaN renders as "—" and sorts last, never as 0. */
function withImageReviews<T extends { name: string }>(
  projects: T[], counts: Record<string, ImageReviewCount> | null,
) {
  return projects.map(p => {
    const c = counts?.[p.name];
    return {
      ...p,
      n_image_reviewed: counts ? (c?.n_items ?? 0) : NaN,
      n_image_reviewed_papers: c?.n_papers ?? 0,
      n_image_reviewed_other_runs: c?.n_items_other_runs ?? 0,
      // NaN (rendered "—", sorted last) when no latest-queue count exists.
      n_image_unviewed: c?.n_latest_items != null ? c.n_latest_items - (c.n_viewed ?? 0) : NaN,
      n_image_viewed: c?.n_viewed ?? 0,
    };
  });
}

/** Image projects with results that the shared catalog does not list yet.
 * The two registries are separate (image results live in the local review
 * store); a gap between them must never hide results from this page, as it
 * hid Yadong Huang's on 2026-09-30. Paper counts are unknown here: 0, flagged. */
function imageOnlyProjects(listed: { name: string }[], counts: Record<string, ImageReviewCount> | null) {
  if (!counts) return [];
  const names = new Set(listed.map(p => p.name));
  return Object.entries(counts)
    .filter(([name, c]) => !names.has(name) && (c.n_latest_items ?? 0) > 0)
    .map(([name]) => ({
      name, image_only: true, n_papers: 0, n_pdf: 0, n_xml: 0, n_image_run: 0,
      n_text_run: 0, n_human_reviewed: 0, n_not_fetched: 0, n_in_progress: 0,
    }));
}

export default async function Home() {
  const settings = loadSettings();
  // Image decisions live in the local image-review database, a separate
  // worker; fetch both at once. A failed count renders as unavailable, not 0.
  const imageCounts = workbench<{ projects: Record<string, ImageReviewCount> }>("image_review_counts")
    .then(r => r.projects).catch(() => null);
  let index;
  try {
    index = await workbench("projects");
  } catch (e) {
    const detail = e instanceof Error ? e.message : String(e);
    return (
      <div className="page">
        <h1 style={{ fontSize: 20, marginTop: 0 }}>Projects</h1>
        <p className="muted" style={{ maxWidth: 640 }}>
          The local catalog could not be read. If the workbench service failed
          to start, resolve the error below and restart the webapp. Once the
          service is running, set the papers root and scan if this machine has
          no cache yet. Scanning does not re-run the agent.
        </p>
        <p style={{ color: "var(--sev-impossible)", maxWidth: 720 }}>{detail}</p>
        <RootForm initial={settings.papers_root} />
      </div>
    );
  }

  return (
    <div className="page">
      <h1 style={{ fontSize: 20, margin: "0 0 6px" }}>Projects</h1>
      <p className="muted" style={{ marginBottom: 14 }}>
        {index.n_projects} project{index.n_projects === 1 ? "" : "s"} ·{" "}
        {index.n_papers} papers in the synchronized catalog
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <RootForm initial={settings.papers_root} />
        <RefreshCountsButton />
      </div>

      {await (async () => {
        const counts = await imageCounts;
        const listed = [...index.projects, ...imageOnlyProjects(index.projects, counts)];
        return <ProjectsTable projects={withImageReviews(listed, counts)} />;
      })()}
      {index.errors && index.errors.length > 0 && (
        <p style={{ color: "var(--sev-impossible)", marginTop: 12 }}>
          {index.errors.length} project(s) could not be read.
        </p>
      )}
    </div>
  );
}
