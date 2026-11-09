import { Link, Navigate } from 'react-router-dom';
import { ArrowLeft, Eye, MapPin, ShieldCheck, Sparkles } from 'lucide-react';
import { useAuth, homePathFor } from '../context/AuthContext';
import { ThemeToggle, LangToggle } from '../components/common/PrefsToggles';
import BeforeAfter from '../components/common/BeforeAfter';
import { REPAIRS } from '../content/landing';
import { tr } from '../i18n';

const FEATURES = [
  { icon: MapPin, title: tr("بلاغ بموقع دقيق"), text: tr("حدّد المشكلة على الخريطة بدقة تحديد المواقع (GPS)، وأرفق صورة أو ملاحظة صوتية.") },
  { icon: Sparkles, title: tr("تحليل آلي، وقرار بشري"), text: tr("النظام يقترح التصنيف والأولوية لمساعدة المشرف، والقرار النهائي دائمًا لإنسان.") },
  { icon: Eye, title: tr("متابعة شفافة"), text: tr("تشوف بلاغك في كل مرحلة، من الاستلام حتى التحقق من الإصلاح.") },
];

const STEPS = [
  { title: tr("قدّم البلاغ"), text: tr("بالموقع والوصف والصورة.") },
  { title: tr("مراجعة وتحليل"), text: tr("المشرف يراجع التحليل الآلي.") },
  { title: tr("اعتماد وإسناد"), text: tr("يُسند البلاغ إلى فريق صيانة.") },
  { title: tr("تنفيذ وتحقق"), text: tr("الفريق ينفّذ ويرفع الإثبات، ثم يتحقق المشرف.") },
];

const btn = 'inline-flex items-center justify-center gap-2 rounded-lg px-5 py-3 text-sm font-bold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400';
const wrap = 'mx-auto max-w-6xl px-4';

function Brand({ className = '' }) {
  return (
    <Link to="/" className={`flex items-center gap-3 ${className}`}>
      <span className="grid h-10 w-10 place-items-center rounded-lg bg-blue-700 ring-2 ring-blue-400/40"><ShieldCheck className="h-5 w-5 text-white" aria-hidden /></span>
      <span className="text-lg font-extrabold text-slate-50">EG Civic Operations</span>
    </Link>
  );
}

// Single photograph, or a same-place before/after pair. Credit is shown only when provided.
function GalleryItem({ item }) {
  const c = item.credit;
  return (
    <figure className="group relative overflow-hidden rounded-xl border border-slate-700 bg-slate-800">
      {item.photo
        ? <img src={item.photo} alt={tr(item.title)} loading="lazy" className="aspect-[4/3] w-full object-cover" />
        : <div className="p-3"><BeforeAfter before={item.before} after={item.after} /></div>}
      <figcaption className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent px-4 pb-3 pt-10 text-white">
        <span className="block text-sm font-bold">{tr(item.title)}</span>
        {c && <span className="pointer-events-auto block text-xs text-white/75">{tr("تصوير")}: <a href={c.url} target="_blank" rel="noreferrer" className="underline">{c.author}</a> · {c.license}</span>}
      </figcaption>
      {item.illustrative && <span className="absolute start-3 top-3 rounded bg-black/70 px-2 py-1 text-xs font-bold text-white">{tr("رسم توضيحي")}</span>}
    </figure>
  );
}

