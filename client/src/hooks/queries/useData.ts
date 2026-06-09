/**
 * My Data — React Query hooks (read operations)
 *
 * Caching strategy:
 *   stats   — 2 min stale (changes after every ingestion)
 *   sources — 2 min stale
 *   entries — 3 min stale (larger payload, changes less often)
 *   entry   — 5 min stale (single item, rarely changes)
 *
 * Data fetching strategy:
 *   ALL entries are always fetched from the DB in a single request
 *   (page_size=500 covers virtually all realistic datasets).
 *   Category/source filtering is done CLIENT-SIDE so:
 *     1. The left-nav category counts are always accurate (all categories visible)
 *     2. Switching categories is instant (no extra network round-trip)
 *     3. Loading stops as soon as all DB data is received — no Qdrant involved
 *   This approach is intentional: GET /data/entries reads PostgreSQL only.
 */

import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import {
  dataApi,
  type DataCategory,
  type DataEntryListParams,
} from '@/services/endpoints/data';

/** Aggregate stats for the My Data page header (entries, sources, avg quality, AI-ready). */
export function useDataStats() {
  return useQuery({
    queryKey: queryKeys.data.stats(),
    queryFn:  () => dataApi.getStats(),
    staleTime: 2 * 60 * 1000,
  });
}

/** All data sources for the authenticated user. */
export function useDataSources() {
  return useQuery({
    queryKey: queryKeys.data.sources(),
    queryFn:  () => dataApi.getSources(),
    staleTime: 2 * 60 * 1000,
  });
}

/**
 * Fetch ALL entries from the DB in one shot (page_size=500).
 * No category filter — filtering is done client-side.
 * This is the single source of truth for the My Data page.
 */
export function useAllDataEntries() {
  return useQuery({
    queryKey: queryKeys.data.entries(),
    queryFn:  () => dataApi.getEntries({ page: 1, page_size: 500 }),
    staleTime: 3 * 60 * 1000,
    placeholderData: (prev) => prev,
  });
}

/** Paginated data entries — supports category + source_id filtering. */
export function useDataEntries(params: DataEntryListParams = {}) {
  const queryKey = Object.keys(params).length
    ? queryKeys.data.list(params as Record<string, unknown>)
    : queryKeys.data.entries();

  return useQuery({
    queryKey,
    queryFn:  () => dataApi.getEntries(params),
    staleTime: 3 * 60 * 1000,
    placeholderData: (prev) => prev,
  });
}

/**
 * @deprecated Use useAllDataEntries() + client-side filtering instead.
 * Kept for backward compatibility only.
 */
export function useDataEntriesByCategory(category: DataCategory | 'all') {
  return useQuery({
    queryKey: queryKeys.data.entries(),
    queryFn:  () => dataApi.getEntries({ page: 1, page_size: 500 }),
    staleTime: 3 * 60 * 1000,
    placeholderData: (prev) => prev,
  });
}

/** Single entry detail — used by the EntryPanel overlay. */
export function useDataEntry(entryId: string | null) {
  return useQuery({
    queryKey: queryKeys.data.entry(entryId ?? ''),
    queryFn:  () => dataApi.getEntry(entryId!),
    enabled:  !!entryId,
    staleTime: 5 * 60 * 1000,
  });
}
