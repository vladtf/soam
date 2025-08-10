import { getConfig } from '../config';
import { Building } from '../models/Building';

export interface SensorData {
    temperature?: number;
    humidity?: number;
}

// Standard API response wrapper
type ApiResponse<T> = {
  status?: string;
  detail?: string;
  data?: T;
};

export const extractDataSchema = (data: SensorData[]): Record<string, string[]> => {
    const schema: Record<string, string[]> = {};
    data.forEach((sensorData) => {
        Object.keys(sensorData).forEach((key) => {
            schema[key] = ['http://www.w3.org/2001/XMLSchema#float']; // TODO: actual type extraction
        });
    });
    return schema;
};

// General fetch handler
async function doFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  let resultRaw: unknown;
  try {
    resultRaw = await response.json();
  } catch {
    resultRaw = undefined;
  }

  // Normalize to ApiResponse
  const result = resultRaw as ApiResponse<T>;

  if (!response.ok) {
    let detailMsg: string;
    if (typeof result.detail === 'object' && result.detail !== null) {
      detailMsg = JSON.stringify(result.detail);
    } else {
      detailMsg = result.detail ?? response.statusText;
    }
    throw new Error(detailMsg);
  }

  if (result.status && result.status !== 'success') {
    const errMsg = result.detail ?? `Error on ${url}`;
    throw new Error(errMsg);
  }

  if (result.data !== undefined) {
    return result.data;
  }

  // Fallback to raw
  return resultRaw as T;
}

export const fetchSensorData = (): Promise<SensorData[]> => {
  const { ingestorUrl } = getConfig();
  return doFetch<SensorData[]>(`${ingestorUrl}/data`);
};

export const fetchAverageTemperature = (): Promise<unknown[]> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown[]>(`${backendUrl}/spark/average-temperature`);
};

// Spark Master Status interfaces
export interface SparkWorker {
  id: string;
  host: string;
  port: number;
  webuiaddress: string;
  cores: number;
  coresused: number;
  coresfree: number;
  memory: number;
  memoryused: number;
  memoryfree: number;
  state: string;
  lastheartbeat: number;
}

export interface SparkApplication {
  id: string;
  starttime: number;
  name: string;
  cores: number;
  user: string;
  submitdate: string;
  state: string;
  duration: number;
}

export interface SparkMasterStatus {
  url: string;
  workers: SparkWorker[];
  aliveworkers: number;
  cores: number;
  coresused: number;
  memory: number;
  memoryused: number;
  activeapps: SparkApplication[];
  completedapps: SparkApplication[];
  status: string;
}

export const fetchSparkMasterStatus = (): Promise<SparkMasterStatus> => {
  const { backendUrl } = getConfig();
  return doFetch<SparkMasterStatus>(`${backendUrl}/spark/master-status`);
};

export const postNewBuilding = (newBuilding: Building): Promise<unknown> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown>(`${backendUrl}/buildings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(newBuilding),
  });
};

export const fetchTemperatureAlerts = (
  sinceMinutes = 60
): Promise<unknown[]> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown[]>(
    `${backendUrl}/spark/temperature-alerts?since_minutes=${sinceMinutes}`
  );
};

export const fetchConnections = (): Promise<unknown> => {
  const { ingestorUrl } = getConfig();
  return doFetch<unknown>(`${ingestorUrl}/connections`);
};

export const switchBroker = (id: number): Promise<unknown> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown>(`${backendUrl}/switchBroker`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  });
};

export const fetchBuildings = (): Promise<Building[]> => {
  const { backendUrl } = getConfig();
  return doFetch<Building[]>(`${backendUrl}/buildings`);
};

export const addConnection = (config: unknown): Promise<unknown> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown>(`${backendUrl}/addConnection`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
};

// Feedback API functions
export interface FeedbackData {
  email: string;
  message: string;
}

export interface FeedbackResponse {
  id: number;
  email: string;
  message: string;
  created_at: string;
}

export const submitFeedback = (feedback: FeedbackData): Promise<ApiResponse<{ id: number }>> => {
  const { backendUrl } = getConfig();
  return doFetch<ApiResponse<{ id: number }>>(`${backendUrl}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(feedback),
  });
};

export const fetchFeedbacks = (): Promise<FeedbackResponse[]> => {
  const { backendUrl } = getConfig();
  return doFetch<FeedbackResponse[]>(`${backendUrl}/feedback`);
};

// MinIO Browser API
export interface MinioListResponse {
  prefixes: string[];
  files: string[];
}

