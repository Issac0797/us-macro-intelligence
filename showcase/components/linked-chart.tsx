'use client';
import {useEffect,useMemo,useRef,useState} from 'react';
import {use,type EChartsType} from 'echarts/core';
import {LineChart,BarChart} from 'echarts/charts';
import {GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,AxisPointerComponent,TitleComponent} from 'echarts/components';
import {SVGRenderer} from 'echarts/renderers';
import {useResearchChart} from '../shared/lib/chart-presentation';
import {useUI} from '../shared/components/presentation-provider';
import type {Point,Series,Snapshot,Transform} from '../lib/research';
import {exactCursor,chartExport,exportCsv,downloadFile,visiblePoints} from '../lib/workbench';
use([LineChart,BarChart,GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,AxisPointerComponent,TitleComponent,SVGRenderer]);
type Member={instance:EChartsType;pointer:(stamp:number|null)=>void;zoom:(start:number,end:number,apply:boolean)=>void};
const members=new Map<string,Member>();
type ExportContext={snapshot:Snapshot;series:Series;method:Transform};
export function Chart({label,lines,unit,linked=false,categories,domain,exportContext}:{label:string;lines:{name:string;points:Point[]}[];unit:string;linked?:boolean;categories?:string[];domain?:[number,number];exportContext?:ExportContext}){
 const {locale,resolvedTheme,number}=useUI(),zh=locale==='zh-CN';const [cursor,setCursor]=useState<{date:string;event:number}|null>(null),[zoom,setZoom]=useState(''),[exportStatus,setExportStatus]=useState('');const counters=useRef({pointer:0,zoom:0});const cursorStamp=useRef<number|null>(null);
 const option=useMemo(()=>({animation:false,grid:{left:78,right:28,top:45,bottom:90},legend:{top:4},tooltip:{trigger:'axis'},axisPointer:{link:[{xAxisIndex:'all'}]},xAxis:{type:categories?'category':'time',...(categories?{data:categories}:domain?{min:domain[0],max:domain[1]}:{}),axisPointer:{snap:false,label:{show:true}},boundaryGap:false},yAxis:{type:'value',name:unit,scale:true,nameGap:12},dataZoom:categories?[]:[{type:'inside',filterMode:'none'},{type:'slider',bottom:22,height:22,filterMode:'none'}],series:lines.map(s=>({name:s.name,type:'line',showSymbol:!!categories,symbolSize:6,connectNulls:false,lineStyle:{width:2},data:s.points.map((p,i)=>categories?[categories[i],p.value]:[p.date,p.value])}))}),[lines,unit,categories,domain]);
 const {container,chart,background}=useResearchChart(option,'svg');
 useEffect(()=>{
  const instance=chart.current;if(!instance||categories||(!domain&&!linked))return;
  // Broadcast UTC axis values, never another chart's dataIndex. Daily indexes
  // are not valid monthly indexes. Silent target actions prevent feedback loops.
  const receivePointer=(stamp:number|null)=>{
   cursorStamp.current=stamp;
   if(stamp===null){setCursor(null);instance.dispatchAction({type:'hideTip',escapeConnect:true},{silent:true});instance.dispatchAction({type:'updateAxisPointer',currTrigger:'leave',escapeConnect:true},{silent:true});return;}
   counters.current.pointer++;setCursor({date:new Date(stamp).toISOString().slice(0,10),event:counters.current.pointer});
   const x=instance.convertToPixel({xAxisIndex:0},stamp) as number;
   if(Number.isFinite(x))instance.dispatchAction({type:'updateAxisPointer',currTrigger:'mousemove',x,y:instance.getHeight()/2,axesInfo:[{axisDim:'x',axisIndex:0,value:stamp}],escapeConnect:true},{silent:true});
  };
  const receiveZoom=(start:number,end:number,apply:boolean)=>{
   counters.current.zoom++;if(apply)instance.dispatchAction({type:'dataZoom',startValue:start,endValue:end,escapeConnect:true},{silent:true});
   setZoom(new Date(start).toISOString().slice(0,10)+' → '+new Date(end).toISOString().slice(0,10));
  };
  const member={instance,pointer:receivePointer,zoom:receiveZoom};
  if(linked)members.set(instance.id,member);
  const broadcast=(stamp:number|null)=>{if(linked)members.forEach(target=>target.pointer(stamp));else receivePointer(stamp)};
  const moved=(event:any)=>{const pixel=[event.offsetX,event.offsetY];if(!instance.containPixel({gridIndex:0},pixel))return;const raw=instance.convertFromPixel({xAxisIndex:0},event.offsetX) as number;if(Number.isFinite(raw))broadcast(Date.parse(new Date(raw).toISOString().slice(0,10)+'T00:00:00Z'));};
  const left=()=>broadcast(null);
  const zoomed=()=>{const z=(instance.getOption().dataZoom as any[])?.[0];if(!z)return;const begin=typeof z.startValue==='number'?z.startValue:Date.parse(z.startValue),end=typeof z.endValue==='number'?z.endValue:Date.parse(z.endValue);if(Number.isFinite(begin)&&Number.isFinite(end)){receiveZoom(begin,end,false);if(linked)members.forEach(target=>{if(target.instance.id!==instance.id)target.zoom(begin,end,true)})}};
  instance.getZr().on('mousemove',moved);instance.getZr().on('globalout',left);instance.on('datazoom',zoomed);
  instance.setOption({tooltip:{formatter:(raw:any)=>{const row=Array.isArray(raw)?raw[0]:raw;const stamp=cursorStamp.current??Number(row?.axisValue);if(!Number.isFinite(stamp))return '';const date=new Date(stamp).toISOString().slice(0,10);return date+' UTC\n'+lines.map(line=>{const p=line.points.find(p=>p.date===date);return line.name+': '+(p?.value==null?(zh?'该日无原生观测':'No native observation on this date'):number(p.value))}).join('\n')}}});
  return()=>{members.delete(instance.id);if(!instance.isDisposed()){instance.getZr().off('mousemove',moved);instance.getZr().off('globalout',left);instance.off('datazoom',zoomed)}};
 },[chart,categories,domain,linked,lines,locale,resolvedTheme,number]);

 const data=exportContext?chartExport(exportContext.snapshot,exportContext.series,exportContext.method,lines[0].points,unit):null;
 const currentExport=()=>{if(!data)return null;const z=(chart.current?.getOption().dataZoom as any[])?.[0];const start=typeof z?.startValue==='number'?z.startValue:Date.parse(z?.startValue),end=typeof z?.endValue==='number'?z.endValue:Date.parse(z?.endValue);return Number.isFinite(start)&&Number.isFinite(end)?{...data,visible_range:{start:new Date(start).toISOString(),end:new Date(end).toISOString()},displayed_observations:visiblePoints(data.displayed_observations,start,end)}:data;};
 const exportPng=async()=>{try{
  const svg=container.current?.querySelector('svg');if(!svg||!chart.current||!exportContext)throw Error('Chart unavailable');const source=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)],{type:'image/svg+xml'}));
  try{const img=new Image();await new Promise<void>((resolve,reject)=>{img.onload=()=>resolve();img.onerror=()=>reject(Error('SVG render failed'));img.src=source});const width=chart.current.getWidth(),height=chart.current.getHeight(),canvas=document.createElement('canvas');canvas.width=width*2;canvas.height=(height+110)*2;const context=canvas.getContext('2d');if(!context)throw Error('Canvas unavailable');context.scale(2,2);context.fillStyle=background;context.fillRect(0,0,width,height+110);context.fillStyle=resolvedTheme==='dark'?'#e2eaf5':'#182c44';context.font='14px Arial, Microsoft YaHei';context.fillText(label,18,24,width-36);context.drawImage(img,0,35,width,height);context.font='10px Arial, Microsoft YaHei';context.fillText('SNAPSHOT · NOT LIVE · '+exportContext.snapshot.generated_at,18,height+55,width-36);context.fillText(exportContext.series.id+' · '+exportContext.series.source,18,height+73,width-36);context.fillText('Data retain agency terms. Sources / licenses: /sources/',18,height+91,width-36);const blob=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(Error('PNG export failed')),'image/png'));downloadFile(exportContext.series.id+'-snapshot.png',blob,'image/png');setExportStatus(zh?'PNG 已导出':'PNG exported')}finally{URL.revokeObjectURL(source)}
 }catch{setExportStatus(zh?'图表导出失败，请重试。':'Chart export failed; retry.')}};
 const empty=lines.every(l=>!l.points.some(p=>p.value!==null));
 return <section className="chart-card" data-pointer-events={counters.current.pointer} data-zoom-events={counters.current.zoom} data-cursor-date={cursor?.date||''} data-zoom-range={zoom}><div className="chart-heading"><h2>{label}</h2><div className="chart-actions">{data&&<><button onClick={()=>{downloadFile(data.source.id+'-snapshot.csv',exportCsv(currentExport()!),'text/csv;charset=utf-8');setExportStatus(zh?'CSV 已导出':'CSV exported')}}>CSV</button><button onClick={()=>{downloadFile(data.source.id+'-snapshot.json',JSON.stringify(currentExport(),null,2));setExportStatus(zh?'JSON 已导出':'JSON exported')}}>JSON</button><button onClick={exportPng}>PNG</button></>}{!categories&&<button onClick={()=>{chart.current?.dispatchAction({type:'dataZoom',start:0,end:100});setCursor(null)}}>{zh?'重置缩放':'Reset zoom'}</button>}</div></div><div className="static-chart-frame"><div className="showcase-chart" role="img" aria-label={label} ref={container}/>{empty&&<div role="status" className="static-empty">{zh?'所选范围没有观测，不生成替代数据。':'No observations in this range. No substitute data are generated.'}</div>}</div>{domain&&<div className="linked-context" aria-live="off"><span>{cursor?cursor.date+' UTC · '+lines.map(l=>{const p=exactCursor(l.points,Date.parse(cursor.date+'T00:00:00Z'));return p.hasObservation?number(p.value):zh?'该日无原生观测':'No native observation on this date'}).join(' / '):zh?'移动光标以核对原生观测日期':'Move cursor to inspect the native observation date'}</span>{zoom&&<span>{zh?'显示范围：':'Visible range: '}{zoom} UTC</span>}<span role="status">{exportStatus}</span></div>}</section>;
}
