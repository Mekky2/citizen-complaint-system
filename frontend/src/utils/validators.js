import { parseNationalId } from './nationalId';
import { tr } from '../i18n';

// Client-side validation mirrors the backend's rules (app/schemas/auth.py) so users get instant feedback.
// The backend remains the authority — these never replace its validation.

export const PHONE_RE = /^01[0125][0-9]{8}$/;

export const validatePhone = (v) => (PHONE_RE.test(v) ? null : tr("رقم موبايل مصري صحيح، مثال: 01012345678"));
export const validateName = (v) => (v.trim().length >= 3 ? null : tr("الاسم لا يقل عن 3 أحرف"));
export const validatePassword = (v) => (v.length >= 8 ? null : tr("كلمة المرور لا تقل عن 8 أحرف"));

// Optional field: empty is fine. When given it must be a valid, real, 18+ Egyptian national ID.
export function validateNationalId(raw) {
  const v = (raw ?? '').trim();
  if (!v) return null;
  const r = parseNationalId(v);
  return r.ok ? null : r.error;
}

// Registration: full four-part Arabic name (first, father, grandfather, family) — Arabic letters only.
const ARABIC_WORD = /^[\u0621-\u064A\u0671\u0640]+$/;
export function validateFullNameAr(v) {
  const parts = (v ?? '').trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return tr("الاسم الرباعي مطلوب");
  if (!parts.every((w) => ARABIC_WORD.test(w))) return tr("اكتب الاسم بالحروف العربية فقط");
  if (parts.length < 4) return tr("اكتب الاسم رباعيًا (الاسم الأول واسم الأب والجد واللقب)");
  if (parts.some((w) => w.replace(/\u0640/g, '').length < 2)) return tr("كل جزء من الاسم لا يقل عن حرفين");
  return null;
}

// Required version of the national-ID check, used by the registration form.
export function validateNationalIdRequired(raw) {
  if (!(raw ?? '').trim()) return tr("الرقم القومي مطلوب");
  return validateNationalId(raw);
}
