"use client";
import Link from 'next/link';
import {usePathname} from 'next/navigation';
import {contextUrl,type ResearchContext} from '@/lib/research-context';
import {useUI} from './presentation-provider';
export function WorkspaceActions({seriesIds,start,end,dataMode='latest',asOf,observationDate}:{seriesIds:string[];start?:string;end?:string;dataMode?:'latest'|'vintage';asOf?:string|null;observationDate?:string}){
 const {t}=useUI(),source=usePathname();let rangeStart=start,rangeEnd=end;if(observationDate&&!start&&!end){const a=new Date(observationDate+'T00:00:00Z'),b=new Date(observationDate+'T00:00:00Z');if(Number.isFinite(a.getTime())){a.setUTCFullYear(a.getUTCFullYear()-1);b.setUTCFullYear(b.getUTCFullYear()+1);rangeStart=a.toISOString().slice(0,10);rangeEnd=b.toISOString().slice(0,10);}}const context:ResearchContext={series_ids:seriesIds.slice(0,6),start:rangeStart,end:rangeEnd,data_mode:dataMode,as_of:dataMode==='vintage'?asOf:undefined,selected_observation_date:observationDate,source_page:source};
 return <span className="workspace-quick-actions"><Link href={contextUrl({...context,action:'add'})}>{t('Add to Workspace')}</Link><Link href={contextUrl({...context,action:'compare'})}>{t('Compare in Workspace')}</Link></span>;
}
