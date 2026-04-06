import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { LayoutDashboard, PlusCircle, CheckSquare, FileText } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import NewOrder from './pages/NewOrder';
import OrderDetail from './pages/OrderDetail';
import ApprovalPortal from './pages/ApprovalPortal';

function Sidebar() {
  const links = [
    { to: '/',          icon: LayoutDashboard, label: 'Dashboard'       },
    { to: '/new-order', icon: PlusCircle,      label: 'New Order'       },
    { to: '/approvals', icon: CheckSquare,     label: 'Approval Portal' },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <h2>🎨 ArtEngine</h2>
        <p>Sainmarks / Britannia</p>
      </div>
      <nav className="sidebar-nav">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <Icon className="icon" size={16} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div style={{ padding: '16px 20px', borderTop: '1px solid var(--border)' }}>
        <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>v1.0.0 Prototype</p>
        <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>Phase 1 — Internal</p>
      </div>
    </aside>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/"            element={<Dashboard />} />
            <Route path="/new-order"   element={<NewOrder />} />
            <Route path="/orders/:id"  element={<OrderDetail />} />
            <Route path="/approvals"   element={<ApprovalPortal />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
