import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Download, ArrowLeft, ChevronLeft, ChevronRight } from 'lucide-react';
import { getApprovalSheetData, artworkPngUrl, approvalSheetPdfUrl } from '../api/client';

// ── Small sub-components ────────────────────────────────────────────────────

function HeaderBox({ data }) {
  return (
    <div style={{
      display: 'flex',
      border: '1px solid #bbb',
      marginBottom: '28px',
      fontFamily: 'Arial, Helvetica, sans-serif',
      fontSize: '12px',
    }}>
      {/* Col 1 – Sainmarks logo */}
      <div style={{
        width: '200px',
        borderRight: '1px solid #bbb',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
        gap: '4px',
      }}>
        {/* Diamond icon approximation */}
        <div style={{ fontSize: '28px', color: '#2b8f41', lineHeight: 1 }}>✦</div>
        <div style={{ fontWeight: '700', fontSize: '16px', color: '#1a1a1a', letterSpacing: '0.5px' }}>
          Sainmarks<sup style={{ fontSize: '8px' }}>®</sup>
        </div>
      </div>

      {/* Col 2 – info rows */}
      <div style={{ flex: 1, borderRight: '1px solid #bbb' }}>
        {[
          ['BUYER',          data.buyer],
          ['CUSTOMER',       data.customer_name],
          ['DESIGN CODE',    data.design_code],
          ['PRODUCT CODE',   data.product_code],
          ['SUBMITTED DATE', data.submitted_date],
        ].map(([label, value], i) => (
          <div key={label} style={{
            padding: '7px 12px',
            borderBottom: i < 4 ? '1px solid #ddd' : 'none',
            display: 'flex',
            gap: '6px',
          }}>
            <span style={{ color: '#444', fontWeight: '600', minWidth: '130px' }}>{label} :</span>
            <span style={{ color: '#111' }}>{value || '—'}</span>
          </div>
        ))}
      </div>

      {/* Col 3 – ARTWORK FOR APPROVAL */}
      <div style={{
        width: '160px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        fontWeight: '700',
        fontSize: '13px',
        lineHeight: '1.6',
        color: '#1a1a1a',
        padding: '12px',
      }}>
        ARTWORK<br />FOR<br />APPROVAL
      </div>
    </div>
  );
}

function FrontTag() {
  return (
    <div style={{
      width: '110px',
      height: '280px',
      background: '#0d1526',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      position: 'relative',
      flexShrink: 0,
    }}>
      {/* Punch hole */}
      <div style={{
        position: 'absolute',
        top: '14px',
        width: '10px', height: '10px',
        borderRadius: '50%',
        background: 'white',
      }} />
      {/* OVS */}
      <div style={{
        color: '#e8b519',
        fontWeight: '800',
        fontSize: '34px',
        letterSpacing: '-1px',
        lineHeight: 1,
        fontFamily: 'Arial Black, Arial, sans-serif',
      }}>OVS</div>
      {/* kids */}
      <div style={{
        color: '#e8b519',
        fontWeight: '700',
        fontSize: '18px',
        fontFamily: 'Arial, sans-serif',
        marginTop: '2px',
      }}>kids</div>
      {/* Pink line at bottom */}
      <div style={{
        position: 'absolute',
        bottom: '22px',
        left: 0, right: 0,
        height: '2px',
        background: '#e02070',
      }} />
    </div>
  );
}

function BackTag({ variant }) {
  if (!variant.has_artwork || !variant.artwork_id) {
    return (
      <div style={{
        width: '100px',
        height: '280px',
        border: '1.5px dashed #bbb',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '11px',
        color: '#999',
        flexShrink: 0,
      }}>
        No Artwork
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '10px',
      flexShrink: 0,
    }}>
      <div style={{
        border: '1.5px solid #d0338e',
        padding: '2px',
        background: 'white',
      }}>
        <img
          key={variant.artwork_id}
          src={artworkPngUrl(variant.artwork_id) + `?v=${variant.artwork_id}`}
          alt={`Artwork ${variant.sizes?.YEARS || ''}`}
          style={{
            width: '100px',
            height: '280px',
            objectFit: 'contain',
            display: 'block',
            background: 'white',
          }}
          onError={e => { e.target.style.opacity = '0.2'; }}
        />
      </div>
    </div>
  );
}

