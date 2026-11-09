import { cn } from '../../utils/cn';

const TONE = {
  neutral: { v: 'text-slate-50', i: 'bg-slate-700/60 text-slate-300' },
  info: { v: 'text-blue-300', i: 'bg-blue-500/15 text-blue-300' },
  ok: { v: 'text-emerald-300', i: 'bg-emerald-500/15 text-emerald-300' },
  warn: { v: 'text-amber-300', i: 'bg-amber-500/15 text-amber-300' },
  crit: { v: 'text-red-300', i: 'bg-red-500/15 text-red-300' },
};

export default function StatTile({ label, value, tone = 'neutral', icon: Icon, hint, className }) {
  const t = TONE[tone] ?? TONE.neutral;
  return (
    <div className={cn('flex items-center gap-3 rounded-2xl border border-slate-700 bg-slate-800/80 p-4 shadow-xl', className)}>
      {Icon && <span className={cn('grid h-11 w-11 shrink-0 place-items-center rounded-xl', t.i)}><Icon className="h-5 w-5" aria-hidden /></span>}
      <div className="min-w-0">
        <p className="text-xs font-semibold leading-tight text-slate-400">{label}</p>
        <p className={cn('text-2xl font-extrabold leading-tight', t.v)} dir="ltr">{value}</p>
        {hint && <p className="truncate text-xs text-slate-500">{hint}</p>}
      </div>
    </div>
  );
}
