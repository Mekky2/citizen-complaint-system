import { Loader2 } from 'lucide-react';
import { cn } from '../../utils/cn';

const VARIANTS = {
  primary: 'bg-blue-600 text-white hover:bg-blue-500 shadow-lg shadow-blue-900/30 disabled:bg-slate-700 disabled:text-slate-400 disabled:shadow-none',
  secondary: 'bg-slate-700 text-slate-100 hover:bg-slate-600 disabled:text-slate-500',
  ghost: 'bg-transparent text-slate-300 hover:bg-slate-700/60 disabled:text-slate-500',
  danger: 'bg-red-600 text-white hover:bg-red-500 disabled:bg-slate-700 disabled:text-slate-400',
  success: 'bg-emerald-600 text-white hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-400',
};
const SIZES = {
  sm: 'h-9 px-3 text-sm gap-1.5 rounded-lg',
  md: 'h-11 px-4 text-sm gap-2 rounded-xl',
  lg: 'h-14 px-6 text-lg gap-2 rounded-xl font-extrabold',
};

export default function Button({
  variant = 'primary', size = 'md', loading = false, icon: Icon, className, children, disabled, type = 'button', ...rest
}) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center font-bold transition focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-400/50 disabled:cursor-not-allowed',
        VARIANTS[variant], SIZES[size], className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : Icon ? <Icon className="h-4 w-4" aria-hidden /> : null}
      {children}
    </button>
  );
}
