import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadXML, createOrder } from '../api/client';
import { Upload, FileText, Plus, Trash2, ChevronDown, ChevronUp } from 'lucide-react';

const EMPTY_ITEM = {
  variant_name: '', quantity: 100,
  sizes: { EUR: '', US: '', CA: '', MX: '', CN: '', AUS: '', UK: '', BR: '' },
  order_number: '', product_number: '', season_code: '',
  country_of_origin: 'Made in India',
  tape_color: 'BLACK', supplier_style: '',
  fibre_content: [{ header: 'SHELL', percentage: 100, wording: 'COTTON' }],
  layout_variant: 'logo_with_size',
};

export default function NewOrder() {
  const navigate = useNavigate();
  const fileRef  = useRef(null);

  const [tab, setTab]         = useState('xml');        // 'xml' | 'form'
  const [dragging, setDragging] = useState(false);
  const [file, setFile]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');
  const [success, setSuccess] = useState('');

  // Form state
  const [form, setForm] = useState({
    bgp_order_id:  `B${Date.now().toString().slice(-7)}`,
    customer_name: 'H&M',
    customer_email:'',
    customer_ref:  '',
    design_code:   'HM30105',
    required_date: '',
    items: [{ ...EMPTY_ITEM }],
  });

  const [expandedItem, setExpandedItem] = useState(0);

  // ── XML upload ────────────────────────────────────────────────────────────
  const handleFileDrop = (e) => {
    e.preventDefault(); setDragging(false);
    const f = e.dataTransfer?.files[0] || e.target.files[0];
    if (f) setFile(f);
  };

  const handleXmlSubmit = async () => {
    if (!file) return setError('Please select an XML file.');
    const fd = new FormData();
    fd.append('file', file);
    setLoading(true); setError(''); setSuccess('');
    try {
      const res = await uploadXML(fd);
      setSuccess(res.data.message);
      setTimeout(() => navigate(`/orders/${res.data.order_id}`), 1500);
    } catch(e) {
      setError(e.response?.data?.detail || 'Upload failed.');
    } finally { setLoading(false); }
  };

  // ── Manual form ───────────────────────────────────────────────────────────
  const setField = (path, val) => {
    setForm(f => {
      const copy = { ...f };
      const parts = path.split('.');
      let cur = copy;
      for (let i = 0; i < parts.length - 1; i++) {
        if (!isNaN(parts[i])) cur = cur[parseInt(parts[i])];
        else cur = cur[parts[i]];
      }
      cur[parts[parts.length - 1]] = val;
      return { ...copy };
    });
  };

  const addItem = () => {
    setForm(f => ({ ...f, items: [...f.items, { ...EMPTY_ITEM }] }));
    setExpandedItem(form.items.length);
  };

  const removeItem = (idx) => {
    setForm(f => ({ ...f, items: f.items.filter((_, i) => i !== idx) }));
  };

  const handleFormSubmit = async () => {
    setLoading(true); setError(''); setSuccess('');
    try {
      const res = await createOrder(form);
      setSuccess(res.data.message);
      setTimeout(() => navigate(`/orders/${res.data.order_id}`), 1500);
    } catch(e) {
      setError(e.response?.data?.detail || 'Failed to create order.');
    } finally { setLoading(false); }
  };

  return (
    <div>
      <div className="page-header">
        <h1>New Order</h1>
        <p>Upload a BGP Connect XML or fill the form manually</p>
      </div>

      {error   && <div className="alert alert-error">⚠ {error}</div>}
      {success && <div className="alert alert-success">✓ {success}</div>}

      {/* Tab switcher */}
      <div className="tabs">
        <button className={`tab ${tab==='xml'  ? 'active':''}`} onClick={() => setTab('xml')}>
          Upload XML
        </button>
        <button className={`tab ${tab==='form' ? 'active':''}`} onClick={() => setTab('form')}>
          Manual Form
        </button>
      </div>

      {/* ── XML tab ────────────────────────────────────────────────────── */}
      {tab === 'xml' && (
        <div className="card" style={{ maxWidth: 600 }}>
          <h2 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '20px' }}>
            Upload BGP Connect XML
          </h2>
          <div
            className={`upload-zone ${dragging ? 'drag-over' : ''}`}
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleFileDrop}
            onClick={() => fileRef.current?.click()}
          >
            <Upload size={36} style={{ margin: '0 auto', color: 'var(--brand)', opacity: 0.8 }} />
            <h3>{file ? file.name : 'Drop XML file here'}</h3>
            <p>{file ? `${(file.size/1024).toFixed(1)} KB` : 'or click to browse'}</p>
            <input ref={fileRef} type="file" accept=".xml" style={{ display:'none' }} onChange={handleFileDrop} />
          </div>

          {file && (
            <div style={{ display:'flex', gap:'12px', marginTop:'20px' }}>
              <button className="btn btn-primary" onClick={handleXmlSubmit} disabled={loading}>
                {loading ? <><span className="spinner" /> Parsing…</> : <><FileText size={15}/> Parse & Create Order</>}
              </button>
              <button className="btn btn-ghost" onClick={() => setFile(null)}>Clear</button>
            </div>
          )}

          <div style={{ marginTop:'20px', padding:'14px', background:'var(--bg-elevated)', borderRadius:'var(--radius-md)', fontSize:'13px', color:'var(--text-secondary)' }}>
            <strong style={{ color:'var(--text-primary)' }}>Supported format:</strong> BGP Connect / BRAT XML export.<br />
            The engine will automatically parse all order items, sizes, fibre content, care symbols, and multilingual text.
          </div>
        </div>
      )}

      {/* ── Manual form tab ─────────────────────────────────────────────── */}
      {tab === 'form' && (
        <div>
          {/* Order details */}
          <div className="card mb-4">
            <h2 style={{ fontSize:'15px', fontWeight:600, marginBottom:'20px' }}>Order Details</h2>
            <div className="form-grid-2">
              <div className="form-group">
                <label>Order ID (BGP)</label>
                <input value={form.bgp_order_id} onChange={e => setForm(f=>({...f,bgp_order_id:e.target.value}))} />
              </div>
              <div className="form-group">
                <label>Design Code</label>
                <select value={form.design_code} onChange={e => setForm(f=>({...f,design_code:e.target.value}))}>
                  <option value="HM30105">HM30105 — H&M Care Label 35mm</option>
                </select>
              </div>
              <div className="form-group">
                <label>Customer Name</label>
                <input value={form.customer_name} onChange={e => setForm(f=>({...f,customer_name:e.target.value}))} />
              </div>
              <div className="form-group">
                <label>Customer Email</label>
                <input type="email" value={form.customer_email} onChange={e => setForm(f=>({...f,customer_email:e.target.value}))} />
              </div>
              <div className="form-group">
                <label>Customer Reference</label>
                <input value={form.customer_ref} onChange={e => setForm(f=>({...f,customer_ref:e.target.value}))} />
              </div>
              <div className="form-group">
                <label>Required Date</label>
                <input type="date" value={form.required_date} onChange={e => setForm(f=>({...f,required_date:e.target.value}))} />
              </div>
            </div>
          </div>

          {/* Items */}
          {form.items.map((item, idx) => (
            <div key={idx} className="card mb-4">
              <div className="flex justify-between items-center" style={{ marginBottom:'16px' }}>
                <h3 style={{ fontSize:'14px', fontWeight:600 }}>
                  Variant {idx+1}: {item.variant_name || 'Unnamed'}
                </h3>
                <div style={{ display:'flex', gap:'8px' }}>
                  <button className="btn btn-ghost btn-sm" onClick={() => setExpandedItem(expandedItem===idx?-1:idx)}>
                    {expandedItem===idx ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}
                  </button>
                  {form.items.length > 1 && (
                    <button className="btn btn-danger btn-sm" onClick={() => removeItem(idx)}>
                      <Trash2 size={14}/>
                    </button>
                  )}
                </div>
              </div>

              {expandedItem === idx && (
                <>
                  <div className="form-grid-3">
                    <div className="form-group" style={{ gridColumn:'1/3' }}>
                      <label>Variant Name</label>
                      <input value={item.variant_name} onChange={e => {
                        const items = [...form.items]; items[idx].variant_name = e.target.value; setForm(f=>({...f,items}));
                      }} placeholder="e.g. 01-Childrens tops, single size-0010" />
                    </div>
                    <div className="form-group">
                      <label>Quantity</label>
                      <input type="number" value={item.quantity} onChange={e => {
                        const items = [...form.items]; items[idx].quantity = parseInt(e.target.value)||0; setForm(f=>({...f,items}));
                      }} />
                    </div>
                  </div>

                  {/* Sizes */}
                  <p style={{ fontSize:'12px', fontWeight:600, color:'var(--text-secondary)', marginBottom:'10px', letterSpacing:'0.5px', textTransform:'uppercase' }}>Size Markets</p>
                  <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:'12px', marginBottom:'20px' }}>
                    {['EUR','US','CA','MX','CN','AUS','UK','BR'].map(mkt => (
                      <div className="form-group" key={mkt} style={{ marginBottom:0 }}>
                        <label>{mkt}</label>
                        <input value={item.sizes[mkt]||''} onChange={e => {
                          const items = [...form.items]; items[idx].sizes[mkt] = e.target.value; setForm(f=>({...f,items}));
                        }} placeholder="—" />
                      </div>
                    ))}
                  </div>

                  {/* Label fields */}
                  <div className="form-grid-3">
                    {[
                      ['Order Number','order_number'],
                      ['Product Number','product_number'],
                      ['Season Code','season_code'],
                      ['Country of Origin','country_of_origin'],
                      ['Tape Color','tape_color'],
                      ['Supplier Style','supplier_style'],
                    ].map(([lbl, key]) => (
                      <div className="form-group" key={key}>
                        <label>{lbl}</label>
                        <input value={item[key]||''} onChange={e => {
                          const items = [...form.items]; items[idx][key] = e.target.value; setForm(f=>({...f,items}));
                        }} />
                      </div>
                    ))}
                  </div>

                  {/* Layout variant */}
                  <div className="form-group">
                    <label>Layout Variant</label>
                    <select value={item.layout_variant} onChange={e => {
                      const items = [...form.items]; items[idx].layout_variant = e.target.value; setForm(f=>({...f,items}));
                    }}>
                      <option value="logo_with_size">Logo + Size Grid</option>
                      <option value="logo_without_size">Logo only (no size)</option>
                      <option value="without_logo_with_size">No logo + Size Grid</option>
                      <option value="without_logo_without_size">No logo, no size</option>
                    </select>
                  </div>
                </>
              )}
            </div>
          ))}

          <div style={{ display:'flex', gap:'12px', marginBottom:'24px' }}>
            <button className="btn btn-ghost" onClick={addItem}>
              <Plus size={15}/> Add Size Variant
            </button>
          </div>

          <button className="btn btn-primary btn-lg" onClick={handleFormSubmit} disabled={loading}>
            {loading ? <><span className="spinner"/> Creating…</> : 'Create Order →'}
          </button>
        </div>
      )}
    </div>
  );
}
