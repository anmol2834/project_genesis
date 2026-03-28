import { get, post } from '../apiClient';

// ── Request types (mirror backend ConnectEmailRequest) ────────────────────────

export type EmailProvider      = 'gmail' | 'outlook' | 'smtp';
export type EmailConnectionType = 'oauth' | 'manual';
export type ConnectionStatus   = 'connected' | 'disconnected' | 'error';
export type SyncStatus         = 'idle' | 'syncing' | 'failed';

export interface EmailConnectionCredentials {
  // OAuth
  code?: string;
  code_verifier?: string; // For PKCE flow (Outlook)
  // SMTP / manual
  smtp_host?: string;
  smtp_port?: number;
  username?: string;
  password?: string;
  smtp_use_tls?: boolean;
  imap_host?: string;
  imap_port?: number;
}

export interface ConnectEmailPayload {
  provider: EmailProvider;
  connection_type: EmailConnectionType;
  email?: string;
  credentials: EmailConnectionCredentials;
}

// ── Response types (mirror backend ConnectEmailResponse) ─────────────────────

export interface ConnectedEmailAccount {
  email: string;
  provider: EmailProvider;
  status: ConnectionStatus;
  account_id: string;
}

export interface ConnectEmailResponse {
  status: string;
  message: string;
  data: ConnectedEmailAccount;
}

// ── Full account shape returned by list endpoint ──────────────────────────────

export interface EmailAccountFull {
  id: string;
  user_id: string;
  email_address: string;
  display_name: string | null;
  provider: EmailProvider;
  connection_status: ConnectionStatus;
  sync_status: SyncStatus;
  daily_send_limit: number;
  daily_sent_count: number;
  warmup_enabled: boolean;
  is_active: boolean;
  is_primary: boolean;
  automation_enabled: boolean;
  last_synced_at: string | null;
  last_error_message: string | null;
  created_at: string;
  updated_at: string;
}

// ── API object ────────────────────────────────────────────────────────────────

export const emailApi = {
  /** POST /email-service/email/connect */
  connect: (payload: ConnectEmailPayload) =>
    post<ConnectEmailResponse, ConnectEmailPayload>('/email-service/email/connect', payload),

  /** GET /email-service/email/accounts */
  listAccounts: () =>
    get<EmailAccountFull[]>('/email-service/email/accounts'),

  /** PATCH /email-service/email/accounts/:id */
  updateAccount: (id: string, data: Partial<Pick<EmailAccountFull, 'is_active' | 'automation_enabled' | 'daily_send_limit' | 'display_name'>>) =>
    post<EmailAccountFull>(`/email-service/email/accounts/${id}`, data),

  /** DELETE /email-service/email/accounts/:id */
  deleteAccount: (id: string) =>
    post<void>(`/email-service/email/accounts/${id}/disconnect`),
};
