/**
 * Core API utilities — shared doFetch, types, and helpers.
 * All domain API modules import from here.
 */
import { getConfig } from '../config';
import { fetchWithErrorHandling, NetworkError } from '../utils/networkErrorHandler';
import { withAuth, tryRefreshToken, clearAuthData } from '../utils/authUtils';
import { logger, isDev } from '../utils/logger';

export { getConfig };

export interface SensorData {
  sensorId?: string;
  ingestion_id?: string;
}

// Standard API response wrapper
type ApiResponse<T> = {
  status?: string;
  detail?: string;
  data?: T;
  message?: string;
};

export const extractDataSchema = (data: SensorData[]): Record<string, string[]> => {
  const schema: Record<string, string[]> = {};
  data.forEach((sensorData) => {
    Object.keys(sensorData).forEach((key) => {
      schema[key] = ['http://www.w3.org/2001/XMLSchema#float'];
    });
  });
  return schema;
};

// Enhanced fetch handler with better error handling, token refresh, and development debugging
// Auth is enabled by default - all requests will include the Authorization header if token is available
export async function doFetch<T>(url: string, options?: RequestInit, useAuth: boolean = true, isRetry: boolean = false): Promise<T> {
  const startTime = Date.now();

  const fetchOptions = useAuth ? withAuth(options) : options;

  try {
    const response = await fetchWithErrorHandling(url, fetchOptions);

    let resultRaw: unknown;
    try {
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        resultRaw = await response.json();
      } else {
        const text = await response.text();
        try {
          resultRaw = JSON.parse(text);
        } catch {
          resultRaw = text;
        }
      }
    } catch (parseError) {
      const error = new Error(`Failed to parse response from ${url}`) as NetworkError;
      error.name = 'ParseError';
      error.url = url;
      error.method = options?.method || 'GET';
      logger.error('doFetch', `Response parsing failed for ${url}`, parseError);
      throw error;
    }

    const result = resultRaw as ApiResponse<T>;

    if (result.status && result.status !== 'success') {
      const errMsg = result.detail ?? `API error on ${url}`;
      const apiError = new Error(errMsg) as NetworkError;
      apiError.name = 'APIError';
      apiError.url = url;
      apiError.method = options?.method || 'GET';
      apiError.response = result;
      throw apiError;
    }

    if (isDev()) {
      const duration = Date.now() - startTime;
      logger.debug('doFetch', `${options?.method || 'GET'} ${url} (${duration}ms)`, result);
    }

    if (result.data !== undefined) {
      return result.data;
    }

    return resultRaw as T;

  } catch (error) {
    if (error instanceof Error && useAuth && !isRetry) {
      const networkError = error as NetworkError;
      if (networkError.status === 401) {
        logger.info('doFetch', 'Attempting to refresh token...');
        const refreshed = await tryRefreshToken();
        if (refreshed) {
          logger.info('doFetch', 'Retrying request with new token...');
          return doFetch<T>(url, options, useAuth, true);
        } else {
          logger.error('doFetch', 'Token refresh failed, logging out...');
          clearAuthData();
        }
      }
    }

    if (error instanceof Error) {
      const enhancedError = error as NetworkError;
      enhancedError.url = enhancedError.url || url;
      enhancedError.method = enhancedError.method || options?.method || 'GET';
      if (isDev()) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (enhancedError as any).requestDetails = {
          url, options,
          timestamp: new Date().toISOString(),
          duration: Date.now() - startTime,
        };
      }
    }
    throw error;
  }
}
