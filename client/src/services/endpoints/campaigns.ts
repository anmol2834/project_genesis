import { get, post, patch, del } from '../apiClient';

export type CampaignStatus = 'running' | 'paused' | 'draft';

export interface Campaign {
  id: string;
  name: string;
  status: CampaignStatus;
  emailsSent: number;
  emailsTotal: number;
  openRate: number;
  replyRate: number;
  lastActivity: string;
  createdAt: string;
  accentColor: string;
  aiInsight: string;
  insightType: 'positive' | 'warning' | 'neutral';
  tags: string[];
}

export interface CreateCampaignPayload {
  name: string;
  tags?: string[];
  emailsTotal?: number;
}

export interface UpdateCampaignPayload {
  name?: string;
  status?: CampaignStatus;
  tags?: string[];
}

export const campaignsApi = {
  list:   ()                                    => get<Campaign[]>('/campaigns'),
  get:    (id: string)                          => get<Campaign>(`/campaigns/${id}`),
  create: (payload: CreateCampaignPayload)      => post<Campaign>('/campaigns', payload),
  update: (id: string, p: UpdateCampaignPayload) => patch<Campaign>(`/campaigns/${id}`, p),
  delete: (id: string)                          => del<void>(`/campaigns/${id}`),
  pause:  (id: string)                          => patch<Campaign>(`/campaigns/${id}/pause`),
  resume: (id: string)                          => patch<Campaign>(`/campaigns/${id}/resume`),
};
