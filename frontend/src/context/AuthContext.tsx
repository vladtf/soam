import React, { createContext, useContext, useEffect, useMemo, useState, useCallback } from 'react';
import { getConfig } from '../config';
import { subscribeToAuthEvents } from '../utils/authUtils';

// User role type
export type UserRole = 'admin' | 'user' | 'viewer';

// User interface
export interface User {
  id: number;
  username: string;
  email: string;
  roles: UserRole[];  // Multiple roles per user
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

// Auth context value type
type AuthContextValue = {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  hasRole: (roles: UserRole[]) => boolean;
  hasAllRoles: (roles: UserRole[]) => boolean;
  isAdmin: boolean;
  refreshToken: () => Promise<boolean>;
  // Legacy support for username-based attribution
  username: string;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_KEY = 'user';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load stored auth data on mount
  useEffect(() => {
    try {
      const storedToken = localStorage.getItem(ACCESS_TOKEN_KEY);
      const storedUser = localStorage.getItem(USER_KEY);
      
      if (storedToken && storedUser) {
        setToken(storedToken);
        setUser(JSON.parse(storedUser));
      }
    } catch (error) {
      console.error('Error loading auth state:', error);
      // Clear invalid data
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Listen for auth events from authUtils (logout, token refresh)
  useEffect(() => {
    const unsubscribe = subscribeToAuthEvents((event) => {
      if (event === 'logout') {
        // Auth was cleared externally (e.g., token refresh failed)
        setToken(null);
        setUser(null);
      } else if (event === 'tokenRefreshed') {
        // Token was refreshed, update local state
        const newToken = localStorage.getItem(ACCESS_TOKEN_KEY);
        if (newToken) {
          setToken(newToken);
        }
      }
    });
    return unsubscribe;
  }, []);

  // Verify token on mount and refresh if needed
  useEffect(() => {
    if (token && user) {
      verifyToken();
    }
  }, []);

  const verifyToken = async () => {
    try {
      const { backendUrl } = getConfig();
      const response = await fetch(`${backendUrl}/api/auth/me`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data.data) {
          setUser(data.data);
          localStorage.setItem(USER_KEY, JSON.stringify(data.data));
        }
      } else if (response.status === 401) {
        // Token expired, try to refresh
        const refreshed = await refreshToken();
        if (!refreshed) {
          logout();
        }
      }
    } catch (error) {
      console.error('Token verification failed:', error);
    }
  };

  const login = useCallback(async (username: string, password: string) => {
    const { backendUrl } = getConfig();
    
    const response = await fetch(`${backendUrl}/api/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ username, password })
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.detail || 'Login failed');
    }
    
    // Store tokens and user data
    localStorage.setItem(ACCESS_TOKEN_KEY, data.data.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, data.data.refresh_token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.data.user));
    
    setToken(data.data.access_token);
    setUser(data.data.user);
  }, []);

  const register = useCallback(async (username: string, email: string, password: string) => {
    const { backendUrl } = getConfig();
    
    const response = await fetch(`${backendUrl}/api/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ username, email, password })
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.detail || 'Registration failed');
    }
    
    // Auto-login after registration
    await login(username, password);
  }, [login]);

  const logout = useCallback(() => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  }, []);

  const refreshToken = useCallback(async (): Promise<boolean> => {
    try {
      const storedRefreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
      if (!storedRefreshToken) {
        return false;
      }

      const { backendUrl } = getConfig();
      const response = await fetch(`${backendUrl}/api/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ refresh_token: storedRefreshToken })
      });
      
      if (!response.ok) {
        return false;
      }
      
      const data = await response.json();
      localStorage.setItem(ACCESS_TOKEN_KEY, data.data.access_token);
      setToken(data.data.access_token);
      
      return true;
    } catch (error) {
      console.error('Token refresh failed:', error);
      return false;
    }
  }, []);

  const hasRole = useCallback((roles: UserRole[]): boolean => {
    if (!user || !user.roles) return false;
    // Check if user has ANY of the specified roles
    return roles.some(role => user.roles.includes(role));
  }, [user]);

  const hasAllRoles = useCallback((roles: UserRole[]): boolean => {
    if (!user || !user.roles) return false;
    // Check if user has ALL of the specified roles
    return roles.every(role => user.roles.includes(role));
  }, [user]);

  const value = useMemo(
    () => ({
      user,
      token,
      isAuthenticated: !!user && !!token,
      isLoading,
      login,
      register,
      logout,
      hasRole,
      hasAllRoles,
      isAdmin: user?.roles?.includes('admin') ?? false,
      refreshToken,
      // Legacy support: use username from user object or 'guest'
      username: user?.username || 'guest',
    }),
    [user, token, isLoading, login, register, logout, hasRole, hasAllRoles, refreshToken]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

// Helper hook to get auth header for API requests
export function useAuthHeader(): () => Record<string, string> {
  const { token } = useAuth();
  
  return useCallback((): Record<string, string> => {
    if (!token) return {};
    return { 'Authorization': `Bearer ${token}` };
  }, [token]);
}
