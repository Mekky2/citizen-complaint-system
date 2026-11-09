import { LANG, LOCALE, tr } from '../i18n';

// Western digits in Arabic locale — consistent with Arabic government UIs and easier to scan in tables.
const dt = new Intl.DateTimeFormat(LOCALE, { dateStyle: 'medium', timeStyle: 'short' });
const d = new Intl.DateTimeFormat(LOCALE, { dateStyle: 'medium' });

export const formatDateTime = (v) => (v ? dt.format(new Date(v)) : '—');
export const formatDate = (v) => (v ? d.format(new Date(v)) : '—');
export const shortId = (id) => (id ? String(id).slice(0, 8) : '—');
export const ACTIVE_TICKET = (s) => !['completed', 'rejected', 'cancelled'].includes(s);

// Human-friendly ticket number shown to citizens: EG-<year>-<first 6 hex of the id>.
export const ticketRef = (id, createdAt) => (id ? `EG-${createdAt ? new Date(createdAt).getFullYear() : new Date().getFullYear()}-${String(id).replace(/-/g, '').slice(0, 6).toUpperCase()}` : '—');

const rtf = new Intl.RelativeTimeFormat(LANG === 'ar' ? 'ar-u-nu-latn' : 'en', { numeric: 'auto' });
export function timeAgo(v) {
  if (!v) return '—';
  const diff = (new Date(v).getTime() - Date.now()) / 1000;
  const a = Math.abs(diff);
  if (a < 60) return tr("الآن");
  if (a < 3600) return rtf.format(Math.round(diff / 60), 'minute');
  if (a < 86400) return rtf.format(Math.round(diff / 3600), 'hour');
  return rtf.format(Math.round(diff / 86400), 'day');
}
