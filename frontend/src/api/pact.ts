import api from './client';
import { Mandate, Proposal, AuditLogEntry, PolicyResult, Product } from '../types';

export interface ProposalGenerationResponse {
  proposal: Proposal;
  policy: PolicyResult;
  message: string;
}

export interface PayPalOrderResponse {
  order_id: string;
  approve_url: string;
  proposal: Proposal;
}

export interface PayPalCaptureResponse {
  proposal: Proposal;
  capture_id: string;
  status: string;
  message: string;
}

export const pactApi = {
  // Mandates
  getMandates: async (): Promise<Mandate[]> => {
    return api.get<Mandate[]>('/mandates');
  },

  getMandate: async (id: string): Promise<Mandate> => {
    return api.get<Mandate>(`/mandates/${id}`);
  },

  createMandate: async (mandate: Partial<Mandate>): Promise<Mandate> => {
    return api.post<Mandate>('/mandates', mandate);
  },

  updateMandate: async (id: string, updates: Partial<Mandate>): Promise<Mandate> => {
    return api.put<Mandate>(`/mandates/${id}`, updates);
  },

  // Products
  getProducts: async (): Promise<Product[]> => {
    return api.get<Product[]>('/products');
  },

  // Proposals & AI Agent
  generateProposal: async (prompt: string, mandate_id: string): Promise<ProposalGenerationResponse> => {
    return api.post<ProposalGenerationResponse>('/proposals/generate', { prompt, mandate_id });
  },

  getProposals: async (): Promise<Proposal[]> => {
    return api.get<Proposal[]>('/proposals');
  },

  getProposal: async (id: string): Promise<Proposal> => {
    return api.get<Proposal>(`/proposals/${id}`);
  },

  approveProposal: async (id: string): Promise<Proposal> => {
    return api.post<Proposal>(`/proposals/${id}/approve`);
  },

  rejectProposal: async (id: string): Promise<Proposal> => {
    return api.post<Proposal>(`/proposals/${id}/reject`);
  },

  // Payments (PayPal)
  createPayPalOrder: async (proposal_id: string): Promise<PayPalOrderResponse> => {
    return api.post<PayPalOrderResponse>(`/payments/${proposal_id}/create-order`);
  },

  capturePayPalPayment: async (proposal_id: string): Promise<PayPalCaptureResponse> => {
    return api.post<PayPalCaptureResponse>(`/payments/${proposal_id}/capture`);
  },

  getPayPalOrderStatus: async (proposal_id: string): Promise<any> => {
    return api.get(`/payments/${proposal_id}/status`);
  },

  // Audit Logs
  getAuditLogs: async (limit: number = 50): Promise<AuditLogEntry[]> => {
    return api.get<AuditLogEntry[]>(`/audit?limit=${limit}`);
  },
};
