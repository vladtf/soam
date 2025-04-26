import { getConfig } from '../config';

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
