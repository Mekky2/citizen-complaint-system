import { Gauge } from 'lucide-react';
import { SEVERITY } from '../../utils/status';
import { cn } from '../../utils/cn';
import { tr } from '../../i18n';

export default function SeverityPicker({ value, onChange, label = tr("درجة الخطورة") }) {
  return (
    <div role="group" aria-label={label}>
      <span className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-200"><Gauge className="h-4 w-4 text-slate-400" aria-hidden />{label}</span>
      <div className="grid grid-cols-4 gap-2">
        {Object.entries(SEVERITY).map(([k, s]) => (
          <button type="button" key={k} onClick={() => onChange(k)} aria-pressed={value === k}
            className={cn('rounded-lg border py-2 text-sm font-bold transition',
              value === k ? `${s.chip} ring-2 ring-current ring-offset-2 ring-offset-slate-800` : 'border-slate-600 text-slate-300 hover:bg-slate-700')}>
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
