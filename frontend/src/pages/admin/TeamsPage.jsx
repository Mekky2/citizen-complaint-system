import { useMemo, useState } from 'react';
import { Plus, UserPlus, HardHat } from 'lucide-react';
import { Button, Card, EndpointRequired, Input, Modal, Select, Table, AsyncView, PageHeader, useToast } from '../../components/common';
import useFetch from '../../hooks/useFetch';
import { listDepartments } from '../../api/admin';
import { listTeams, createTeam, addTeamMember, listTeamMembers } from '../../api/maintenance';
import { listUsers } from '../../api/users';
import { errorMessage, isMissingEndpoint } from '../../utils/errors';
import { tr } from '../../i18n';

export default function TeamsPage() {
  const toast = useToast();
  const teams = useFetch(() => listTeams(), []);
  const deps = useFetch(listDepartments, []);
  const techs = useFetch(() => listUsers({ role: 'technician', limit: 200 }), []);
  const depName = useMemo(() => Object.fromEntries((deps.data ?? []).map((d) => [d.id, d.name])), [deps.data]);
  const [creating, setCreating] = useState(false);
  const [adding, setAdding] = useState(null); // team
  const [viewing, setViewing] = useState(null); // team
  const [f, setF] = useState({ name: '', department_id: '' });
  const [userId, setUserId] = useState('');
  const [busy, setBusy] = useState(false);

  const run = async (fn, okMsg, after) => {
    setBusy(true);
    try { await fn(); toast.success(okMsg); after(); } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };

  const columns = [
    { key: 'name', header: tr("الفريق"), render: (t) => <span className="font-bold text-slate-100">{t.name}</span> },
    { key: 'dep', header: tr("الجهة"), render: (t) => depName[t.department_id] ?? '—' },
    { key: 'a', header: '', render: (t) => (
      <div className="flex justify-end gap-1">
        <Button size="sm" variant="ghost" onClick={() => setViewing(t)}>{tr("الأعضاء")}</Button>
        <Button size="sm" variant="secondary" icon={UserPlus} onClick={() => { setAdding(t); setUserId(''); }}>{tr("إضافة فني")}</Button>
      </div>
    ) },
  ];

  return (
    <div className="space-y-5">
      <PageHeader icon={HardHat} title={tr("فرق الصيانة")} subtitle={tr("فرق التنفيذ الميداني وأعضاؤها.")} actions={<Button icon={Plus} onClick={() => setCreating(true)}>{tr("فريق جديد")}</Button>} />
      <Card bodyClassName="p-0">
        <AsyncView loading={teams.loading} error={teams.error} onRetry={teams.reload} empty={teams.data?.length === 0} emptyProps={{ title: tr("لا توجد فرق بعد") }}>
          <Table columns={columns} rows={teams.data ?? []} />
        </AsyncView>
      </Card>

      <Modal open={creating} onClose={() => setCreating(false)} title={tr("فريق صيانة جديد")}
        footer={<><Button variant="secondary" onClick={() => setCreating(false)} disabled={busy}>{tr("إلغاء")}</Button>
          <Button loading={busy} disabled={f.name.trim().length < 2 || !f.department_id}
            onClick={() => run(() => createTeam({ name: f.name.trim(), department_id: f.department_id }), tr("تم إنشاء الفريق"), () => { setCreating(false); setF({ name: '', department_id: '' }); teams.reload(); })}>{tr("حفظ")}</Button></>}>
        <div className="space-y-4">
          <Input label={tr("اسم الفريق")} required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
          <Select label={tr("الجهة")} required placeholder={tr("اختر الجهة")} value={f.department_id} onChange={(e) => setF({ ...f, department_id: e.target.value })} options={(deps.data ?? []).map((d) => ({ value: d.id, label: d.name }))} />
        </div>
      </Modal>

      <Modal open={!!adding} onClose={() => setAdding(null)} title={tr("إضافة فني إلى «{p0}»", { p0: adding?.name ?? '' })}
        footer={<><Button variant="secondary" onClick={() => setAdding(null)} disabled={busy}>{tr("إلغاء")}</Button>
          <Button loading={busy} disabled={!userId} onClick={() => run(() => addTeamMember(adding.id, userId), tr("تمت إضافة الفني"), () => setAdding(null))}>{tr("إضافة")}</Button></>}>
        <AsyncView loading={techs.loading} error={techs.error} onRetry={techs.reload} empty={techs.data?.length === 0} emptyProps={{ title: tr("لا يوجد فنيون. أنشئ حساب فني من صفحة المستخدمين.") }}>
          <Select label={tr("الفني")} placeholder={tr("اختر الفني")} value={userId} onChange={(e) => setUserId(e.target.value)} options={(techs.data ?? []).map((u) => ({ value: u.id, label: u.name }))} />
        </AsyncView>
      </Modal>

      {viewing && <MembersModal team={viewing} onClose={() => setViewing(null)} />}
    </div>
  );
}

function MembersModal({ team, onClose }) {
  const { data, loading, error, raw, reload } = useFetch(() => listTeamMembers(team.id), [team.id]);
  return (
    <Modal open onClose={onClose} title={tr("أعضاء «{p0}»", { p0: team.name })}>
      {error && isMissingEndpoint(raw)
        ? <EndpointRequired endpoint="GET /api/v1/maintenance/teams/{team_id}/members">{tr("عرض أعضاء الفريق يحتاج هذه الواجهة البرمجية. إضافة الأعضاء تعمل بالفعل.")}</EndpointRequired>
        : (
          <AsyncView loading={loading} error={error} onRetry={reload} empty={data?.length === 0} emptyProps={{ title: tr("لا يوجد أعضاء") }}>
            <ul className="divide-y divide-slate-700/70 text-sm">{data?.map((m) => <li key={m.id ?? m.user_id} className="py-2">{m.name ?? m.user_id}</li>)}</ul>
          </AsyncView>
        )}
    </Modal>
  );
}
