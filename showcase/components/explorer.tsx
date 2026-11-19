"use client";

import Link from "next/link";
import { BookOpen, ExternalLink } from "lucide-react";
import { useMemo, useState } from "react";
import { TerminalMetric } from "../shared/components/terminal-metric";
import { useUI } from "../shared/components/presentation-provider";
import { availableSeries, explorerSections, initialTransform, rangePresets, rangeStart, type RangePreset } from "../lib/explorer";
import { supported, transform, units, type Snapshot, type Transform } from "../lib/research";
import { Chart } from "./chart";

export function RangeButtons({ value, onChange }: {
  value: RangePreset | null;
  onChange: (range: RangePreset) => void;
}) {
  const { t } = useUI();
  return <div className="range-control" aria-label={t("Chart time range")}>
    {rangePresets.map(range => <button type="button" key={range} aria-pressed={range === value}
      className={range === value ? "active" : ""} onClick={() => onChange(range)}>{t(range)}</button>)}
  </div>;
}

function suffix(unit: string) {
  if (unit === "Percent" || unit === "%") return "%";
  return unit === "Thousands of persons" ? "K" : unit === "pp" ? "pp" : "";
}

export function SnapshotExplorer({ snapshot, section }: {
  snapshot: Snapshot;
  section: keyof typeof explorerSections;
}) {
  const { t, locale, number, date } = useUI();
  const zh = locale === "zh-CN";
  const name = (item: Snapshot["series"][number]) => zh ? item.title_zh : item.title;
  const choices = useMemo(() => availableSeries(snapshot.series, explorerSections[section]), [snapshot, section]);
  const [selected, setSelected] = useState<string>(explorerSections[section][0]);
  const [method, setMethod] = useState<Transform>(() => initialTransform(explorerSections[section][0]));
  const [range, setRange] = useState<RangePreset>("5Y");
  const active = choices.find(item => item.id === selected) ?? choices[0];
  const methods: Record<Transform, string> = {
    raw: zh ? "原始值" : "Level",
    yoy: zh ? "同比" : "YoY",
    mom: zh ? "环比" : "MoM",
    absolute_change: zh ? "上期变化" : "Change from prior period",
  };

  const cards = useMemo(() => choices.map(series => {
    const display = initialTransform(series.id);
    const points = transform(series, display);
    return { series, display, points, latest: points.findLast(point => point.value !== null) };
  }), [choices]);
  const activeMethod = active && supported(active, method) ? method : "raw";
  const points = useMemo(() => {
    if (!active) return [];
    const start = rangeStart(active.coverage.end, range);
    return transform(active, activeMethod).filter(point => point.date >= start);
  }, [active, activeMethod, range]);
  const lines = useMemo(() => active ? [{ name: zh ? active.title_zh : active.title, points }] : [], [active, points, zh]);
  if (!active) return <div className="empty-box">{zh ? "此快照没有适用于该页面的指标。" : "This snapshot has no series for this page."}</div>;

  const raw = new Map(active.observations.map(point => [point.date, point.value]));
  const latest = points.findLast(point => point.value !== null);
  const unit = units(active, activeMethod);
  const comparisonId = (choices.find(item => item.id !== active.id) ??
    snapshot.series.find(item => item.id !== active.id))?.id;
  const workspace = `/workspace/?${new URLSearchParams({ series: active.id, transform: activeMethod, range })}`;
  const facts = [
    [t("Series ID"), active.id], [t("Frequency"), t(active.frequency)],
    [t("Adjustment"), active.seasonal_adjustment], [t("Native units"), active.units],
    [t("Latest valid period"), latest ? date(latest.date) : "—"],
    [zh ? "覆盖范围" : "Coverage", `${date(active.coverage.start)} – ${date(active.coverage.end)}`],
  ];
  const choose = (id: string) => {
    if (id === active.id) return;
    setSelected(id);
    setMethod(initialTransform(id));
  };

  return <>
    <div className="metrics-grid public-metrics">
      {cards.map(({ series, display, points, latest }) => <TerminalMetric
        key={series.id} id={series.id} label={name(series)}
        value={number(latest?.value, series.id === "PAYEMS" ? 0 : 2)} unit={suffix(units(series, display))}
        method={methods[display]} date={latest?.date ?? "—"} history={points.slice(-36).map(point => point.value)}
        selected={series.id === active.id} onSelect={() => choose(series.id)}
      />)}
    </div>
    <div className="research-grid">
      <section className="history-panel terminal-surface">
        <div className="panel-heading">
          <div>
            <div className="panel-kicker">{t("HISTORICAL EXPLORER")}</div>
            <h2>{name(active)} <span className="frequency-tag">{t(active.frequency)}</span></h2>
          </div>
          <a className="source-link" href={active.source_url} target="_blank" rel="noreferrer">
            {t("View source")}<ExternalLink size={13} aria-hidden="true" />
          </a>
        </div>
        <div className="chart-toolbar">
          <div className="chart-controls">
            <label className="sr-only" htmlFor="explorer-series">{t("Series")}</label>
            <select id="explorer-series" value={active.id} onChange={event => choose(event.target.value)}>
              {choices.map(item => <option value={item.id} key={item.id}>{name(item)}</option>)}
            </select>
            <label className="sr-only" htmlFor="explorer-transform">{t("Transformation")}</label>
            <select id="explorer-transform" value={activeMethod} onChange={event => setMethod(event.target.value as Transform)}>
              {(Object.keys(methods) as Transform[]).filter(value => supported(active, value))
                .map(value => <option key={value} value={value}>{methods[value]}</option>)}
            </select>
          </div>
          <RangeButtons value={range} onChange={setRange} />
        </div>
        <div className="chart-summary">
          <span className="chart-legend-dot" /><span>{methods[activeMethod]}</span>
          <strong>{number(latest?.value, 2)}{suffix(unit)}</strong>
          {!suffix(unit) && <span className="chart-units">{unit}</span>}
        </div>
        <Chart key={active.id + activeMethod + range} label={name(active)} unit={unit} lines={lines}
          embedded exportContext={{ snapshot, series: active, method: activeMethod }} />
        <div className="chart-foot">
          <span>{number(points.length, 0)} {t("observations")} <span className="strip-divider" />{t("Missing values are not interpolated")}</span>
          <span>{t("Scroll to zoom · Drag to explore")}</span>
        </div>
      </section>
      <section className="detail-panel terminal-surface">
        <div data-slot="card-content">
          <div className="panel-kicker">{t("SERIES BRIEF")}</div>
          <h2>{name(active)}</h2>
          <p className="brief-description">{active.source}</p>
          <dl className="facts">
            {facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
          </dl>
          <div className="method-note">
            <BookOpen size={16} aria-hidden="true" />
            <div><strong>{t("Research note")}</strong><p>{zh
              ? "保留原始观测频率和缺失值。同比及环比按日历月份计算。"
              : "Native frequency and missing values are preserved. Year-over-year and month-over-month rates use calendar months."}</p></div>
          </div>
          <div className="workspace-quick-actions public-quick-actions">
            <Link href={workspace}>{t("Add to Workspace")}</Link>
            {comparisonId && <Link href={`${workspace}&compare=${encodeURIComponent(comparisonId)}`}>{t("Compare in Workspace")}</Link>}
          </div>
        </div>
      </section>
    </div>
    <section className="observations-panel terminal-surface">
      <div className="panel-heading">
        <div><div className="panel-kicker">{t("LATEST READINGS")}</div><h2>{t("Observation ledger")}</h2></div>
        <span className="ledger-label">{active.id} · {methods[activeMethod]}</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>{t("Observation period")}</th><th>{t("Transformed value")}</th>
            <th>{t("Original value")}</th><th>{t("Source")}</th></tr></thead>
          <tbody>{points.slice(-8).reverse().map(point => <tr key={point.date}>
            <td className="mono">{point.date}</td>
            <td className="mono table-value">{point.value === null ? "—" : `${number(point.value, 2)} ${unit}`}</td>
            <td className="mono">{raw.get(point.date) ?? "—"}</td>
            <td><a href={active.source_url} target="_blank" rel="noreferrer">{active.source}</a></td>
          </tr>)}</tbody>
        </table>
      </div>
    </section>
  </>;
}
