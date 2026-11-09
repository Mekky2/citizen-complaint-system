import { LayoutDashboard, FilePlus2, ListChecks, Bell, UserRound } from 'lucide-react';
import AppShell from '../components/layout/AppShell';
import { tr } from '../i18n';

const NAV = [
  { to: '/citizen', label: tr("الرئيسية"), icon: LayoutDashboard, end: true },
  { to: '/citizen/new', label: tr("بلاغ جديد"), icon: FilePlus2 },
  { to: '/citizen/tickets', label: tr("بلاغاتي"), icon: ListChecks },
  { to: '/citizen/notifications', label: tr("الإشعارات"), icon: Bell, badge: 'notifications' },
  { to: '/citizen/profile', label: tr("حسابي"), icon: UserRound },
];

export default function CitizenLayout() {
  return <AppShell nav={NAV} title={tr("بوابة المواطن — جمهورية مصر العربية")} />;
}
