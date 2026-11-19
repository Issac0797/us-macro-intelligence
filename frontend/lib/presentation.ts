import en from '../messages/en-US.json';
import zh from '../messages/zh-CN.json';
export type Locale='zh-CN'|'en-US';
export type Theme='light'|'dark'|'system';
export const validTheme=(v:unknown):Theme=>v==='light'||v==='dark'||v==='system'?v:'system';
export const validLocale=(v:unknown):Locale|null=>v==='zh-CN'||v==='en-US'?v:null;
export function preferredLocale(cookie:unknown,languages:string):Locale{const saved=validLocale(cookie);if(saved)return saved;for(const raw of languages.split(',')){const l=raw.trim().split(';')[0].toLowerCase();if(l.startsWith('zh'))return 'zh-CN';if(l.startsWith('en'))return 'en-US';}return 'zh-CN';}
const english=en as Record<string,string>,chinese=zh as Record<string,string>;
const folded=new Map(Object.keys(english).map(key=>[key.toLowerCase(),key]));
const patterns=Object.keys(english).filter(k=>/\{p\d+\}/.test(k)).map(key=>{const names:string[]=[];const segments=key.split(/(\{p\d+\})/);const source=segments.map(v=>{if(/^\{p\d+\}$/.test(v)){names.push(v.slice(1,-1));return '([\\s\\S]*?)';}return v.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}).join('');return {key,names,literals:segments.filter(v=>!/^\{p\d+\}$/.test(v)&&v.trim().length>0),pattern:new RegExp('^'+source+'$')};});
export function translate(key:string,locale:Locale,params:Record<string,string|number>={}):string{
 if(/^\d{4}-\d{2}-\d{2}$/.test(key))return formatDate(key,locale);
 if(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$/.test(key))return formatDate(/[Z+-]\d{2}:\d{2}$|Z$/.test(key)?key:key+'Z',locale,'UTC',true)+' UTC';
 const dict=locale==='zh-CN'?chinese:english;const canonical=folded.get(key.toLowerCase());if(canonical&&!(key in english))return dict[canonical]??key;
 if(!(key in english)){
  if(locale==='en-US'||key.startsWith('{')||key.startsWith('[')||key.length>4096)return key;
  for(const candidate of patterns){if(!candidate.literals.every(part=>key.includes(part)))continue;const match=candidate.pattern.exec(key);if(match){return translate(candidate.key,locale,Object.fromEntries(candidate.names.map((n,i)=>[n,match[i+1]])));}}
 }
 const message=dict[key]??english[key]??key;
 return message.replace(/\{([\w]+)\}/g,(m,k)=>{if(params[k]===undefined)return m;const value=String(params[k]);if(/^\d{4}-\d{2}-\d{2}$/.test(value))return formatDate(value,locale);const known=folded.get(value.toLowerCase());return known?(dict[known]??value):value;});
}
export function formatNumber(v:number|null|undefined,locale:Locale,digits=3){return v==null?translate('Not Available',locale):new Intl.NumberFormat(locale,{maximumFractionDigits:digits}).format(v);}
export function formatDate(value:string|Date|null|undefined,locale:Locale,timeZone='America/New_York',withTime=false):string{if(!value)return translate('Time unknown',locale);const dayOnly=typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value);const d=value instanceof Date?value:new Date(dayOnly?value+'T12:00:00Z':value);if(!Number.isFinite(d.getTime()))return String(value);return new Intl.DateTimeFormat(locale,{year:'numeric',month:'long',day:'numeric',...(withTime?{hour:'2-digit',minute:'2-digit'}:{}),timeZone:dayOnly?'UTC':timeZone}).format(d);}
export const chartPalette={light:{background:'#ffffff',foreground:'#182c44',muted:'#52677e',border:'#c2cfdd',grid:'#dce4ed',primary:'#1764c0',positive:'#11715a',negative:'#a72d40',warning:'#875600',surface:'#eef3f8',colors:['#1764c0','#087f83','#7548b2','#b43a58','#976200','#537522']},dark:{background:'#121e30',foreground:'#e2eaf5',muted:'#b1c0d3',border:'#41536b',grid:'#34455b',primary:'#67a9ff',positive:'#73cbb3',negative:'#f198a4',warning:'#efc47f',surface:'#1d2e45',colors:['#67a9ff','#73cbb3','#bc9aef','#f198a4','#efc47f','#b4d18a']}} as const;