function GroupPage({ group, header }) {
  return (
    <div style={{
      background: 'white',
      padding: '40px 50px',
      minHeight: '700px',
      fontFamily: 'Arial, Helvetica, sans-serif',
      color: '#111',
    }}>
      <HeaderBox data={header} />

      {/* Red Title */}
      <div style={{
        textAlign: 'center',
        color: '#cc0000',
        fontWeight: '700',
        fontSize: '17px',
        marginBottom: '8px',
        letterSpacing: '0.3px',
      }}>
        {group.title}
      </div>

      {/* Label size */}
      <div style={{
        textAlign: 'center',
        fontWeight: '700',
        fontSize: '13px',
        marginBottom: '32px',
        color: '#111',
      }}>
        {group.label_size}
      </div>

      {/* Front / Back row */}
      <div style={{ display: 'flex', gap: '24px' }}>
        {/* Front column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'flex-start' }}>
          <div style={{ fontWeight: '700', fontSize: '13px', marginBottom: '4px' }}>Front</div>
          <FrontTag />
          {/* Qty spacer */}
          <div style={{ height: '30px' }} />
        </div>

        {/* Back tags flex row */}
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
          <div style={{ fontWeight: '700', fontSize: '13px', marginBottom: '4px' }}>Back</div>
          <div style={{ display: 'flex', gap: '14px', flexWrap: 'nowrap', overflowX: 'auto' }}>
            {group.variants.map((v, idx) => (
              <div key={idx} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
                <BackTag variant={v} />
                <div style={{ fontWeight: '700', fontSize: '13px', whiteSpace: 'nowrap' }}>
                  Qty - {v.quantity}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function ApprovalPreview() {
  const { orderId, artworkId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activePage, setActivePage] = useState(0);

  useEffect(() => {
    setLoading(true);
    getApprovalSheetData(artworkId)
      .then(res => {
        setData(res.data);
        setLoading(false);
      })
      .catch(err => {
        const detail = err?.response?.data?.detail || err.message || 'Unknown error';
        setError(detail);
        setLoading(false);
      });
  }, [artworkId]);

  if (loading) return (
    <div style={{ textAlign: 'center', padding: '80px' }}>
      <div className="spinner" style={{ margin: '0 auto', width: 36, height: 36 }} />
      <p className="text-muted" style={{ marginTop: '16px' }}>Loading approval sheet…</p>
    </div>
  );

  if (error) return (
    <div style={{ padding: '40px' }}>
      <div className="alert alert-error">⚠ {error}</div>
    </div>
  );

  if (!data) return null;

  const groups = data.country_groups || [];
  const totalPages = groups.length;
  const currentGroup = groups[activePage] || null;

  const headerData = {
    buyer:          data.buyer,
    customer_name:  data.customer_name,
    design_code:    data.design_code,
    product_code:   data.product_code,
    submitted_date: data.submitted_date,
  };

  return (
    <div>
      {/* ── Screen action bar (not printed) ── */}
      <div className="page-header" style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <button className="btn btn-ghost" onClick={() => navigate(`/orders/${orderId}`)}>
              <ArrowLeft size={16} /> Back to Order
            </button>
            <div>
              <h1 style={{ fontSize: '18px', margin: 0 }}>Approval Preview</h1>
              <p style={{ margin: 0, fontSize: '13px', opacity: 0.7 }}>
                {data.bgp_order_id} — {totalPages} market group{totalPages !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
          <a
            href={approvalSheetPdfUrl(artworkId)}
            download
            className="btn btn-primary"
          >
            <Download size={16} /> Download Full PDF
          </a>
        </div>

        {/* Page switcher */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '16px' }}>
            <button className="btn btn-ghost btn-sm"
              disabled={activePage === 0}
              onClick={() => setActivePage(p => p - 1)}>
              <ChevronLeft size={14} /> Prev
            </button>
            {groups.map((g, i) => (
              <button key={i}
                className={`btn btn-sm ${i === activePage ? 'btn-primary' : 'btn-ghost'}`}
                onClick={() => setActivePage(i)}
                style={{ minWidth: '80px' }}>
                {g.country}
              </button>
            ))}
            <button className="btn btn-ghost btn-sm"
              disabled={activePage === totalPages - 1}
              onClick={() => setActivePage(p => p + 1)}>
              Next <ChevronRight size={14} />
            </button>
          </div>
        )}
      </div>

      {/* ── Approval Sheet Card (mimics print page) ── */}
      <div style={{
        background: '#f0f0f0',
        padding: '32px',
        borderRadius: '8px',
        overflowX: 'auto',
      }}>
        <div style={{
          maxWidth: '1300px',
          margin: '0 auto',
          boxShadow: '0 4px 32px rgba(0,0,0,0.18)',
          borderRadius: '2px',
          overflow: 'hidden',
        }}>
          {currentGroup ? (
            <GroupPage group={currentGroup} header={headerData} />
          ) : (
            <div style={{ padding: '60px', textAlign: 'center', background: 'white', color: '#999' }}>
              No groups found.
            </div>
          )}
        </div>

        {/* Page indicator */}
        {totalPages > 0 && (
          <div style={{ textAlign: 'center', marginTop: '12px', color: '#888', fontSize: '12px' }}>
            Page {activePage + 1} of {totalPages}
          </div>
        )}
      </div>
    </div>
  );
}
