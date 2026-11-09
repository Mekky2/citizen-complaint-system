import { useEffect, useState } from 'react';
import { NavLink, Outlet, Link } from 'react-router-dom';
import { Bell, LogOut, Menu, ShieldCheck, X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { ROLE_LABEL } from '../../utils/status';
import { listNotifications } from '../../api/notifications';
import { cn } from '../../utils/cn';
import { ThemeToggle, LangToggle } from '../common/PrefsToggles';
import { tr } from '../../i18n';

// One shell for every role, ported from the prototype: sticky blurred header with logo box, pill-segmented nav
// (desktop), bottom tab bar (mobile) and a footer. Only the nav items, subtitle and width differ per role.
// nav: [{ to, label, icon, end?, badge?: 'notifications' }]
function useUnreadCount() {
  const [n, setN] = useState(0);
  useEffect(() => {
    let alive = true;
    const load = () => listNotifications({ unread_only: true, limit: 100 }).then((r) => alive && setN(r.length)).catch(() => {});
    load();
    const t = setInterval(load, 60000);
    const onRead = () => load();
    window.addEventListener('notifications:changed', onRead);
    return () => { alive = false; clearInterval(t); window.removeEventListener('notifications:changed', onRead); };
  }, []);
  return n;
}

export default function AppShell({ nav, title, wide = false }) {
  const { user, logout } = useAuth();
  const unread = useUnreadCount();
  const [drawer, setDrawer] = useState(false);
  const bell = nav.find((n) => n.badge === 'notifications');
  const main = nav.filter((n) => n.badge !== 'notifications');
  const bottomBar = nav.length <= 5;
  const width = wide ? 'max-w-7xl' : 'max-w-6xl';

  const pill = ({ isActive }) =>
    cn('flex items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-bold transition xl:px-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400',
      isActive ? 'bg-blue-600 text-white shadow' : 'text-slate-300 hover:bg-slate-700');

  return (
    <div className={cn('flex min-h-screen flex-col', bottomBar && 'pb-20 lg:pb-0')}>
      <header className="sticky top-0 z-30 border-b border-slate-700 bg-slate-950/90 backdrop-blur">
        <div className={cn('mx-auto flex items-center justify-between gap-3 px-4 py-3', width)}>
          <div className="flex min-w-0 items-center gap-3">
            {!bottomBar && (
              <button className="rounded-lg p-2 text-slate-300 hover:bg-slate-800 lg:hidden" onClick={() => setDrawer(true)} aria-label={tr("القائمة")}><Menu className="h-5 w-5" /></button>
            )}
            <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-blue-700 ring-2 ring-blue-400/40"><ShieldCheck className="h-6 w-6 text-white" aria-hidden /></div>
            <div className={cn('hidden min-w-0 sm:block', !bottomBar && 'lg:hidden 2xl:block')}>
              <p className="truncate text-lg font-extrabold leading-tight text-slate-50 sm:text-xl">EG Civic Operations</p>
              <p className="truncate text-xs text-slate-400">{title}</p>
            </div>
          </div>

          <nav className="hidden rounded-xl border border-slate-700 bg-slate-800 p-1 lg:flex" aria-label={tr("التنقل الرئيسي")}>
            {main.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end} className={pill}><Icon className="h-4 w-4" aria-hidden />{label}</NavLink>
            ))}
          </nav>

          <div className="flex shrink-0 items-center gap-1.5">
            <LangToggle />
            <ThemeToggle />
            {bell && (
              <Link to={bell.to} aria-label={unread ? tr("الإشعارات ({p0} غير مقروء)", { p0: unread }) : tr("الإشعارات")} className="relative rounded-xl border border-slate-700 bg-slate-800 p-2.5 text-slate-300 hover:bg-slate-700">
                <Bell className="h-5 w-5" aria-hidden />
                {unread > 0 && <span className="absolute -end-1 -top-1 min-w-5 rounded-full bg-red-600 px-1 text-center text-[11px] font-bold text-white">{unread > 99 ? '99+' : unread}</span>}
              </Link>
            )}
            <span className="hidden px-2 text-end leading-tight xl:block">
              <span className="block max-w-[10rem] truncate text-sm font-bold text-slate-100">{user?.name}</span>
              <span className="block text-xs text-slate-400">{ROLE_LABEL[user?.role]}</span>
            </span>
            <button onClick={logout} aria-label={tr("تسجيل الخروج")} className="rounded-xl border border-slate-700 bg-slate-800 p-2.5 text-slate-300 hover:bg-red-600/80 hover:text-white"><LogOut className="h-5 w-5" /></button>
          </div>
        </div>
      </header>

      <main className={cn('mx-auto w-full flex-1 px-4 py-6 sm:py-8', width)}><Outlet /></main>

      <footer className="border-t border-slate-800 py-6 text-center text-sm text-slate-500">
        © {new Date().getFullYear()} {tr("EG Civic Operations — منصة حكومية ذكية لإدارة الشكاوى والمرافق الميدانية")}
      </footer>

      {bottomBar && (
        <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-slate-700 bg-slate-950/95 backdrop-blur lg:hidden" aria-label={tr("التنقل")}>
          {nav.map(({ to, label, icon: Icon, end, badge }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => cn('relative flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[11px] font-bold', isActive ? 'text-blue-300' : 'text-slate-400')}>
              {({ isActive }) => (
                <>
                  <span className={cn('grid h-7 w-12 place-items-center rounded-full transition', isActive && 'bg-blue-500/20')}><Icon className="h-5 w-5" aria-hidden /></span>
                  {label}
                  {badge === 'notifications' && unread > 0 && <span className="absolute end-1/4 top-1.5 h-2.5 w-2.5 rounded-full bg-red-500 ring-2 ring-slate-950" />}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      )}

      {!bottomBar && drawer && (
        <div className="fixed inset-0 z-40 lg:hidden" onClick={() => setDrawer(false)}>
          <div className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm" />
          <aside className="absolute inset-y-0 end-0 w-72 border-s border-slate-700 bg-slate-900 p-3 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <button className="mb-2 rounded-lg p-2 text-slate-300 hover:bg-slate-800" onClick={() => setDrawer(false)} aria-label={tr("إغلاق")}><X className="h-5 w-5" /></button>
            <nav className="space-y-1" aria-label={tr("القائمة الرئيسية")}>
              {nav.map(({ to, label, icon: Icon, end }) => (
                <NavLink key={to} to={to} end={end} onClick={() => setDrawer(false)} className={pill}><Icon className="h-5 w-5" aria-hidden />{label}</NavLink>
              ))}
            </nav>
          </aside>
        </div>
      )}
    </div>
  );
}
