export const dynamic='force-dynamic';
export default async function Page(props:{params:Promise<{project:string}>}){
  const params=await props.params;
  const project=decodeURIComponent(params.project);
  return <div className="page"><h1>End of this paper list</h1><p>This is a navigation boundary, not a statement about whether the project is fully reviewed.</p><a href={`/project/${encodeURIComponent(project)}`}>Return to the project</a></div>;
}
