import { Sparkles, UserCheck, Scale, Copy } from 'lucide-react';
import { SeverityBadge } from '../common/Badge';
import { cn } from '../../utils/cn';
import { tr } from '../../i18n';

// Fixed trust-boundary contract: the AI region is always read-only and always reads as a
// suggestion. The human decision region is visually separate and rendered via `decision` / `actions`.
//
// Props follow the backend's AiRecommendationOut: { severity, confidence, explanation, factors, evidence[] }.
// `categoryName` / `departmentName` are resolved by the page (ids -> names) before being passed in.
export default function AiRecommendationCard({ recommendation, categoryName, departmentName, decision, actions, unavailable }) {
  const rec = recommendation;
  const legal = (rec?.evidence ?? []).filter((e) => e.evidence_type === 'LEGAL_EVIDENCE');
  const similar = (rec?.evidence ?? []).filter((e) => e.evidence_type === 'SIMILAR_CASE');
  const pct = rec?.confidence != null ? Math.round(rec.confidence * 100) : null;

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-700 bg-slate-800/80 shadow-xl">
      <section className="border-s-4 border-blue-500 bg-blue-500/10 p-5" aria-label={tr("توصية الذكاء الاصطناعي")}>
        <header className="mb-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-blue-300">
            <Sparkles className="h-4 w-4" aria-hidden />
            <h3 className="text-sm font-bold">{tr("توصية الذكاء الاصطناعي")}</h3>
            <span className="rounded bg-blue-500/20 px-1.5 py-0.5 text-[11px] font-bold">{tr("اقتراح — للقراءة فقط")}</span>
          </div>
          {pct != null && <span className="text-xs font-semibold text-slate-300">{tr("درجة الثقة")} <span dir="ltr">{pct}%</span></span>}
        </header>

        {unavailable ? unavailable : (<>
        <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
          <div><dt className="text-xs text-slate-400">{tr("التصنيف المقترح")}</dt><dd className="font-bold text-slate-50">{categoryName ?? '—'}</dd></div>
          <div><dt className="text-xs text-slate-400">{tr("الجهة المقترحة")}</dt><dd className="font-bold text-slate-50">{departmentName ?? '—'}</dd></div>
          <div><dt className="text-xs text-slate-400">{tr("الخطورة المقترحة")}</dt><dd className="mt-0.5">{rec?.severity ? <SeverityBadge value={rec.severity} /> : '—'}</dd></div>
        </dl>

        {pct != null && (
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-700" role="presentation">
            <div className="h-full rounded-full bg-blue-500" style={{ width: `${pct}%` }} />
          </div>
        )}
        {rec?.explanation && <p className="mt-3 text-sm leading-relaxed text-slate-200">{rec.explanation}</p>}

        {(legal.length > 0 || similar.length > 0) && (
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <EvidenceList icon={Scale} title={tr("أدلة قانونية")} items={legal} />
            <EvidenceList icon={Copy} title={tr("حالات مشابهة")} items={similar} />
          </div>
        )}
        </>)}
      </section>

      <section className="border-t border-slate-700 border-s-4 border-s-emerald-500 bg-slate-800/80 p-5" aria-label={tr("قرار المشرف")}>
        <header className="mb-2 flex items-center gap-2 text-slate-50">
          <UserCheck className="h-4 w-4" aria-hidden />
          <h3 className="text-sm font-bold">{tr("قرار المشرف")}</h3>
          <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[11px] font-bold text-emerald-300">{tr("قرار بشري")}</span>
        </header>
        {decision ?? (
          <p className="text-sm text-slate-400">{tr("لم يُتخذ قرار بعد. لن يتم تنفيذ أي إجراء إلا بعد اعتماد المشرف.")}</p>
        )}
        {actions && <div className="mt-4 flex flex-wrap gap-2">{actions}</div>}
      </section>
    </div>
  );
}

function EvidenceList({ icon: Icon, title, items }) {
  if (!items.length) return null;
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-900/50 p-3">
      <h4 className="mb-2 flex items-center gap-1.5 text-xs font-bold text-slate-300"><Icon className="h-3.5 w-3.5" aria-hidden />{title}</h4>
      <ul className="space-y-2">
        {items.map((e) => (
          <li key={e.id} className="text-xs leading-relaxed text-slate-200">
            {e.snippet}
            {e.similarity_score != null && (
              <span className={cn('ms-1.5 font-semibold text-slate-400')} dir="ltr">({Math.round(e.similarity_score * 100)}%)</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
