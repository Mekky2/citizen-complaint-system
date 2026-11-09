import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Cpu, Loader2 } from 'lucide-react';
import { AsyncView, Button, Card, ConfirmDialog, useToast } from '../../components/common';
import TicketSummary from '../../components/tickets/TicketSummary';
import SupervisorDecisionPanel from '../../components/ai/SupervisorDecisionPanel';
import AssignTaskPanel from '../../components/maintenance/AssignTaskPanel';
import TaskVerificationPanel from '../../components/maintenance/TaskVerificationPanel';
import useFetch from '../../hooks/useFetch';
import { getTicket } from '../../api/tickets';
import { triggerAiRun } from '../../api/ai';
import { listCategories, listDepartments } from '../../api/admin';
import { errorMessage } from '../../utils/errors';
import { tr } from '../../i18n';

// Right-hand pane of the Operations Room. What the supervisor can do depends only on the ticket's real status.
export default function IncidentWorkspace() {
  const { id } = useParams();
  const toast = useToast();
  const ticket = useFetch(() => getTicket(id), [id]);
  const categories = useFetch(listCategories, []);
  const departments = useFetch(listDepartments, []);
  const [confirmAi, setConfirmAi] = useState(false);
  const [busy, setBusy] = useState(false);

  const runAi = async () => {
    setBusy(true);
    try {
      await triggerAiRun(id);
      toast.success(tr("بدأ التحليل الآلي للبلاغ"));
      setConfirmAi(false);
      ticket.reload();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };

  const t = ticket.data;
  return (
    <AsyncView loading={ticket.loading} error={ticket.error} onRetry={ticket.reload}>
      {t && (
        <div className="space-y-4">
          {t.status === 'submitted' && (
            <Card title={tr("خطوة المراجعة الآلية")} subtitle={tr("لم يُحلَّل هذا البلاغ بعد")}>
              <p className="mb-3 text-sm text-slate-300">{tr("يمكنك تشغيل تحليل الذكاء الاصطناعي لاقتراح التصنيف والجهة والخطورة. النتيجة مجرد توصية تنتظر قرارك.")}</p>
              <Button icon={Cpu} onClick={() => setConfirmAi(true)}>{tr("تشغيل التحليل الآلي")}</Button>
            </Card>
          )}
          {t.status === 'under_ai_review' && (
            <Card>
              <div className="flex items-center gap-3 text-sm text-slate-200">
                <Loader2 className="h-5 w-5 animate-spin text-blue-300" aria-hidden />
                <span className="flex-1">{tr("الذكاء الاصطناعي يحلل البلاغ الآن. سيظهر الاقتراح هنا عند اكتماله.")}</span>
                <Button size="sm" variant="secondary" onClick={ticket.reload}>{tr("تحديث")}</Button>
              </div>
            </Card>
          )}
          {t.status === 'awaiting_approval' && (
            <SupervisorDecisionPanel ticket={t} categories={categories.data} departments={departments.data} onDone={ticket.reload} />
          )}
          {t.status === 'assigned' && <AssignTaskPanel ticket={t} onDone={ticket.reload} />}
          {['in_progress', 'pending_verification', 'completed'].includes(t.status) && <TaskVerificationPanel ticket={t} onDone={ticket.reload} />}

          <TicketSummary ticket={t} showCitizenId />
        </div>
      )}
      <ConfirmDialog open={confirmAi} onClose={() => setConfirmAi(false)} onConfirm={runAi} loading={busy}
        title={tr("تشغيل التحليل الآلي")} message={tr("سيتم إرسال البلاغ إلى خدمة الذكاء الاصطناعي لتحليله. لن يُنفَّذ أي إجراء قبل اعتمادك.")} confirmLabel={tr("تشغيل")} />
    </AsyncView>
  );
}
