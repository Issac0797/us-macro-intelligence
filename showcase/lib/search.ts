import type {Series} from './research';
export const publicPages=[['','Overview','总览'],['inflation','Inflation','通胀'],['labor','Labor','就业'],['yield-curve','Treasury Yield Curve','国债收益率曲线'],['workspace','Chart Workspace','图表工作区'],['analytics','Macro Analytics','宏观分析'],['business-cycle','Business Cycle · static limits','经济周期 · 静态限制'],['fed','Fed Policy','美联储政策'],['sources','Sources & licenses','来源与许可'],['about','About / Data Status','关于 / 数据状态']];
export function searchPublic(query:string,series:Series[],zh:boolean){
 const q=query.trim().toLowerCase();
 const pages=publicPages.map(([route,en,cn])=>({label:zh?cn:en,detail:route||'overview',url:`/${route}${route?'/':''}`,terms:en+' '+cn+' '+route}));
 const indicators=series.map(s=>({label:s.id+' · '+(zh?s.title_zh:s.title),detail:s.units,url:'/workspace/?series='+encodeURIComponent(s.id),terms:s.id+' '+s.title+' '+s.title_zh+' '+s.native_id}));
 return [...pages,...indicators].filter(item=>!q||item.terms.toLowerCase().includes(q)).slice(0,20);
}
