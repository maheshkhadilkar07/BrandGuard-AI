import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import { Spinner } from './components/UI';
import { useAuth } from './context/AuthContext';
import Analytics from './pages/Analytics';
import ContentList from './pages/ContentList';
import ContentNew from './pages/ContentNew';
import ContentResults from './pages/ContentResults';
import Dashboard from './pages/Dashboard';
import FactsTerms from './pages/FactsTerms';
import Guidelines from './pages/Guidelines';
import Login from './pages/Login';
import Register from './pages/Register';
import Review, { ReviewQueue } from './pages/Review';
import Suggestions from './pages/Suggestions';
import Users from './pages/Users';

function Protected({ roles, children }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route path="/register" element={user ? <Navigate to="/" replace /> : <Register />} />
      <Route element={<Protected><Layout /></Protected>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/guidelines" element={<Guidelines />} />
        <Route path="/rules" element={<FactsTerms />} />
        <Route path="/content" element={<ContentList />} />
        <Route path="/content/new" element={<Protected roles={['creator']}><ContentNew /></Protected>} />
        <Route path="/content/:id" element={<ContentResults />} />
        <Route path="/content/:id/suggestions" element={<Protected roles={['creator', 'reviewer', 'admin']}><Suggestions /></Protected>} />
        <Route path="/review" element={<Protected roles={['reviewer', 'admin']}><ReviewQueue /></Protected>} />
        <Route path="/review/:id" element={<Protected roles={['reviewer', 'admin']}><Review /></Protected>} />
        <Route path="/analytics" element={<Protected roles={['admin', 'reviewer']}><Analytics /></Protected>} />
        <Route path="/users" element={<Protected roles={['admin']}><Users /></Protected>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
