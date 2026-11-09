import { useNavigate, Link } from 'react-router-dom';
import { Cpu, Gavel, Wrench, ShieldCheck, Inbox, Radar, Map as MapIcon, ListOrdered } from 'lucide-react';
import { Card, AsyncView, TicketStatusBadge, SeverityBadge, StatTile, PageHeader } from '../../components/common';
import MapView from '../../components/common/MapView';
import useFetch from '../../hooks/useFetch';
import { listTickets } from '../../api/tickets';
import { ACTIVE_TICKET, ticketRef, timeAgo } from '../../utils/format';
import { tr } from '../../i18n';

// KPIs are computed client-side from GET /tickets (supervisors receive all tickets).
export default function OperationsDashboard() {
  const nav = useNavigate();
  const { data, loading, error, reload } = useFetch(() => listTickets({ limit: 200 }), [], { pollMs: 30000 });
  const tickets = data ?? [];
  const count = (...s) => tickets.filter((t) => s.includes(t.status)).length;
  const active = tickets.filter((t) => ACTIVE_TICKET(t.status));
  const queue = tickets.filter((t) => ['awaiting_approval', 'submitted'].includes(t.status))
    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

  return (
    <div className="space-y-6">
      <PageHeader icon={Radar} title={tr("غرفة العمليات")} subtitle={tr("نظرة حيّة على البلاغات وما ينتظر قرارك.")} />
      <AsyncView loading={loading} error={error} onRetry={reload}>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile label={tr("جديدة — تحتاج تحليلًا")} value={count('submitted')} icon={Inbox} tone="info" />
          <StatTile label={tr("بانتظار اعتمادك")} value={count('awaiting_approval')} icon={Gavel} tone="warn" />
          <StatTile label={tr("قيد التنفيذ")} value={count('assigned', 'in_progress')} icon={Wrench} tone="info" />
          <StatTile label={tr("بانتظار التحقق")} value={count('pending_verification')} icon={ShieldCheck} tone="ok" />
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Card title={tr("خريطة البلاغات النشطة")} icon={MapIcon} subtitle={tr("{p0} بلاغ نشط", { p0: active.length })}>
            <MapView height={360} zoom={11}
              markers={active.map((t) => ({ id: t.id, position: [t.lat, t.lng], onClick: () => nav(`/supervisor/incidents/${t.id}`) }))} />
          </Card>

          <Card title={tr("قائمة الأولويات")} icon={ListOrdered} subtitle={tr("الأقدم أولًا")} bodyClassName="p-0">
            {queue.length === 0 ? (
              <p className="px-5 py-10 text-center text-sm text-slate-400">{tr("لا توجد بلاغات تنتظر إجراءً منك.")}</p>
            ) : (
              <ul className="max-h-[360px] divide-y divide-slate-700/70 overflow-y-auto">
                {queue.map((t) => (
                  <li key={t.id}>
                    <Link to={`/supervisor/incidents/${t.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-700/40">
                      <Cpu className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-bold text-slate-100">{t.title || t.description}</p>
                        <p className="text-xs text-slate-400"><span dir="ltr" className="font-mono text-blue-300">{ticketRef(t.id, t.created_at)}</span> · {timeAgo(t.created_at)}</p>
                      </div>
                      {t.severity && <SeverityBadge value={t.severity} />}
                      <TicketStatusBadge value={t.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </AsyncView>
    </div>
  );
}
