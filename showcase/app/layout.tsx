import type {Metadata} from 'next';
import type {ReactNode} from 'react';
import {DisplayProvider} from '../components/showcase';
import './style.css';
export const metadata:Metadata={title:'US Macro Intelligence — Static Showcase',description:'Source-linked US macroeconomic research using reviewed public-domain snapshots. Not live data.'};
export default function RootLayout({children}:{children:ReactNode}){
 const boot=`(()=>{try{const p=localStorage.getItem('macro-theme')||'system';const r=p==='system'?(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'):p;document.documentElement.dataset.theme=r;document.documentElement.style.colorScheme=r}catch{}})()`;
 return <html lang="en-US" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{__html:boot}}/></head><body><DisplayProvider>{children}</DisplayProvider></body></html>;
}
