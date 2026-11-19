import type {Dashboard} from './dashboard-state';
import {addSeries,globalContext} from './dashboard-state';
import type {Frequency} from './workspace-types';
export type ResearchContext={series_ids?:string[];start?:string;end?:string;data_mode?:'latest'|'vintage';as_of?:string|null;source_page?:string;selected_observation_date?:string;action?:'add'|'open'|'compare';workspace_id?:string};
const validDay=(s:string)=>/^\d{4}-\d{2}-\d{2}$/.test(s)&&new Date(s+'T00:00:00Z').toISOString().slice(0,10)===s;
export function contextUrl(c:ResearchContext){const q=new URLSearchParams();if(c.series_ids?.length)q.set('series',c.series_ids.join(','));for(const k of ['start','end','data_mode','as_of','source_page','selected_observation_date','action','workspace_id'] as const){if(c[k]!=null)q.set(k,String(c[k]));}return '/workspace?'+q;}
export function parseContext(search:string):ResearchContext{
 if(search.length>2048)throw Error('Research URL is too long');const q=new URLSearchParams(search);const result:ResearchContext={};
 const series=q.get('series');if(series){const ids=series.split(',');if(ids.length>6||ids.some(s=>!/^[A-Z0-9]{1,32}$/.test(s)))throw Error('Invalid Series ID');result.series_ids=[...new Set(ids)];}
 for(const k of ['start','end','as_of','selected_observation_date'] as const){const v=q.get(k);if(v){if(!validDay(v))throw Error('Invalid research date');result[k]=v;}}
 if(result.start&&result.end&&result.start>result.end)throw Error('Invalid research range');const mode=q.get('data_mode');if(mode){if(mode!=='latest'&&mode!=='vintage')throw Error('Invalid data mode');result.data_mode=mode;}
 if(mode==='vintage'&&!result.as_of||mode==='latest'&&result.as_of)throw Error('Invalid as_of context');if(result.as_of&&!mode)throw Error('as_of requires vintage mode');
 const source=q.get('source_page');if(source){if(source.length>120||!/^\/[a-zA-Z0-9/_-]*$/.test(source))throw Error('Invalid source page');result.source_page=source;}
 const action=q.get('action');if(action){if(!['add','open','compare'].includes(action))throw Error('Invalid workspace action');result.action=action as ResearchContext['action'];}
 const id=q.get('workspace_id');if(id){if(!/^[a-f0-9-]{36}$/.test(id))throw Error('Invalid workspace identifier');result.workspace_id=id;}
 return result;
}
export function applyContext(d:Dashboard,c:ResearchContext,known:Map<string,Frequency>):Dashboard{
 for(const sid of c.series_ids||[])if(!known.has(sid))throw Error('Unknown Series ID: '+sid);
 let next=d;if(c.start||c.end||c.data_mode){next=globalContext(next,{...(c.start?{start:c.start}:{}),...(c.end?{end:c.end}:{}),...(c.data_mode?{data_mode:c.data_mode,as_of:c.as_of||null}:{})});}
 for(const sid of c.series_ids||[])next=addSeries(next,sid,known.get(sid));return next;
}
