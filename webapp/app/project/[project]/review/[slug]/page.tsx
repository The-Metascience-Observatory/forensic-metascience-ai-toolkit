import { Reviewer } from "./Reviewer";

export const dynamic = "force-dynamic";

export default function ReviewPage({
  params,
  searchParams,
}: { params: { project: string; slug: string }; searchParams?: { dir?: string } }) {
  return (
    <Reviewer
      project={decodeURIComponent(params.project)}
      slug={decodeURIComponent(params.slug)}
      dir={searchParams?.dir || null}
    />
  );
}
