import axios from 'axios';

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({ baseURL: BASE });

// ── Orders ──────────────────────────────────────────────────────────────────
export const uploadXML = (formData) =>
  api.post('/orders/upload-xml', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

export const createOrder = (payload) => api.post('/orders/', payload);
export const listOrders  = (skip=0, limit=50) => api.get(`/orders/?skip=${skip}&limit=${limit}`);
export const getOrder    = (orderId) => api.get(`/orders/${orderId}`);

// ── Artwork ──────────────────────────────────────────────────────────────────
export const generateItem    = (itemId)   => api.post(`/artwork/generate/${itemId}`);
export const generateOrder   = (orderId)  => api.post(`/artwork/generate-order/${orderId}`);
export const getArtworkInfo  = (artworkId)=> api.get(`/artwork/${artworkId}`);

export const artworkPngUrl       = (artworkId) => `${BASE}/artwork/${artworkId}/png`;
export const artworkPdfUrl       = (artworkId) => `${BASE}/artwork/${artworkId}/pdf`;
export const artworkThumbnailUrl = (artworkId) => `${BASE}/artwork/${artworkId}/thumbnail`;

// ── Approvals ────────────────────────────────────────────────────────────────
export const listPending       = ()           => api.get('/approvals/pending');
export const submitApproval    = (artworkId, payload) => api.post(`/approvals/${artworkId}`, payload);
export const getApprovalHistory= (artworkId)  => api.get(`/approvals/history/${artworkId}`);

export default api;
