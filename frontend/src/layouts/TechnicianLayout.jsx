import { LayoutDashboard, Wrench, Bell } from 'lucide-react';
import AppShell from '../components/layout/AppShell';
import { tr } from '../i18n';

const NAV = [
  { to: '/technician', label: tr("الرئيسية"), icon: LayoutDashboard, end: true },
  { to: '/technician/tasks', label: tr("مهامي"), icon: Wrench },
  { to: '/technician/notifications', label: tr("الإشعارات"), icon: Bell, badge: 'notifications' },
];

export default function TechnicianLayout() {
  return <AppShell nav={NAV} title={tr("بوابة الفني الميداني")} />;
}
