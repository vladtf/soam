/** MinIO browser API. */
import { doFetch, getConfig } from './apiCore';

export interface MinioListResponse {
  prefixes: string[];
  files: string[];
}

export interface MinioObjectInfo {
  key: string;
  size: number;
}

export interface MinioPaginatedResponse {
  items: MinioObjectInfo[];
  pagination: {
    page: number;
    page_size: number;
    total_items: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

export interface ParquetPreview {
  schema: Record<string, string>;
  rows: Record<string, unknown>[];
}

export const minioList = (prefix = ""): Promise<MinioListResponse> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/api/minio/ls`);
  if (prefix) url.searchParams.set('prefix', prefix);
  return doFetch<MinioListResponse>(url.toString());
};

export interface MinioFindOptions {
  prefix?: string;
  sortBy?: string;
  sortOrder?: string;
  minSize?: number;
  maxSize?: number;
  limit?: number;
  page?: number;
  pageSize?: number;
}

export const minioFind = (options: MinioFindOptions = {}): Promise<MinioPaginatedResponse> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/api/minio/find`);
  if (options.prefix) url.searchParams.set('prefix', options.prefix);
  if (options.sortBy) url.searchParams.set('sort_by', options.sortBy);
  if (options.minSize !== undefined && options.minSize > 0) url.searchParams.set('min_size', options.minSize.toString());
  if (options.maxSize !== undefined) url.searchParams.set('max_size', options.maxSize.toString());
  if (options.limit !== undefined) url.searchParams.set('limit', options.limit.toString());
  if (options.page !== undefined) url.searchParams.set('page', options.page.toString());
  if (options.pageSize !== undefined) url.searchParams.set('page_size', options.pageSize.toString());
  return doFetch<MinioPaginatedResponse>(url.toString());
};

export const minioSmartFiles = (prefix = "", minSize = 1000): Promise<MinioObjectInfo[]> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/api/minio/smart-files`);
  if (prefix) url.searchParams.set('prefix', prefix);
  url.searchParams.set('minSize', minSize.toString());
  return doFetch<MinioObjectInfo[]>(url.toString());
};

export const minioPreviewParquet = (key: string, limit = 50): Promise<ParquetPreview> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/api/minio/preview`);
  url.searchParams.set('key', key);
  url.searchParams.set('limit', String(limit));
  return doFetch<ParquetPreview>(url.toString());
};

export const minioDeleteObject = (key: string): Promise<{ deleted: number; errors: unknown[] }> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/api/minio/object`);
  url.searchParams.set('key', key);
  return doFetch<{ deleted: number; errors: unknown[] }>(url.toString(), { method: 'DELETE' });
};

export const minioDeleteObjects = (keys: string[]): Promise<{ deleted: number; errors: unknown[] }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ deleted: number; errors: unknown[] }>(`${backendUrl}/api/minio/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keys }),
  });
};

export const minioDeletePrefix = (prefix: string): Promise<{ deleted: number; errors: unknown[] }> => {
  const { backendUrl } = getConfig();
  const url = new URL(`${backendUrl}/api/minio/prefix`);
  url.searchParams.set('prefix', prefix);
  return doFetch<{ deleted: number; errors: unknown[] }>(url.toString(), { method: 'DELETE' });
};
