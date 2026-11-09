import { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Button, Input, useToast } from '../../components/common';
import { useAuth, homePathFor } from '../../context/AuthContext';
import { errorMessage } from '../../utils/errors';
import { Lock, UserRound } from 'lucide-react';
import AuthFrame from './AuthFrame';
import { tr } from '../../i18n';

export default function LoginPage() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const toast = useToast();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homePathFor(user.role)} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const profile = await login(identifier.trim(), password);
      const from = loc.state?.from;
      nav(from && from.startsWith(homePathFor(profile.role)) ? from : homePathFor(profile.role), { replace: true });
    } catch (err) {
      toast.error(errorMessage(err, tr("تعذّر تسجيل الدخول")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthFrame title={tr("تسجيل الدخول")} subtitle={tr("ادخل برقم الموبايل أو البريد الإلكتروني")} footer={<>{tr("مواطن جديد؟")} <Link to="/register" className="font-bold text-blue-300 hover:underline">{tr("إنشاء حساب")}</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        <Input label={tr("رقم الموبايل أو البريد")} icon={UserRound} value={identifier} onChange={(e) => setIdentifier(e.target.value)} dir="ltr" autoComplete="username" required />
        <Input label={tr("كلمة المرور")} icon={Lock} type="password" value={password} onChange={(e) => setPassword(e.target.value)} dir="ltr" autoComplete="current-password" required />
        <Button type="submit" loading={busy} className="w-full" size="lg">{tr("دخول")}</Button>
      </form>
    </AuthFrame>
  );
}
