/** Configuration and settings API. */
import { doFetch, getConfig } from './apiCore';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export interface SchemaConfig { use_union_schema: boolean; schema_type: string; message: string; }

export interface SystemConfig {
  schema: { use_union_schema: boolean; schema_type: string };
  storage: { minio_bucket: string; bronze_path: string; enriched_path: string; gold_temp_avg_path: string; gold_alerts_path: string };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  spark: { status: string; master_host: string; workers: any[] };
  streaming: { enrichment_active: boolean; temperature_active: boolean; alert_active: boolean };
}

export interface FeatureFlags {
  union_schema: { available: boolean; description: string; benefits: string[] };
  legacy_schema: { available: boolean; description: string; benefits: string[] };
  dynamic_normalization: { available: boolean; description: string };
  stream_processing: { available: boolean; description: string };
}

export const getSchemaConfig = (): Promise<SchemaConfig> => {
  const { backendUrl } = getConfig();
  return doFetch<SchemaConfig>(`${backendUrl}/api/config/schema`);
};

export const getSystemConfig = (): Promise<SystemConfig> => {
  const { backendUrl } = getConfig();
  return doFetch<SystemConfig>(`${backendUrl}/api/config`);
};

export const getFeatureFlags = (): Promise<FeatureFlags> => {
  const { backendUrl } = getConfig();
  return doFetch<FeatureFlags>(`${backendUrl}/api/config/features`);
};

// ── Settings ────────────────────────────────────────────────────

export interface Setting {
  id?: number;
  key: string;
  value: string;
  value_type?: string;
  description?: string | null;
  category?: string | null;
  created_by?: string;
  updated_by?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface SettingCreatePayload {
  key: string;
  value: string;
  value_type?: string;
  description?: string;
  category?: string;
  created_by: string;
}

export interface SettingUpdatePayload {
  value: string;
  value_type?: string;
  description?: string;
  category?: string;
  updated_by: string;
}

export const listSettings = (): Promise<Setting[]> => {
  const { backendUrl } = getConfig();
  return doFetch<Setting[]>(`${backendUrl}/api/settings`);
};

export const getSetting = (key: string): Promise<Setting> => {
  const { backendUrl } = getConfig();
  return doFetch<Setting>(`${backendUrl}/api/settings/${encodeURIComponent(key)}`);
};

export const createSetting = (payload: SettingCreatePayload): Promise<Setting> => {
  const { backendUrl } = getConfig();
  return doFetch<Setting>(`${backendUrl}/api/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const updateSetting = (key: string, payload: SettingUpdatePayload): Promise<Setting> => {
  const { backendUrl } = getConfig();
  return doFetch<Setting>(`${backendUrl}/api/settings/${encodeURIComponent(key)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const deleteSetting = (key: string): Promise<{ status?: string; message?: string }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ status?: string; message?: string }>(`${backendUrl}/api/settings/${encodeURIComponent(key)}`, { method: 'DELETE' });
};
