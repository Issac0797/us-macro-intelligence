export type Indicator = {series_id:string;title:string;units:string;previous:number|null;actual:number|null;observation_date:string|null;captured_at:string|null};
export type Release = {revision_count:number;id:string;release_name:string;provider:string;category:string;importance:string;scheduled_date:string;scheduled_at:string|null;actual_released_at:string|null;detected_at:string|null;reference_period:string|null;status:string;source_name:string;source_url:string;last_verified_at:string;indicators:Indicator[]};
export type ProviderState={provider:string;status:string;event_count:number;last_success_at:string|null;last_error:string|null;source_url:string};
export type Revision={id:number;series_id:string;observation_date:string;old_value:number|null;new_value:number|null;delta:number|null;detected_at:string;scope:string};
export type ReleaseDetail=Release & {reference_observation_date:string|null;vintage_availability:Record<string,boolean>;monitor:{status:string;attempts:number;last_error:string|null}|null;schedule_changes:{id:number;detected_at:string;old_snapshot:string;new_snapshot:string}[];revisions:Revision[]};
import {researchRequest} from './query-client';
export const calendarFetch=<T,>(path:string,signal?:AbortSignal)=>researchRequest<T>(path,'GET',undefined,signal);
export function releaseTime(value:string|null,tz:string){return value?new Intl.DateTimeFormat('en-GB',{dateStyle:'medium',timeStyle:'short',timeZone:tz}).format(new Date(value)):'Time unknown';}
