import { requireProjectPage } from "@/lib/pageAccess";

export const dynamic = "force-dynamic";

/** Every page under a project: 404 unless the viewer may open it and the
 *  project is one of the configured sources (`lib/pageAccess.ts`). */
export default async function ProjectLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ project: string }>;
}) {
  const { project } = await params;
  await requireProjectPage(decodeURIComponent(project));
  return children;
}
