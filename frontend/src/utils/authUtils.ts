/**
 * Auth utilities for API requests.
 * Provides functions to get auth tokens and build auth headers.
 */

const ACCESS_TOKEN_KEY = 'access_token';

/**
 * Get the current access token from localStorage.
 * Returns null if no token is stored.
 */
export function getAccessToken(): string | null {
  try {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  } catch {
    return null;
  }
}

/**
 * Build headers object with Authorization header if token is available.
 * Can be merged with other headers for API requests.
 * 
 * @param additionalHeaders - Additional headers to include
 * @returns Headers object with Authorization header if authenticated
 */
export function getAuthHeaders(additionalHeaders?: Record<string, string>): Record<string, string> {
  const token = getAccessToken();
  const headers: Record<string, string> = { ...additionalHeaders };
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  return headers;
}

/**
 * Build fetch options with auth headers included.
 * 
 * @param options - Base fetch options
 * @returns Fetch options with auth headers merged
 */
export function withAuth(options?: RequestInit): RequestInit {
  const token = getAccessToken();
  
  if (!token) {
    return options || {};
  }
  
  const existingHeaders = options?.headers as Record<string, string> | undefined;
  
  return {
    ...options,
    headers: {
      ...existingHeaders,
      'Authorization': `Bearer ${token}`,
    },
  };
}

/**
 * Check if the user is currently authenticated (has a token stored).
 * This is a simple check and doesn't validate the token.
 */
export function hasStoredToken(): boolean {
  return !!getAccessToken();
}
