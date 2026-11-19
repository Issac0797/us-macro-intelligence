import {supported,type Series,type Transform,type Workspace,type Snapshot,type Point} from './research.ts';
export type Panel={series:string;transform:Transform};
export type Workbench={version:2;panels:Panel[];start:string;end:string;linked:boolean};
export const initialWorkbench:Workbench={version:2,panels:[{series:'CPIAUCSL',transform:'yoy'},{series:'UNRATE',transform:'raw'},{series:'DGS2',transform:'raw'},{series:'DGS10',transform:'raw'}],start:'2021-01-01',end:'',linked:true};
export function validDate(v:unknown):v is string{return typeof v==='string'&&(v===''||/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v+'T00:00:00Z'))&&new Date(v+'T00:00:00Z').toISOString().slice(0,10)===v);}
export function restoreWorkbench(raw:string|null,series:Series[],legacy?:Workspace):Workbench{
 const fallback=()=>({...initialWorkbench,panels:initialWorkbench.panels.map(p=>({...p}))});
 try{
  const v=JSON.parse(raw||'null');
  if(v?.version===2&&Array.isArray(v.panels)&&v.panels.length===4&&v.panels.every((p:Panel)=>{const s=series.find(s=>s.id===p.series);return s&&['raw','yoy','mom','absolute_change'].includes(p.transform)&&supported(s,p.transform);})&&validDate(v.start)&&validDate(v.end)&&(!v.end||v.start<=v.end)&&typeof v.linked==='boolean')return v;
 }catch{}
 const result=fallback();
 if(legacy&&series.some(s=>s.id===legacy.first)&&series.some(s=>s.id===legacy.second)){
  result.panels.splice(0,2,...[legacy.first,legacy.second].map(id=>({series:id,transform:supported(series.find(s=>s.id===id)!,legacy.transform)?legacy.transform:'raw' as Transform})));
  result.start=legacy.start;result.end=legacy.end;result.linked=legacy.linked;
 }
 return result;
}
export function commonDomain(snapshot:Snapshot,start:string,end:string):[number,number]{
 const begins=snapshot.series.map(s=>s.coverage.start).sort(),ends=snapshot.series.map(s=>s.coverage.end).sort();
 const first=Date.parse((start||begins[0])+'T00:00:00Z'),last=Date.parse((end||ends.at(-1))+'T00:00:00Z');
 return first<last?[first,last]:[first,first+86400000];
}
export function exactCursor(points:Point[],timestamp:number){const date=new Date(timestamp).toISOString().slice(0,10);const observation=points.find(p=>p.date===date);return {date,value:observation?.value??null,hasObservation:observation!=null&&observation.value!=null};}
export function visiblePoints(points:Point[],start:number,end:number){return points.filter(p=>{const stamp=Date.parse(p.date+'T00:00:00Z');return stamp>=start&&stamp<=end});}
export function chartExport(snapshot:Snapshot,series:Series,method:Transform,points:Point[],displayUnits:string){
 const {observations,...provenance}=series;
 return {format_version:1,is_live:false,mode:'frozen_latest_revised_snapshot',snapshot_generated_at:snapshot.generated_at,revision_basis:snapshot.revision_basis,transformation:method,display_units:displayUnits,data_license:'Original agency terms; data are not relicensed under MIT.',source:provenance,displayed_observations:points};
}
export function exportCsv(data:ReturnType<typeof chartExport>){
 const cell=(v:unknown)=>{const text=String(v??'');return '"'+(typeof v==='string'&&/^[=+@-]/.test(text)?"'"+text:text).replaceAll('"','""')+'"'};
 const rows:unknown[][]=[['series_id','native_id','observation_date','value','display_units','transform','snapshot_generated_at','source_url','notice']];
 data.displayed_observations.forEach(p=>rows.push([data.source.id,data.source.native_id,p.date,p.value,data.display_units,data.transformation,data.snapshot_generated_at,data.source.source_url,data.source.notice]));
 return rows.map(r=>r.map(cell).join(',')).join('\r\n');
}
export function downloadFile(name:string,content:Blob|string,type='application/json'){
 const url=URL.createObjectURL(typeof content==='string'?new Blob([content],{type}):content);const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
