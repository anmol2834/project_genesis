import { get, post, patch, del } from '../apiClient';

export type LeadStatus = 'new' | 'contacted' | 'engaged' | 'unresponsive';
export type LeadTag = 'hot' | 'warm' | 'cold' | 'vip' | 'decision-maker' | 'technical';

export interface Lead {
  id: string;
  name: string;
  email: string;
  company: string;
  role: string;
  status: LeadStatus;
  tags: LeadTag[];
  campaign: string | null;
  lastActivity: string;
  addedAt: string;
  avatarColor: string;
  score: number;
}

export interface LeadsListParams {
  page?:    number;
  limit?:   number;
  status?:  LeadStatus;
  search?:  string;
  campaign?: string;
}

export interface LeadsListResponse {
  data:  Lead[];
  total: number;
  page:  number;
  limit: number;
}

export interface CreateLeadPayload {
  name: string;
  email: string;
  company?: string;
  role?: string;
  tags?: LeadTag[];
  campaign?: string;
}

export interface ImportLeadsPayload {
  file: File;
}

export const leadsApi = {
  list:   (params?: LeadsListParams)          => get<LeadsListResponse>('/leads', { params }),
  get:    (id: string)                        => get<Lead>(`/leads/${id}`),
  create: (payload: CreateLeadPayload)        => post<Lead>('/leads', payload),
  update: (id: string, p: Partial<Lead>)      => patch<Lead>(`/leads/${id}`, p),
  delete: (id: string)                        => del<void>(`/leads/${id}`),
  import: (formData: FormData)                => post<{ imported: number; duplicates: number; skipped: number }>('/leads/import', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
};
