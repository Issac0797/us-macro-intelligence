"use client";

import Link from "next/link";
import { Activity, ChevronRight, Globe2, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import type { ReactNode } from "react";
import { MainNavigation } from "./main-navigation";
import { Preferences } from "./preferences";
import { useUI } from "./presentation-provider";

export function TerminalFrame({
  children, label, collapsed, onToggle, availableRoutes, sidebarFooter, onNavigate,
  edition, status, ready, tools, statusFooter, className = "",
}: {
  children: ReactNode;
  label: string;
  collapsed: boolean;
  onToggle: () => void;
  onNavigate?: () => void;
  availableRoutes?: readonly string[];
  sidebarFooter: ReactNode;
  edition?: string;
  status: string;
  ready?: boolean;
  tools?: ReactNode;
  statusFooter: ReactNode;
  className?: string;
}) {
  const { t } = useUI();
  const ToggleIcon = collapsed ? PanelLeftOpen : PanelLeftClose;
  return (
    <div className={["terminal", collapsed && "rail-collapsed", className].filter(Boolean).join(" ")}>
      <a className="skip-link" href="#main">{t("Skip to research")}</a>
      <aside id="terminal-sidebar" className="sidebar" onClick={onNavigate ? event => {
        if (event.target instanceof Element && event.target.closest("a")) onNavigate();
      } : undefined}>
        <Link href="/" className="brand" aria-label={t("Macro Intelligence")}>
          <span className="brand-symbol"><Activity size={22} aria-hidden="true" /></span>
          <span className="brand-text">{t("MACRO")}<span>{t("INTELLIGENCE")}</span></span>
        </Link>
        <div className="workspace-label">
          <span className="status-dot" />{edition ?? t("U.S. RESEARCH TERMINAL")}
          {!edition && <span className="version">01</span>}
        </div>
        <div className="nav-caption">{t("WORKSPACE")}</div>
        <MainNavigation availableRoutes={availableRoutes} />
        <div className="sidebar-bottom">{sidebarFooter}</div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <Preferences />
          <div className="breadcrumb">
            <button type="button" className="inline-flex size-9 shrink-0 items-center justify-center rounded-md hover:bg-accent"
              onClick={onToggle} aria-label={t("Toggle navigation")}
              aria-controls="terminal-sidebar" aria-expanded={!collapsed}>
              <ToggleIcon size={17} aria-hidden="true" />
            </button>
            <span>{t("Research workspace")}</span><ChevronRight size={13} aria-hidden="true" />
            <strong>{label}</strong>
          </div>
          <div className="topbar-right">
            {tools}
            <span className="region"><Globe2 size={14} aria-hidden="true" />{t("UNITED STATES")}</span>
            <span className={"connection" + (ready ? " connected" : "")}><span className="status-dot" />{status}</span>
          </div>
        </header>
        <main id="main">{children}</main>
        <div className="statusbar">{statusFooter}</div>
      </div>
    </div>
  );
}
