import { cn } from '../../utils/cn';
import { TICKET_STATUS, TASK_STATUS, SEVERITY } from '../../utils/status';

// Tinted pills as in the prototype: translucent fill + matching border.
const TONES = {
  neutral: 'bg-slate-500/15 text-slate-300 border-slate-500/40',
  info: 'bg-blue-500/15 text-blue-300 border-blue-500/40',
  ok: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
  warn: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
  high: 'bg-orange-500/15 text-orange-300 border-orange-500/40',
  crit: 'bg-red-500/15 text-red-300 border-red-500/40',
};

export default function Badge({ tone = 'neutral', dot = true, className, children }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-bold', TONES[tone], className)}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  );
}

const make = (map) =>
  function MappedBadge({ value, ...rest }) {
    const m = map[value] ?? { label: value ?? '—', tone: 'neutral' };
    return <Badge tone={m.tone} {...rest}>{m.label}</Badge>;
  };

export const TicketStatusBadge = make(TICKET_STATUS);
export const TaskStatusBadge = make(TASK_STATUS);
export const SeverityBadge = make(SEVERITY);
