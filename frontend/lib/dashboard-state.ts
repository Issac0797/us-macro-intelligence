import type {Configuration} from './workspace-types';
import {template,line,calc,today} from './workspace-utils';
export type Panel={id:string;configuration:Configuration;grid:{x:number;y:number;w:number;h:number};linked:boolean;independent:boolean;collapsed:boolean;zoom:{start:string;end:string}|null};
export type Dashboard={kind:'dashboard';configuration_version:2;title:string;charts:Panel[];linked:boolean;layout_mode:'single'|'two'|'four'|'custom';active_chart_id:string;start:string;end:string;data_mode:'latest'|'vintage';as_of:string|null};
export const chartId=()=>crypto.randomUUID();
export function pack(charts:Panel[]):Panel[]{const occupied=new Set<string>();return charts.map(c=>{const w=Math.max(3,Math.min(12,c.grid.w)),h=Math.max(3,Math.min(10,c.grid.h));let x=0,y=0;for(;y<100;y++){let found=false;for(x=0;x<=12-w;x++){let clear=true;for(let i=x;i<x+w;i++)for(let j=y;j<y+h;j++)if(occupied.has(i+','+j))clear=false;if(clear){found=true;break;}}if(found)break;}for(let i=x;i<x+w;i++)for(let j=y;j<y+h;j++)occupied.add(i+','+j);return {...c,grid:{x,y,w,h}};});}
export function panel(configuration:Configuration):Panel{return {id:chartId(),configuration,grid:{x:0,y:0,w:6,h:5},linked:true,independent:false,collapsed:false,zoom:null};}
export function single(sid='CPIAUCSL',frequency:Configuration['frequency']='monthly'):Configuration{return {...template(0),title:sid,frequency,lines:[line(sid,sid,[calc('raw')])],show_recessions:false};}
export function initialDashboard():Dashboard{const c={...panel(template(0)),id:'chart-initial',grid:{x:0,y:0,w:12,h:5}};return {kind:'dashboard',configuration_version:2,title:'Research Dashboard',charts:pack([c]),linked:true,layout_mode:'single',active_chart_id:c.id,start:c.configuration.start,end:c.configuration.end,data_mode:'latest',as_of:null};}
export function validateDashboard(value:unknown):Dashboard{
 const d=value as Dashboard;if(!d||d.kind!=='dashboard'||d.configuration_version!==2||!Array.isArray(d.charts)||!d.charts.length||d.charts.length>8)throw Error('Invalid dashboard configuration');
 const ids=d.charts.map(c=>c.id);if(new Set(ids).size!==ids.length||!ids.includes(d.active_chart_id)||ids.some(id=>!/^[A-Za-z0-9_-]{1,60}$/.test(id)))throw Error('Invalid chart IDs');
 for(const c of d.charts){const q=c.configuration;if(!q||q.configuration_version!==1||!q.lines?.length||q.lines.length>6||q.lines.some(l=>!/^[A-Z0-9]{1,32}$/.test(l.series_id)))throw Error('Invalid chart configuration');if(!c.grid||c.grid.w<3||c.grid.w>12||c.grid.h<3||c.grid.h>10||c.grid.x<0||c.grid.x+c.grid.w>12)throw Error('Invalid grid');if(!c.independent&&(q.data_mode!==d.data_mode||q.as_of!==d.as_of))throw Error('Independent historical context must be explicit');}
 return d;
}
export function upgrade(value:unknown):Dashboard{const v=value as Configuration&{kind?:string};if(v?.kind==='dashboard')return validateDashboard(value);if(v?.configuration_version!==1||!Array.isArray(v.lines))throw Error('Unsupported chart configuration');const c=panel(structuredClone(v));return {...initialDashboard(),title:v.title,start:v.start,end:v.end,data_mode:v.data_mode,as_of:v.as_of,charts:[c],active_chart_id:c.id};}
export function globalContext(d:Dashboard,patch:Partial<Pick<Dashboard,'start'|'end'|'data_mode'|'as_of'>>):Dashboard{const next={...d,...patch};return {...next,charts:d.charts.map(c=>c.independent?c:{...c,configuration:{...c.configuration,start:next.start,end:next.end,data_mode:next.data_mode,as_of:next.as_of},zoom:null})};}
export function reorder(d:Dashboard,id:string,target:string):Dashboard{const charts=[...d.charts];const a=charts.findIndex(c=>c.id===id),b=charts.findIndex(c=>c.id===target);if(a<0||b<0)return d;const [c]=charts.splice(a,1);charts.splice(b,0,c);return {...d,charts:pack(charts)};}
export function addPanel(d:Dashboard,c:Panel):Dashboard{if(d.charts.length>=8)throw Error('Maximum 8 charts');return {...d,charts:pack([...d.charts,c]),active_chart_id:c.id};}
export function addSeries(d:Dashboard,sid:string,frequency:Configuration['frequency']='monthly',transform='raw'):Dashboard{
 if(d.charts.some(c=>c.configuration.data_mode===d.data_mode&&c.configuration.as_of===d.as_of&&c.configuration.lines.some(l=>l.series_id===sid&&l.calculations.length===1&&l.calculations[0].transform===transform)))return d;
 const config={...single(sid,frequency),start:d.start,end:d.end,data_mode:d.data_mode,as_of:d.as_of,lines:[line(sid,sid,[calc(transform)])]};
 return {...addPanel(d,panel(config)),layout_mode:'custom'};
}
