export type Availability={status:string;native_count?:number;native_valid_count?:number;transformed_valid_count?:number;displayed_valid_count?:number};
export function availabilityMessage(state?:Availability):string {
 switch(state?.status){
  case 'NEEDS_SYNC':return 'This indicator has no stored observations. Source synchronization is required.';
  case 'HISTORICAL_VINTAGE_UNAVAILABLE':return 'Historical Vintage Unavailable; no latest-data fallback';
  case 'NO_OBSERVATIONS_IN_RANGE':return 'Stored data exists, but no valid observations match the selected dates and alignment.';
  case 'NO_CLOSED_PERIODS':return 'No closed periods in the selected range. Extend the range or select a finer supported frequency.';
  case 'INSUFFICIENT_TRANSFORM_DATA':return 'Stored observations exist, but the transformation has insufficient valid history or a zero denominator or variance.';
  case 'SOURCE_VALUES_MISSING':return 'Source observations are stored, but their values are missing or their units do not match.';
  default:return 'No valid samples to display. Check the date range, source coverage and transformation window.';
 }
}
// Test the ECharts output, not just whether an API array contains rows. Zero is valid.
export function hasChartValues(option:Record<string,unknown>):boolean {
 const series=option.series as {data?:unknown[]}[]|undefined;
 return !!series?.some(s=>s.data?.some(point=>{
  const value=point&&typeof point==='object'&&!Array.isArray(point)?(point as {value?:unknown}).value:point;
  const scalar=Array.isArray(value)?value.at(-1):value;
  return scalar!=null&&scalar!==''&&(typeof scalar==='number'||typeof scalar==='string')&&Number.isFinite(Number(scalar));
 }));
}
