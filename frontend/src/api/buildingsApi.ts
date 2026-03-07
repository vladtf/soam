/** Buildings and ontology / knowledge graph API. */
import { doFetch, getConfig } from './apiCore';
import { Building } from '../models/Building';

export const postNewBuilding = (newBuilding: Building): Promise<unknown> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown>(`${backendUrl}/api/buildings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(newBuilding),
  });
};

export const fetchBuildings = (): Promise<Building[]> => {
  const { backendUrl } = getConfig();
  return doFetch<Building[]>(`${backendUrl}/api/buildings`);
};

export const deleteBuilding = (name: string, lat: number, lng: number): Promise<{ status?: string; message?: string }> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/api/buildings`);
  url.searchParams.set('name', name);
  url.searchParams.set('lat', String(lat));
  url.searchParams.set('lng', String(lng));
  return doFetch<{ status?: string; message?: string }>(url.toString(), { method: 'DELETE' });
};

// ── Ontology / Knowledge Graph API ────────────────────────────

export interface GraphNode {
  id: string;
  labels: string[];
  props: Record<string, unknown>;
}

export interface GraphLink {
  source: string;
  target: string;
  type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export const fetchOntologyGraph = (): Promise<GraphData> => {
  const { backendUrl } = getConfig();
  return doFetch<GraphData>(`${backendUrl}/api/ontology/graph`);
};

export const createCity = (name: string, description = ''): Promise<unknown> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown>(`${backendUrl}/api/ontology/cities`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  });
};

export const createSensorNode = (sensorId: string): Promise<unknown> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown>(`${backendUrl}/api/ontology/sensors`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sensor_id: sensorId }),
  });
};

export const linkBuildingToCity = (buildingName: string, cityName: string): Promise<unknown> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown>(`${backendUrl}/api/ontology/link/building-city`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_name: buildingName, target_name: cityName }),
  });
};

export const linkSensorToBuilding = (sensorId: string, buildingName: string): Promise<unknown> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown>(`${backendUrl}/api/ontology/link/sensor-building`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_name: sensorId, target_name: buildingName }),
  });
};

export const linkSensorToCity = (sensorId: string, cityName: string): Promise<unknown> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown>(`${backendUrl}/api/ontology/link/sensor-city`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_name: sensorId, target_name: cityName }),
  });
};

export const deleteOntologyRelationship = (sourceId: string, targetId: string, relType: string): Promise<unknown> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown>(`${backendUrl}/api/ontology/relationship`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_id: sourceId, target_id: targetId, rel_type: relType }),
  });
};

export const deleteOntologyNode = (nodeId: string): Promise<unknown> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown>(`${backendUrl}/api/ontology/node`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ node_id: nodeId }),
  });
};

export const addConnection = (config: unknown): Promise<unknown> => {
  const { backendUrl } = getConfig();
  return doFetch<unknown>(`${backendUrl}/api/addConnection`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
};

// ── Ontology Schema API ─────────────────────────────────────────

export interface OntologyClassProperty {
  uri: string;
  label: string;
  range: string | null;
  type: 'data' | 'object';
  python_type: string | null;
}

export interface OntologyClass {
  uri: string;
  label: string;
  comment: string;
  subClassOf: string | null;
  properties: OntologyClassProperty[];
}

export interface OntologySchema {
  classes: OntologyClass[];
}

export const fetchOntologySchema = (): Promise<OntologySchema> => {
  const { backendUrl } = getConfig();
  return doFetch<OntologySchema>(`${backendUrl}/api/ontology/schema`);
};

// ── Ontology Query API ──────────────────────────────────────────

export interface QueryTemplate {
  name: string;
  description: string;
  query: string;
  params: string[];
}

export interface QueryResult {
  rows: Record<string, unknown>[];
  count: number;
}

export const fetchQueryTemplates = (): Promise<QueryTemplate[]> => {
  const { backendUrl } = getConfig();
  return doFetch<QueryTemplate[]>(`${backendUrl}/api/ontology/query/templates`);
};

export const executeOntologyQuery = (
  query: string,
  params: Record<string, unknown> = {}
): Promise<QueryResult> => {
  const { backendUrl } = getConfig();
  return doFetch<QueryResult>(`${backendUrl}/api/ontology/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, params }),
  });
};
