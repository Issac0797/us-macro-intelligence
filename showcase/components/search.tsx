'use client';
import {useEffect,useMemo,useRef,useState} from 'react';
import {useUI} from '../shared/components/presentation-provider';
import {searchPublic} from '../lib/search';
import type {Series} from '../lib/research';
export function PublicSearch({series}:{series:Series[]}){
 const {locale}=useUI(),zh=locale==='zh-CN';const dialog=useRef<HTMLDialogElement>(null),input=useRef<HTMLInputElement>(null);const [open,setOpen]=useState(false),[query,setQuery]=useState(''),[active,setActive]=useState(0);
 const results=useMemo(()=>searchPublic(query,series,zh),[query,series,zh]);
 useEffect(()=>{const key=(e:KeyboardEvent)=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();setOpen(v=>!v)}};addEventListener('keydown',key);return()=>removeEventListener('keydown',key)},[]);
 useEffect(()=>{if(open){dialog.current?.showModal();input.current?.focus()}else dialog.current?.close()},[open]);
 return <><button className="search-trigger" onClick={()=>setOpen(true)}>{zh?'搜索页面 / 指标':'Search pages / series'} <kbd>Ctrl+K</kbd></button><dialog className="public-search" ref={dialog} onCancel={()=>setOpen(false)} aria-label={zh?'搜索页面和公开指标':'Search pages and public series'}><div className="search-header"><strong>{zh?'搜索公开快照':'Search public snapshots'}</strong><button onClick={()=>setOpen(false)}>{zh?'关闭':'Close'} · Esc</button></div><input ref={input} aria-label={zh?'搜索关键词':'Search query'} placeholder={zh?'输入 CPI、失业率或页面名称':'Type CPI, unemployment or a page'} value={query} onChange={e=>{setQuery(e.target.value);setActive(0)}} role="combobox" aria-expanded={open} aria-controls="public-search-results" aria-activedescendant={results[active]?'search-'+active:undefined} onKeyDown={e=>{if(e.key==='ArrowDown'){e.preventDefault();setActive(i=>Math.min(results.length-1,i+1))}if(e.key==='ArrowUp'){e.preventDefault();setActive(i=>Math.max(0,i-1))}if(e.key==='Enter'&&results[active])location.assign(results[active].url)}}/><div id="public-search-results" role="listbox">{results.map((r,i)=><a id={'search-'+i} key={r.url} href={r.url} role="option" aria-selected={i===active} onMouseEnter={()=>setActive(i)}><span>{r.label}</span><small>{r.detail}</small></a>)}{!results.length&&<p>{zh?'没有匹配的公开页面或指标。':'No matching public page or series.'}</p>}</div></dialog></>;
}
