import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),load=require('./ts-runtime.cjs');
const React=require('react'),{act}=React,{JSDOM}=require('jsdom');

test('Fed real component: success → 503 → 200 clears error and retains year selection',async()=>{
 const dom=new JSDOM('<div id="root"></div>',{url:'http://localhost/fed'});
 const saved=new Map();for(const k of ['window','document','navigator','IS_REACT_ACT_ENVIRONMENT'])saved.set(k,Object.getOwnPropertyDescriptor(globalThis,k));
 for(const [k,v]of Object.entries({window:dom.window,document:dom.window.document,navigator:dom.window.navigator,IS_REACT_ACT_ENVIRONMENT:true}))Object.defineProperty(globalThis,k,{value:v,configurable:true,writable:true});
 let fail=false,calls=0;
 const overview={meetings:[],recent:null,next:null,last_change:null,coverage:{},latest_statement:null,latest_sep:null,natural_release_validation:'PENDING_REAL_RELEASE_VALIDATION'};
 const t=k=>k,tx=x=>x;
 const mocks={'next/link':({children,...p})=>React.createElement('a',p,children),'./presentation-provider':{useUI:()=>({t,tx,number:String,date:String,locale:'en-US'})},'./research-shell':{ResearchShell:({children})=>React.createElement('main',null,children)},'./workspace-chart':{WorkspaceChart:()=>null},'./ui/button':{Button:({children,...props})=>React.createElement('button',props,children)},'@/lib/workspace-utils':{today:()=> '2026-11-16',request:async()=>{calls++;if(fail)throw new Error('AUDIT_SINGLE_TRANSIENT_503');return structuredClone(overview)}}};
 const {FedTerminal}=load(process.env.FED_RECOVERY_SOURCE||'components/fed-terminal.tsx',mocks);const {createRoot}=require('react-dom/client');const root=createRoot(document.querySelector('#root'));
 const click=async label=>act(async()=>Array.from(document.querySelectorAll('button')).find(b=>b.textContent===label).click());
 try{
  await act(async()=>root.render(React.createElement(FedTerminal,{view:'overview'})));
  const year=Array.from(document.querySelectorAll('select')).find(s=>s.parentElement.textContent.startsWith('Year'));
  await act(async()=>{year.value='2025';year.dispatchEvent(new dom.window.Event('change',{bubbles:true}));});
  fail=true;await click('Refresh');assert.match(document.querySelector('[role=alert]').textContent,/503/);
  fail=false;await click('Retry');assert(!document.querySelector('[role=alert]'),'a successful recovery must clear the old error');
  assert.equal(Array.from(document.querySelectorAll('select')).find(s=>s.parentElement.textContent.startsWith('Year')).value,'2025');assert(calls>=3);assert.match(document.body.textContent,/Meeting archive/);
 }finally{await act(async()=>root.unmount());dom.window.close();for(const [k,d]of saved){if(d)Object.defineProperty(globalThis,k,d);else delete globalThis[k];}}
});
