import { useState } from 'react';
import { UserPlus, Pencil, UserX, UserCheck, Users } from 'lucide-react';
import { Badge, Button, Card, ConfirmDialog, Input, Modal, Select, Table, AsyncView, PageHeader, useToast } from '../../components/common';
import Pager from '../../components/common/Pager';
import useFetch from '../../hooks/useFetch';
import { listUsers, updateUser, createStaff } from '../../api/users';
import { errorMessage } from '../../utils/errors';
import { validateName, validatePhone, validatePassword } from '../../utils/validators';
import { ROLE_LABEL } from '../../utils/status';
import { tr } from '../../i18n';

const LIMIT = 20;
const ROLE_OPTIONS = Object.entries(ROLE_LABEL).map(([value, label]) => ({ value, label }));
const STAFF_ROLES = ROLE_OPTIONS.filter((r) => r.value !== 'citizen');

export default function UsersPage() {
  const toast = useToast();
  const [role, setRole] = useState('');
  const [offset, setOffset] = useState(0);
  const { data, loading, error, reload } = useFetch(() => listUsers({ limit: LIMIT, offset, ...(role && { role }) }), [role, offset]);
  const [editing, setEditing] = useState(null);
  const [toggle, setToggle] = useState(null); // { user, deactivated }
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);

  const columns = [
    { key: 'name', header: tr("الاسم"), render: (u) => <span className="font-semibold text-slate-50">{u.name}</span> },
    { key: 'role', header: tr("الدور"), render: (u) => <Badge tone={{ admin: 'crit', supervisor: 'warn', technician: 'high', citizen: 'info' }[u.role] ?? 'neutral'} dot={false}>{ROLE_LABEL[u.role] ?? u.role}</Badge> },
    { key: 'phone', header: tr("الموبايل"), render: (u) => <span dir="ltr">{u.phone ?? '—'}</span> },
    { key: 'email', header: tr("البريد"), render: (u) => <span dir="ltr">{u.email ?? '—'}</span> },
    { key: 'a', header: '', render: (u) => (
      <div className="flex justify-end gap-1">
        <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setEditing(u)} aria-label={tr("تعديل {p0}", { p0: u.name })} />
        <Button size="sm" variant="ghost" icon={UserX} onClick={() => setToggle({ user: u, deactivated: true })} aria-label={tr("تعطيل {p0}", { p0: u.name })} />
        <Button size="sm" variant="ghost" icon={UserCheck} onClick={() => setToggle({ user: u, deactivated: false })} aria-label={tr("تفعيل {p0}", { p0: u.name })} />
      </div>
    ) },
  ];

  const doToggle = async () => {
    setBusy(true);
    try {
      await updateUser(toggle.user.id, { deactivated: toggle.deactivated });
      toast.success(toggle.deactivated ? tr("تم تعطيل الحساب") : tr("تمت إعادة تفعيل الحساب"));
      setToggle(null);
      reload();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-5">
      <PageHeader icon={Users} title={tr("المستخدمون")} subtitle={tr("حسابات المواطنين والموظفين وصلاحياتهم.")}
        actions={<>
          <div className="w-44"><Select placeholder={tr("كل الأدوار")} value={role} onChange={(e) => { setRole(e.target.value); setOffset(0); }} options={ROLE_OPTIONS} aria-label={tr("تصفية بالدور")} /></div>
          <Button icon={UserPlus} onClick={() => setCreating(true)}>{tr("إضافة موظف")}</Button>
        </>} />
      <Card bodyClassName="p-0">
        <AsyncView loading={loading} error={error} onRetry={reload} empty={data?.length === 0} emptyProps={{ title: tr("لا يوجد مستخدمون") }}>
          <Table columns={columns} rows={data ?? []} />
          <Pager offset={offset} limit={LIMIT} count={data?.length ?? 0} onChange={setOffset} />
        </AsyncView>
      </Card>
      <p className="text-xs text-slate-400">{tr("حالة التفعيل غير معروضة لأن الخادم لا يُرجع حقل الحالة؛ استخدم زر التعطيل/التفعيل.")}</p>

      {editing && <EditUserModal user={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); reload(); }} />}
      {creating && <CreateStaffModal onClose={() => setCreating(false)} onSaved={() => { setCreating(false); reload(); }} />}
      <ConfirmDialog open={!!toggle} onClose={() => setToggle(null)} loading={busy} danger={toggle?.deactivated}
        title={toggle?.deactivated ? tr("تعطيل الحساب") : tr("إعادة تفعيل الحساب")}
        message={toggle ? tr(toggle.deactivated ? "سيتم تعطيل حساب «{name}»." : "ستتم إعادة تفعيل حساب «{name}».", { name: toggle.user.name }) : ''}
        confirmLabel={toggle?.deactivated ? tr("تعطيل") : tr("تفعيل")} onConfirm={doToggle} />
    </div>
  );
}

