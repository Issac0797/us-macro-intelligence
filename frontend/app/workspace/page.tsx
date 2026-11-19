import WorkspaceDashboard from '@/components/workspace-dashboard';
import {Suspense} from 'react';
export default function Page(){return <Suspense fallback={<p>Loading workspace…</p>}><WorkspaceDashboard/></Suspense>;}
