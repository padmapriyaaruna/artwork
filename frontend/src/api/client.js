import axios from 'axios';

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// Log the resolved API base so we can verify in browser console
console.log('[API] Base URL:', BASE);

const api = axios.create({
  baseURL: BASE,
  timeout: 90000,   // 90s — covers Render free-tier cold-start (up to ~60s)
});

// ── Orders ──────────────────────────────────────────────────────────────────
export const uploadXML = (formData) =>
  api.post('/orders/upload-xml', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,  // PDF processing can take longer
  });

export const uploadZIP = (formData) =>
  api.post('/orders/upload-zip', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,  // PDF→SVG conversion can take longer
  });

export const createOrder = (payload) => api.post('/orders/', payload);
export const listOrders  = (skip=0, limit=50) => api.get(`/orders/?skip=${skip}&limit=${limit}`);
export const getOrder    = (orderId) => api.get(`/orders/${orderId}`);

// ── Artwork ──────────────────────────────────────────────────────────────────
export const generateItem    = (itemId)    => api.post(`/artwork/generate/${itemId}`);
export const generateOrder   = (orderId)   => api.post(`/artwork/generate-order/${orderId}`);
export const getArtworkInfo  = (artworkId) => api.get(`/artwork/${artworkId}`);

export const artworkPngUrl       = (artworkId) => `${BASE}/artwork/${artworkId}/png`;
export const artworkPdfUrl       = (artworkId) => `${BASE}/artwork/${artworkId}/pdf`;
export const artworkThumbnailUrl = (artworkId) => `${BASE}/artwork/${artworkId}/thumbnail`;
export const getApprovalSheetData = (artworkId) => api.get(`/artwork/${artworkId}/approval-sheet`);
export const approvalSheetPdfUrl  = (artworkId) => `${BASE}/artwork/${artworkId}/approval-pdf`;

// ── Approvals ────────────────────────────────────────────────────────────────
export const listPending        = ()                       => api.get('/approvals/pending');
export const submitApproval     = (artworkId, payload)     => api.post(`/approvals/${artworkId}`, payload);
export const getApprovalHistory = (artworkId)              => api.get(`/approvals/history/${artworkId}`);

export default api;
