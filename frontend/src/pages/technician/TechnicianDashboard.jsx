import { Link } from 'react-router-dom';
import { ClipboardList, PlayCircle, ShieldCheck, LayoutDashboard, Wrench } from 'lucide-react';
import { Card, AsyncView, PageHeader, StatTile } from '../../components/common';
import TaskRow from '../../components/maintenance/TaskRow';
import useFetch from '../../hooks/useFetch';
import { listMyTasks } from '../../api/maintenance';
import { useAuth } from '../../context/AuthContext';
import { tr } from '../../i18n';

export default function TechnicianDashboard() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useFetch(listMyTasks, [], { pollMs: 30000 });
  const tasks = data ?? [];
  const n = (s) => tasks.filter((t) => t.status === s).length;
  const open = tasks.filter((t) => t.status !== 'completed');

  return (
    <div className="space-y-6">
      <PageHeader icon={LayoutDashboard} title={tr("أهلاً {p0}", { p0: user?.name ?? '' })} subtitle={tr("مهام فريقك الحالية.")} />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatTile label={tr("مسندة")} value={loading ? '…' : n('assigned')} icon={ClipboardList} tone="info" />
        <StatTile label={tr("قيد التنفيذ")} value={loading ? '…' : n('in_progress')} tone="info" icon={PlayCircle} />
        <StatTile label={tr("بانتظار التحقق")} value={loading ? '…' : n('pending_verification')} tone="warn" icon={ShieldCheck} />
      </div>
      <Card title={tr("مهام تحتاج عملًا")} icon={Wrench} actions={<Link to="/technician/tasks" className="text-sm font-bold text-blue-300 hover:underline">{tr("كل المهام")}</Link>} bodyClassName="p-0">
        <AsyncView loading={loading} error={error} onRetry={reload} empty={open.length === 0} emptyProps={{ title: tr("لا توجد مهام حاليًا") }}>
          <ul className="divide-y divide-slate-700/70">{open.slice(0, 6).map((t) => <TaskRow key={t.id} task={t} />)}</ul>
        </AsyncView>
      </Card>
    </div>
  );
}
