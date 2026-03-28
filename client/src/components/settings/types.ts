/**
 * Settings Page Types
 * Centralized type definitions for settings components
 */

import type { Theme } from '@mui/material';
import type { UpdateProfileResponse } from '@/services/endpoints/profile';

// User Settings from API
export interface UserSettings {
  // Email Settings
  auto_sync_replies?: boolean;
  sync_sent_folder?: boolean;
  sync_frequency?: '5m' | '15m' | '30m';
  
  // AI Settings
  automation_level?: 'off' | 'assist' | 'auto';
  learn_from_edits?: boolean;
  personalize_per_lead?: boolean;
  avoid_repetition?: boolean;
  max_reply_length?: 'short' | 'medium' | 'long';
  
  // Automation Settings
  automation_enabled?: boolean;
  pause_on_weekends?: boolean;
  respect_sending_hours?: boolean;
  delay_between_steps?: '1d' | '3d' | '7d';
  stop_on_reply?: boolean;
  max_emails_per_lead?: number;
  
  // Notification Settings
  email_new_reply?: boolean;
  email_campaign_complete?: boolean;
  email_lead_status?: boolean;
  email_weekly_digest?: boolean;
  inapp_realtime_replies?: boolean;
  inapp_ai_actions?: boolean;
  inapp_team_activity?: boolean;
  inapp_system_alerts?: boolean;
  notification_batching?: 'instant' | 'hourly' | 'daily';
  
  // Security Settings
  two_factor_enabled?: boolean;
  require_2fa_for_team?: boolean;
  
  // Team Settings
  workspace_name?: string | null;
  default_member_role?: 'viewer' | 'member' | 'admin';
  invite_by_domain?: boolean;
  require_admin_approval?: boolean;
  
  // Data & Privacy Settings
  analytics_improvement?: boolean;
  personalization_data?: boolean;
  third_party_integrations?: boolean;
}

// User Profile from API
export interface UserProfile {
  user_id?: string;
  email?: string;
  full_name?: string;
  profile_pic?: string;
  business_name?: string;
  business_type?: string;
  industries?: string[];
  country?: string;
  timezone?: string;
  business_description?: string;
  target_audience?: string;
  communication_tone?: string;
  use_cases?: string[];
  created_at?: string;
  updated_at?: string;
}

// Mutation type
export interface SettingsMutation {
  mutateAsync: (data: Record<string, unknown>) => Promise<unknown>;
  isPending?: boolean;
}

export interface ProfileMutation {
  mutateAsync: (data: Record<string, unknown>) => Promise<UpdateProfileResponse>;
  isPending?: boolean;
}

// Section component props
export interface SettingsSectionProps {
  isDark: boolean;
  theme: Theme;
  settings?: UserSettings;
  updateSettings?: SettingsMutation;
  profile?: UserProfile;
  updateProfile?: ProfileMutation;
}

export interface ProfileSectionProps {
  isDark: boolean;
  theme: Theme;
  profile?: UserProfile;
  updateProfile?: ProfileMutation;
}
