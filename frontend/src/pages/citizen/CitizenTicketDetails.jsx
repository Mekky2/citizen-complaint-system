import { Link, useParams } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { AsyncView, Card } from '../../components/common';
import TicketSummary from '../../components/tickets/TicketSummary';
import useFetch from '../../hooks/useFetch';
import { getTicket } from '../../api/tickets';
import { tr } from '../../i18n';

// The citizen sees the ticket and its real lifecycle. AI analysis is never shown to citizens:
// it is a supervisor-side recommendation until a human decides (see design proposal, architecture note).
export default function CitizenTicketDetails() {
  const { id } = useParams();
  const { data, loading, error, reload } = useFetch(() => getTicket(id), [id]);

  return (
    <div className="space-y-4">
      <Link to="/citizen/tickets" className="inline-flex items-center gap-1 text-sm font-semibold text-slate-300 hover:text-white"><ArrowRight className="h-4 w-4 ltr:rotate-180" />{tr("بلاغاتي")}</Link>
      <AsyncView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <TicketSummary ticket={data} />
            {data.status === 'awaiting_approval' && (
              <Card><p className="text-sm text-slate-300">{tr("بلاغك قيد مراجعة المشرف. لن يتم اتخاذ أي إجراء إلا بعد اعتماده.")}</p></Card>
            )}
          </>
        )}
      </AsyncView>
    </div>
  );
}
