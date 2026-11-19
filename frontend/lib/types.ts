export type Series = {
  id: string; short_name: string; title: string; category: string; frequency: string; units: string;
  unit_kind: string; seasonal_adjustment: string; agency: string; default_transform: string;
  source: string; source_url: string; last_synced_at: string | null; available_transforms: string[];
};
export type Point = {date: string; value: number | null; raw_value: string; source: string;
  version: string; collected_at: string; released_at: string | null; realtime_start: string | null; realtime_end: string | null};
export type MacroCard = {series: Series; value: number | null; previous_value: number | null; change: number | null;
  observation_date: string | null; latest_observation_date: string | null; collected_at: string | null;
  provider: string | null; transform: string; units: string; stale: boolean; history: Point[]};
export type Overview = {generated_at: string; cards: MacroCard[]; latest_sync: {status: string; provider: string; finished_at: string | null} | null; data_status: string};
export type ObservationResponse = {series: Series; transform: string; units: string; observations: Point[]; count: number; availability?:import('./chart-availability').Availability};
export const transformNames: Record<string, string> = {raw: "Original level", mom: "Month over month", yoy: "Year over year", annualized_3m: "3M annualized", annualized_6m: "6M annualized", moving_average: "Moving average", absolute_change: "Absolute change"};
export function number(value: number | null | undefined, digits=2) {
  return value == null ? "—" : new Intl.NumberFormat("en-US", {maximumFractionDigits: digits, minimumFractionDigits: digits}).format(value);
}
export function unitSuffix(units: string) { const unit = units.toLowerCase(); return unit === "percent" ? "%" : unit === "percentage points" ? "pp" : unit === "thousands of persons" ? "K" : ""; }
