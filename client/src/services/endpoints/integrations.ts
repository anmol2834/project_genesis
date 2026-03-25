import { get, post, patch, del } from '../apiClient';

export type IntegrationStatus = 'connected' | 'disconnected' | 'error' | 'syncing';

export interface Integration {
  id: string;
  name: string;
  category: string;
  status: IntegrationStatus;
  lastSync?: string;
  leadsImported?: number;
  automationsTriggered?: number;
  dataFlow?: string;
}

export interface ConnectIntegrationPayload { integrationId: string; config: Record<string, unknown>; }
export interface UpdateSyncPayload         { autoSync?: boolean; triggerAutomations?: boolean; bidirectional?: boolean; }

export const integrationsApi = {
  list:       ()                                          => get<Integration[]>('/integrations'),
  connect:    (p: ConnectIntegrationPayload)              => post<Integration>('/integrations/connect', p),
  update:     (id: string, p: UpdateSyncPayload)          => patch<Integration>(`/integrations/${id}`, p),
  disconnect: (id: string)                               => del<void>(`/integrations/${id}`),
  sync:       (id: string)                               => post<void>(`/integrations/${id}/sync`),
};
