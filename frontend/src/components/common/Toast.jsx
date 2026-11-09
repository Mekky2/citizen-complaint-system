import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { CheckCircle2, AlertTriangle, XCircle, Info, X } from 'lucide-react';
import { cn } from '../../utils/cn';
import { tr } from '../../i18n';

const ToastCtx = createContext(null);

const STYLE = {
  success: { icon: CheckCircle2, cls: 'border-emerald-500/40 bg-emerald-950/90 text-emerald-200' },
  error: { icon: XCircle, cls: 'border-red-500/40 bg-red-950/90 text-red-200' },
  warning: { icon: AlertTriangle, cls: 'border-amber-500/40 bg-amber-950/90 text-amber-200' },
  info: { icon: Info, cls: 'border-blue-500/40 bg-slate-900/95 text-slate-100' },
};

export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);

  const dismiss = useCallback((id) => setItems((xs) => xs.filter((x) => x.id !== id)), []);
  const push = useCallback((type, message) => {
    const id = crypto.randomUUID();
    setItems((xs) => [...xs, { id, type, message }]);
    setTimeout(() => dismiss(id), 5000);
  }, [dismiss]);

  const api = useMemo(() => ({
    success: (m) => push('success', m),
    error: (m) => push('error', m),
    warning: (m) => push('warning', m),
    info: (m) => push('info', m),
  }), [push]);

  return (
    <ToastCtx.Provider value={api}>
      {children}
      <div className="fixed bottom-20 start-4 z-[60] lg:bottom-4 flex w-[calc(100%-2rem)] max-w-sm flex-col gap-2" aria-live="polite">
        {items.map((t) => {
          const { icon: Icon, cls } = STYLE[t.type];
          return (
            <div key={t.id} role="status" className={cn('flex items-start gap-2.5 rounded-xl border px-3.5 py-3 text-sm shadow-2xl backdrop-blur', cls)}>
              <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <span className="flex-1 font-semibold">{t.message}</span>
              <button onClick={() => dismiss(t.id)} aria-label={tr("إغلاق")} className="opacity-60 hover:opacity-100"><X className="h-4 w-4" /></button>
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastCtx);
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>');
  return ctx;
}
