import { ImageQueue } from "./ImageQueue";
export const dynamic="force-dynamic";
export default function Page({params}:{params:{project:string}}){const project=decodeURIComponent(params.project);return <><p><a href={`/project/${encodeURIComponent(project)}/images/text-regions`}>Text-region audit</a></p><ImageQueue project={project} projectName={project}/></>;}
