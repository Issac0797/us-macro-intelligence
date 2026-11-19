"use client";
import {useEffect,useRef} from 'react';
import {init,type EChartsType} from 'echarts/core';
import {useUI} from '@/components/presentation-provider';
import {chartPalette,formatDate,formatNumber,translate,type Locale} from './presentation';
import {themedOption} from './chart-theme';
export function useResearchChart(option:Record<string,unknown>,renderer:'canvas'|'svg'='canvas'){
 const container=useRef<HTMLDivElement>(null),chart=useRef<EChartsType|null>(null);const {locale,resolvedTheme}=useUI();
 useEffect(()=>{if(!container.current)return;const instance=init(container.current,undefined,{renderer});chart.current=instance;const observer=new ResizeObserver(()=>{instance.resize();const titles=instance.getOption()?.title as Record<string,unknown>[]|undefined;if(titles)instance.setOption({title:titles.map((v,i)=>({id:v.id||String(i),textStyle:{width:Math.max(100,instance.getWidth()-36)}}))});});observer.observe(container.current);return()=>{observer.disconnect();instance.dispose();chart.current=null;};},[renderer]);
 useEffect(()=>{const instance=chart.current;if(!instance)return;const previous=instance.getOption()?.dataZoom as Record<string,unknown>[]|undefined;const prepared=themedOption(option,locale,resolvedTheme);if(Array.isArray(prepared.title))prepared.title=prepared.title.map((v:Record<string,unknown>)=>({...v,textStyle:{...(v.textStyle as object||{}),width:Math.max(100,instance.getWidth()-36)}}));if(previous&&Array.isArray(prepared.dataZoom))prepared.dataZoom=(prepared.dataZoom as Record<string,unknown>[]).map((z,i)=>({...z,...(previous[i]?{start:previous[i].start,end:previous[i].end}:{} )}));instance.setOption(prepared,{notMerge:true,lazyUpdate:false});},[option,locale,resolvedTheme]);
 return {container,chart,background:chartPalette[resolvedTheme].background};
}
