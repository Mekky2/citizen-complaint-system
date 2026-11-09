import { useMemo, useState } from 'react';
import { Plus, Tags } from 'lucide-react';
import { Button, Card, Input, Modal, Select, Table, AsyncView, PageHeader, useToast } from '../../components/common';
import useFetch from '../../hooks/useFetch';
import { listCategories, listDepartments, createCategory } from '../../api/admin';
import { errorMessage } from '../../utils/errors';
import { tr } from '../../i18n';

export default function CategoriesPage() {
  const toast = useToast();
  const cats = useFetch(listCategories, []);
  const deps = useFetch(listDepartments, []);
  const depName = useMemo(() => Object.fromEntries((deps.data ?? []).map((d) => [d.id, d.name])), [deps.data]);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ name: '', default_department_id: '' });
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      await createCategory({ name: f.name.trim(), default_department_id: f.default_department_id || undefined });
      toast.success(tr("تمت إضافة التصنيف"));
      setOpen(false); setF({ name: '', default_department_id: '' }); cats.reload();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-5">
      <PageHeader icon={Tags} title={tr("التصنيفات")} subtitle={tr("تصنيفات البلاغات والجهة الافتراضية لكل منها.")} actions={<Button icon={Plus} onClick={() => setOpen(true)}>{tr("إضافة تصنيف")}</Button>} />
      <Card bodyClassName="p-0">
        <AsyncView loading={cats.loading} error={cats.error} onRetry={cats.reload} empty={cats.data?.length === 0} emptyProps={{ title: tr("لا توجد تصنيفات بعد") }}>
          <Table columns={[{ key: 'name', header: tr("التصنيف"), render: (c) => <span className="font-bold text-slate-100">{c.name}</span> }, { key: 'dep', header: tr("الجهة الافتراضية"), render: (c) => depName[c.default_department_id] ?? '—' }]} rows={cats.data ?? []} />
        </AsyncView>
      </Card>
      <Modal open={open} onClose={() => setOpen(false)} title={tr("إضافة تصنيف")}
        footer={<><Button variant="secondary" onClick={() => setOpen(false)} disabled={busy}>{tr("إلغاء")}</Button><Button onClick={save} loading={busy} disabled={f.name.trim().length < 2}>{tr("حفظ")}</Button></>}>
        <div className="space-y-4">
          <Input label={tr("اسم التصنيف")} required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
          <Select label={tr("الجهة الافتراضية (اختياري)")} placeholder={tr("بدون")} value={f.default_department_id} onChange={(e) => setF({ ...f, default_department_id: e.target.value })} options={(deps.data ?? []).map((d) => ({ value: d.id, label: d.name }))} />
        </div>
      </Modal>
    </div>
  );
}
