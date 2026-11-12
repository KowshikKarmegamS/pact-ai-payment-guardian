import api from './client';
import type {
  AuditLogEntry,
  AuthorizationReceipt,
  Mandate,
  MandateInput,
  PaymentStateResponse,
  PayPalOrderResponse,
  ConnectedAgent,
  OwnerSession,
  ConnectedAgentCreated,
  AnalyticsDataset,
  Channel3SearchResult,
  ConnectorSyncResult,
  RetailerHandoff,
  MerchantConnector,
  Product,
  ProductUpdateResult,
  Proposal,
  ProposalGenerationResponse,
  SystemStatus,
} from '../types';

export const pactApi = {
  // Owner session (Control Center sign-in)
  getOwnerSession: () => api.get<OwnerSession>('/owner/session'),
  ownerLogin: (password: string) => api.post<OwnerSession>('/owner/login', { password }),
  ownerLogout: () => api.post<OwnerSession>('/owner/logout'),

  getStatus: (checkPayPal = false) => api.get<SystemStatus>(`/status${checkPayPal ? '?check_paypal=true' : ''}`),

  // Mandates
  getMandates: () => api.get<Mandate[]>('/mandates'),
  createMandate: (mandate: MandateInput) => api.post<Mandate>('/mandates', mandate),
  updateMandate: (id: string, updates: MandateInput) => api.put<Mandate>(`/mandates/${id}`, updates),
  revokeMandate: (id: string) => api.post<Mandate>(`/mandates/${id}/revoke`),

  // Catalog
  getProducts: () => api.get<Product[]>('/products'),
  updateProduct: (id: number, updates: { price?: string; in_stock?: boolean }) =>
    api.put<ProductUpdateResult>(`/products/${id}`, updates),
  getConnectors: () => api.get<MerchantConnector[]>('/connectors'),
  getAnalytics: () => api.get<AnalyticsDataset>('/analytics/dataset'),
  syncConnector: (id: string) => api.post<ConnectorSyncResult>(`/connectors/${id}/sync`),
  searchChannel3: (query: string, limit = 12) => api.post<Channel3SearchResult>('/connectors/channel3/search', { query, limit }),
  retailerHandoff: (id: string) => api.post<RetailerHandoff>(`/payments/${id}/retailer-handoff`),

  // Proposals
  generateProposal: (prompt: string, mandate_id: string, source: 'demo-store' | 'channel3' = 'demo-store') =>
    api.post<ProposalGenerationResponse>('/proposals/generate', { prompt, mandate_id, source }),
  proposeProduct: (mandate_id: string, product_id: number, source_proposal_id?: string) =>
    api.post<ProposalGenerationResponse>('/proposals/propose', { mandate_id, product_id, source_proposal_id }),
  getProposals: () => api.get<Proposal[]>('/proposals'),
  getReceipt: (id: string) => api.get<AuthorizationReceipt>(`/proposals/${id}/receipt`),
  approveProposal: (id: string, expectedFingerprint: string) =>
    api.post<Proposal>(`/proposals/${id}/approve`, { expected_fingerprint: expectedFingerprint }),
  rejectProposal: (id: string) => api.post<Proposal>(`/proposals/${id}/reject`),
  reEvaluateProposal: (id: string) => api.post<ProposalGenerationResponse>(`/proposals/${id}/re-evaluate`),

  // PayPal
  createPayPalOrder: (proposalId: string) => api.post<PayPalOrderResponse>(`/payments/${proposalId}/create-order`),
  verifyPayPalOrder: (proposalId: string, orderToken?: string) =>
    api.post<PaymentStateResponse>(`/payments/${proposalId}/verify`, orderToken ? { order_token: orderToken } : {}),
  cancelPayPalCheckout: (proposalId: string) => api.post<PaymentStateResponse>(`/payments/${proposalId}/cancel`),
  capturePayPalPayment: (proposalId: string) => api.post<PaymentStateResponse>(`/payments/${proposalId}/capture`),

  // Agent Gateway (Control Center side)
  getAgents: () => api.get<ConnectedAgent[]>('/agents'),
  createAgent: (body: { name: string; description?: string; mandate_ids: string[] }) =>
    api.post<ConnectedAgentCreated>('/agents', body),
  revokeAgent: (id: string) => api.post<ConnectedAgent>(`/agents/${id}/revoke`),

  // Audit
  getAuditLogs: (limit = 300) => api.get<AuditLogEntry[]>(`/audit?limit=${limit}`),
};
