import { getConfig } from '../config';
import { Building } from '../models/Building';
import { fetchWithErrorHandling, NetworkError } from '../utils/networkErrorHandler';

export interface SensorData {
  sensorId?: string;
  ingestion_id?: string;
}

// Standard API response wrapper
type ApiResponse<T> = {
  status?: string;
  detail?: string;
  data?: T;
  message?: string;
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

// Enhanced fetch handler with better error handling and development debugging
async function doFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const startTime = Date.now();
  
  try {
    // Use our enhanced fetch with error handling
    const response = await fetchWithErrorHandling(url, options);
    
    let resultRaw: unknown;
    try {
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        resultRaw = await response.json();
      } else {
        const text = await response.text();
        // Try to parse as JSON, fallback to text
        try {
          resultRaw = JSON.parse(text);
        } catch {
          resultRaw = text;
        }
      }
    } catch (parseError) {
      const error = new Error(`Failed to parse response from ${url}`) as NetworkError;
      error.name = 'ParseError';
      error.url = url;
      error.method = options?.method || 'GET';
      
      // Log parsing error in development
      if ((import.meta as any).env?.MODE === 'development') {
        console.error('Response parsing failed:', parseError);
        console.log('Response:', response);
      }
      
      throw error;
    }

    // Normalize to ApiResponse
    const result = resultRaw as ApiResponse<T>;

    // Check for API-level errors in the response
    if (result.status && result.status !== 'success') {
      const errMsg = result.detail ?? `API error on ${url}`;
      const apiError = new Error(errMsg) as NetworkError;
      apiError.name = 'APIError';
      apiError.url = url;
      apiError.method = options?.method || 'GET';
      apiError.response = result;
      throw apiError;
    }

    // Log successful API calls in development
    if ((import.meta as any).env?.MODE === 'development') {
      const duration = Date.now() - startTime;
      console.log(`📡 API Success: ${options?.method || 'GET'} ${url} (${duration}ms)`, {
        request: { url, options },
        response: result,
      });
    }

    // Return the data field if present, otherwise return the raw result
    if (result.data !== undefined) {
      return result.data;
    }

    return resultRaw as T;
    
  } catch (error) {
    // Add additional context to the error
    if (error instanceof Error) {
      const enhancedError = error as NetworkError;
      enhancedError.url = enhancedError.url || url;
      enhancedError.method = enhancedError.method || options?.method || 'GET';
      
      // Add request details for debugging
      if ((import.meta as any).env?.MODE === 'development') {
        (enhancedError as any).requestDetails = {
          url,
          options,
          timestamp: new Date().toISOString(),
          duration: Date.now() - startTime,
        };
      }
    }
    
    throw error;
  }
}

export const fetchSensorData = (partition?: string): Promise<SensorData[]> => {
  const { ingestorUrl } = getConfig();
  if (partition && partition.length > 0) {
    return doFetch<SensorData[]>(`${ingestorUrl}/api/data/${encodeURIComponent(partition)}`);
  }
  return doFetch<SensorData[]>(`${ingestorUrl}/api/data`);
};

export const fetchPartitions = (): Promise<string[]> => {
  const { ingestorUrl } = getConfig();
  return doFetch<string[]>(`${ingestorUrl}/api/partitions`);
};

export const setBufferMaxRows = (maxRows: number): Promise<{ max_rows: number }> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ max_rows: number }>(`${ingestorUrl}/api/buffer/size`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ max_rows: maxRows }),
  });
};

export const fetchAverageTemperature = (): Promise<unknown[]> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown[]>(`${backendUrl}/api/spark/average-temperature`);
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
    processing_metrics?: {
      records_processed: number;
      records_failed: number;
      processing_duration_seconds?: number;
      records_per_second?: number;
      error_rate_percent?: number;
      last_processing_time?: string;
    };
    streaming_metrics?: {
      query_active: boolean;
      query_name?: string;
      last_batch_id?: number;
      input_rows_per_second?: number;
      processing_time_ms?: number;
      batch_duration_ms?: number;
      last_batch_timestamp?: string;
    };
    normalization_stats?: {
      total_rules_applied: number;
      active_rules_count: number;
      field_mappings_applied: number;
      normalization_success_rate?: number;
    };
    data_quality?: {
      schema_compliance_rate?: number;
      unique_ingestion_ids: number;
      ingestion_id_breakdown: Record<string, number>;
      fields_with_data: string[];
      fields_normalized: string[];
    };
  };
  gold: {
    exists: boolean;
    recent_rows: number;
    recent_sensors: number;
  };
}

