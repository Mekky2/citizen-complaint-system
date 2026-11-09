import { cn } from '../../utils/cn';

// One h1 per page: title + one-line purpose on the start side, page actions on the end side.
export default function PageHeader({ title, subtitle, icon: Icon, actions, className }) {
  return (
    <div className={cn('flex flex-wrap items-center justify-between gap-3', className)}>
      <div className="flex min-w-0 items-center gap-3">
        {Icon && <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-blue-500/15 text-blue-300 ring-1 ring-blue-400/30"><Icon className="h-5 w-5" aria-hidden /></span>}
        <div className="min-w-0">
          <h1 className="text-2xl font-extrabold leading-tight text-slate-50">{title}</h1>
          {subtitle && <p className="text-sm text-slate-400">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
