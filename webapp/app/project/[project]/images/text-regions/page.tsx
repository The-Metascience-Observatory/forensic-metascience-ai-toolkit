import {TextRegionAudit} from './TextRegionAudit';
export const dynamic='force-dynamic';
export default function Page({params,searchParams}:{params:{project:string};searchParams:{run?:string}}) {
  return <TextRegionAudit project={decodeURIComponent(params.project)} initialRun={searchParams.run || ''}/>;
}
