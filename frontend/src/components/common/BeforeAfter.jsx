import { useState } from 'react';
import { cn } from '../../utils/cn';
import { tr } from '../../i18n';

// Prototype comparison slider. Works in RTL: "before" is revealed from the right edge.
export default function BeforeAfter({ before, after, className }) {
  const [v, setV] = useState(50);
  return (
    <div className={className}>
      <div className="relative aspect-video select-none overflow-hidden rounded-xl border border-slate-600" dir="ltr">
        <img src={after} alt={tr("بعد الإصلاح")} className="absolute inset-0 h-full w-full object-cover" />
        <div className="absolute inset-0" style={{ clipPath: `inset(0 ${100 - v}% 0 0)` }}>
          <img src={before} alt={tr("قبل الإصلاح")} className="h-full w-full object-cover" />
        </div>
        <div className="absolute inset-y-0 w-0.5 bg-white shadow" style={{ left: `${v}%` }} />
        <span className="absolute left-3 top-3 rounded bg-slate-950/80 px-2 py-1 text-xs font-bold">{tr("قبل")}</span>
        <span className="absolute right-3 top-3 rounded bg-emerald-600/90 px-2 py-1 text-xs font-bold">{tr("بعد")}</span>
      </div>
      <input type="range" min="0" max="100" value={v} onChange={(e) => setV(+e.target.value)} aria-label={tr("مقارنة قبل وبعد")} className={cn('mt-4 w-full')} />
    </div>
  );
}
