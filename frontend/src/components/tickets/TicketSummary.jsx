
import { Clock, FileText, Image as ImageIcon, MapPin, History } from 'lucide-react';
import { Card, TicketStatusBadge, SeverityBadge, StatusTimeline, CopyButton } from '../common';
import MapView from '../common/MapView';
import { TICKET_STATUS, historyReason } from '../../utils/status';
import { formatDateTime, shortId, ticketRef } from '../../utils/format';
import { tr } from '../../i18n';
import MediaAttachment from './MediaAttachment';

// Read-only view of a TicketDetailOut. Used by Citizen and Supervisor detail pages.
// Shows ONLY what the backend returned — nothing is derived or simulated.
export default function TicketSummary({ ticket, showCitizenId = false }) {
  const t = ticket;

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs text-slate-400">
              {tr("بلاغ رقم")} <span dir="ltr" className="font-mono text-blue-300">{ticketRef(t.id, t.created_at)}</span>
            </p>
            <h1 className="text-2xl font-extrabold text-slate-50">
              {t.title || tr("بلاغ بدون عنوان")}
            </h1>
            <div className="mt-1">
              <CopyButton text={ticketRef(t.id, t.created_at)} />
            </div>
          </div>

          <div className="flex items-center gap-2">
            {t.severity && <SeverityBadge value={t.severity} />}
            <TicketStatusBadge value={t.status} />
          </div>
        </div>

        <div className="mt-5">
          <StatusTimeline current={t.status} hints={!showCitizenId} />
        </div>
      </Card>

      <Card title={tr("تفاصيل البلاغ")} icon={FileText}>
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">
          {t.description}
        </p>

        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <Row k={tr("تاريخ الإرسال")} v={formatDateTime(t.created_at)} />
          <Row k={tr("آخر تحديث")} v={formatDateTime(t.updated_at)} />
          <Row k={tr("العنوان")} v={t.address} />
          <Row
            k={tr("المحافظة / المدينة")}
            v={[t.governorate, t.city].filter(Boolean).join(' — ')}
          />
          {showCitizenId && (
            <Row
              k={tr("معرّف مقدّم البلاغ")}
              v={
                <span dir="ltr" className="font-mono">
                  {shortId(t.citizen_id)}
                </span>
              }
            />
          )}
        </dl>
      </Card>

      <Card title={tr("الموقع")} icon={MapPin}>
        <MapView position={[t.lat, t.lng]} height={240} />
      </Card>

      {t.media?.length > 0 && (
        <Card title={tr("المرفقات")} icon={ImageIcon}>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {t.media.map((m) => (
              <li
                key={m.id}
                className="overflow-hidden rounded-xl border border-slate-600 bg-slate-900"
              >
                <MediaAttachment media={m} />
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card title={tr("سجل الحالة")} icon={History}>
        {t.status_history?.length ? (
          <ol className="space-y-3">
            {[...t.status_history].reverse().map((h) => (
              <li key={h.id} className="flex gap-3 text-sm">
                <span
                  className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-blue-600"
                  aria-hidden
                />
                <div>
                  <p className="font-semibold text-slate-100">
                    {TICKET_STATUS[h.to_status]?.label ?? h.to_status}
                  </p>
                  {h.reason && (
                    <p className="text-slate-300">{historyReason(h.reason)}</p>
                  )}
                  <p className="text-xs text-slate-400">
                    {formatDateTime(h.created_at)}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-slate-400">{tr("لا يوجد سجل بعد.")}</p>
        )}
      </Card>
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div>
      <dt className="text-xs text-slate-400">{k}</dt>
      <dd className="font-semibold text-slate-100">{v || '—'}</dd>
    </div>
  );
}
