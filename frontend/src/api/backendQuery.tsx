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
}

export const fetchSensorData = async (): Promise<SensorData[]> => {
    const { backendUrl } = getConfig();
    const response = await fetch(`${backendUrl}/data`);
    const json = await response.json();
    return json;
}