export const fetchEnrichmentSummary = (minutes = 10): Promise<EnrichmentSummary> => {
  const { backendUrl } = getConfig();
  return doFetch<EnrichmentSummary>(`${backendUrl}/api/spark/enrichment-summary?minutes=${minutes}`);
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
  return doFetch<SparkMasterStatus>(`${backendUrl}/api/spark/master-status`);
};

// Spark Streaming interfaces
export interface SparkStreamSource {
  description: string;
  inputRowsPerSecond: number;
  processedRowsPerSecond: number;
  numInputRows: number;
}

export interface SparkStreamSink {
  description: string;
  numOutputRows: number;
}

export interface SparkStream {
  id: string;
  name: string;
  runId: string;
  isActive: boolean;
  status: string;
  inputRowsPerSecond?: number;
  processedRowsPerSecond?: number;
  batchDuration?: number;
  timestamp?: string;
  batchId?: number;
  numInputRows?: number;
  sources?: SparkStreamSource[];
  sink?: SparkStreamSink;
  exception?: string;
  progressError?: string;
}

export interface SparkManagedStream {
  id: string;
  name: string;
  isActive: boolean;
  type: string;
}

export interface SparkStreamsStatus {
  totalActiveStreams: number;
  activeStreams: SparkStream[];
  managedStreams: Record<string, SparkManagedStream>;
  timestamp: number;
  error?: string;
}

export const fetchSparkStreamsStatus = (): Promise<SparkStreamsStatus> => {
  const { backendUrl } = getConfig();
  return doFetch<SparkStreamsStatus>(`${backendUrl}/api/spark/streams-status`);
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
  return doFetch<EnrichmentDiagnosticData>(`${backendUrl}/api/spark/diagnose/enrichment-filtering`);
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
    total_messages_in_buffers: number;
    note: string;
    active_broker?: string;
    subscribed_topic?: string;
  };
}

export const fetchIngestorTopicAnalysis = (): Promise<IngestorTopicAnalysis> => {
  const { ingestorUrl } = getConfig();
  console.log('Fetching from URL:', `${ingestorUrl}/api/diagnostics/topic-analysis`);

  return doFetch<IngestorTopicAnalysis>(`${ingestorUrl}/api/diagnostics/topic-analysis`)
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
  return doFetch<unknown>(`${backendUrl}/api/buildings`, {
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
    `${backendUrl}/api/spark/temperature-alerts?since_minutes=${sinceMinutes}`
  );
};

export const fetchBuildings = (): Promise<Building[]> => {
  const { backendUrl } = getConfig();
  return doFetch<Building[]>(`${backendUrl}/api/buildings`);
};

export const deleteBuilding = (name: string, lat: number, lng: number): Promise<{ status?: string; message?: string }> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/api/buildings`);
  url.searchParams.set('name', name);
  url.searchParams.set('lat', String(lat));
  url.searchParams.set('lng', String(lng));
  return doFetch<{ status?: string; message?: string }>(url.toString(), { method: 'DELETE' });
};

export const addConnection = (config: unknown): Promise<unknown> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown>(`${backendUrl}/api/addConnection`, {
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

export const submitFeedback = (feedback: FeedbackData): Promise<{ id: number }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ id: number }>(`${backendUrl}/api/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(feedback),
  });
};

