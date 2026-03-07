import React, { createContext, useContext, useState, useCallback, useRef } from 'react';

export interface AppAlert {
  id: string;
  message: string;
  variant: 'warning' | 'info' | 'danger' | 'success';
  link?: string;
  linkText?: string;
  dismissible?: boolean;
}

interface AlertContextValue {
  alerts: AppAlert[];
  /** Push a batch of alerts from the backend, resetting dismissed state when the set changes. */
  syncAlerts: (incoming: AppAlert[]) => void;
  dismissAlert: (id: string) => void;
  clearAlerts: () => void;
}

const AlertContext = createContext<AlertContextValue | undefined>(undefined);

export const AlertProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [alerts, setAlerts] = useState<AppAlert[]>([]);
  const dismissedRef = useRef<Set<string>>(new Set());
  const prevIdsRef = useRef<string>('');

  const syncAlerts = useCallback((incoming: AppAlert[]) => {
    // Build a fingerprint of the incoming alert IDs
    const incomingIds = incoming.map((a) => a.id).sort().join(',');

    // If the set of alerts changed, clear dismissed state
    if (incomingIds !== prevIdsRef.current) {
      dismissedRef.current = new Set();
      prevIdsRef.current = incomingIds;
    }

    // Filter out dismissed alerts
    const visible = incoming.filter((a) => !dismissedRef.current.has(a.id));
    setAlerts(visible);
  }, []);

  const dismissAlert = useCallback((id: string) => {
    dismissedRef.current.add(id);
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const clearAlerts = useCallback(() => {
    dismissedRef.current = new Set();
    prevIdsRef.current = '';
    setAlerts([]);
  }, []);

  return (
    <AlertContext.Provider value={{ alerts, syncAlerts, dismissAlert, clearAlerts }}>
      {children}
    </AlertContext.Provider>
  );
};

export function useAlerts(): AlertContextValue {
  const ctx = useContext(AlertContext);
  if (!ctx) throw new Error('useAlerts must be used within AlertProvider');
  return ctx;
}
