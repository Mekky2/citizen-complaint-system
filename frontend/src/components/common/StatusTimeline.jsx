import { Check, XCircle } from 'lucide-react';
import { cn } from '../../utils/cn';
import { TICKET_FLOW, TICKET_STATUS, STEP_COLOR, STEP_HINT } from '../../utils/status';
import { tr } from '../../i18n';

// Vertical coloured timeline from the prototype (default) or a compact horizontal strip (`compact`).
// `current` is a TicketStatus. rejected / cancelled replace the remaining steps with one terminal step.
export default function StatusTimeline({ current, steps = TICKET_FLOW, labels = TICKET_STATUS, compact = false, hints = true }) {
  const terminal = current === 'rejected' || current === 'cancelled';
  const idx = steps.indexOf(current);
  const list = terminal ? [...steps.slice(0, Math.max(idx, 1)), current] : steps;
  const cur = terminal ? list.length - 1 : idx;

  if (compact) {
    return (
      <ol className="flex items-center gap-1" aria-label={tr("مراحل البلاغ")}>
        {list.map((s, i) => (
          <li key={s} className="flex-1" aria-current={i === cur ? 'step' : undefined} title={labels[s]?.label}>
            <span className="block h-1.5 rounded-full" style={{ background: i <= cur ? STEP_COLOR[s] : 'rgb(var(--s-700))' }} />
          </li>
        ))}
      </ol>
    );
  }

  return (
    <ol className="relative" aria-label={tr("مراحل البلاغ")}>
      {list.map((s, i) => {
        const done = i <= cur;
        const active = i === cur;
        const color = STEP_COLOR[s] ?? '#60a5fa';
        const last = i === list.length - 1;
        return (
          <li key={s} className={cn('relative flex gap-4', !last && 'pb-7')} aria-current={active ? 'step' : undefined}>
            {!last && <span className="absolute bottom-0 top-11 w-0.5 start-5" style={{ background: i < cur ? color : 'rgb(var(--s-700))' }} aria-hidden />}
            <span
              className={cn('relative z-10 grid h-10 w-10 shrink-0 place-items-center rounded-full border-2', active && 'ring-4 ring-offset-2 ring-offset-slate-800')}
              style={{ borderColor: done ? color : 'rgb(var(--s-600))', background: done ? `${color}22` : 'rgb(var(--s-900))', color: done ? color : 'rgb(var(--s-400))', '--tw-ring-color': `${color}55` }}
            >
              {s === 'rejected' || s === 'cancelled' ? <XCircle className="h-5 w-5" aria-hidden /> : done && !active ? <Check className="h-5 w-5" aria-hidden /> : <span className="text-sm font-extrabold">{i + 1}</span>}
            </span>
            <div className="pt-1.5">
              <p className="font-bold" style={{ color: done ? color : 'rgb(var(--s-400))' }}>{labels[s]?.label ?? s}</p>
              <p className="text-sm text-slate-400">{active ? (hints ? STEP_HINT[s] : tr("الحالة الحالية")) : done ? tr("مكتملة") : tr("في الانتظار")}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
