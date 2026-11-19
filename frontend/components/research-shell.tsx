"use client";
import {MainNavigation} from "./main-navigation";
import {Preferences} from "./preferences";
import {useUI} from "./presentation-provider";
import Link from 'next/link';
import { Activity, ChartNoAxesCombined } from 'lucide-react';
export function ResearchShell({ title, description, children, advanced = false }: {
    title: string;
    description: string;
    children: React.ReactNode;
    advanced?: boolean;
}) {
    const { t, tx, locale, date: uiDate, number: uiNumber } = useUI();
    return <div className={'terminal ' + (advanced ? 'advanced-terminal rail-collapsed' : '')}><aside className="sidebar"><Link href="/" className="brand" title={t("Macro Intelligence")}><span className="brand-symbol"><Activity size={22}/></span><span className="brand-text">{t("MACRO")}<span>{t("INTELLIGENCE")}</span></span></Link><div className="workspace-label">{tx(advanced ? 'RESEARCH WORKSPACE · 04' : 'VINTAGE RESEARCH · 03')}</div><MainNavigation/></aside><div className="workspace"><header className="topbar"><Preferences/><span className="breadcrumb">{t("Research workspace /") + " "}{tx(advanced ? 'Macro & Rates' : 'ALFRED')}</span><span className="region">{tx(advanced ? 'REAL DATA · EXPLICIT METHODS' : 'DATE-LEVEL POINT-IN-TIME DATA')}</span></header><main><div className="eyebrow">{tx(advanced ? 'MACRO INTELLIGENCE · RESEARCH TOOLS' : 'ALFRED · ARCHIVED ECONOMIC DATA')}</div><h1>{tx(title)}</h1><p className="vintage-description">{tx(description)}</p>{tx(children)}</main></div></div>;
}
