/** Normalization rules + preview API. */
import { doFetch, getConfig } from './apiCore';

export interface NormalizationRule {
  id: number;
  ingestion_id?: string | null;
  raw_key: string;
  canonical_key: string;
  enabled: boolean;
  applied_count?: number;
  last_applied_at?: string | null;
  created_by: string;
  updated_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface NormalizationRuleCreatePayload {
  ingestion_id?: string | null;
  raw_key: string;
  canonical_key: string;
  enabled?: boolean;
  created_by: string;
}

export interface NormalizationRuleUpdatePayload {
  ingestion_id?: string | null;
  canonical_key?: string;
  enabled?: boolean;
  updated_by: string;
}

export const listNormalizationRules = (): Promise<NormalizationRule[]> => {
  const { backendUrl } = getConfig();
  return doFetch<NormalizationRule[]>(`${backendUrl}/api/normalization`);
};

export const createNormalizationRule = (payload: NormalizationRuleCreatePayload): Promise<NormalizationRule> => {
  const { backendUrl } = getConfig();
  return doFetch<NormalizationRule>(`${backendUrl}/api/normalization`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: true, ...payload }),
  });
};

export const createMultipleNormalizationRules = (rules: NormalizationRuleCreatePayload[]): Promise<NormalizationRule[]> => {
  return Promise.all(rules.map(rule => createNormalizationRule(rule)));
};

export const updateNormalizationRule = (id: number, payload: NormalizationRuleUpdatePayload): Promise<NormalizationRule> => {
  const { backendUrl } = getConfig();
  return doFetch<NormalizationRule>(`${backendUrl}/api/normalization/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const deleteNormalizationRule = (id: number): Promise<{ status?: string; message?: string }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ status?: string; message?: string }>(`${backendUrl}/api/normalization/${id}`, { method: 'DELETE' });
};

export const toggleNormalizationRule = (id: number): Promise<NormalizationRule> => {
  const { backendUrl } = getConfig();
  return doFetch<NormalizationRule>(`${backendUrl}/api/normalization/${id}/toggle`, { method: 'PATCH' });
};

// ── Normalization Preview ───────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export interface NormalizationPreviewSampleData {
  status: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any[];
  columns: string[];
  total_records: number;
  sample_ingestion_ids: string[];
}

export interface NormalizationPreviewResult {
  status: string;
  summary: {
    total_records: number;
    total_columns: number;
    rules_applied: number;
    columns_mapped: number;
    unmapped_columns: number;
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  original_data: any[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  normalized_data: any[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  applied_rules: any[];
  column_mappings: Record<string, string>;
  unmapped_columns: string[];
  available_columns: string[];
}

export const getNormalizationSampleData = (ingestionId?: string, limit: number = 100): Promise<NormalizationPreviewSampleData> => {
  const { backendUrl } = getConfig();
  const params = new URLSearchParams({ limit: limit.toString() });
  if (ingestionId) params.append('ingestion_id', ingestionId);
  return doFetch<NormalizationPreviewSampleData>(`${backendUrl}/api/normalization/preview/sample-data?${params}`);
};

export const previewNormalization = (payload: {
  ingestion_id?: string;
  custom_rules?: Array<{ raw_key: string; canonical_key: string; ingestion_id?: string }>;
  sample_limit: number;
}): Promise<{ status: string; data: { preview: NormalizationPreviewResult } }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ status: string; data: { preview: NormalizationPreviewResult } }>(`${backendUrl}/api/normalization/preview/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const validateNormalizationRules = (payload: {
  rules: Array<{ raw_key: string; canonical_key: string; ingestion_id?: string }>;
  ingestion_id?: string;
  sample_limit: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
}): Promise<{ status: string; validation: any }> => {
  const { backendUrl } = getConfig();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return doFetch<{ status: string; validation: any }>(`${backendUrl}/api/normalization/preview/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const compareNormalizationScenarios = (payload: {
  ingestion_id?: string;
  scenario_a_rules: Array<{ raw_key: string; canonical_key: string; ingestion_id?: string }>;
  scenario_b_rules: Array<{ raw_key: string; canonical_key: string; ingestion_id?: string }>;
  sample_limit: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
}): Promise<any> => {
  const { backendUrl } = getConfig();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return doFetch<any>(`${backendUrl}/api/normalization/preview/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};
