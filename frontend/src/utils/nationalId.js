import { tr } from '../i18n';
// Egyptian national ID: C YYMMDD GG SSSS D  (14 digits). Century 2 = 1900s, 3 = 2000s.
// Used for instant feedback only — the backend stays the authority.
export const GOVERNORATES = {
  '01': tr("القاهرة"), '02': tr("الإسكندرية"), '03': tr("بورسعيد"), '04': tr("السويس"), '11': tr("دمياط"), '12': tr("الدقهلية"),
  '13': tr("الشرقية"), '14': tr("القليوبية"), '15': tr("كفر الشيخ"), '16': tr("الغربية"), '17': tr("المنوفية"), '18': tr("البحيرة"),
  '19': tr("الإسماعيلية"), '21': tr("الجيزة"), '22': tr("بني سويف"), '23': tr("الفيوم"), '24': tr("المنيا"), '25': tr("أسيوط"),
  '26': tr("سوهاج"), '27': tr("قنا"), '28': tr("أسوان"), '29': tr("الأقصر"), '31': tr("البحر الأحمر"), '32': tr("الوادي الجديد"),
  '33': tr("مطروح"), '34': tr("شمال سيناء"), '35': tr("جنوب سيناء"), '88': tr("خارج الجمهورية"),
};

export function parseNationalId(raw, { minAge = 18 } = {}) {
  const id = (raw || '').replace(/\s/g, '');
  if (!/^\d{14}$/.test(id)) return { ok: false, error: tr("الرقم القومي يجب أن يكون 14 رقمًا") };
  const c = id[0];
  if (c !== '2' && c !== '3') return { ok: false, error: tr("الرقم القومي غير صحيح: يبدأ بالرقم 2 أو 3") };
  const year = (c === '2' ? 1900 : 2000) + Number(id.slice(1, 3));
  const month = Number(id.slice(3, 5));
  const day = Number(id.slice(5, 7));
  const birth = new Date(year, month - 1, day);
  if (birth.getFullYear() !== year || birth.getMonth() !== month - 1 || birth.getDate() !== day) return { ok: false, error: tr("تاريخ الميلاد في الرقم القومي غير صحيح") };
  const now = new Date();
  if (birth > now) return { ok: false, error: tr("تاريخ الميلاد في الرقم القومي في المستقبل") };
  const gov = GOVERNORATES[id.slice(7, 9)];
  if (!gov) return { ok: false, error: tr("كود المحافظة في الرقم القومي غير معروف") };
  let age = now.getFullYear() - year;
  if (now.getMonth() < month - 1 || (now.getMonth() === month - 1 && now.getDate() < day)) age -= 1;
  if (minAge && age < minAge) return { ok: false, error: tr("عمر صاحب الرقم {p0} سنة — الحد الأدنى {p1} سنة", { p0: age, p1: minAge }) };
  const pad = (n) => String(n).padStart(2, '0');
  return { ok: true, age, gov, birth: `${pad(day)}/${pad(month)}/${year}`, gender: Number(id[12]) % 2 ? tr("ذكر") : tr("أنثى") };
}