export const fetchFeedbacks = (): Promise<FeedbackResponse[]> => {
  const { backendUrl } = getConfig();
  return doFetch<FeedbackResponse[]>(`${backendUrl}/api/feedback`);
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

export interface MinioPaginatedResponse {
  items: MinioObjectInfo[];
  pagination: {
    page: number;
    page_size: number;
    total_items: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

export interface ParquetPreview {
  schema: Record<string, string>;
  rows: Record<string, unknown>[];
}

export const minioList = (prefix = ""): Promise<MinioListResponse> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/api/minio/ls`);
  if (prefix) url.searchParams.set('prefix', prefix);
  return doFetch<MinioListResponse>(url.toString());
};

export interface MinioFindOptions {
  prefix?: string;
  sortBy?: string;
  sortOrder?: string;
  minSize?: number;
  maxSize?: number;
  limit?: number;
  page?: number;
  pageSize?: number;
}

export const minioFind = (options: MinioFindOptions = {}): Promise<MinioPaginatedResponse> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/api/minio/find`);
  
  if (options.prefix) url.searchParams.set('prefix', options.prefix);
  if (options.sortBy) url.searchParams.set('sort_by', options.sortBy);
  if (options.minSize !== undefined && options.minSize > 0) {
    url.searchParams.set('min_size', options.minSize.toString());
  }
  if (options.maxSize !== undefined) {
    url.searchParams.set('max_size', options.maxSize.toString());
  }
  if (options.limit !== undefined) {
    url.searchParams.set('limit', options.limit.toString());
  }
  if (options.page !== undefined) {
    url.searchParams.set('page', options.page.toString());
  }
  if (options.pageSize !== undefined) {
    url.searchParams.set('page_size', options.pageSize.toString());
  }
  
  return doFetch<MinioPaginatedResponse>(url.toString());
};

export const minioSmartFiles = (prefix = "", minSize = 1000): Promise<MinioObjectInfo[]> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/api/minio/smart-files`);
  if (prefix) url.searchParams.set('prefix', prefix);
  url.searchParams.set('minSize', minSize.toString());
  return doFetch<MinioObjectInfo[]>(url.toString());
};

export const minioPreviewParquet = (key: string, limit = 50): Promise<ParquetPreview> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/api/minio/preview`);
  url.searchParams.set('key', key);
  url.searchParams.set('limit', String(limit));
  return doFetch<ParquetPreview>(url.toString());
};

export const minioDeleteObject = (key: string): Promise<{ deleted: number; errors: unknown[] }> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/api/minio/object`);
  url.searchParams.set('key', key);
  return doFetch<{ deleted: number; errors: unknown[] }>(url.toString(), { method: 'DELETE' });
};

export const minioDeleteObjects = (keys: string[]): Promise<{ deleted: number; errors: unknown[] }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ deleted: number; errors: unknown[] }>(`${backendUrl}/api/minio/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keys }),
  });
};

export const minioDeletePrefix = (prefix: string): Promise<{ deleted: number; errors: unknown[] }> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/api/minio/prefix`);
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

export const createNormalizationRule = (
  payload: NormalizationRuleCreatePayload
): Promise<NormalizationRule> => {
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

export const updateNormalizationRule = (
  id: number,
  payload: NormalizationRuleUpdatePayload
): Promise<NormalizationRule> => {
  const { backendUrl } = getConfig();
  return doFetch<NormalizationRule>(`${backendUrl}/api/normalization/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const deleteNormalizationRule = (id: number): Promise<{ status?: string; message?: string }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ status?: string; message?: string }>(`${backendUrl}/api/normalization/${id}`, {
    method: 'DELETE',
  });
};

export const toggleNormalizationRule = (id: number): Promise<NormalizationRule> => {
  const { backendUrl } = getConfig();
  return doFetch<NormalizationRule>(`${backendUrl}/api/normalization/${id}/toggle`, {
    method: 'PATCH',
  });
};

