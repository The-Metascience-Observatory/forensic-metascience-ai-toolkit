import { PapersPage } from "./PapersPage";
export const dynamic="force-dynamic";
export default async function Page(props:{params:Promise<{project:string}>}){const params=await props.params;return <PapersPage project={decodeURIComponent(params.project)}/>;}
