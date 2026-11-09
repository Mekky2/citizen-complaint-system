import { tr } from '../i18n';
// Single source of truth for how backend enum values look in the UI.
// Keys mirror app/models/enums.py exactly. Tone drives Badge colour everywhere.

export const TICKET_STATUS = {
  submitted: { label: tr("تم الإرسال"), tone: 'neutral' },
  under_ai_review: { label: tr("قيد المراجعة الآلية"), tone: 'info' },
  awaiting_approval: { label: tr("بانتظار اعتماد المشرف"), tone: 'warn' },
  assigned: { label: tr("تم الإسناد"), tone: 'info' },
  in_progress: { label: tr("قيد التنفيذ"), tone: 'info' },
  pending_verification: { label: tr("بانتظار التحقق"), tone: 'warn' },
  completed: { label: tr("مكتمل"), tone: 'ok' },
  rejected: { label: tr("مرفوض"), tone: 'crit' },
  cancelled: { label: tr("ملغي"), tone: 'neutral' },
};

// Order used by the Status Timeline (happy path). rejected/cancelled are terminal side-branches.
export const TICKET_FLOW = [
  'submitted',
  'under_ai_review',
  'awaiting_approval',
  'assigned',
  'in_progress',
  'pending_verification',
  'completed',
];

export const TASK_STATUS = {
  assigned: { label: tr("مسندة"), tone: 'info' },
  in_progress: { label: tr("قيد التنفيذ"), tone: 'info' },
  pending_verification: { label: tr("بانتظار التحقق"), tone: 'warn' },
  completed: { label: tr("مكتملة"), tone: 'ok' },
};

// `chip` = tinted pill classes ported from the prototype (low emerald / medium amber / high orange / critical red).
export const SEVERITY = {
  low: { label: tr("منخفضة"), tone: 'ok', chip: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40' },
  medium: { label: tr("متوسطة"), tone: 'warn', chip: 'bg-amber-500/15 text-amber-300 border-amber-500/40' },
  high: { label: tr("عالية"), tone: 'high', chip: 'bg-orange-500/15 text-orange-300 border-orange-500/40' },
  critical: { label: tr("حرجة"), tone: 'crit', chip: 'bg-red-500/15 text-red-300 border-red-500/40' },
};

// Accent colour per lifecycle step (same palette as the prototype's timeline) + a hint for the citizen.
export const STEP_COLOR = {
  submitted: '#60a5fa',
  under_ai_review: '#a78bfa',
  awaiting_approval: '#fbbf24',
  assigned: '#38bdf8',
  in_progress: '#fb923c',
  pending_verification: '#facc15',
  completed: '#34d399',
  rejected: '#f87171',
  cancelled: '#94a3b8',
};
export const STEP_HINT = {
  submitted: tr("تم استلام بلاغك وسيدخل المراجعة."),
  under_ai_review: tr("يجري تحليل البلاغ لمساعدة المشرف."),
  awaiting_approval: tr("بانتظار قرار المشرف — لا يتم أي إجراء قبل اعتماده."),
  assigned: tr("تم اعتماد البلاغ وبانتظار إسناده لفريق الصيانة."),
  in_progress: tr("فريق الصيانة يعمل على الإصلاح."),
  pending_verification: tr("تم التنفيذ وبانتظار تحقق المشرف."),
  completed: tr("تم إصلاح المشكلة والتحقق منها."),
  rejected: tr("تم رفض البلاغ."),
  cancelled: tr("تم إلغاء البلاغ."),
};

export const DECISION = {
  approve: { label: tr("اعتماد"), tone: 'ok' },
  edit: { label: tr("اعتماد مع تعديل"), tone: 'info' },
  reject: { label: tr("رفض"), tone: 'crit' },
};

export const ROLE_LABEL = {
  citizen: tr("مواطن"),
  supervisor: tr("مشرف"),
  technician: tr("فني"),
  admin: tr("مدير النظام"),
};

// Backend writes status-history reasons in English; in the Arabic UI the known ones are translated.
// Free text typed by a person (e.g. a supervisor's rejection reason) is shown as written.
import { LANG } from '../i18n';
export function historyReason(r) {
  if (!r || LANG !== 'ar') return r;
  const lbl = (c) => (TICKET_STATUS[c] || TASK_STATUS[c])?.label ?? c;
  let m;
  if (r === 'Ticket created') return 'تم إنشاء البلاغ';
  if ((m = r.match(/^Maintenance task created \(attempt (\d+)\)/))) return `تم إسناد مهمة صيانة (المحاولة ${m[1]})`;
  if ((m = r.match(/^Maintenance task status -> (\w+)/))) return `تغيّرت حالة مهمة الصيانة إلى «${lbl(m[1])}»`;
  if (r === 'AI run triggered') return 'بدأت المراجعة الآلية';
  if (/^AI run failed/.test(r)) return 'تعذّرت المراجعة الآلية';
  if (/^AI recommendation received/.test(r)) return 'وصلت توصية الذكاء الاصطناعي، بانتظار قرار المشرف';
  if (r === 'Verification passed') return 'تم التحقق من الإصلاح بنجاح';
  if ((m = r.match(/^Verification failed \((.*)\) — sent back for rework/))) return `لم ينجح التحقق${m[1] && m[1] !== 'no note' ? ` (${m[1]})` : ''}، وأُعيدت المهمة لإعادة العمل`;
  if ((m = r.match(/^Supervisor (\w+) the AI recommendation/))) return { approved: 'اعتمد المشرف التوصية', edited: 'اعتمد المشرف التوصية بعد تعديلها', rejected: 'رفض المشرف التوصية' }[m[1]] ?? 'قرار المشرف على التوصية';
  return r;
}
