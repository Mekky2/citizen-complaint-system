import { useState } from 'react';
import { Plus, Building2 } from 'lucide-react';
import { Button, Card, Input, Modal, Table, AsyncView, PageHeader, useToast } from '../../components/common';
import useFetch from '../../hooks/useFetch';
import { listDepartments, createDepartment } from '../../api/admin';
import { errorMessage } from '../../utils/errors';
import { tr } from '../../i18n';

export default function DepartmentsPage() {
  const toast = useToast();
  const { data, loading, error, reload } = useFetch(listDepartments, []);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ name: '', description: '' });
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      await createDepartment({ name: f.name.trim(), description: f.description.trim() || undefined });
      toast.success(tr("تمت إضافة الجهة"));
      setOpen(false); setF({ name: '', description: '' }); reload();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-5">
      <PageHeader icon={Building2} title={tr("الجهات")} subtitle={tr("الجهات الحكومية التي تستقبل البلاغات.")} actions={<Button icon={Plus} onClick={() => setOpen(true)}>{tr("إضافة جهة")}</Button>} />
      <Card bodyClassName="p-0">
        <AsyncView loading={loading} error={error} onRetry={reload} empty={data?.length === 0} emptyProps={{ title: tr("لا توجد جهات بعد") }}>
          <Table columns={[{ key: 'name', header: tr("الجهة"), render: (d) => <span className="font-bold text-slate-100">{d.name}</span> }, { key: 'description', header: tr("الوصف"), render: (d) => d.description ?? '—' }]} rows={data ?? []} />
        </AsyncView>
      </Card>
      <Modal open={open} onClose={() => setOpen(false)} title={tr("إضافة جهة")}
        footer={<><Button variant="secondary" onClick={() => setOpen(false)} disabled={busy}>{tr("إلغاء")}</Button><Button onClick={save} loading={busy} disabled={f.name.trim().length < 2}>{tr("حفظ")}</Button></>}>
        <div className="space-y-4">
          <Input label={tr("اسم الجهة")} required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
          <Input label={tr("الوصف (اختياري)")} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
        </div>
      </Modal>
    </div>
  );
}
