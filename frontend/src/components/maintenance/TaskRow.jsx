import { Link } from 'react-router-dom';
import { ChevronLeft } from 'lucide-react';
import { TaskStatusBadge } from '../common';
import useFetch from '../../hooks/useFetch';
import { getTicket } from '../../api/tickets';
import { ticketRef, timeAgo } from '../../utils/format';
import { tr } from '../../i18n';

// A task only carries ticket_id; the title comes from the ticket itself (technicians may read tickets).
export default function TaskRow({ task }) {
  const { data: ticket } = useFetch(() => getTicket(task.ticket_id), [task.ticket_id]);
  return (
    <li>
      <Link to={`/technician/tasks/${task.id}`} className="flex items-center gap-3 px-5 py-4 transition hover:bg-slate-700/40">
        <div className="min-w-0 flex-1">
          <p className="truncate font-bold text-slate-100">{ticket ? ticket.title || ticket.description : '…'}</p>
          <p className="mt-0.5 text-xs text-slate-400">
            <span dir="ltr" className="font-mono text-blue-300">{ticketRef(task.ticket_id, ticket?.created_at)}</span> {tr("· محاولة")} {task.attempt_number} · {timeAgo(task.assigned_at)}
          </p>
        </div>
        <TaskStatusBadge value={task.status} />
        <ChevronLeft className="h-4 w-4 shrink-0 text-slate-400 ltr:rotate-180" aria-hidden />
      </Link>
    </li>
  );
}
