/** Devices API. */
import { doFetch, getConfig } from './apiCore';

export type DataSensitivity = 'public' | 'internal' | 'confidential' | 'restricted';

export interface SensitivityLevel {
  value: DataSensitivity;
  label: string;
  description: string;
  access: string;
  badge_color: string;
}

export interface Device {
  id?: number;
  sensor_id: string;
  ingestion_id?: string;
  name?: string;
  description?: string;
  enabled?: boolean;
  sensitivity?: DataSensitivity;
  data_retention_days?: number;
  created_at?: string;
  updated_at?: string;
  created_by?: string;
  updated_by?: string;
}

export interface DeviceAuditLog {
  id: number;
  user_id: number;
  username: string;
  device_id?: number;
  device_ingestion_id?: string;
  action: string;
  sensitivity?: DataSensitivity;
  ip_address?: string;
  details?: string;
  created_at: string;
}

export const listDevices = (): Promise<Device[]> => {
  const { backendUrl } = getConfig();
  return doFetch<Device[]>(`${backendUrl}/api/devices`);
};

export const getSensitivityLevels = (): Promise<SensitivityLevel[]> => {
  const { backendUrl } = getConfig();
  return doFetch<SensitivityLevel[]>(`${backendUrl}/api/devices/sensitivity-levels`);
};

export interface RegisterDevicePayload {
  ingestion_id: string;
  sensor_id?: string;
  name?: string;
  description?: string;
  enabled?: boolean;
  sensitivity?: DataSensitivity;
  data_retention_days?: number;
  created_by: string;
}

export const registerDevice = (payload: RegisterDevicePayload): Promise<Device> => {
  const { backendUrl } = getConfig();
  return doFetch<Device>(`${backendUrl}/api/devices`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: true, sensitivity: 'internal', data_retention_days: 90, ...payload }),
  });
};

export interface UpdateDevicePayload {
  name?: string;
  description?: string;
  enabled?: boolean;
  sensitivity?: DataSensitivity;
  data_retention_days?: number;
  updated_by: string;
}

export const updateDevice = (id: number, payload: UpdateDevicePayload): Promise<Device> => {
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
