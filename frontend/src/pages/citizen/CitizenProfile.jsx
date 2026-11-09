import { UserRound, Phone, Mail, BadgeCheck } from 'lucide-react';
import { Card, AsyncView, PageHeader } from '../../components/common';
import useFetch from '../../hooks/useFetch';
import { getMyProfile } from '../../api/users';
import { ROLE_LABEL } from '../../utils/status';
import { tr } from '../../i18n';

// Read-only: the backend exposes GET /users/me but no self-service update (PATCH /users/{id} is admin-only).
export default function CitizenProfile() {
  const { data, loading, error, reload } = useFetch(getMyProfile, []);
  return (
    <div className="space-y-5">
      <PageHeader icon={UserRound} title={tr("حسابي")} subtitle={tr("بيانات حسابك كما هي مسجّلة في النظام.")} />
      <Card title={tr("البيانات الشخصية")} icon={UserRound}>
        <AsyncView loading={loading} error={error} onRetry={reload}>
          {data && (
            <dl className="grid gap-5 text-sm sm:grid-cols-2">
              <Item icon={UserRound} k={tr("الاسم")} v={data.name} />
              <Item icon={BadgeCheck} k={tr("نوع الحساب")} v={ROLE_LABEL[data.role] ?? data.role} />
              <Item icon={Phone} k={tr("رقم الموبايل")} v={data.phone && <span dir="ltr">{data.phone}</span>} />
              <Item icon={Mail} k={tr("البريد الإلكتروني")} v={data.email && <span dir="ltr">{data.email}</span>} />
            </dl>
          )}
        </AsyncView>
      </Card>
      <p className="text-xs text-slate-400">{tr("لتعديل بياناتك تواصل مع مدير النظام.")}</p>
    </div>
  );
}

const Item = ({ icon: I, k, v }) => (
  <div className="flex items-start gap-3 rounded-xl border border-slate-700 bg-slate-900/50 p-3">
    <I className="mt-0.5 h-4 w-4 text-slate-400" aria-hidden />
    <div><dt className="text-xs text-slate-400">{k}</dt><dd className="font-bold text-slate-100">{v || '—'}</dd></div>
  </div>
);
