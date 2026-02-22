/** Value transformation rules API. */
import { doFetch, getConfig } from './apiCore';

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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  transformation_config: Record<string, any>;
  order_priority?: number;
  enabled?: boolean;
  created_by: string;
}

export interface ValueTransformationRuleUpdatePayload {
  ingestion_id?: string | null;
  field_name?: string;
  transformation_type?: 'filter' | 'aggregate' | 'convert' | 'validate';
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  transformation_config?: Record<string, any>;
  order_priority?: number;
  enabled?: boolean;
  updated_by: string;
}

export const listValueTransformationRules = (): Promise<ValueTransformationRule[]> => {
  const { backendUrl } = getConfig();
  return doFetch<ValueTransformationRule[]>(`${backendUrl}/api/value-transformations`);
};

export const createValueTransformationRule = (payload: ValueTransformationRuleCreatePayload): Promise<ValueTransformationRule> => {
  const { backendUrl } = getConfig();
  return doFetch<ValueTransformationRule>(`${backendUrl}/api/value-transformations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: true, ...payload }),
  });
};

export const updateValueTransformationRule = (id: number, payload: ValueTransformationRuleUpdatePayload): Promise<ValueTransformationRule> => {
  const { backendUrl } = getConfig();
  return doFetch<ValueTransformationRule>(`${backendUrl}/api/value-transformations/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

export const deleteValueTransformationRule = (id: number): Promise<{ status?: string; message?: string }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ status?: string; message?: string }>(`${backendUrl}/api/value-transformations/${id}`, { method: 'DELETE' });
};

export const toggleValueTransformationRule = (id: number): Promise<ValueTransformationRule> => {
  const { backendUrl } = getConfig();
  return doFetch<ValueTransformationRule>(`${backendUrl}/api/value-transformations/${id}/toggle`, { method: 'PATCH' });
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const getValueTransformationTypes = (): Promise<Record<string, any>> => {
  const { backendUrl } = getConfig();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return doFetch<Record<string, any>>(`${backendUrl}/api/value-transformations/types`);
};