// Value Transformation API
export interface ValueTransformationRule {
  id: number;
  ingestion_id: string | null;
  field_name: string;
  transformation_type: 'filter' | 'aggregate' | 'convert' | 'validate';
  transformation_config: string;
  order_priority: number;
  enabled: boolean;
  applied_count: number;
  last_applied_at: string | null;
  created_by: string;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ValueTransformationRuleCreatePayload {
  ingestion_id?: string | null;
  field_name: string;
  transformation_type: 'filter' | 'aggregate' | 'convert' | 'validate';
  transformation_config: Record<string, any>;  // JSON object, not string
  order_priority?: number;
  enabled?: boolean;
  created_by: string;
}

export interface ValueTransformationRuleUpdatePayload {
  ingestion_id?: string | null;
  field_name?: string;
  transformation_type?: 'filter' | 'aggregate' | 'convert' | 'validate';
  transformation_config?: Record<string, any>;  // JSON object, not string
  order_priority?: number;
  enabled?: boolean;
  updated_by: string;
}

export const listValueTransformationRules = (): Promise<ValueTransformationRule[]> => {
  const { backendUrl } = getConfig();
  return doFetch<ValueTransformationRule[]>(`${backendUrl}/api/value-transformations`);
};

export const createValueTransformationRule = (
  payload: ValueTransformationRuleCreatePayload
): Promise<ValueTransformationRule> => {
  const { backendUrl } = getConfig();
  return doFetch<ValueTransformationRule>(`${backendUrl}/api/value-transformations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: true, ...payload }),
  });
};

export const updateValueTransformationRule = (
  id: number,
  payload: ValueTransformationRuleUpdatePayload
): Promise<ValueTransformationRule> => {
  const { backendUrl } = getConfig();
  return doFetch<ValueTransformationRule>(`${backendUrl}/api/value-transformations/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const deleteValueTransformationRule = (id: number): Promise<{ status?: string; message?: string }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ status?: string; message?: string }>(`${backendUrl}/api/value-transformations/${id}`, {
    method: 'DELETE',
  });
};

export const toggleValueTransformationRule = (id: number): Promise<ValueTransformationRule> => {
  const { backendUrl } = getConfig();
  return doFetch<ValueTransformationRule>(`${backendUrl}/api/value-transformations/${id}/toggle`, {
    method: 'PATCH',
  });
};

export const getValueTransformationTypes = (): Promise<Record<string, any>> => {
  const { backendUrl } = getConfig();
  return doFetch<Record<string, any>>(`${backendUrl}/api/value-transformations/types`);
};

// Computations API
export interface ComputationDef {
  id?: number;
  name: string;
  description?: string;
  dataset: string;
  definition: Record<string, unknown>;
  recommended_tile_type?: string; // 'table' | 'stat' | 'timeseries'
  enabled?: boolean;
  created_at?: string;
  updated_at?: string;
  created_by?: string;
  updated_by?: string;
}

export const listComputations = (): Promise<ComputationDef[]> => {
  const { backendUrl } = getConfig();
  return doFetch<ComputationDef[]>(`${backendUrl}/api/computations`);
};

export const createComputation = (payload: ComputationDef): Promise<ComputationDef> => {
  const { backendUrl } = getConfig();
  return doFetch<ComputationDef>(`${backendUrl}/api/computations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const updateComputation = (id: number, payload: Partial<ComputationDef>): Promise<ComputationDef> => {
  const { backendUrl } = getConfig();
  return doFetch<ComputationDef>(`${backendUrl}/api/computations/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const deleteComputation = (id: number): Promise<{ status?: string; message?: string }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ status?: string; message?: string }>(`${backendUrl}/api/computations/${id}`, { method: 'DELETE' });
};

export const checkComputationDependencies = (id: number): Promise<{
  computation: { id: number; name: string };
  dependent_tiles: Array<{ id: number; name: string; viz_type: string; enabled: boolean }>;
  can_delete: boolean;
  has_dependencies: boolean;
}> => {
  const { backendUrl } = getConfig();
  return doFetch<{
    computation: { id: number; name: string };
    dependent_tiles: Array<{ id: number; name: string; viz_type: string; enabled: boolean }>;
    can_delete: boolean;
    has_dependencies: boolean;
  }>(`${backendUrl}/api/computations/${id}/dependencies`);
};

export const previewComputation = (id: number): Promise<unknown[]> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown[]>(`${backendUrl}/api/computations/${id}/preview`, {
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
  return doFetch<ComputationExamplesResponse>(`${backendUrl}/api/computations/examples`);
};

export const previewExampleComputation = (exampleId: string): Promise<{ example: ComputationExample; result: unknown[]; row_count: number }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ example: ComputationExample; result: unknown[]; row_count: number }>(`${backendUrl}/api/computations/examples/${encodeURIComponent(exampleId)}/preview`, {
    method: 'POST',
  });
};

