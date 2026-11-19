"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import {
  LayoutDashboard, CalendarDays, ChartNoAxesCombined, Database, History,
  TrendingUp, Users, Landmark, FileText, GitCompareArrows, Info,
} from "lucide-react";
import { useUI } from "./presentation-provider";

const groups = [
  { label: "Overview", links: [
    ["/", "Overview", LayoutDashboard], ["/calendar", "Economic Calendar", CalendarDays],
  ] },
  { label: "Research", links: [
    ["/workspace", "Chart Workspace", ChartNoAxesCombined], ["/analytics", "Macro Analytics", ChartNoAxesCombined],
    ["/business-cycle", "Business Cycle", TrendingUp], ["/historical-snapshot", "Historical Snapshot", History],
    ["/revisions", "Revision Analysis", GitCompareArrows],
  ] },
  { label: "Indicators", links: [
    ["/inflation", "Inflation", TrendingUp], ["/labor", "Labor Market", Users], ["/growth", "Growth", ChartNoAxesCombined],
    ["/monetary", "Monetary Policy", Landmark], ["/yield-curve", "Treasury Yield Curve", ChartNoAxesCombined],
  ] },
  { label: "Fed Policy", links: [
    ["/fed", "Fed Policy", Landmark], ["/fed/statements", "FOMC Statements", FileText],
    ["/fed/projections", "SEP & Dot Plot", ChartNoAxesCombined], ["/fed/rates", "Policy Rates", TrendingUp],
    ["/fed/historical", "Historical Policy", History],
  ] },
] as const;

const dataGroup = { label: "Data", links: [
  ["/sources", "Sources & licenses", Database],
  ["/about", "About / Data Status", Info],
] } as const;

export function MainNavigation({ availableRoutes }: { availableRoutes?: readonly string[] }) {
  const { t, locale } = useUI();
  const path = usePathname().replace(/\/$/, "") || "/";
  const nav = useRef<HTMLElement>(null);
  useEffect(() => {
    nav.current?.querySelector<HTMLElement>('[aria-current="page"]')?.scrollIntoView?.({ block: "nearest" });
  }, [path]);
  const display = (label: string) => locale === "zh-CN"
    ? ({ "Data": "数据", "Sources & licenses": "来源与许可", "About / Data Status": "关于 / 数据状态" }[label] ?? t(label))
    : t(label);

  return <nav ref={nav} aria-label={t("Main navigation")}>
    {(availableRoutes ? [...groups, dataGroup] : groups).map(group => {
      const links = group.links.filter(([href]) => !availableRoutes || availableRoutes.includes(href));
      if (!links.length) return null;
      return <div className="nav-group" key={group.label}>
        <div className="nav-group-label">{display(group.label)}</div>
        {links.map(([href, label, Icon]) => {
          const active = path === href || (href === "/fed" && path.startsWith("/fed/meetings/"));
          return <Link key={href} href={href} className={"nav-item" + (active ? " active" : "")}
            title={display(label)} aria-label={display(label)} aria-current={active ? "page" : undefined}>
            <Icon size={18} aria-hidden="true" /><span>{display(label)}</span>
          </Link>;
        })}
      </div>;
    })}
  </nav>;
}
