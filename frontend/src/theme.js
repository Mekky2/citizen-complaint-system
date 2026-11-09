const KEY = 'egc.theme';
export function getTheme() {
  try { const v = localStorage.getItem(KEY); if (v === 'light' || v === 'dark') return v; } catch { /* storage blocked */ }
  return 'dark';
}
export function applyTheme(t) { document.documentElement.dataset.theme = t; }
export function setTheme(t) {
  try { localStorage.setItem(KEY, t); } catch { /* ignore */ }
  applyTheme(t);
}
applyTheme(getTheme());
