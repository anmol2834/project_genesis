import { get, post, patch, del } from '../apiClient';
import type { EmailAccountFull } from './email';

// Re-export for backwards compat with existing hooks
export type { EmailAccountFull as EmailAccount };
export type AccountStatus   = 'connected' | 'disconnected' | 'error' | 'syncing';
export type AccountProvider = 'gmail' | 'outlook' | 'smtp';

/**
 * All endpoints route through the API gateway at port 8000.
 * Gateway forwards /email-service/* → emailservice:8004
 */
export const accountsApi = {
  /** GET /email-service/email/accounts — full EmailAccountFull list */
  list: () => get<EmailAccountFull[]>('/email-service/email/accounts'),

  /** GET /email-service/email/accounts/:id */
  get: (id: string) => get<EmailAccountFull>(`/email-service/email/accounts/${id}`),

  /** PATCH /email-service/email/accounts/:id — toggle automation, limits, display name */
  update: (id: string, data: Partial<Pick<EmailAccountFull, 'is_active' | 'automation_enabled' | 'daily_send_limit' | 'display_name'>>) =>
    patch<EmailAccountFull>(`/email-service/email/accounts/${id}`, data),

  /** POST /email-service/email/accounts/:id/sync — trigger manual sync */
  sync: (id: string) => post<{ status: string; account_id: string }>(`/email-service/email/accounts/${id}/sync`),

  /** DELETE /email-service/email/accounts/:id */
  delete: (id: string) => del<void>(`/email-service/email/accounts/${id}`),
};