export const fetchComputationSources = (): Promise<{ sources: string[] }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ sources: string[] }>(`${backendUrl}/api/computations/sources`);
};

export interface ComputationSchemasResponse {
  sources: string[];
  schemas: Record<string, { name: string; type: string }[]>;
}

export const fetchComputationSchemas = (): Promise<ComputationSchemasResponse> => {
  const { backendUrl } = getConfig();
  return doFetch<ComputationSchemasResponse>(`${backendUrl}/api/computations/schemas`);
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
  return doFetch<DashboardTileDef[]>(`${backendUrl}/api/dashboard/tiles`);
};

export const createDashboardTile = (payload: DashboardTileDef): Promise<DashboardTileDef> => {
  const { backendUrl } = getConfig();
  return doFetch<DashboardTileDef>(`${backendUrl}/api/dashboard/tiles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const updateDashboardTile = (id: number, payload: Partial<DashboardTileDef>): Promise<DashboardTileDef> => {
  const { backendUrl } = getConfig();
  return doFetch<DashboardTileDef>(`${backendUrl}/api/dashboard/tiles/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const deleteDashboardTile = (id: number): Promise<{ status?: string; message?: string }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ status?: string; message?: string }>(`${backendUrl}/api/dashboard/tiles/${id}`, { method: 'DELETE' });
};

export const previewDashboardTile = (id: number): Promise<unknown[]> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown[]>(`${backendUrl}/api/dashboard/tiles/${id}/preview`, {
    method: 'POST',
  });
};

export const previewDashboardTileConfig = (tileConfig: {
  computation_id: number;
  viz_type: string;
  config: any;
}): Promise<unknown[]> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown[]>(`${backendUrl}/api/dashboard/tiles/preview`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(tileConfig),
  });
};

export interface DashboardTileExamplesResponse {
  examples: { id: string; title: string; tile: Omit<DashboardTileDef, 'id'> }[];
  vizTypes: string[];
}

export const fetchDashboardTileExamples = (): Promise<DashboardTileExamplesResponse> => {
  const { backendUrl } = getConfig();
  return doFetch<DashboardTileExamplesResponse>(`${backendUrl}/api/dashboard/examples`);
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
  created_by?: string;
  updated_by?: string;
}

export const listDevices = (): Promise<Device[]> => {
  const { backendUrl } = getConfig();
  return doFetch<Device[]>(`${backendUrl}/api/devices`);
};

export const registerDevice = (payload: { ingestion_id: string; sensor_id?: string; name?: string; description?: string; enabled?: boolean; created_by: string }): Promise<Device> => {
  const { backendUrl } = getConfig();
  return doFetch<Device>(`${backendUrl}/api/devices`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: true, ...payload }),
  });
};

