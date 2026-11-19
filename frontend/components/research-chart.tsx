"use client";
import {useMemo} from 'react';
import {use} from 'echarts/core';
import {LineChart,BarChart,HeatmapChart} from 'echarts/charts';
import {GridComponent,TooltipComponent,LegendComponent,VisualMapComponent} from 'echarts/components';
import {SVGRenderer} from 'echarts/renderers';
import {useResearchChart} from '@/lib/chart-presentation';
import {useUI} from './presentation-provider';
use([LineChart,BarChart,HeatmapChart,GridComponent,TooltipComponent,LegendComponent,VisualMapComponent,SVGRenderer]);
export default function ResearchChart({option,label}:{option:Record<string,unknown>;label:string}){const {t}=useUI();const prepared=useMemo(()=>({...option,yAxis:option.yAxis&&!Array.isArray(option.yAxis)?{nameLocation:'middle',nameGap:60,nameRotate:90,...option.yAxis as object}:option.yAxis}),[option]);const combined=useMemo(()=>({animation:false,grid:{left:85,right:30,top:55,bottom:70},tooltip:{trigger:'axis'},legend:{type:'scroll',top:5},...prepared}),[prepared]);const {container}=useResearchChart(combined,'svg');return <div ref={container} className="research-chart" role="img" aria-label={t(label)}/>;}
