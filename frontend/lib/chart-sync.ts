/** Timestamp-only interaction coordinator. Never fetches or persists mouse state. */
export type DatePoint={date:string;index:number;seriesIndex:number;available:boolean};
export type SyncChart={isDisposed?:()=>boolean;on:(event:string,fn:(event:any)=>void)=>void;off:(event:string,fn:(event:any)=>void)=>void;dispatchAction:(action:any,options?:any)=>void};
export type ZoomRange={start:string;end:string};
const stamp=(value:unknown)=>typeof value==='number'?value:Date.parse(String(value));
export class ChartSyncController{
 private charts=new Map<string,{chart:SyncChart;points:DatePoint[];linked:boolean;axis:(e:any)=>void;zoom:(e:any)=>void}>();
 private broadcasting=false;private cursorTimer:ReturnType<typeof setTimeout>|null=null;private pending:{id:string;date:number}|null=null;
 constructor(private onCursor:(id:string,date:string,available:boolean)=>void=()=>{},private onZoom:(range:ZoomRange,ids:string[])=>void=()=>{}){}
 register(id:string,chart:SyncChart,points:DatePoint[],linked=true){
  this.remove(id);const axis=(e:any)=>{const date=stamp(e.axesInfo?.find((a:any)=>a.axisDim==='x')?.value??e.axesInfo?.[0]?.value);if(this.broadcasting||!this.charts.get(id)?.linked||!Number.isFinite(date))return;this.pending={id,date};if(!this.cursorTimer)this.cursorTimer=setTimeout(()=>{this.cursorTimer=null;const p=this.pending;this.pending=null;if(p)this.cursor(p.id,p.date)},32)};
  const zoom=(e:any)=>{if(this.broadcasting||!this.charts.get(id)?.linked)return;const v=e.batch?.[0]||e;const dates=this.charts.get(id)!.points.map(p=>stamp(p.date)).filter(Number.isFinite);if(!dates.length)return;const min=Math.min(...dates),max=Math.max(...dates);const start=v.startValue!=null?stamp(v.startValue):min+(max-min)*(v.start??0)/100;const end=v.endValue!=null?stamp(v.endValue):min+(max-min)*(v.end??100)/100;if(Number.isFinite(start)&&Number.isFinite(end)&&start<=end)this.zoom(id,{start:new Date(start).toISOString(),end:new Date(end).toISOString()});};
  this.charts.set(id,{chart,points,linked,axis,zoom});chart.on('updateAxisPointer',axis);chart.on('datazoom',zoom);return()=>this.remove(id);
 }
 update(id:string,points:DatePoint[],linked:boolean){const c=this.charts.get(id);if(c){c.points=points;c.linked=linked;}}
 cursor(source:string,date:number){if(this.broadcasting||!this.charts.get(source)?.linked)return;this.broadcasting=true;try{for(const [id,c]of this.charts){if(!c.linked)continue;const p=c.points.find(p=>stamp(p.date)===date&&p.available);this.onCursor(id,new Date(date).toISOString().slice(0,10),!!p);if(id!==source){if(p)c.chart.dispatchAction({type:'showTip',seriesIndex:p.seriesIndex,dataIndex:p.index},{silent:true});else{c.chart.dispatchAction({type:'hideTip'},{silent:true});c.chart.dispatchAction({type:'updateAxisPointer',currTrigger:'leave'},{silent:true});}}}}finally{this.broadcasting=false;}}
 zoom(source:string,range:ZoomRange){if(this.broadcasting||!this.charts.get(source)?.linked)return;this.broadcasting=true;try{const ids:string[]=[];for(const [id,c]of this.charts){if(!c.linked)continue;ids.push(id);if(id!==source)c.chart.dispatchAction({type:'dataZoom',startValue:stamp(range.start),endValue:stamp(range.end)},{silent:true});c.chart.dispatchAction({type:'hideTip'},{silent:true});}this.onZoom(range,ids);}finally{this.broadcasting=false;}}
 remove(id:string){const c=this.charts.get(id);if(c){if(!c.chart.isDisposed?.()){c.chart.off('updateAxisPointer',c.axis);c.chart.off('datazoom',c.zoom);}this.charts.delete(id);}}
 dispose(){for(const id of [...this.charts.keys()])this.remove(id);if(this.cursorTimer)clearTimeout(this.cursorTimer);this.pending=null;this.cursorTimer=null;}
 get size(){return this.charts.size;}
}
