"use client";
import {WorkspaceActions} from "./workspace-actions";
import {RefreshStatus} from "./refresh-status";
import {requestMetadata} from "@/lib/query-client";
import {useRevalidation} from "@/lib/use-revalidation";
import {availabilityMessage} from '@/lib/chart-availability';
import {useUI} from "./presentation-provider";
import { useState, useEffect, useMemo, useRef } from 'react';
import { ResearchShell } from './research-shell';
import { WorkspaceChart, type ChartHandle } from './workspace-chart';
import { request, download, csv, today } from '@/lib/workspace-utils';
import { Button } from './ui/button';
type AnyData = Record<string, any>;
const initial = () => ({ kind: 'analytics', configuration_version: 1, title: 'Macro Research Analytics', start: '2010-01-01', end: today(), frequency: 'monthly', data_mode: 'latest', as_of: null, method: 'pearson', window: 24, max_lag: 12, min_samples: 12, show_ex_post_recessions: false, rule_version: 'cycle-v1', lines: [{ key: 'x', series_id: 'UNRATE', display_name: 'Unemployment', calculations: [{ transform: 'absolute_change', window: 12, base_date: null }], axis: 'left', alignment: 'period_end' }, { key: 'y', series_id: 'PAYEMS', display_name: 'Payroll change', calculations: [{ transform: 'absolute_change', window: 12, base_date: null }], axis: 'right', alignment: 'period_end' }] });
export default function Analytics({ cycle = false }: {
    cycle?: boolean;
}) {
    const { t, tx, locale, date: uiDate, number: uiNumber } = useUI();
    const [config, setConfig] = useState<AnyData>(initial);
    const [operation, setOperation] = useState('correlation');
    const [statistic, setStatistic] = useState('z_score');
    const [signal, setSignal] = useState('Unemployment');
    const [data, setData] = useState<AnyData | null>(null);
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(true);
    const [library, setLibrary] = useState<AnyData[]>([]);
    const [saved, setSaved] = useState<AnyData[]>([]);
    const [selected, setSelected] = useState('');
    const [drawer, setDrawer] = useState(false);
    const [notice, setNotice] = useState('');
    const [rules, setRules] = useState<AnyData>({ inflation: 3, unemployment_change: .3, payroll: 50, growth: 0, inversion: 0, sahm: .5, claims_change: 0 });
    const [name, setName] = useState('Macro Research');
    const [refresh,refreshData]=useRevalidation(cycle?['business-cycle/','recession-indicators']:['analytics/']);
    const [lastFetch,setLastFetch]=useState<string|null>(null);
    const lastConfig=useRef('');
    const chart = useRef<ChartHandle>(null);
    const patch = (p: AnyData) => setConfig(c => ({ ...c, ...p }));
    const reload = () => request<AnyData>('workspaces').then(r => setSaved(r.workspaces.filter((s: any) => s.kind === 'analytics' && (s.view || 'analytics') === (cycle ? 'business-cycle' : 'analytics'))));
    useEffect(() => { request<AnyData>('workspace/series/search?page_size=100').then(r => setLibrary(r.series)).catch(e => setError(e.message)); reload().catch(e => setNotice(e.message)); }, []);
    useEffect(() => { const a = new AbortController(); setBusy(true); setError('');const key=JSON.stringify([config,operation,rules]);if(lastConfig.current!==key)setData(null);lastConfig.current=key; const t = setTimeout(() => { if (cycle) {
        const q = new URLSearchParams({ data_mode: config.data_mode, ...Object.fromEntries(Object.entries(rules).map(([k, v]) => [k, String(v)])) });
        if (config.data_mode === 'vintage')
            q.set('as_of', config.as_of);
        const h = new URLSearchParams(q);
        h.set('start', config.start);
        h.set('end', config.end);
        h.set('show_ex_post_recessions', String(config.show_ex_post_recessions));
        const parts:AnyData={};
        const publish=()=>{if(!a.signal.aborted&&parts.current)setData(old=>({...old,history:old?.history||[],recent_three:old?.recent_three||[],...parts}));};
        const tasks=[request<AnyData>('business-cycle/current?'+q,'GET',undefined,a.signal).then(r=>{parts.current=r;publish()}),request<AnyData>('business-cycle/history?'+h,'GET',undefined,a.signal).then(r=>{Object.assign(parts,r);publish()}),request<AnyData>('recession-indicators?'+q,'GET',undefined,a.signal).then(r=>{parts.recession=r;publish()})];
        Promise.allSettled(tasks).then(results=>{if(a.signal.aborted)return;const failed=results.find(r=>r.status==='rejected');setError(failed&&failed.status==='rejected'?failed.reason.message:'');if(!failed)setLastFetch(requestMetadata(parts.current)?.fetchedAt||null);setBusy(false)});

    }
    else
        request<AnyData>('analytics/' + operation, 'POST', config, a.signal).then(r=>{if(a.signal.aborted)return;setData(r);setError('');setLastFetch(requestMetadata(r)?.fetchedAt||null)}).catch(e => { if (!a.signal.aborted)
            setError(e.message); }).finally(() => { if (!a.signal.aborted)
            setBusy(false); }); }, 350); return () => { clearTimeout(t); a.abort(); }; }, [config, operation, cycle, rules,refresh]);
    useEffect(()=>{const id=new URLSearchParams(window.location.search).get('workspace_id');if(id&&/^[a-f0-9-]{36}$/.test(id))void load(id)},[]);
    const option = useMemo(() => {
        if (!data)
            return {};
        let labels: any[] = [], series: any[] = [];
        if (cycle) {
            labels = data.history?.map((p: any) => p.evaluated_date) || [];
            series = Object.keys(rules).slice(0, 0);
            series = ['inflation', 'labor', 'growth', 'financial'].map(d => ({ name: d, type: 'line', connectNulls: false, data: data.history?.map((p: any) => p.scores[d]) }));
        }
        else if (operation === 'lead-lag') {
            labels = data.lags?.map((p: any) => String(p.lag)) || [];
            series = [{ name: 'Full sample', type: 'bar', data: data.lags?.map((p: any) => p.value) }, { name: 'Trailing stability', type: 'line', data: data.lags?.map((p: any) => p.trailing_stability.value) }];
        }
        else if (operation === 'rolling-statistics') {
            labels = data.dates || [];
            series = [statistic].map(k => ({ name: k, type: 'line', connectNulls: false, data: data.statistics?.[0]?.points.map((p: any) => p[k]) }));
        }
        else if (operation === 'rolling-correlation') {
            labels = data.dates || [];
            series = [{ name: 'Rolling correlation', type: 'line', connectNulls: false, data: data.rolling?.map((p: any) => p.value) }];
        }
        else {
            labels = data.series?.map((p: any) => p.name) || [];
            series = data.series?.map((s: any) => ({ name: s.name, type: 'bar', data: data.matrix?.filter((p: any) => p.x === s.key).map((p: any) => p.value) })) || [];
        }
        const rec = data.recessions || [];
        if (series[0] && operation !== 'lead-lag' && operation !== 'correlation')
            series[0].markArea = { silent: true, itemStyle: { color: '#aeb9cf20' }, data: rec.map((r: any) => labels.filter((d: string) => r.start <= d && d < r.end)).filter((x: any) => x.length).map((x: any) => [{ xAxis: x[0] }, { xAxis: x[x.length - 1] }]) };
        if (!cycle && operation === 'correlation')
            return { dataZoom: [], grid: { left: 110, right: 45, top: 90, bottom: 140 }, xAxis: { type: 'category', data: labels }, yAxis: { type: 'category', data: labels }, visualMap: { min: -1, max: 1, orient: 'horizontal', left: 'center', bottom: 65, inRange: { color: ['#d78d8a', '#192737', '#7dbdb6'] }, textStyle: { color: '#aabbce' } }, series: [{ type: 'heatmap', label: { show: true, color: '#eef4fa', formatter: (p: any) => p.value[2] == null ? '—' : p.value[2].toFixed(2) }, data: data.matrix?.map((p: any) => [data.series.findIndex((s: any) => s.key === p.x), data.series.findIndex((s: any) => s.key === p.y), p.value]) }] };
        return { xAxis: { type: 'category', data: labels }, yAxis: { type: 'value', name: cycle ? 'Dimension score' : operation === 'rolling-statistics' ? 'Selected statistic (see table)' : 'Correlation', scale: true, splitLine: { lineStyle: { color: '#29394c' } } }, series };
    }, [data, operation, cycle, rules, statistic]);
    async function save(copy = false) { try {
        const r = await request<AnyData>(selected && !copy ? 'workspaces/' + selected : 'workspaces', selected && !copy ? 'PUT' : 'POST', { name: copy ? name + ' (copy)' : name, configuration: { ...config, data_fingerprints: !cycle && data?.series ? Object.fromEntries(data.series.filter((s: any) => s.provenance.dependency_fingerprint).map((s: any) => [s.key, s.provenance.dependency_fingerprint])) : {}, operation, statistic, view: cycle ? 'business-cycle' : 'analytics', rule_parameters: rules } });
        setSelected(r.id);
        await reload();
        setNotice('Configuration saved.');
    }
    catch (e) {
        setNotice((e as Error).message);
    } }
    async function load(id: string) { setSelected(id); if (!id)
        return; try {
        const r = await request<AnyData>('workspaces/' + id);
        if (r.configuration.kind !== 'analytics')
            throw new Error('Choose an analytics configuration; chart workspaces remain available at /workspace');
        setConfig(r.configuration);
        setOperation(r.configuration.operation || 'correlation');
        setStatistic(r.configuration.statistic || 'z_score');
        if (Object.keys(r.configuration.rule_parameters || {}).length)
            setRules(r.configuration.rule_parameters);
        setName(r.name);
        setNotice('Loaded analytics configuration');
    }
    catch (e) {
        setNotice((e as Error).message);
    } }
    const periodEnd = new Date();
    periodEnd.setMonth(periodEnd.getMonth() - 5);
    const cycleStart = periodEnd.toLocaleDateString('en-CA').slice(0, 7) + '-01';
    useEffect(() => { if (cycle)
        patch({ start: cycleStart }); }, [cycle]);
    const controls = <><label className="workspace-field">{t("Mode")}<select value={config.data_mode} onChange={e => patch({ data_mode: e.target.value, as_of: e.target.value === 'vintage' ? '2023-06-15' : null, ...(cycle && e.target.value === 'vintage' ? { start: '2023-01-01', end: '2023-06-15' } : {}) })}><option value="latest">{t("Latest revised data")}</option><option value="vintage">{t("Historical Vintage")}</option></select></label>{config.data_mode === 'vintage' && <label className="workspace-field">{t("Shared as-of")}<input type="date" value={config.as_of || ''} onChange={e => patch({ as_of: e.target.value, start: cycle ? '2023-01-01' : config.start, end: e.target.value })}/></label>}<label className="workspace-field">{t("Start")}<input type="date" value={config.start} onChange={e => patch({ start: e.target.value })}/></label><label className="workspace-field">{t("End")}<input type="date" value={config.end} onChange={e => patch({ end: e.target.value })}/></label><label className="workspace-check"><input type="checkbox" checked={config.show_ex_post_recessions} onChange={e => patch({ show_ex_post_recessions: e.target.checked })}/>{t("Show Ex-post NBER Recessions")}</label><p className="calendar-note">{t("Ex-post chronology is reference only, never a historically known input. Date-level ALFRED only.")}</p>
 {cycle ? <>{Object.entries(rules).map(([k, v]) => <label className="workspace-field" key={k}>{tx(k)}{" " + t("threshold")}<input type="number" step="0.1" value={v} onChange={e => setRules(r => ({ ...r, [k]: Number(e.target.value) }))}/></label>)}</> : <><label className="workspace-field">{t("Analysis")}<select value={operation} onChange={e => setOperation(e.target.value)}>{tx(['correlation', 'rolling-correlation', 'lead-lag', 'rolling-statistics'].map(x => <option key={x} value={x}>{tx(x)}</option>))}</select></label><label className="workspace-field">{t("Method")}<select value={config.method} onChange={e => patch({ method: e.target.value })}><option value={"pearson"}>{t("pearson")}</option><option value={"spearman"}>{t("spearman")}</option></select></label><label className="workspace-field">{t("Frequency")}<select value={config.frequency} onChange={e => patch({ frequency: e.target.value })}>{tx(['daily', 'weekly', 'monthly', 'quarterly'].map(f => <option key={f} value={f}>{tx(f)}</option>))}</select></label><label className="workspace-field">{t("Rolling statistic")}<select value={statistic} onChange={e => setStatistic(e.target.value)}>{tx(['mean', 'std', 'z_score', 'percentile'].map(t => <option key={t} value={t}>{tx(t)}</option>))}</select></label>{['window', 'max_lag', 'min_samples'].map(k => <label className="workspace-field" key={k}>{tx(k)}<input type="number" value={config[k]} onChange={e => patch({ [k]: Number(e.target.value) })}/></label>)}{config.lines.map((l: any, i: number) => <div key={l.key} className="calculation-step"><label className="workspace-field">{tx(i === 0 ? 'X' : i === 1 ? 'Y' : 'Series ' + (i + 1))}<select value={l.series_id} onChange={e => patch({ lines: config.lines.map((x: any, n: number) => n === i ? { ...x, series_id: e.target.value, display_name: e.target.value } : x) })}>{tx(library.map(s => <option key={s.id} value={s.id}>{tx(s.id)} · {tx(s.short_name)}</option>))}</select></label><label className="workspace-field">{t("Transform")}<select value={l.calculations[0].transform} onChange={e => patch({ lines: config.lines.map((x: any, n: number) => n === i ? { ...x, calculations: [{ transform: e.target.value, window: 12, base_date: null }] } : x) })}>{tx(['raw', 'absolute_change', 'mom', 'yoy', 'annualized_3m', 'annualized_6m', 'moving_average', 'z_score'].map(t => <option key={t} value={t}>{tx(t)}</option>))}</select></label><label className="workspace-field">{t("Alignment")}<select value={l.alignment} onChange={e => patch({ lines: config.lines.map((x: any, n: number) => n === i ? { ...x, alignment: e.target.value } : x) })}>{tx(['period_end', 'period_average', 'last_available'].map(t => <option key={t} value={t}>{tx(t)}</option>))}</select></label>{tx(config.lines.length > 2 && <button onClick={() => patch({ lines: config.lines.filter((_: any, n: number) => n !== i) })}>{t("Remove")}</button>)}</div>)}<Button variant="outline" disabled={config.lines.length >= 8} onClick={() => patch({ lines: [...config.lines, { ...config.lines[0], key: 's' + Date.now() }] })}>{t("Add indicator")}</Button></>}
 </>;
    return <ResearchShell advanced title={tx(cycle ? 'Business Cycle Monitor' : 'Macro Research Analytics')} description={t("Transparent research calculations. Correlation is not causation or verified forecast skill; cycle rules are not NBER designations or recession probabilities.")}><Button variant="outline" className="analytics-mobile" onClick={() => setDrawer(!drawer)}>{t("Parameters")}</Button><WorkspaceActions seriesIds={cycle?[data?.current?.signals?.find((s:any)=>s.name===signal)?.series_id||'UNRATE']:config.lines.map((l:any)=>l.series_id)} start={config.start} end={config.end} dataMode={config.data_mode} asOf={config.as_of}/><div className="analytics-layout"><aside className={'workbench-panel analytics-controls ' + (drawer ? 'analytics-open' : '')}>{tx(drawer && <Button onClick={() => setDrawer(false)}>{t("Close parameters")}</Button>)}{tx(controls)}</aside><section style={{ minWidth: 0 }}><Button variant="outline" disabled={busy} onClick={refreshData}>{t('Refresh view')}</Button><RefreshStatus cached={requestMetadata(cycle?data?.current:data)?.cacheHit} busy={busy} error={error} hasData={!!data} lastFetch={lastFetch} retry={refreshData}/>{tx(busy && !data ? <div className="workspace-loading skeleton" role="status">{t('Computing real data…')}</div> : data && <>{cycle && <><div className="workspace-notice"><h2>{tx(data.current.state)}</h2><p>{tx(data.current.note)}</p><p>{t("Rule: cycle-v1 \u00B7 Coverage:") + " "}{tx(data.current.status)}</p></div><div className="vintage-summary">{tx(Object.entries(data.current.scores).map(([d, v]) => <span key={d}>{tx(d)}<strong>{tx(v === null ? 'Insufficient Data' : Number(Number(v).toFixed(3)))}</strong></span>))}</div><p>{t("Sahm gap:") + " "}{tx(data.current.sahm.value?.toFixed(3) ?? 'Unavailable')}{" " + t("pp \u00B7 threshold") + " "}{tx(rules.sahm)} · {tx(data.current.sahm.period)}</p><p className="calendar-note">{tx(data.current.sahm.method)}</p>{data.current.sahm.missing_reason&&<p className="workspace-warning">{tx(data.current.sahm.missing_reason)}</p>}</>}
 <WorkspaceChart ref={chart} option={option} emptyReason={busy?t('Loading observations…'):data.series?.filter((s:any)=>s.availability?.status!=='AVAILABLE').map((s:any)=>s.series_id+': '+t(availabilityMessage(s.availability))).join(' · ')||t('The calculation has insufficient paired samples, incomplete windows or zero variance. See sample counts and source coverage below.')}  title={tx(cycle ? 'Macro dimension history · cycle-v1' : config.title + ' · ' + operation)} footnote={tx(`${config.data_mode} ${config.as_of || 'revised data'} | ${config.start} — ${config.end}\nSource: FRED / ALFRED · Ex-post shading reference only; no prediction claim`)} label={t("Macro research analytics chart")}/>{(cycle || operation === 'lead-lag') && <><label className="workspace-field">{t("Evidence timeline")}{tx(cycle && <select value={signal} onChange={e => setSignal(e.target.value)}>{tx(data.current.signals.map((s: any) => <option key={s.name} value={s.name}>{tx(s.name)}</option>))}</select>)}</label><WorkspaceChart title={tx(cycle ? signal + (config.data_mode === 'vintage' ? ' · archived date-level availability' : ' · revised-data retrospective history') : 'Transformed X · sample timeline')} label={t("Indicator timeline with optional ex-post recession reference")} footnote={t("Source: FRED / ALFRED \u00B7 Ex-post NBER shading is hindsight reference only")} option={{ xAxis: { type: 'category', data: cycle ? data.history.map((r: any) => r.evaluated_date) : data.dates }, yAxis: { type: 'value', scale: true }, series: [{ type: 'line', name: cycle ? signal : data.series?.[0]?.name, connectNulls: false, data: cycle ? data.history.map((r: any) => r.signals.find((s: any) => s.name === signal)?.value) : data.series?.[0]?.values, markArea: { silent: true, itemStyle: { color: '#aeb9cf20' }, data: (data.recessions || []).map((r: any) => (cycle ? data.history.map((h: any) => h.evaluated_date) : data.dates).filter((d: string) => r.start <= d && d < r.end)).filter((d: any) => d.length).map((d: any) => [{ xAxis: d[0] }, { xAxis: d[d.length - 1] }]) } }] }}/></>}{!cycle && <><p className="calendar-note">{tx(data.lag_definition || data.alignment_note)} {tx(data.best_lag != null ? 'Best in-sample absolute correlation lag: ' + data.best_lag : '')}</p>{data.warnings?.map((w: string) => <p className="calendar-note" key={w}>{tx(w)}</p>)}</>}
 <div className="table-scroll research-panel"><table><thead><tr>{tx((cycle ? ['Indicator', 'Value', 'Units', 'Change', 'Threshold', 'Score', 'Period', 'Source', 'Retrieved at'] : operation === 'correlation' ? ['X', 'Y', 'Correlation', 'N', 'Start', 'End', 'Missing ratio'] : operation === 'lead-lag' ? ['Lag', 'Correlation', 'N', 'Start', 'End', 'Missing ratio'] : operation === 'rolling-correlation' ? ['Date', 'Correlation', 'N', 'Missing ratio'] : ['Date', 'Mean', 'Std', 'Z-score', 'Percentile', 'N']).map(h => <th key={h}>{tx(h)}</th>))}</tr></thead><tbody>{tx((cycle ? data.current.signals : operation === 'correlation' ? data.matrix : operation === 'lead-lag' ? data.lags : operation === 'rolling-correlation' ? data.rolling : data.statistics?.[0]?.points)?.map((r: any, i: number) => <tr key={i}>{tx((cycle ? [r.name, r.value, r.units, r.change, r.threshold, r.score, r.period, r.source.status, r.source.retrieved_at] : operation === 'correlation' ? [r.x, r.y, r.value, r.sample_count, r.sample_start, r.sample_end, r.missing_ratio] : operation === 'lead-lag' ? [r.lag, r.value, r.sample_count, r.sample_start, r.sample_end, r.missing_ratio] : operation === 'rolling-correlation' ? [r.date, r.value, r.sample_count, r.missing_ratio] : [r.date, r.mean, r.std, r.z_score, r.percentile, r.sample_count]).map((v: any, j: number) => <td key={j}>{tx(v === null || v === undefined ? '—' : typeof v === 'number' ? Number(v.toFixed(4)) : String(v))}</td>))}</tr>))}</tbody></table></div>
 {cycle && <><h2>{t("Recent three states")}</h2>{data.recent_three?.map((r: any) => <p key={r.evaluated_date}>{tx(r.evaluated_date)} · {tx(r.state)} · {tx(r.status)}</p>)}<details className="workspace-method"><summary>{t("Inversion evidence and signal methods")}</summary><pre style={{ whiteSpace: 'pre-wrap' }}>{tx(JSON.stringify(data.recession, null, 2))}</pre></details></>}
 <details className="workspace-method"><summary>{t("Data versions, method and sample evidence")}</summary><pre style={{ whiteSpace: 'pre-wrap' }}>{tx(JSON.stringify(cycle ? data.current : data.series?.map((s: any) => ({ ...s, values: undefined })), null, 2))}</pre></details><div className="workspace-exports"><Button variant="outline" onClick={() => chart.current?.exportPng()}>{t("PNG")}</Button><Button variant="outline" onClick={() => { const rows = cycle ? data.current.signals : operation === 'correlation' ? data.matrix : operation === 'lead-lag' ? data.lags : operation === 'rolling-correlation' ? data.rolling : data.statistics?.[0]?.points; download('analytics.csv', csv([['mode', 'as_of', 'configuration', 'result'], ...rows.map((r: any) => [config.data_mode, config.as_of, JSON.stringify(config), JSON.stringify(r)])]), 'text/csv'); }}>{t("CSV")}</Button><Button variant="outline" onClick={() => download('analytics-result.json', JSON.stringify(data, null, 2), 'application/json')}>{t("Result JSON")}</Button></div></>)}
 </section><aside className="workbench-panel"><h2>{t("Preserve research")}</h2><label className="workspace-field">{t("Name")}<input value={name} onChange={e => setName(e.target.value)}/></label><label className="workspace-field">{t("Saved analysis")}<select value={selected} onChange={e => load(e.target.value)}><option value="">{t("Unsaved")}</option>{tx(saved.map(r => <option key={r.id} value={r.id}>{tx(r.name)}</option>))}</select></label><div className="workspace-save-actions"><Button variant="outline" onClick={() => save()}>{t("Save")}</Button><Button variant="outline" onClick={() => save(true)}>{t("Duplicate")}</Button><Button variant="outline" disabled={!selected} onClick={async () => { await request('workspaces/' + selected, 'DELETE'); setSelected(''); reload(); }}>{t("Delete")}</Button><Button variant="outline" onClick={() => download('analytics-config.json', JSON.stringify({ ...config, operation, statistic, view: cycle ? 'business-cycle' : 'analytics', rule_parameters: rules }, null, 2), 'application/json')}>{t("Configuration JSON")}</Button></div><label className="workspace-field">{t("Import configuration")}<input type="file" accept=".json" onChange={async (e) => { try {
        const file = e.target.files?.[0];
        if (!file)
            return;
        if (file.size > 131072)
            throw new Error('File too large');
        const c = JSON.parse(await file.text());
        await request('analytics/correlation', 'POST', c);
        setConfig(c);
        setNotice('Imported and validated');
    }
    catch (err) {
        setNotice((err as Error).message);
    } }}/></label><p role="status">{tx(notice)}</p><p className="calendar-note">{t("Rolling statistics require a complete trailing window; sample metadata appears per result. Missing historical series never use latest values.")}</p></aside></div></ResearchShell>;
}
