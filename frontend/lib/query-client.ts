import {QueryClient} from '@tanstack/react-query';

export class DataError extends Error {
 constructor(message:string,public status=0,public retryAfter=0,public requestId=''){super(message);}
}
export const researchClient=new QueryClient({defaultOptions:{queries:{gcTime:5*60_000,retry:false,refetchOnWindowFocus:false}}});
const metadata=new WeakMap<object,{fetchedAt:string|null;cacheHit:boolean}>();
export const requestMetadata=(data:unknown)=>data&&typeof data==='object'?metadata.get(data as object):undefined;
const active=new Map<string,{key:readonly unknown[];promise:Promise<unknown>;users:number;controller:AbortController;networked:()=>boolean}>();
const canonical=(v:unknown):unknown=>Array.isArray(v)?v.map(canonical):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=>[k,canonical(v)])):v;
export function queryKey(path:string,method='GET',body?:unknown){const [base,search='']=path.split('?');const q=new URLSearchParams(search);q.sort();return ['research',method,base+(q.size?'?'+q:''),canonical(body??null)] as const;}
export function policy(path:string){
 if(/workspaces/.test(path))return {staleTime:0,gcTime:60_000};
 if(/calendar|releases/.test(path))return {staleTime:15_000,gcTime:120_000};
 if(/historical|vintages|revisions/.test(path)||path.includes('data_mode=vintage'))return {staleTime:300_000,gcTime:600_000};
 if(/fed\/meetings\//.test(path))return {staleTime:300_000,gcTime:600_000};
 if(/overview|business-cycle|recession-indicators|fed\//.test(path))return {staleTime:15_000,gcTime:120_000};
 return {staleTime:60_000,gcTime:300_000};
}
export async function invalidateResearch(prefixes:string[]=[]){
 const predicate=(q:{queryKey:readonly unknown[]})=>q.queryKey[0]==='research'&&(!prefixes.length||prefixes.some(p=>String(q.queryKey[2]).startsWith(p)));
 for(const [hash,flight] of active){if(predicate({queryKey:flight.key})){active.delete(hash);flight.controller.abort();}}
 await researchClient.cancelQueries({predicate});
 await researchClient.invalidateQueries({predicate,refetchType:'none'});
}

// Empty successes are transient: a sync or archive completion must be visible on
// the next read. Populated results retain the Phase A cache policy and limits.
function emptyResult(data:any):boolean {
 if(!data||typeof data!=='object')return false;
 if(Array.isArray(data.observations))return !data.observations.some((p:any)=>p.value!=null);
 if(Array.isArray(data.series)&&data.series.every((s:any)=>Array.isArray(s.points)||Array.isArray(s.values)))return !data.series.some((s:any)=>(s.points||s.values).some((p:any)=>typeof p==='object'&&p!==null?p.value!=null:p!=null));
 if(Array.isArray(data.cards))return !data.cards.some((c:any)=>c.value!=null);
 return false;
}

function prune(){
 const all=researchClient.getQueryCache().getAll().filter(q=>q.state.fetchStatus!=='fetching').sort((a,b)=>a.state.dataUpdatedAt-b.state.dataUpdatedAt);
 let bytes=all.reduce((n,q)=>n+JSON.stringify(q.state.data??null).length*2,0),count=all.length;
 for(const q of all){if(count<=96&&bytes<=24*1024*1024)break;bytes-=JSON.stringify(q.state.data??null).length*2;count--;researchClient.removeQueries({queryKey:q.queryKey,exact:true});}
}
export async function researchRequest<T>(path:string,method='GET',body?:unknown,signal?:AbortSignal):Promise<T>{
 if(signal?.aborted)throw new DOMException('Request cancelled','AbortError');
 const read=method==='GET'||method==='POST'&&/^(workspace\/(?:chart-data|validate)|analytics\/)/.test(path);
 const key=queryKey(path,method,body),hash=JSON.stringify(key);
 const execute=async (upstreamSignal:AbortSignal,attempt=0)=>{
  const id=crypto.randomUUID();let response:Response;
  try{response=await fetch('/api/v1/'+path,{method,headers:{'Content-Type':'application/json','X-Request-ID':id,'X-Retry-Count':String(attempt)},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store',signal:AbortSignal.any([upstreamSignal,AbortSignal.timeout(12_000)])});}
  catch(e){if(upstreamSignal.aborted)throw e;throw new DataError('Temporary network failure; retry.',0,0,id);}
  const retry=response.headers.get('Retry-After');const delay=retry?(Number.isFinite(Number(retry))?Number(retry)*1000:Math.max(0,Date.parse(retry)-Date.now())):0;
  const data=await response.json().catch(()=>{throw new DataError('Invalid data service response',response.ok?502:response.status,0,id)});
  if(!response.ok)throw new DataError(data.error?.message||data.detail||'Data service unavailable',response.status,delay,response.headers.get('X-Request-ID')||id);
  return data;
 };
 if(!read){const data=await execute(signal||new AbortController().signal);await invalidateResearch(['workspaces']);return data;}
 let flight=active.get(hash);
 if(!flight){
  const controller=new AbortController();let attempt=0,networked=false;const started=Date.now();
  const promise=researchClient.fetchQuery({...policy(path),staleTime:q=>emptyResult(q.state.data)?0:policy(path).staleTime,queryKey:key,
   queryFn:({signal:s})=>{networked=true;return execute(AbortSignal.any([s,controller.signal]),attempt++)},
   retry:(count,error)=>error instanceof DataError&&count<2&&Date.now()-started<15_000&&error.retryAfter<=5000&&([0,429,502,503,504].includes(error.status)),
   retryDelay:(count,error)=>Math.max(error instanceof DataError?error.retryAfter:0,Math.min(2000,250*2**count))});
  flight={key,promise,users:0,controller,networked:()=>networked};active.set(hash,flight);
  void promise.finally(()=>{if(active.get(hash)?.promise===promise)active.delete(hash);prune();}).catch(()=>{});
 }
 flight.users++;
 return new Promise<T>((resolve,reject)=>{
  let settled=false;const entry=flight!;
  const finish=()=>{if(settled)return false;settled=true;entry.users--;signal?.removeEventListener('abort',abort);return true;};
  const abort=()=>{if(!finish())return;reject(new DOMException('Request cancelled','AbortError'));if(entry.users===0){if(active.get(hash)===entry)active.delete(hash);entry.controller.abort();void researchClient.cancelQueries({queryKey:entry.key,exact:true});}};
  signal?.addEventListener('abort',abort,{once:true});
  entry.promise.then(data=>{if(!finish())return;const copy=structuredClone(data);const at=researchClient.getQueryState(entry.key)?.dataUpdatedAt;const meta={fetchedAt:at?new Date(at).toISOString():null,cacheHit:!entry.networked()};if(copy&&typeof copy==='object')metadata.set(copy,meta);resolve(copy as T)},error=>{if(!finish())return;const prior=researchClient.getQueryData(entry.key);if(prior!==undefined&&error instanceof Error){const old=structuredClone(prior);const at=researchClient.getQueryState(entry.key)?.dataUpdatedAt;if(old&&typeof old==='object')metadata.set(old,{fetchedAt:at?new Date(at).toISOString():null,cacheHit:true});Object.assign(error,{lastGood:old});}reject(error)});
 });
}
