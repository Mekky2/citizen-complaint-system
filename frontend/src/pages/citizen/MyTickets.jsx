import { useState } from 'react';
import { Link } from 'react-router-dom';
import { FilePlus2, ListChecks } from 'lucide-react';
import { Button, Card, Select, AsyncView, PageHeader } from '../../components/common';
import TicketList from '../../components/tickets/TicketList';
import useFetch from '../../hooks/useFetch';
import { listTickets } from '../../api/tickets';
import { TICKET_STATUS } from '../../utils/status';
import { tr } from '../../i18n';

const STATUS_OPTIONS = Object.entries(TICKET_STATUS).map(([value, { label }]) => ({ value, label }));

export default function MyTickets() {
  const [status, setStatus] = useState('');
  const { data, loading, error, reload } = useFetch(() => listTickets({ limit: 200, ...(status && { status }) }), [status]);

  return (
    <div className="space-y-5">
      <PageHeader icon={ListChecks} title={tr("بلاغاتي")} subtitle={tr("كل البلاغات التي قدّمتها وحالة كل منها.")}
        actions={<div className="w-56"><Select placeholder={tr("كل الحالات")} value={status} onChange={(e) => setStatus(e.target.value)} options={STATUS_OPTIONS} aria-label={tr("تصفية بالحالة")} /></div>} />
      <Card bodyClassName="p-0">
        <AsyncView loading={loading} error={error} onRetry={reload} empty={data?.length === 0}
          emptyProps={{
            title: status ? tr("لا توجد بلاغات بهذه الحالة") : tr("لا توجد بلاغات حتى الآن"),
            action: !status && <Link to="/citizen/new"><Button icon={FilePlus2} size="sm">{tr("تقديم بلاغ")}</Button></Link>,
          }}>
          <TicketList tickets={data ?? []} basePath="/citizen/tickets" />
        </AsyncView>
      </Card>
    </div>
  );
}
