"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useUI } from "../shared/components/presentation-provider";
import { searchPublic } from "../lib/search";
import type { Series } from "../lib/research";

export function PublicSearch({ series }: { series: Series[] }) {
  const { locale } = useUI();
  const zh = locale === "zh-CN";
  const router = useRouter();
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const results = useMemo(() => searchPublic(query, series, zh), [query, series, zh]);
  const label = zh ? "搜索页面和公开指标" : "Search pages and public series";
  const selected = results[Math.min(active, results.length - 1)];

  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(value => !value);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);

  useEffect(() => {
    if (!open) {
      dialog.current?.close();
      return;
    }
    dialog.current?.showModal();
    input.current?.focus();
  }, [open]);

  const selectedIndex = Math.min(active, results.length - 1);
  useEffect(() => {
    if (open) dialog.current?.querySelector(`#search-${selectedIndex}`)?.scrollIntoView?.({ block: "nearest" });
  }, [open, selectedIndex]);

  return <>
    <button type="button" className="command-trigger search-trigger" onClick={() => setOpen(true)} aria-label={label}>
      <Search size={15} aria-hidden="true" /><span>{zh ? "搜索" : "Search"}</span><kbd>Ctrl+K</kbd>
    </button>
    <dialog className="command-palette" ref={dialog} onCancel={() => setOpen(false)} aria-label={label}>
      <header className="search-header">
        <h2>{label}</h2>
        <button type="button" onClick={() => setOpen(false)}>{zh ? "关闭" : "Close"} · Esc</button>
      </header>
      <input ref={input} aria-label={zh ? "搜索关键词" : "Search query"}
        placeholder={zh ? "输入 CPI、失业率或页面名称" : "Type CPI, unemployment or a page"}
        value={query} onChange={event => { setQuery(event.target.value); setActive(0); }}
        role="combobox" aria-expanded={open} aria-controls="public-search-results"
        aria-activedescendant={selected ? "search-" + selectedIndex : undefined}
        onKeyDown={event => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            const step = event.key === "ArrowDown" ? 1 : -1;
            setActive(Math.max(0, Math.min(results.length - 1, selectedIndex + step)));
          }
          if (event.key === "Enter" && selected) {
            event.preventDefault();
            setOpen(false);
            router.push(selected.url);
          }
        }}
      />
      <div id="public-search-results" role="listbox" aria-label={zh ? "搜索结果" : "Search results"}>
        {results.map((result, i) => <Link id={"search-" + i} key={result.url} href={result.url}
          role="option" aria-selected={i === selectedIndex} onClick={() => setOpen(false)}>
          <span>{result.label}</span><small>{result.detail}</small>
        </Link>)}
        {!results.length && <p>{zh ? "没有匹配的公开页面或指标。" : "No matching public page or series."}</p>}
      </div>
    </dialog>
  </>;
}
