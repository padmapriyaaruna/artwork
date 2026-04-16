import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getOrder, generateOrder, generateItem, artworkPngUrl, artworkPdfUrl } from '../api/client';
import { Zap, Download, ArrowLeft, RefreshCw, Eye } from 'lucide-react';

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

  const reload = (keepSelectedId) => {
    setLoading(true);
    getOrder(id)
      .then(r => {
        setOrder(r.data);
        const items = r.data.items || [];
        // Always sync selectedItem from fresh data so artwork_id / status are up-to-date
        if (keepSelectedId) {
          const fresh = items.find(i => i.id === keepSelectedId) || items[0] || null;
          setSelectedItem(fresh);
        } else if (!selectedItem && items.length) {
          setSelectedItem(items[0]);
        }
      })
      .catch(() => setError('Failed to load order.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { reload(); }, [id]);

  // ── Poll every 5s while backend is generating ──────────────────────────────
  const [polling, setPolling] = useState(false);

  const startPolling = (keepId) => {
    setPolling(true);
    const MAX_POLLS = 60;   // 5 min cap
    let count = 0;
    const timer = setInterval(async () => {
      count++;
      try {
        const r = await import('../api/client').then(m => m.getOrder(id));
        const fresh = r.data;
        setOrder(fresh);
        // Sync selected item
        const freshItem = fresh.items?.find(i => i.id === keepId) || fresh.items?.[0];
        if (freshItem) setSelectedItem(freshItem);

        const items = fresh.items || [];
        const doneCount   = items.filter(i => i.has_artwork).length;
        const totalCount  = items.length;
        const stillActive = items.some(i => i.status === 'generating');
        const orderDone   = fresh.status === 'completed' || fresh.status === 'in_progress';

        if ((!stillActive && orderDone) || doneCount === totalCount || count >= MAX_POLLS) {
          clearInterval(timer);
          setPolling(false);
          setGenLoading(false);
          const failedCount = items.filter(i => !i.has_artwork).length;
          if (failedCount > 0) {
            setSuccess(`Generated ${doneCount} artwork(s). ${failedCount} item(s) pending — check logs.`);
          } else {
            setSuccess(`✓ All ${doneCount} artwork(s) generated successfully!`);
          }
        }
      } catch {
        // Network blip — keep polling
      }
    }, 5000);
  };

  const handleGenerateAll = async () => {
    setGenLoading(true); setError(''); setSuccess(''); setPolling(false);
    try {
      await generateOrder(id);
      // 202 response — backend is processing in background
      setSuccess('⚙ Generating artwork in background… This page will update automatically.');
      startPolling(selectedItem?.id);
    } catch(err) {
      setGenLoading(false);
      const resp = err.response;
      if (resp?.data?.detail) {
        setError(resp.data.detail);
      } else if (resp?.data) {
        setError(JSON.stringify(resp.data).slice(0, 300));
      } else if (err.request) {
        // Network timeout — backend IS working, just start polling anyway
        setSuccess('⚙ Request timed out but backend is still processing. Checking progress…');
        startPolling(selectedItem?.id);
        setGenLoading(true); // keep spinner until poll confirms done
      } else {
        setError(err.message || 'Generation failed.');
      }
    }
  };

  const handleGenerateItem = async (itemId) => {
    setError(''); setSuccess('');
    try {
      await generateItem(itemId);
      setSuccess('Artwork generated.');
      reload(itemId);
    } catch(err) {
      const resp = err.response;
      setError(resp?.data?.detail || err.message || 'Generation failed.');
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
          <div style={{ display:'flex', alignItems:'center', gap:'12px' }}>
            {polling && (
              <span style={{ fontSize:'13px', color:'var(--text-secondary)' }}>
                {order.items.filter(i => i.has_artwork).length}/{order.item_count} done
              </span>
            )}
            <button className="btn btn-primary" onClick={handleGenerateAll} disabled={genLoading}>
              {genLoading
                ? <><span className="spinner"/> {polling ? 'Processing…' : 'Generating…'}</>
                : <><Zap size={15}/> Generate All Artwork</>}
            </button>
          </div>
        </div>
      </div>

      {error   && <div className="alert alert-error">⚠ {error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

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
                onClick={() => setSelectedItem(item)}  // stale-safe: label data reads from `current` (re-derived from order.items)
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
                <div className="flex gap-2 items-center">
                  <a className="btn btn-ghost" href={artworkPdfUrl(current.artwork_id)} target="_blank" rel="noreferrer">
                    <Download size={15}/> Download Label PDF
                  </a>
                  <button className="btn btn-primary" onClick={() => navigate(`/orders/${order.id}/approval-preview/${current.artwork_id}`)}>
                    <Eye size={15}/> Preview Approval Sheet
                  </button>
                </div>
              </div>

              <div className="artwork-viewer">
                {/* key forces React to unmount/remount the img whenever the artwork changes,
                    preventing the browser from serving a cached image for a different variant */}
                <img
                  key={current.artwork_id}
                  src={artworkPngUrl(current.artwork_id) + `?v=${current.artwork_id}`}
                  alt="Generated artwork"
                  onError={e => e.target.style.display='none'}
                />
              </div>

              {/* Label data summary */}
              <div className="card mt-4">
                <p style={{ fontSize:'12px', fontWeight:600, color:'var(--text-secondary)', textTransform:'uppercase', letterSpacing:'0.5px', marginBottom:'14px' }}>Label Data</p>
                <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'12px' }}>
                  {[
                    // H&M fields
                    ['Order No.',    current.order_number],
                    ['Product No.',  current.product_number],
                    ['Season Code',  current.season_code],
                    ['Quantity',     current.quantity],
                    ['Country',      current.country_of_origin],
                    ['Layout',       current.layout_variant],
                    ['Supplier Ref', current.supplier_style],
                    ['Tape Color',   current.tape_color],
                    // OVS fields
                    ['Barcode',      current.barcode_number],
                    ['Price',        current.selling_price ? `${current.currency_symbol || ''} ${current.selling_price}`.trim() : null],
                    ['SKU',          current.sku_code],
                    ['Color',        current.color],
                    ['Commercial Ref', current.commercial_ref],
                    ['Style Code',   current.style_code],
                  ].filter(([,v]) => v != null && v !== '').map(([k,v]) => (
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
