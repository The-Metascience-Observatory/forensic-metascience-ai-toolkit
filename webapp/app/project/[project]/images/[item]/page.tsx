import { ImageItem } from "./ImageItem";
export const dynamic = "force-dynamic";
export default async function Page(props: { params: Promise<{ project: string; item: string }> }) {
  const params = await props.params;
  const project = decodeURIComponent(params.project);
  return (
    <ImageItem project={project} projectName={project} itemId={decodeURIComponent(params.item)} />
  );
}
