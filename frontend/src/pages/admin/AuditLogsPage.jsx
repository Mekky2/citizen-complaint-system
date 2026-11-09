import { useState } from 'react';
import { Eye, ScrollText } from 'lucide-react';
import { Button, Card, Select, Modal, Table, AsyncView, PageHeader } from '../../components/common';
import Pager from '../../components/common/Pager';
import useFetch from '../../hooks/useFetch';
import { listAuditLogs } from '../../api/admin';
import { formatDateTime, shortId } from '../../utils/format';
import { tr } from '../../i18n';
import { auditAction, auditEntity, AUDIT_ENTITY_TYPES } from '../../utils/audit';

const LIMIT = 25;

// Read-only. Pure reporting — no mutations on this page.
export default function AuditLogsPage() {
  const [entity, setEntity] = useState('');
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(null);
  const { data, loading, error, reload } = useFetch(() => listAuditLogs({ limit: LIMIT, offset, ...(entity.trim() && { entity_type: entity.trim() }) }), [entity, offset]);

  const columns = [
    { key: 'created_at', header: tr("الوقت"), render: (r) => formatDateTime(r.created_at) },
    { key: 'action', header: tr("الإجراء"), render: (r) => <span className="text-sm">{auditAction(r.action)}</span> },
    { key: 'entity_type', header: tr("الكيان"), render: (r) => <span className="text-sm">{auditEntity(r.entity_type)} <span dir="ltr" className="font-mono text-xs text-slate-400">#{shortId(r.entity_id)}</span></span> },
    { key: 'actor_id', header: tr("المنفّذ"), render: (r) => <span dir="ltr" className="font-mono text-xs">{r.actor_id ? shortId(r.actor_id) : tr("النظام")}</span> },
    { key: 'a', header: '', render: (r) => <Button size="sm" variant="ghost" icon={Eye} onClick={() => setOpen(r)} aria-label={tr("التفاصيل")} /> },
  ];

  return (
    <div className="space-y-5">
      <PageHeader icon={ScrollText} title={tr("سجل التدقيق")} subtitle={tr("كل تغيير على النظام، للقراءة فقط.")}
        actions={<div className="w-64"><Select placeholder={tr("كل أنواع الكيانات")} value={entity} options={AUDIT_ENTITY_TYPES.map((v) => ({ value: v, label: auditEntity(v) }))} onChange={(e) => { setEntity(e.target.value); setOffset(0); }} aria-label={tr("تصفية بنوع الكيان")} /></div>} />
      <Card bodyClassName="p-0">
        <AsyncView loading={loading} error={error} onRetry={reload} empty={data?.length === 0} emptyProps={{ title: tr("لا توجد سجلات") }}>
          <Table columns={columns} rows={data ?? []} />
          <Pager offset={offset} limit={LIMIT} count={data?.length ?? 0} onChange={setOffset} />
        </AsyncView>
      </Card>
      <Modal open={!!open} onClose={() => setOpen(null)} title={tr("تفاصيل السجل")} size="lg">
        {open && (
          <div className="space-y-3 text-sm" dir="ltr">
            <Block label="before" value={open.before} />
            <Block label="after" value={open.after} />
          </div>
        )}
      </Modal>
    </div>
  );
}

const Block = ({ label, value }) => (
  <div><p className="mb-1 text-xs font-bold text-slate-400">{label}</p>
    <pre className="overflow-x-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-200">{value ? JSON.stringify(value, null, 2) : 'null'}</pre></div>
);
