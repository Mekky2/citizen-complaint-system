import { Radar, Siren, Bell } from 'lucide-react';
import AppShell from '../components/layout/AppShell';
import { tr } from '../i18n';

const NAV = [
  { to: '/supervisor', label: tr("غرفة العمليات"), icon: Radar, end: true },
  { to: '/supervisor/incidents', label: tr("البلاغات"), icon: Siren },
  { to: '/supervisor/notifications', label: tr("الإشعارات"), icon: Bell, badge: 'notifications' },
];

export default function SupervisorLayout() {
  return <AppShell nav={NAV} title={tr("غرفة العمليات — المشرف")} wide />;
}
