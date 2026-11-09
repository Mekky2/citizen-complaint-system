import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { Button, Input, useToast } from '../../components/common';
import { useAuth, homePathFor } from '../../context/AuthContext';
import { errorMessage } from '../../utils/errors';
import { validateFullNameAr, validatePhone, validatePassword, validateNationalIdRequired } from '../../utils/validators';
import { parseNationalId } from '../../utils/nationalId';
import { IdCard, Lock, Mail, Phone, User } from 'lucide-react';
import AuthFrame from './AuthFrame';
import { tr } from '../../i18n';

export default function RegisterPage() {
  const { user, register } = useAuth();
  const nav = useNavigate();
  const toast = useToast();
  const [f, setF] = useState({ name: '', phone: '', national_id: '', email: '', password: '' });
  const [touched, setTouched] = useState({});
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homePathFor(user.role)} replace />;

  const errors = {
    name: validateFullNameAr(f.name),
    phone: validatePhone(f.phone),
    national_id: validateNationalIdRequired(f.national_id),
    password: validatePassword(f.password),
  };
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));
  const blur = (k) => () => setTouched((t) => ({ ...t, [k]: true }));
  const show = (k) => (touched[k] ? errors[k] : null);
  const nid = f.national_id.trim() ? parseNationalId(f.national_id.trim()) : null;

  const submit = async (e) => {
    e.preventDefault();
    setTouched({ name: true, phone: true, national_id: true, password: true });
    if (Object.values(errors).some(Boolean)) return;
    setBusy(true);
    try {
      const payload = { name: f.name.trim().replace(/\s+/g, ' '), phone: f.phone, national_id: f.national_id.trim(), password: f.password };
      if (f.email.trim()) payload.email = f.email.trim();
      await register(payload);
      nav('/citizen', { replace: true });
    } catch (err) {
      toast.error(errorMessage(err, tr("تعذّر إنشاء الحساب")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthFrame title={tr("إنشاء حساب مواطن")} footer={<>{tr("لديك حساب؟")} <Link to="/login" className="font-bold text-blue-300 hover:underline">{tr("تسجيل الدخول")}</Link></>}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Input label={tr("الاسم الرباعي")} placeholder={tr("مثال: أحمد محمد علي حسن")} icon={User} value={f.name} onChange={set('name')} onBlur={blur('name')} error={show('name')} required />
        <Input label={tr("رقم الموبايل")} icon={Phone} value={f.phone} onChange={set('phone')} onBlur={blur('phone')} error={show('phone')} dir="ltr" inputMode="numeric" required />
        <Input label={tr("الرقم القومي")} icon={IdCard} success={nid?.ok ? tr("تم التحقق — تاريخ الميلاد {p0}، العمر {p1} سنة، {p2}", { p0: nid.birth, p1: nid.age, p2: nid.gov }) : undefined} value={f.national_id} onChange={set('national_id')} onBlur={blur('national_id')} error={show('national_id')} dir="ltr" inputMode="numeric" maxLength={14} required />
        <Input label={tr("البريد الإلكتروني (اختياري)")} icon={Mail} type="email" value={f.email} onChange={set('email')} dir="ltr" />
        <Input label={tr("كلمة المرور")} icon={Lock} type="password" value={f.password} onChange={set('password')} onBlur={blur('password')} error={show('password')} dir="ltr" autoComplete="new-password" required />
        <Button type="submit" loading={busy} className="w-full" size="lg">{tr("إنشاء الحساب")}</Button>
      </form>
    </AuthFrame>
  );
}
