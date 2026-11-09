import { Link } from 'react-router-dom';
import { ArrowLeft, ShieldCheck } from 'lucide-react';
import { ThemeToggle, LangToggle } from '../../components/common/PrefsToggles';
import { tr } from '../../i18n';

// Auth screens: just the form. All marketing copy lives on the landing page ("/").
export default function AuthFrame({ title, subtitle, children, footer }) {
  return (
    <div className="relative flex min-h-screen items-center justify-center bg-slate-900 p-4 sm:p-8">
      <div className="pointer-events-none absolute -start-24 -top-24 h-80 w-80 rounded-full bg-blue-600/10 blur-3xl" aria-hidden />
      <div className="absolute end-4 top-4 flex gap-2"><LangToggle /><ThemeToggle /></div>
      <Link to="/" className="absolute start-4 top-4 inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-300 hover:bg-slate-800" aria-label={tr("العودة إلى الصفحة الرئيسية")}>
        <ArrowLeft className="h-4 w-4 rotate-180 ltr:rotate-0" aria-hidden />
        <span className="hidden sm:inline">{tr("الرئيسية")}</span>
      </Link>
      <div className="relative w-full max-w-md">
        <div className="mb-5 flex justify-center">
          <span className="grid h-12 w-12 place-items-center rounded-xl bg-blue-700 ring-2 ring-blue-400/40"><ShieldCheck className="h-7 w-7 text-white" aria-hidden /></span>
        </div>
        <div className="rounded-2xl border border-slate-700 bg-slate-800/80 p-6 shadow-xl">
          <h1 className="text-2xl font-extrabold text-slate-50">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-slate-400">{subtitle}</p>}
          <div className="mt-5">{children}</div>
        </div>
        {footer && <p className="mt-4 text-center text-sm text-slate-300">{footer}</p>}
      </div>
    </div>
  );
}
