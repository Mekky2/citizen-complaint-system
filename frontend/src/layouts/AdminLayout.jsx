import { LayoutDashboard, Users, Building2, Tags, HardHat, ScrollText } from 'lucide-react';
import AppShell from '../components/layout/AppShell';
import { tr } from '../i18n';

const NAV = [
  { to: '/admin', label: tr("لوحة التحكم"), icon: LayoutDashboard, end: true },
  { to: '/admin/users', label: tr("المستخدمون"), icon: Users },
  { to: '/admin/departments', label: tr("الجهات"), icon: Building2 },
  { to: '/admin/categories', label: tr("التصنيفات"), icon: Tags },
  { to: '/admin/teams', label: tr("فرق الصيانة"), icon: HardHat },
  { to: '/admin/audit-logs', label: tr("سجل التدقيق"), icon: ScrollText },
];

export default function AdminLayout() {
  return <AppShell nav={NAV} title={tr("لوحة إدارة النظام")} wide />;
}
