import { useId } from 'react';
import { AlertCircle, CheckCircle2 } from 'lucide-react';
import { cn } from '../../utils/cn';

// Prototype input: rounded-xl, slate-900/70 fill, blue focus ring.
export const inputCls =
  'w-full rounded-xl bg-slate-900/70 border px-4 py-3 text-slate-100 placeholder-slate-500 transition ' +
  'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-60';

// Labelled wrapper (icon + label above, error/success hint below). Also used directly for custom controls.
export function Field({ id, label, icon: Icon, error, hint, success, required, children }) {
  return (
    <div className="block">
      {label && (
        <label htmlFor={id} className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-200">
          {Icon && <Icon className="h-4 w-4 text-slate-400" aria-hidden />}
          {label}
          {required && <span className="text-red-400" aria-hidden>*</span>}
        </label>
      )}
      {children}
      {error ? (
        <p role="alert" className="mt-2 flex items-start gap-1.5 text-sm text-red-300"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{error}</p>
      ) : success ? (
        <p className="mt-2 flex items-start gap-1.5 text-sm text-emerald-300"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{success}</p>
      ) : hint ? (
        <p className="mt-2 text-sm text-slate-400">{hint}</p>
      ) : null}
    </div>
  );
}

export function Input({ label, icon, error, hint, success, required, className, ...rest }) {
  const id = useId();
  return (
    <Field {...{ id, label, icon, error, hint, success, required }}>
      <input id={id} aria-invalid={!!error} className={cn(inputCls, error ? 'border-red-500/70' : 'border-slate-600', className)} {...rest} />
    </Field>
  );
}

export function Textarea({ label, icon, error, hint, success, required, className, rows = 4, ...rest }) {
  const id = useId();
  return (
    <Field {...{ id, label, icon, error, hint, success, required }}>
      <textarea id={id} rows={rows} aria-invalid={!!error} className={cn(inputCls, error ? 'border-red-500/70' : 'border-slate-600', className)} {...rest} />
    </Field>
  );
}

export function Select({ label, icon, error, hint, required, options = [], placeholder, className, ...rest }) {
  const id = useId();
  return (
    <Field {...{ id, label, icon, error, hint, required }}>
      <select id={id} aria-invalid={!!error} className={cn(inputCls, error ? 'border-red-500/70' : 'border-slate-600', className)} {...rest}>
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </Field>
  );
}
