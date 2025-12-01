/**
 * Auth utilities for API requests.
 * Provides functions to get auth tokens and build auth headers.
 */

import { getConfig } from '../config';

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_KEY = 'user';

// Track ongoing refresh to prevent multiple simultaneous refresh attempts
let refreshPromise: Promise<boolean> | null = null;

// Listeners for auth events (logout, token refresh)
type AuthEventListener = (event: 'logout' | 'tokenRefreshed') => void;
const authEventListeners: Set<AuthEventListener> = new Set();

/**
 * Subscribe to auth events (logout, token refresh).
 * Returns an unsubscribe function.
 */
export function subscribeToAuthEvents(listener: AuthEventListener): () => void {
  authEventListeners.add(listener);
  return () => authEventListeners.delete(listener);
}

/**
 * Notify all listeners of an auth event.
 */
function notifyAuthEvent(event: 'logout' | 'tokenRefreshed') {
  authEventListeners.forEach(listener => {
    try {
      listener(event);
    } catch (err) {
      console.error('Error in auth event listener:', err);
    }
  });
}

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

/**
 * Attempt to refresh the access token using the stored refresh token.
 * Returns true if successful, false otherwise.
 * 
 * This function ensures only one refresh attempt happens at a time.
 */
export async function tryRefreshToken(): Promise<boolean> {
  // If a refresh is already in progress, wait for it
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
      if (!refreshToken) {
        console.log('No refresh token available');
        return false;
      }

      const { backendUrl } = getConfig();
      const response = await fetch(`${backendUrl}/api/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ refresh_token: refreshToken })
      });

      if (!response.ok) {
        console.log('Token refresh failed with status:', response.status);
        return false;
      }

      const data = await response.json();
      if (data.data?.access_token) {
        localStorage.setItem(ACCESS_TOKEN_KEY, data.data.access_token);
        console.log('✅ Token refreshed successfully');
        notifyAuthEvent('tokenRefreshed');
        return true;
      }

      return false;
    } catch (error) {
      console.error('Token refresh error:', error);
      return false;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

/**
 * Clear all auth data and notify listeners.
 * Called when token refresh fails and user needs to re-authenticate.
 */
export function clearAuthData() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  notifyAuthEvent('logout');
}
