import { Inbox, AlertCircle } from 'lucide-react';
import Button from './Button';
import { cn } from '../../utils/cn';
import { tr } from '../../i18n';

export function EmptyState({ title = tr("لا توجد بيانات"), description, icon: Icon = Inbox, action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-12 text-center">
      <div className="rounded-full bg-slate-700/60 p-3 text-slate-400"><Icon className="h-6 w-6" aria-hidden /></div>
      <p className="font-bold text-slate-200">{title}</p>
      {description && <p className="max-w-sm text-sm text-slate-400">{description}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message = tr("حدث خطأ أثناء تحميل البيانات"), onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-4 py-12 text-center" role="alert">
      <div className="rounded-full bg-red-500/15 p-3 text-red-300"><AlertCircle className="h-6 w-6" aria-hidden /></div>
      <p className="font-bold text-slate-200">{message}</p>
      {onRetry && <Button variant="secondary" size="sm" onClick={onRetry}>{tr("إعادة المحاولة")}</Button>}
    </div>
  );
}

export function Skeleton({ className }) {
  return <div className={cn('animate-pulse rounded-lg bg-slate-700/70', className)} aria-hidden />;
}

export function LoadingState({ rows = 4 }) {
  return (
    <div className="space-y-3 p-5" role="status" aria-label={tr("جارٍ التحميل")}>
      {Array.from({ length: rows }, (_, i) => <Skeleton key={i} className="h-10 w-full" />)}
    </div>
  );
}

// Standard contract for every API-driven view: loading -> error -> empty -> content.
export function AsyncView({ loading, error, empty, emptyProps, onRetry, children }) {
  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={typeof error === 'string' ? error : undefined} onRetry={onRetry} />;
  if (empty) return <EmptyState {...emptyProps} />;
  return children;
}
