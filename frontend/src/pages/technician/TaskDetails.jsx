import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowRight, Play, SendHorizonal, MapPin, RefreshCw, Camera, ExternalLink, ClipboardCheck, AlertTriangle, ListChecks } from 'lucide-react';
import { AsyncView, Button, Card, EndpointRequired, FileUpload, Select, Textarea, TaskStatusBadge, useToast } from '../../components/common';
import MapView from '../../components/common/MapView';
import EvidenceGallery from '../../components/maintenance/EvidenceGallery';
import useFetch from '../../hooks/useFetch';
import { getTicket } from '../../api/tickets';
import { listMyTasks, listEvidence, updateTaskStatus, addEvidence } from '../../api/maintenance';
import { UPLOADS_ENABLED, uploadFile, mediaTypeOf } from '../../api/storage';
import { errorMessage } from '../../utils/errors';
import { formatDateTime } from '../../utils/format';
import { historyReason } from '../../utils/status';
import { tr } from '../../i18n';

const NEXT_STEP = {
  assigned: tr("الخطوة التالية: توجّه إلى الموقع ثم اضغط «بدء التنفيذ»."),
  in_progress: tr("الخطوة التالية: نفّذ الأعمال وأرفق الأدلة، ثم أرسل المهمة للتحقق."),
  pending_verification: tr("بانتظار قرار المشرف. لا يلزم أي إجراء منك الآن."),
  completed: tr("انتهت هذه المحاولة من المهمة."),
};

