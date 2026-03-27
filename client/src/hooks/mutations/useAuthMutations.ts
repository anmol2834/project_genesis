import { useMutation } from '@tanstack/react-query';
import {
  authApi,
  storeTokens,
  type SendOtpRequest,
  type SendOtpResponse,
  type VerifyOtpRequest,
  type VerifyOtpResponse,
  type SignupRequest,
  type SignupResponse,
} from '@/services/endpoints/auth';
import type { ApiError } from '@/services/apiClient';

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

export function useSignup() {
  return useMutation<SignupResponse, ApiError, SignupRequest>({
    mutationFn: (payload) => authApi.signup(payload),
    onSuccess: (data) => {
      storeTokens(data.tokens);
    },
  });
}
