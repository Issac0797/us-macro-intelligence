export type Point = {date:string;value:number|null};
export type Series = {id:string;native_id:string;title:string;title_zh:string;units:string;frequency:'monthly'|'daily';seasonal_adjustment:string;source:string;source_url:string;download_url:string;notice:string;policy_url:string;generated_at:string;maturity_months?:number;coverage:{start:string;end:string;count:number};observations:Point[]};
export type Snapshot = {schema_version:1;generated_at:string;is_live:false;revision_basis:string;series:Series[];fed_decisions:{date:string;lower:number;upper:number;units:string;source_url:string;notice:string}[]};
export type Transform = 'raw'|'yoy'|'mom'|'absolute_change';
export function supported(s:Series,t:Transform){return t==='raw'||t==='absolute_change'||(s.frequency==='monthly'&&s.units!=='Percent');}
export function transform(s:Series,t:Transform):Point[]{
 if(!supported(s,t))throw new Error('Unsupported transformation');
 const byDate=new Map(s.observations.map(p=>[p.date,p.value]));
 return s.observations.map((p,i)=>{
  if(t==='raw')return {...p};
  let previous:number|null|undefined;
  if(s.frequency==='monthly'){
   const [year,month]=p.date.split('-').map(Number);const d=new Date(Date.UTC(year,month-1-(t==='yoy'?12:1),1));
   previous=byDate.get(d.toISOString().slice(0,10));
  }else previous=s.observations[i-1]?.value;
  const value=p.value==null||previous==null?null:t==='absolute_change'?p.value-previous:p.value<=0||previous<=0?null:(p.value/previous-1)*100;
  return {date:p.date,value};
 });
}
export function units(s:Series,t:Transform){return t==='yoy'||t==='mom'?'%':t==='absolute_change'&&s.units==='Percent'?'pp':s.units;}
export function spread(a:Series,b:Series):Point[]{
 const rhs=new Map(b.observations.map(p=>[p.date,p.value]));
 return a.observations.map(p=>{const q=rhs.get(p.date);return {date:p.date,value:p.value==null||q==null?null:p.value-q};});
}
export function correlation(a:Point[],b:Point[]){
 const rhs=new Map(b.map(p=>[p.date,p.value]));const pairs=a.flatMap(p=>{const q=rhs.get(p.date);return p.value==null||q==null?[]:[[p.value,q]];});
 const n=pairs.length;if(n<3)return {n,value:null};
 const mean=(i:number)=>pairs.reduce((sum,p)=>sum+p[i],0)/n;const x=mean(0),y=mean(1);
 const dx=pairs.reduce((s,p)=>s+(p[0]-x)**2,0),dy=pairs.reduce((s,p)=>s+(p[1]-y)**2,0);
 return {n,value:dx===0||dy===0?null:pairs.reduce((s,p)=>s+(p[0]-x)*(p[1]-y),0)/Math.sqrt(dx*dy)};
}
export type Workspace = {version:1;first:string;second:string;transform:Transform;start:string;end:string;linked:boolean};
export const defaults:Workspace={version:1,first:'CPIAUCSL',second:'CPILFESL',transform:'yoy',start:'2021-01-01',end:'',linked:true};
export function readWorkspace(raw:string|null,ids:string[]):Workspace{
 try{const v=JSON.parse(raw||'null');if(v?.version===1&&ids.includes(v.first)&&ids.includes(v.second)&&['raw','yoy','mom','absolute_change'].includes(v.transform)&&typeof v.linked==='boolean'&&[v.start,v.end].every(x=>typeof x==='string'&&(x===''||/^\d{4}-\d{2}-\d{2}$/.test(x)))&&(!v.end||v.start<=v.end))return v;}catch{}
 return {...defaults};
}
