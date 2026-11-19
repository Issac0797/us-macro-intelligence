"use client";
import {useEffect,useState,useCallback} from 'react';
import {invalidateResearch} from './query-client';
export function useRevalidation(prefixes:string[]){
 const [epoch,setEpoch]=useState(0);const key=prefixes.join('|');
 const refresh=useCallback(()=>{void invalidateResearch(key.split('|')).then(()=>setEpoch(e=>e+1));},[key]);
 useEffect(()=>{const update=()=>{if(document.visibilityState!=='hidden')setEpoch(e=>e+1)};const visible=()=>{if(document.visibilityState!=='hidden')refresh()};window.addEventListener('macro-data-version',update);window.addEventListener('focus',visible);document.addEventListener('visibilitychange',visible);const timer=setInterval(update,60_000);return()=>{clearInterval(timer);window.removeEventListener('macro-data-version',update);window.removeEventListener('focus',visible);document.removeEventListener('visibilitychange',visible)};},[refresh]);
 return [epoch,refresh] as const;
}
