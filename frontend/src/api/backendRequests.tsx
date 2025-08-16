import { getConfig } from '../config';
import { Building } from '../models/Building';

export interface SensorData {
  sensorId?: string;
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

export const fetchSensorData = (partition?: string): Promise<SensorData[]> => {
  const { ingestorUrl } = getConfig();
  if (partition && partition.length > 0) {
    return doFetch<SensorData[]>(`${ingestorUrl}/data/${encodeURIComponent(partition)}`);
  }
  return doFetch<SensorData[]>(`${ingestorUrl}/data`);
};

export const fetchPartitions = (): Promise<string[]> => {
  const { ingestorUrl } = getConfig();
  return doFetch<string[]>(`${ingestorUrl}/partitions`);
};

export const setBufferMaxRows = (max_rows: number): Promise<{ status?: string; data?: { max_rows: number } }> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ status?: string; data?: { max_rows: number } }>(`${ingestorUrl}/buffer/size`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ max_rows }),
  });
};

export const fetchAverageTemperature = (): Promise<unknown[]> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown[]>(`${backendUrl}/spark/average-temperature`);
};

// Enrichment summary (verification aid)
export interface EnrichmentSummary {
  registered_total: number;
  registered_any_partition: number;
  registered_by_partition: Record<string, number>;
  enriched: {
    exists: boolean;
    recent_rows: number;
    recent_sensors: number;
    sample_sensors: string[];
    matched_sensors: number;
  };
  gold: {
    exists: boolean;
    recent_rows: number;
    recent_sensors: number;
  };
}

export const fetchEnrichmentSummary = (minutes = 10): Promise<EnrichmentSummary> => {
  const { backendUrl } = getConfig();
  return doFetch<EnrichmentSummary>(`${backendUrl}/spark/enrichment-summary?minutes=${minutes}`);
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

// Enrichment Filtering Diagnostic interfaces
export interface EnrichmentDiagnosticDevice {
  id: number;
  ingestion_id: string | null;
  name: string | null;
  enabled: boolean;
  is_wildcard: boolean;
}

export interface EnrichmentDiagnosticData {
  registered_devices: EnrichmentDiagnosticDevice[];
  enriched_data_ingestion_ids: string[];
  enriched_sensors_by_ingestion_id: Record<string, string[]>;
  total_enriched_sensors: number;
  potential_issues: string[];
}

export const fetchEnrichmentDiagnostic = (): Promise<EnrichmentDiagnosticData> => {
  const { backendUrl } = getConfig();
  return doFetch<EnrichmentDiagnosticData>(`${backendUrl}/spark/diagnose/enrichment-filtering`);
};

// Ingestor Topic Analysis interfaces
export interface IngestorTopicAnalysis {
  total_partitions: number;
  partitions: Record<string, {
    message_count: number;
    topics_seen: string[];
    sensor_ids_seen: string[];
    sample_recent_messages: any[];
    status?: string;
  }>;
  topic_to_ingestion_id_mapping: Record<string, string[]>;
  sensor_types_by_partition: Record<string, any>;
  buffer_status: {
    max_rows_per_partition: number;
    active_connections: number;
    mqtt_handler_active: boolean;
    total_messages_in_buffers: number;
    active_broker?: string;
    subscribed_topic?: string;
  };
}

export const fetchIngestorTopicAnalysis = (): Promise<IngestorTopicAnalysis> => {
  const { ingestorUrl } = getConfig();
  console.log('Fetching from URL:', `${ingestorUrl}/diagnostics/topic-analysis`);
  
  return doFetch<IngestorTopicAnalysis>(`${ingestorUrl}/diagnostics/topic-analysis`)
    .then(response => {
      console.log('Processed API response:', response);
      return response;
    })
    .catch(error => {
      console.error('API call failed:', error);
      throw error;
    });
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

export const deleteBuilding = (name: string, lat: number, lng: number): Promise<{ status?: string; message?: string }> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/buildings`);
  url.searchParams.set('name', name);
  url.searchParams.set('lat', String(lat));
  url.searchParams.set('lng', String(lng));
  return doFetch<{ status?: string; message?: string }>(url.toString(), { method: 'DELETE' });
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

export const minioDeleteObject = (key: string): Promise<{ deleted: number; errors: unknown[] }> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/minio/object`);
  url.searchParams.set('key', key);
  return doFetch<{ deleted: number; errors: unknown[] }>(url.toString(), { method: 'DELETE' });
};

export const minioDeleteObjects = (keys: string[]): Promise<{ deleted: number; errors: unknown[] }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ deleted: number; errors: unknown[] }>(`${backendUrl}/minio/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keys }),
  });
};

export const minioDeletePrefix = (prefix: string): Promise<{ deleted: number; errors: unknown[] }> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/minio/prefix`);
  url.searchParams.set('prefix', prefix);
  return doFetch<{ deleted: number; errors: unknown[] }>(url.toString(), { method: 'DELETE' });
};

