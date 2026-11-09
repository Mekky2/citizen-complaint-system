import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth, homePathFor } from '../context/AuthContext';
import { LoadingState } from '../components/common';

// Guards a whole role branch: must be signed in AND hold `role`. A signed-in user who types another
// role's URL is sent to their own home — never shown the other role's UI.
export default function ProtectedRoute({ role }) {
  const { user, booting } = useAuth();
  const loc = useLocation();

  if (booting) return <div className="mx-auto max-w-md pt-24"><LoadingState rows={3} /></div>;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  if (user.role !== role) return <Navigate to={homePathFor(user.role)} replace />;
  return <Outlet />;
}
