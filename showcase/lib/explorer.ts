import type { Series, Transform } from "./research.ts";

export const rangePresets = ["1Y", "3Y", "5Y", "10Y", "ALL"] as const;
export type RangePreset = typeof rangePresets[number];

export const explorerSections = {
  "": ["CPIAUCSL", "CPILFESL", "UNRATE", "PAYEMS", "DFF", "DGS2", "DGS10"],
  inflation: ["CPIAUCSL", "CPILFESL"],
  labor: ["UNRATE", "PAYEMS"],
} as const;

export function initialTransform(id: string): Transform {
  if (id === "CPIAUCSL" || id === "CPILFESL") return "yoy";
  return id === "PAYEMS" ? "absolute_change" : "raw";
}

export function rangeStart(end: string, preset: RangePreset) {
  if (!end || preset === "ALL") return "";
  const [year, month, day] = end.split("-").map(Number);
  const startYear = year - Number.parseInt(preset, 10);
  const lastDay = new Date(Date.UTC(startYear, month, 0)).getUTCDate();
  return new Date(Date.UTC(startYear, month - 1, Math.min(day, lastDay))).toISOString().slice(0, 10);
}

export function availableSeries(series: Series[], ids: readonly string[]) {
  const byId = new Map(series.map(item => [item.id, item]));
  return ids.flatMap(id => {
    const item = byId.get(id);
    return item ? [item] : [];
  });
}
