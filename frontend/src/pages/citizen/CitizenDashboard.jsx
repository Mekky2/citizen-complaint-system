import { Link } from 'react-router-dom';
import { FilePlus2, ListChecks, Hourglass, CheckCircle2, LayoutDashboard } from 'lucide-react';
import { Button, Card, AsyncView, PageHeader, StatTile } from '../../components/common';
import TicketList from '../../components/tickets/TicketList';
import useFetch from '../../hooks/useFetch';
import { listTickets } from '../../api/tickets';
import { useAuth } from '../../context/AuthContext';
import { ACTIVE_TICKET } from '../../utils/format';
import { tr } from '../../i18n';

// KPIs are computed client-side from GET /tickets (already scoped to the signed-in citizen by the backend).
export default function CitizenDashboard() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useFetch(() => listTickets({ limit: 200 }), [], { pollMs: 30000 });
  const tickets = data ?? [];
  const active = tickets.filter((t) => ACTIVE_TICKET(t.status)).length;
  const done = tickets.filter((t) => t.status === 'completed').length;

  return (
    <div className="space-y-6">
      <PageHeader icon={LayoutDashboard} title={tr("أهلاً {p0}", { p0: user?.name ?? '' })} subtitle={tr("تابع بلاغاتك أو قدّم بلاغًا جديدًا.")}
        actions={<Link to="/citizen/new"><Button icon={FilePlus2}>{tr("بلاغ جديد")}</Button></Link>} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatTile label={tr("كل البلاغات")} value={loading ? '…' : tickets.length} icon={ListChecks} tone="info" />
        <StatTile label={tr("قيد المعالجة")} value={loading ? '…' : active} tone="warn" icon={Hourglass} />
        <StatTile label={tr("مكتملة")} value={loading ? '…' : done} tone="ok" icon={CheckCircle2} />
      </div>

      <Card title={tr("آخر البلاغات")} icon={ListChecks} actions={<Link to="/citizen/tickets" className="text-sm font-bold text-blue-300 hover:underline">{tr("عرض الكل")}</Link>} bodyClassName="p-0">
        <AsyncView loading={loading} error={error} onRetry={reload} empty={tickets.length === 0}
          emptyProps={{ title: tr("لا توجد بلاغات حتى الآن"), description: tr("ابدأ بتقديم أول بلاغ لك."), action: <Link to="/citizen/new"><Button size="sm" icon={FilePlus2}>{tr("تقديم بلاغ")}</Button></Link> }}>
          <TicketList tickets={tickets.slice(0, 5)} basePath="/citizen/tickets" />
        </AsyncView>
      </Card>
    </div>
  );
}
