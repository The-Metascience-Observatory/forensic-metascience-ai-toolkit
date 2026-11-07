import {TextRegionAudit} from './TextRegionAudit';
export const dynamic='force-dynamic';
export default async function Page(props:{params:Promise<{project:string}>;searchParams:Promise<{run?:string}>}) {
  const [params,searchParams]=await Promise.all([props.params,props.searchParams]);
  return <TextRegionAudit project={decodeURIComponent(params.project)} initialRun={searchParams.run || ''}/>;
}
