import {Suspense} from 'react';
import {EconomicCalendar} from '@/components/economic-calendar';
export default function Page(){return <Suspense fallback={<div className="chart-placeholder">Loading calendar…</div>}><EconomicCalendar/></Suspense>;}
