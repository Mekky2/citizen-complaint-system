import { useState } from 'react';
import { CheckCircle2, XCircle, Eye, HardHat } from 'lucide-react';
import { AsyncView, Button, Card, EndpointRequired, Textarea, TaskStatusBadge, BeforeAfter, useToast } from '../common';
import EvidenceGallery from './EvidenceGallery';
import useFetch from '../../hooks/useFetch';
import { listTicketTasks, listEvidence } from '../../api/maintenance';
import { verifyTask } from '../../api/decisions';
import { errorMessage, isMissingEndpoint } from '../../utils/errors';
import { formatDateTime } from '../../utils/format';
import { tr } from '../../i18n';

// Supervisor view of the maintenance work on a ticket: latest attempt, its evidence, and — once the
// technician reports done (pending_verification) — the pass/fail verification.
export default function TaskVerificationPanel({ ticket, onDone }) {
  const tasks = useFetch(() => listTicketTasks(ticket.id), [ticket.id]);
  if (tasks.error && isMissingEndpoint(tasks.raw)) {
    return (
      <Card title={tr("مهمة الصيانة")} icon={HardHat}>
        <EndpointRequired endpoint="GET /api/v1/maintenance/tickets/{ticket_id}/tasks">
          {tr("المشرف يحتاج معرّف المهمة لعرض الأدلة وتنفيذ التحقق. حتى إضافته لا يمكن إتمام التحقق من هذه الشاشة.")}
        </EndpointRequired>
      </Card>
    );
  }
  const latest = [...(tasks.data ?? [])].sort((a, b) => b.attempt_number - a.attempt_number)[0];

  return (
    <Card title={tr("مهمة الصيانة")} icon={HardHat} subtitle={latest ? tr("المحاولة رقم {p0}", { p0: latest.attempt_number }) : undefined}>
      <AsyncView loading={tasks.loading} error={tasks.error} onRetry={tasks.reload} empty={!latest} emptyProps={{ title: tr("لا توجد مهمة مسندة بعد") }}>
        {latest && <TaskBody task={latest} ticket={ticket} onDone={onDone} />}
      </AsyncView>
    </Card>
  );
}

function TaskBody({ task, ticket, onDone }) {
  const toast = useToast();
  const evidence = useFetch(() => listEvidence(task.id), [task.id]);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  // Real before/after: the citizen's first ticket photo vs the newest 'after' evidence image (when both exist).
  const before = ticket.media?.find((m) => m.type === 'image')?.url;
  const after = [...(evidence.data ?? [])].reverse().find((e) => e.type === 'image' && e.stage === 'after')?.url;

  const verify = async (result) => {
    setBusy(true);
    try {
      await verifyTask(task.id, { result, note: note.trim() || undefined });
      toast.success(result === 'pass' ? tr("تم اعتماد التنفيذ") : tr("تم إرجاع المهمة لإعادة التنفيذ"));
      onDone();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <TaskStatusBadge value={task.status} />
        <span className="text-slate-400">{tr("أُسندت:")} {formatDateTime(task.assigned_at)}</span>
        {task.notes && <span className="text-slate-300">{tr("ملاحظات:")} {task.notes}</span>}
      </div>
      <div>
        <h4 className="mb-2 text-sm font-bold text-slate-200">{tr("أدلة التنفيذ")}</h4>
        <AsyncView loading={evidence.loading} error={evidence.error} onRetry={evidence.reload}><EvidenceGallery items={evidence.data} /></AsyncView>
      </div>
      {before && after && (
        <div>
          <h4 className="mb-2 flex items-center gap-2 text-sm font-bold text-slate-200"><Eye className="h-4 w-4 text-blue-400" aria-hidden />{tr("مقارنة قبل وبعد الإصلاح")}</h4>
          <BeforeAfter before={before} after={after} />
        </div>
      )}
      {task.status === 'pending_verification' && (
        <div className="space-y-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4">
          <p className="text-sm font-bold text-amber-300">{tr("بانتظار تحقق المشرف")}</p>
          <Textarea label={tr("ملاحظة التحقق")} rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="flex gap-2">
            <Button variant="success" icon={CheckCircle2} loading={busy} onClick={() => verify('pass')}>{tr("اجتاز التحقق")}</Button>
            <Button variant="danger" icon={XCircle} loading={busy} onClick={() => verify('fail')}>{tr("لم يجتز — إعادة تنفيذ")}</Button>
          </div>
        </div>
      )}
    </div>
  );
}
