import { PapersPage } from "./PapersPage";
export const dynamic="force-dynamic";
export default function Page({params}:{params:{project:string}}){return <PapersPage project={decodeURIComponent(params.project)}/>;}
