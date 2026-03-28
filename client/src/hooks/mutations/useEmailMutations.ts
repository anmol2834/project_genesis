'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { emailApi, type ConnectEmailPayload, type ConnectEmailResponse } from '@/services/endpoints/email';
import { queryKeys } from '@/lib/react-query/queryKeys';

/**
 * useConnectEmail
 *
 * Unified mutation for connecting any email provider (Gmail OAuth, Outlook OAuth, SMTP).
 * On success:
 *  - Invalidates accounts cache → triggers fresh fetch on EmailAccountsPage
 *  - Invalidates integrations cache → reflects new connection on IntegrationsPage
 */
export function useConnectEmail() {
  const qc = useQueryClient();

  return useMutation<ConnectEmailResponse, Error, ConnectEmailPayload>({
    mutationFn: emailApi.connect,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      qc.invalidateQueries({ queryKey: queryKeys.integrations.all() });
    },
  });
}
