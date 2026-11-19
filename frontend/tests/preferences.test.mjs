import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);const load=require('./ts-runtime.cjs');const React=require('react');const {act}=React;
const {JSDOM}=require('jsdom');
test('live preferences: persistence, cross-tab events, system changes, research state and chart lifecycle',async()=>{
 const dom=new JSDOM('<!doctype html><html lang="en-US"><body><div id="root"></div></body></html>',{url:'http://localhost'});const saved=new Map();
 for(const key of ['window','document','navigator','localStorage','matchMedia','ResizeObserver','IS_REACT_ACT_ENVIRONMENT'])saved.set(key,Object.getOwnPropertyDescriptor(globalThis,key));
 const media=new dom.window.EventTarget();media.matches=false;media.addEventListener=media.addEventListener.bind(media);media.removeEventListener=media.removeEventListener.bind(media);
 class Observer{observe(){}disconnect(){}}
 for(const [key,value] of Object.entries({window:dom.window,document:dom.window.document,navigator:dom.window.navigator,localStorage:dom.window.localStorage,matchMedia:()=>media,ResizeObserver:Observer,IS_REACT_ACT_ENVIRONMENT:true}))Object.defineProperty(globalThis,key,{value,configurable:true,writable:true});
 const savedAdd=globalThis.addEventListener,savedRemove=globalThis.removeEventListener;globalThis.addEventListener=dom.window.addEventListener.bind(dom.window);globalThis.removeEventListener=dom.window.removeEventListener.bind(dom.window);
 let initCount=0,disposeCount=0,lastOption=undefined;const imageOptions=[];const instance={on(){},off(){},isDisposed:()=>false,resize(){},getWidth:()=>800,getOption:()=>lastOption,setOption(o){lastOption=o},dispose(){disposeCount++},getDataURL(o){imageOptions.push(o);return 'data:image/png;base64,aGVsbG8=';}};
 const mocks={'echarts/core':{init(){initCount++;return instance},use(){}},'echarts/charts':{},'echarts/components':{},'echarts/renderers':{}};const cache=new Map();const provider=load('components/presentation-provider.tsx',mocks,cache);const {Preferences}=load('components/preferences.tsx',mocks,cache);const {WorkspaceChart}=load('components/workspace-chart.tsx',mocks,cache);const ref=React.createRef();
 globalThis.URL.createObjectURL=()=> 'blob:test';globalThis.URL.revokeObjectURL=()=>{};dom.window.HTMLAnchorElement.prototype.click=function(){};
 const config={data_mode:'vintage',as_of:'2023-06-15',frequency:'monthly',lines:[{series_id:'PAYEMS',axis:'left',calculations:[{transform:'yoy'}]}]};const original=JSON.stringify(config);
 function Research(){const {t}=provider.useUI();const [count,setCount]=React.useState(0);return React.createElement('section',null,React.createElement('button',{id:'increment',onClick:()=>setCount(n=>n+1)},'keep'),React.createElement('output',{id:'state'},count+' '+JSON.stringify(config)),React.createElement('p',{id:'label'},t('Historical Snapshot')),React.createElement(WorkspaceChart,{ref,title:'Dot Plot',footnote:'Source',label:'Dot Plot',option:{xAxis:{type:'time'},series:[{type:'line',name:'Core PCE',data:[['2023-01-01',1]]}]}}));}
 const {createRoot}=require('react-dom/client');let root=createRoot(document.querySelector('#root'));
 const tree=()=>React.createElement(provider.PresentationProvider,{initialLocale:'en-US',initialTheme:'system'},React.createElement(Preferences),React.createElement(Research));
 const select=async(index,value)=>{await act(async()=>{const e=document.querySelectorAll('select')[index];e.value=value;e.dispatchEvent(new dom.window.Event('change',{bubbles:true}));});};
 try{
  await act(async()=>root.render(tree()));assert.equal(document.documentElement.dataset.theme,'light');assert.equal(initCount,1);
  await act(async()=>document.querySelector('#increment').click());lastOption.dataZoom=[{type:'inside',start:22,end:67},{type:'slider',start:22,end:67}];
  await select(0,'dark');assert.equal(document.documentElement.dataset.theme,'dark');assert.equal(localStorage.getItem('macro-theme'),'dark');assert.match(document.cookie,/macro-theme=dark/);assert.equal(lastOption.dataZoom[0].start,22);assert.equal(lastOption.dataZoom[0].end,67);
  await select(1,'zh-CN');assert.equal(document.documentElement.lang,'zh-CN');assert.equal(document.querySelector('#label').textContent,'历史时点快照');assert.equal(localStorage.getItem('macro-locale'),'zh-CN');assert.match(document.querySelector('#state').textContent,/^1 /);assert.equal(JSON.stringify(config),original);assert.equal(initCount,1);assert.equal(disposeCount,0);
  await act(async()=>ref.current.exportPng());assert.equal(imageOptions.at(-1).backgroundColor,'#121e30');
  await select(0,'light');await act(async()=>ref.current.exportPng());assert.equal(imageOptions.at(-1).backgroundColor,'#ffffff');
  await select(0,'system');await act(async()=>{media.matches=true;media.dispatchEvent(new dom.window.Event('change'));});assert.equal(document.documentElement.dataset.theme,'dark');await act(async()=>{media.matches=false;media.dispatchEvent(new dom.window.Event('change'));});assert.equal(document.documentElement.dataset.theme,'light');
  await act(async()=>window.dispatchEvent(new dom.window.StorageEvent('storage',{key:'macro-locale',newValue:'en-US'})));assert.equal(document.documentElement.lang,'en-US');assert.equal(document.querySelector('#label').textContent,'Historical Snapshot');
  await select(0,'dark');await select(1,'zh-CN');await act(async()=>root.unmount());assert.equal(disposeCount,1);
  const localeCookie=document.cookie.match(/macro-locale=([^;]+)/)[1],themeCookie=document.cookie.match(/macro-theme=([^;]+)/)[1];root=createRoot(document.querySelector('#root'));await act(async()=>root.render(React.createElement(provider.PresentationProvider,{initialLocale:localeCookie,initialTheme:themeCookie},React.createElement(Preferences),React.createElement(Research))));assert.equal(document.querySelectorAll('select')[0].value,'dark');assert.equal(document.querySelectorAll('select')[1].value,'zh-CN');assert.equal(document.documentElement.dataset.theme,'dark');
 }finally{await act(async()=>root.unmount());dom.window.close();for(const [k,d] of saved){if(d)Object.defineProperty(globalThis,k,d);else delete globalThis[k];}globalThis.addEventListener=savedAdd;globalThis.removeEventListener=savedRemove;}
});
