import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),load=require('./ts-runtime.cjs'),React=require('react'),{act}=React,{JSDOM}=require('jsdom');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function mount(file,mocks,props={}){
 const dom=new JSDOM('<div id="root"></div>',{url:'http://localhost/workspace'}),saved=new Map();
 for(const [k,v]of Object.entries({window:dom.window,document:dom.window.document,navigator:dom.window.navigator,sessionStorage:dom.window.sessionStorage,IS_REACT_ACT_ENVIRONMENT:true})){
  saved.set(k,Object.getOwnPropertyDescriptor(globalThis,k));Object.defineProperty(globalThis,k,{value:v,configurable:true,writable:true});
 }
 dom.window.HTMLDialogElement.prototype.showModal=function(){this.open=true};dom.window.HTMLDialogElement.prototype.close=function(){this.open=false};
 const base={'next/link':({children,...p})=>React.createElement('a',p,children),'./presentation-provider':{useUI:()=>({t:k=>k,tx:v=>v,date:String,number:v=>String(v??'—'),locale:'en-US'})}};
 const exports=load(file,{...base,...mocks}),Component=exports.default||Object.values(exports).find(v=>typeof v==='function');
 const root=require('react-dom/client').createRoot(document.querySelector('#root'));
 await act(async()=>root.render(React.createElement(Component,props)));
 return {dom,root,render:async p=>act(async()=>root.render(React.createElement(Component,p))),close:async()=>{await act(async()=>root.unmount());dom.window.close();for(const[k,d]of saved){if(d)Object.defineProperty(globalThis,k,d);else delete globalThis[k];}}};
}
const click=async text=>act(async()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent===text);assert(b,'button '+text);b.click()});

test('palette Ctrl K, metadata debounce, Chinese/ID results, arrows/Enter, Escape and cancellation',async()=>{
 const calls=[],routes=[];
 const app=await mount('components/command-palette.tsx',{'next/navigation':{useRouter:()=>({push:v=>routes.push(v)})},'@/lib/query-client':{invalidateResearch:async()=>{}},'@/lib/workspace-utils':{request:async(path,method,body,signal)=>{calls.push({path,signal});if(path==='workspaces')return {workspaces:[]};if(path==='fed/overview')return {meetings:[]};return {series:[{id:'PAYEMS',name:'All Employees, Total Nonfarm',short_name:'Nonfarm Payrolls'}]}}}});
 try{
  await act(async()=>{window.dispatchEvent(new app.dom.window.KeyboardEvent('keydown',{key:'k',ctrlKey:true,bubbles:true}));await pause(210)});
  assert(document.querySelector('dialog').open);assert.equal(document.activeElement.getAttribute('role'),'combobox');
  const input=document.querySelector('[role=combobox]');
  const change=async value=>act(async()=>{Object.getOwnPropertyDescriptor(app.dom.window.HTMLInputElement.prototype,'value').set.call(input,value);input.dispatchEvent(new app.dom.window.Event('input',{bubbles:true}));await pause(220)});
  await change('PAYEMS');assert.match(document.body.textContent,/PAYEMS.*Open Series/);assert(document.querySelector('mark'));
  await act(async()=>input.dispatchEvent(new app.dom.window.KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true})));
  await act(async()=>input.dispatchEvent(new app.dom.window.KeyboardEvent('keydown',{key:'Enter',bubbles:true})));
  assert.match(routes[0],/series=PAYEMS/);assert(!document.querySelector('dialog').open);
  assert(calls.filter(c=>c.path.includes('search')).every(c=>!c.path.includes('observations')));
  assert(calls.some(c=>c.signal.aborted),'superseded query signal is cancelled');
  await act(async()=>window.dispatchEvent(new app.dom.window.KeyboardEvent('keydown',{key:'k',ctrlKey:true,bubbles:true})));
  await act(async()=>pause(220));const beforeIME=calls.length;
  await act(async()=>input.dispatchEvent(new app.dom.window.CompositionEvent('compositionstart',{bubbles:true,data:''})));
  await change('fei');assert.equal(calls.length,beforeIME,'IME composition must not search intermediate text');
  await act(async()=>{Object.getOwnPropertyDescriptor(app.dom.window.HTMLInputElement.prototype,'value').set.call(input,'非农');input.dispatchEvent(new app.dom.window.CompositionEvent('compositionend',{bubbles:true,data:'非农'}));await pause(220)});
  assert.match(document.body.textContent,/PAYEMS/);
  await change('zzzzzzzz');assert.match(document.body.textContent,/No matching research results/);
  await act(async()=>document.querySelector('dialog').dispatchEvent(new app.dom.window.Event('cancel',{bubbles:true})));assert(!document.querySelector('dialog').open);
 }finally{await app.close()}
});

