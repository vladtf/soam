import { useState, useEffect, useCallback, useRef } from 'react';
import { 
  fetchAverageTemperature, 
  fetchSparkMasterStatus, 
  fetchTemperatureAlerts, 
  SparkMasterStatus 
} from '../api/backendRequests';
import { reportClientError } from '../errors';

interface TemperatureData {
  time_start: string;
  avg_temp: number;
  sensorId: string;
}

interface TemperatureAlert {
  sensorId: string;
  temperature: number;
  event_time: string;
}

export const useDashboardData = () => {
  // Temperature data state
  const [averageTemperature, setAverageTemperature] = useState<TemperatureData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshingTemperature, setRefreshingTemperature] = useState<boolean>(false);
  
  // Spark status state
  const [sparkMasterStatus, setSparkMasterStatus] = useState<SparkMasterStatus | null>(null);
  const [loadingSparkStatus, setLoadingSparkStatus] = useState<boolean>(true);
  const [refreshingSparkStatus, setRefreshingSparkStatus] = useState<boolean>(false);
  
  // Temperature alerts state
  const [temperatureAlerts, setTemperatureAlerts] = useState<TemperatureAlert[]>([]);
  const [loadingAlerts, setLoadingAlerts] = useState<boolean>(true);
  const [refreshingAlerts, setRefreshingAlerts] = useState<boolean>(false);
  
  // Time range for temperature data
  const [timeRange, setTimeRange] = useState<number>(24);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);
  
  // Error state
  const [latestError, setLatestError] = useState<unknown>(null);

  // Use refs to track initial loading state
  const hasLoadedTemperature = useRef(false);
  const hasLoadedSparkStatus = useRef(false);
  const hasLoadedAlerts = useRef(false);
  
  // Handle errors when they change
  useEffect(() => {
    if (latestError) {
      console.error('Dashboard data error:', latestError);
      // Implement error handling here if needed, e.g., setError(latestError);
      setLatestError(null); // Clear after handling
    }
  }, [latestError]);

  // Fetch temperature data
  const fetchTemperature = useCallback(async () => {
      if (hasLoadedTemperature.current) {
        setRefreshingTemperature(true);
      } else {
        setLoading(true);
      }
      
      try {
        const data = await fetchAverageTemperature();
        // Format the time_start field for proper display on the X-axis
        const formattedData = (data as TemperatureData[]).map((item) => ({
          ...item,
          time_start: new Date(item.time_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }));
        setAverageTemperature(formattedData);
        hasLoadedTemperature.current = true;
      } catch (error: unknown) {
        // Handle error outside useCallback to avoid dependency
        setLatestError(error);
        reportClientError({ message: String(error), severity: 'error', component: 'useDashboardData', context: 'fetchTemperature' }).catch(() => {});
        // Don't clear existing data on error if we have it
      } finally {
        setLoading(false);
        setRefreshingTemperature(false);
        setLastUpdated(new Date());
      }
    }, []);

  useEffect(() => {
    fetchTemperature();
    if (!autoRefresh) return;
    const interval = setInterval(fetchTemperature, 15000);
    return () => clearInterval(interval);
  }, [autoRefresh]); // Removed fetchTemperature from dependencies

  // Fetch Spark status
  const fetchSparkStatusNow = useCallback(async () => {
      if (hasLoadedSparkStatus.current) {
        setRefreshingSparkStatus(true);
      } else {
        setLoadingSparkStatus(true);
      }
      
      try {
        const data = await fetchSparkMasterStatus();
        setSparkMasterStatus(data);
        hasLoadedSparkStatus.current = true;
      } catch (error: unknown) {
        setLatestError(error);
        reportClientError({ message: String(error), severity: 'error', component: 'useDashboardData', context: 'fetchSparkStatusNow' }).catch(() => {});
        // Don't clear existing data on error if we have it
      } finally {
        setLoadingSparkStatus(false);
        setRefreshingSparkStatus(false);
      }
    }, []);

  useEffect(() => {
    fetchSparkStatusNow();
    if (!autoRefresh) return;
    const interval = setInterval(fetchSparkStatusNow, 15000);
    return () => clearInterval(interval); // Cleanup interval on component unmount
  }, [autoRefresh]); // Removed setError dependency

  // Fetch temperature alerts
  const fetchAlertsNow = useCallback(async () => {
      if (hasLoadedAlerts.current) {
        setRefreshingAlerts(true);
      } else {
        setLoadingAlerts(true);
      }
      
      try {
        const data = await fetchTemperatureAlerts();
        setTemperatureAlerts(data as TemperatureAlert[]);
        hasLoadedAlerts.current = true;
      } catch (error: unknown) {
        setLatestError(error);
        reportClientError({ message: String(error), severity: 'error', component: 'useDashboardData', context: 'fetchAlertsNow' }).catch(() => {});
        // Don't clear existing data on error if we have it
      } finally {
        setLoadingAlerts(false);
        setRefreshingAlerts(false);
      }
    }, []);

  useEffect(() => {
    fetchAlertsNow();
    if (!autoRefresh) return;
    const interval = setInterval(fetchAlertsNow, 15000);
    return () => clearInterval(interval);
  }, [autoRefresh]); // Removed setError dependency

  return {
    // Temperature data
    averageTemperature,
    loading,
    refreshingTemperature,
    timeRange,
    setTimeRange,
    lastUpdated,
    autoRefresh,
    setAutoRefresh,
    refreshAll: async () => {
      await Promise.all([
        fetchTemperature(),
        fetchSparkStatusNow(),
        fetchAlertsNow(),
      ]);
      setLastUpdated(new Date());
    },
    
    // Spark status
    sparkMasterStatus,
    loadingSparkStatus,
    refreshingSparkStatus,
    
    // Temperature alerts
    temperatureAlerts,
    loadingAlerts,
    refreshingAlerts,
    refreshAlerts: fetchAlertsNow
  };
};
