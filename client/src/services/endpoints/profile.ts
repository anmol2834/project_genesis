/**
 * User Profile API - All endpoints go through Gateway Service
 * 
 * Architecture: Frontend → Gateway (8000) → User Service (8002)
 */

import { get, patch } from '../apiClient';

// ── Types ──────────────────────────────────────────────────────────────────────

export interface UserProfile {
  user_id: string;
  email: string;
  full_name: string;
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
  created_at: string;
  updated_at: string;
}

export interface UpdateProfileRequest {
  full_name?: string;
  business_name?: string;
  business_type?: string;
  industries?: string[];
  country?: string;
  timezone?: string;
  business_description?: string;
  target_audience?: string;
  communication_tone?: string;
  use_cases?: string[];
}

export interface UpdateProfileResponse extends UserProfile {
  success: boolean;
  message: string;
  fields_updated: string[];
  vector_update_triggered: boolean;
}

// ── API ────────────────────────────────────────────────────────────────────────

export const profileApi = {
  /** Get current user's profile */
  getProfile: () => 
    get<UserProfile>('/user-service/users/profile'),

  /** Update user profile (partial update) */
  updateProfile: (data: UpdateProfileRequest) => 
    patch<UpdateProfileResponse>('/user-service/users/update-profile', data),
};