export default function TaskDetails() {
  const { id } = useParams();
  const toast = useToast();
  // There is no GET /tasks/{id}; the task comes from the technician's own task list.
  const tasks = useFetch(listMyTasks, []);
  const task = tasks.data?.find((t) => t.id === id);
  const ticket = useFetch(() => getTicket(task.ticket_id), [task?.ticket_id], { enabled: !!task });
  const evidence = useFetch(() => listEvidence(id), [id], { enabled: !!task });

  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState([]);
  const [stage, setStage] = useState('after');

  const move = async (status) => {
    setBusy(true);
    try {
      await updateTaskStatus(id, status, notes.trim() || undefined);
      toast.success(status === 'in_progress' ? tr("بدأ التنفيذ") : tr("تم إرسال المهمة للتحقق"));
      setNotes('');
      tasks.reload();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };

  const uploadEvidence = async () => {
    setBusy(true);
    try {
      for (const file of files) {
        const url = await uploadFile(file);
        await addEvidence(id, { type: mediaTypeOf(file), stage, url });
      }
      setFiles([]);
      toast.success(tr("تم رفع الأدلة"));
      evidence.reload();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };

  const t = ticket.data;
  // Verification outcomes live in the ticket's status history (there is no read endpoint for verifications).
  const verifications = (t?.status_history ?? []).filter((h) => /^Verification/.test(h.reason || '')).reverse();
  const passed = (h) => /^Verification passed/.test(h.reason);
  const isRework = task && task.attempt_number > 1 && task.status !== 'completed';
  return (
    <div className="space-y-4">
      <Link to="/technician/tasks" className="inline-flex items-center gap-1 text-sm font-semibold text-slate-300 hover:text-white"><ArrowRight className="h-4 w-4 ltr:rotate-180" />{tr("مهامي")}</Link>
      <AsyncView loading={tasks.loading} error={tasks.error} onRetry={tasks.reload} empty={!task}
        emptyProps={{ title: tr("المهمة غير موجودة أو ليست ضمن فريقك") }}>
        {task && (
          <>
            <Card>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h1 className="text-2xl font-extrabold text-slate-50">{t ? t.title || tr("مهمة صيانة") : '…'}</h1>
                  <p className="text-xs text-slate-400">{tr("محاولة")} {task.attempt_number} {tr("· أُسندت")} {formatDateTime(task.assigned_at)}</p>
                </div>
                <TaskStatusBadge value={task.status} />
              </div>
              {t && <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-200">{t.description}</p>}
              {t?.address && <p className="mt-2 text-sm text-slate-300">{tr("العنوان:")} {t.address}</p>}
              {task.notes && <p className="mt-2 rounded-xl bg-slate-900/60 p-3 text-sm text-slate-200">{tr("ملاحظات المشرف:")} {task.notes}</p>}
            </Card>

            <div className="rounded-xl border border-blue-500/30 bg-blue-500/10 p-3 text-sm font-semibold text-blue-200" role="status">
              <ListChecks className="me-2 inline h-4 w-4" aria-hidden />{NEXT_STEP[task.status]}
            </div>
            {isRework && (
              <div className="flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200" role="alert">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
                <p>{tr("هذه مهمة إعادة عمل (المحاولة {n}): لم ينجح التحقق من المحاولة السابقة. راجع ملاحظات المشرف وسجل التحقق قبل البدء.", { n: task.attempt_number })}</p>
              </div>
            )}

            {t && (
              <Card title={tr("الموقع")} icon={MapPin}>
                <MapView position={[t.lat, t.lng]} height={220} />
                <a href={`https://www.openstreetmap.org/?mlat=${t.lat}&mlon=${t.lng}#map=19/${t.lat}/${t.lng}`} target="_blank" rel="noreferrer"
                  className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-blue-300 hover:underline">
                  <ExternalLink className="h-4 w-4" aria-hidden />{tr("فتح الموقع في الخريطة")}
                </a>
              </Card>
            )}

            {verifications.length > 0 && (
              <Card title={tr("نتيجة التحقق")} icon={ClipboardCheck}>
                <ul className="space-y-2">
                  {verifications.map((h) => (
                    <li key={h.id} className={`rounded-xl border p-3 text-sm ${passed(h) ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200' : 'border-red-500/40 bg-red-500/10 text-red-200'}`}>
                      <p className="font-semibold">{historyReason(h.reason)}</p>
                      <p className="mt-1 text-xs opacity-80">{formatDateTime(h.created_at)}</p>
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            {task.status !== 'completed' && (
              <Card title={tr("تحديث الحالة")} icon={RefreshCw}>
                {task.status === 'pending_verification' ? (
                  <p className="text-sm text-slate-300">{tr("تم إرسال المهمة للتحقق. بانتظار قرار المشرف.")}</p>
                ) : (
                  <div className="space-y-3">
                    <Textarea label={tr("ملاحظات (اختياري)")} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
                    {task.status === 'assigned'
                      ? <Button icon={Play} loading={busy} onClick={() => move('in_progress')}>{tr("بدء التنفيذ")}</Button>
                      : <Button variant="success" icon={SendHorizonal} loading={busy} onClick={() => move('pending_verification')}>{tr("تم التنفيذ — إرسال للتحقق")}</Button>}
                  </div>
                )}
              </Card>
            )}

            <Card title={tr("أدلة التنفيذ")} icon={Camera}>
              <AsyncView loading={evidence.loading} error={evidence.error} onRetry={evidence.reload}><EvidenceGallery items={evidence.data} /></AsyncView>
              {task.status !== 'completed' && (
                <div className="mt-5 border-t border-slate-700 pt-4">
                  {UPLOADS_ENABLED ? (
                    <div className="space-y-3">
                      <Select label={tr("مرحلة الدليل")} value={stage} onChange={(e) => setStage(e.target.value)} options={[{ value: 'progress', label: tr("أثناء التنفيذ") }, { value: 'after', label: tr("بعد التنفيذ") }]} />
                      <FileUpload files={files} onChange={setFiles} accept="image/*,video/*" onReject={toast.error} />
                      <Button onClick={uploadEvidence} loading={busy} disabled={!files.length}>{tr("رفع الأدلة")}</Button>
                    </div>
                  ) : (
                    <EndpointRequired endpoint={tr("رفع الملفات (رابط رفع مباشر)")}>{tr("لا يمكن رفع صور الأدلة قبل توفر رفع الملفات في الخادم.")}</EndpointRequired>
                  )}
                </div>
              )}
            </Card>
          </>
        )}
      </AsyncView>
    </div>
  );
}
