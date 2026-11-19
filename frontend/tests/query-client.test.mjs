import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),load=require('./ts-runtime.cjs');
const {researchRequest:request,researchClient,queryKey,invalidateResearch,policy,requestMetadata}=load('lib/query-client.ts');
const original=globalThis.fetch;
const response=(data,status=200,headers={})=>new Response(JSON.stringify(data),{status,headers});
test.afterEach(()=>{globalThis.fetch=original;researchClient.clear()});

test('identical subscribers share one request and cannot mutate each other',async()=>{
 let calls=0,release;globalThis.fetch=()=>{calls++;return new Promise(r=>release=r)};
 const a=request('overview'),b=request('overview');release(response({v:[1]}));const [x,y]=await Promise.all([a,b]);
 assert.equal(calls,1);x.v.push(2);assert.deepEqual(y,{v:[1]});assert.deepEqual(await request('overview'),{v:[1]});assert.equal(calls,1);
});
test('keys canonicalize parameter order and isolate vintage date, rules and transforms',()=>{
 assert.deepEqual(queryKey('x?b=2&a=1','POST',{z:2,a:1}),queryKey('x?a=1&b=2','POST',{a:1,z:2}));
 assert.notDeepEqual(queryKey('x?as_of=2020-01-01'),queryKey('x?as_of=2020-02-01'));
 assert.notDeepEqual(queryKey('x','POST',{transform:'yoy'}),queryKey('x','POST',{transform:'raw'}));
 assert(policy('vintages/PAYEMS').staleTime>policy('overview').staleTime);
});
test('503 retries are bounded and a recovered 200 replaces the failed result',async()=>{
 let calls=0;globalThis.fetch=async()=>++calls<3?response({detail:'temporary'},503):response({ok:true});
 assert.deepEqual(await request('fed/overview'),{ok:true});assert.equal(calls,3);
});
test('400/401/403/404 do not retry; errors do not poison success cache',async()=>{
 for(const status of [400,401,403,404]){let calls=0;globalThis.fetch=async()=>{calls++;return response({detail:'invalid'},status)};await assert.rejects(request('series/error'+status));assert.equal(calls,1);globalThis.fetch=async()=>response({ok:true});assert.deepEqual(await request('series/error'+status),{ok:true});}
});
test('Retry-After beyond the bounded retry budget is not retried early',async()=>{
 let calls=0;globalThis.fetch=async()=>{calls++;return response({detail:'rate limit'},429,{'Retry-After':'20'})};
 await assert.rejects(request('overview'));assert.equal(calls,1);
});
test('cancelling one subscriber preserves the other; cancelled consumer receives no late response',async()=>{
 let release,upstream;globalThis.fetch=(_,{signal})=>{upstream=signal;return new Promise(r=>release=r)};
 const a=new AbortController(),b=new AbortController();const x=request('overview','GET',undefined,a.signal),y=request('overview','GET',undefined,b.signal);
 const rejected=assert.rejects(x,e=>e.name==='AbortError');a.abort();await rejected;assert(!upstream.aborted);release(response({ok:true}));assert.deepEqual(await y,{ok:true});
});
test('last subscriber cancellation releases the upstream request',async()=>{
 let upstream;globalThis.fetch=(_,{signal})=>{upstream=signal;return new Promise((_,reject)=>signal.addEventListener('abort',()=>reject(new DOMException('aborted','AbortError'))))};
 const a=new AbortController(),p=request('overview','GET',undefined,a.signal);const rejected=assert.rejects(p,e=>e.name==='AbortError');a.abort();await rejected;assert(upstream.aborted);
});
test('manual invalidation actually revalidates and stale filter responses cannot overwrite new keys',async()=>{
 let count=0;globalThis.fetch=async()=>response({value:++count});assert.equal((await request('overview')).value,1);await invalidateResearch(['overview']);assert.equal((await request('overview')).value,2);
 let slow;globalThis.fetch=path=>path.includes('old')?new Promise(r=>slow=r):Promise.resolve(response({value:'new'}));const old=request('x?filter=old'),fresh=await request('x?filter=new');slow(response({value:'old'}));await old;assert.equal(fresh.value,'new');assert.equal((await request('x?filter=new')).value,'new');
});
test('invalid JSON is an error, not cached as successful data',async()=>{
 let count=0;globalThis.fetch=async()=>{count++;return new Response('broken',{status:400})};await assert.rejects(request('bad-json'));assert.equal(count,1);
 globalThis.fetch=async()=>response({ok:true});assert.deepEqual(await request('bad-json'),{ok:true});
});
test('client cache has a finite entry limit',async()=>{
 globalThis.fetch=async()=>response({value:1});for(let i=0;i<110;i++)await request('series/'+i);
 assert(researchClient.getQueryCache().getAll().length<=96);
});

