import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getOrder, generateOrder, generateItem, artworkPngUrl, artworkPdfUrl } from '../api/client';
import { Zap, Download, ArrowLeft, RefreshCw } from 'lucide-react';

const itemStatusBadge = (s) => {
  const map = { pending:'badge-pending', generating:'badge-generating', ready:'badge-ready', approved:'badge-approved', rejected:'badge-rejected' };
  return `badge ${map[s]||'badge-pending'}`;
};

export default function OrderDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [order,   setOrder]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [genLoading, setGenLoading] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [error,   setError]   = useState('');
  const [success, setSuccess] = useState('');

  const reload = () => {
    setLoading(true);
    getOrder(id)
      .then(r => { setOrder(r.data); if (!selectedItem && r.data.items?.length) setSelectedItem(r.data.items[0]); })
      .catch(() => setError('Failed to load order.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { reload(); }, [id]);

  const handleGenerateAll = async () => {
    setGenLoading(true); setError(''); setSuccess('');
    try {
      const res = await generateOrder(id);
      setSuccess(`Generated ${res.data.generated} artwork(s). ${res.data.failed} failed.`);
      reload();
    } catch(e) {
      setError(e.response?.data?.detail || 'Generation failed.');
    } finally { setGenLoading(false); }
  };

  const handleGenerateItem = async (itemId) => {
    setError(''); setSuccess('');
    try {
      await generateItem(itemId);
      setSuccess('Artwork generated.');
      reload();
    } catch(e) {
      setError(e.response?.data?.detail || 'Generation failed.');
    }
  };

  if (loading) return (
    <div style={{ textAlign:'center', padding:'60px' }}>
      <div className="spinner" style={{ margin:'0 auto', width:32, height:32 }}/>
      <p className="text-muted mt-4">Loading order…</p>
    </div>
  );

  if (!order) return <div className="alert alert-error">Order not found.</div>;

  const current = selectedItem && order.items.find(i => i.id === selectedItem.id);

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <button className="btn btn-ghost btn-sm mb-4" onClick={() => navigate('/')}>
          <ArrowLeft size={14}/> Back
        </button>
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-mono" style={{ color:'#a78bfa' }}>{order.bgp_order_id}</h1>
            <p>{order.customer_name} · {order.design_code} · {order.item_count} variant(s)</p>
          </div>
          <button className="btn btn-primary" onClick={handleGenerateAll} disabled={genLoading}>
            {genLoading ? <><span className="spinner"/> Generating…</> : <><Zap size={15}/> Generate All Artwork</>}
          </button>
        </div>
      </div>

      {error   && <div className="alert alert-error">⚠ {error}</div>}
      {success && <div className="alert alert-success">✓ {success}</div>}

      {/* Two-column layout */}
      <div style={{ display:'grid', gridTemplateColumns:'320px 1fr', gap:'24px', alignItems:'start' }}>

        {/* Left: Item list */}
        <div>
          <div className="card" style={{ padding:0, overflow:'hidden' }}>
            <div style={{ padding:'16px 20px', borderBottom:'1px solid var(--border)' }}>
              <p style={{ fontSize:'12px', fontWeight:600, color:'var(--text-secondary)', textTransform:'uppercase', letterSpacing:'0.5px' }}>
                Size Variants ({order.item_count})
              </p>
            </div>
            {order.items.map((item, i) => (
              <div
                key={item.id}
                onClick={() => setSelectedItem(item)}
                style={{
                  padding:'14px 20px',
                  cursor:'pointer',
                  borderBottom: i < order.items.length-1 ? '1px solid var(--border)' : 'none',
                  background: selectedItem?.id === item.id ? 'var(--bg-elevated)' : 'transparent',
                  transition:'background 0.15s',
                  borderLeft: selectedItem?.id === item.id ? '3px solid var(--brand)' : '3px solid transparent',
                }}
              >
                <div className="flex justify-between items-center">
                  <div>
                    <p style={{ fontSize:'13px', fontWeight:500 }}>{item.variant_name || `Variant ${i+1}`}</p>
                    <p style={{ fontSize:'11.5px', color:'var(--text-muted)', marginTop:'3px' }}>
                      EUR: {item.sizes?.EUR||'—'} · US: {item.sizes?.US||'—'} · Qty: {item.quantity}
                    </p>
                  </div>
                  <span className={itemStatusBadge(item.status)}>{item.status}</span>
                </div>
                {item.has_artwork && (
                  <div style={{ display:'flex', gap:'6px', marginTop:'8px' }}>
                    <button className="btn btn-ghost btn-sm" style={{ fontSize:'11px', padding:'4px 8px' }}
                      onClick={e => { e.stopPropagation(); handleGenerateItem(item.id); }}>
                      <RefreshCw size={11}/> Regen
                    </button>
                    <a className="btn btn-ghost btn-sm" style={{ fontSize:'11px', padding:'4px 8px' }}
                      href={artworkPdfUrl(item.artwork_id)} target="_blank" rel="noreferrer"
                      onClick={e => e.stopPropagation()}>
                      <Download size={11}/> PDF
                    </a>
                  </div>
                )}
                {!item.has_artwork && (
                  <button className="btn btn-primary btn-sm" style={{ marginTop:'8px', fontSize:'11px' }}
                    onClick={e => { e.stopPropagation(); handleGenerateItem(item.id); }}>
                    <Zap size={11}/> Generate
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Right: Artwork viewer */}
        <div>
          {current?.has_artwork ? (
            <div>
              <div className="flex justify-between items-center mb-4">
                <div>
                  <h2 style={{ fontSize:'15px', fontWeight:600 }}>Artwork Preview</h2>
                  <p className="text-muted text-sm">{current.variant_name} · Status: <span style={{ color: current.artwork_status==='approved'?'var(--success)':current.artwork_status==='rejected'?'var(--danger)':'var(--warning)' }}>{current.artwork_status}</span></p>
                </div>
                <a className="btn btn-ghost" href={artworkPdfUrl(current.artwork_id)} target="_blank" rel="noreferrer">
                  <Download size={15}/> Download PDF
                </a>
              </div>

              <div className="artwork-viewer">
                <img
                  src={artworkPngUrl(current.artwork_id) + `?t=${Date.now()}`}
                  alt="Generated artwork"
                  onError={e => e.target.style.display='none'}
                />
              </div>

              {/* Label data summary */}
              <div className="card mt-4">
                <p style={{ fontSize:'12px', fontWeight:600, color:'var(--text-secondary)', textTransform:'uppercase', letterSpacing:'0.5px', marginBottom:'14px' }}>Label Data</p>
                <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'12px' }}>
                  {[
                    ['Order No.',    current.order_number],
                    ['Product No.',  current.product_number],
                    ['Season Code',  current.season_code],
                    ['Quantity',     current.quantity],
                    ['Country',      current.country_of_origin],
                    ['Tape Color',   current.tape_color],
                    ['Layout',       current.layout_variant],
                    ['Supplier Ref', current.supplier_style],
                  ].map(([k,v]) => (
                    <div key={k} style={{ padding:'10px 14px', background:'var(--bg-elevated)', borderRadius:'var(--radius-md)' }}>
                      <p style={{ fontSize:'11px', color:'var(--text-muted)', fontWeight:600, textTransform:'uppercase', letterSpacing:'0.4px' }}>{k}</p>
                      <p style={{ fontSize:'13px', fontWeight:500, marginTop:'3px' }}>{v||'—'}</p>
                    </div>
                  ))}
                </div>

                {/* Size breakdown */}
                {current.sizes && Object.keys(current.sizes).length > 0 && (
                  <div style={{ marginTop:'14px' }}>
                    <p style={{ fontSize:'12px', fontWeight:600, color:'var(--text-secondary)', textTransform:'uppercase', letterSpacing:'0.5px', marginBottom:'10px' }}>Sizes</p>
                    <div style={{ display:'flex', gap:'8px', flexWrap:'wrap' }}>
                      {Object.entries(current.sizes).filter(([,v])=>v).map(([k,v]) => (
                        <div key={k} style={{ padding:'6px 12px', background:'var(--brand-glow)', border:'1px solid rgba(108,99,255,0.2)', borderRadius:'var(--radius-sm)', fontSize:'12px' }}>
                          <span style={{ color:'var(--text-muted)' }}>{k}: </span>
                          <span style={{ color:'#a78bfa', fontWeight:600 }}>{v}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="empty-state card">
              <Zap size={36} style={{ margin:'0 auto', opacity:0.3 }} />
              <h3>No artwork yet</h3>
              <p>Select a variant and click Generate, or use "Generate All Artwork" above.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
