import { useMemo, useState } from 'react';
import { Check, PencilLine, X } from 'lucide-react';
import { Button, ConfirmDialog, EndpointRequired, LoadingState, Modal, Select, Textarea, useToast } from '../common';
import AiRecommendationCard from './AiRecommendationCard';
import useFetch from '../../hooks/useFetch';
import { getRecommendation } from '../../api/ai';
import { submitDecision } from '../../api/decisions';
import { errorMessage, isMissingEndpoint } from '../../utils/errors';
import { SEVERITY } from '../../utils/status';
import { tr } from '../../i18n';

// The human-approval gate. The AI region is read-only; every action below is the supervisor's own decision.
export default function SupervisorDecisionPanel({ ticket, categories, departments, onDone }) {
  const toast = useToast();
  const rec = useFetch(() => getRecommendation(ticket.id), [ticket.id]);
  const [mode, setMode] = useState(null); // 'approve' | 'edit' | 'reject'
  const [busy, setBusy] = useState(false);
  const [edit, setEdit] = useState({ category_id_override: '', department_id_override: '', severity_override: '' });
  const [reason, setReason] = useState('');

  const catName = useMemo(() => Object.fromEntries((categories ?? []).map((c) => [c.id, c.name])), [categories]);
  const depName = useMemo(() => Object.fromEntries((departments ?? []).map((d) => [d.id, d.name])), [departments]);
  const missing = rec.error && isMissingEndpoint(rec.raw);

  const send = async (payload) => {
    setBusy(true);
    try {
      await submitDecision(ticket.id, payload);
      toast.success(tr("تم تسجيل قرارك"));
      setMode(null);
      onDone();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const sendEdit = () => {
    const payload = { action: 'edit' };
    Object.entries(edit).forEach(([k, v]) => { if (v) payload[k] = v; });
    if (Object.keys(payload).length === 1) return toast.warning(tr("اختر تعديلًا واحدًا على الأقل"));
    send(payload);
  };

  if (rec.loading) return <LoadingState rows={3} />;

  let unavailable = null;
  if (missing) {
    unavailable = <EndpointRequired endpoint="GET /api/v1/ai/tickets/{ticket_id}/recommendation">
      {tr("لا يمكن عرض توصية الذكاء الاصطناعي هنا حاليًا. القرار ما زال متاحًا، لكنه سيُتخذ دون رؤية التوصية في هذه الشاشة.")}
    </EndpointRequired>;
  } else if (rec.error) {
    unavailable = <p className="text-sm text-red-300" role="alert">{rec.error} <button className="font-bold underline" onClick={rec.reload}>{tr("إعادة المحاولة")}</button></p>;
  }

  return (
    <>
      <AiRecommendationCard
        recommendation={rec.data}
        unavailable={unavailable}
        categoryName={catName[rec.data?.category_id]}
        departmentName={depName[rec.data?.department_id]}
        actions={
          <>
            <Button variant="success" icon={Check} onClick={() => setMode('approve')}>{tr("اعتماد التوصية")}</Button>
            <Button variant="secondary" icon={PencilLine} onClick={() => setMode('edit')}>{tr("اعتماد مع تعديل")}</Button>
            <Button variant="danger" icon={X} onClick={() => setMode('reject')}>{tr("رفض")}</Button>
          </>
        }
      />

      <ConfirmDialog open={mode === 'approve'} onClose={() => setMode(null)} loading={busy}
        title={tr("اعتماد التوصية")} message={tr("سيتم اعتماد التصنيف والجهة والخطورة كما اقترحها الذكاء الاصطناعي، ثم يصبح البلاغ جاهزًا للإسناد لفريق صيانة.")}
        confirmLabel={tr("اعتماد")} onConfirm={() => send({ action: 'approve' })} />

      <Modal open={mode === 'edit'} onClose={() => setMode(null)} title={tr("اعتماد مع تعديل")}
        footer={<><Button variant="secondary" onClick={() => setMode(null)} disabled={busy}>{tr("إلغاء")}</Button><Button onClick={sendEdit} loading={busy}>{tr("حفظ القرار")}</Button></>}>
        <div className="space-y-4">
          <Select label={tr("التصنيف")} placeholder={tr("كما اقترح الذكاء الاصطناعي")} value={edit.category_id_override}
            onChange={(e) => setEdit({ ...edit, category_id_override: e.target.value })} options={(categories ?? []).map((c) => ({ value: c.id, label: c.name }))} />
          <Select label={tr("الجهة")} placeholder={tr("كما اقترح الذكاء الاصطناعي")} value={edit.department_id_override}
            onChange={(e) => setEdit({ ...edit, department_id_override: e.target.value })} options={(departments ?? []).map((d) => ({ value: d.id, label: d.name }))} />
          <Select label={tr("الخطورة")} placeholder={tr("كما اقترح الذكاء الاصطناعي")} value={edit.severity_override}
            onChange={(e) => setEdit({ ...edit, severity_override: e.target.value })} options={Object.entries(SEVERITY).map(([value, { label }]) => ({ value, label }))} />
        </div>
      </Modal>

      <Modal open={mode === 'reject'} onClose={() => setMode(null)} title={tr("رفض التوصية")}
        footer={<><Button variant="secondary" onClick={() => setMode(null)} disabled={busy}>{tr("إلغاء")}</Button>
          <Button variant="danger" loading={busy} disabled={!reason.trim()} onClick={() => send({ action: 'reject', reason: reason.trim() })}>{tr("تأكيد الرفض")}</Button></>}>
        <Textarea label={tr("سبب الرفض")} required value={reason} onChange={(e) => setReason(e.target.value)} hint={tr("السبب إلزامي ويُسجَّل في سجل التدقيق.")} />
      </Modal>
    </>
  );
}
