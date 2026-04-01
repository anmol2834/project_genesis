/**
 * My Data — React Query mutation hooks (write operations)
 *
 * Invalidation strategy after every mutation:
 *   - data.stats()   — counters in the header update
 *   - data.sources() — source list updates
 *   - data.entries() — entry list updates
 *
 * Optimistic updates are applied where the result is predictable
 * (delete entry, sync source status). File upload and manual entry
 * are async on the server so we wait for the server response.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import {
  dataApi,
  type DataEntry,
  type DataSource,
  type ManualEntryPayload,
  type GoogleSheetsConnectPayload,
  type UpdateEntryPayload,
  type DataCategory,
} from '@/services/endpoints/data';

// ── Shared invalidation helper ────────────────────────────────────────────────

function useInvalidateData() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: queryKeys.data.stats() });
    qc.invalidateQueries({ queryKey: queryKeys.data.sources() });
    qc.invalidateQueries({ queryKey: queryKeys.data.entries() });
  };
}

// ── File upload (CSV / Excel) ─────────────────────────────────────────────────

export interface UploadFileVars {
  file:       File;
  sourceName: string;
  category:   DataCategory;
}

/**
 * Upload a CSV or Excel file.
 * Returns immediately with a job_id (processing is async on the server).
 * Invalidates sources + entries so the new source appears in the list.
 */
export function useUploadFile() {
  const qc = useQueryClient();
  const invalidate = useInvalidateData();

  return useMutation({
    mutationFn: ({ file, sourceName, category }: UploadFileVars) =>
      dataApi.uploadFile(file, sourceName, category),
    onSuccess: () => {
      invalidate();
      // Poll entries after a short delay to catch the async processing result
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: queryKeys.data.entries() });
        qc.invalidateQueries({ queryKey: queryKeys.data.stats() });
      }, 3000);
    },
  });
}

// ── Manual entry ──────────────────────────────────────────────────────────────

/**
 * Create a single manual data entry (synchronous on the server).
 * Optimistically adds a placeholder to the entries list, then syncs.
 */
export function useCreateManualEntry() {
  const qc = useQueryClient();
  const invalidate = useInvalidateData();

  return useMutation({
    mutationFn: (payload: ManualEntryPayload) =>
      dataApi.createManualEntry(payload),
    onSuccess: () => invalidate(),
    onError: () => {
      // Rollback any optimistic state by re-fetching
      qc.invalidateQueries({ queryKey: queryKeys.data.entries() });
    },
  });
}

// ── Google Sheets connect ─────────────────────────────────────────────────────

/**
 * Connect a Google Sheet as a live data source.
 * Optimistically adds the new source to the sources list.
 */
export function useConnectGoogleSheet() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (payload: GoogleSheetsConnectPayload) =>
      dataApi.connectGoogleSheet(payload),
    onMutate: async (payload) => {
      await qc.cancelQueries({ queryKey: queryKeys.data.sources() });
      const prev = qc.getQueryData(queryKeys.data.sources());

      // Optimistic: add a placeholder source immediately
      qc.setQueryData<{ sources: DataSource[]; total: number; ai_ready: number; total_records: number }>(
        queryKeys.data.sources(),
        (old) => {
          if (!old) return old;
          const placeholder: DataSource = {
            id:               'optimistic-' + Date.now(),
            user_id:          '',
            name:             payload.name,
            source_type:      'google_sheets',
            status:           'syncing',
            total_records:    0,
            ai_ready_count:   0,
            last_sync_at:     null,
            ingestion_status: 'pending',
            sheet_url:        payload.sheet_url,
            created_at:       new Date().toISOString(),
            updated_at:       new Date().toISOString(),
          };
          return { ...old, sources: [placeholder, ...old.sources], total: old.total + 1 };
        },
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.data.sources(), ctx.prev);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: queryKeys.data.sources() });
      qc.invalidateQueries({ queryKey: queryKeys.data.stats() });
    },
  });
}

