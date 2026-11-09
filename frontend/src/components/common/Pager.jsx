import { ChevronLeft, ChevronRight } from 'lucide-react';
import Button from './Button';
import { tr } from '../../i18n';

// The backend's list endpoints return plain arrays (no total), so "next" is offered while a full page came back.
const PrevIcon = (p) => <ChevronRight {...p} className={`${p.className ?? ''} ltr:rotate-180`} />;

export default function Pager({ offset, limit, count, onChange }) {
  if (offset === 0 && count < limit) return null;
  return (
    <div className="flex items-center justify-between border-t border-slate-700 px-4 py-3 text-sm">
      <Button variant="secondary" size="sm" icon={PrevIcon} disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>{tr("السابق")}</Button>
      <span className="text-slate-400">{tr("صفحة")} {Math.floor(offset / limit) + 1}</span>
      <Button variant="secondary" size="sm" disabled={count < limit} onClick={() => onChange(offset + limit)}>{tr("التالي")} <ChevronLeft className="h-4 w-4 ltr:rotate-180" /></Button>
    </div>
  );
}
