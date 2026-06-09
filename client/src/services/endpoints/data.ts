/**
 * My Data API — all calls route through Gateway → user-service
 * Path prefix: /user-service/data
 *
 * Mirrors server/services/user-service/api/data_ingestion.py exactly.
 */

import { get, post, patch, del, apiClient } from '../apiClient';

// ── Enums ─────────────────────────────────────────────────────────────────────

export type DataCategory =
  | 'product_service'
  | 'issue_resolution'
  | 'contact_support'
  | 'offers_promotions'
  | 'delivery_shipping'
  | 'company_info'
  | 'policies_legal'
  | 'educational_content'
  | 'uncategorized';

export type SourceType    = 'csv_import' | 'excel_import' | 'manual' | 'google_sheets' | 'api';
export type SourceStatus  = 'active' | 'paused' | 'error' | 'syncing';
export type IngestionStatus = 'pending' | 'processing' | 'completed' | 'failed';

// ── Source ────────────────────────────────────────────────────────────────────

export interface DataSource {
  id:               string;
  user_id:          string;
  name:             string;
  source_type:      SourceType;
  status:           SourceStatus;
  total_records:    number;
  ai_ready_count:   number;
  last_sync_at:     string | null;
  ingestion_status: IngestionStatus;
  sheet_url?:       string | null;
  api_endpoint?:    string | null;
  created_at:       string;
  updated_at:       string;
}

export interface DataSourceListResponse {
  sources:       DataSource[];
  total:         number;
  ai_ready:      number;
  total_records: number;
}

// ── Entry ─────────────────────────────────────────────────────────────────────

export interface DataEntry {
  id:                  string;
  user_id:             string;
  source_id:           string;
  category:            DataCategory;
  subtype:             string | null;
  title:               string;
  structured_data:     Record<string, string>;
  search_text:         string;
  ai_tags:             string[] | null;
  ai_relevance:        string[] | null;
  entities:            Array<{ type: string; value: string }> | null;
  quality_score:       number;
  missing_fields:      string[] | null;
  classification_meta: Record<string, unknown> | null;
  source_type:         SourceType;
  version:             number;
  created_at:          string;
  updated_at:          string;
}

export interface DataEntryListResponse {
  entries:   DataEntry[];
  total:     number;
  page:      number;
  page_size: number;
  has_more:  boolean;
}

export interface DataEntryListParams {
  category?:  DataCategory;
  source_id?: string;
  page?:      number;
  page_size?: number;
}

// ── Stats ─────────────────────────────────────────────────────────────────────

export interface DataStats {
  total_entries:    number;
  total_sources:    number;
  avg_quality:      number;
  ai_ready_entries: number;
  by_category:      Record<string, number>;
  by_source_type:   Record<string, number>;
}

// ── Request payloads ──────────────────────────────────────────────────────────

export interface ManualEntryField {
  key:   string;
  label: string;
  value: string;
}

export interface ManualEntryPayload {
  title:    string;
  category: DataCategory;
  fields:   ManualEntryField[];
}

export interface GoogleSheetsConnectPayload {
  name:        string;
  sheet_url:   string;
  sheet_name?: string;
  category:    DataCategory;
}

export interface UpdateEntryPayload {
  title?:           string;
  category?:        DataCategory;
  structured_data?: Record<string, string>;
}

// ── Responses ─────────────────────────────────────────────────────────────────

export interface IngestionJobResponse {
  job_id:     string;
  source_id:  string;
  status:     'processing' | 'completed' | 'failed';
  message:    string;
  total_rows?: number;
  accepted?:  number;
  rejected?:  number;
  errors?:    string[];
}

export interface DeleteSourceResponse {
  success:         boolean;
  source_id:       string;
  entries_deleted: number;
  vectors_deleted: number;
  message:         string;
}

export interface SyncSourceResponse {
  success:   boolean;
  source_id: string;
  message:   string;
  job_id?:   string;
}

// ── API ───────────────────────────────────────────────────────────────────────

const BASE = '/user-service/data';

export const dataApi = {

  // ── Sources ────────────────────────────────────────────────────────────────

  getSources: () =>
    get<DataSourceListResponse>(`${BASE}/sources`),

  deleteSource: (sourceId: string) =>
    del<DeleteSourceResponse>(`${BASE}/sources/${sourceId}`),

  syncSource: (sourceId: string) =>
    patch<SyncSourceResponse>(`${BASE}/sources/${sourceId}/sync`, {}),

  // ── Entries ────────────────────────────────────────────────────────────────

  getEntries: (params: DataEntryListParams = {}) =>
    get<DataEntryListResponse>(`${BASE}/entries`, { params }),

  getEntry: (entryId: string) =>
    get<DataEntry>(`${BASE}/entries/${entryId}`),

  updateEntry: (entryId: string, payload: UpdateEntryPayload) =>
    patch<DataEntry>(`${BASE}/entries/${entryId}`, payload),

  deleteEntry: (entryId: string) =>
    del<void>(`${BASE}/entries/${entryId}`),

  // ── Stats ──────────────────────────────────────────────────────────────────

  getStats: () =>
    get<DataStats>(`${BASE}/stats`),

  // ── Ingestion ──────────────────────────────────────────────────────────────

  /** Upload CSV or Excel file. Uses multipart/form-data. */
  uploadFile: (file: File, sourceName: string, category: DataCategory) => {
    const form = new FormData();
    form.append('file', file);
    form.append('source_name', sourceName);
    form.append('category', category);
    return apiClient.post<IngestionJobResponse>(`${BASE}/upload`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data);
  },

  /** Create a single manual entry. */
  createManualEntry: (payload: ManualEntryPayload) =>
    post<IngestionJobResponse>(`${BASE}/manual`, payload),

  /** Connect a Google Sheet as a live source. */
  connectGoogleSheet: (payload: GoogleSheetsConnectPayload) =>
    post<DataSource>(`${BASE}/sources/google-sheets`, payload),
};
