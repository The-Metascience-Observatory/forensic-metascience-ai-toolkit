import { Reviewer } from "./Reviewer";

export const dynamic = "force-dynamic";

export default async function ReviewPage(props: {
  params: Promise<{ project: string; slug: string }>;
  searchParams: Promise<{ dir?: string }>;
}) {
  const [params, searchParams] = await Promise.all([props.params, props.searchParams]);
  return (
    <Reviewer
      project={decodeURIComponent(params.project)}
      slug={decodeURIComponent(params.slug)}
      dir={searchParams?.dir || null}
    />
  );
}
