import { useState } from 'react';
import { Link, Outlet, useMatch, useNavigate } from 'react-router-dom';
import { ArrowRight, Siren } from 'lucide-react';
import { Card, Select, AsyncView, EmptyState, TicketStatusBadge, SeverityBadge } from '../../components/common';
import useFetch from '../../hooks/useFetch';
import { listTickets } from '../../api/tickets';
import { TICKET_STATUS } from '../../utils/status';
import { ticketRef, timeAgo } from '../../utils/format';
import { cn } from '../../utils/cn';
import { tr } from '../../i18n';

const STATUS_OPTIONS = Object.entries(TICKET_STATUS).map(([value, { label }]) => ({ value, label }));

// Two-pane Operations Room: list on one side, workspace for the selected ticket on the other.
// On small screens only one pane shows at a time, so nothing is hidden — just stacked.
export default function IncidentsPage() {
  const [status, setStatus] = useState('');
  const match = useMatch('/supervisor/incidents/:id');
  const selected = match?.params.id;
  const nav = useNavigate();
  const { data, loading, error, reload } = useFetch(() => listTickets({ limit: 200, ...(status && { status }) }), [status], { pollMs: 30000 });

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[380px_minmax(0,1fr)]">
      <div className={cn(selected && 'hidden lg:block')}>
        <Card title={tr("البلاغات")} icon={Siren} actions={<div className="w-40"><Select placeholder={tr("كل الحالات")} value={status} onChange={(e) => setStatus(e.target.value)} options={STATUS_OPTIONS} aria-label={tr("تصفية بالحالة")} /></div>} bodyClassName="p-0">
          <AsyncView loading={loading} error={error} onRetry={reload} empty={data?.length === 0} emptyProps={{ title: tr("لا توجد بلاغات"), icon: Siren }}>
            <ul className="max-h-[calc(100vh-14rem)] divide-y divide-slate-700/70 overflow-y-auto">
              {data?.map((t) => (
                <li key={t.id}>
                  <button onClick={() => nav(`/supervisor/incidents/${t.id}`)} aria-current={selected === t.id} className={cn('w-full border-s-4 px-4 py-3 text-start transition hover:bg-slate-700/40', selected === t.id ? 'border-blue-500 bg-blue-500/10' : 'border-transparent')}>
                    <p className="truncate text-sm font-bold text-slate-100">{t.title || t.description}</p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-2">
                      <TicketStatusBadge value={t.status} />
                      {t.severity && <SeverityBadge value={t.severity} />}
                      <span className="text-xs text-slate-400"><span dir="ltr" className="font-mono text-blue-300">{ticketRef(t.id, t.created_at)}</span> · {timeAgo(t.created_at)}</span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </AsyncView>
        </Card>
      </div>

      <div className={cn(!selected && 'hidden lg:block')}>
        {selected ? (
          <div className="space-y-3">
            <Link to="/supervisor/incidents" className="inline-flex items-center gap-1 text-sm font-semibold text-slate-300 hover:text-white lg:hidden"><ArrowRight className="h-4 w-4 ltr:rotate-180" />{tr("كل البلاغات")}</Link>
            <Outlet />
          </div>
        ) : (
          <Card><EmptyState title={tr("اختر بلاغًا من القائمة")} description={tr("ستظهر هنا تفاصيله وتوصية الذكاء الاصطناعي وخيارات القرار.")} icon={Siren} /></Card>
        )}
      </div>
    </div>
  );
}
