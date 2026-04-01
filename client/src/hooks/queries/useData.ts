/**
 * My Data — React Query hooks (read operations)
 *
 * Caching strategy:
 *   stats   — 2 min stale (changes after every ingestion)
 *   sources — 2 min stale
 *   entries — 3 min stale (larger payload, changes less often)
 *   entry   — 5 min stale (single item, rarely changes)
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

/** Paginated data entries — supports category + source_id filtering. */
export function useDataEntries(params: DataEntryListParams = {}) {
  const queryKey = Object.keys(params).length
    ? queryKeys.data.list(params as Record<string, unknown>)
    : queryKeys.data.entries();

  return useQuery({
    queryKey,
    queryFn:  () => dataApi.getEntries(params),
    staleTime: 3 * 60 * 1000,
    placeholderData: (prev) => prev, // keeps previous data visible while loading
  });
}

/** Entries filtered to a single category — used by the left-nav category filter. */
export function useDataEntriesByCategory(category: DataCategory | 'all') {
  return useQuery({
    queryKey: category === 'all'
      ? queryKeys.data.entries()
      : queryKeys.data.byCategory(category),
    queryFn: () =>
      category === 'all'
        ? dataApi.getEntries()
        : dataApi.getEntries({ category }),
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
