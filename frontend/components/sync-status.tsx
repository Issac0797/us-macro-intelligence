"use client";
import {useEffect,useState} from 'react';
import {request} from '@/lib/workspace-utils';
import {useUI} from './presentation-provider';
type State={series_id:string;state:string;latest_observation_date:string|null;last_successful_sync:string|null;last_attempt:string|null;next_scheduled_attempt:string|null;source_status:string};
export function SyncStatus({epoch}:{epoch:number}){
 const {t,tx,date}=useUI();const [rows,setRows]=useState<State[]>([]);const [error,setError]=useState('');
 useEffect(()=>{const a=new AbortController();request<{series_sync:State[]}>('monitor/status','GET',undefined,a.signal).then(r=>{if(!a.signal.aborted){setRows(r.series_sync||[]);setError('')}}).catch(e=>{if(!a.signal.aborted)setError(e.message)});return()=>a.abort()},[epoch]);
 return <details className="workspace-method"><summary>{t('Backend source synchronization')}</summary><p className="calendar-note">{t('A successful source check may contain no new observation. Browser refresh does not download FRED data.')}</p>{error&&<p role="alert">{tx(error)}</p>}<div className="table-scroll"><table><thead><tr>{['Series ID','Source status','Latest observation','Last successful backend sync','Last attempt','Next scheduled attempt'].map(k=><th key={k}>{tx(k)}</th>)}</tr></thead><tbody>{rows.map(r=><tr key={r.series_id}><td>{r.series_id}</td><td>{tx(r.state)} · {tx(r.source_status)}</td><td>{r.latest_observation_date?date(r.latest_observation_date):t('Not Available')}</td><td>{r.last_successful_sync?date(r.last_successful_sync,'UTC',true)+' UTC':t('Not Available')}</td><td>{r.last_attempt?date(r.last_attempt,'UTC',true)+' UTC':t('Not Available')}</td><td>{r.next_scheduled_attempt?date(r.next_scheduled_attempt,'UTC',true)+' UTC':t('Not Available')}</td></tr>)}</tbody></table></div></details>;
}
