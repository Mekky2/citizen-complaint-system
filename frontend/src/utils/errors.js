import { tr, LANG } from '../i18n';
import { TICKET_STATUS, TASK_STATUS } from './status';

// The backend answers in English. In Arabic mode every known message is mapped to Arabic here;
// an unknown English message is replaced by a generic Arabic sentence instead of leaking English into the UI.
const EXACT = {
  'Account is deactivated': tr("هذا الحساب معطّل. تواصل مع مسؤول النظام."),
  'An account with this email or phone already exists': tr("يوجد حساب بنفس البريد الإلكتروني أو رقم الموبايل."),
  'An account with this phone, email, or national ID already exists': tr("يوجد حساب بنفس رقم الموبايل أو البريد الإلكتروني أو الرقم القومي."),
  'Category already exists': tr("هذه الفئة موجودة بالفعل."),
  'Department already exists': tr("هذه الجهة موجودة بالفعل."),
  'Could not validate credentials': tr("انتهت الجلسة. سجّل الدخول مرة أخرى."),
  'Invalid credentials': tr("بيانات الدخول غير صحيحة."),
  'Invalid refresh token': tr("انتهت الجلسة. سجّل الدخول مرة أخرى."),
  'Invalid or missing AI service credentials': tr("تعذّر التحقق من خدمة الذكاء الاصطناعي."),
  'Maintenance task not found': tr("المهمة غير موجودة."),
  'Maintenance team not found': tr("فريق الصيانة غير موجود."),
  'Not authorized for this task': tr("غير مصرّح لك بهذه المهمة."),
  'Notification not found': tr("الإشعار غير موجود."),
  "Only users with the 'technician' role can be added to a maintenance team": tr("يمكن إضافة الفنيين فقط إلى فرق الصيانة."),
  'This is not your ticket': tr("هذا البلاغ ليس بلاغك."),
  'Ticket not found': tr("البلاغ غير موجود."),
  'User has no assigned role': tr("لا يوجد دور مرتبط بهذا الحساب."),
  'User is already a member of this team': tr("هذا الفني عضو بالفعل في الفريق."),
  'User not found': tr("المستخدم غير موجود."),
  'You are not a member of the maintenance team assigned to this task': tr("لست عضوًا في فريق الصيانة المكلّف بهذه المهمة."),
  'default_department_id not found': tr("الجهة الافتراضية غير موجودة."),
  'Not Found': tr("الطلب غير موجود."),
  'Method Not Allowed': tr("هذه العملية غير متاحة حاليًا."),
  'Forbidden': tr("لا تملك صلاحية تنفيذ هذا الإجراء."),
  'Not authenticated': tr("سجّل الدخول للمتابعة."),
  'reason is required when rejecting an AI recommendation': tr("سبب الرفض مطلوب عند رفض توصية الذكاء الاصطناعي."),
  'national_id must be exactly 14 digits': tr("الرقم القومي يجب أن يكون 14 رقمًا."),
  'lat must be between -90 and 90': tr("خط العرض غير صحيح."),
  'lng must be between -180 and 180': tr("خط الطول غير صحيح."),
};
const FIELD = {
  name: tr("الاسم"), phone: tr("رقم الموبايل"), national_id: tr("الرقم القومي"), email: tr("البريد الإلكتروني"),
  password: tr("كلمة المرور"), identifier: tr("رقم الموبايل أو البريد"), title: tr("العنوان"), description: tr("الوصف"),
  lat: tr("الموقع"), lng: tr("الموقع"), address: tr("العنوان"), reason: tr("السبب"), role: tr("الدور"), notes: tr("الملاحظات"),
};
const statusLabel = (code) => (TICKET_STATUS[code] || TASK_STATUS[code])?.label ?? code;

