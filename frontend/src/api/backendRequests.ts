/**
 * Re-export hub — all domain API modules are re-exported from here
 * so that existing imports throughout the codebase continue to work.
 *
 * Domain modules:
 *   apiCore.ts           — doFetch, SensorData, extractDataSchema
 *   sensorDataApi.ts     — sensor data, partitions, enrichment, diagnostics
 *   sparkApi.ts          — Spark master/streams
 *   buildingsApi.ts      — buildings, ontology graph
 *   feedbackApi.ts       — feedback
 *   minioApi.ts          — MinIO browser
 *   normalizationApi.ts  — normalization rules + preview
 *   transformationsApi.ts— value transformations
 *   computationsApi.ts   — computations
 *   dashboardApi.ts      — dashboard tiles
 *   devicesApi.ts        — devices
 *   configApi.ts         — config + settings
 *   copilotApi.ts        — copilot + error reporting
 *   dataSourcesApi.ts    — data sources + metadata
 *   testUsersApi.ts      — test users
 */

export { extractDataSchema } from './apiCore';
export type { SensorData } from './apiCore';
export * from './sensorDataApi';
export * from './sparkApi';
export * from './buildingsApi';
export * from './feedbackApi';
export * from './minioApi';
export * from './normalizationApi';
export * from './transformationsApi';
export * from './computationsApi';
export * from './dashboardApi';
export * from './devicesApi';
export * from './configApi';
export * from './copilotApi';
export * from './dataSourcesApi';
export * from './testUsersApi';