function EditUserModal({ user, onClose, onSaved }) {
  const toast = useToast();
  const [f, setF] = useState({ name: user.name ?? '', email: user.email ?? '', phone: user.phone ?? '' });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));
  const phoneErr = f.phone && validatePhone(f.phone);
  const nameErr = validateName(f.name);

  const save = async () => {
    setBusy(true);
    try {
      const payload = {};
      if (f.name !== user.name) payload.name = f.name.trim();
      if (f.email && f.email !== user.email) payload.email = f.email.trim();
      if (f.phone && f.phone !== user.phone) payload.phone = f.phone.trim();
      if (!Object.keys(payload).length) return onClose();
      await updateUser(user.id, payload);
      toast.success(tr("تم حفظ التعديلات"));
      onSaved();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };

  return (
    <Modal open onClose={onClose} title={tr("تعديل مستخدم")}
      footer={<><Button variant="secondary" onClick={onClose} disabled={busy}>{tr("إلغاء")}</Button><Button onClick={save} loading={busy} disabled={!!nameErr || !!phoneErr}>{tr("حفظ")}</Button></>}>
      <div className="space-y-4">
        <Input label={tr("الاسم")} value={f.name} onChange={set('name')} error={nameErr} />
        <Input label={tr("البريد الإلكتروني")} type="email" dir="ltr" value={f.email} onChange={set('email')} />
        <Input label={tr("رقم الموبايل")} dir="ltr" value={f.phone} onChange={set('phone')} error={phoneErr} />
      </div>
    </Modal>
  );
}

function CreateStaffModal({ onClose, onSaved }) {
  const toast = useToast();
  const [f, setF] = useState({ name: '', email: '', phone: '', password: '', role: 'technician' });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));
  const errs = { name: validateName(f.name), phone: f.phone ? validatePhone(f.phone) : null, password: validatePassword(f.password), email: f.email.includes('@') ? null : tr("بريد إلكتروني غير صالح") };
  const invalid = Object.values(errs).some(Boolean);

  const save = async () => {
    setBusy(true);
    try {
      await createStaff({ name: f.name.trim(), email: f.email.trim(), phone: f.phone || undefined, password: f.password, role: f.role });
      toast.success(tr("تم إنشاء الحساب"));
      onSaved();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };

  return (
    <Modal open onClose={onClose} title={tr("إضافة موظف")}
      footer={<><Button variant="secondary" onClick={onClose} disabled={busy}>{tr("إلغاء")}</Button><Button onClick={save} loading={busy} disabled={invalid}>{tr("إنشاء")}</Button></>}>
      <div className="space-y-4">
        <Input label={tr("الاسم")} required value={f.name} onChange={set('name')} error={f.name && errs.name} />
        <Input label={tr("البريد الإلكتروني")} required type="email" dir="ltr" value={f.email} onChange={set('email')} error={f.email && errs.email} />
        <Input label={tr("رقم الموبايل (اختياري)")} dir="ltr" value={f.phone} onChange={set('phone')} error={errs.phone} />
        <Input label={tr("كلمة المرور")} required type="password" dir="ltr" value={f.password} onChange={set('password')} error={f.password && errs.password} />
        <Select label={tr("الدور")} value={f.role} onChange={set('role')} options={STAFF_ROLES} />
      </div>
    </Modal>
  );
}