export default function LandingPage() {
  const { user, booting } = useAuth();
  if (booting) return null;
  if (user) return <Navigate to={homePathFor(user.role)} replace />;
  const hero = REPAIRS[0];

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      {/* thin flag-coloured rule */}
      <div className="flex h-1" aria-hidden><span className="flex-1 bg-[#CE1126]" /><span className="flex-1 bg-white" /><span className="flex-1 bg-black" /></div>

      <header className="sticky top-0 z-30 border-b border-slate-800 bg-slate-900/90 backdrop-blur">
        <div className={`${wrap} flex items-center justify-between gap-3 py-3`}>
          <Brand className="[&>span:last-child]:hidden sm:[&>span:last-child]:block" />
          <nav className="hidden items-center gap-6 text-sm font-semibold text-slate-300 lg:flex" aria-label={tr("أقسام الصفحة")}>
            <a href="#about" className="hover:text-slate-50">{tr("عن المنصة")}</a>
            <a href="#how" className="hover:text-slate-50">{tr("كيف يعمل البلاغ؟")}</a>
            <a href="#field" className="hover:text-slate-50">{tr("من الميدان")}</a>
          </nav>
          <div className="flex items-center gap-2">
            <LangToggle /><ThemeToggle />
            <Link to="/login" className={`${btn} border border-slate-600 text-slate-100 hover:bg-slate-800`}>{tr("تسجيل الدخول")}</Link>
            <Link to="/register" className={`${btn} hidden bg-blue-600 text-white hover:bg-blue-500 sm:inline-flex`}>{tr("إنشاء حساب")}</Link>
          </div>
        </div>
      </header>

      <main>
        {/* Hero: full-bleed photograph, text on a fixed dark scrim so it reads in both themes */}
        <section className="relative isolate overflow-hidden bg-[#0b1220] text-white">
          <img src={hero.photo} alt="" className="absolute inset-0 -z-20 h-full w-full object-cover object-[50%_58%]" />
          <div className="absolute inset-0 -z-10 bg-[#0b1220]/70 lg:bg-gradient-to-l lg:from-[#0b1220]/90 lg:via-[#0b1220]/50 lg:to-transparent ltr:lg:bg-gradient-to-r" aria-hidden />
          <div className={`${wrap} flex min-h-[460px] items-center py-16 lg:min-h-[560px]`}>
            <div className="max-w-2xl">
              <h1 className="text-4xl font-extrabold leading-tight sm:text-5xl sm:leading-tight">{tr("بلّغ عن المشكلة، وتابع إصلاحها خطوة بخطوة.")}</h1>
              <p className="mt-5 max-w-xl text-lg leading-relaxed text-white/85">{tr("منصة حكومية تستقبل بلاغات الخدمات المدنية، وتحلّلها آليًا لمساعدة المشرف، وتنقلها إلى فريق الصيانة حتى يتم التحقق من الإصلاح.")}</p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link to="/register" className={`${btn} bg-blue-600 text-white hover:bg-blue-500`}>{tr("إنشاء حساب مواطن")}</Link>
                <Link to="/login" className={`${btn} border border-white/40 text-white hover:bg-white/10`}>{tr("تسجيل الدخول")}</Link>
              </div>
            </div>
          </div>
        </section>

        <section id="about" className={`${wrap} scroll-mt-20 py-16`}>
          <div className="grid gap-10 lg:grid-cols-[1fr_1.4fr]">
            <div>
              <h2 className="text-3xl font-extrabold text-slate-50">{tr("ما هي المنصة؟")}</h2>
              <p className="mt-4 leading-relaxed text-slate-300">{tr("بوابة واحدة تربط المواطن بجهات الخدمات المدنية وفرق الصيانة الميدانية، بدون أوراق ولا تنقّل بين الإدارات.")}</p>
            </div>
            <ul className="divide-y divide-slate-700 border-y border-slate-700">
              {FEATURES.map(({ icon: I, title, text }) => (
                <li key={title} className="flex items-start gap-4 py-5">
                  <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-blue-500/15 text-blue-300"><I className="h-5 w-5" aria-hidden /></span>
                  <div><h3 className="font-bold text-slate-50">{title}</h3><p className="mt-1 text-sm leading-relaxed text-slate-300">{text}</p></div>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="how" className="scroll-mt-20 border-y border-slate-800 bg-slate-950/40">
          <div className={`${wrap} py-16`}>
            <h2 className="text-3xl font-extrabold text-slate-50">{tr("كيف يعمل البلاغ؟")}</h2>
            <ol className="mt-10 grid gap-8 md:grid-cols-4 md:gap-6">
              {STEPS.map((s, i) => (
                <li key={s.title} className="relative md:pt-0">
                  <div className="flex items-center gap-3">
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-blue-600 text-base font-extrabold text-white">{i + 1}</span>
                    {i < STEPS.length - 1 && <span className="hidden h-px flex-1 bg-slate-700 md:block" aria-hidden />}
                  </div>
                  <h3 className="mt-4 font-bold text-slate-50">{s.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-slate-300">{s.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="field" className={`${wrap} scroll-mt-20 py-16`}>
          <h2 className="text-3xl font-extrabold text-slate-50">{tr("من الميدان")}</h2>
          <p className="mt-2 text-slate-300">{tr("صور من أعمال الرصف والصيانة في شوارع مصر.")}{REPAIRS.some((r) => r.illustrative) && <span className="text-slate-400"> {tr("بعض الصور رسومات توضيحية وليست حالات حقيقية.")}</span>}</p>
          <div className="mt-8 grid gap-5 md:grid-cols-3">
            {REPAIRS.slice(1).map((r) => <GalleryItem key={r.id} item={r} />)}
          </div>
        </section>

        <section className={`${wrap} pb-16`}>
          <div className="flex flex-col items-start justify-between gap-6 rounded-xl border border-slate-700 bg-slate-800/80 p-8 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-2xl font-extrabold text-slate-50">{tr("عندك مشكلة في الشارع؟")}</h2>
              <p className="mt-1 text-slate-300">{tr("سجّل حسابك وقدّم أول بلاغ في دقائق.")}</p>
            </div>
            <Link to="/register" className={`${btn} shrink-0 bg-blue-600 text-white hover:bg-blue-500`}>{tr("إنشاء حساب مواطن")}<ArrowLeft className="h-4 w-4 ltr:rotate-180" aria-hidden /></Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-800 bg-slate-950/40">
        <div className={`${wrap} flex flex-col gap-6 py-8 sm:flex-row sm:items-center sm:justify-between`}>
          <div>
            <Brand />
            <p className="mt-3 max-w-md text-sm text-slate-400">{tr("منصة حكومية ذكية لإدارة الشكاوى والمرافق الميدانية")}</p>
          </div>
          <div className="flex items-center gap-5 text-sm font-semibold text-slate-300">
            <Link to="/login" className="hover:text-slate-50">{tr("تسجيل الدخول")}</Link>
            <Link to="/register" className="hover:text-slate-50">{tr("إنشاء حساب")}</Link>
          </div>
        </div>
        <p className="border-t border-slate-800 py-4 text-center text-xs text-slate-500">© {new Date().getFullYear()} EG Civic Operations</p>
      </footer>
    </div>
  );
}
