"use client";
import {useMemo} from 'react';
import {use} from 'echarts/core';
import {LineChart} from 'echarts/charts';
import {GridComponent,TooltipComponent,DataZoomComponent,MarkLineComponent,LegendComponent} from 'echarts/components';
import {SVGRenderer} from 'echarts/renderers';
import type {Point} from '@/lib/types';
import {useResearchChart} from '@/lib/chart-presentation';
import {useUI} from './presentation-provider';
use([LineChart,GridComponent,TooltipComponent,DataZoomComponent,MarkLineComponent,LegendComponent,SVGRenderer]);
export default function MacroChart({points,label,units}:{points:Point[];label:string;units:string}){const {t}=useUI();const option=useMemo(()=>({animation:false,grid:{left:65,right:25,top:35,bottom:70},tooltip:{trigger:'axis'},xAxis:{type:'time',axisTick:{show:false},splitLine:{show:false}},yAxis:{type:'value',name:units,scale:true,splitNumber:5},dataZoom:[{type:'inside',filterMode:'none'},{type:'slider',height:18,bottom:8}],series:[{name:label,type:'line',showSymbol:false,connectNulls:false,sampling:'lttb',lineStyle:{width:2.3},areaStyle:{opacity:.08},data:points.map(p=>[p.date,p.value])}]}),[points,label,units]);const {container}=useResearchChart(option,'svg');return <div ref={container} className="macro-chart" role="img" aria-label={t(label)+' · '+t(units)}/>;}
