/** Sensor data, partitions, enrichment summary, and ingestor diagnostics. */
import { doFetch, getConfig, SensorData } from './apiCore';

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
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ max_rows: maxRows }),
  });
};

export const fetchAverageTemperature = (): Promise<unknown[]> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown[]>(`${backendUrl}/api/spark/average-temperature`);
};

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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export interface IngestorTopicAnalysis {
  total_partitions: number;
  partitions: Record<string, {
    message_count: number;
    topics_seen: string[];
    sensor_ids_seen: string[];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    sample_recent_messages: any[];
    status?: string;
  }>;
  topic_to_ingestion_id_mapping: Record<string, string[]>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
  return doFetch<IngestorTopicAnalysis>(`${ingestorUrl}/api/diagnostics/topic-analysis`);
};

export const fetchTemperatureAlerts = (sinceMinutes = 60): Promise<unknown[]> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown[]>(`${backendUrl}/api/spark/temperature-alerts?since_minutes=${sinceMinutes}`);
};
