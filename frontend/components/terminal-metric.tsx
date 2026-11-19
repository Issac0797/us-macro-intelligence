"use client";

import type { ReactNode } from "react";
import { useUI } from "./presentation-provider";

function Sparkline({ values }: { values: readonly (number | null)[] }) {
  const { t } = useUI();
  const valid = values.filter((value): value is number => value !== null);
  if (valid.length < 2) return <span className="spark-empty">{t("Awaiting history")}</span>;

  const min = Math.min(...valid);
  const spread = Math.max(...valid) - min || 1;
  let path = "";
  let gap = true;
  values.forEach((value, index) => {
    if (value === null) {
      gap = true;
      return;
    }
    path += `${gap ? "M" : "L"}${index / (values.length - 1) * 140},${38 - (value - min) / spread * 32} `;
    gap = false;
  });
  return <svg className="sparkline" viewBox="0 0 140 44" aria-hidden="true">
    <path d={path} fill="none" stroke="currentColor" strokeWidth="1.8" />
  </svg>;
}

export function TerminalMetric({ id, label, value, unit, history, method, date, selected, onSelect }: {
  id: string;
  label: string;
  value: string;
  unit: string;
  history: readonly (number | null)[];
  method: ReactNode;
  date: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return <button type="button" className={"metric-card" + (selected ? " selected" : "")}
    aria-pressed={selected} onClick={onSelect}>
    <div className="metric-top"><span>{label}</span><span className="series-code">{id}</span></div>
    <div className="metric-middle">
      <div className="metric-value">{value}<span>{unit}</span></div>
      <Sparkline values={history} />
    </div>
    <div className="metric-bottom"><span>{method}</span><span className="metric-date">{date}</span></div>
  </button>;
}
