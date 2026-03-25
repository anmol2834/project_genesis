import { get, patch, post } from '../apiClient';

export type AiTone = 'professional' | 'friendly' | 'concise' | 'persuasive' | 'empathetic';
export type AutoLevel = 'off' | 'assist' | 'auto';

export interface UserProfile {
  name: string; email: string; title: string;
  company: string; industry: string; website: string; avatarUrl?: string;
}

export interface AiSettings {
  tone: AiTone; automationLevel: AutoLevel;
  customInstructions: string;
  learnFromEdits: boolean; personalizePerLead: boolean;
  avoidRepetition: boolean; maxReplyLength: 'short' | 'medium' | 'long';
}

export interface NotificationSettings {
  emailNewReply: boolean; emailCampaignComplete: boolean;
  emailLeadStatus: boolean; emailWeeklyDigest: boolean;
  inAppReplies: boolean; inAppAI: boolean; inAppTeam: boolean; inAppSystem: boolean;
  frequency: 'instant' | 'hourly' | 'daily';
}

export const settingsApi = {
  profile:              ()                          => get<UserProfile>('/settings/profile'),
  updateProfile:        (p: Partial<UserProfile>)   => patch<UserProfile>('/settings/profile', p),
  aiSettings:           ()                          => get<AiSettings>('/settings/ai'),
  updateAiSettings:     (p: Partial<AiSettings>)    => patch<AiSettings>('/settings/ai', p),
  notifications:        ()                          => get<NotificationSettings>('/settings/notifications'),
  updateNotifications:  (p: Partial<NotificationSettings>) => patch<NotificationSettings>('/settings/notifications', p),
  exportData:           (type: 'leads' | 'campaigns' | 'emails') => post<{ downloadUrl: string }>('/settings/export', { type }),
  deleteAccount:        ()                          => post<void>('/settings/delete-account'),
};
