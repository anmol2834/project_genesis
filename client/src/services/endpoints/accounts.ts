import { get, post, patch, del } from '../apiClient';

export type AccountStatus   = 'connected' | 'syncing' | 'paused';
export type AccountProvider = 'gmail' | 'outlook' | 'custom';

export interface EmailAccount {
  id: string;
  email: string;
  name: string;
  provider: AccountProvider;
  status: AccountStatus;
  automationEnabled: boolean;
  lastSync: string;
  emailsProcessed: number;
  emailsSentToday: number;
  replyRate: number;
  dailyLimit: number;
  dailyUsed: number;
}

export interface ConnectOAuthPayload  { provider: 'gmail' | 'outlook'; code: string; }
export interface ConnectSmtpPayload   { name: string; email: string; host: string; port: number; username: string; password: string; encryption: 'TLS' | 'SSL' | 'None'; }

export const accountsApi = {
  list:          ()                                  => get<EmailAccount[]>('/email-accounts'),
  get:           (id: string)                        => get<EmailAccount>(`/email-accounts/${id}`),
  connectOAuth:  (p: ConnectOAuthPayload)            => post<EmailAccount>('/email-accounts/oauth', p),
  connectSmtp:   (p: ConnectSmtpPayload)             => post<EmailAccount>('/email-accounts/smtp', p),
  toggleAuto:    (id: string, enabled: boolean)      => patch<EmailAccount>(`/email-accounts/${id}`, { automationEnabled: enabled }),
  sync:          (id: string)                        => post<void>(`/email-accounts/${id}/sync`),
  delete:        (id: string)                        => del<void>(`/email-accounts/${id}`),
};
