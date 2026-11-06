import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const NAV = {
  admin: [
    ['/', 'Dashboard', '▦'], ['/guidelines', 'Brand Guidelines', '☰'], ['/rules', 'Facts & Terminology', '✎'],
    ['/content', 'Content History', '🗂'], ['/analytics', 'Analytics', '📊'], ['/users', 'Users & Audit', '👥'],
  ],
  creator: [
    ['/', 'Dashboard', '▦'], ['/content/new', 'New Content', '＋'], ['/content', 'My Content', '🗂'],
    ['/guidelines', 'Brand Guidelines', '☰'], ['/rules', 'Facts & Terminology', '✎'],
  ],
  reviewer: [
    ['/', 'Dashboard', '▦'], ['/review', 'Review Queue', '✔'], ['/content', 'Content History', '🗂'],
    ['/analytics', 'Analytics', '📊'], ['/guidelines', 'Brand Guidelines', '☰'], ['/rules', 'Facts & Terminology', '✎'],
  ],
};

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const items = NAV[user.role] || [];
  return (
    <div className="shell">
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="brand"><span className="logo">B</span><div><strong>BrandGuard AI</strong><small>Brand governance</small></div></div>
        <nav onClick={() => setOpen(false)}>
          {items.map(([to, label, icon]) => (
            <NavLink key={to} to={to} end={to === '/' || to === '/content'} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              <span className="nav-ico" aria-hidden>{icon}</span>{label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">AI assists. Humans decide.</div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="btn btn-ghost menu-btn" onClick={() => setOpen(!open)} aria-label="Menu">☰</button>
          <div className="spacer" />
          <div className="user-chip"><strong>{user.full_name}</strong><small>{user.role}</small></div>
          <button className="btn btn-outline" onClick={async () => { await logout(); navigate('/login'); }}>Log out</button>
        </header>
        <main className="content"><Outlet /></main>
      </div>
    </div>
  );
}
