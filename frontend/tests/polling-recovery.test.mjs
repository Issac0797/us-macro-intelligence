import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),load=require('./ts-runtime.cjs'),React=require('react'),{act}=React,{JSDOM}=require('jsdom');
test('actual polling component recovers network/timeout/502/503, pauses hidden, revalidates on activation and cleans up',async()=>{
 const dom=new JSDOM('<div id="root"></div>',{url:'http://localhost'}),saved=new Map();
 for(const k of ['window','document','navigator','IS_REACT_ACT_ENVIRONMENT','Event','fetch','setInterval','clearInterval'])saved.set(k,Object.getOwnPropertyDescriptor(globalThis,k));
 let callback,cleared=0,requests=0,invalidations=0,updates=0,visibility='visible';
 Object.defineProperty(dom.window.document,'visibilityState',{get:()=>visibility,configurable:true});
 const responses=[{version:'a'},503,new TypeError('network disconnected'),502,new DOMException('timeout','TimeoutError'),{version:'a'},{version:'b'}];
 const fetch=async()=>{requests++;const value=responses.shift()??{version:'b'};if(value instanceof Error)throw value;return {ok:typeof value!=='number',json:async()=>value}};
 for(const [key,value]of Object.entries({window:dom.window,document:dom.window.document,navigator:dom.window.navigator,IS_REACT_ACT_ENVIRONMENT:true,Event:dom.window.Event,fetch,setInterval:fn=>(callback=fn,42),clearInterval:()=>cleared++}))Object.defineProperty(globalThis,key,{value,configurable:true,writable:true});
 dom.window.addEventListener('macro-data-version',()=>updates++);
 const {DataRevalidation}=load('components/data-revalidation.tsx',{'@/lib/query-client':{invalidateResearch:async()=>invalidations++}});
 const {createRoot}=require('react-dom/client');const root=createRoot(document.querySelector('#root'));
 try{
  await act(async()=>root.render(React.createElement(DataRevalidation)));assert.equal(requests,1);
  for(let i=0;i<5;i++)await act(async()=>callback());assert.equal(updates,0);assert.equal(requests,6);
  visibility='hidden';await act(async()=>callback());assert.equal(requests,6);
  visibility='visible';await act(async()=>document.dispatchEvent(new dom.window.Event('visibilitychange')));assert.equal(updates,1);assert.equal(invalidations,1);
  await act(async()=>root.unmount());assert.equal(cleared,1);
 }finally{dom.window.close();for(const [k,d]of saved){if(d)Object.defineProperty(globalThis,k,d);else delete globalThis[k];}}
});
