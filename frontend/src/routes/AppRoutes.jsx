import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth, homePathFor } from '../context/AuthContext';
import ProtectedRoute from './ProtectedRoute';
import LandingPage from '../pages/LandingPage';
import LoginPage from '../pages/auth/LoginPage';
import RegisterPage from '../pages/auth/RegisterPage';
import DesignSystemPreview from '../pages/dev/DesignSystemPreview';
import NotificationsPage from '../pages/shared/NotificationsPage';
import CitizenLayout from '../layouts/CitizenLayout';
import CitizenDashboard from '../pages/citizen/CitizenDashboard';
import CreateTicket from '../pages/citizen/CreateTicket';
import MyTickets from '../pages/citizen/MyTickets';
import CitizenTicketDetails from '../pages/citizen/CitizenTicketDetails';
import CitizenProfile from '../pages/citizen/CitizenProfile';
import SupervisorLayout from '../layouts/SupervisorLayout';
import OperationsDashboard from '../pages/supervisor/OperationsDashboard';
import IncidentsPage from '../pages/supervisor/IncidentsPage';
import IncidentWorkspace from '../pages/supervisor/IncidentWorkspace';
import TechnicianLayout from '../layouts/TechnicianLayout';
import TechnicianDashboard from '../pages/technician/TechnicianDashboard';
import MyTasks from '../pages/technician/MyTasks';
import TaskDetails from '../pages/technician/TaskDetails';
import AdminLayout from '../layouts/AdminLayout';
import AdminDashboard from '../pages/admin/AdminDashboard';
import UsersPage from '../pages/admin/UsersPage';
import DepartmentsPage from '../pages/admin/DepartmentsPage';
import CategoriesPage from '../pages/admin/CategoriesPage';
import TeamsPage from '../pages/admin/TeamsPage';
import AuditLogsPage from '../pages/admin/AuditLogsPage';

function RootRedirect() {
  const { user, booting } = useAuth();
  if (booting) return null;
  return <Navigate to={user ? homePathFor(user.role) : '/'} replace />;
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      {import.meta.env.DEV && <Route path="/dev/design-system" element={<DesignSystemPreview />} />}
      <Route path="/citizen" element={<ProtectedRoute role="citizen" />}>
        <Route element={<CitizenLayout />}>
          <Route index element={<CitizenDashboard />} />
          <Route path="new" element={<CreateTicket />} />
          <Route path="tickets" element={<MyTickets />} />
          <Route path="tickets/:id" element={<CitizenTicketDetails />} />
          <Route path="notifications" element={<NotificationsPage ticketPath={(id) => `/citizen/tickets/${id}`} />} />
          <Route path="profile" element={<CitizenProfile />} />
        </Route>
      </Route>
      <Route path="/supervisor" element={<ProtectedRoute role="supervisor" />}>
        <Route element={<SupervisorLayout />}>
          <Route index element={<OperationsDashboard />} />
          <Route path="incidents" element={<IncidentsPage />}>
            <Route path=":id" element={<IncidentWorkspace />} />
          </Route>
          <Route path="notifications" element={<NotificationsPage ticketPath={(id) => `/supervisor/incidents/${id}`} />} />
        </Route>
      </Route>
      <Route path="/technician" element={<ProtectedRoute role="technician" />}>
        <Route element={<TechnicianLayout />}>
          <Route index element={<TechnicianDashboard />} />
          <Route path="tasks" element={<MyTasks />} />
          <Route path="tasks/:id" element={<TaskDetails />} />
          <Route path="notifications" element={<NotificationsPage />} />
        </Route>
      </Route>
      <Route path="/admin" element={<ProtectedRoute role="admin" />}>
        <Route element={<AdminLayout />}>
          <Route index element={<AdminDashboard />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="departments" element={<DepartmentsPage />} />
          <Route path="categories" element={<CategoriesPage />} />
          <Route path="teams" element={<TeamsPage />} />
          <Route path="audit-logs" element={<AuditLogsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<RootRedirect />} />
    </Routes>
  );
}