test('drawer retains exact PIT/native observation, lazy revisions/source links and rejects late responses',async()=>{
 const calls=[],pending=[];const selection={series_id:'PAYEMS',observation_date:'2023-01-01',observation_dates:['2023-01-01'],aligned_date:'2023-01-01',value:1,units:'Percent',data_mode:'vintage',as_of:'2023-06-15'};
 const details=period=>({series_id:'PAYEMS',name:'Payrolls',observation_date:period,value:123,units:'Thousands',frequency:'monthly',seasonal_adjustment:'SA',source:'ALFRED',source_url:'https://alfred.stlouisfed.org/series?seid=PAYEMS',source_release_date:null,status:'AVAILABLE',historical_available:true,first_available_vintage:'2023-02-03',latest_available_vintage:'2023-06-02',initial_note:'Earliest ALFRED archive',precision_note:'Date precision',related_events:[]});
 const app=await mount('components/observation-drawer.tsx',{'./workspace-chart':{WorkspaceChart:()=>React.createElement('div',null,'Timeline')},'./workspace-actions':{WorkspaceActions:()=>null},'@/lib/workspace-utils':{request:(path,method,body,signal)=>{calls.push({path,signal});if(path.startsWith('revisions'))return Promise.resolve({observations:[{initial_value:120,revised_value:123,absolute_revision:3,initial_units:'Thousands',units:'Thousands',revision_units:'Thousands',timeline:[]}]});return new Promise(resolve=>pending.push({path,resolve}))}}},{selection,onClose:()=>{}});
 try{
  await app.render({selection:{...selection,observation_date:'2023-02-01',observation_dates:['2023-02-01']},onClose:()=>{}});
  await act(async()=>pending.filter(p=>p.path.includes('2023-02-01')).forEach(p=>p.resolve(details('2023-02-01'))));
  await act(async()=>pending.filter(p=>p.path.includes('2023-01-01')).forEach(p=>p.resolve(details('2023-01-01'))));
  assert.match(document.body.textContent,/2023-02-01/);assert(!document.querySelector('.point-facts').textContent.includes('2023-01-01'));
  assert(calls.every(c=>c.path.includes('data_mode=vintage')&&c.path.includes('as_of=2023-06-15')));
  assert(!calls.some(c=>c.path.startsWith('revisions')),'revisions are on demand');
  assert.match(document.body.textContent,/No explicitly linked release event/);
  assert(document.querySelector('a[href="https://alfred.stlouisfed.org/series?seid=PAYEMS"]'));
  assert(document.querySelector('a[href*="/revisions?"]').href.includes('as_of=2023-06-15'));
  await click('View Revision History');assert(calls.at(-1).path.includes('as_of=2023-06-15'));assert(calls.at(-1).path.includes('page_size=1'));assert.match(document.body.textContent,/Absolute Revision.*3/s);
 }finally{await app.close()}
});

