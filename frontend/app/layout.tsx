import type { Metadata } from 'next';
import {cookies,headers} from 'next/headers';
import {PresentationProvider} from '@/components/presentation-provider';
import {preferredLocale,validTheme} from '@/lib/presentation';
import './globals.css';
import {CommandPalette} from '@/components/command-palette';
import {DataRevalidation} from '@/components/data-revalidation';
export const metadata:Metadata={title:'US Macro Intelligence | 宏观研究终端',description:'Official US macroeconomic and monetary policy research.'};
export default async function RootLayout({children}:Readonly<{children:React.ReactNode}>){
 const [jar,requestHeaders]=await Promise.all([cookies(),headers()]);const locale=preferredLocale(jar.get('macro-locale')?.value,requestHeaders.get('accept-language')||'');const theme=validTheme(jar.get('macro-theme')?.value);
 const boot=`(()=>{let p=${JSON.stringify(theme)};try{let c=document.cookie.match(/(?:^|; )macro-theme=([^;]+)/);let s=c?decodeURIComponent(c[1]):localStorage.getItem('macro-theme');p=['light','dark','system'].includes(s)?s:p}catch{}let r=p==='system'?(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'):p;document.documentElement.dataset.theme=r;document.documentElement.classList.toggle('dark',r==='dark');document.documentElement.style.colorScheme=r})()`;
 return <html lang={locale} suppressHydrationWarning><head><script dangerouslySetInnerHTML={{__html:boot}}/></head><body><PresentationProvider initialLocale={locale} initialTheme={theme}><DataRevalidation/><CommandPalette/>{children}</PresentationProvider></body></html>;
}
