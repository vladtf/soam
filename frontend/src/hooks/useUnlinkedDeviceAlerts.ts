import { useEffect } from 'react';
import { useAlerts, AppAlert } from '../context/AlertContext';
import { useAuth } from '../context/AuthContext';
import { doFetch, getConfig } from '../api/apiCore';

/**
 * Fetches alerts from the backend and syncs them into the AlertContext.
 * Mount this once at the app level.
 */
export function useUnlinkedDeviceAlerts() {
  const { syncAlerts } = useAlerts();
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isAuthenticated) return;

    const check = () => {
      const { backendUrl } = getConfig();
      doFetch<AppAlert[]>(`${backendUrl}/api/alerts`)
        .then((alerts) => syncAlerts(alerts))
        .catch(() => { /* alerts are best-effort */ });
    };

    check();
    const interval = setInterval(check, 60_000);
    return () => clearInterval(interval);
  }, [isAuthenticated, syncAlerts]);
}