export const updateDevice = (id: number, payload: { name?: string; description?: string; enabled?: boolean; updated_by: string }): Promise<Device> => {
  const { backendUrl } = getConfig();
  return doFetch<Device>(`${backendUrl}/api/devices/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const deleteDevice = (id: number): Promise<{ status?: string; message?: string }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ status?: string; message?: string }>(`${backendUrl}/api/devices/${id}`, { method: 'DELETE' });
};

export const toggleDevice = (id: number): Promise<Device> => {
  const { backendUrl } = getConfig();
  return doFetch<Device>(`${backendUrl}/api/devices/${id}/toggle`, { method: 'POST' });
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
  return doFetch<SensorIdsResponse>(`${backendUrl}/api/troubleshooting/sensor-ids?${params}`);
};

// Settings API
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
  return doFetch<{ status?: string; message?: string }>(`${backendUrl}/api/settings/${encodeURIComponent(key)}`, {
    method: 'DELETE',
  });
};

// Normalization Preview API
export interface NormalizationPreviewSampleData {
  status: string;
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
  original_data: any[];
  normalized_data: any[];
  applied_rules: any[];
  column_mappings: Record<string, string>;
  unmapped_columns: string[];
  available_columns: string[];
}

export const getNormalizationSampleData = (
  ingestionId?: string,
  limit: number = 100
): Promise<NormalizationPreviewSampleData> => {
  const { backendUrl } = getConfig();
  const params = new URLSearchParams({ limit: limit.toString() });
  if (ingestionId) {
    params.append('ingestion_id', ingestionId);
  }
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

export const validateNormalizationRules = (payload: {
  rules: Array<{ raw_key: string; canonical_key: string; ingestion_id?: string }>;
  ingestion_id?: string;
  sample_limit: number;
}): Promise<{ status: string; validation: any }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ status: string; validation: any }>(`${backendUrl}/api/normalization/preview/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const compareNormalizationScenarios = (payload: {
  ingestion_id?: string;
  scenario_a_rules: Array<{ raw_key: string; canonical_key: string; ingestion_id?: string }>;
  scenario_b_rules: Array<{ raw_key: string; canonical_key: string; ingestion_id?: string }>;
  sample_limit: number;
}): Promise<any> => {
  const { backendUrl } = getConfig();
  return doFetch<any>(`${backendUrl}/api/normalization/preview/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

// Error reporting API
export interface ClientErrorRow {
  id: number;
  message: string;
  stack?: string | null;
  url?: string | null;
  component?: string | null;
  context?: string | null;
  severity?: string | null;
  user_agent?: string | null;
  session_id?: string | null;
  extra?: Record<string, unknown> | null;
  created_at?: string | null;
}

export const fetchErrors = (limit: number = 200): Promise<ClientErrorRow[]> => {
  const { backendUrl } = getConfig();
  return doFetch<ClientErrorRow[]>(`${backendUrl}/api/errors/?limit=${limit}`);
};

// Troubleshooting API types
export interface FieldDiagnosticResult {
  sensor_id: string;
  field_name: string;
  minutes_back: number;
  ingestion_id?: string;
  timestamp: string;
  status: string;
  error?: string;
  raw_data_analysis?: {
    found_data: boolean;
    record_count?: number;
    field_variants_found?: string[];
    field_values_sample?: Array<{
      field_variant?: string;
      field?: string;
      value: any;
      type: string;
      timestamp: string;
    }>;
  };
  normalization_analysis?: {
    transformation_applied: boolean;
    field_mapping?: { [raw: string]: string };
    normalized_values?: Array<{
      raw_field: string;
      canonical_field: string;
      before_values: any[];
      after_values: any[];
      values_match: boolean[];
    }>;
  };
  enrichment_analysis?: {
    found_in_enriched: boolean;
    record_count?: number;
    field_in_sensor_data?: boolean;
    field_in_normalized_data?: boolean;
    union_schema_analysis?: {
      field_values_found?: Array<{
        field_variant?: string;
        field?: string;
        value: any;
        type: string;
        timestamp: string;
      }>;
    };
  };
  gold_analysis?: {
    found_in_gold: boolean;
    record_count?: number;
    field_aggregations?: {
      [field: string]: {
        count: number;
        min_value: number;
        max_value: number;
        avg_value: number;
      };
    };
  };
  recommendations: string[];
}

export interface PipelineTraceResult {
  sensor_id: string;
  minutes_back: number;
  timestamp: string;
  status: string;
  error?: string;
  pipeline_stages: {
    [stage: string]: {
      record_count?: number;
      columns?: string[];
      sample_records?: any[];
      error?: string;
    };
  };
}

export const diagnoseField = (
  sensorId: string,
  fieldName: string,
  minutesBack: number,
  ingestionId?: string
): Promise<FieldDiagnosticResult> => {
  const { backendUrl } = getConfig();
  return doFetch<FieldDiagnosticResult>(`${backendUrl}/api/troubleshooting/diagnose-field`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sensor_id: sensorId,
      field_name: fieldName,
      minutes_back: minutesBack,
      ingestion_id: ingestionId
    })
  });
};

export const tracePipeline = (
  sensorId: string,
  minutesBack: number
): Promise<PipelineTraceResult> => {
  const { backendUrl } = getConfig();
  return doFetch<PipelineTraceResult>(`${backendUrl}/api/troubleshooting/trace-pipeline`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sensor_id: sensorId,
      minutes_back: minutesBack
    })
  });
};

// Copilot API interfaces and functions
export interface ComputationRequest {
  user_prompt: string;
  context?: string;
  preferred_dataset?: string;
}

export interface ComputationSuggestion {
  title: string;
  description: string;
  dataset: string;
  definition: Record<string, unknown>; // Changed from string to object to match backend
  confidence: number;
  explanation: string;
  suggested_columns: string[];
}

export const generateComputationWithCopilot = (request: ComputationRequest): Promise<ComputationSuggestion> => {
  const { backendUrl } = getConfig();
  return doFetch<ComputationSuggestion>(`${backendUrl}/api/copilot/generate-computation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
};

export const getCopilotContext = (): Promise<any> => {
  const { backendUrl } = getConfig();
  return doFetch<any>(`${backendUrl}/api/copilot/context`);
};

export const getCopilotHealth = (): Promise<{available: boolean; reason?: string; endpoint?: string}> => {
  const { backendUrl } = getConfig();
  return doFetch<{available: boolean; reason?: string; endpoint?: string}>(`${backendUrl}/api/copilot/health`);
};

// Data Sources API - New modular data source management
import { 
  DataSourceType, 
  DataSource, 
  CreateDataSourceRequest, 
  UpdateDataSourceRequest,
  DataSourceHealth,
  ConnectorStatusOverview
} from '../types/dataSource';

export const fetchDataSourceTypes = (): Promise<DataSourceType[]> => {
  const { ingestorUrl } = getConfig();
  return doFetch<DataSourceType[]>(`${ingestorUrl}/api/data-sources/types`);
};

export const fetchDataSources = (enabledOnly: boolean = true): Promise<DataSource[]> => {
  const { ingestorUrl } = getConfig();
  const url = new URL(`${ingestorUrl}/api/data-sources`);
  if (enabledOnly) url.searchParams.set('enabled_only', 'true');
  return doFetch<DataSource[]>(url.toString());
};

export const getDataSource = (id: number): Promise<DataSource> => {
  const { ingestorUrl } = getConfig();
  return doFetch<DataSource>(`${ingestorUrl}/api/data-sources/${id}`);
};

export const createDataSource = (payload: CreateDataSourceRequest): Promise<DataSource> => {
  const { ingestorUrl } = getConfig();
  return doFetch<DataSource>(`${ingestorUrl}/api/data-sources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ created_by: 'frontend-user', ...payload }),
  });
};

export const updateDataSource = (id: number, payload: UpdateDataSourceRequest): Promise<DataSource> => {
  const { ingestorUrl } = getConfig();
  return doFetch<DataSource>(`${ingestorUrl}/api/data-sources/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const deleteDataSource = (id: number): Promise<{ status: string; message: string }> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ status: string; message: string }>(`${ingestorUrl}/api/data-sources/${id}`, {
    method: 'DELETE',
  });
};

export const startDataSource = (id: number): Promise<{ status: string; message: string }> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ status: string; message: string }>(`${ingestorUrl}/api/data-sources/${id}/start`, {
    method: 'POST',
  });
};

export const stopDataSource = (id: number): Promise<{ status: string; message: string }> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ status: string; message: string }>(`${ingestorUrl}/api/data-sources/${id}/stop`, {
    method: 'POST',
  });
};

