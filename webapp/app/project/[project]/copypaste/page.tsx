import { CopyQueue } from "./CopyQueue";
export const dynamic="force-dynamic";
export default async function Page(props:{params:Promise<{project:string}>}){const params=await props.params;return <CopyQueue project={decodeURIComponent(params.project)}/>;}
