import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Download, ArrowLeft, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { getApprovalSheetData, artworkPngUrl, approvalSheetPdfUrl } from '../api/client';

export default function ApprovalPreview() {
  const { orderId, artworkId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getApprovalSheetData(artworkId)
      .then(res => {
        setData(res.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load approval preview data', err);
        setLoading(false);
      });
  }, [artworkId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted" style={{ padding: '64px' }}>
        <div className="spinner" /> Loading full preview...
      </div>
    );
  }

  if (!data) {
    return <div className="alert alert-error">Failed to load preview data.</div>;
  }

  // Format date
  const submitDate = new Date(data.submitted_date).toLocaleDateString('en-GB');

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
      {/* ── Page Header & Actions (Not part of printed sheet) ── */}
      <div className="flex justify-between items-center page-header no-print">
        <div className="flex items-center gap-4">
          <button className="btn btn-ghost" onClick={() => navigate(`/orders/${orderId}`)}>
            <ArrowLeft size={16} /> Back to Order
          </button>
          <div>
            <h1 style={{ fontSize: '20px', margin: 0 }}>Approval Preview</h1>
            <p style={{ margin: 0 }}>{data.bgp_order_id} — {data.variant_name}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <a
            href={approvalSheetPdfUrl(artworkId)}
            download
            className="btn btn-primary"
          >
            <Download size={16} /> Download PDF
          </a>
          <div style={{ width: '1px', height: '24px', background: 'var(--border)' }}></div>
          <button className="btn btn-danger"><XCircle size={16} /> Reject</button>
          <button className="btn btn-success"><CheckCircle size={16} /> Approve</button>
        </div>
      </div>

      {/* ── Approval Sheet Canvas (Matches TOK100 PDF) ── */}
      <div className="approval-sheet bg-white border shadow-md relative mx-auto"
           style={{
             width: '1400px', // Fixed width to approximate A2 proportion
             minHeight: '800px',
             padding: '40px',
             fontFamily: "'Helvetica Neue', Helvetica, Arial, sans-serif"
           }}>
        
        {/* 1. Header Box */}
        <div style={{
          display: 'flex',
          border: '1px solid #ccc',
          marginBottom: '24px'
        }}>
          {/* Logo */}
          <div style={{
            width: '300px',
            borderRight: '1px solid #ccc',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px'
          }}>
            <h1 style={{ color: '#2b8f41', fontSize: '32px', margin: 0, fontWeight: 'bold' }}>
              <span style={{ fontSize: '36px' }}>❖</span> Sainmarks<span style={{ fontSize: '14px', verticalAlign: 'super' }}>®</span>
            </h1>
          </div>
          
          {/* Info table */}
          <div style={{ flex: 1, borderRight: '1px solid #ccc', fontSize: '13px' }}>
            <div style={{ padding: '8px 16px', borderBottom: '1px solid #ccc' }}>BUYER : {data.buyer}</div>
            <div style={{ padding: '8px 16px', borderBottom: '1px solid #ccc' }}>CUSTOMER : {data.customer_name}</div>
            <div style={{ padding: '8px 16px', borderBottom: '1px solid #ccc' }}>DESIGN CODE : {data.design_code}</div>
            <div style={{ padding: '8px 16px', borderBottom: '1px solid #ccc' }}>PRODUCT CODE : {data.product_code}</div>
            <div style={{ padding: '8px 16px' }}>SUBMITTED DATE : {submitDate}</div>
          </div>
          
          {/* Approval text */}
          <div style={{
            width: '250px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            textAlign: 'center',
            fontWeight: '600',
            fontSize: '15px'
          }}>
            ARTWORK<br/>FOR<br/>APPROVAL
          </div>
        </div>

        {/* 2. Red Title */}
        <h2 style={{
          color: '#d62027',
          textAlign: 'center',
          fontSize: '22px',
          fontWeight: 'bold',
          marginBottom: '8px'
        }}>
          {data.variant_name}
        </h2>
        <div style={{
          textAlign: 'center',
          fontSize: '16px',
          fontWeight: 'bold',
          marginBottom: '32px'
        }}>
          {data.label_size}
        </div>

        {/* 3. Label Grid Wrapper */}
        <div style={{
          display: 'flex',
          borderTop: '1px solid #ccc',
          paddingTop: '20px'
        }}>
          {/* Front Column */}
          <div style={{
            width: '240px',
            borderRight: '1px solid #ccc',
            paddingRight: '30px'
          }}>
            <h3 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '20px' }}>Front</h3>
            {/* Front Tag mock */}
            <div style={{
              width: '180px',
              height: '360px',
              background: '#0f172a', /* dark navy */
              position: 'relative',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)'
            }}>
              <div style={{
                position: 'absolute', top: '20px', left: '50%', transform: 'translateX(-50%)',
                width: '12px', height: '12px', borderRadius: '50%', background: 'white'
              }}></div>
              <div style={{ color: '#eab308', textAlign: 'center' }}>
                <div style={{ fontSize: '48px', fontWeight: '300', letterSpacing: '-1px' }}>OVS</div>
                <div style={{ fontSize: '24px', fontWeight: 'bold' }}>kids</div>
              </div>
            </div>
          </div>

          {/* Back Variants Row */}
          <div style={{ flex: 1, paddingLeft: '30px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '20px' }}>Back</h3>
            <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
              {data.all_variants.map((v, idx) => (
                <div key={idx} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  {v.has_artwork && v.artwork_id ? (
                    <img 
                      src={artworkPngUrl(v.artwork_id)} 
                      alt={v.variant_name} 
                      style={{ height: '360px', objectFit: 'contain', border: '1px solid #eee', background: 'white' }} 
                    />
                  ) : (
                    <div style={{ width: '130px', height: '360px', background: '#f8fafc', border: '1px dashed #ccc', display:'flex', alignItems:'center', justifyContent:'center', fontSize:'12px', color:'#999' }}>
                      No Artwork
                    </div>
                  )}
                  <div style={{ marginTop: '16px', fontWeight: 'bold', fontSize: '16px' }}>
                    Qty - {v.quantity}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

      </div>
      
      {/* Print styles */}
      <style>{`
        @media print {
          .sidebar, .page-header.no-print { display: none !important; }
          .main-content { margin: 0 !important; padding: 0 !important; }
          body { background: white !important; }
          .approval-sheet { border: none !important; box-shadow: none !important; margin: 0 !important; width: 100% !important; padding: 20px !important; }
          @page { size: landscape; margin: 1cm; }
        }
      `}</style>
    </div>
  );
}