// ── Update entry ──────────────────────────────────────────────────────────────

/**
 * Update a data entry (title, category, or structured_data).
 * Optimistic update on the detail cache + list cache.
 */
export function useUpdateEntry() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ entryId, payload }: { entryId: string; payload: UpdateEntryPayload }) =>
      dataApi.updateEntry(entryId, payload),
    onMutate: async ({ entryId, payload }) => {
      await qc.cancelQueries({ queryKey: queryKeys.data.entry(entryId) });
      const prev = qc.getQueryData<DataEntry>(queryKeys.data.entry(entryId));
      qc.setQueryData<DataEntry>(
        queryKeys.data.entry(entryId),
        (old) => old ? { ...old, ...payload } : old,
      );
      return { prev };
    },
    onError: (_err, { entryId }, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.data.entry(entryId), ctx.prev);
    },
    onSettled: (_data, _err, { entryId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.data.entry(entryId) });
      qc.invalidateQueries({ queryKey: queryKeys.data.entries() });
      qc.invalidateQueries({ queryKey: queryKeys.data.stats() });
    },
  });
}

// ── Delete entry ──────────────────────────────────────────────────────────────

/**
 * Soft-delete a data entry.
 * Optimistically removes it from the entries list immediately.
 */
export function useDeleteEntry() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (entryId: string) => dataApi.deleteEntry(entryId),
    onMutate: async (entryId) => {
      await qc.cancelQueries({ queryKey: queryKeys.data.entries() });
      const prev = qc.getQueryData(queryKeys.data.entries());

      // Optimistic: remove from list immediately
      qc.setQueryData<{ entries: DataEntry[]; total: number; page: number; page_size: number; has_more: boolean }>(
        queryKeys.data.entries(),
        (old) => old
          ? { ...old, entries: old.entries.filter(e => e.id !== entryId), total: old.total - 1 }
          : old,
      );
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.data.entries(), ctx.prev);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: queryKeys.data.entries() });
      qc.invalidateQueries({ queryKey: queryKeys.data.stats() });
    },
  });
}

// ── Delete source ─────────────────────────────────────────────────────────────

/**
 * Delete a source and all its entries.
 * Optimistically removes the source from the list.
 */
export function useDeleteSource() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (sourceId: string) => dataApi.deleteSource(sourceId),
    onMutate: async (sourceId) => {
      await qc.cancelQueries({ queryKey: queryKeys.data.sources() });
      const prev = qc.getQueryData(queryKeys.data.sources());

      qc.setQueryData<{ sources: DataSource[]; total: number; ai_ready: number; total_records: number }>(
        queryKeys.data.sources(),
        (old) => old
          ? { ...old, sources: old.sources.filter(s => s.id !== sourceId), total: old.total - 1 }
          : old,
      );
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.data.sources(), ctx.prev);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: queryKeys.data.sources() });
      qc.invalidateQueries({ queryKey: queryKeys.data.entries() });
      qc.invalidateQueries({ queryKey: queryKeys.data.stats() });
    },
  });
}

// ── Sync source ───────────────────────────────────────────────────────────────

/**
 * Trigger a re-sync on a Google Sheets source.
 * Optimistically sets the source status to 'syncing'.
 */
export function useSyncSource() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (sourceId: string) => dataApi.syncSource(sourceId),
    onMutate: async (sourceId) => {
      await qc.cancelQueries({ queryKey: queryKeys.data.sources() });
      const prev = qc.getQueryData(queryKeys.data.sources());

      qc.setQueryData<{ sources: DataSource[]; total: number; ai_ready: number; total_records: number }>(
        queryKeys.data.sources(),
        (old) => old
          ? {
              ...old,
              sources: old.sources.map(s =>
                s.id === sourceId ? { ...s, status: 'syncing' as const } : s,
              ),
            }
          : old,
      );
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.data.sources(), ctx.prev);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: queryKeys.data.sources() });
    },
  });
}
