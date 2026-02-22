/** Spark master status, streaming, and worker interfaces. */
import { doFetch, getConfig } from './apiCore';

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
