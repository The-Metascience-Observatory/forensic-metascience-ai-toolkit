import { redirect } from "next/navigation";
import { PapersPage } from "./PapersPage";
export const dynamic = "force-dynamic";

/** True when the project has image findings and no other findings: then its
 *  page opens on the Image findings tab. Any failure answers false (the
 *  non-image tab is the safe default). */
async function onlyImageFindings(project: string): Promise<boolean> {
  const { workbench } = await import("@/lib/workbench");
  try {
    const [papers, feed] = await Promise.all([
      // Sorted by non-image findings, most first: the top row says whether any paper has one.
      workbench("papers", { project, offset: 0, limit: 1, sort: "findings", direction: "desc" }),
      workbench("feed", { project, component: "image_forensics", verdict: "all", offset: 0, limit: 1, facets: "none" }),
    ]);
    const images = Number(feed?.pagination?.total ?? 0);
    const nonImage = Number(papers?.papers?.[0]?.n_non_image_findings ?? 0);
    return images > 0 && !(nonImage > 0);
  } catch {
    return false;
  }
}

export default async function Page(props: {
  params: Promise<{ project: string }>;
  searchParams: Promise<{ view?: string }>;
}) {
  const [params, searchParams] = await Promise.all([props.params, props.searchParams]);
  const project = decodeURIComponent(params.project);
  // `?view=findings` is the tab's own link: an explicit choice is never redirected.
  if (!searchParams.view && await onlyImageFindings(project)) {
    redirect(`/project/${encodeURIComponent(project)}/images`);
  }
  return <PapersPage project={project} />;
}
