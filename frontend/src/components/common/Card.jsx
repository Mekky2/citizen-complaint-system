import { cn } from '../../utils/cn';

// Prototype card: rounded-2xl, slate-800/80, slate-700 border, header with blue icon.
export default function Card({ title, subtitle, icon: Icon, actions, className, bodyClassName, children }) {
  return (
    <section className={cn('rounded-2xl border border-slate-700 bg-slate-800/80 shadow-xl', className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-slate-700 px-5 py-4">
          <div className="min-w-0">
            {title && (
              <h3 className="flex items-center gap-2 text-lg font-bold text-slate-50">
                {Icon && <Icon className="h-5 w-5 shrink-0 text-blue-400" aria-hidden />}{title}
              </h3>
            )}
            {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn('p-5', bodyClassName)}>{children}</div>
    </section>
  );
}
