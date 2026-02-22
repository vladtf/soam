/** Data sources (ingestor) and metadata API. */
import { doFetch, getConfig } from './apiCore';
import {
  DataSourceType,
  DataSource,
  CreateDataSourceRequest,
  UpdateDataSourceRequest,
  DataSourceHealth,
  ConnectorStatusOverview,
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
  return doFetch<{ status: string; message: string }>(`${ingestorUrl}/api/data-sources/${id}`, { method: 'DELETE' });
};

export const startDataSource = (id: number): Promise<{ status: string; message: string }> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ status: string; message: string }>(`${ingestorUrl}/api/data-sources/${id}/start`, { method: 'POST' });
};

export const stopDataSource = (id: number): Promise<{ status: string; message: string }> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ status: string; message: string }>(`${ingestorUrl}/api/data-sources/${id}/stop`, { method: 'POST' });
};

export const restartDataSource = (id: number): Promise<{ status: string; message: string }> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ status: string; message: string }>(`${ingestorUrl}/api/data-sources/${id}/restart`, { method: 'POST' });
};

export const getDataSourceHealth = (id: number): Promise<DataSourceHealth> => {
  const { ingestorUrl } = getConfig();
  return doFetch<DataSourceHealth>(`${ingestorUrl}/api/data-sources/${id}/health`);
};

export const getConnectorStatusOverview = (): Promise<ConnectorStatusOverview> => {
  const { ingestorUrl } = getConfig();
  return doFetch<ConnectorStatusOverview>(`${ingestorUrl}/api/data-sources/status/overview`);
};

// ── Metadata ────────────────────────────────────────────────────

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

export const getIngestorMetadataStats = (): Promise<MetadataStats> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ stats: MetadataStats }>(`${ingestorUrl}/api/metadata/stats`).then(r => r.stats);
};

export const getIngestorDatasets = (): Promise<DatasetMetadata[]> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ datasets: DatasetMetadata[] }>(`${ingestorUrl}/api/metadata/datasets`).then(r => r.datasets);
};

export const getIngestorDataset = (ingestionId: string): Promise<DatasetMetadata> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ dataset: DatasetMetadata }>(`${ingestorUrl}/api/metadata/datasets/${ingestionId}`).then(r => r.dataset);
};

export const getIngestorDatasetSchema = (ingestionId: string): Promise<{ ingestion_id: string; schema_fields: SchemaField[]; field_count: number }> => {
  const { ingestorUrl } = getConfig();
  return doFetch(`${ingestorUrl}/api/metadata/datasets/${ingestionId}/schema`);
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const getIngestorSchemaEvolution = (ingestionId: string): Promise<any[]> => {
  const { ingestorUrl } = getConfig();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return doFetch<{ evolution: any[] }>(`${ingestorUrl}/api/metadata/datasets/${ingestionId}/evolution`).then(r => r.evolution);
};

export const getIngestorTopicsSummary = (): Promise<TopicSummary[]> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ topics: TopicSummary[] }>(`${ingestorUrl}/api/metadata/topics`).then(r => r.topics);
};

export const getIngestorCurrentMetadata = (): Promise<Record<string, DatasetMetadata>> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ current_metadata: Record<string, DatasetMetadata> }>(`${ingestorUrl}/api/metadata/current`).then(r => r.current_metadata);
};

export const getIngestorQualityMetrics = (ingestionId: string): Promise<QualityMetric[]> => {
  const { ingestorUrl } = getConfig();
  return doFetch<{ metrics: QualityMetric[] }>(`${ingestorUrl}/api/metadata/datasets/${ingestionId}/quality`).then(r => r.metrics);
};

export const storeIngestorQualityMetric = (ingestionId: string, metricName: string, metricValue: number): Promise<void> => {
  const { ingestorUrl } = getConfig();
  return doFetch<void>(`${ingestorUrl}/api/metadata/datasets/${ingestionId}/quality`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ metric_name: metricName, metric_value: metricValue }),
  });
};
