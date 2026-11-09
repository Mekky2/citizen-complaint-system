import { useState } from 'react';
import { Wrench } from 'lucide-react';
import { AsyncView, Button, Card, Select, Textarea, useToast } from '../common';
import useFetch from '../../hooks/useFetch';
import { listTeams, createTask } from '../../api/maintenance';
import { errorMessage } from '../../utils/errors';
import { tr } from '../../i18n';

// Ticket is 'assigned' (approved) — a supervisor now opens a maintenance task for one team.
export default function AssignTaskPanel({ ticket, onDone }) {
  const toast = useToast();
  const teams = useFetch(() => listTeams(ticket.department_id ? { department_id: ticket.department_id } : undefined), [ticket.department_id]);
  const [teamId, setTeamId] = useState('');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      await createTask(ticket.id, { team_id: teamId, notes: notes.trim() || undefined });
      toast.success(tr("تم إسناد المهمة للفريق"));
      onDone();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };

  return (
    <Card title={tr("إسناد إلى فريق صيانة")} icon={Wrench} subtitle={tr("البلاغ معتمد وجاهز للتنفيذ")}>
      <AsyncView loading={teams.loading} error={teams.error} onRetry={teams.reload} empty={teams.data?.length === 0}
        emptyProps={{ title: tr("لا توجد فرق صيانة لهذه الجهة"), description: tr("يمكن للمدير إنشاء فريق من صفحة فرق الصيانة."), icon: Wrench }}>
        <div className="space-y-4">
          <Select label={tr("الفريق")} placeholder={tr("اختر الفريق")} value={teamId} onChange={(e) => setTeamId(e.target.value)} options={(teams.data ?? []).map((t) => ({ value: t.id, label: t.name }))} />
          <Textarea label={tr("ملاحظات للفريق (اختياري)")} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
          <Button onClick={submit} loading={busy} disabled={!teamId}>{tr("إسناد المهمة")}</Button>
        </div>
      </AsyncView>
    </Card>
  );
}
