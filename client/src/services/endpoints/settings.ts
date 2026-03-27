import { get, patch, post } from '../apiClient';

export type AiTone = 'professional' | 'friendly' | 'concise' | 'persuasive' | 'empathetic';
export type AutoLevel = 'off' | 'assist' | 'auto';

// User Settings Response from backend
export interface UserSettings {
  // Email Settings
  auto_sync_replies: boolean;
  sync_sent_folder: boolean;
  sync_frequency: '5m' | '15m' | '30m';
  
  // AI Settings
  automation_level: 'off' | 'assist' | 'auto';
  learn_from_edits: boolean;
  personalize_per_lead: boolean;
  avoid_repetition: boolean;
  max_reply_length: 'short' | 'medium' | 'long';
  
  // Automation Settings
  automation_enabled: boolean;
  pause_on_weekends: boolean;
  respect_sending_hours: boolean;
  delay_between_steps: '1d' | '3d' | '7d';
  stop_on_reply: boolean;
  max_emails_per_lead: number;
  
  // Notification Settings
  email_new_reply: boolean;
  email_campaign_complete: boolean;
  email_lead_status: boolean;
  email_weekly_digest: boolean;
  inapp_realtime_replies: boolean;
  inapp_ai_actions: boolean;
  inapp_team_activity: boolean;
  inapp_system_alerts: boolean;
  notification_batching: 'instant' | 'hourly' | 'daily';
  
  // Security Settings
  two_factor_enabled: boolean;
  require_2fa_for_team: boolean;
  
  // Team Settings
  workspace_name: string | null;
  default_member_role: 'viewer' | 'member' | 'admin';
  invite_by_domain: boolean;
  require_admin_approval: boolean;
  
  // Data & Privacy Settings
  analytics_improvement: boolean;
  personalization_data: boolean;
  third_party_integrations: boolean;
}

export type UpdateUserSettingsRequest = Partial<UserSettings>;

export const settingsApi = {
  // Get user settings
  getSettings: () => get<UserSettings>('/user-service/settings'),
  
  // Update user settings (partial update)
  updateSettings: (data: UpdateUserSettingsRequest) => patch<UserSettings>('/user-service/settings', data),
  
  // Reset settings to defaults
  resetSettings: () => post<UserSettings>('/user-service/settings/reset', {}),
};