function translateDetail(msg) {
  if (LANG !== 'ar') return msg;
  const clean = msg.replace(/^Value error, /, '');
  if (EXACT[clean]) return EXACT[clean];
  let m;
  if ((m = clean.match(/^phone must be a valid Egyptian mobile number/))) return tr("رقم الموبايل غير صحيح، مثال: 01012345678");
  if ((m = clean.match(/^role must be one of/))) return tr("الدور غير صحيح.");
  if ((m = clean.match(/^Ticket is '(\w+)', not 'awaiting_approval'/))) return tr("حالة البلاغ الحالية «{s}» ولا يوجد قرار معلّق.", { s: statusLabel(m[1]) });
  if ((m = clean.match(/^Ticket is '(\w+)', not 'assigned'/))) return tr("لا يمكن إسناد مهمة والبلاغ في حالة «{s}».", { s: statusLabel(m[1]) });
  if ((m = clean.match(/^Ticket is '(\w+)', not 'submitted'/))) return tr("لا يمكن بدء المراجعة الآلية والبلاغ في حالة «{s}».", { s: statusLabel(m[1]) });
  if ((m = clean.match(/^Task is '(\w+)', not 'pending_verification'/))) return tr("المهمة في حالة «{s}» وليست بانتظار التحقق.", { s: statusLabel(m[1]) });
  if (/^This action requires one of roles/.test(clean)) return tr("لا تملك صلاحية تنفيذ هذا الإجراء.");
  if (/^Role '.*' is not seeded/.test(clean)) return tr("الدور غير معرّف في النظام.");
  // Pydantic default messages
  if (/^Field required/i.test(clean)) return tr("هذا الحقل مطلوب.");
  if (/at least (\d+) characters/.test(clean)) return tr("النص أقصر من الحد الأدنى ({n} أحرف).", { n: clean.match(/at least (\d+)/)[1] });
  if (/at most (\d+) characters/.test(clean)) return tr("النص أطول من الحد الأقصى ({n} حرفًا).", { n: clean.match(/at most (\d+)/)[1] });
  if (/valid email/i.test(clean)) return tr("البريد الإلكتروني غير صحيح.");
  if (/not a valid|Input should be/i.test(clean)) return tr("القيمة المُدخلة غير صحيحة.");
  // Any other English text: never show it in the Arabic UI.
  return /[A-Za-z]{3,}/.test(clean) ? tr("تعذّر تنفيذ الطلب. حاول مرة أخرى.") : clean;
}
// Turn any axios/FastAPI error into an Arabic-friendly string for toasts and error states.
export function errorMessage(err, fallback = tr("حدث خطأ غير متوقع")) {
  if (!err) return fallback;
  if (err.code === 'ERR_NETWORK' || (!err.response && err.request)) {
    return tr("تعذّر الاتصال بالخادم. تأكد من اتصالك بالإنترنت ثم حاول مرة أخرى.");
  }
  const detail = err.response?.data?.detail;
  if (typeof detail === 'string') return translateDetail(detail);
  if (Array.isArray(detail)) {
    // Pydantic validation errors: [{ loc, msg }]
    return detail.map((d) => {
      const key = (d.loc ?? []).slice(1).pop();
      return `${FIELD[key] ?? key ?? tr("الحقل")}: ${translateDetail(d.msg)}`;
    }).join(tr("، "));
  }
  return LANG === 'ar' ? fallback : (err.message || fallback);
}

export const httpStatus = (err) => err?.response?.status;

// Endpoints the design proposal flagged as "Backend endpoint required". A 404/405 on them means the
// backend doesn't expose the route yet — the UI shows that explicitly instead of faking data.
// FastAPI answers an unknown route with exactly {"detail":"Not Found"} (404) or "Method Not Allowed" (405);
// a real missing resource carries a specific detail ("Ticket not found"), so it is NOT treated as a missing route.
export const isMissingEndpoint = (err) =>
  httpStatus(err) === 405 || (httpStatus(err) === 404 && err.response?.data?.detail === 'Not Found');
