"use client";
import {createContext,useCallback,useContext,useEffect,useMemo,useState,type ReactNode} from 'react';
import {validLocale,validTheme,translate,formatDate,formatNumber,type Locale,type Theme} from '@/lib/presentation';
type UI={locale:Locale;theme:Theme;resolvedTheme:'light'|'dark';setLocale:(l:Locale)=>void;setTheme:(t:Theme)=>void;t:(key:string,params?:Record<string,string|number>)=>string;tx:<T>(value:T)=>T;date:(v:string|Date|null|undefined,tz?:string,time?:boolean)=>string;number:(v:number|null|undefined,digits?:number)=>string};
const UIContext=createContext<UI|null>(null);
export function PresentationProvider({children,initialLocale,initialTheme}:{children:ReactNode;initialLocale:Locale;initialTheme:Theme}){
 const [locale,setLocaleState]=useState(initialLocale),[theme,setThemeState]=useState(initialTheme),[resolvedTheme,setResolved]=useState<'light'|'dark'>(()=>typeof document!=='undefined'&&document.documentElement.dataset.theme==='light'?'light':initialTheme==='light'?'light':'dark');
 const persist=(key:string,value:string)=>{try{localStorage.setItem('macro-'+key,value)}catch{}document.cookie=`macro-${key}=${value}; Path=/; Max-Age=31536000; SameSite=Lax`;};
 const setLocale=useCallback((value:Locale)=>{setLocaleState(value);persist('locale',value);},[]);
 const setTheme=useCallback((value:Theme)=>{setThemeState(value);persist('theme',value);},[]);
 useEffect(()=>{const media=matchMedia('(prefers-color-scheme: dark)');const apply=()=>{const resolved=theme==='system'?(media.matches?'dark':'light'):theme;document.documentElement.dataset.theme=resolved;document.documentElement.classList.toggle('dark',resolved==='dark');document.documentElement.style.colorScheme=resolved;setResolved(resolved);};apply();media.addEventListener('change',apply);return()=>media.removeEventListener('change',apply)},[theme]);
 useEffect(()=>{document.documentElement.lang=locale;},[locale]);
 useEffect(()=>{const sync=(event:StorageEvent)=>{if(event.key==='macro-theme'){const v=validTheme(event.newValue);setThemeState(v);document.cookie=`macro-theme=${v}; Path=/; Max-Age=31536000; SameSite=Lax`;}if(event.key==='macro-locale'){const v=validLocale(event.newValue)||initialLocale;setLocaleState(v);document.cookie=`macro-locale=${v}; Path=/; Max-Age=31536000; SameSite=Lax`;}};addEventListener('storage',sync);return()=>removeEventListener('storage',sync)},[initialLocale]);
 const value=useMemo<UI>(()=>{const t=(key:string,params:Record<string,string|number>={})=>translate(key,locale,params);return {locale,theme,resolvedTheme,setLocale,setTheme,t,tx:<T,>(v:T):T=>(typeof v==='string'?t(v):v) as T,date:(v,tz,time)=>formatDate(v,locale,tz,time),number:(v,digits)=>formatNumber(v,locale,digits)}},[locale,theme,resolvedTheme,setLocale,setTheme]);
 return <UIContext.Provider value={value}>{children}</UIContext.Provider>
}
export function useUI(){const value=useContext(UIContext);if(!value)throw new Error('PresentationProvider missing');return value;}