test('cache hits retain the actual network fetch time and identify cached reads',async()=>{
 let calls=0;globalThis.fetch=async()=>{calls++;return response({value:1})};const first=await request('overview');const second=await request('overview');
 assert.equal(calls,1);assert.equal(requestMetadata(first).cacheHit,false);assert.equal(requestMetadata(second).cacheHit,true);assert.equal(requestMetadata(first).fetchedAt,requestMetadata(second).fetchedAt);
});
test('recoverable failures expose last-good data with its original fetch time',async()=>{
 globalThis.fetch=async()=>response({value:7});const prior=await request('fed/overview');const stamp=requestMetadata(prior).fetchedAt;await invalidateResearch(['fed/']);globalThis.fetch=async()=>response({detail:'temporary'},503);
 await assert.rejects(request('fed/overview'),error=>{assert.deepEqual(error.lastGood,{value:7});assert.equal(requestMetadata(error.lastGood).fetchedAt,stamp);return true});
});

test('immediate resubscription after final cancellation starts a fresh request',async()=>{
 let calls=0;globalThis.fetch=(_,{signal})=>{calls++;return calls===1?new Promise((_,reject)=>signal.addEventListener('abort',()=>reject(new DOMException('aborted','AbortError')))):Promise.resolve(response({observations:[{date:'2026-10-01',value:4.1}]}));};
 const a=new AbortController(),old=request('series/UNRATE/observations','GET',undefined,a.signal);const cancelled=assert.rejects(old);a.abort();
 const fresh=request('series/UNRATE/observations');await cancelled;
 assert.equal((await fresh).observations[0].value,4.1);assert.equal(calls,2);
});

test('empty observations revalidate without discarding the normal populated cache',async()=>{
 let calls=0;globalThis.fetch=async()=>response({observations:++calls===1?[]:[{value:0}]});
 assert.deepEqual((await request('series/UNRATE/observations')).observations,[]);
 assert.equal((await request('series/UNRATE/observations')).observations[0].value,0);
 await request('series/UNRATE/observations');assert.equal(calls,2);
});

test('explicit refresh detaches a cancelled in-flight query before the replacement subscribes',async()=>{
 let calls=0;globalThis.fetch=(_,{signal})=>++calls===1?new Promise((_,reject)=>signal.addEventListener('abort',()=>reject(new DOMException('aborted','AbortError')))):Promise.resolve(response({value:8}));
 const old=request('yield-curve');const cancelled=assert.rejects(old);await invalidateResearch(['yield-curve']);
 assert.deepEqual(await request('yield-curve'),{value:8});await cancelled;assert.equal(calls,2);
});

test('empty chart POST revalidates; populated data and vintage keys remain isolated',async()=>{
 let calls=0;globalThis.fetch=async()=>response({series:[{points:++calls===1?[{value:null}]:[{value:0}]}]});
 const cfg={data_mode:'latest',as_of:null};await request('workspace/chart-data','POST',cfg);
 assert.equal((await request('workspace/chart-data','POST',cfg)).series[0].points[0].value,0);
 await request('workspace/chart-data','POST',cfg);assert.equal(calls,2);
 await request('workspace/chart-data','POST',{data_mode:'vintage',as_of:'2023-06-15'});assert.equal(calls,3);
});
