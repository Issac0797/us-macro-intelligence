"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useUI } from "../shared/components/presentation-provider";
import { rangeStart, type RangePreset } from "../lib/explorer";
import { readWorkspace, supported, transform, units, type Snapshot, type Transform } from "../lib/research";
import { applyWorkspaceLink, commonDomain, downloadFile, initialWorkbench, restoreWorkbench, type Panel, type Workbench } from "../lib/workbench";
import { Chart } from "./chart";
import { RangeButtons } from "./explorer";

const storageKey = "macro-showcase-workspace-v2";
const legacyKey = "macro-showcase-workspace-v1";
const methods = ["raw", "yoy", "mom", "absolute_change"] as const;

export function StaticWorkbench({ snapshot }: { snapshot: Snapshot }) {
  const { locale } = useUI();
  const zh = locale === "zh-CN";
  const L = (en: string, cn: string) => zh ? cn : en;
  const router = useRouter();
  const query = useSearchParams().toString();
  const [config, setConfig] = useState<Workbench>(initialWorkbench);
  const [status, setStatus] = useState<"saved" | "reset" | "unavailable" | null>(null);
  const [preset, setPreset] = useState<RangePreset | null>(null);
  const latestDate = useMemo(() => snapshot.series.map(item => item.coverage.end).sort().at(-1) ?? "", [snapshot]);

  useEffect(() => {
    let restored = restoreWorkbench(null, snapshot.series);
    try {
      const legacy = localStorage.getItem(legacyKey);
      restored = restoreWorkbench(localStorage.getItem(storageKey), snapshot.series,
        legacy ? readWorkspace(legacy, snapshot.series.map(item => item.id)) : undefined);
    } catch {}
    setConfig(applyWorkspaceLink(restored, new URLSearchParams(query), snapshot.series));
    setPreset(null);
  }, [query, snapshot]);

  const validRange = !config.end || config.start <= config.end;
  const domain = useMemo(() => commonDomain(snapshot, config.start, validRange ? config.end : config.start),
    [snapshot, config.start, config.end, validRange]);
  const seriesById = useMemo(() => new Map(snapshot.series.map(item => [item.id, item])), [snapshot]);
  const traces = useMemo(() => config.panels.map(panel => {
    const series = seriesById.get(panel.series);
    if (!series) return null;
    const name = zh ? series.title_zh : series.title;
    const points = transform(series, panel.transform)
      .filter(point => validRange && (!config.start || point.date >= config.start) && (!config.end || point.date <= config.end));
    return { series, lines: [{ name, points }] };
  }), [config.panels, config.start, config.end, seriesById, validRange, zh]);
  const change = (patch: Partial<Workbench>) => {
    setConfig(current => ({ ...current, ...patch }));
    setStatus(null);
  };
  const panelChange = (index: number, patch: Partial<Panel>) => {
    setConfig(current => ({
      ...current, panels: current.panels.map((panel, i) => i === index ? { ...panel, ...patch } : panel),
    }));
    setStatus(null);
  };
  const persist = (value: Workbench, action: "saved" | "reset") => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(value));
      setStatus(action);
      if (query) router.replace("/workspace/", { scroll: false });
    } catch {
      setStatus("unavailable");
    }
  };
  const labels: Record<Transform, string> = {
    raw: L("Level", "原始值"), yoy: L("YoY (%)", "同比 (%)"),
    mom: L("MoM (%)", "环比 (%)"), absolute_change: L("Change", "上期变化"),
  };

  return <>
    <section className="dashboard-global static-workspace-controls" aria-label={L("Workspace controls", "工作区设置")}>
      <div className="controls">
        <RangeButtons value={preset} onChange={range => {
          change({ start: rangeStart(latestDate, range), end: "" });
          setPreset(range);
        }} />
        <label>{L("From", "开始")}<input type="date" value={config.start} onChange={event => {
          change({ start: event.target.value });
          setPreset(null);
        }} /></label>
        <label>{L("Through", "结束")}<input type="date" value={config.end} onChange={event => {
          change({ end: event.target.value });
          setPreset(null);
        }} /></label>
        <label className="checkbox"><input type="checkbox" checked={config.linked}
          onChange={event => change({ linked: event.target.checked })} />{L("Link all four charts", "四图光标与缩放联动")}</label>
      </div>
      <div className="controls">
        <button type="button" disabled={!validRange} onClick={() => persist(config, "saved")}>{L("Save configuration", "保存配置")}</button>
        <button type="button" onClick={() => {
          const reset = restoreWorkbench(null, snapshot.series);
          change(reset);
          setPreset(null);
          persist(reset, "reset");
        }}>{L("Reset configuration", "重置配置")}</button>
        <button type="button" disabled={!validRange} onClick={() => downloadFile("macro-workspace.json", JSON.stringify({
          configuration: config, snapshot_generated_at: snapshot.generated_at, is_live: false,
        }, null, 2))}>{L("Export workspace JSON", "导出工作区 JSON")}</button>
        {status && <span role="status">{{
          saved: L("Saved in this browser.", "已保存在此浏览器。"),
          reset: L("Default configuration restored.", "已恢复默认配置。"),
          unavailable: L("Browser storage is unavailable.", "浏览器存储不可用。"),
        }[status]}</span>}
        {!validRange && <span role="alert">{L("The start date must be on or before the end date.", "开始日期须早于或等于结束日期。")}</span>}
      </div>
    </section>
    <p className="explanation">{L(
      "Linked charts share a UTC time axis and show a gap when the cursor date has no native observation.",
      "联动图表使用共同的 UTC 时间轴。光标所在日期缺少原生观测时显示为空。")}</p>
    <div className="chart-grid four-chart-grid">
      {config.panels.map((panel, i) => {
        const trace = traces[i];
        if (!trace) return null;
        const { series, lines } = trace;
        const panelLabel = L("Panel " + (i + 1), "图表 " + (i + 1));
        return <div className="terminal-surface static-workspace-panel" key={i} data-panel={i + 1}>
          <div className="panel-config">
            <label>{L("Series", "序列")}<select aria-label={L(panelLabel + " series", panelLabel + " 序列")} value={panel.series}
              onChange={event => panelChange(i, { series: event.target.value, transform: "raw" })}>
              {snapshot.series.map(item => <option key={item.id} value={item.id}>
                {item.id} · {zh ? item.title_zh : item.title}
              </option>)}
            </select></label>
            <label>{L("Transform", "转换")}<select aria-label={L(panelLabel + " transform", panelLabel + " 转换")}
              value={panel.transform} onChange={event => panelChange(i, { transform: event.target.value as Transform })}>
              {methods.filter(method => supported(series, method)).map(method =>
                <option key={method} value={method}>{labels[method]}</option>)}
            </select></label>
          </div>
          <Chart label={panelLabel + " · " + lines[0].name} unit={units(series, panel.transform)} lines={lines}
            linked={config.linked} domain={domain} exportContext={{ snapshot, series, method: panel.transform }} />
        </div>;
      })}
    </div>
    <p className="explanation">{L(
      "CSV and JSON include displayed observations and source terms. PNG names the snapshot and original agency.",
      "CSV 和 JSON 包含当前展示的观测与来源条款。PNG 标注快照及原始机构。")}</p>
  </>;
}
