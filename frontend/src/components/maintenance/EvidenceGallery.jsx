import { useState } from 'react';
import { Modal } from '../common/Modal';
import { EmptyState } from '../common/States';
import { ImageOff } from 'lucide-react';
import { tr } from '../../i18n';

// Backend TaskEvidenceCreateIn.stage is 'progress' | 'after'
const STAGE_LABEL = { progress: tr("أثناء التنفيذ"), after: tr("بعد التنفيذ") };

// items: TaskEvidenceOut[] -> { id, type, stage, url, created_at }
export default function EvidenceGallery({ items }) {
  const [open, setOpen] = useState(null);
  if (!items?.length) return <EmptyState icon={ImageOff} title={tr("لا توجد أدلة مرفوعة بعد")} />;

  return (
    <>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {items.map((e) => (
          <li key={e.id}>
            <button type="button" onClick={() => setOpen(e)} className="group relative block aspect-square w-full overflow-hidden rounded-xl border border-slate-600 bg-slate-900">
              {e.type === 'image' ? (
                <img src={e.url} alt={tr("دليل {p0}", { p0: STAGE_LABEL[e.stage] ?? e.stage })} className="h-full w-full object-cover transition-transform group-hover:scale-105" loading="lazy" />
              ) : (
                <span className="flex h-full items-center justify-center text-xs text-slate-400">{e.type}</span>
              )}
              <span className="absolute start-1.5 top-1.5 rounded bg-slate-900/75 px-1.5 py-0.5 text-[11px] font-bold text-white">
                {STAGE_LABEL[e.stage] ?? e.stage}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <Modal open={!!open} onClose={() => setOpen(null)} title={open ? tr("دليل — {p0}", { p0: STAGE_LABEL[open.stage] ?? open.stage }) : ''} size="lg">
        {open?.type === 'image' && <img src={open.url} alt="" className="w-full rounded-xl" />}
      </Modal>
    </>
  );
}
