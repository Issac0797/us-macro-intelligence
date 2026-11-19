"use client";
import {useUI} from "./presentation-provider";
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { calendarFetch, Release, releaseTime } from '@/lib/calendar-types';
export function ReleaseWidgets({refreshEpoch=0}:{refreshEpoch?:number}) {
    const { t, tx, locale, date: uiDate, number: uiNumber } = useUI(); const releaseTime=(v:string|null|undefined,zone:string)=>uiDate(v,zone,true);
    const [upcoming, setUpcoming] = useState<Release[]>([]), [latest, setLatest] = useState<Release[]>([]), [error, setError] = useState('');
    useEffect(() => { const abort = new AbortController(); const load = () => Promise.all([calendarFetch<{
            events: Release[];
        }>('calendar/upcoming', abort.signal), calendarFetch<{
            events: Release[];
        }>('calendar?status=Released&confirmed_only=true&order=desc&limit=5', abort.signal)]).then(([a, b]) => { setUpcoming(a.events); setLatest(b.events); setError(''); }).catch(e => { if (!abort.signal.aborted)
        setError(e.message); }); load(); const timer = setInterval(load, 60000); return () => { abort.abort(); clearInterval(timer); }; }, [refreshEpoch]);
    return <div className="release-widgets">{tx([["Upcoming Economic Releases", upcoming], ["Latest Data Releases", latest]].map(([title, items]) => <section className="release-widget" key={String(title)}><div className="panel-kicker">{t("RELEASE MONITOR \u00B7 NEW YORK TIME")}</div><h2>{tx(String(title))}</h2>{tx(error ? <p role="alert">{tx(error)}</p> : (items as Release[]).length ? (items as Release[]).map(e => <Link href={`/calendar?event=${e.id}`} key={e.id}><span>{tx(e.release_name)}</span><small>{tx(e.scheduled_at ? releaseTime(e.scheduled_at, 'America/New_York') : e.scheduled_date + ' · time unknown')} · {tx(e.status)}</small></Link>) : <p>{t("No verified") + " "}{tx(title === 'Upcoming Economic Releases' ? 'upcoming events' : 'data updates detected yet')}. <Link href="/calendar">{t("Open calendar \u2192")}</Link></p>)}</section>))}</div>;
}
