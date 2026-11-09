import en from './en';

// Arabic is the source language: the Arabic text IS the key. English comes from ./en.js.
// Switching language reloads the page, so module-level constants (status maps, option lists) are always in the
// right language without every component having to subscribe to a context.
const KEY = 'egc.lang';

function readLang() {
  try { const v = localStorage.getItem(KEY); if (v === 'en' || v === 'ar') return v; } catch { /* storage blocked */ }
  return 'ar';
}

export const LANG = readLang();
export const DIR = LANG === 'ar' ? 'rtl' : 'ltr';
export const LOCALE = LANG === 'ar' ? 'ar-EG-u-nu-latn' : 'en-GB';

if (typeof document !== 'undefined') {
  document.documentElement.lang = LANG;
  document.documentElement.dir = DIR;
}

const missing = new Set();
if (typeof window !== 'undefined') window.__missingI18n = missing; // inspected by the coverage check / e2e

export function tr(key, params) {
  let s = key;
  if (LANG === 'en') {
    s = en[key];
    if (s === undefined) { missing.add(key); s = key; }
  }
  return params ? s.replace(/\{(\w+)\}/g, (m, k) => (params[k] ?? m)) : s;
}

export function setLang(next) {
  try { localStorage.setItem(KEY, next); } catch { /* ignore */ }
  window.location.reload();
}

export const isRtl = DIR === 'rtl';
