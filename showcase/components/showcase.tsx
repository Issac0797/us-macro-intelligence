'use client';
import {createContext,Suspense,useContext,useEffect,useMemo,useState,type ReactNode} from 'react';
import {PresentationProvider,useUI} from '../shared/components/presentation-provider';
import Link from 'next/link';
import { Database, ExternalLink } from 'lucide-react';
import {TerminalFrame} from '../shared/components/terminal-frame';
import {SnapshotExplorer} from './explorer';
import {validLocale,validTheme} from '../shared/lib/presentation';
import {Chart} from './chart';
import {StaticWorkbench} from './workbench';
import {PublicSearch} from './search';
import {publicPages} from '../lib/search';
import {transform,units,spread,correlation,defaults,readWorkspace,supported,type Series,type Snapshot,type Workspace,type Transform,type Point} from '../lib/research';

function RestoreDisplay(){const {setTheme,setLocale}=useUI();useEffect(()=>{try{setLocale(validLocale(localStorage.getItem('macro-locale'))||(navigator.language.startsWith('zh')?'zh-CN':'en-US'));setTheme(validTheme(localStorage.getItem('macro-theme')));}catch{}},[setLocale,setTheme]);return null;}
const SnapshotContext = createContext<{ snapshot: Snapshot | null; error: boolean }>({ snapshot: null, error: false });
const availableRoutes = publicPages.map(([section]) => section ? '/' + section : '/');
const emptySeries: Series[] = [];

export function DisplayProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/data/snapshot.json', { signal: controller.signal })
      .then(response => {
        if (!response.ok) throw new Error('Snapshot unavailable');
        return response.json();
      })
      .then((data: Snapshot) => {
        if (data.schema_version !== 1 || data.is_live !== false || !data.series?.length) {
          throw new Error('Invalid snapshot');
        }
        if (!controller.signal.aborted) setSnapshot(data);
      })
      .catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, []);
  const data = useMemo(() => ({ snapshot, error }), [snapshot, error]);
  return <PresentationProvider initialLocale="en-US" initialTheme="system">
    <RestoreDisplay />
    <SnapshotContext.Provider value={data}>{children}</SnapshotContext.Provider>
  </PresentationProvider>;
}

const title = (series: Series, zh: boolean) => zh ? series.title_zh : series.title;

