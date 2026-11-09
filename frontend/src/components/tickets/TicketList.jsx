import { Link } from 'react-router-dom';
import { ChevronLeft, MapPin } from 'lucide-react';
import { TicketStatusBadge, SeverityBadge, StatusTimeline } from '../common';
import { formatDate, ticketRef, timeAgo } from '../../utils/format';

// Card rows (mobile friendly): title, ref + place, badges and a thin coloured progress strip.
// `basePath` is the role's tickets route, e.g. '/citizen/tickets'.
export default function TicketList({ tickets, basePath }) {
  return (
    <ul className="divide-y divide-slate-700/70">
      {tickets.map((t) => (
        <li key={t.id}>
          <Link to={`${basePath}/${t.id}`} className="block px-5 py-4 transition hover:bg-slate-700/40">
            <div className="flex items-center gap-3">
              <div className="min-w-0 flex-1">
                <p className="truncate font-bold text-slate-100">{t.title || t.description}</p>
                <p className="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-slate-400">
                  <span dir="ltr" className="font-mono text-blue-300">{ticketRef(t.id, t.created_at)}</span>
                  <span title={formatDate(t.created_at)}>{timeAgo(t.created_at)}</span>
                  {(t.address || t.city) && <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3" aria-hidden />{t.address || t.city}</span>}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
                {t.severity && <SeverityBadge value={t.severity} />}
                <TicketStatusBadge value={t.status} />
              </div>
              <ChevronLeft className="h-4 w-4 shrink-0 text-slate-500 ltr:rotate-180" aria-hidden />
            </div>
            <div className="mt-3"><StatusTimeline current={t.status} compact /></div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
