import { useEffect, useState } from 'react';
import { listPending, submitApproval, getApprovalHistory, artworkPngUrl, artworkPdfUrl } from '../api/client';
import { CheckCircle, XCircle, RotateCcw, Download, Clock, User } from 'lucide-react';

export default function ApprovalPortal() {
  const [items,   setItems]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [history,  setHistory]  = useState([]);
  const [approver, setApprover] = useState('');
  const [comments, setComments] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error,   setError]    = useState('');
  const [success, setSuccess]  = useState('');

  const reload = () => {
    setLoading(true);
    listPending()
      .then(r => { setItems(r.data); if (!selected && r.data.length) selectItem(r.data[0]); })
      .catch(() => setError('Failed to load pending items.'))
      .finally(() => setLoading(false));
  };

  const selectItem = async (item) => {
    setSelected(item);
    setComments('');
    setError('');
    setSuccess('');
    try {
      const h = await getApprovalHistory(item.artwork_id);
      setHistory(h.data);
    } catch { setHistory([]); }
  };

  useEffect(() => { reload(); }, []);

  const handleAction = async (action) => {
    if (!approver.trim()) return setError('Please enter your name before submitting.');
    setSubmitting(true); setError(''); setSuccess('');
    try {
      await submitApproval(selected.artwork_id, { action, comments, approved_by: approver });
      setSuccess(`Artwork ${action.replace('_',' ')} successfully.`);
      reload();
      setSelected(null);
      setHistory([]);
    } catch(e) {
      setError(e.response?.data?.detail || 'Action failed.');
    } finally { setSubmitting(false); }
  };

  const pendingCount = items.length;

  return (
    <div>
      <div className="page-header">
        <h1>Approval Portal</h1>
        <p>Review and approve generated artwork before production</p>
      </div>

      {/* Approver name */}
      <div className="card mb-4" style={{ maxWidth: 400 }}>
        <div className="form-group" style={{ marginBottom:0 }}>
          <label style={{ display:'flex', alignItems:'center', gap:'6px' }}>
            <User size={12}/> Your Name (required for approval)
          </label>
          <input
            value={approver}
            onChange={e => setApprover(e.target.value)}
            placeholder="e.g. Krish Sreedharan"
          />
        </div>
      </div>

      {error   && <div className="alert alert-error">⚠ {error}</div>}
      {success && <div className="alert alert-success">✓ {success}</div>}

      {loading ? (
        <div style={{ textAlign:'center', padding:'60px' }}>
          <div className="spinner" style={{margin:'0 auto'}}/> 
          <p className="text-muted mt-4">Loading pending artwork…</p>
        </div>
      ) : items.length === 0 ? (
        <div className="empty-state card">
          <CheckCircle size={40} style={{ margin:'0 auto', color:'var(--success)', opacity:0.5 }}/>
          <h3>All caught up!</h3>
          <p>No artwork pending approval. Generate artwork from an order first.</p>
        </div>
      ) : (
        <div style={{ display:'grid', gridTemplateColumns:'300px 1fr', gap:'24px', alignItems:'start' }}>

          {/* Left: Queue */}
          <div className="card" style={{ padding:0, overflow:'hidden' }}>
            <div style={{ padding:'14px 20px', borderBottom:'1px solid var(--border)', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
              <p style={{ fontSize:'12px', fontWeight:600, color:'var(--text-secondary)', textTransform:'uppercase', letterSpacing:'0.5px' }}>
                Pending Queue
              </p>
              <span className="badge badge-pending">{pendingCount}</span>
            </div>

            {items.map((item, i) => (
              <div
                key={item.artwork_id}
                onClick={() => selectItem(item)}
                style={{
                  padding:'14px 20px',
                  cursor:'pointer',
                  borderBottom: i < items.length-1 ? '1px solid var(--border)' : 'none',
                  background: selected?.artwork_id === item.artwork_id ? 'var(--bg-elevated)' : 'transparent',
                  borderLeft: selected?.artwork_id === item.artwork_id ? '3px solid var(--brand)' : '3px solid transparent',
                  transition:'all 0.15s',
                }}
              >
                <div style={{ display:'flex', gap:'12px', alignItems:'center' }}>
                  <img
                    src={artworkPngUrl(item.artwork_id)}
                    style={{ width:44, height:60, objectFit:'cover', borderRadius:'4px', border:'1px solid var(--border)' }}
                    alt=""
                    onError={e => e.target.style.display='none'}
                  />
                  <div>
                    <p style={{ fontSize:'12px', fontWeight:600, color:'#a78bfa' }}>{item.bgp_order_id}</p>
                    <p style={{ fontSize:'12px', color:'var(--text-secondary)', marginTop:'2px' }}>{item.customer_name}</p>
                    <p style={{ fontSize:'11px', color:'var(--text-muted)', marginTop:'3px' }}>{item.variant_name?.slice(0,30) || 'Variant'}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Right: Viewer & actions */}
          {selected ? (
            <div>
              <div className="flex justify-between items-center mb-4">
                <div>
                  <h2 style={{ fontSize:'16px', fontWeight:600 }}>{selected.bgp_order_id} — {selected.variant_name?.slice(0,40)}</h2>
                  <p className="text-muted text-sm">{selected.customer_name} · {selected.design_code} · Required: {selected.required_date||'—'}</p>
                </div>
                <a className="btn btn-ghost" href={artworkPdfUrl(selected.artwork_id)} target="_blank" rel="noreferrer">
                  <Download size={15}/> PDF
                </a>
              </div>

              {/* Artwork */}
              <div className="artwork-viewer" style={{ marginBottom:'20px' }}>
                <img
                  src={artworkPngUrl(selected.artwork_id) + `?t=${Date.now()}`}
                  alt="Artwork for approval"
                />
              </div>

              {/* Comments */}
              <div className="card" style={{ marginBottom:'16px' }}>
                <div className="form-group" style={{ marginBottom:0 }}>
                  <label>Comments / Revision Notes</label>
                  <textarea
                    value={comments}
                    onChange={e => setComments(e.target.value)}
                    placeholder="Add comments before approving or rejecting…"
                    style={{ minHeight:'80px' }}
                  />
                </div>
              </div>

              {/* Action buttons */}
              <div style={{ display:'flex', gap:'12px' }}>
                <button
                  className="btn btn-success"
                  style={{ fontSize:'14px', padding:'12px 24px' }}
                  onClick={() => handleAction('approved')}
                  disabled={submitting}
                >
                  {submitting ? <span className="spinner"/> : <CheckCircle size={16}/>}
                  Approve
                </button>
                <button
                  className="btn"
                  style={{ background:'var(--warning-bg)', color:'var(--warning)', border:'1px solid rgba(245,158,11,0.3)', fontSize:'14px', padding:'12px 24px' }}
                  onClick={() => handleAction('revision_requested')}
                  disabled={submitting}
                >
                  <RotateCcw size={16}/> Request Revision
                </button>
                <button
                  className="btn btn-danger"
                  style={{ fontSize:'14px', padding:'12px 24px' }}
                  onClick={() => handleAction('rejected')}
                  disabled={submitting}
                >
                  <XCircle size={16}/> Reject
                </button>
              </div>

              {/* History */}
              {history.length > 0 && (
                <div className="card mt-4">
                  <p style={{ fontSize:'12px', fontWeight:600, color:'var(--text-secondary)', textTransform:'uppercase', letterSpacing:'0.5px', marginBottom:'14px' }}>
                    Approval History
                  </p>
                  {history.map((h, i) => (
                    <div key={i} style={{ display:'flex', gap:'12px', marginBottom:'10px', padding:'10px 14px', background:'var(--bg-elevated)', borderRadius:'var(--radius-md)' }}>
                      <div style={{ width:8, height:8, borderRadius:'50%', marginTop:5, flexShrink:0, background: h.action==='approved'?'var(--success)':h.action==='rejected'?'var(--danger)':'var(--warning)' }}/>
                      <div>
                        <p style={{ fontSize:'13px', fontWeight:500 }}>
                          <span style={{ color: h.action==='approved'?'var(--success)':h.action==='rejected'?'var(--danger)':'var(--warning)' }}>
                            {h.action.replace('_',' ')}
                          </span>
                          {' '}by {h.approved_by}
                        </p>
                        {h.comments && <p style={{ fontSize:'12px', color:'var(--text-secondary)', marginTop:'3px' }}>{h.comments}</p>}
                        <p style={{ fontSize:'11px', color:'var(--text-muted)', marginTop:'3px', display:'flex', alignItems:'center', gap:'4px' }}>
                          <Clock size={10}/> {new Date(h.actioned_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="empty-state card">
              <p>Select an item from the queue to review.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
