import { Users, Building2, Tags, HardHat, LayoutDashboard, ScrollText } from 'lucide-react';
import { Card, Table, AsyncView, PageHeader, StatTile } from '../../components/common';
import useFetch from '../../hooks/useFetch';
import { listUsers } from '../../api/users';
import { listDepartments, listCategories, listAuditLogs } from '../../api/admin';
import { listTeams } from '../../api/maintenance';
import { formatDateTime, shortId } from '../../utils/format';
import { tr } from '../../i18n';
import { auditAction, auditEntity } from '../../utils/audit';

// Counts come from the real list endpoints (users is capped at the backend's page max of 200).
export default function AdminDashboard() {
  const users = useFetch(() => listUsers({ limit: 200 }), []);
  const deps = useFetch(listDepartments, []);
  const cats = useFetch(listCategories, []);
  const teams = useFetch(() => listTeams(), []);
  const logs = useFetch(() => listAuditLogs({ limit: 8 }), []);
  const n = (f) => (f.loading ? '…' : f.error ? '!' : f.data?.length);

  return (
    <div className="space-y-6">
      <PageHeader icon={LayoutDashboard} title={tr("لوحة التحكم")} subtitle={tr("ملخص المستخدمين والجهات والفرق وآخر العمليات.")} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label={tr("المستخدمون")} value={n(users)} icon={Users} tone="info" />
        <StatTile label={tr("الجهات")} value={n(deps)} icon={Building2} tone="ok" />
        <StatTile label={tr("التصنيفات")} value={n(cats)} icon={Tags} tone="warn" />
        <StatTile label={tr("فرق الصيانة")} value={n(teams)} icon={HardHat} />
      </div>
      <Card title={tr("آخر العمليات")} icon={ScrollText} bodyClassName="p-0">
        <AsyncView loading={logs.loading} error={logs.error} onRetry={logs.reload} empty={logs.data?.length === 0} emptyProps={{ title: tr("لا توجد عمليات مسجلة") }}>
          <Table rows={logs.data ?? []} columns={[
            { key: 't', header: tr("الوقت"), render: (r) => formatDateTime(r.created_at) },
            { key: 'a', header: tr("الإجراء"), render: (r) => <span className="text-sm">{auditAction(r.action)}</span> },
            { key: 'e', header: tr("الكيان"), render: (r) => <span className="text-sm">{auditEntity(r.entity_type)} <span dir="ltr" className="font-mono text-xs text-slate-400">#{shortId(r.entity_id)}</span></span> },
          ]} />
        </AsyncView>
      </Card>
    </div>
  );
}
