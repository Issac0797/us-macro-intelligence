import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),load=require('./ts-runtime.cjs');
const {hasChartValues,availabilityMessage}=load('lib/chart-availability.ts');
test('ECharts null rows are empty; scalar, tuple, object and real zero are valid',()=>{
 for(const data of [[],[null,undefined],[['2020-01-01',null]],[{value:[0,null]}]])assert.equal(hasChartValues({series:[{data}]}),false);
 for(const data of [[0],[['2020-01-01',0]],[{value:[0,0,0]}],['4.25']])assert.equal(hasChartValues({series:[{data}]}),true);
});
test('empty reasons preserve source, vintage, filters and transform distinctions in both languages',()=>{
 const {translate}=load('lib/presentation.ts');
 const states=['NEEDS_SYNC','HISTORICAL_VINTAGE_UNAVAILABLE','NO_OBSERVATIONS_IN_RANGE','NO_CLOSED_PERIODS','INSUFFICIENT_TRANSFORM_DATA','SOURCE_VALUES_MISSING'];
 assert.equal(new Set(states.map(status=>availabilityMessage({status}))).size,states.length);
 for(const status of states){const message=availabilityMessage({status});assert.notEqual(translate(message,'zh-CN'),message);assert.equal(translate(message,'en-US'),message);}
});

test('mounted chart clears its empty state when real observations arrive and rebinds after locale/theme changes',async()=>{
 const {JSDOM}=require('jsdom'),React=require('react'),{act}=React;
 const dom=new JSDOM('<html><body><div id="root"></div></body></html>',{url:'http://localhost'}),saved=new Map();
 const media={matches:false,addEventListener(){},removeEventListener(){}};
 for(const [key,value] of Object.entries({window:dom.window,document:dom.window.document,navigator:dom.window.navigator,localStorage:dom.window.localStorage,matchMedia:()=>media,ResizeObserver:class{observe(){}disconnect(){}},IS_REACT_ACT_ENVIRONMENT:true,addEventListener(){},removeEventListener(){}})){saved.set(key,Object.getOwnPropertyDescriptor(globalThis,key));Object.defineProperty(globalThis,key,{value,configurable:true,writable:true});}
 let last,initializations=0,disposals=0;const instance={on(){},off(){},isDisposed:()=>false,resize(){},getWidth:()=>800,getOption:()=>last,setOption(o){last=o},dispose(){disposals++}};
 const mocks={'echarts/core':{use(){},init(){initializations++;return instance}},'echarts/charts':{},'echarts/components':{},'echarts/renderers':{}},cache=new Map();
 const provider=load('components/presentation-provider.tsx',mocks,cache),{WorkspaceChart}=load('components/workspace-chart.tsx',mocks,cache),{Preferences}=load('components/preferences.tsx',mocks,cache);
 const root=require('react-dom/client').createRoot(document.querySelector('#root'));
 const tree=data=>React.createElement(provider.PresentationProvider,{initialLocale:'en-US',initialTheme:'light'},React.createElement(Preferences),React.createElement(WorkspaceChart,{title:'Unemployment',footnote:'FRED',label:'Chart',emptyReason:availabilityMessage({status:'NO_OBSERVATIONS_IN_RANGE'}),option:{xAxis:{type:'time'},series:[{name:'Unemployment',type:'line',data}]}}));
 try{
  await act(async()=>root.render(tree([['2026-10-01',null]])));assert.match(document.querySelector('[role=status]').textContent,/Stored data exists/);
  await act(async()=>root.render(tree([['2026-10-01',0]])));assert.equal(document.querySelector('[role=status]'),null);assert.equal(last.series[0].data[0][1],0);
  for(const theme of ['light','dark'])for(const locale of ['zh-CN','en-US']){
   await act(async()=>{for(const [index,value] of [[0,theme],[1,locale]]){const el=document.querySelectorAll('select')[index];el.value=value;el.dispatchEvent(new dom.window.Event('change',{bubbles:true}));}});
   assert.equal(document.documentElement.dataset.theme,theme);assert.equal(document.documentElement.lang,locale);assert.equal(last.series[0].data[0][1],0);
  }
  assert.equal(initializations,1);assert.equal(disposals,0);
 }finally{await act(async()=>root.unmount());dom.window.close();for(const [key,value] of saved)if(value)Object.defineProperty(globalThis,key,value);else delete globalThis[key];}
 assert.equal(disposals,1);
});
