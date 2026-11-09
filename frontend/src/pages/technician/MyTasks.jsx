import { Wrench } from 'lucide-react';
import { Card, AsyncView, PageHeader } from '../../components/common';
import TaskRow from '../../components/maintenance/TaskRow';
import useFetch from '../../hooks/useFetch';
import { listMyTasks } from '../../api/maintenance';
import { tr } from '../../i18n';

// GET /maintenance/tasks/mine is scoped by the backend to teams this technician actually belongs to.
export default function MyTasks() {
  const { data, loading, error, reload } = useFetch(listMyTasks, [], { pollMs: 30000 });
  const tasks = [...(data ?? [])].sort((a, b) => new Date(b.assigned_at) - new Date(a.assigned_at));
  return (
    <div className="space-y-5">
      <PageHeader icon={Wrench} title={tr("مهامي")} subtitle={tr("المهام المسندة لفريقك، الأحدث أولًا.")} />
      <Card bodyClassName="p-0">
        <AsyncView loading={loading} error={error} onRetry={reload} empty={tasks.length === 0} emptyProps={{ title: tr("لا توجد مهام مسندة لفريقك") }}>
          <ul className="divide-y divide-slate-700/70">{tasks.map((t) => <TaskRow key={t.id} task={t} />)}</ul>
        </AsyncView>
      </Card>
    </div>
  );
}
