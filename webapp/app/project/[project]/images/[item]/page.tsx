import { ImageItem } from "./ImageItem";
export const dynamic="force-dynamic";
export default function Page({params}:{params:{project:string;item:string}}){const project=decodeURIComponent(params.project);return <ImageItem project={project} projectName={project} itemId={decodeURIComponent(params.item)}/>;}
