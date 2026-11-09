import { useState } from 'react';
import { Moon, Sun, Languages } from 'lucide-react';
import { getTheme, setTheme } from '../../theme';
import { LANG, setLang, tr } from '../../i18n';

const btn = 'inline-flex h-10 items-center justify-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-2.5 text-sm font-bold text-slate-300 transition hover:bg-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400';

export function ThemeToggle() {
  const [theme, set] = useState(getTheme());
  const next = theme === 'dark' ? 'light' : 'dark';
  return (
    <button type="button" className={btn} aria-label={theme === 'dark' ? tr('الوضع الفاتح') : tr('الوضع الداكن')} title={theme === 'dark' ? tr('الوضع الفاتح') : tr('الوضع الداكن')}
      onClick={() => { setTheme(next); set(next); }}>
      {theme === 'dark' ? <Sun className="h-5 w-5" aria-hidden /> : <Moon className="h-5 w-5" aria-hidden />}
    </button>
  );
}

export function LangToggle() {
  const next = LANG === 'ar' ? 'en' : 'ar';
  return (
    <button type="button" className={btn} aria-label={LANG === 'ar' ? 'Switch to English' : tr("التبديل إلى العربية")} title={LANG === 'ar' ? 'English' : tr("العربية")} onClick={() => setLang(next)}>
      <Languages className="h-5 w-5" aria-hidden /><span className="hidden sm:inline">{LANG === 'ar' ? 'EN' : tr("ع")}</span>
    </button>
  );
}