test('historical revision page bounds both period and dashboard requests to URL as_of',async()=>{
 const calls=[];
 const app=await mount('components/revision-analysis.tsx',{'next/navigation':{useSearchParams:()=>new URLSearchParams('series=PAYEMS&period=2023-01-01&as_of=2023-06-15')},'next/dynamic':()=>()=>null,'./workspace-actions':{WorkspaceActions:()=>null},'./research-shell':{ResearchShell:({children})=>React.createElement('main',null,children)},'@/lib/calendar-types':{calendarFetch:async path=>{calls.push(path);return path.includes('/summary')?{heatmap:[],by_units:[],by_year:[],distribution:[],sample_count:0}:{observations:[]}}}});
 try{assert.equal(calls.length,2);assert(calls.every(p=>p.includes('as_of=2023-06-15')));assert(calls[0].includes('observation_date=2023-01-01'));}finally{await app.close()}
});

test('panel point click uses native dates; drag, resize and keyboard layout changes do not refetch data',async()=>{
 let chartOption;const requests=[],patches=[],moves=[],drops=[],selections=[];
 const config={title:'PAYEMS',configuration_version:1,start:'2023-01-01',end:'2023-06-15',data_mode:'vintage',as_of:'2023-06-15',frequency:'monthly',lines:[{key:'a',series_id:'PAYEMS',display_name:'PAYEMS',axis:'left',chart_type:'line',calculations:[{transform:'raw'}]}]};
 const panel={id:'stable-a',configuration:config,grid:{x:0,y:0,w:6,h:4},linked:true,independent:false,collapsed:false,zoom:null};
 const props={panel,library:[],globalLinked:true,sync:{update(){},register(){return()=>{}}},refresh:0,active:true,expanded:false,onActivate(){},onPatch:p=>patches.push(p),onConfiguration(){},onInspect:p=>selections.push(p),onMove:d=>moves.push(d),onDrop:s=>drops.push(s),onRemove(){},onDuplicate(){},onExpand(){}};
 const app=await mount('components/workspace-panel.tsx',{'@/lib/workspace-utils':{request:async(path)=>{requests.push(path);return {axes:{left:'Thousands',right:''},series:[{key:'a',series_id:'PAYEMS',display_name:'PAYEMS',units:'Thousands',axis:'left',points:[{date:'2023-01-01',value:155000,selected_observation_date:'2023-01-01',observation_dates:['2023-01-01']}]}]}}},'@/lib/query-client':{requestMetadata:()=>null},'./refresh-status':{RefreshStatus:()=>null},'./workspace-chart':{WorkspaceChart:React.forwardRef(({onPoint,option},ref)=>{chartOption=option;return React.createElement('button',{onClick:()=>onPoint({seriesIndex:0,dataIndex:0})},'Canvas point')})}},props);
 try{
  assert.equal(chartOption.series[0].data[0][0],Date.parse('2023-01-01'));assert.equal(chartOption.xAxis.min,Date.parse(config.start));
  await click('Canvas point');assert.equal(selections[0].observation_date,'2023-01-01');assert.equal(selections[0].as_of,'2023-06-15');assert.equal(selections[0].value,155000);
  await click('Move chart down');assert.deepEqual(moves,[1]);
  const article=document.querySelector('article'),drop=new app.dom.window.Event('drop',{bubbles:true});Object.defineProperty(drop,'dataTransfer',{value:{getData:()=> 'stable-b'}});
  await act(async()=>article.dispatchEvent(drop));assert.deepEqual(drops,['stable-b']);
  const resize=document.querySelector('[aria-label="Resize chart"]');resize.setPointerCapture=()=>{};
  const pointer=(type,x,y)=>{const event=new app.dom.window.MouseEvent(type,{bubbles:true,clientX:x,clientY:y});Object.defineProperty(event,'pointerId',{value:1});resize.dispatchEvent(event)};
  await act(async()=>pointer('pointerdown',0,0));await act(async()=>pointer('pointerup',100,110));assert.equal(patches.at(-1).grid.w,7);assert.equal(patches.at(-1).grid.h,5);
  await app.render({...props,panel:{...panel,zoom:{start:'2023-02-01',end:'2023-05-01'},grid:{x:0,y:0,w:7,h:5}},cursor:{date:'2023-02-01',available:false}});
  assert.equal(requests.length,1);assert.match(document.body.textContent,/No Observation/);
 }finally{await app.close()}
});