export const restartDataSource = (id: number): Promise<{ status: string; message: string }> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ status: string; message: string }>(`${ingestorUrl}/api/data-sources/${id}/restart`, {
    method: 'POST',
  });
};

export const getDataSourceHealth = (id: number): Promise<DataSourceHealth> => {
  const { ingestorUrl } = getConfig();
  return doFetch<DataSourceHealth>(`${ingestorUrl}/api/data-sources/${id}/health`);
};

export const getConnectorStatusOverview = (): Promise<ConnectorStatusOverview> => {
  const { ingestorUrl } = getConfig();
  return doFetch<ConnectorStatusOverview>(`${ingestorUrl}/api/data-sources/status/overview`);
};

// Metadata API interfaces and functions
export interface SchemaField {
  name: string;
  type: string;
  nullable: boolean;
  sample_values: string[];
}

export interface DatasetMetadata {
  ingestion_id: string;
  topic: string;
  record_count: number;
  first_seen?: string;
  last_seen?: string;
  unique_sensor_count: number;
  unique_sensor_ids: string[];
  data_size_bytes: number;
  schema_fields: SchemaField[];
  created_at?: string;
  updated_at?: string;
}

export interface TopicSummary {
  topic: string;
  dataset_count: number;
  total_records: number;
  total_size_bytes: number;
  total_unique_sensors: number;
  earliest_data?: string;
  latest_data?: string;
}

