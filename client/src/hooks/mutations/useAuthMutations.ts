import { useMutation } from '@tanstack/react-query';
import {
  authApi,
  type SendOtpRequest,
  type SendOtpResponse,
  type VerifyOtpRequest,
  type VerifyOtpResponse,
  type LoginRequest,
  type LoginResponse,
  type SignupRequest,
  type SignupResponse,
  type RefreshTokenRequest,
  type RefreshTokenResponse,
  type LogoutRequest,
  type User,
} from '@/services/endpoints/auth';
import type { ApiError } from '@/services/apiClient';

/**
 * Enterprise-grade Auth Mutations using React Query
 * 
 * Architecture:
 * - React Query handles all API interactions (loading, error, success states)
 * - AuthContext handles only client-side state (user data, auth status)
 * - Clean separation of concerns: server state vs client state
 */

// ─── OTP Mutations ─────────────────────────────────────────────────────────

export function useSendOtp() {
  return useMutation<SendOtpResponse, ApiError, SendOtpRequest>({
    mutationFn: (payload) => authApi.sendOtp(payload),
  });
}

export function useVerifyOtp() {
  return useMutation<VerifyOtpResponse, ApiError, VerifyOtpRequest>({
    mutationFn: (payload) => authApi.verifyOtp(payload),
  });
}

// ─── Login Mutation ──────────────────────────────────────────────────────────

export function useLogin() {
  return useMutation<LoginResponse, ApiError, LoginRequest>({
    mutationFn: (payload) => authApi.login(payload),
  });
}

// ─── Signup Mutation ─────────────────────────────────────────────────────────

export function useSignup() {
  return useMutation<SignupResponse, ApiError, SignupRequest>({
    mutationFn: (payload) => authApi.signup(payload),
  });
}

// ─── Get Profile Mutation ─────────────────────────────────────────────────────

export function useGetProfile() {
  return useMutation<User, ApiError, void>({
    mutationFn: () => authApi.getProfile(),
  });
}

// ─── Refresh Token Mutation ──────────────────────────────────────────────────

export function useRefreshToken() {
  return useMutation<RefreshTokenResponse, ApiError, RefreshTokenRequest>({
    mutationFn: (payload) => authApi.refreshToken(payload),
  });
}

// ─── Logout Mutation ────────────────────────────────────────────────────────

export function useLogout() {
  return useMutation<void, ApiError, LogoutRequest>({
    mutationFn: (request) => authApi.logout(request),
  });
}
