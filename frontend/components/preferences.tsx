"use client";
import {Sun,Moon,Monitor,Languages} from 'lucide-react';
import {useUI} from './presentation-provider';
import type {Theme,Locale} from '@/lib/presentation';
export function Preferences(){const {theme,locale,setTheme,setLocale,t}=useUI();const Icon=theme==='light'?Sun:theme==='dark'?Moon:Monitor;return <div className="presentation-settings" role="group" aria-label={t('Display preferences')}><label><Icon size={15}/><span className="sr-only">{t('Theme')}</span><select aria-label={t('Theme')} value={theme} onChange={e=>setTheme(e.target.value as Theme)}><option value="system">{t('System')}</option><option value="light">{t('Light')}</option><option value="dark">{t('Dark')}</option></select></label><label><Languages size={15}/><span className="sr-only">{t('Language')}</span><select aria-label={t('Language')} value={locale} onChange={e=>setLocale(e.target.value as Locale)}><option value="zh-CN">中文</option><option value="en-US">English</option></select></label></div>}