// Normalization Rules API
export interface NormalizationRule {
  id: number;
  ingestion_id?: string | null;
  raw_key: string;
  canonical_key: string;
  enabled: boolean;
  applied_count?: number;
  last_applied_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface NormalizationRuleCreatePayload {
  ingestion_id?: string | null;
  raw_key: string;
  canonical_key: string;
  enabled?: boolean;
}

export interface NormalizationRuleUpdatePayload {
  ingestion_id?: string | null;
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
  dataset: string; // 'gold' | 'silver' | 'bronze'
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

// Dashboard tiles API
export interface DashboardTileDef {
  id?: number;
  name: string;
  computation_id: number;
  viz_type: 'table' | 'stat' | 'timeseries';
  config: Record<string, unknown>;
  layout?: Record<string, unknown> | null;
  enabled?: boolean;
  created_at?: string;
  updated_at?: string;
}

export const listDashboardTiles = (): Promise<DashboardTileDef[]> => {
  const { backendUrl } = getConfig();
  return doFetch<DashboardTileDef[]>(`${backendUrl}/dashboard/tiles`);
};

export const createDashboardTile = (payload: DashboardTileDef): Promise<DashboardTileDef> => {
  const { backendUrl } = getConfig();
  return doFetch<DashboardTileDef>(`${backendUrl}/dashboard/tiles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const updateDashboardTile = (id: number, payload: Partial<DashboardTileDef>): Promise<DashboardTileDef> => {
  const { backendUrl } = getConfig();
  return doFetch<DashboardTileDef>(`${backendUrl}/dashboard/tiles/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const deleteDashboardTile = (id: number): Promise<{ status?: string; message?: string }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ status?: string; message?: string }>(`${backendUrl}/dashboard/tiles/${id}`, { method: 'DELETE' });
};

export const previewDashboardTile = (id: number): Promise<unknown[]> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown[]>(`${backendUrl}/dashboard/tiles/${id}/preview`, {
    method: 'POST',
  });
};

export interface DashboardTileExamplesResponse {
  examples: { id: string; title: string; tile: Omit<DashboardTileDef, 'id'> }[];
  vizTypes: string[];
}

export const fetchDashboardTileExamples = (): Promise<DashboardTileExamplesResponse> => {
  const { backendUrl } = getConfig();
  return doFetch<DashboardTileExamplesResponse>(`${backendUrl}/dashboard/examples`);
};

// Devices API
export interface Device {
  id?: number;
  sensor_id: string;
  ingestion_id?: string;
  name?: string;
  description?: string;
  enabled?: boolean;
  created_at?: string;
  updated_at?: string;
}

export const listDevices = (): Promise<Device[]> => {
  const { backendUrl } = getConfig();
  return doFetch<Device[]>(`${backendUrl}/devices/`);
};

export const registerDevice = (payload: { ingestion_id: string; sensor_id?: string; name?: string; description?: string; enabled?: boolean }): Promise<Device> => {
  const { backendUrl } = getConfig();
  return doFetch<Device>(`${backendUrl}/devices/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: true, ...payload }),
  });
};

export const deleteDevice = (id: number): Promise<{ status?: string; message?: string }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ status?: string; message?: string }>(`${backendUrl}/devices/${id}`, { method: 'DELETE' });
};

export const toggleDevice = (id: number): Promise<Device> => {
  const { backendUrl } = getConfig();
  return doFetch<Device>(`${backendUrl}/devices/${id}/toggle`, { method: 'POST' });
};

// Configuration API
export interface SchemaConfig {
  use_union_schema: boolean;
  schema_type: string;
  message: string;
}

export interface SystemConfig {
  schema: {
    use_union_schema: boolean;
    schema_type: string;
  };
  storage: {
    minio_bucket: string;
    bronze_path: string;
    enriched_path: string;
    gold_temp_avg_path: string;
    gold_alerts_path: string;
  };
  spark: {
    status: string;
    master_host: string;
    workers: any[];
  };
  streaming: {
    enrichment_active: boolean;
    temperature_active: boolean;
    alert_active: boolean;
  };
}

export interface FeatureFlags {
  union_schema: {
    available: boolean;
    description: string;
    benefits: string[];
  };
  legacy_schema: {
    available: boolean;
    description: string;
    benefits: string[];
  };
  dynamic_normalization: {
    available: boolean;
    description: string;
  };
  stream_processing: {
    available: boolean;
    description: string;
  };
}

export const getSchemaConfig = (): Promise<SchemaConfig> => {
  const { backendUrl } = getConfig();
  return doFetch<SchemaConfig>(`${backendUrl}/config/schema`);
};

export const getSystemConfig = (): Promise<SystemConfig> => {
  const { backendUrl } = getConfig();
  return doFetch<SystemConfig>(`${backendUrl}/config/`);
};

export const getFeatureFlags = (): Promise<FeatureFlags> => {
  const { backendUrl } = getConfig();
  return doFetch<FeatureFlags>(`${backendUrl}/config/features`);
};

// Troubleshooting interfaces and functions
export interface SensorIdsResponse {
  bronze_sensors: string[];
  enriched_sensors: string[];
  gold_sensors: string[];
  total_unique_sensors: number;
  all_sensors: string[];
  timestamp: string;
  error?: string;
}

export const fetchAvailableSensorIds = (limit: number = 100, minutesBack: number = 1440): Promise<SensorIdsResponse> => {
  const { backendUrl } = getConfig();
  const params = new URLSearchParams({
    limit: limit.toString(),
    minutes_back: minutesBack.toString()
  });
  return doFetch<SensorIdsResponse>(`${backendUrl}/api/v1/troubleshooting/sensor-ids?${params}`);
};