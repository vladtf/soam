import { getConfig } from '../config';
import { Building } from '../models/Building';

export interface SensorData {
    temperature?: number;
    humidity?: number;
}

export const extractDataSchema = (data: SensorData[]): Record<string, string[]> => {
    const schema: Record<string, string[]> = {};
    data.forEach((sensorData) => {
        Object.keys(sensorData).forEach((key) => {
            schema[key] = ['http://www.w3.org/2001/XMLSchema#float']; // TODO: actual type extraction
        });
    });
    return schema;
};

export const fetchSensorData = async (): Promise<SensorData[]> => {
    const { ingestorUrl } = getConfig();
    const response = await fetch(`${ingestorUrl}/data`);
    const json = await response.json();
    return json;
};

export const fetchAverageTemperature = async (): Promise<any[]> => {
    const { backendUrl } = getConfig();
    const response = await fetch(`${backendUrl}/averageTemperature`);
    const json = await response.json();
    if (json.status === "success") {
        return json.data;
    } else {
        throw new Error(json.detail || "Error fetching average temperature");
    }
};

export const fetchRunningSparkJobs = async (): Promise<any[]> => {
    const { backendUrl } = getConfig();
    const response = await fetch(`${backendUrl}/runningSparkJobs`);
    const json = await response.json();
    if (json.status === "success") {
        return json.data;
    } else {
        throw new Error(json.detail || "Error fetching running Spark jobs");
    }
};

export const postNewBuilding = async (newBuilding: Building) => {
    const { backendUrl } = getConfig();
    const response = await fetch(`${backendUrl}/buildings`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(newBuilding),
    });
    if (!response.ok) {
        throw new Error('Failed to add new building');
    }
    return response.json();
  };

  export const fetchTemperatureAlerts = async (sinceMinutes: number = 60) => {
    const response = await fetch(`${getConfig().backendUrl}/temperatureAlerts?sinceMinutes=${sinceMinutes}`);
    if (!response.ok) {
        throw new Error('Failed to fetch temperature alerts');
    }
    const json = await response.json();
    if (json.status === "success") {
        return json.data;
    } else {
        throw new Error(json.detail || "Error fetching temperature alerts");
    }
  };

  export const fetchConnections = async () => {
    const { ingestorUrl } = getConfig();
    const response = await fetch(`${ingestorUrl}/connections`);
    if (!response.ok) throw new Error('Failed to fetch connections');
    return response.json();
};

export const switchBroker = async (id: number) => {
  const { backendUrl } = getConfig();
  const response = await fetch(`${backendUrl}/switchBroker`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id })
  });
  if (!response.ok) throw new Error('Failed to switch broker');
  return response.json();
};

export const fetchBuildings = async (): Promise<Building[]> => {
  const { backendUrl } = getConfig();
  const response = await fetch(`${backendUrl}/buildings`);
  if (!response.ok) throw new Error('Failed to fetch buildings');
  return response.json();
};

export const addConnection = async (config: any) => {
  const { backendUrl } = getConfig();
  const response = await fetch(`${backendUrl}/addConnection`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  });
  if (!response.ok) throw new Error('Failed to add connection');
  return response.json();
};