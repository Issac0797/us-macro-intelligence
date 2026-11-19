"use client";
import {useUI} from './presentation-provider';
import {Button} from './ui/button';

export function RefreshStatus({busy,error,hasData,lastFetch,retry,empty=false,statusCode=0,cached=false}:{busy:boolean;error:string;hasData:boolean;lastFetch:string|null;retry:()=>void;empty?:boolean;statusCode?:number;cached?:boolean}){
 const {t,tx,date}=useUI();
 const state=error?(hasData?'stale':[400,401,403,404,422].includes(statusCode)?'unrecoverable-error':'recoverable-error'):busy?(hasData?'refreshing':'initial-loading'):empty?'empty':'success';
 return <div className="refresh-status" data-state={state} aria-busy={busy}>
  {error?<div className="error-box" role="alert"><span>{hasData?t('Showing last successful data; refresh failed.'):t('Unable to load data.')} {tx(error)}</span><Button variant="outline" disabled={busy||[400,401,403,404,422].includes(statusCode)} onClick={retry}>{t('Retry')}</Button></div>:busy&&hasData?<p role="status">{t('Refreshing in background…')}</p>:null}
  {cached&&<p className="calendar-note">{t('Served from shared query cache')}</p>}
  {lastFetch&&<p className="calendar-note">{t('Last successful frontend fetch')}: {date(lastFetch,'UTC',true)} UTC · {t('Fetch time is not the source release time.')}</p>}
 </div>;
}
