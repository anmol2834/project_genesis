import axios, { AxiosError } from 'axios';
import type { ApiError } from '@/services/apiClient';

/**
 * Dedicated Axios instance for the auth-service (port 8001).
 * Auth endpoints are NOT proxied through the gateway — hit the service directly.
 */
const authClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_AUTH_URL ?? 'http://localhost:8001',
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
});

// Normalise errors into ApiError shape — same pattern as apiClient.ts
authClient.interceptors.response.use(
  (res) => res,
  (err: AxiosError<{ detail?: string; message?: string }>) => {
    const status  = err.response?.status ?? 0;
    const message =
      err.response?.data?.detail ??
      err.response?.data?.message ??
      err.message ??
      'An unexpected error occurred';
    const apiError: ApiError = { message, status, code: err.code };
    return Promise.reject(apiError);
  },
);

// ── Types (mirror server schemas/auth.py exactly) ─────────────────────────────

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
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

export interface SendOtpRequest  { email: string; }
export interface SendOtpResponse { success: boolean; message: string; }

export interface VerifyOtpRequest  { email: string; code: string; }
export interface VerifyOtpResponse { success: boolean; message: string; }

// ── API ───────────────────────────────────────────────────────────────────────

export const authApi = {
  sendOtp: async (payload: SendOtpRequest): Promise<SendOtpResponse> => {
    const res = await authClient.post<SendOtpResponse>('/auth/send-otp', payload);
    return res.data;
  },

  verifyOtp: async (payload: VerifyOtpRequest): Promise<VerifyOtpResponse> => {
    const res = await authClient.post<VerifyOtpResponse>('/auth/verify-otp', payload);
    return res.data;
  },

  signup: async (payload: SignupRequest): Promise<SignupResponse> => {
    const res = await authClient.post<SignupResponse>('/auth/signup', payload);
    return res.data;
  },
};

/** Persist tokens to localStorage after successful auth. */
export function storeTokens(tokens: TokenResponse): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem('mailflow_token', tokens.access_token);
  localStorage.setItem('mailflow_refresh_token', tokens.refresh_token);
}
