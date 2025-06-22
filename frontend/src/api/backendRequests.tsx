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
  return doFetch<unknown[]>(`${backendUrl}/averageTemperature`);
};

export const fetchRunningSparkJobs = (): Promise<unknown[]> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown[]>(`${backendUrl}/runningSparkJobs`);
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
    `${backendUrl}/temperatureAlerts?sinceMinutes=${sinceMinutes}`
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