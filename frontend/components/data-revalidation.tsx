"use client";
import {useEffect} from 'react';
import {invalidateResearch} from '@/lib/query-client';
export function DataRevalidation(){
 useEffect(()=>{let previous='',busy=false;const a=new AbortController();
  const check=async()=>{if(busy||document.visibilityState==='hidden')return;busy=true;try{const r=await fetch('/api/v1/data-version',{signal:a.signal,cache:'no-store'});if(!r.ok)return;const {version}=await r.json();if(previous&&previous!==version){await invalidateResearch();window.dispatchEvent(new Event('macro-data-version'));}previous=version;}catch{}finally{busy=false;}};
  void check();const timer=setInterval(check,30_000);const focus=()=>void check();window.addEventListener('focus',focus);document.addEventListener('visibilitychange',focus);return()=>{a.abort();clearInterval(timer);window.removeEventListener('focus',focus);document.removeEventListener('visibilitychange',focus)};
 },[]);return null;
}
