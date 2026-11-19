import {FedTerminal} from '@/components/fed-terminal';
export default async function Page({params}:{params:Promise<{id:string}>}){const {id}=await params;return <FedTerminal view="meeting" meetingId={id}/>;}
