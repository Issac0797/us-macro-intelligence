"use client";
import {WorkspaceActions} from "./workspace-actions";
import {RefreshStatus} from "./refresh-status";
import {requestMetadata} from "@/lib/query-client";
import {useRevalidation} from "@/lib/use-revalidation";
import {availabilityMessage} from '@/lib/chart-availability';
import {SyncStatus} from "./sync-status";
import {TerminalFrame} from "./terminal-frame";
import {TerminalMetric} from "./terminal-metric";
import {useUI} from "./presentation-provider";
import {request} from "@/lib/workspace-utils";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { CalendarDays, ArrowUpRight, BarChart3, BookOpen, CircleAlert, Database, ExternalLink, Landmark, LayoutDashboard, LoaderCircle, RefreshCw, TrendingUp, Users } from "lucide-react";
import { ReleaseWidgets } from "@/components/release-widgets";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { MacroCard, ObservationResponse, Overview, number, transformNames, unitSuffix } from "@/lib/types";
const MacroChart = dynamic(() => import("./macro-chart"), { ssr: false, loading: () => <div className="chart-placeholder"><LoaderCircle className="animate-spin"/>Loading chart…</div> });
const navigation = [
    { id: "fed", label: "Fed Policy", icon: Landmark, kicker: "POLICY", title: "Fed Policy", description: "Official FOMC research" },
    { id: "analytics", label: "Macro Analytics", icon: BarChart3, kicker: "RESEARCH", title: "Analytics", description: "Macro research" },
    { id: "business-cycle", label: "Business Cycle", icon: TrendingUp, kicker: "RESEARCH", title: "Business Cycle", description: "Transparent cycle rules" },
    { id: "workspace", label: "Chart Workspace", icon: BarChart3, kicker: "RESEARCH", title: "Chart Workspace", description: "Multi-series chart research" },
    { id: "yield-curve", label: "Treasury Yield Curve", icon: Landmark, kicker: "RATES", title: "Treasury Yield Curve", description: "Treasury term structure" },
    { id: "historical-snapshot", label: "Historical Snapshot", icon: CalendarDays, kicker: "ALFRED", title: "Historical Snapshot", description: "Archived vintages" },
    { id: "revisions", label: "Revision Analysis", icon: TrendingUp, kicker: "ALFRED", title: "Revision Analysis", description: "Revision history" },
    { id: "calendar", label: "Economic Calendar", icon: CalendarDays, kicker: "RELEASE MONITOR", title: "Economic Calendar", description: "Official schedules and verified updates." },
    { id: "overview", label: "Overview", icon: LayoutDashboard, kicker: "THE BIG PICTURE", title: "U.S. economy at a glance", description: "The essential signals. One connected view of the U.S. economy." },
    { id: "inflation", label: "Inflation", icon: TrendingUp, kicker: "PRICES & PURCHASING POWER", title: "Tracking the inflation cycle", description: "Consumer prices and consumption deflators, beyond the headline." },
    { id: "labor", label: "Labor Market", icon: Users, kicker: "EMPLOYMENT & PARTICIPATION", title: "The pulse of the labor market", description: "Follow payroll growth and unemployment across the business cycle." },
    { id: "growth", label: "Growth", icon: BarChart3, kicker: "OUTPUT & ECONOMIC ACTIVITY", title: "Measuring economic momentum", description: "Real output, historical expansions, and the pace of U.S. growth." },
    { id: "monetary", label: "Monetary Policy", icon: Landmark, kicker: "RATES & POLICY TRANSMISSION", title: "The interest rate landscape", description: "Effective policy rates and the Treasury market’s term structure." },
];
const ranges = ["1Y", "3Y", "5Y", "10Y", "ALL"];
const preferred = ["CES0500000003", "JTSJOL", "RSAFS", "INDPRO", "CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE", "UNRATE", "PAYEMS", "GDPC1", "DFF", "DGS2", "DGS10"];
const api=<T,>(path:string,signal:AbortSignal)=>request<T>(path,'GET',undefined,signal);
function timestamp(value: string | null | undefined) {
    return value ? new Date(value).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }) + " UTC" : "Not collected";
}
export function Terminal({ section }: {
    section: string;
}) {
    const { t, tx, locale, date: uiDate, number: uiNumber } = useUI(); const timestamp=(v:string|null|undefined)=>uiDate(v,"UTC",true)+" UTC";
    useEffect(() => { const sid = new URLSearchParams(globalThis.window.location.search).get("series"); if (sid)
        setSelected(sid); }, []);
    const page = navigation.find(n => n.id === section) || navigation[0];
    const [overview, setOverview] = useState<Overview | null>(null);
    const [overviewError, setOverviewError] = useState("");
    const [refresh,refreshData]=useRevalidation(['overview','series/','calendar','monitor/']);
    const [lastFetch,setLastFetch]=useState<string|null>(null);
    const [busy, setBusy] = useState(true);
    const [selected, setSelected] = useState("");
    const [transform, setTransform] = useState("");
    const [range, setRange] = useState("5Y");
    const [window, setWindow] = useState(3);
    const [observations, setObservations] = useState<ObservationResponse | null>(null);
    const [chartBusy, setChartBusy] = useState(false);
    const lastChartKey=useRef('');
    const [chartError, setChartError] = useState("");
    const [collapsed, setCollapsed] = useState(false);
    useEffect(() => {
        const controller = new AbortController();
        setBusy(true);
        setOverviewError("");
        api<Overview>(`overview${section === "overview" ? "" : `?category=${section}`}`, controller.signal)
            .then(r=>{if(controller.signal.aborted)return;setOverview(r);setOverviewError('');setLastFetch(requestMetadata(r)?.fetchedAt||null)}).catch(error => { if (!controller.signal.aborted)
            setOverviewError(error.message); if(!controller.signal.aborted&&error.lastGood)setOverview(error.lastGood); })
            .finally(() => { if (!controller.signal.aborted)
            setBusy(false); });
        return () => controller.abort();
    }, [section, refresh]);
    // Treasury additions and helper indicators belong to the workspace; retain the original research universe here.
    const cards = useMemo(() => [...(overview?.cards || [])].filter(c => preferred.includes(c.series.id)).sort((a, b) => preferred.indexOf(a.series.id) - preferred.indexOf(b.series.id)), [overview]);
    const active = cards.find(c => c.series.id === selected) || cards[0];
    const currentTransform = transform || active?.transform || "raw";
    const choose = useCallback((card: MacroCard) => { setSelected(card.series.id); setTransform(""); }, []);
    useEffect(() => {
        if (!active)
            return;
        const controller = new AbortController();
        setChartBusy(true);
        setChartError("");
        const key=JSON.stringify([active.series.id,currentTransform,range,window]);
        if(lastChartKey.current!==key)setObservations(null);lastChartKey.current=key;

        const params = new URLSearchParams({ transform: currentTransform, limit: "100000", window: String(window) });
        if (range !== "ALL") {
            const start = new Date();
            start.setUTCFullYear(start.getUTCFullYear() - parseInt(range));
            params.set("start", start.toISOString().slice(0, 10));
        }
        api<ObservationResponse>(`series/${active.series.id}/observations?${params}`, controller.signal)
            .then(r=>{if(controller.signal.aborted)return;setObservations(r);setChartError('')}).catch(error => { if (!controller.signal.aborted)
            setChartError(error.message); })
            .finally(() => { if (!controller.signal.aborted)
            setChartBusy(false); });
        return () => controller.abort();
    }, [active?.series.id, currentTransform, range, window, refresh]);
    const validPoints = observations?.observations.filter(p => p.value !== null) || [];
    const latestPoint = validPoints.at(-1);
    const providers = Array.from(new Set(cards.map(c => c.provider).filter(Boolean)));
    const populated = cards.filter(c => c.value !== null).length;
    const isReady = overview && !overviewError && overview.data_status === "ready";
    return <TerminalFrame label={tx(page.label)} collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)}
      ready={!!isReady} status={tx(busy ? "CONNECTING" : overviewError ? "SERVICE OFFLINE" : isReady ? "DATA CONNECTED" : "DATA INCOMPLETE")}
      sidebarFooter={<><div className="source-box"><Database size={17}/><div><strong>{t("Built on public data")}</strong><p>{t("Federal Reserve Economic Data")}</p><a href="https://fred.stlouisfed.org/" target="_blank" rel="noreferrer">{t("Explore FRED") + " "}<ExternalLink size={11}/></a></div></div><div className="local-label"><span className="status-dot"/>{t("LOCAL WORKSPACE")}<span>{t("v0.1.0")}</span></div></>}
      statusFooter={<><span><span className="status-dot"/>{tx(overviewError ? "DATA SERVICE UNAVAILABLE" : "U.S. MACRO INTELLIGENCE")}<span className="strip-divider"/>{t("ITERATION 01")}</span><span>{t("View generated:") + " "}{tx(timestamp(overview?.generated_at))}</span></>}>
        <div className="page-heading"><div><div className="eyebrow">{tx(page.kicker)}</div><h1>{tx(page.title)}</h1><p>{tx(page.description)}</p></div><Button variant="outline" onClick={() => refreshData()} disabled={busy} title={t("Reload the database view; this does not trigger a FRED sync")}><RefreshCw size={14} className={busy ? "animate-spin" : ""}/>{t("Refresh view")}</Button></div>
        <RefreshStatus cached={requestMetadata(overview)?.cacheHit} busy={busy} error={overviewError} hasData={!!overview} lastFetch={lastFetch} retry={refreshData}/>
        <>{active&&<WorkspaceActions seriesIds={[active.series.id]} observationDate={active.observation_date||undefined}/>}</><div className="data-strip"><div><span className={cn("status-dot", populated === 0 && "muted-dot")}/><strong>{tx(providers.length ? providers.map(p => p === "fred_api" ? "FRED API" : "FRED public CSV").join(" + ") : "FRED DATA")}</strong><span className="strip-divider"/>{t("Native observations \u00B7 Validated transformations")}</div><span>{tx(populated)} / {tx(cards.length || "—")}{" " + t("series available")}</span></div>

        {tx(busy && !overview ? <div className="metrics-grid">{tx(Array.from({ length: 4 }, (_, i) => <div className="skeleton metric-skeleton" key={i}/>))}</div> : <div className="metrics-grid">{cards.map(card => <TerminalMetric
          key={card.series.id} id={tx(card.series.id)} label={tx(card.series.short_name)}
          value={tx(number(card.value, card.series.id === "PAYEMS" ? 0 : 2))} unit={tx(unitSuffix(card.units))}
          history={card.history.map(p => p.value)} selected={active?.series.id === card.series.id} onSelect={() => choose(card)}
          date={tx(card.observation_date?.slice(0, card.series.frequency === "daily" ? 10 : 7) || "No data")}
          method={<>{tx(transformNames[card.transform])}{tx(card.stale && <em title={t("Observation is older than the expected reporting cadence")}>{" " + t("\u00B7 Delayed")}</em>)}</>}
        />)}</div>)}
        {tx(!busy && overview?.data_status === "empty" && <div className="empty-box"><Database size={26}/><h2>{t("Your research workspace is ready")}</h2><p>{t("Import observations from FRED to populate these series. Run the initialization command in the README, then refresh this view.")}</p></div>)}
        {tx(active && <>
          <div className="research-grid"><Card className="history-panel"><div className="panel-heading"><div><div className="panel-kicker">{t("HISTORICAL EXPLORER")}</div><h2>{tx(active.series.short_name)}<span className="frequency-tag">{tx(active.series.frequency)}</span></h2></div><a href={active.series.source_url} target="_blank" rel="noreferrer" className="source-link">{t("View source")}<ExternalLink size={13}/></a></div>
            <div className="chart-toolbar"><div className="chart-controls"><label className="sr-only" htmlFor="series">{t("Series")}</label><select id="series" value={active.series.id} onChange={e => { const card = cards.find(c => c.series.id === e.target.value); if (card)
            choose(card); }}>{tx(cards.map(c => <option key={c.series.id} value={c.series.id}>{tx(c.series.short_name)}</option>))}</select><label className="sr-only" htmlFor="transform">{t("Transformation")}</label><select id="transform" value={currentTransform} onChange={e => setTransform(e.target.value)}>{tx(active.series.available_transforms.map(t => <option value={t} key={t}>{tx(transformNames[t])}</option>))}</select>{tx(currentTransform === "moving_average" && <label className="ma-window">{t("Window")}<input aria-label={t("Moving average observation window")} type="number" min={2} max={365} value={window} onChange={e => setWindow(Math.min(365, Math.max(2, Number(e.target.value) || 2)))}/></label>)}</div><div className="range-control" aria-label={t("Chart time range")}>{tx(ranges.map(r => <button key={r} aria-pressed={range === r} className={range === r ? "active" : ""} onClick={() => setRange(r)}>{tx(r)}</button>))}</div></div>
            <div className="chart-summary"><span className="chart-legend-dot"/><span>{tx(transformNames[currentTransform])}</span><strong>{tx(number(latestPoint?.value))}{tx(unitSuffix(observations?.units || ""))}</strong><span className="chart-units">{tx(observations?.units || active.units)}</span></div>
            {tx(chartBusy ? <div className="chart-placeholder" role="status"><LoaderCircle className="animate-spin"/>{t("Loading observations\u2026")}</div> : chartError ? <div className="chart-placeholder error-text" role="alert"><CircleAlert />{tx(chartError)}<Button variant="outline" size="sm" onClick={() => refreshData()}>{t("Retry")}</Button></div> : !validPoints.length ? <div className="chart-placeholder">{t(availabilityMessage(observations?.availability))}</div> : <MacroChart points={observations?.observations || []} label={tx(active.series.short_name)} units={observations?.units || ""}/>)}
            <div className="chart-foot"><span>{tx(observations?.observations.length.toLocaleString() || 0)}{" " + t("observations")}<span className="strip-divider"/>{t("Missing values are not interpolated")}</span><span>{t("Scroll to zoom \u00B7 Drag to explore")}</span></div>
          </Card>
          <Card className="detail-panel"><CardContent><div className="panel-kicker">{t("SERIES BRIEF")}</div><h2>{tx(active.series.title)}</h2><p className="brief-description">{tx(active.series.agency)}</p><dl className="facts"><div><dt>{t("Series ID")}</dt><dd className="mono amber">{tx(active.series.id)}</dd></div><div><dt>{t("Frequency")}</dt><dd className="capitalize">{tx(active.series.frequency)}</dd></div><div><dt>{t("Adjustment")}</dt><dd>{tx(active.series.seasonal_adjustment)}</dd></div><div><dt>{t("Native units")}</dt><dd>{tx(active.series.units)}</dd></div><div><dt>{t("Latest valid period")}</dt><dd className="mono">{tx((observations ? latestPoint?.date : active.observation_date) || "—")}</dd></div><div><dt>{t("Collected")}</dt><dd>{tx(timestamp(active.collected_at))}</dd></div><div><dt>{t("Delivery")}</dt><dd>{tx(active.provider === "fred_api" ? "FRED API" : active.provider === "fred_csv" ? "Official FRED CSV" : "Awaiting import")}</dd></div></dl><div className="method-note"><BookOpen size={16}/><div><strong>{t("Research note")}</strong><p>{tx(currentTransform === "annualized_3m" || currentTransform === "annualized_6m" ? "Annualized growth compounds the change over the selected calendar interval. GDP uses quarterly observations." : currentTransform === "absolute_change" ? "Change from the previous native period. Rate changes are measured in percentage points." : currentTransform === "moving_average" ? `A simple average of ${window} native observations. Missing observations remain missing.` : "Each series retains its native frequency and units. Transformations use calendar-aligned observations.")}</p></div></div><a className="brief-source" href={active.series.source_url} target="_blank" rel="noreferrer">{t("Open series on FRED")}<ArrowUpRight size={16}/></a></CardContent></Card></div>
          <Card className="observations-panel"><div className="panel-heading"><div><div className="panel-kicker">{t("LATEST READINGS")}</div><h2>{t("Observation ledger")}</h2></div><span className="ledger-label">{tx(active.series.id)} · {tx(transformNames[currentTransform])}</span></div><div className="table-scroll"><table><thead><tr><th>{t("Observation period")}</th><th>{t("Transformed value")}</th><th>{t("Original value")}</th><th>{t("Collected (UTC)")}</th><th>{t("Source")}</th></tr></thead><tbody>{tx([...(observations?.observations || [])].reverse().slice(0, 8).map(p => <tr key={p.date}><td className="mono">{tx(p.date)}</td><td className="mono table-value">{tx(number(p.value))} <span>{tx(unitSuffix(observations?.units || ""))}</span></td><td className="mono muted">{tx(p.raw_value === "." ? "Missing (.)" : p.raw_value)}</td><td className="muted">{tx(timestamp(p.collected_at).replace(" UTC", ""))}</td><td><span className="provider-tag">{tx(p.source === "fred_api" ? "FRED API" : "FRED CSV")}</span></td></tr>))}{tx(!observations?.observations.length && <tr><td colSpan={5} className="table-empty">{tx(chartBusy ? "Loading observations…" : "No observations to display")}</td></tr>)}</tbody></table></div></Card>
        </>)}
        {tx(section === "overview" && <><SyncStatus epoch={refresh}/><ReleaseWidgets refreshEpoch={refresh} /></>)}
        <footer className="footer"><span><Database size={13}/>{t("Source: FRED, Federal Reserve Bank of St. Louis. Original agencies retain data ownership.")}</span><span>{t("Observation dates \u2260 release dates. Release timestamps unavailable.")}</span></footer>
  </TerminalFrame>;
}
