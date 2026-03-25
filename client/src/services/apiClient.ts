import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig } from 'axios';

/**
 * Centralized Axios instance.
 * All query/mutation hooks MUST use this — never raw fetch/axios in components.
 *
 * Auth: reads JWT from localStorage (key: 'mailflow_token').
 * Error: normalises server errors into a consistent ApiError shape.
 */

export interface ApiError {
  message: string;
  status:  number;
  code?:   string;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
});

// ── Request interceptor: attach JWT ──────────────────────────────────────────
apiClient.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('mailflow_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Response interceptor: normalise errors ───────────────────────────────────
apiClient.interceptors.response.use(
  (res) => res,
  (err: AxiosError<{ detail?: string; message?: string }>) => {
    const status  = err.response?.status ?? 0;
    const message =
      err.response?.data?.detail ??
      err.response?.data?.message ??
      err.message ??
      'An unexpected error occurred';

    // 401 → clear token and redirect to sign-in
    if (status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('mailflow_token');
      window.location.href = '/sign-in';
    }

    const apiError: ApiError = { message, status, code: err.code };
    return Promise.reject(apiError);
  },
);

/** Typed GET helper */
export async function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const res = await apiClient.get<T>(url, config);
  return res.data;
}

/** Typed POST helper */
export async function post<T, B = unknown>(url: string, body?: B, config?: AxiosRequestConfig): Promise<T> {
  const res = await apiClient.post<T>(url, body, config);
  return res.data;
}

/** Typed PUT helper */
export async function put<T, B = unknown>(url: string, body?: B, config?: AxiosRequestConfig): Promise<T> {
  const res = await apiClient.put<T>(url, body, config);
  return res.data;
}

/** Typed PATCH helper */
export async function patch<T, B = unknown>(url: string, body?: B, config?: AxiosRequestConfig): Promise<T> {
  const res = await apiClient.patch<T>(url, body, config);
  return res.data;
}

/** Typed DELETE helper */
export async function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const res = await apiClient.delete<T>(url, config);
  return res.data;
}
