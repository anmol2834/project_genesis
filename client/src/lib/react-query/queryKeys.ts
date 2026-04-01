/**
 * Centralized query key factory.
 *
 * Rules:
 *  - Always use these constants — never inline strings in useQuery calls.
 *  - Keys are arrays so React Query can do partial invalidation.
 *  - Naming: ['resource'] for lists, ['resource', id] for single items,
 *    ['resource', 'sub-resource', params] for filtered/paginated queries.
 */

import type { LeadsListParams } from '@/services/endpoints/leads';
import type { ConversationsParams } from '@/services/endpoints/inbox';
import type { TimeRange } from '@/services/endpoints/analytics';

export const queryKeys = {

  // ── Auth ───────────────────────────────────────────────────────────────────
  auth: {
    me: () => ['auth', 'me'] as const,
  },

  // ── Profile ────────────────────────────────────────────────────────────────
  profile: {
    detail: () => ['profile'] as const,
  },


  // ── Campaigns ──────────────────────────────────────────────────────────────
  campaigns: {
    all:    ()         => ['campaigns']                    as const,
    detail: (id: string) => ['campaigns', id]             as const,
  },

  // ── Leads ──────────────────────────────────────────────────────────────────
  leads: {
    all:    ()                         => ['leads']                        as const,
    list:   (params: LeadsListParams)  => ['leads', 'list', params]        as const,
    detail: (id: string)               => ['leads', id]                    as const,
  },

  // ── Inbox ──────────────────────────────────────────────────────────────────
  inbox: {
    all:          ()                              => ['inbox']                          as const,
    conversations:(params?: ConversationsParams)  => ['inbox', 'conversations', params] as const,
    thread:       (threadId: string)              => ['inbox', 'thread', threadId]      as const,
  },

  // ── Analytics ──────────────────────────────────────────────────────────────
  analytics: {
    overview:  (range: TimeRange) => ['analytics', 'overview', range] as const,
    campaigns: ()                 => ['analytics', 'campaigns']        as const,
    accounts:  ()                 => ['analytics', 'accounts']         as const,
  },

  // ── Email Accounts ─────────────────────────────────────────────────────────
  accounts: {
    all:    ()           => ['accounts']       as const,
    detail: (id: string) => ['accounts', id]   as const,
  },

  // ── Team ───────────────────────────────────────────────────────────────────
  team: {
    members:  () => ['team', 'members']  as const,
    activity: () => ['team', 'activity'] as const,
  },

  // ── Integrations ───────────────────────────────────────────────────────────
  integrations: {
    all:    ()           => ['integrations']       as const,
    detail: (id: string) => ['integrations', id]   as const,
  },

  // ── Billing ────────────────────────────────────────────────────────────────
  billing: {
    overview:       () => ['billing', 'overview']        as const,
    invoices:       () => ['billing', 'invoices']        as const,
    paymentMethods: () => ['billing', 'payment-methods'] as const,
  },

  // ── Settings ───────────────────────────────────────────────────────────────
  settings: {
    all: () => ['settings'] as const,
  },

  // ── My Data ────────────────────────────────────────────────────────────────
  data: {
    // Aggregate stats (header counters)
    stats:   ()                                    => ['data', 'stats']                    as const,
    // All sources list
    sources: ()                                    => ['data', 'sources']                  as const,
    // All entries (no filter)
    entries: ()                                    => ['data', 'entries']                  as const,
    // Entries filtered by category
    byCategory: (category: string)                 => ['data', 'entries', category]        as const,
    // Entries filtered by source
    bySource: (sourceId: string)                   => ['data', 'entries', 'source', sourceId] as const,
    // Paginated entries with full params
    list: (params: Record<string, unknown>)        => ['data', 'entries', 'list', params]  as const,
    // Single entry detail
    entry: (id: string)                            => ['data', 'entries', id]              as const,
  },

} as const;
