import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listOrders } from '../api/client';
import { FileText, Clock, CheckCircle, AlertCircle, TrendingUp, Zap } from 'lucide-react';

const statusBadge = (status) => {
  const map = {
    pending:     'badge badge-pending',
    in_progress: 'badge badge-ready',
    completed:   'badge badge-approved',
    rejected:    'badge badge-rejected',
  };
  return map[status] || 'badge badge-pending';
};

export default function Dashboard() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    listOrders()
      .then(r => setOrders(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const stats = {
    total:     orders.length,
    pending:   orders.filter(o => o.status === 'pending').length,
    completed: orders.filter(o => o.status === 'completed').length,
    items:     orders.reduce((s, o) => s + (o.item_count || 0), 0),
  };

  return (
    <div>
      <div className="page-header flex justify-between items-center">
        <div>
          <h1>Dashboard</h1>
          <p>Artwork orders overview — Sainmarks / Britannia</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/new-order')}>
          <Zap size={15} /> New Order
        </button>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-num" style={{ color: '#a78bfa' }}>{stats.total}</div>
          <div className="stat-label">Total Orders</div>
        </div>
        <div className="stat-card">
          <div className="stat-num" style={{ color: 'var(--warning)' }}>{stats.pending}</div>
          <div className="stat-label">Pending</div>
        </div>
        <div className="stat-card">
          <div className="stat-num" style={{ color: 'var(--success)' }}>{stats.completed}</div>
          <div className="stat-label">Completed</div>
        </div>
        <div className="stat-card">
          <div className="stat-num" style={{ color: 'var(--info)' }}>{stats.items}</div>
          <div className="stat-label">Label Variants</div>
        </div>
      </div>

      {/* Orders table */}
      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Recent Orders</h2>
          <span className="text-muted text-sm">{orders.length} orders</span>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <div className="spinner" style={{ margin: '0 auto' }} />
            <p className="text-muted text-sm mt-4">Loading orders…</p>
          </div>
        ) : orders.length === 0 ? (
          <div className="empty-state">
            <FileText size={40} style={{ margin: '0 auto', opacity: 0.3 }} />
            <h3>No orders yet</h3>
            <p>Upload a BGP Connect XML or create a new order to get started.</p>
            <button className="btn btn-primary mt-4" onClick={() => navigate('/new-order')}>
              Create First Order
            </button>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Order ID</th>
                  <th>Customer</th>
                  <th>Design Code</th>
                  <th>Items</th>
                  <th>Approved</th>
                  <th>Required By</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {orders.map(o => (
                  <tr key={o.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/orders/${o.id}`)}>
                    <td className="text-mono" style={{ color: '#a78bfa', fontSize: '13px' }}>{o.bgp_order_id}</td>
                    <td style={{ fontWeight: 500 }}>{o.customer_name}</td>
                    <td className="text-mono text-sm">{o.design_code}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>{o.item_count}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '60px' }}>
                          <div className="progress-bar">
                            <div className="progress-fill" style={{ width: `${o.item_count ? (o.approved_count / o.item_count) * 100 : 0}%` }} />
                          </div>
                        </div>
                        <span className="text-sm text-muted">{o.approved_count}/{o.item_count}</span>
                      </div>
                    </td>
                    <td className="text-sm text-muted">{o.required_date || '—'}</td>
                    <td><span className={statusBadge(o.status)}>{o.status}</span></td>
                    <td onClick={e => e.stopPropagation()}>
                      <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/orders/${o.id}`)}>
                        View →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
