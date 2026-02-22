/** Dashboard tiles API. */
import { doFetch, getConfig } from './apiCore';
import type { DataSensitivity } from './devicesApi';

export interface DashboardTileDef {
  id?: number;
  name: string;
  computation_id: number;
  viz_type: 'table' | 'stat' | 'timeseries';
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: Record<string, any>;
  layout?: Record<string, unknown> | null;
  enabled?: boolean;
  created_at?: string;
  updated_at?: string;
  sensitivity?: DataSensitivity;
  access_restricted?: boolean;
  restriction_message?: string;
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
  return doFetch<unknown[]>(`${backendUrl}/api/dashboard/tiles/${id}/preview`, { method: 'POST' });
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const previewDashboardTileConfig = (tileConfig: { computation_id: number; viz_type: string; config: any }): Promise<unknown[]> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown[]>(`${backendUrl}/api/dashboard/tiles/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
