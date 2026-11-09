import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { tr } from '../../i18n';

export default function CopyButton({ text, label = tr("نسخ الرقم"), done = tr("تم النسخ") }) {
  const [ok, setOk] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setOk(true); setTimeout(() => setOk(false), 1800); } catch { /* clipboard blocked */ }
  };
  return (
    <button type="button" onClick={copy} className="inline-flex items-center gap-1.5 text-sm text-slate-300 hover:text-white">
      {ok ? <Check className="h-4 w-4 text-emerald-400" aria-hidden /> : <Copy className="h-4 w-4" aria-hidden />}{ok ? done : label}
    </button>
  );
}
