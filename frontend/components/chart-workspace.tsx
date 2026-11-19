"use client";
import {RefreshStatus} from "./refresh-status";
import {requestMetadata} from "@/lib/query-client";
import {useRevalidation} from "@/lib/use-revalidation";
import {chartPalette} from "@/lib/presentation";
import {useUI} from "./presentation-provider";
import { useEffect, useMemo, useRef, useState } from 'react';
import { Plus, Search, Settings2, X, Download, Save, Copy, Trash2, FolderOpen, SlidersHorizontal } from 'lucide-react';
import { ResearchShell } from './research-shell';
import { Button } from './ui/button';
import { WorkspaceChart, type ChartHandle } from './workspace-chart';
import { calc, chartCsv, download, line, request, template, templateNames, today } from '@/lib/workspace-utils';
import type { Calculation, ChartLine, ChartResult, Configuration, Frequency, SavedWorkspace, SearchSeries, WorkspaceList } from '@/lib/workspace-types';
import { number } from '@/lib/types';
const operations: Record<string, string> = { raw: 'Raw', mom: 'MoM %', yoy: 'YoY %', annualized_3m: '3M Annualized', annualized_6m: '6M Annualized', moving_average: 'Moving Average', z_score: 'Z-Score', index_100: 'Index 100', absolute_change: 'Absolute Change' };
const frequencies: Frequency[] = ['daily', 'weekly', 'monthly', 'quarterly'];
export default function ChartWorkspace() {
    const { t, tx, locale, resolvedTheme, date: uiDate, number: uiNumber } = useUI();
    const [config, setConfig] = useState<Configuration>(() => template(0));
    const [selected, setSelected] = useState(0);
    const [data, setData] = useState<ChartResult | null>(null);
    const [busy, setBusy] = useState(true);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [refresh,refreshData]=useRevalidation(['workspace/','workspaces']);
    const [lastFetch,setLastFetch]=useState<string|null>(null);
    const lastConfig=useRef('');
    const [q, setQ] = useState('');
    const [category, setCategory] = useState('');
    const [results, setResults] = useState<SearchSeries[]>([]);
    const [searchError, setSearchError] = useState('');
    const [drawer, setDrawer] = useState<'search' | 'settings' | null>(null);
    const [saved, setSaved] = useState<WorkspaceList['workspaces']>([]);
    const [savedId, setSavedId] = useState('');
    const [name, setName] = useState('Inflation Momentum');
    const [description, setDescription] = useState('');
    const [working, setWorking] = useState(false);
    const chart = useRef<ChartHandle>(null);
    const active = config.lines[Math.min(selected, config.lines.length - 1)];
    const patch = (value: Partial<Configuration>) => setConfig(c => ({ ...c, ...value }));
    const patchLine = (value: Partial<ChartLine>) => setConfig(c => ({ ...c, lines: c.lines.map((l, i) => i === selected ? { ...l, ...value } : l) }));
    useEffect(() => { const a = new AbortController(); const timer = setTimeout(() => { const params = new URLSearchParams({ q, page_size: '100' }); if (category)
        params.set('category', category); request<{
        series: SearchSeries[];
    }>('workspace/series/search?' + params, 'GET', undefined, a.signal).then(r => { setResults(r.series); setSearchError(''); }).catch(e => { if (!a.signal.aborted)
        setSearchError(e.message); }); }, 200); return () => { clearTimeout(timer); a.abort(); }; }, [q, category]);
    useEffect(() => { const a = new AbortController(); setBusy(true); setError(''); if(lastConfig.current!==JSON.stringify(config))setData(null);lastConfig.current=JSON.stringify(config); const timer = setTimeout(() => request<ChartResult>('workspace/chart-data', 'POST', config, a.signal).then(r=>{if(a.signal.aborted)return;setData(r);setError('');setLastFetch(requestMetadata(r)?.fetchedAt||null)}).catch(e => { if (!a.signal.aborted)
        setError(e.message); if(!a.signal.aborted&&e.lastGood)setData(e.lastGood); }).finally(() => { if (!a.signal.aborted)
        setBusy(false); }), 250); return () => { clearTimeout(timer); a.abort(); }; }, [config, refresh]);
    const reloadSaved = () => request<WorkspaceList>('workspaces').then(r => setSaved(r.workspaces.filter(s => s.kind !== 'analytics' && s.kind !== 'dashboard')));
    useEffect(() => { reloadSaved().catch(e => setNotice(e.message)); }, []);
    const option = useMemo(() => { if (!data)
        return {}; const recessionAreas = data.recession_intervals.map(r => data.dates.filter(d => r.start <= d && d < r.end)).filter(days => days.length).map(days => [{ xAxis: days[0] }, { xAxis: days[days.length - 1] }]); const visible = config.lines.filter(l => l.visible); const series = visible.map((l, i) => { const s = data.series.find(s => s.key === l.key); return { name: l.display_name, type: l.chart_type, yAxisIndex: l.axis === 'right' ? 1 : 0, showSymbol: false, connectNulls: false, lineStyle: { type: l.line_style, width: 2 }, data: s?.points.map(p => p.value) || [], ...(i === 0 && recessionAreas.length ? { markArea: { silent: true, itemStyle: { color: '#96a0b017' }, data: recessionAreas } } : {}) }; }); return { xAxis: { type: 'category', data: data.dates, axisLabel: { color: '#8096b1', fontSize: 10 } }, yAxis: ['left', 'right'].map((axis, i) => ({ type: 'value', name: data.axes[axis] || '', nameLocation: 'middle', nameRotate: i ? -90 : 90, nameGap: 55, scale: true, axisLabel: { fontSize: 10 }, splitLine: { show: i === 0, lineStyle: { color: '#27374b' } } })), series }; }, [data, config.lines]);
    function add(s: SearchSeries) { if (config.lines.length >= 6)
        return; const axis = config.lines.length === 1 && data?.series[0]?.units !== s.units ? 'right' : 'left'; const next = line(s.id, s.short_name, [calc()], axis); patch({ lines: [...config.lines, next] }); setSelected(config.lines.length); setNotice(''); }
    function updateStep(index: number, value: Partial<Calculation>) { const calculations = active.calculations.map((c, i) => i === index ? { ...c, ...value } : c); patchLine({ calculations }); }
    function frozenConfiguration() { return { ...config, data_fingerprints: data ? Object.fromEntries(data.series.filter(s => s.provenance.dependency_fingerprint).map(s => [s.key, s.provenance.dependency_fingerprint!])) : config.data_fingerprints }; }
    async function save(asCopy = false) { setWorking(true); setNotice(''); try {
        const payload = { name: asCopy ? name + ' (copy)' : name, description, configuration: frozenConfiguration() };
        const result = await request<SavedWorkspace>(savedId && !asCopy ? 'workspaces/' + savedId : 'workspaces', savedId && !asCopy ? 'PUT' : 'POST', payload);
        setSavedId(result.id);
        setName(result.name);
        await reloadSaved();
        setNotice(asCopy ? 'Workspace duplicated.' : 'Workspace saved with configuration and source fingerprints.');
    }
    catch (e) {
        setNotice((e as Error).message);
    }
    finally {
        setWorking(false);
    } }
    async function load(id: string) { if (!id) {
        setSavedId('');
        return;
    } setWorking(true); try {
        const r = await request<SavedWorkspace>('workspaces/' + id);
        setConfig(r.configuration);
        setName(r.name);
        setDescription(r.description);
        setSavedId(r.id);
        setSelected(0);
        setNotice('Saved configuration loaded. Latest mode is dynamic; Vintage retains its as-of date.');
    }
    catch (e) {
        setNotice((e as Error).message);
    }
    finally {
        setWorking(false);
    } }
    async function removeSaved() { if (!savedId)
        return; setWorking(true); try {
        await request('workspaces/' + savedId, 'DELETE');
        setSavedId('');
        await reloadSaved();
        setNotice('Saved workspace deleted. Current chart remains editable.');
    }
    catch (e) {
        setNotice((e as Error).message);
    }
    finally {
        setWorking(false);
    } }
    async function importFile(file: File | undefined) { if (!file)
        return; try {
        if (file.size > 131072)
            throw new Error('Configuration exceeds 128 KiB');
        const value = JSON.parse(await file.text());
        const candidate = value.configuration || value;
        await request('workspace/chart-data', 'POST', candidate);
        setConfig(candidate);
        setSelected(0);
        setSavedId('');
        setName(value.name || candidate.title);
        setDescription(value.description || '');
        setNotice('Configuration imported and schema validated. Save to persist it.');
    }
    catch (e) {
        setNotice('Import failed: ' + (e as Error).message);
    } }
    const selectedSeries = results.find(s => s.id === active?.series_id);
    return <ResearchShell title={t("Chart Workspace")} description={t("Build, compare and preserve macroeconomic research. Each line keeps its own transformation and source evidence.")} advanced>
 <div className="workspace-actionbar"><label>{t("Research template")}<select aria-label={t("Research template")} defaultValue="0" onChange={e => { const c = template(Number(e.target.value)); setConfig(c); setName(c.title); setDescription(''); setSavedId(''); setSelected(0); setNotice('Template loaded; all parameters remain editable.'); }}>{tx(templateNames.map((t, i) => <option key={t} value={i}>{tx(t)}</option>))}</select></label><label>{t("Saved workspace")}<select aria-label={t("Saved workspace")} value={savedId} onChange={e => load(e.target.value)}><option value="">{t("Unsaved workspace")}</option>{tx(saved.map(s => <option key={s.id} value={s.id}>{tx(s.name)}</option>))}</select></label><Button variant="outline" onClick={() => { setDrawer('search'); }} className="drawer-toggle"><Search size={14}/>{t("Series")}</Button><Button variant="outline" onClick={() => setDrawer('settings')} className="drawer-toggle"><Settings2 size={14}/>{t("Settings")}</Button><span className="workspace-count">{tx(config.lines.length)}{" " + t("/ 6 SERIES \u00B7 LOCAL SINGLE USER")}</span></div>
 {tx(notice && <div className="workspace-notice" role="status">{tx(notice)}</div>)}
 <div className="chart-workbench">
 {tx(drawer && <button className="drawer-shade" aria-label={t("Close workspace panel")} onClick={() => setDrawer(null)}/>)}
 <aside className={'workbench-panel series-browser ' + (drawer === 'search' ? 'drawer-open' : '')} aria-label={t("Indicator browser")}><div className="panel-title"><h2><Search size={14}/>{t("Series Library")}</h2><button className="drawer-toggle" aria-label={t("Close indicator browser")} onClick={() => setDrawer(null)}><X size={18}/></button></div><label className="workspace-field">{t("Search database")}<input aria-label={t("Search indicators")} placeholder={t("ID or indicator name")} value={q} onChange={e => setQ(e.target.value)}/></label><label className="workspace-field">{t("Category")}<select value={category} onChange={e => setCategory(e.target.value)}><option value="">{t("All categories")}</option>{tx(['inflation', 'labor', 'growth', 'interest_rates', 'financial_conditions'].map(c => <option key={c} value={c}>{tx(c.replaceAll('_', ' '))}</option>))}</select></label>{tx(searchError ? <p className="error-text" role="alert">{tx(searchError)}</p> : <div className="series-results">{tx(results.map(s => <div className="series-search-result" key={s.id}><div><strong>{tx(s.id)}</strong><button aria-label={t('Add {p0}', {p0:s.id})} disabled={config.lines.length >= 6} onClick={() => add(s)}><Plus size={15}/></button></div><p>{tx(s.name)}</p><small>{tx(s.units)} · {tx(s.frequency)} · {tx(s.seasonal_adjustment)}</small><small>{tx(s.source)}{tx(!s.has_observations ? ' · Needs sync' : '')}</small></div>))}{tx(!results.length && <p>{t("No matching database series.")}</p>)}</div>)}</aside>
 <section className="workbench-center"><div className="workbench-range"><label className="workspace-field">{t("Chart title")}<input value={config.title} onChange={e => patch({ title: e.target.value })}/></label><div><label className="workspace-field">{t("Start")}<input type="date" value={config.start} onChange={e => patch({ start: e.target.value })}/></label><label className="workspace-field">{t("End")}<input type="date" value={config.end} onChange={e => patch({ end: e.target.value })}/></label></div></div>
 <div className="workspace-mode"><span className={config.data_mode === 'vintage' ? 'vintage-mode' : 'latest-mode'}>{tx(config.data_mode === 'vintage' ? 'HISTORICAL VINTAGE · ' + config.as_of : 'DYNAMIC LATEST DATA')}</span><span>{tx(config.frequency.toUpperCase())}{" " + t("\u00B7 CLOSED PERIODS")}</span></div>
 <Button variant="outline" disabled={busy} onClick={refreshData}>{t('Refresh view')}</Button>
 <RefreshStatus cached={requestMetadata(data)?.cacheHit} busy={busy} error={error} hasData={!!data} lastFetch={lastFetch} retry={refreshData}/>
 {tx(busy && !data ? <div className="workspace-loading skeleton" role="status">{t('Loading real series and calculating chart…')}</div> : data && <><WorkspaceChart ref={chart} option={option} title={tx(config.title)} footnote={tx(`${config.start} — ${data.effective_end} | ${config.data_mode === 'vintage' ? 'ALFRED as of ' + config.as_of : 'FRED · dynamic latest'}\nNative transforms → ${config.frequency}; no fill. Source: FRED / ALFRED.`)} label={t("Multi-indicator macroeconomic research chart")}/>{data.warnings.map(w => <p className="workspace-warning" key={w}>{tx(w)}</p>)}<div className="workspace-provenance">{tx(data.series.map(s => <div key={s.key}><strong>{tx(s.display_name)}</strong><span>{tx(s.provenance.status === 'HISTORICAL_VINTAGE_UNAVAILABLE' ? 'Historical Vintage Unavailable' : s.provenance.status === 'NEEDS_SYNC' ? 'Needs sync' : `${s.units} · ${s.missing_points} missing / ${s.points.length} aligned points`)}</span><small>{tx(s.provenance.native_frequency)}{" " + t("\u00B7 latest source period") + " "}{tx(s.provenance.latest_available_date || '—')} · {tx(s.provenance.source || 'No archive')}</small>{tx(s.provenance.message && <p>{tx(s.provenance.message)}</p>)}</div>))}</div><details className="workspace-method"><summary>{t("Calculation, alignment and version evidence")}</summary><p>{tx(data.mode_note)}</p><p>{tx(data.alignment_note)}</p><p>{tx(data.recession_note)}</p><p>{t("Rolling windows refer to native observations; Z-score uses population standard deviation (ddof=0). Historical mode is date-level only.")}</p>{tx(data.series.map(s => <p key={s.key}>{tx(s.display_name)}: {tx(JSON.stringify(config.lines.find(l => l.key === s.key)?.calculations))}<br />{t("Dependency SHA-256:") + " "}{tx(s.provenance.dependency_fingerprint || 'Unavailable')}{tx(s.provenance.source_url && <> · <a href={s.provenance.source_url} target="_blank" rel="noreferrer">{t("Official source \u2197")}</a></>)}</p>))}</details><div className="workspace-exports"><Button variant="outline" onClick={() => download('macro-workspace.csv', chartCsv(data), 'text/csv;charset=utf-8')}><Download size={14}/>{t("CSV")}</Button><Button variant="outline" onClick={() => chart.current?.exportPng()}><Download size={14}/>{t("PNG")}</Button><Button variant="outline" onClick={() => download('macro-workspace.json', JSON.stringify({ name, description, configuration: frozenConfiguration() }, null, 2), 'application/json')}>{t("JSON configuration")}</Button></div></>)}
 <div className="selected-lines"><h2>{t("Chart series") + " "}<span>{t("select to edit")}</span></h2>{tx(config.lines.map((l, i) => <div className={selected === i ? 'selected-line active-line' : 'selected-line'} key={l.key}><button onClick={() => { setSelected(i); setDrawer('settings'); }}><i style={{ background: chartPalette[resolvedTheme].colors[i] }}/>{tx(l.display_name)}<small>{tx(l.axis)} · {tx(l.calculations.map(c => operations[c.transform]).join(' → '))}{tx(!l.visible ? ' · hidden' : '')}</small></button><button aria-label={t('Remove {p0}', {p0:l.display_name})} disabled={config.lines.length === 1} onClick={() => { patch({ lines: config.lines.filter((_, n) => n !== i) }); setSelected(Math.max(0, selected - 1)); }}><X size={14}/></button></div>))}</div>
 </section>
 <aside className={'workbench-panel line-settings ' + (drawer === 'settings' ? 'drawer-open' : '')} aria-label={t("Chart settings")}><div className="panel-title"><h2><SlidersHorizontal size={14}/>{t("Chart Settings")}</h2><button className="drawer-toggle" aria-label={t("Close chart settings")} onClick={() => setDrawer(null)}><X size={18}/></button></div><label className="workspace-field">{t("Data mode")}<select value={config.data_mode} onChange={e => patch({ data_mode: e.target.value as Configuration['data_mode'], as_of: e.target.value === 'vintage' ? '2023-06-15' : null })}><option value="latest">{t("Latest \u00B7 dynamic")}</option><option value="vintage">{t("Historical Vintage")}</option></select></label>{tx(config.data_mode === 'vintage' && <label className="workspace-field">{t("Shared as-of date")}<input type="date" value={config.as_of || ''} onChange={e => patch({ as_of: e.target.value })}/></label>)}<label className="workspace-field">{t("Common frequency")}<select value={config.frequency} onChange={e => patch({ frequency: e.target.value as Frequency })}>{tx(frequencies.map(f => <option key={f} value={f}>{tx(f)}</option>))}</select></label><label className="workspace-check"><input type="checkbox" checked={config.show_recessions} onChange={e => patch({ show_recessions: e.target.checked })}/>{t("Show recession chronology when available")}</label><hr />
 <label className="workspace-field">{t("Edit series")}<select aria-label={t("Edit chart series")} value={selected} onChange={e => setSelected(Number(e.target.value))}>{tx(config.lines.map((l, i) => <option key={l.key} value={i}>{tx(l.display_name)}</option>))}</select></label><p className="workspace-series-code">{tx(active.series_id)}{tx(active.subtract_series_id ? ' − ' + active.subtract_series_id : '')} {tx(selectedSeries && '· ' + t(selectedSeries.frequency))}</p><label className="workspace-field">{t("Display name")}<input value={active.display_name} onChange={e => patchLine({ display_name: e.target.value })}/></label>
 {tx(active.calculations.map((c, i) => <div className="calculation-step" key={i}><label className="workspace-field">{t("Transform") + " "}{tx(i + 1)}<select aria-label={t('Transform {p0}', {p0:i + 1})} value={c.transform} onChange={e => updateStep(i, { transform: e.target.value, window: e.target.value === 'moving_average' ? 3 : 12, base_date: e.target.value === 'index_100' ? config.start : null })}>{tx(Object.entries(operations).map(([value, label]) => <option key={value} value={value}>{tx(label)}</option>))}</select></label>{tx(['moving_average', 'z_score'].includes(c.transform) && <label className="workspace-field">{t("Native observation window")}{tx(c.transform === 'moving_average' ? <select value={c.window} onChange={e => updateStep(i, { window: Number(e.target.value) })}>{tx([3, 6, 12].map(n => <option key={n} value={n}>{tx(n)}</option>))}</select> : <input type="number" min="3" max="365" value={c.window} onChange={e => updateStep(i, { window: Number(e.target.value) })}/>)}</label>)}{tx(c.transform === 'index_100' && <label className="workspace-field">{t("Exact native base date")}<input type="date" value={c.base_date || ''} onChange={e => updateStep(i, { base_date: e.target.value })}/></label>)}{tx(active.calculations.length > 1 && <button className="text-action" onClick={() => patchLine({ calculations: active.calculations.filter((_, n) => n !== i) })}>{t("Remove step")}</button>)}</div>))}<button className="text-action" disabled={active.calculations.length >= 3} onClick={() => patchLine({ calculations: [...active.calculations, calc('moving_average', 3)] })}>{t("+ Add transformation step")}</button>
 <label className="workspace-field">{t("Y axis")}<select value={active.axis} onChange={e => patchLine({ axis: e.target.value as ChartLine['axis'] })}><option value="left">{t("Left")}</option><option value="right">{t("Right")}</option></select></label><label className="workspace-field">{t("Chart type")}<select value={active.chart_type} onChange={e => patchLine({ chart_type: e.target.value as ChartLine['chart_type'] })}><option value="line">{t("Line")}</option><option value="bar">{t("Bar")}</option></select></label><label className="workspace-field">{t("Line style")}<select value={active.line_style} onChange={e => patchLine({ line_style: e.target.value as ChartLine['line_style'] })}>{tx(['solid', 'dashed', 'dotted'].map(v => <option key={v} value={v}>{tx(v)}</option>))}</select></label><label className="workspace-field">{t("Alignment rule")}<select value={active.alignment} onChange={e => patchLine({ alignment: e.target.value as ChartLine['alignment'] })}><option value="period_end">{t("Period End")}</option><option value="period_average">{t("Period Average")}</option><option value="last_available">{t("Last Available in Period")}</option></select></label><label className="workspace-check"><input type="checkbox" checked={active.visible} onChange={e => patchLine({ visible: e.target.checked })}/>{t("Visible")}</label><hr />
 <h2>{t("Preserve research")}</h2><label className="workspace-field">{t("Workspace name / rename")}<input value={name} onChange={e => setName(e.target.value)}/></label><label className="workspace-field">{t("Description")}<textarea rows={2} value={description} onChange={e => setDescription(e.target.value)}/></label><div className="workspace-save-actions"><Button variant="outline" disabled={working || busy || !!error} onClick={() => save()}><Save size={14}/>{tx(savedId ? 'Update / Rename' : 'Save new')}</Button><Button variant="outline" disabled={working || busy || !!error} onClick={() => save(true)}><Copy size={14}/>{t("Duplicate")}</Button><Button variant="outline" disabled={!savedId || working} onClick={removeSaved}><Trash2 size={14}/>{t("Delete saved")}</Button></div><label className="workspace-import"><FolderOpen size={14}/>{t("Import JSON")}<input aria-label={t("Import workspace JSON")} type="file" accept=".json,application/json" onChange={e => { importFile(e.target.files?.[0]); e.target.value = ''; }}/></label><p className="calendar-note">{t("Single-user local storage. Latest refreshes when data changes. Fixed as-of plus exported source fingerprints identify a historical research result.")}</p>
 </aside></div></ResearchShell>;
}
