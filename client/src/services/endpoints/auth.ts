/**
 * Auth API - All endpoints go through Gateway Service
 * 
 * Architecture: Frontend → Gateway (8000) → Auth Service (8001)
 * 
 * Benefits:
 * - Rate limiting on all auth endpoints
 * - Circuit breaker protection
 * - Request tracking and tracing
 * - Centralized logging
 * - Consistent error handling
 * - Automatic retry on failures
 */

import { get, post } from '../apiClient';

// ── Types (mirror server schemas/auth.py exactly) ─────────────────────────────

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface User {
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
  created_at?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  success: boolean;
  message: string;
  user_id: string;
  email: string;
  full_name: string;
  tokens: TokenResponse;
}

export interface SignupRequest {
  full_name: string;
  email: string;
  password: string;
  business_name: string;
  business_type: string;
  industries: string[];
  country: string;
  timezone: string;
  business_description: string;
  target_audience: string;
  communication_tone: string;
  use_cases: string[];
}

export interface SignupResponse {
  success: boolean;
  message: string;
  user_id: string;
  email: string;
  tokens: TokenResponse;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface RefreshTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface LogoutRequest {
  refresh_token: string;
}

export interface SendOtpRequest  { email: string; }
export interface SendOtpResponse { success: boolean; message: string; }

export interface VerifyOtpRequest  { email: string; code: string; }
export interface VerifyOtpResponse { success: boolean; message: string; }

// ── API ───────────────────────────────────────────────────────────────────────

// ── API (All calls go through Gateway) ───────────────────────────────────────

export const authApi = {
  /** Send OTP to email */
  sendOtp: (payload: SendOtpRequest) => 
    post<SendOtpResponse>('/auth/send-otp', payload),

  /** Verify OTP code */
  verifyOtp: (payload: VerifyOtpRequest) => 
    post<VerifyOtpResponse>('/auth/verify-otp', payload),

  /** Login with email and password */
  login: (payload: LoginRequest) => 
    post<LoginResponse>('/auth/login', payload),

  /** Register new user */
  signup: (payload: SignupRequest) => 
    post<SignupResponse>('/auth/signup', payload),

  /** Get current user profile (requires auth token in apiClient interceptor) */
  getProfile: () => 
    get<User>('/auth/me'),

  /** Refresh access token */
  refreshToken: (payload: RefreshTokenRequest) => 
    post<RefreshTokenResponse>('/auth/refresh', payload),

  /** Logout and invalidate tokens (requires auth token in apiClient interceptor) */
  logout: (payload: LogoutRequest) => 
    post<void>('/auth/logout', payload),
};