export function Showcase({ section = '' }: { section?: string }) {
  const ui = useUI();
  const zh = ui.locale === 'zh-CN';
  const L = (en: string, cn: string) => zh ? cn : en;
  const { snapshot, error } = useContext(SnapshotContext);
  const [config, setConfig] = useState<Workspace>(defaults);
  const [saved, setSaved] = useState('');
  const [curveDate, setCurveDate] = useState('');
  const [compareDate, setCompareDate] = useState('');
  const [collapsed, setCollapsed] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    try { setCollapsed(localStorage.getItem('macro-public-rail') === 'collapsed'); } catch {}
    const viewport = matchMedia('(max-width: 800px)');
    const update = () => {
      setMobile(viewport.matches);
      setMobileOpen(false);
    };
    update();
    viewport.addEventListener('change', update);
    return () => viewport.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    if (!mobileOpen) return;
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') setMobileOpen(false); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [mobileOpen]);
  useEffect(() => {
    if (!snapshot) return;
    try {
      setConfig(readWorkspace(localStorage.getItem('macro-showcase-workspace-v1'), snapshot.series.map(series => series.id)));
    } catch {}
  }, [snapshot]);
  const toggleRail = () => {
    if (mobile) {
      setMobileOpen(value => !value);
      return;
    }
    const next = !collapsed;
    setCollapsed(next);
    try { localStorage.setItem('macro-public-rail', next ? 'collapsed' : 'expanded'); } catch {}
  };
 const lookup=useMemo(()=>new Map(snapshot?.series.map(s=>[s.id,s])||[]),[snapshot]);
 const series=(id:string)=>lookup.get(id)!;
 const route = publicPages.find(page => page[0] === section) ?? publicPages[0];
 const label = zh ? route[2] : route[1];
 const pageTitle = section === '' ? L('U.S. economy at a glance', '美国经济一览')
   : section === 'inflation' ? L('Tracking the inflation cycle', '追踪通胀周期')
   : section === 'labor' ? L('The pulse of the labor market', '劳动力市场动态') : label;
 const kicker = ['', 'inflation', 'labor', 'yield-curve'].includes(section)
   ? L('ECONOMIC INDICATORS', '经济指标') : L('U.S. RESEARCH TERMINAL', '美国宏观研究终端');
 const change=(patch:Partial<Workspace>)=>{setConfig(c=>({...c,...patch}));setSaved('')};
 const filter=(p:Point[])=>p.filter(p=>(!config.start||p.date>=config.start)&&(!config.end||p.date<=config.end));
 const trace=(id:string,t:Transform)=>({name:title(series(id),zh),points:filter(transform(series(id),t))});
 const renderChart=(id:string,t:Transform,label?:string)=> <Chart key={label||id} label={label||title(series(id),zh)} unit={units(series(id),t)} lines={[trace(id,t)]} linked={(section==='workspace'||section==='analytics')&&config.linked}/>;
 const maturities = useMemo(() => section === 'yield-curve' ?
   snapshot?.series.filter(item => (item.maturity_months ?? 0) > 0)
     .sort((a, b) => a.maturity_months! - b.maturity_months!) ?? [] : [], [section, snapshot]);
 const dates = useMemo(() => {
   const coverage = maturities.map(item => new Set(item.observations
     .filter(point => point.value !== null).map(point => point.date)));
   return [...(coverage[0] ?? [])].filter(date => coverage.every(values => values.has(date)));
 }, [maturities]);
 const activeCurve=curveDate||dates.at(-1)||'';
 const toolbar=<div className="controls"><label>{L('From','开始')}<input aria-label={L('From','开始')} type="date" value={config.start} onChange={e=>change({start:e.target.value})}/></label><label>{L('Through','结束')}<input aria-label={L('Through','结束')} type="date" value={config.end} onChange={e=>change({end:e.target.value})}/></label><button onClick={()=>change({start:'',end:''})}>{L('Full snapshot','完整快照')}</button>{config.end&&config.start>config.end&&<strong role="alert">{L('Start must precede end.','开始日期必须早于结束日期。')}</strong>}</div>;
 return <TerminalFrame className={mobileOpen ? "public-terminal mobile-rail-open" : "public-terminal"}
   label={label} collapsed={mobile ? !mobileOpen : collapsed} onToggle={toggleRail}
   onNavigate={mobileOpen ? () => setMobileOpen(false) : undefined}
   availableRoutes={availableRoutes} edition={L('PUBLIC RESEARCH TERMINAL', '公开宏观研究终端')}
   status={error ? L('SNAPSHOT UNAVAILABLE', '快照无法加载') : L('STATIC SNAPSHOT', '静态快照')}
   tools={<PublicSearch series={snapshot?.series ?? emptySeries} />}
   sidebarFooter={<div className="source-box"><Database size={17} aria-hidden="true" />
     <div><strong>{L('Reviewed official data', '已审核官方数据')}</strong><p>BLS · Federal Reserve</p>
       <Link href="/sources/">{L('Sources & licenses', '来源与许可')}<ExternalLink size={11} aria-hidden="true" /></Link>
     </div>
   </div>}
   statusFooter={<><span>US MACRO INTELLIGENCE · {L('PUBLIC EDITION', '公开版')}</span>
     {snapshot && <span>{L('Snapshot generated', '快照生成于')} {ui.date(snapshot.generated_at, 'UTC', true)} UTC</span>}</>}>
   <div className="page-heading">
     <div><div className="eyebrow">{kicker}</div><h1>{pageTitle}</h1></div>
   </div>
   <div className="data-strip public-snapshot-strip">
     <div><strong>{L('SNAPSHOT · NOT LIVE', '历史快照 · 非实时')}</strong>
       {snapshot && <><span className="strip-divider" /><time dateTime={snapshot.generated_at}>
         {ui.date(snapshot.generated_at, 'UTC', true)} UTC
       </time><span>{ui.number(snapshot.series.length, 0)} {L('reviewed series', '个已审核序列')}</span></>}
     </div>
     <Link href="/sources/">{L('Sources & licenses', '来源与许可')}</Link>
   </div>
   {error && <div role="alert" className="notice">
     {L('Snapshot unavailable. Reload this page or download the reviewed release.', '快照无法加载。请刷新页面或下载已审核版本。')}
   </div>}
   {!snapshot && !error && <div role="status" className="chart-placeholder">
     {L('Loading reviewed public data…', '正在加载已审核公开数据…')}
   </div>}
   {snapshot && <>
     {(section === '' || section === 'inflation' || section === 'labor') &&
       <SnapshotExplorer key={section} snapshot={snapshot} section={section} />}
 {section==='yield-curve'&&<><div className="controls"><label>{L('Observation date','观测日期')}<select aria-label={L('Observation date','观测日期')} value={activeCurve} onChange={e=>setCurveDate(e.target.value)}>{[...dates].reverse().map(d=><option key={d}>{d}</option>)}</select></label><label>{L('Compare date','比较日期')}<select aria-label={L('Compare date','比较日期')} value={compareDate} onChange={e=>setCompareDate(e.target.value)}><option value="">{L('None','不比较')}</option>{[...dates].reverse().map(d=><option key={d}>{d}</option>)}</select></label></div><p className="explanation">{L('Constant-maturity nominal Treasury yields. Only dates with observations for every included maturity are selectable. No interpolation or forward filling.','名义国债固定期限收益率；仅可选择所有纳入期限均有观测值的日期，不插值、不前填。')}</p><Chart label={L('Treasury term structure','国债期限结构')} unit="%" categories={maturities.map(s=>title(s,zh))} lines={[activeCurve,...(compareDate?[compareDate]:[])].map(d=>({name:d,points:maturities.map(s=>({date:d,value:s.observations.find(p=>p.date===d)?.value??null}))}))}/><div className="table-scroll public-data-table"><table><thead><tr><th>{L('Maturity','期限')}</th><th>{activeCurve} (%)</th></tr></thead><tbody>{maturities.map(s=><tr key={s.id}><td>{title(s,zh)}</td><td>{ui.number(s.observations.find(p=>p.date===activeCurve)?.value)}</td></tr>)}</tbody></table></div>{toolbar}<Chart label={L('10Y minus 2Y spread','10年减2年利差')} unit="pp" lines={[{name:L('10Y − 2Y','10年 − 2年'),points:filter(spread(series('DGS10'),series('DGS2')))}]}/></>}
 {section==='workspace'&&<Suspense fallback={<div role="status" className="chart-placeholder">
   {L('Loading workspace…', '正在加载工作区…')}
 </div>}><StaticWorkbench snapshot={snapshot}/></Suspense>}
 {section==='analytics'&&<>{toolbar}<div className="controls">{(['first','second'] as const).map((key,i)=><label key={key}>{L(`Series ${i+1}`,`序列 ${i+1}`)}<select aria-label={L(`Series ${i+1}`,`序列 ${i+1}`)} value={config[key]} onChange={e=>change({[key]:e.target.value,transform:'raw'})}>{snapshot.series.map(s=><option key={s.id} value={s.id}>{s.id} · {title(s,zh)}</option>)}</select></label>)}<label>{L('Transform','转换')}<select aria-label={L('Transform','转换')} value={supported(series(config.first),config.transform)&&supported(series(config.second),config.transform)?config.transform:'raw'} onChange={e=>change({transform:e.target.value as Transform})}>{(['raw','yoy','mom','absolute_change'] as Transform[]).filter(t=>supported(series(config.first),t)&&supported(series(config.second),t)).map(t=><option key={t} value={t}>{({raw:L('Level','原始值'),yoy:L('YoY (%)','同比 (%)'),mom:L('MoM (%)','环比 (%)'),absolute_change:L('Absolute change','绝对变化')})[t]}</option>)}</select></label><label className="checkbox"><input type="checkbox" checked={config.linked} onChange={e=>change({linked:e.target.checked})}/>{L('Link zoom & cursor','联动缩放与光标')}</label><button onClick={()=>{try{localStorage.setItem('macro-showcase-workspace-v1',JSON.stringify(config));setSaved(L('Saved in this browser.','已保存在此浏览器。'))}catch{setSaved(L('Browser storage is unavailable.','浏览器存储不可用。'))}}}>{L('Save configuration','保存配置')}</button><button onClick={()=>{change({...defaults});try{localStorage.removeItem('macro-showcase-workspace-v1')}catch{}}}>{L('Reset configuration','重置配置')}</button><span role="status">{saved}</span></div>{(()=>{const t=supported(series(config.first),config.transform)&&supported(series(config.second),config.transform)?config.transform:'raw',a=filter(transform(series(config.first),t)),b=filter(transform(series(config.second),t)),stats=correlation(a,b);return <>{section==='analytics'&&<div className="notice"><strong>{L('Pearson correlation','皮尔逊相关系数')}: {ui.number(stats.value,4)}</strong><p>{L('Exact-date matched pairs','日期完全匹配的观测对')}: {stats.n}. {L('Computed in your browser over the selected range and transform. Correlation is descriptive, not causal; level correlations may be spurious. Different frequencies are not resampled.','按所选范围和转换在浏览器内计算。相关性仅作描述，不代表因果；水平值相关性可能虚假。不同频率不重采样。')}</p></div>}<div className="chart-grid">{renderChart(config.first,t,L('Panel 1','图表 1')+' · '+title(series(config.first),zh))}{renderChart(config.second,t,L('Panel 2','图表 2')+' · '+title(series(config.second),zh))}</div></>})()}<p className="explanation">{L('Drag the bottom handles or scroll inside a time chart to zoom. Charts keep native units; changes in percent rates use percentage points (pp). Missing observations remain gaps. Saved configuration includes series, transforms, dates and linking, not a server account.','拖动底部滑块或在时间图表内滚动以缩放。保留各图原生单位；利率变化使用百分点 (pp)，缺失观测保留为空。保存内容为序列、转换、日期和联动设置，不涉及服务器账户。')}</p></>}
 {section==='business-cycle'&&<><h2>{L('Business cycle research — static edition limits','经济周期研究：静态版限制')}</h2><div className="notice">{L('This preview does not redistribute NBER recession dates or unreviewed indicators. Cycle classification, recession shading, vintage comparisons and database research remain in the local terminal. No synthetic cycle signal or forecast is shown.','本预览不再分发 NBER 衰退日期或未获审核的指标。周期分类、衰退阴影、历史版本比较和数据库研究保留在本地终端，不展示人为生成的周期信号或预测。')}</div><Link className="public-page-link" href="/analytics/">{L('Open available descriptive analytics →','查看可用的描述性分析 →')}</Link></>}
 {section==='about'&&<div className="notice"><strong>v0.1.0 Public Preview · {L('Frozen public snapshot','固定公开快照')}</strong><p>{L('13 reviewed series · 17,192 observation records · no live backend. Observation dates and generation time are separate.','13 个已审核系列 · 17,192 条观测记录 · 无实时后端。观测日期与快照生成时间分别标注。')}</p></div>}
 {section==='fed'&&<><div className="notice">{L('Selected verified historical decisions. This is not a complete chronology, a current policy signal, or a projection. Statement differences, SEP/Dot Plot, meeting search and point-in-time reconstruction require the local terminal.','仅展示选定且已核验的历史决策，不构成完整年表、当前政策信号或预测。声明对比、SEP/点阵图、会议检索及历史时点重建需要本地完整版。')}</div><div className="policy-list">{snapshot.fed_decisions.map(d=><article className="terminal-surface" key={d.date}><time>{ui.date(d.date)}</time><h2>{ui.number(d.lower,2)}–{ui.number(d.upper,2)}%</h2><p>{L('Federal funds target range','联邦基金目标区间')}</p><a href={d.source_url} target="_blank" rel="noreferrer">{L('Verified official statement ↗','已核验官方声明 ↗')}</a></article>)}</div>{renderChart('DFF','raw',L('Effective federal funds rate (not the target range)','有效联邦基金利率（非目标区间）'))}</>}
 {(section==='sources'||section==='about')&&<><h2>{L('Data you can trace.','可以追溯的数据。')}</h2><p className="explanation">{L('Frozen observations downloaded directly from original government agencies. Familiar FRED series IDs are aliases only. No FRED/ALFRED dataset is redistributed. Original data are not licensed under the project’s MIT code license.','固定快照直接下载自原始政府机构；常用 FRED Series ID 仅作别名，不再分发 FRED/ALFRED 数据集。原始数据不属于项目 MIT 代码许可范围。')}</p><p>{L('Revision basis: latest observations at retrieval; these are not historical vintages or exact release-time records.','修订口径：下载时的最新观测；不属于历史版本或精确发布时间记录。')}</p><div className="downloads"><a href="/data/snapshot.json" download>{L('Download snapshot JSON','下载快照 JSON')}</a><a href="/data/licenses.json">{L('Independent data license register','独立数据许可清单')}</a><a href="/data/snapshot.schema.json">JSON Schema</a><a href="/data/third-party-notices.txt">{L('Software notices','软件许可声明')}</a></div><div className="table-scroll public-data-table"><table><thead><tr>{[L('Series / Native ID','序列 / 原生编号'),L('Unit','单位'),L('Coverage','覆盖范围'),L('Source / permission','来源 / 许可')].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{snapshot.series.map(s=><tr key={s.id}><td><strong>{s.id}</strong><br/>{s.native_id}<br/>{title(s,zh)}</td><td>{s.units}<br/>{s.frequency==='monthly'?L('Monthly · SA','月频 · 季调'):L('Daily · NSA','日频 · 未季调')}</td><td>{s.coverage.start}<br/>→ {s.coverage.end}<br/>{ui.number(s.coverage.count,0)} {L('observations','条观测')}</td><td><a href={s.source_url} target="_blank" rel="noreferrer">{s.source} ↗</a><p>{s.notice}</p><a href={s.policy_url} target="_blank" rel="noreferrer">{L('Permission policy ↗','许可政策 ↗')}</a></td></tr>)}</tbody></table></div></>}
 <details className="limitations"><summary>{L('Static edition limits & disclaimer','静态版限制与免责声明')}</summary><p>{L('No live refresh, economic calendar monitor, ALFRED revisions, database writes, server workspaces, custom imports or forecasts. PCE, GDP, NBER and other unreviewed data are excluded. Browser storage can be cleared by your browser. Downloads and charts contain historical snapshot data only. This independent research software is provided without warranty, does not imply agency endorsement and is not investment advice.','不提供实时刷新、经济日历监控、ALFRED 修订、数据库写入、服务器工作区、自定义导入或预测。PCE、GDP、NBER 及其他未审核数据均被排除。浏览器可能清除本地存储。下载和图表仅包含历史快照。独立研究软件不作担保，不代表官方背书，也不构成投资建议。')}</p></details>
 </>}
 <footer className="footer"><span><Database size={13} aria-hidden="true" />
   {L('Original agencies retain their data terms.', '原始机构数据保留各自条款。')}
 </span><span>{L('Observation dates are separate from snapshot generation.', '观测日期与快照生成时间分别标注。')}</span></footer>
 </TerminalFrame>;
}
