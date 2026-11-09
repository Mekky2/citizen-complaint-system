import { Link } from 'react-router-dom';
import { BellRing, CheckCheck } from 'lucide-react';
import { Card, AsyncView, Button, PageHeader, useToast } from '../../components/common';
import useFetch from '../../hooks/useFetch';
import { listNotifications, markRead } from '../../api/notifications';
import { errorMessage } from '../../utils/errors';
import { timeAgo, formatDateTime } from '../../utils/format';
import { cn } from '../../utils/cn';
import { tr } from '../../i18n';

// Shared by all four roles. `ticketPath(ticketId)` builds the role-specific link to a ticket (optional).
export default function NotificationsPage({ ticketPath }) {
  const toast = useToast();
  const { data, loading, error, reload } = useFetch(() => listNotifications({ limit: 100 }), [], { pollMs: 30000 });

  const read = async (n) => {
    try { await markRead(n.id); window.dispatchEvent(new Event('notifications:changed')); reload(); } catch (e) { toast.error(errorMessage(e)); }
  };

  return (
    <div className="space-y-5">
      <PageHeader icon={BellRing} title={tr("الإشعارات")} subtitle={tr("تحديثات بلاغاتك ومهامك فور حدوثها.")} />
      <Card bodyClassName="p-0">
        <AsyncView loading={loading} error={error} onRetry={reload} empty={data?.length === 0}
          emptyProps={{ title: tr("لا توجد إشعارات"), icon: BellRing }}>
          <ul className="divide-y divide-slate-700/70">
            {data?.map((n) => (
              <li key={n.id} className={cn('flex items-start gap-3 border-s-4 px-4 py-3.5', n.read_at ? 'border-transparent' : 'border-blue-500 bg-blue-500/10')}>
                <span className={cn('mt-2 h-2 w-2 shrink-0 rounded-full', n.read_at ? 'bg-slate-600' : 'bg-blue-400')} aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-slate-50">{n.title}</p>
                  {n.body && <p className="text-sm text-slate-300">{n.body}</p>}
                  <p className="mt-1 text-xs text-slate-400" title={formatDateTime(n.created_at)}>{timeAgo(n.created_at)}</p>
                  {n.ticket_id && ticketPath && <Link to={ticketPath(n.ticket_id)} className="mt-1 inline-block text-xs font-bold text-blue-300 hover:underline">{tr("عرض البلاغ")}</Link>}
                </div>
                {!n.read_at && <Button size="sm" variant="ghost" icon={CheckCheck} onClick={() => read(n)}>{tr("تمت القراءة")}</Button>}
              </li>
            ))}
          </ul>
        </AsyncView>
      </Card>
    </div>
  );
}