export interface MinioObjectInfo {
  key: string;
  size: number;
}

export interface ParquetPreview {
  schema: Record<string, string>;
  rows: Record<string, unknown>[];
}

export const minioList = (prefix = ""): Promise<MinioListResponse> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/minio/ls`);
  if (prefix) url.searchParams.set('prefix', prefix);
  return doFetch<MinioListResponse>(url.toString());
};

export const minioFind = (prefix = ""): Promise<MinioObjectInfo[]> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/minio/find`);
  if (prefix) url.searchParams.set('prefix', prefix);
  return doFetch<MinioObjectInfo[]>(url.toString());
};

export const minioPreviewParquet = (key: string, limit = 50): Promise<ParquetPreview> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/minio/preview`);
  url.searchParams.set('key', key);
  url.searchParams.set('limit', String(limit));
  return doFetch<ParquetPreview>(url.toString());
};

// Normalization Rules API
export interface NormalizationRule {
  id: number;
  raw_key: string;
  canonical_key: string;
  enabled: boolean;
  applied_count?: number;
  last_applied_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface NormalizationRuleCreatePayload {
  raw_key: string;
  canonical_key: string;
  enabled?: boolean;
}

export interface NormalizationRuleUpdatePayload {
  canonical_key?: string;
  enabled?: boolean;
}

export const listNormalizationRules = (): Promise<NormalizationRule[]> => {
  const { backendUrl } = getConfig();
  return doFetch<NormalizationRule[]>(`${backendUrl}/normalization/`);
};

export const createNormalizationRule = (
  payload: NormalizationRuleCreatePayload
): Promise<NormalizationRule> => {
  const { backendUrl } = getConfig();
  return doFetch<NormalizationRule>(`${backendUrl}/normalization/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: true, ...payload }),
  });
};

export const updateNormalizationRule = (
  id: number,
  payload: NormalizationRuleUpdatePayload
): Promise<NormalizationRule> => {
  const { backendUrl } = getConfig();
  return doFetch<NormalizationRule>(`${backendUrl}/normalization/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const deleteNormalizationRule = (id: number): Promise<{ status?: string; message?: string }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ status?: string; message?: string }>(`${backendUrl}/normalization/${id}`, {
    method: 'DELETE',
  });
};

// Computations API
export interface ComputationDef {
  id?: number;
  name: string;
  description?: string;
  dataset: string; // 'silver' | 'alerts' | 'sensors'
  definition: Record<string, unknown>;
  enabled?: boolean;
  created_at?: string;
  updated_at?: string;
}

export const listComputations = (): Promise<ComputationDef[]> => {
  const { backendUrl } = getConfig();
  return doFetch<ComputationDef[]>(`${backendUrl}/computations/`);
};

export const createComputation = (payload: ComputationDef): Promise<ComputationDef> => {
  const { backendUrl } = getConfig();
  return doFetch<ComputationDef>(`${backendUrl}/computations/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const updateComputation = (id: number, payload: Partial<ComputationDef>): Promise<ComputationDef> => {
  const { backendUrl } = getConfig();
  return doFetch<ComputationDef>(`${backendUrl}/computations/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const deleteComputation = (id: number): Promise<{ status?: string; message?: string }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ status?: string; message?: string }>(`${backendUrl}/computations/${id}`, { method: 'DELETE' });
};

export const previewComputation = (id: number): Promise<unknown[]> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown[]>(`${backendUrl}/computations/${id}/preview`, {
    method: 'POST',
  });
};

// Computation examples and sources
export interface ComputationExample {
  id: string;
  title: string;
  description?: string;
  dataset: string;
  definition: Record<string, unknown>;
}

export interface ComputationExamplesResponse {
  sources: string[];
  examples: ComputationExample[];
  dsl: { keys: string[]; ops: string[]; notes?: string };
}

export const fetchComputationExamples = (): Promise<ComputationExamplesResponse> => {
  const { backendUrl } = getConfig();
  return doFetch<ComputationExamplesResponse>(`${backendUrl}/computations/examples`);
};

export const fetchComputationSources = (): Promise<{ sources: string[] }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ sources: string[] }>(`${backendUrl}/computations/sources`);
};

export interface ComputationSchemasResponse {
  sources: string[];
  schemas: Record<string, { name: string; type: string }[]>;
}

export const fetchComputationSchemas = (): Promise<ComputationSchemasResponse> => {
  const { backendUrl } = getConfig();
  return doFetch<ComputationSchemasResponse>(`${backendUrl}/computations/schemas`);
};