/** Computations API. */
import { doFetch, getConfig } from './apiCore';
import type { DataSensitivity } from './devicesApi';

export interface ComputationDef {
  id?: number;
  name: string;
  description?: string;
  dataset: string;
  definition: Record<string, unknown>;
  recommended_tile_type?: string;
  enabled?: boolean;
  created_at?: string;
  updated_at?: string;
  created_by?: string;
  updated_by?: string;
  sensitivity?: DataSensitivity;
  source_devices?: string[];
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
  return doFetch(`${backendUrl}/api/computations/${id}/dependencies`);
};

export const previewComputation = (id: number): Promise<unknown[]> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown[]>(`${backendUrl}/api/computations/${id}/preview`, { method: 'POST' });
};

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
  return doFetch<{ example: ComputationExample; result: unknown[]; row_count: number }>(`${backendUrl}/api/computations/examples/${encodeURIComponent(exampleId)}/preview`, { method: 'POST' });
};

export interface SensitivitySourceDevice {
  ingestion_id: string;
  name: string | null;
  sensitivity: DataSensitivity;
}

export interface AnalyzeSensitivityResponse {
  sensitivity: DataSensitivity;
  source_devices: SensitivitySourceDevice[];
  warning: string | null;
  sensitivity_levels: string[];
}

export const analyzeComputationSensitivity = (definition: Record<string, unknown>): Promise<AnalyzeSensitivityResponse> => {
  const { backendUrl } = getConfig();
  return doFetch<AnalyzeSensitivityResponse>(`${backendUrl}/api/computations/analyze-sensitivity`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ definition }),
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
