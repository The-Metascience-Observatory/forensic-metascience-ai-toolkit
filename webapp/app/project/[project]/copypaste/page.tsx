import { CopyQueue } from "./CopyQueue";
export const dynamic="force-dynamic";
export default function Page({params}:{params:{project:string}}){return <CopyQueue project={decodeURIComponent(params.project)}/>;}