export interface QualityMetric {
  metric_name: string;
  metric_value: number;
  measurement_time: string;
}

export interface MetadataStats {
  dataset_count: number;
  topic_count: number;
  active_datasets: number;
  total_records: number;
  total_size_bytes: number;
  total_unique_sensors: number;
  size_mb: number;
}

// Get metadata from ingestor service
export const getIngestorMetadataStats = (): Promise<MetadataStats> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ stats: MetadataStats }>(`${ingestorUrl}/api/metadata/stats`)
    .then(response => response.stats);
};

export const getIngestorDatasets = (): Promise<DatasetMetadata[]> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ datasets: DatasetMetadata[] }>(`${ingestorUrl}/api/metadata/datasets`)
    .then(response => response.datasets);
};

export const getIngestorDataset = (ingestionId: string): Promise<DatasetMetadata> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ dataset: DatasetMetadata }>(`${ingestorUrl}/api/metadata/datasets/${ingestionId}`)
    .then(response => response.dataset);
};

export const getIngestorDatasetSchema = (ingestionId: string): Promise<{ingestion_id: string; schema_fields: SchemaField[]; field_count: number}> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ingestion_id: string; schema_fields: SchemaField[]; field_count: number}>(`${ingestorUrl}/api/metadata/datasets/${ingestionId}/schema`);
};

export const getIngestorSchemaEvolution = (ingestionId: string): Promise<any[]> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ evolution: any[] }>(`${ingestorUrl}/api/metadata/datasets/${ingestionId}/evolution`)
    .then(response => response.evolution);
};

export const getIngestorTopicsSummary = (): Promise<TopicSummary[]> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ topics: TopicSummary[] }>(`${ingestorUrl}/api/metadata/topics`)
    .then(response => response.topics);
};

export const getIngestorCurrentMetadata = (): Promise<Record<string, DatasetMetadata>> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ current_metadata: Record<string, DatasetMetadata> }>(`${ingestorUrl}/api/metadata/current`)
    .then(response => response.current_metadata);
};

export const getIngestorQualityMetrics = (ingestionId: string): Promise<QualityMetric[]> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ metrics: QualityMetric[] }>(`${ingestorUrl}/api/metadata/datasets/${ingestionId}/quality`)
    .then(response => response.metrics);
};

export const storeIngestorQualityMetric = (ingestionId: string, metricName: string, metricValue: number): Promise<void> => {
  const { ingestorUrl } = getConfig();
  return doFetch<void>(`${ingestorUrl}/api/metadata/datasets/${ingestionId}/quality`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      metric_name: metricName,
      metric_value: metricValue
    })
  });
};