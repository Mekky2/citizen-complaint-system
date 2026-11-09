import { PlugZap } from 'lucide-react';
import { tr } from '../../i18n';

// Shown wherever a flagged backend gap blocks a feature. Never substitutes fake data.
export default function EndpointRequired({ endpoint, children }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-slate-200" role="note">
      <PlugZap className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" aria-hidden />
      <div className="space-y-1">
        <p className="font-bold text-amber-300">{tr("هذه الميزة تحتاج واجهة برمجية غير متوفرة في الخادم حاليًا")}</p>
        <p className="text-xs text-slate-300">{tr("المطلوب في الخادم")}: <span dir="ltr" className="font-mono">{endpoint}</span></p>
        {children && <p className="text-slate-300">{children}</p>}
      </div>
    </div>
  );
}
